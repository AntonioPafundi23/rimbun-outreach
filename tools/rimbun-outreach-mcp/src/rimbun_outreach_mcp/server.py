from __future__ import annotations

import csv
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTREACH_HOME = PROJECT_ROOT.parents[1]
OUTREACH_HOME = Path(
    os.environ.get("RIMBUN_OUTREACH_HOME", str(DEFAULT_OUTREACH_HOME))
).expanduser()
DATA_DIR = OUTREACH_HOME / "data"
CONFIG_DIR = OUTREACH_HOME / "config"
TEMPLATES_DIR = OUTREACH_HOME / "templates"
PROSPECTS_CSV = DATA_DIR / "prospects.csv"
CRITERIA_JSON = CONFIG_DIR / "criteria.json"
LOCAL_ENV_PATH = PROJECT_ROOT / ".env"
HUNTER_API_BASE = "https://api.hunter.io/v2"

DEFAULT_CRITERIA: dict[str, list[str]] = {
    "positive_keywords": [
        "bank",
        "digital bank",
        "neobank",
        "fintech",
        "wallet",
        "e-wallet",
        "payments",
        "open banking",
        "personal finance",
        "pfm",
        "transaction enrichment",
        "merchant intelligence",
        "customer engagement",
        "next best action",
        "cross-sell",
        "retention",
        "deposit",
        "liquidity",
        "bill pay",
        "insurance",
        "southeast asia",
        "sea",
        "indonesia",
        "philippines",
        "brunei",
    ],
    "negative_keywords": [
        "student",
        "crypto only",
        "web3 only",
        "consumer only",
        "not hiring",
        "closed",
    ],
    "target_titles": [
        "founder",
        "co-founder",
        "ceo",
        "chief product",
        "chief data",
        "chief digital",
        "chief analytics",
        "head of product",
        "head of data",
        "head of digital",
        "head of analytics",
        "head of growth",
        "head of partnerships",
        "vp product",
        "vp data",
        "director",
        "product manager",
        "partnerships",
    ],
    "target_locations": [
        "southeast asia",
        "sea",
        "indonesia",
        "jakarta",
        "philippines",
        "manila",
        "brunei",
        "singapore",
        "malaysia",
        "kuala lumpur",
        "thailand",
        "vietnam",
    ],
    "target_segments": [
        "bank",
        "digital bank",
        "fintech",
        "e-wallet",
        "payments",
        "personal finance",
        "core banking",
        "data platform",
    ],
}

DEFAULT_TEMPLATES = {
    "linkedin_connection.txt": """Hi {{first_name}}, I came across {{company}} and noticed your work around {{segment}}.

I'm building Rimbun, a transaction intelligence layer for banks and fintechs in Southeast Asia. It turns payment behavior into explainable, non-credit product recommendations like liquidity buffers, bill-pay automation, and protection prompts.

Curious whether this kind of behavioral recommendation layer is something your team is exploring, or if it sits with someone else?
""",
    "linkedin_followup.txt": """Hi {{first_name}}, quick follow-up on my note about Rimbun and {{company}}.

I thought it might be relevant because {{fit_reason}}

Worth a short chat, or is someone else closer to product/data partnerships?
""",
}

FIELDNAMES = [
    "company",
    "website",
    "linkedin_profile",
    "name",
    "title",
    "location",
    "segment",
    "source",
    "fit_score",
    "fit_reason",
    "message_draft",
    "status",
    "last_contacted",
    "notes",
]

mcp = FastMCP("rimbun-outreach")


@dataclass(frozen=True)
class ScoredFit:
    score: int
    reasons: list[str]


def ensure_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    if not PROSPECTS_CSV.exists():
        write_rows([])
    if not CRITERIA_JSON.exists():
        CRITERIA_JSON.write_text(
            json.dumps(DEFAULT_CRITERIA, indent=2) + "\n",
            encoding="utf-8",
        )
    for name, content in DEFAULT_TEMPLATES.items():
        template_path = TEMPLATES_DIR / name
        if not template_path.exists():
            template_path.write_text(content, encoding="utf-8")


