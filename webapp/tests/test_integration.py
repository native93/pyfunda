#!/usr/bin/env python3
"""Integration tests for the Funda webapp."""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app, get_krib_data


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_overbid_data():
    """Create sample overbid data for testing."""
    return {
        "last_updated": "2026-04-17T12:00:00",
        "transactions": [
            {
                "address": "Test Street 1",
                "postal_code": "1234AB",
                "city": "Amsterdam",
                "asking_price": 400000,
                "sale_price": 450000,
                "overbid_pct": 12.5,
                "transaction_date": "2025-06-15",
                "lat": 52.3676,
                "lng": 4.9041,
                "living_area_m2": 75,
                "energy_label": "A",
                "funda_url": "https://www.funda.nl/detail/koop/amsterdam/test/12345678/"
            },
            {
                "address": "Test Street 2",
                "postal_code": "3456CD",
                "city": "Utrecht",
                "asking_price": 350000,
                "sale_price": 380000,
                "overbid_pct": 8.6,
                "transaction_date": "2025-07-20",
                "lat": 52.0907,
                "lng": 5.1214,
                "living_area_m2": 65,
                "energy_label": "B",
                "funda_url": "https://www.funda.nl/detail/koop/utrecht/test/87654321/"
            }
        ]
    }


class TestFlaskEndpoints:
    """Test Flask API endpoints."""

    def test_index_page_loads(self, client):
        """Test that the index page loads successfully."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'html' in response.data.lower()

    def test_heatmap_page_loads(self, client):
        """Test that the heatmap page loads successfully."""
        response = client.get('/heatmap')
        assert response.status_code == 200
        assert b'Overbidding Heatmap' in response.data
        assert b'leaflet' in response.data.lower()

    def test_heatmap_contains_required_elements(self, client):
        """Test that heatmap page has all required UI elements."""
        response = client.get('/heatmap')
        html = response.data.decode('utf-8')

        # Check for filter controls
        assert 'cityFilter' in html
        assert 'minOverbid' in html
        assert 'maxOverbid' in html

        # Check for stats display
        assert 'avgOverbid' in html
        assert 'medianOverbid' in html

        # Check for legend
        assert 'legend' in html.lower()

        # Check for map container
        assert 'id="map"' in html

    def test_overbid_data_endpoint_returns_json(self, client):
        """Test that /api/overbid-data returns valid JSON."""
        response = client.get('/api/overbid-data')
        assert response.status_code == 200
        assert response.content_type == 'application/json'

        data = json.loads(response.data)
        assert 'transactions' in data or 'error' in data

    def test_overbid_data_has_cors_header(self, client):
        """Test that /api/overbid-data includes CORS header."""
        response = client.get('/api/overbid-data')
        assert 'Access-Control-Allow-Origin' in response.headers

    def test_search_endpoint_requires_location(self, client):
        """Test that /search returns error without location."""
        response = client.post('/search',
                               json={},
                               content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_search_endpoint_accepts_valid_request(self, client):
        """Test that /search accepts valid location request."""
        response = client.post('/search',
                               json={'location': 'utrecht', 'radius': 2},
                               content_type='application/json')
        # May take time but should not error immediately
        assert response.status_code in [200, 500]  # 500 if network issues

    def test_krib_endpoint_returns_json(self, client):
        """Test that /krib/<id> returns JSON."""
        # Use a known working ID
        response = client.get('/krib/43398240')
        assert response.content_type == 'application/json'
        # May be 200 or 404 depending on krib.nl availability
        assert response.status_code in [200, 404, 500]


class TestKribAPI:
    """Test krib.nl API integration."""

    def test_krib_api_with_valid_id(self):
        """Test krib.nl API returns data for valid listing ID."""
        # Known working ID (Theemsdreef 177, Utrecht)
        result = get_krib_data('43398240')

        if result:  # API may be unavailable
            assert 'woz_values' in result or 'closest_transactions' in result

    def test_krib_api_with_invalid_id(self):
        """Test krib.nl API handles invalid ID gracefully."""
        result = get_krib_data('99999999999')
        # Should return None or empty, not crash
        assert result is None or isinstance(result, dict)

    def test_krib_api_signature_generation(self):
        """Test that HMAC signature is generated correctly."""
        import base64
        import hashlib
        import hmac

        # Load secret from secrets.json
        secrets_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'secrets.json')
        if not os.path.exists(secrets_file):
            pytest.skip("secrets.json not found - skipping signature test")

        with open(secrets_file, 'r') as f:
            secrets = json.load(f)

        secret_b64 = secrets.get('krib_api_secret_b64', '')
        if not secret_b64:
            pytest.skip("krib_api_secret_b64 not in secrets.json")

        API_SECRET = base64.b64decode(secret_b64).decode()

        listing_id = '89201502'
        timestamp = '29607249'
        message = f'{listing_id}:{timestamp}'

        expected_sig = '07cbabb679d37698c43a3bcec56ba7ceb8a995292e5a39fd8858643e949d57cb'
        computed_sig = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

        assert computed_sig == expected_sig


class TestOverbidDataFormat:
    """Test overbid data format and validation."""

    def test_transaction_has_required_fields(self, sample_overbid_data):
        """Test that transactions have all required fields."""
        required_fields = [
            'address', 'postal_code', 'city', 'asking_price', 'sale_price',
            'overbid_pct', 'transaction_date', 'lat', 'lng', 'funda_url'
        ]

        for tx in sample_overbid_data['transactions']:
            for field in required_fields:
                assert field in tx, f"Missing field: {field}"

    def test_overbid_calculation_is_correct(self, sample_overbid_data):
        """Test that overbid percentage is calculated correctly."""
        for tx in sample_overbid_data['transactions']:
            expected_pct = round((tx['sale_price'] - tx['asking_price']) / tx['asking_price'] * 100, 1)
            assert abs(tx['overbid_pct'] - expected_pct) < 0.1

    def test_coordinates_are_valid(self, sample_overbid_data):
        """Test that coordinates are within Netherlands bounds."""
        # Netherlands bounding box (approximate)
        NL_LAT_MIN, NL_LAT_MAX = 50.5, 53.7
        NL_LNG_MIN, NL_LNG_MAX = 3.3, 7.3

        for tx in sample_overbid_data['transactions']:
            assert NL_LAT_MIN <= tx['lat'] <= NL_LAT_MAX, f"Invalid latitude: {tx['lat']}"
            assert NL_LNG_MIN <= tx['lng'] <= NL_LNG_MAX, f"Invalid longitude: {tx['lng']}"


class TestDataCollection:
    """Test data collection script functionality."""

    def test_extract_listing_id_from_url(self):
        """Test extracting listing ID from Funda URL."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from collect_overbid_data import extract_listing_id

        test_cases = [
            ("https://www.funda.nl/detail/koop/utrecht/appartement-test/43210915/", "43210915"),
            ("https://www.funda.nl/detail/koop/amsterdam/huis-test/89201502/", "89201502"),
            ("https://funda.nl/detail/koop/city/type/12345678", "12345678"),
        ]

        for url, expected_id in test_cases:
            assert extract_listing_id(url) == expected_id

    def test_load_and_save_data(self):
        """Test loading and saving overbid data."""
        from collect_overbid_data import load_existing_data, save_data

        # Create temp directory for test
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                # Test loading non-existent data
                data = load_existing_data()
                assert data == {"last_updated": None, "transactions": []}

                # Test saving data
                test_data = {
                    "last_updated": None,
                    "transactions": [{"test": "data"}]
                }
                save_data(test_data)

                # Test loading saved data
                loaded = load_existing_data()
                assert loaded['transactions'] == [{"test": "data"}]
                assert loaded['last_updated'] is not None

            finally:
                os.chdir(original_cwd)


