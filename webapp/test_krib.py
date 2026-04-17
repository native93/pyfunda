#!/usr/bin/env python3
"""Working krib.nl API for fetching actual sale prices."""

import base64
import hashlib
import hmac
import json
import os
import time
import requests

# Load secrets
SECRETS_FILE = os.path.join(os.path.dirname(__file__), 'secrets.json')

def load_secrets():
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE, 'r') as f:
            return json.load(f)
    return {}

SECRETS = load_secrets()

API_ENDPOINT = "https://krib.nl/api/v1/funda-listing-meta-data"
API_SECRET = base64.b64decode(SECRETS.get('krib_api_secret_b64', '')).decode() if SECRETS.get('krib_api_secret_b64') else ''
AUTH_TOKEN = SECRETS.get('krib_auth_token', '')

print(f"Secret loaded: {'Yes' if API_SECRET else 'No'}")


def get_krib_data(funda_id: str) -> dict:
    """Fetch sale price and WOZ data from krib.nl API."""
    timestamp = str(int(time.time() // 60))

    # Message format: listingId:timestamp (from extension source)
    message = f"{funda_id}:{timestamp}"
    signature = hmac.new(
        API_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "accept": "*/*",
        "authorization": f"Bearer {AUTH_TOKEN}",
        "content-type": "application/json",
        "origin": "https://www.funda.nl",
        "referer": "https://www.funda.nl/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "x-request-signature": signature,
        "x-request-timestamp": timestamp,
    }

    response = requests.post(API_ENDPOINT, json={"id": funda_id}, headers=headers)
    print(f"Status: {response.status_code}")

    if response.ok:
        return response.json()
    else:
        print(f"Error: {response.text}")
        return None


# Verify signature algorithm with known working example
known_timestamp = "29607249"
known_id = "89201502"
known_sig = "07cbabb679d37698c43a3bcec56ba7ceb8a995292e5a39fd8858643e949d57cb"

message = f"{known_id}:{known_timestamp}"
computed_sig = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
print(f"\nVerifying signature algorithm:")
print(f"Message: {message}")
print(f"Expected: {known_sig}")
print(f"Computed: {computed_sig}")
print(f"Match: {computed_sig == known_sig}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing live API...")
    print("="*60)

    # Test with apartments from Burgemeester Norbruislaan
    test_ids = [
        ("43032486", "492"),
        ("43051584", "484"),
        ("43117443", "510 (current listing)"),
        ("42951044", "480"),
        ("42869706", "456"),
    ]

    for funda_id, addr in test_ids:
        print(f"\n--- Testing {addr} (ID: {funda_id}) ---")
        result = get_krib_data(funda_id)
        if result:
            import json
            print(json.dumps(result, indent=2, default=str))