def load_local_env() -> None:
    """Load simple KEY=VALUE lines from the local MCP .env if present."""
    if not LOCAL_ENV_PATH.exists():
        return

    for raw_line in LOCAL_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def hunter_api_key() -> str:
    load_local_env()
    api_key = os.environ.get("HUNTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "Hunter API key is not configured. Set HUNTER_API_KEY in the "
            "environment or in outreach/tools/rimbun-outreach-mcp/.env."
        )
    return api_key


def hunter_get(endpoint: str, params: dict[str, str | int]) -> dict[str, Any]:
    query = {
        **params,
        "api_key": hunter_api_key(),
    }
    url = f"{HUNTER_API_BASE}/{endpoint}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "rimbun-outreach-mcp/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_payload = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"Hunter API error {exc.code}: {error_payload}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Hunter API request failed: {exc}") from exc

    return json.loads(payload)


def extract_domain(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("A domain or website is required.")
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urllib.parse.urlparse(candidate)
    domain = parsed.netloc or parsed.path
    domain = domain.lower().removeprefix("www.").strip("/")
    if not domain or "." not in domain:
        raise ValueError(f"Could not extract a domain from {value!r}.")
    return domain


def compact_hunter_email(email_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "email": email_row.get("value") or email_row.get("email") or "",
        "type": email_row.get("type", ""),
        "confidence": email_row.get("confidence", ""),
        "first_name": email_row.get("first_name", ""),
        "last_name": email_row.get("last_name", ""),
        "position": email_row.get("position", ""),
        "department": email_row.get("department", ""),
        "seniority": email_row.get("seniority", ""),
        "linkedin": email_row.get("linkedin", ""),
        "sources": [
            {
                "domain": source.get("domain", ""),
                "uri": source.get("uri", ""),
                "extracted_on": source.get("extracted_on", ""),
                "last_seen_on": source.get("last_seen_on", ""),
            }
            for source in (email_row.get("sources") or [])[:3]
        ],
    }


def read_rows() -> list[dict[str, str]]:
    ensure_files()
    with PROSPECTS_CSV.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            normalized = {field: (row.get(field) or "") for field in FIELDNAMES}
            rows.append(normalized)
        return rows


def write_rows(rows: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        newline="",
        encoding="utf-8",
        dir=DATA_DIR,
        delete=False,
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})
        temp_name = handle.name
    Path(temp_name).replace(PROSPECTS_CSV)


def load_criteria() -> dict[str, Any]:
    ensure_files()
    if not CRITERIA_JSON.exists():
        return DEFAULT_CRITERIA
    with CRITERIA_JSON.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_text(*parts: str) -> str:
    return " ".join(part for part in parts if part).lower()


def score_fit(row: dict[str, str]) -> ScoredFit:
    criteria = load_criteria()
    text = normalize_text(
        row.get("company", ""),
        row.get("website", ""),
        row.get("title", ""),
        row.get("location", ""),
        row.get("segment", ""),
        row.get("notes", ""),
    )

    score = 50
    reasons: list[str] = []

    for keyword in criteria.get("positive_keywords", []):
        if str(keyword).lower() in text:
            score += 8
            reasons.append(f"Matches positive signal: {keyword}")

    for keyword in criteria.get("negative_keywords", []):
        if str(keyword).lower() in text:
            score -= 12
            reasons.append(f"Contains caution signal: {keyword}")

    title = row.get("title", "").lower()
    for target_title in criteria.get("target_titles", []):
        if str(target_title).lower() in title:
            score += 15
            reasons.append(f"Decision-maker title match: {target_title}")
            break

    location = row.get("location", "").lower()
    for target_location in criteria.get("target_locations", []):
        if str(target_location).lower() in location:
            score += 5
            reasons.append(f"Target market match: {target_location}")
            break

    segment = row.get("segment", "").lower()
    for target_segment in criteria.get("target_segments", []):
        if str(target_segment).lower() in segment:
            score += 10
            reasons.append(f"Target segment match: {target_segment}")
            break

    score = max(0, min(100, score))
    if not reasons:
        reasons.append("No strong configured signals matched yet.")
    return ScoredFit(score=score, reasons=reasons)


