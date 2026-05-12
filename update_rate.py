"""
update_rate.py — Fetches the USD/VES rate from the Banco Central de Venezuela
and writes/updates docs/rate.json and docs/history.json.

Run by GitHub Actions on a daily cron. Idempotent: re-running on the same
Venezuelan calendar date doesn't duplicate history rows.
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import requests
import urllib3
from bs4 import BeautifulSoup

BCV_URL = "https://www.bcv.org.ve/"
TIMEOUT_SECS = 20
MAX_RETRIES = 3
RETRY_BACKOFF_SECS = 30

REPO_ROOT = Path(__file__).resolve().parent
DOCS_DIR = REPO_ROOT / "docs"
RATE_FILE = DOCS_DIR / "rate.json"
HISTORY_FILE = DOCS_DIR / "history.json"

VE_TZ = timezone(timedelta(hours=-4))

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class BCVFetchError(Exception):
    pass


def fetch_usd_ves_rate() -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
    }
    try:
        resp = requests.get(BCV_URL, headers=headers, timeout=TIMEOUT_SECS, verify=False)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise BCVFetchError(f"HTTP request failed: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    dolar_div = soup.find(id="dolar")
    if dolar_div is None:
        raise BCVFetchError("Could not find <div id='dolar'> on the BCV homepage.")

    strong = dolar_div.find("strong")
    if strong is None:
        raise BCVFetchError("Found dolar div but no <strong> inside.")

    raw = strong.get_text(strip=True)
    normalized = raw.replace(".", "").replace(",", ".")
    if not re.match(r"^\d+(\.\d+)?$", normalized):
        raise BCVFetchError(f"Unexpected rate format: {raw!r}")

    fetched_at = datetime.now(timezone.utc)
    return {
        "rate": Decimal(normalized),
        "fetched_at_utc": fetched_at,
        "date_ve": fetched_at.astimezone(VE_TZ).date().isoformat(),
    }


def fetch_with_retries() -> dict:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"Attempt {attempt}/{MAX_RETRIES}...", flush=True)
            return fetch_usd_ves_rate()
        except BCVFetchError as e:
            last_err = e
            print(f"  failed: {e}", flush=True)
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_SECS * attempt
                print(f"  retrying in {wait}s", flush=True)
                time.sleep(wait)
    raise BCVFetchError(f"All {MAX_RETRIES} attempts failed: {last_err}")


def load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError) as e:
        print(f"WARN: history file unreadable ({e}); starting fresh.", flush=True)
        return []


def main() -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        result = fetch_with_retries()
    except BCVFetchError as e:
        print(f"ERROR: {e}", flush=True)
        return 1

    rate_str = f"{result['rate']:f}"
    date_ve = result["date_ve"]
    fetched_at_iso = result["fetched_at_utc"].isoformat()

    # rate.json — always overwrite with latest
    latest_payload = {
        "currency_pair": "USD/VES",
        "rate": rate_str,
        "date_ve": date_ve,
        "fetched_at_utc": fetched_at_iso,
        "source": "Banco Central de Venezuela",
        "source_url": BCV_URL,
    }
    with RATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(latest_payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # history.json — append unless date_ve already present
    history = load_history()
    if any(entry.get("date_ve") == date_ve for entry in history):
        print(f"Date {date_ve} already in history; not appending.", flush=True)
    else:
        history.append({
            "date_ve": date_ve,
            "rate": rate_str,
            "fetched_at_utc": fetched_at_iso,
        })
        history.sort(key=lambda e: e["date_ve"])
        with HISTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Appended {date_ve}: {rate_str} VES/USD", flush=True)

    print(f"Wrote {RATE_FILE.relative_to(REPO_ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
