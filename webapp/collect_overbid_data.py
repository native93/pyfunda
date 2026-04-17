#!/usr/bin/env python3
"""Collect overbidding data from Funda + krib.nl for heatmap visualization."""

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
from datetime import datetime

import requests

sys.path.insert(0, '..')
from funda import Funda

# Load config
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
SECRETS_FILE = os.path.join(os.path.dirname(__file__), 'secrets.json')

def load_config():
    """Load configuration from config.json."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def load_secrets():
    """Load secrets from secrets.json."""
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE, 'r') as f:
            return json.load(f)
    return {}

CONFIG = load_config()
SECRETS = load_secrets()

# Krib.nl API configuration (from secrets)
KRIB_API_ENDPOINT = 'https://krib.nl/api/v1/funda-listing-meta-data'
KRIB_API_SECRET = base64.b64decode(SECRETS.get('krib_api_secret_b64', '')).decode() if SECRETS.get('krib_api_secret_b64') else ''
KRIB_AUTH_TOKEN = SECRETS.get('krib_auth_token', '')

# Target cities from config (with fallback)
TARGET_CITIES = CONFIG.get('target_cities', [
    'amsterdam',
    'utrecht',
    'almere',
    'zaandam',
    'rotterdam',
])

# Data file
DATA_FILE = 'overbid_data.json'
COORDS_CACHE_FILE = 'coords_cache.json'


def get_krib_data(funda_id: str) -> dict:
    """Fetch sale price and WOZ data from krib.nl API."""
    timestamp = str(int(time.time() // 60))
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
        response = requests.post(KRIB_API_ENDPOINT, json={"id": str(funda_id)}, headers=headers, timeout=15)
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"  krib.nl error for {funda_id}: {e}")
    return None


def extract_listing_id(funda_url: str) -> str:
    """Extract listing ID from Funda URL."""
    # https://www.funda.nl/detail/koop/utrecht/appartement-ondiep-137/43210915/
    match = re.search(r'/(\d{8,})/?$', funda_url)
    if match:
        return match.group(1)
    return None


def load_coords_cache() -> dict:
    """Load coordinates cache from file."""
    if os.path.exists(COORDS_CACHE_FILE):
        with open(COORDS_CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_coords_cache(cache: dict):
    """Save coordinates cache to file."""
    with open(COORDS_CACHE_FILE, 'w') as f:
        json.dump(cache, f)


def get_coordinates(funda: Funda, listing_id: str, coords_cache: dict) -> tuple:
    """Get coordinates for a listing, using cache if available."""
    if listing_id in coords_cache:
        return coords_cache[listing_id]

    try:
        listing = funda.get_listing(int(listing_id))
        lat = listing.get('latitude')
        lng = listing.get('longitude')
        if lat and lng:
            coords_cache[listing_id] = (lat, lng)
            return (lat, lng)
    except Exception as e:
        print(f"  Failed to get coords for {listing_id}: {e}")

    return (None, None)


def load_existing_data() -> dict:
    """Load existing data file if present."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"last_updated": None, "transactions": []}


