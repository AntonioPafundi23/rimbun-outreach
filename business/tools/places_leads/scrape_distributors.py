#!/usr/bin/env python3
"""Pull Google Places (New) leads for the business (distributor / grosir) segment."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SEGMENT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SEGMENT_ROOT.parent
DEFAULT_OUTPUT = SEGMENT_ROOT / "data" / "places_leads.csv"
# One shared secrets file at repo root. Tool-local .env is a legacy fallback.
ENV_CANDIDATES = (
    REPO_ROOT / ".env",
    Path(__file__).resolve().parent / ".env",
)

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "nextPageToken",
    ]
)

DEFAULT_QUERIES = [
    "distributor Jakarta",
    "distributor Surabaya",
    "grosir Bandung",
]

FIELDNAMES = [
    "name",
    "phone",
    "website",
    "rating",
    "reviews",
    "address",
    "query",
    "place_id",
    "lead_score",
    "has_phone",
    "has_website",
]


def load_env() -> None:
    for path in ENV_CANDIDATES:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def api_key() -> str:
    load_env()
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "Missing GOOGLE_PLACES_API_KEY. "
            "Copy outreach/.env.example to outreach/.env and add your key."
        )
    return key


def places_post(url: str, key: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": FIELD_MASK,
            "User-Agent": "rimbun-places-leads/0.2",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Places API (New) HTTP {exc.code}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Places API (New) request failed: {exc}") from exc


def search_text(query: str, key: str) -> list[dict[str, Any]]:
    """Text Search (New), following nextPageToken until exhausted."""
    results: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        body: dict[str, Any] = {
            "textQuery": query,
            "pageSize": 20,
            "regionCode": "ID",
            "languageCode": "id",
        }
        if page_token:
            body["pageToken"] = page_token

        payload = places_post(SEARCH_TEXT_URL, key, body)
        results.extend(payload.get("places") or [])
        page_token = payload.get("nextPageToken") or None
        if not page_token:
            break
        time.sleep(2)

    return results


def place_name(place: dict[str, Any]) -> str:
    display = place.get("displayName") or {}
    if isinstance(display, dict):
        return str(display.get("text") or "")
    return str(display or "")


def place_phone(place: dict[str, Any]) -> str:
    return str(
        place.get("nationalPhoneNumber")
        or place.get("internationalPhoneNumber")
        or ""
    )


def lead_score(name: str, reviews: int, website: str, phone: str) -> int:
    score = 0
    lowered = name.lower()
    if any(token in lowered for token in ("distributor", "grosir", "wholesale", "agen")):
        score += 2
    if reviews >= 100:
        score += 2
    elif reviews >= 10:
        score += 1
    if website:
        score += 1
    if phone:
        score += 1
    return score


def load_existing(path: Path) -> dict[str, dict[str, str | int]]:
    """Load existing leads keyed by place_id (empty if file missing)."""
    if not path.exists():
        return {}
    by_id: dict[str, dict[str, str | int]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            place_id = str(row.get("place_id") or "").strip()
            if not place_id:
                continue
            normalized: dict[str, str | int] = {
                field: row.get(field, "") for field in FIELDNAMES
            }
            # Keep numeric fields as ints when possible for scoring display.
            for int_field in ("reviews", "lead_score"):
                try:
                    normalized[int_field] = int(normalized[int_field] or 0)
                except ValueError:
                    normalized[int_field] = 0
            by_id[place_id] = normalized
    return by_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Places API (New) into business/data/places_leads.csv"
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Search query (repeatable). Defaults to Jakarta/Surabaya/Bandung set.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--min-reviews",
        type=int,
        default=10,
        help="Skip places with fewer reviews (default: 10)",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=3,
        help="Skip places below lead score (default: 3)",
    )
    parser.add_argument(
        "--require-phone-website",
        action="store_true",
        help="Keep only rows that have both phone and website",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the CSV instead of merging by place_id (default: merge)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    key = api_key()
    queries = args.queries or DEFAULT_QUERIES

    existing = {} if args.overwrite else load_existing(args.output)
    by_id: dict[str, dict[str, str | int]] = dict(existing)
    added = 0
    updated = 0

    for query in queries:
        print(f"Searching: {query}")
        places = search_text(query, key)
        for place in places:
            place_id = str(place.get("id") or "")
            if not place_id:
                continue

            if place.get("businessStatus") == "CLOSED_PERMANENTLY":
                continue

            name = place_name(place)
            reviews = int(place.get("userRatingCount") or 0)
            if reviews < args.min_reviews:
                continue

            phone = place_phone(place)
            website = str(place.get("websiteUri") or "")
            score = lead_score(name, reviews, website, phone)
            if score < args.min_score:
                continue
            if args.require_phone_website and not (phone and website):
                continue

            row = {
                "name": name,
                "phone": phone,
                "website": website,
                "rating": place.get("rating") or "",
                "reviews": reviews,
                "address": place.get("formattedAddress") or "",
                "query": query,
                "place_id": place_id,
                "lead_score": score,
                "has_phone": "yes" if phone else "no",
                "has_website": "yes" if website else "no",
            }
            if place_id in by_id:
                updated += 1
                action = "Updated"
            else:
                added += 1
                action = "Added"
            by_id[place_id] = row
            print(f"  {action} ({score}): {name}")

    rows = list(by_id.values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    with_contact = sum(1 for row in rows if row["phone"] and row["website"])
    mode = "overwrite" if args.overwrite else "merge"
    print(
        f"Done ({mode}) -> {args.output} "
        f"({len(rows)} total, +{added} new, {updated} updated, "
        f"{with_contact} with phone+website)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
