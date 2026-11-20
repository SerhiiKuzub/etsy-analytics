"""Вивантаження товарів магазину в сирому вигляді (data/raw/listings).

Запуск: python -m src.extract.extract_listings
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.extract.etsy_client import get

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "listings"
PAGE_SIZE = 100
STATES = ["active", "inactive", "sold_out", "expired"]


def fetch_state(shop_id: str, state: str) -> list[dict]:
    """Забирає всі сторінки товарів з потрібним статусом."""
    results, offset = [], 0
    while True:
        page = get(
            f"/shops/{shop_id}/listings",
            {"state": state, "limit": PAGE_SIZE, "offset": offset},
        )
        batch = page.get("results", [])
        results.extend(batch)
        offset += PAGE_SIZE
        if len(batch) < PAGE_SIZE or offset >= page.get("count", 0):
            return results


def main() -> None:
    shop_id = os.environ["ETSY_SHOP_ID"]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()

    for state in STATES:
        try:
            items = fetch_state(shop_id, state)
        except RuntimeError as err:
            print(f"{state}: пропущено ({str(err)[:80]})")
            continue
        payload = {"fetched_at": fetched_at, "state": state, "results": items}
        (RAW_DIR / f"{state}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        print(f"{state}: {len(items)} товарів")


if __name__ == "__main__":
    main()