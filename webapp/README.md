# Funda Webapp - Dutch Real Estate Overbidding Heatmap

Visualize how much buyers are paying above asking price across Dutch cities.

## Setup (5 steps)

### Step 1: Install dependencies

```bash
cd webapp
pip install flask requests
pip install -e ..
```

### Step 2: Get krib.nl credentials

1. Install the [krib.nl Chrome extension](https://chromewebstore.google.com/detail/krib-woning-informatie/fppkfmeikpmpllfdapnigpkmacfaicoc)
2. Go to any Funda listing page
3. Open DevTools (F12) → Network tab
4. Find request to `krib.nl/api/v1/funda-listing-meta-data`
5. Copy the `Authorization` header value (starts with `Bearer ...`)
6. From the extension source, get the API secret (base64 encoded)

### Step 3: Create secrets.json

```bash
cp secrets.example.json secrets.json
```

Edit `secrets.json`:
```json
{
  "krib_api_secret_b64": "YOUR_BASE64_SECRET_HERE",
  "krib_auth_token": "YOUR_BEARER_TOKEN_HERE"
}
```

### Step 4: Collect data

```bash
# Quick test (~10 min)
python3 collect_overbid_data.py --cities amsterdam --max-pages 5

# Full collection (~1-2 hours)
python3 collect_overbid_data.py
```

Check progress:
```bash
python3 collect_overbid_data.py --stats
```

### Step 5: Run the app

```bash
python3 app.py
```

Open http://localhost:5050/heatmap

---

## What is this?

In the Netherlands, houses often sell **above asking price**. This app shows you where and by how much.

- **Green** = 0-5% overbid (buyer-friendly)
- **Yellow** = 5-10% (moderate)
- **Orange** = 10-15% (competitive)  
- **Red** = 15%+ (very competitive)

Data comes from [Funda.nl](https://funda.nl) (listings) and [krib.nl](https://krib.nl) (actual sale prices).

---

## Commands

| Command | What it does |
|---------|--------------|
| `python3 app.py` | Start the web server |
| `python3 collect_overbid_data.py --stats` | Show collected data statistics |
| `python3 collect_overbid_data.py --cities amsterdam utrecht` | Collect data for specific cities |
| `python3 collect_overbid_data.py --year 2025` | Collect only 2025 transactions |
| `python3 -m pytest tests/ -v` | Run tests |

---

## Files

```
webapp/
├── app.py                  # Web server
├── collect_overbid_data.py # Data collection script
├── config.json             # Cities to collect
├── secrets.json            # Your API credentials (not in git)
├── overbid_data.json       # Collected data (not in git)
└── templates/
    └── heatmap.html        # Map page
```

---

## Troubleshooting

**"Failed to load overbid data"**  
→ Run `python3 collect_overbid_data.py` first

**"Invalid signature"**  
→ Check your secrets.json credentials

**Collection is slow**  
→ Normal. Rate limited to ~50 requests/min

---

## How it works

1. Search Funda for sold listings
2. For each listing, ask krib.nl for the actual sale price
3. Calculate overbid % = (sale - asking) / asking × 100
4. Plot on map with colored markers
