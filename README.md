# Funda

Python API for [Funda.nl](https://www.funda.nl) real estate listings.

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from funda import Funda

f = Funda()

# Get a listing by ID
listing = f.get_listing(43117443)
print(listing['title'], listing['city'])
# Reehorst 13 Luttenberg

# Get a listing by URL
listing = f.get_listing('https://www.funda.nl/detail/koop/amsterdam/appartement-123/43117443/')

# Search listings
results = f.search_listing('amsterdam', price_max=500000)
for r in results:
    print(r['title'], r['price'])
```

## API Reference

### Funda

Main entry point for the API.

```python
from funda import Funda

f = Funda(timeout=30)
```

#### get_listing(listing_id)

Get a single listing by ID or URL.

```python
# By numeric ID (tinyId or globalId)
listing = f.get_listing(43117443)

# By URL
listing = f.get_listing('https://www.funda.nl/detail/koop/city/house-name/43117443/')
```

#### search_listing(location, ...)

Search for listings with filters.

```python
results = f.search_listing(
    location='amsterdam',           # City or area name
    offering_type='buy',            # 'buy' or 'rent'
    price_min=200000,               # Minimum price
    price_max=500000,               # Maximum price
    area_min=50,                    # Minimum living area (m²)
    area_max=150,                   # Maximum living area (m²)
    results=25,                     # Max results to return
)
```

Search multiple locations:

```python
results = f.search_listing(['amsterdam', 'rotterdam', 'utrecht'])
```

### Listing

Listing objects support dict-like access with convenient aliases.

```python
listing['title']        # Property title/address
listing['city']         # City name
listing['price']        # Numeric price
listing['price_formatted']  # Formatted price string
listing['bedrooms']     # Number of bedrooms
listing['living_area']  # Living area
listing['energy_label'] # Energy label (A, B, C, etc.)
listing['object_type']  # House, Apartment, etc.
listing['coordinates']  # (lat, lng) tuple
listing['photos']       # List of photo IDs
listing['url']          # Funda URL
```

**Key aliases** - these all work:

| Alias | Canonical Key |
|-------|---------------|
| `name`, `address` | `title` |
| `location`, `locality` | `city` |
| `area`, `size` | `living_area` |
| `type`, `property_type` | `object_type` |
| `images`, `pictures`, `media` | `photos` |
| `agent`, `realtor`, `makelaar` | `broker` |
| `zip`, `zipcode`, `postal_code` | `postcode` |

#### Methods

```python
listing.summary()       # Text summary of the listing
listing.to_dict()       # Convert to plain dictionary
listing.keys()          # List available keys
listing.get('key')      # Get with default (like dict.get)
listing.getID()         # Get listing ID
```

## Examples

### Find apartments in Amsterdam under €400k

```python
from funda import Funda

f = Funda()
results = f.search_listing('amsterdam', price_max=400000)

for listing in results:
    print(f"{listing['title']}")
    print(f"  Price: €{listing['price']:,}")
    print(f"  Area: {listing.get('living_area', 'N/A')}")
    print(f"  Bedrooms: {listing.get('bedrooms', 'N/A')}")
    print()
```

### Get detailed listing information

```python
from funda import Funda

f = Funda()
listing = f.get_listing(43117443)

print(listing.summary())

# Access all characteristics
for key, value in listing['characteristics'].items():
    print(f"{key}: {value}")
```

### Search rentals in multiple cities

```python
from funda import Funda

f = Funda()
results = f.search_listing(
    location=['amsterdam', 'rotterdam', 'den-haag'],
    offering_type='rent',
    price_max=2000,
    results=50
)

print(f"Found {len(results)} rentals")
```

## License

AGPL-3.0