def find_prospect(rows: list[dict[str, str]], company: str, name: str = "") -> int | None:
    company_key = company.strip().lower()
    name_key = name.strip().lower()
    for index, row in enumerate(rows):
        same_company = row.get("company", "").strip().lower() == company_key
        same_name = not name_key or row.get("name", "").strip().lower() == name_key
        if same_company and same_name:
            return index
    return None


def render_template(template_name: str, row: dict[str, str], offer: str) -> str:
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        template_path = TEMPLATES_DIR / "linkedin_connection.txt"

    template = template_path.read_text(encoding="utf-8")
    values = {field: row.get(field, "") for field in FIELDNAMES}
    values["offer"] = offer
    values["sender_name"] = os.environ.get("RIMBUN_SENDER_NAME", "the Rimbun team")
    values["sender_role"] = os.environ.get(
        "RIMBUN_SENDER_ROLE",
        "working with Rimbun",
    )
    values["first_name"] = (row.get("name", "").split() or ["there"])[0]
    values["today"] = date.today().isoformat()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return values.get(key, "")

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replace, template).strip()


@mcp.tool()
def add_prospect(
    company: str,
    website: str = "",
    linkedin_profile: str = "",
    name: str = "",
    title: str = "",
    location: str = "",
    segment: str = "",
    source: str = "manual",
    notes: str = "",
) -> dict[str, Any]:
    """Add or update a prospect in data/prospects.csv and calculate a fit score."""
    rows = read_rows()
    row = {
        "company": company,
        "website": website,
        "linkedin_profile": linkedin_profile,
        "name": name,
        "title": title,
        "location": location,
        "segment": segment,
        "source": source,
        "status": "new",
        "last_contacted": "",
        "notes": notes,
    }
    scored = score_fit(row)
    row["fit_score"] = str(scored.score)
    row["fit_reason"] = "; ".join(scored.reasons)
    row["message_draft"] = ""

    existing_index = find_prospect(rows, company, name)
    if existing_index is None:
        rows.append(row)
        action = "added"
    else:
        rows[existing_index].update({key: value for key, value in row.items() if value})
        action = "updated"

    write_rows(rows)
    return {"action": action, "prospect": row}


@mcp.tool()
def list_top_prospects(limit: int = 10, min_score: int = 0) -> list[dict[str, str]]:
    """Return the highest-scoring prospects from the CSV."""
    rows = read_rows()
    filtered = [
        row for row in rows if int(row.get("fit_score") or 0) >= min_score
    ]
    filtered.sort(key=lambda row: int(row.get("fit_score") or 0), reverse=True)
    return filtered[:limit]


@mcp.tool()
def rescore_prospects() -> dict[str, Any]:
    """Recalculate fit scores for every prospect using config/criteria.json."""
    rows = read_rows()
    for row in rows:
        scored = score_fit(row)
        row["fit_score"] = str(scored.score)
        row["fit_reason"] = "; ".join(scored.reasons)
    write_rows(rows)
    return {"rescored": len(rows)}


@mcp.tool()
def draft_message(
    company: str,
    name: str = "",
    offer: str = (
        "Rimbun helps financial institutions turn payment behavior into "
        "explainable, non-credit product recommendations."
    ),
    template_name: str = "linkedin_connection.txt",
) -> dict[str, str]:
    """Draft a manual LinkedIn message for a saved prospect."""
    rows = read_rows()
    index = find_prospect(rows, company, name)
    if index is None:
        raise ValueError(f"No prospect found for company={company!r}, name={name!r}")

    message = render_template(template_name, rows[index], offer)
    rows[index]["message_draft"] = message
    write_rows(rows)
    return {"company": company, "name": rows[index].get("name", ""), "message": message}


