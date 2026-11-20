"""Вивантаження замовлень (receipts) у сирому вигляді (data/raw/receipts).

Запуск: python -m src.extract.extract_receipts
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.extract.etsy_client import get

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "receipts"
PAGE_SIZE = 100


def main() -> None:
    shop_id = os.environ["ETSY_SHOP_ID"]
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    results, offset = [], 0
    while True:
        page = get(
            f"/shops/{shop_id}/receipts",
            {"limit": PAGE_SIZE, "offset": offset,
             "sort_on": "created", "sort_order": "asc"},
        )
        batch = page.get("results", [])
        results.extend(batch)
        total = page.get("count", 0)
        print(f"{len(results)} / {total}")
        offset += PAGE_SIZE
        if len(batch) < PAGE_SIZE or offset >= total:
            break

    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    (RAW_DIR / "receipts.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Збережено замовлень: {len(results)}")


if __name__ == "__main__":
    main()