# Webapp Tests

## Running Tests

```bash
cd /Users/nattar/personal/pyfunda/webapp
pip install pytest
pytest tests/ -v
```

## Test Coverage

### Flask Endpoints
- `test_index_page_loads` - Index page returns 200
- `test_heatmap_page_loads` - Heatmap page loads with Leaflet
- `test_heatmap_contains_required_elements` - All UI elements present
- `test_overbid_data_endpoint_returns_json` - API returns valid JSON
- `test_overbid_data_has_cors_header` - CORS enabled
- `test_search_endpoint_requires_location` - Validates input
- `test_krib_endpoint_returns_json` - Krib API proxy works

### Krib API
- `test_krib_api_with_valid_id` - Returns data for known listing
- `test_krib_api_with_invalid_id` - Handles bad IDs gracefully
- `test_krib_api_signature_generation` - HMAC signature correct

### Data Format
- `test_transaction_has_required_fields` - All fields present
- `test_overbid_calculation_is_correct` - Math is correct
- `test_coordinates_are_valid` - Within Netherlands bounds

### Data Collection
- `test_extract_listing_id_from_url` - URL parsing works
- `test_load_and_save_data` - File I/O works

### Visualization
- `test_color_mapping_logic` - Colors match overbid %

### Real Data
- `test_real_data_file_exists` - Data file valid
- `test_real_data_has_valid_transactions` - Transactions valid
- `test_real_data_cities_coverage` - Expected cities present