@mcp.tool()
def update_status(
    company: str,
    name: str = "",
    status: str = "contacted",
    notes: str = "",
    last_contacted: str = "",
) -> dict[str, str]:
    """Update outreach status after you manually contact a prospect."""
    rows = read_rows()
    index = find_prospect(rows, company, name)
    if index is None:
        raise ValueError(f"No prospect found for company={company!r}, name={name!r}")

    rows[index]["status"] = status
    if notes:
        existing_notes = rows[index].get("notes", "")
        rows[index]["notes"] = f"{existing_notes} | {notes}".strip(" |")
    if last_contacted:
        rows[index]["last_contacted"] = last_contacted
    elif status in {"contacted", "replied", "follow_up"}:
        rows[index]["last_contacted"] = date.today().isoformat()

    write_rows(rows)
    return rows[index]


@mcp.tool()
def get_prospect_csv_path() -> str:
    """Return the absolute path to the editable prospects CSV."""
    ensure_files()
    return str(PROSPECTS_CSV)


@mcp.tool()
def hunter_domain_search(
    domain_or_website: str,
    limit: int = 10,
    seniority: str = "",
    department: str = "",
) -> dict[str, Any]:
    """Find public emails for a company domain using Hunter Domain Search."""
    domain = extract_domain(domain_or_website)
    params: dict[str, str | int] = {
        "domain": domain,
        "limit": max(1, min(limit, 100)),
    }
    if seniority:
        params["seniority"] = seniority
    if department:
        params["department"] = department

    result = hunter_get("domain-search", params)
    data = result.get("data") or {}
    emails = [compact_hunter_email(row) for row in (data.get("emails") or [])]
    return {
        "domain": data.get("domain", domain),
        "organization": data.get("organization", ""),
        "pattern": data.get("pattern", ""),
        "accept_all": data.get("accept_all", ""),
        "emails": emails,
        "raw_meta": result.get("meta", {}),
    }


@mcp.tool()
def hunter_email_finder(
    domain_or_website: str,
    first_name: str,
    last_name: str,
) -> dict[str, Any]:
    """Find an email for a named person at a company domain using Hunter."""
    domain = extract_domain(domain_or_website)
    result = hunter_get(
        "email-finder",
        {
            "domain": domain,
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
        },
    )
    data = result.get("data") or {}
    return {
        "domain": domain,
        "email": data.get("email", ""),
        "score": data.get("score", ""),
        "first_name": data.get("first_name", first_name),
        "last_name": data.get("last_name", last_name),
        "position": data.get("position", ""),
        "company": data.get("company", ""),
        "sources": data.get("sources", [])[:3],
    }


@mcp.tool()
def hunter_verify_email(email: str) -> dict[str, Any]:
    """Verify an email address using Hunter."""
    result = hunter_get("email-verifier", {"email": email.strip()})
    data = result.get("data") or {}
    return {
        "email": data.get("email", email),
        "status": data.get("status", ""),
        "result": data.get("result", ""),
        "score": data.get("score", ""),
        "regexp": data.get("regexp", ""),
        "gibberish": data.get("gibberish", ""),
        "disposable": data.get("disposable", ""),
        "webmail": data.get("webmail", ""),
        "mx_records": data.get("mx_records", ""),
        "smtp_server": data.get("smtp_server", ""),
        "smtp_check": data.get("smtp_check", ""),
        "accept_all": data.get("accept_all", ""),
        "block": data.get("block", ""),
    }


def main() -> None:
    ensure_files()
    mcp.run()


if __name__ == "__main__":
    main()