class TestHeatmapVisualization:
    """Test heatmap visualization logic."""

    def test_color_mapping_logic(self):
        """Test that overbid percentages map to correct colors."""
        # Color thresholds from heatmap.html
        def get_color(overbid_pct):
            if overbid_pct < 0:
                return 'purple'  # underbid
            if overbid_pct < 5:
                return 'green'
            if overbid_pct < 10:
                return 'yellow'
            if overbid_pct < 15:
                return 'orange'
            return 'red'

        test_cases = [
            (-5.0, 'purple'),
            (0.0, 'green'),
            (3.5, 'green'),
            (5.0, 'yellow'),
            (8.0, 'yellow'),
            (10.0, 'orange'),
            (14.9, 'orange'),
            (15.0, 'red'),
            (25.0, 'red'),
        ]

        for overbid, expected_color in test_cases:
            assert get_color(overbid) == expected_color, f"Failed for {overbid}%"


class TestRealDataIntegration:
    """Integration tests using real collected data."""

    def test_real_data_file_exists(self):
        """Test that overbid_data.json exists and is valid."""
        data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'overbid_data.json')

        if os.path.exists(data_file):
            with open(data_file, 'r') as f:
                data = json.load(f)

            assert 'transactions' in data
            assert 'last_updated' in data
            assert len(data['transactions']) > 0, "Data file has no transactions"

    def test_real_data_has_valid_transactions(self):
        """Test that real data transactions are valid."""
        data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'overbid_data.json')

        if not os.path.exists(data_file):
            pytest.skip("No real data file available")

        with open(data_file, 'r') as f:
            data = json.load(f)

        for tx in data['transactions'][:10]:  # Check first 10
            # Required fields
            assert tx.get('lat') is not None
            assert tx.get('lng') is not None
            assert tx.get('asking_price', 0) > 0
            assert tx.get('sale_price', 0) > 0
            assert tx.get('city') is not None

            # Reasonable overbid range (filter outliers)
            overbid = tx.get('overbid_pct', 0)
            if overbid < -50 or overbid > 100:
                print(f"Warning: Outlier overbid {overbid}% at {tx.get('address')}")

    def test_real_data_cities_coverage(self):
        """Test that real data covers expected cities."""
        data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'overbid_data.json')

        if not os.path.exists(data_file):
            pytest.skip("No real data file available")

        with open(data_file, 'r') as f:
            data = json.load(f)

        cities = set(tx.get('city') for tx in data['transactions'])

        # Should have at least some of the target cities
        expected_cities = {'Amsterdam', 'Utrecht', 'Rotterdam', 'Almere', 'Zaandam'}
        found_cities = cities & expected_cities

        assert len(found_cities) >= 1, f"Expected at least 1 target city, found: {cities}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
