# Rimbun Outreach

This folder is the source of truth for Rimbun prospect research and manual outreach notes.

The MCP helper code lives at:

```text
/Users/apafundi/workspace/Rimbun/outreach/tools/rimbun-outreach-mcp
```

It reads and writes `/Users/apafundi/workspace/Rimbun/outreach` by default. Override this with `RIMBUN_OUTREACH_HOME` only if the outreach folder moves.

This does not scrape LinkedIn or send automated LinkedIn messages. It stores prospects you provide, helps rank them, and drafts messages for manual review.

Optional Hunter.io support can be enabled for email discovery and verification.
Create a local `.env` file in the MCP folder:

```bash
cd /Users/apafundi/workspace/Rimbun/outreach/tools/rimbun-outreach-mcp
cp .env.example .env
```

Then edit `.env`:

```text
HUNTER_API_KEY=your_hunter_key_here
```

`.env` is ignored by git. Do not commit API keys.

## Files

- `data/prospects.csv` - editable working list of prospects.
- `data/outreach_interactions.csv` - log of actual outreach sent/replies.
- `config/criteria.json` - scoring signals for Rimbun fit.
- `templates/` - message templates.
- `tools/rimbun-outreach-mcp/src/rimbun_outreach_mcp/server.py` - MCP server.

## Install

From the MCP folder:

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

Use this command after installing from the MCP folder:

```json
{
  "mcpServers": {
    "rimbun-outreach": {
      "command": "/Users/apafundi/workspace/Rimbun/outreach/tools/rimbun-outreach-mcp/.venv/bin/rimbun-outreach-mcp"
    }
  }
}
```

If you move the folder, update the absolute path.

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

## Example Workflow

1. Add prospects manually from LinkedIn, company websites, partner lists, or other permitted sources.
2. Edit `config/criteria.json` to tune what "good fit" means for Rimbun.
3. Ask your MCP client to list top prospects.
4. Draft a message.
5. Review and send manually.
6. Update the prospect status in the CSV.
