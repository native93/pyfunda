#!/usr/bin/env python3
"""Local web app for Funda apartment analysis."""

import base64
import hashlib
import hmac
import json
import os
import time
import requests
from flask import Flask, render_template, request, jsonify
import sys
sys.path.insert(0, '..')
from funda import Funda

app = Flask(__name__)

# Load secrets
SECRETS_FILE = os.path.join(os.path.dirname(__file__), 'secrets.json')

def load_secrets():
    """Load secrets from secrets.json."""
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE, 'r') as f:
            return json.load(f)
    return {}

SECRETS = load_secrets()

# Krib.nl API configuration (from secrets)
KRIB_API_ENDPOINT = 'https://krib.nl/api/v1/funda-listing-meta-data'
KRIB_API_SECRET = base64.b64decode(SECRETS.get('krib_api_secret_b64', '')).decode() if SECRETS.get('krib_api_secret_b64') else ''
KRIB_AUTH_TOKEN = SECRETS.get('krib_auth_token', '')


def get_krib_data(funda_id: str) -> dict:
    """Fetch sale price and WOZ data from krib.nl API."""
    timestamp = str(int(time.time() // 60))

    # Message format: listingId:timestamp
    message = f"{funda_id}:{timestamp}"
    signature = hmac.new(
        KRIB_API_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "accept": "*/*",
        "authorization": f"Bearer {KRIB_AUTH_TOKEN}",
        "content-type": "application/json",
        "origin": "https://www.funda.nl",
        "referer": "https://www.funda.nl/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "x-request-signature": signature,
        "x-request-timestamp": timestamp,
    }

    try:
        response = requests.post(KRIB_API_ENDPOINT, json={"id": str(funda_id)}, headers=headers, timeout=10)
        if response.ok:
            return response.json()
    except Exception:
        pass
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    location = data.get('location', '')
    radius = int(data.get('radius', 2))

    if not location:
        return jsonify({'error': 'Location required'}), 400

    f = Funda()
    results = []

    try:
        # Search sold apartments
        for page in range(10):
            listings = f.search_listing(
                location=location,
                radius_km=radius,
                offering_type='buy',
                availability='sold',
                object_type=['apartment'],
                sort='newest',
                page=page,
            )

            if not listings:
                break

            for listing in listings:
                results.append({
                    'global_id': listing.get('global_id'),
                    'title': listing.get('title'),
                    'postcode': listing.get('postcode'),
                    'price': listing.get('price'),
                    'status': 'sold'
                })

            if len(listings) < 15:
                break

        # Also search available
        available = f.search_listing(
            location=location,
            radius_km=radius,
            offering_type='buy',
            availability='available',
            object_type=['apartment'],
        )

        for listing in available:
            results.append({
                'global_id': listing.get('global_id'),
                'title': listing.get('title'),
                'postcode': listing.get('postcode'),
                'price': listing.get('price'),
                'status': 'available'
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        f.close()

    return jsonify({'results': results, 'count': len(results)})

@app.route('/details/<int:global_id>')
def get_details(global_id):
    f = Funda()

    try:
        listing = f.get_listing(global_id)
        chars = listing.get('characteristics', {})
        description = listing.get('description', '') or ''

        # Get WOZ values
        woz_data = {}
        try:
            history = f.get_price_history(listing)
            for h in history:
                if h.get('status') == 'woz':
                    year = h.get('date', '')[-4:] if h.get('date') else ''
                    if year:
                        woz_data[f'woz_{year}'] = h.get('price')
                        woz_data[f'woz_{year}_fmt'] = h.get('human_price')
        except:
            pass

        # Check for lift
        has_lift = 'lift' in str(chars.get('Voorzieningen', '')).lower()

        # Check balcony facing from description
        balcony_facing = '-'
        desc_lower = description.lower()
        for direction in ['zuidoosten', 'zuidwesten', 'noordoosten', 'noordwesten', 'zuiden', 'noorden', 'oosten', 'westen']:
            if direction in desc_lower:
                balcony_facing = direction.capitalize()
                break

        price = listing.get('price') or 0
        area = listing.get('living_area') or 0
        price_m2 = int(price / area) if price and area else 0

        result = {
            'global_id': listing.get('global_id'),
            'title': listing.get('title'),
            'postcode': listing.get('postcode'),
            'city': listing.get('city'),
            'price': price,
            'price_formatted': listing.get('price_formatted'),
            'price_m2': price_m2,
            'living_area': area,
            'bedrooms': listing.get('bedrooms'),
            'rooms': listing.get('rooms'),
            'construction_year': listing.get('construction_year'),
            'energy_label': listing.get('energy_label'),
            'floor': chars.get('Gelegen op', '-'),
            'has_lift': has_lift,
            'has_balcony': 'aanwezig' in str(chars.get('Balkon/dakterras', '')).lower(),
            'balcony_facing': balcony_facing,
            'bathroom_facilities': chars.get('Badkamervoorzieningen', '-'),
            'cv_ketel': chars.get('Cv-ketel', '-'),
            'vve': chars.get('Bijdrage VvE', chars.get('Periodieke bijdrage', '-')),
            'parking': chars.get('Soort garage', chars.get('Soort parkeergelegenheid', '-')),
            'status': 'sold' if listing.get('status') == 'sold' else 'available',
            'url': listing.get('url'),
            'publication_date': listing.get('publication_date'),
            'offered_since': chars.get('Aangeboden sinds', '-'),
            **woz_data,
            # User-editable fields (will be filled in via UI)
            'bathroom_condition': '',
            'toilet_condition': '',
            'kitchen_condition': '',
            'cooktop_type': '',
            'actual_sale_price': None,
            'sale_date': '',
        }

        # Try to get krib.nl data for additional WOZ/sale info
        try:
            krib_data = get_krib_data(str(global_id))
            if krib_data:
                # Add latest WOZ from krib if we don't have it
                woz_values = krib_data.get('woz_values', [])
                for woz in woz_values:
                    year = woz.get('date', '')[:4]
                    if year and f'woz_{year}' not in result:
                        result[f'woz_{year}'] = woz.get('value')
                        result[f'woz_{year}_fmt'] = f"€{woz.get('value'):,}".replace(',', '.')

                # Add area stats
                area_stats = krib_data.get('area_stats', {})
                if area_stats:
                    result['area_price_m2'] = area_stats.get('price_per_square_meter')
                    result['area_days_to_sell'] = area_stats.get('days_to_sell')

                # Add property transaction price if available
                prop_stats = krib_data.get('property_stats', {})
                if prop_stats and prop_stats.get('transaction_price'):
                    result['krib_transaction_price'] = prop_stats.get('transaction_price')
        except Exception:
            pass  # krib.nl data is optional

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        f.close()


@app.route('/krib/<int:global_id>')
def get_krib_info(global_id):
    """Fetch krib.nl data (sale prices, WOZ values) for a listing."""
    try:
        data = get_krib_data(str(global_id))
        if data:
            # Extract key info
            result = {
                'woz_values': data.get('woz_values', []),
                'area_stats': data.get('area_stats', {}),
                'property_stats': data.get('property_stats', {}),
                'closest_transactions': data.get('closest_transactions', [])[:5],
                'share_link': data.get('share_link'),
            }
            return jsonify(result)
        else:
            return jsonify({'error': 'Not found in krib.nl'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/heatmap')
def heatmap():
    """Render the overbidding heatmap page."""
    return render_template('heatmap.html')


@app.route('/api/overbid-data')
def overbid_data():
    """Return overbid data for the heatmap."""
    data_file = os.path.join(os.path.dirname(__file__), 'overbid_data.json')

    if not os.path.exists(data_file):
        response = jsonify({
            'error': 'No data collected yet. Run collect_overbid_data.py first.',
            'transactions': []
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
        response = jsonify(data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    except Exception as e:
        response = jsonify({'error': str(e), 'transactions': []})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response


if __name__ == '__main__':
    app.run(debug=True, port=5050)
