# Places leads (business segment)

Uses **Places API (New)** Text Search to build a distributor / grosir CSV.

## Setup

1. Google Cloud Console: enable **Places API (New)**.
2. Create an API key restricted to **Places API (New)** only.
3. Add the key to the shared repo env:

```bash
cd ../../..   # outreach/
cp .env.example .env
# set GOOGLE_PLACES_API_KEY=...
```

No extra packages — script uses the Python standard library.

## Run

From the outreach repo root:

```bash
python3 business/tools/places_leads/scrape_distributors.py
```

Defaults search:

- `distributor Jakarta`
- `distributor Surabaya`
- `grosir Bandung`

Output: `business/data/places_leads.csv`

Useful flags:

```bash
python3 business/tools/places_leads/scrape_distributors.py --query "distributor Medan" --require-phone-website
python3 business/tools/places_leads/scrape_distributors.py --min-reviews 20 --min-score 4
```

By default the script **merges** into the existing CSV by `place_id` (adds new, refreshes matches). Use `--overwrite` only if you intentionally want a fresh file.

## Scoring

Heuristic lead score (keep >= 3 by default):

- +2 name contains distributor / grosir / wholesale / agen
- +2 reviews >= 100 (or +1 if >= 10)
- +1 has website
- +1 has phone

For WhatsApp Phase 1, re-run with `--require-phone-website`.
