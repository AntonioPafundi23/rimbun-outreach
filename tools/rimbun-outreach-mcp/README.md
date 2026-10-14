# Rimbun Outreach MCP

CSV-based MCP server for scoring and drafting manual prospect outreach for Rimbun.

Segment data lives one level up from `tools/`:

```text
../../banks
../../business
../../insurance
```

Default home is **banks**. Override with `RIMBUN_OUTREACH_HOME`:

```bash
export RIMBUN_OUTREACH_HOME=/absolute/path/to/outreach/business
```

This does not scrape LinkedIn or send automated LinkedIn messages. It stores prospects you provide, helps rank them, and drafts messages for manual review.

Optional Hunter.io support can be enabled for email discovery and verification.
Use the **shared** secrets file at the outreach repo root:

```bash
cd ../..
cp .env.example .env
```

```text
HUNTER_API_KEY=your_hunter_key_here
RIMBUN_SENDER_NAME=your_name_here
RIMBUN_SENDER_ROLE=working with Rimbun
GOOGLE_PLACES_API_KEY=...   # used by business Places scrape, not MCP
```

`.env` is ignored by git. Do not commit API keys.

## Files (per segment)

- `data/prospects.csv` - editable working list of prospects.
- `data/outreach_interactions.csv` - log of actual outreach sent/replies.
- `config/criteria.json` - scoring signals for that segment.
- `templates/` - message templates.

## Install

From this folder:

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The macOS system `python3` may be Python 3.9; this project expects Python 3.10+.

## Run

```bash
rimbun-outreach-mcp
```

Or:

```bash
python -m rimbun_outreach_mcp.server
```

## MCP Client Config

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

Each co-founder should update the absolute path for their local checkout.

## Tools

- `add_prospect` - add or update a prospect in the CSV.
- `list_top_prospects` - list prospects sorted by score.
- `rescore_prospects` - recalculate scores after editing criteria.
- `draft_message` - create a LinkedIn-style message for manual sending.
- `update_status` - track manual outreach status.
- `get_prospect_csv_path` - return the CSV path.
- `hunter_domain_search` - find public emails for a company domain via Hunter.
- `hunter_email_finder` - find a likely email for a named person at a domain.
- `hunter_verify_email` - verify an email address before outreach.

## CSV Columns

```csv
company,website,linkedin_profile,name,title,location,segment,source,fit_score,fit_reason,message_draft,status,last_contacted,notes
```