def save_data(data: dict):
    """Save data to file."""
    data["last_updated"] = datetime.now().isoformat()
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def collect_data(cities: list = None, max_pages: int = 100, year_filter: int = 2025):
    """
    Collect overbidding data for specified cities.

    Args:
        cities: List of cities to search (default: TARGET_CITIES)
        max_pages: Maximum pages to fetch per city
        year_filter: Only include transactions from this year
    """
    cities = cities or TARGET_CITIES

    print(f"Starting data collection for: {', '.join(cities)}")
    print(f"Year filter: {year_filter}")
    print(f"Max pages per city: {max_pages}")
    print()

    # Load existing data and caches
    data = load_existing_data()
    coords_cache = load_coords_cache()

    # Track seen transactions to avoid duplicates
    seen_urls = {t['funda_url'] for t in data['transactions']}

    funda = Funda()
    total_new = 0
    krib_requests = 0

    try:
        for city in cities:
            print(f"\n{'='*60}")
            print(f"Processing: {city}")
            print('='*60)

            page = 0
            city_listings = 0

            while page < max_pages:
                print(f"\n  Page {page + 1}...")

                try:
                    # Search for sold listings
                    listings = funda.search_listing(
                        location=city,
                        offering_type='buy',
                        availability='sold',
                        sort='newest',
                        page=page,
                    )
                except Exception as e:
                    print(f"  Search error: {e}")
                    break

                if not listings:
                    print("  No more listings")
                    break

                print(f"  Found {len(listings)} listings")
                city_listings += len(listings)

                for listing in listings:
                    global_id = listing.get('global_id')
                    if not global_id:
                        continue

                    # Need to get tiny_id for krib.nl API
                    # Search results only have global_id, need to fetch full listing
                    try:
                        full_listing = funda.get_listing(global_id)
                        tiny_id = full_listing.get('tiny_id')
                        if not tiny_id:
                            print(f"    No tiny_id for {global_id}, skipping")
                            continue
                    except Exception as e:
                        print(f"    Failed to get tiny_id for {global_id}: {e}")
                        continue

                    # Rate limit krib.nl requests (60/min limit)
                    if krib_requests > 0 and krib_requests % 50 == 0:
                        print(f"  Rate limiting... (waiting 60s)")
                        time.sleep(60)

                    # Get krib.nl data using tiny_id
                    krib_data = get_krib_data(str(tiny_id))
                    krib_requests += 1

                    if not krib_data:
                        continue

                    # Process closest_transactions
                    transactions = krib_data.get('closest_transactions', [])

                    for tx in transactions:
                        funda_url = tx.get('funda_url', '')

                        # Skip if already seen
                        if funda_url in seen_urls:
                            continue

                        # Check year filter
                        tx_date = tx.get('transaction_date', '')
                        if year_filter and not tx_date.startswith(str(year_filter)):
                            continue

                        # Calculate overbid
                        asking = tx.get('funda_asking_price')
                        sale = tx.get('transaction_price')

                        if not asking or not sale:
                            continue

                        overbid_pct = round((sale - asking) / asking * 100, 1)

                        # Get coordinates
                        tx_listing_id = extract_listing_id(funda_url)
                        lat, lng = None, None

                        if tx_listing_id:
                            lat, lng = get_coordinates(funda, tx_listing_id, coords_cache)
                            # Reduced delay
                            time.sleep(0.2)

                        if not lat or not lng:
                            # Skip if no coordinates
                            continue

                        # Build transaction record
                        address = tx.get('address', {})
                        record = {
                            'address': f"{address.get('street', '')} {address.get('number', '')}".strip(),
                            'postal_code': address.get('postal_code', ''),
                            'city': address.get('city', ''),
                            'asking_price': asking,
                            'sale_price': sale,
                            'overbid_pct': overbid_pct,
                            'transaction_date': tx_date,
                            'lat': lat,
                            'lng': lng,
                            'living_area_m2': tx.get('living_space_m2'),
                            'energy_label': tx.get('energy_label'),
                            'funda_url': funda_url,
                        }

                        data['transactions'].append(record)
                        seen_urls.add(funda_url)
                        total_new += 1

                        print(f"    + {record['address']}, {record['city']}: {overbid_pct:+.1f}%")

                    # Reduced delay between listings
                    time.sleep(0.1)

                # Save progress after each page
                save_data(data)
                save_coords_cache(coords_cache)

                if len(listings) < 15:
                    print("  Last page reached")
                    break

                page += 1

            print(f"\n  City total: {city_listings} listings searched")

    except KeyboardInterrupt:
        print("\n\nInterrupted! Saving progress...")
    finally:
        funda.close()
        save_data(data)
        save_coords_cache(coords_cache)

    print(f"\n{'='*60}")
    print(f"Collection complete!")
    print(f"New transactions added: {total_new}")
    print(f"Total transactions: {len(data['transactions'])}")
    print(f"Data saved to: {DATA_FILE}")


def print_stats():
    """Print statistics about collected data."""
    data = load_existing_data()
    transactions = data['transactions']

    if not transactions:
        print("No data collected yet.")
        return

    print(f"\nData Statistics")
    print("="*60)
    print(f"Last updated: {data.get('last_updated', 'N/A')}")
    print(f"Total transactions: {len(transactions)}")

    # By city
    cities = {}
    for tx in transactions:
        city = tx.get('city', 'Unknown')
        cities[city] = cities.get(city, 0) + 1

    print(f"\nBy city:")
    for city, count in sorted(cities.items(), key=lambda x: -x[1]):
        print(f"  {city}: {count}")

    # Overbid stats
    overbids = [tx['overbid_pct'] for tx in transactions if tx.get('overbid_pct') is not None]
    if overbids:
        print(f"\nOverbid statistics:")
        print(f"  Min: {min(overbids):.1f}%")
        print(f"  Max: {max(overbids):.1f}%")
        print(f"  Avg: {sum(overbids)/len(overbids):.1f}%")
        print(f"  Median: {sorted(overbids)[len(overbids)//2]:.1f}%")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Collect overbidding data')
    parser.add_argument('--cities', nargs='+', help='Cities to collect (default: all)')
    parser.add_argument('--max-pages', type=int, default=50, help='Max pages per city')
    parser.add_argument('--year', type=int, default=2025, help='Filter by transaction year')
    parser.add_argument('--stats', action='store_true', help='Print statistics only')

    args = parser.parse_args()

    if args.stats:
        print_stats()
    else:
        collect_data(
            cities=args.cities,
            max_pages=args.max_pages,
            year_filter=args.year,
        )
