"""Вивантаження записів платіжного рахунку (комісії, виплати) у data/raw/ledger.

Запуск: python -m src.extract.extract_ledger
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.extract.etsy_client import get

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "ledger"
PAGE_SIZE = 100
START = datetime(2020, 10, 1, tzinfo=timezone.utc)  # трохи раніше за першу продажу
CHUNK_DAYS = 30  # Etsy дозволяє діапазон не більше 31 дня


def fetch_range(shop_id: str, start_ts: int, end_ts: int) -> list[dict]:
    results, offset = [], 0
    while True:
        page = get(
            f"/shops/{shop_id}/payment-account/ledger-entries",
            {"min_created": start_ts, "max_created": end_ts,
             "limit": PAGE_SIZE, "offset": offset},
        )
        batch = page.get("results", [])
        results.extend(batch)
        offset += PAGE_SIZE
        if len(batch) < PAGE_SIZE or offset >= page.get("count", 0):
            return results


def main() -> None:
    shop_id = os.environ["ETSY_SHOP_ID"]
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    entries: dict[str, dict] = {}  # ключ = вміст запису, щоб прибрати дублі
    window_start = START
    while window_start < now:
        window_end = min(window_start + timedelta(days=CHUNK_DAYS) - timedelta(seconds=1), now)
        batch = fetch_range(shop_id, int(window_start.timestamp()), int(window_end.timestamp()))
        for e in batch:
            entries[json.dumps(e, sort_keys=True)] = e
        if batch:
            print(f"{window_start:%Y-%m-%d}: +{len(batch)}")
        window_start = window_end + timedelta(seconds=1)

    payload = {"fetched_at": now.isoformat(), "results": list(entries.values())}
    (RAW_DIR / "ledger.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Збережено записів: {len(entries)}")


if __name__ == "__main__":
    main()