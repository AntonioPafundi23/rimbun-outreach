# Rimbun Outreach

Source of truth for Rimbun prospect research and manual outreach notes, split by commercial segment.

```text
outreach/
  banks/       # banks, digital banks, e-wallets, fintechs
  business/    # distributors, grosir, wholesale (Places + WhatsApp)
  insurance/   # insurers / protection distribution
  tools/       # shared MCP helper
```

Each segment has the same shape:

```text
<data|config|templates>/
  data/prospects.csv
  data/outreach_interactions.csv
  config/criteria.json
  templates/
```

The MCP helper lives at `tools/rimbun-outreach-mcp`. It reads/writes one segment folder at a time.

Default segment is **banks**. Switch with:

```bash
export RIMBUN_OUTREACH_HOME=/absolute/path/to/outreach/business
# or insurance
```

This does not scrape LinkedIn or send automated messages. It stores prospects you provide, helps rank them, and drafts messages for manual review.

## Secrets (one file)

All tools read from a single env file at the repo root:

```bash
cp .env.example .env
```

Put Hunter, Google Places, and sender fields there. Do not scatter `.env` files per segment.

## Banks (default)

Existing ICP: banks, wallets, fintechs. LinkedIn / email templates. Optional Hunter.io for email discovery.

## Business

Distributor / grosir lead gen via Google Places:

```bash
# after outreach/.env has GOOGLE_PLACES_API_KEY
python3 business/tools/places_leads/scrape_distributors.py
```

See `business/tools/places_leads/README.md`. Output lands in `business/data/places_leads.csv`.

## Insurance

Scaffold ready: criteria + empty prospect CSVs + LinkedIn template. Same MCP workflow as banks once you set `RIMBUN_OUTREACH_HOME` to the insurance folder.

## Install MCP

```bash
cd tools/rimbun-outreach-mcp
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The macOS system `python3` may be Python 3.9; this project expects Python 3.10+.

## Run MCP

```bash
rimbun-outreach-mcp
```

Or:

```bash
python -m rimbun_outreach_mcp.server
```

### MCP client config

```json
{
  "mcpServers": {
    "rimbun-outreach": {
      "command": "/absolute/path/to/outreach/tools/rimbun-outreach-mcp/.venv/bin/rimbun-outreach-mcp",
      "env": {
        "RIMBUN_OUTREACH_HOME": "/absolute/path/to/outreach/banks"
      }
    }
  }
}
```

Change `RIMBUN_OUTREACH_HOME` to `.../business` or `.../insurance` when working that segment.

## MCP tools

- `add_prospect` / `list_top_prospects` / `rescore_prospects`
- `draft_message` / `update_status` / `get_prospect_csv_path`
- `hunter_domain_search` / `hunter_email_finder` / `hunter_verify_email`

## Prospect CSV columns

```csv
company,website,linkedin_profile,name,title,location,segment,source,fit_score,fit_reason,message_draft,status,last_contacted,notes
```

## Example workflows

**Banks / insurance**

1. Add prospects manually from LinkedIn, websites, or partner lists.
2. Tune `config/criteria.json` in that segment.
3. List top prospects → draft → send manually → update status.

**Business**

1. Run Places scrape for city queries.
2. Keep rows with phone + website (`--require-phone-website`).
3. WhatsApp manually using `business/templates/whatsapp_first_touch.txt`.
4. Log touches in `business/data/outreach_interactions.csv`.
