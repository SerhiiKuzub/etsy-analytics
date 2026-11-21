"""Перетворює сирі дані Etsy (data/raw) на таблиці бази etsy_real.

Запуск: python -m src.load.load_real_data
"""
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Text, create_engine, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
load_dotenv(ROOT / ".env")

DB_NAME = os.getenv("REAL_DB_NAME", "etsy_real")
PAYMENT_MATCH_DAYS = 3  # допуск між замовленням і платежем у журналі


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def money(d: dict) -> float:
    return d["amount"] / d["divisor"]


def ts(t: int) -> datetime:
    return datetime.fromtimestamp(t, timezone.utc).replace(tzinfo=None)


def get_engine():
    if DB_NAME == os.environ["POSTGRES_DB"]:
        raise SystemExit("REAL_DB_NAME збігається з демо-базою. Зупиняюсь, щоб не змішати дані.")
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=DB_NAME,
    )
    return create_engine(url)


def build_listings() -> pd.DataFrame:
    rows = {}
    for state in ["active", "inactive", "sold_out", "expired"]:
        path = RAW / "listings" / f"{state}.json"
        if not path.exists():
            continue
        for x in read(path)["results"]:
            rows[x["listing_id"]] = {
                "listing_id": x["listing_id"],
                "title": x["title"],
                "price": money(x["price"]),
                "currency": x["price"]["currency_code"],
                "created_at": ts(x["created_timestamp"]),
                "tags": x.get("tags") or [],
                "views": x.get("views"),
                "favorites": x.get("num_favorers"),
                "state": x.get("state", state),
            }
    return pd.DataFrame(rows.values())


def build_orders(receipts: list[dict], salt: str):
    orders, items = [], []
    for r in receipts:
        assert r["grandtotal"]["divisor"] == 100, "очікуємо суми в центах"
        buyer = hashlib.sha256(f"{salt}:{r['buyer_user_id']}".encode()).hexdigest()[:16]
        orders.append({
            "order_id": r["receipt_id"],
            "created_at": ts(r["created_timestamp"]),
            "buyer_country": r.get("country_iso"),
            "buyer_hash": buyer,
            "total_amount": money(r["grandtotal"]),
            "shipping_amount": money(r["total_shipping_cost"]),
            "currency": r["grandtotal"]["currency_code"],
            "payment_method": r["payment_method"],
        })
        for t in r["transactions"]:
            items.append({
                "order_id": r["receipt_id"],
                "listing_id": t["listing_id"],
                "quantity": t["quantity"],
                "line_total": money(t["price"]) * t["quantity"],
            })
    items = (pd.DataFrame(items)
             .groupby(["order_id", "listing_id"], as_index=False)
             .agg(quantity=("quantity", "sum"), line_total=("line_total", "sum")))
    items["unit_price"] = (items["line_total"] / items["quantity"]).round(2)
    return pd.DataFrame(orders), items.drop(columns="line_total")


def build_fees(ledger: list[dict], receipts: list[dict]):
    """Розкладає записи журналу по замовленнях, товарах або накладних витратах."""
    valid_orders = {r["receipt_id"] for r in receipts}
    tx_map = {t["transaction_id"]: (r["receipt_id"], t["listing_id"])
              for r in receipts for t in r["transactions"]}
    by_entry = {e["entry_id"]: e for e in ledger}

    # Платіж у журналі -> замовлення карткою (збіг за сумою й датою)
    cc = [r for r in receipts if r["payment_method"] == "cc"]
    gross_to_receipt = {}
    for g in (e for e in ledger if e["ledger_type"] == "PAYMENT_GROSS"):
        m = [r for r in cc
             if abs(r["created_timestamp"] - g["created_timestamp"]) <= PAYMENT_MATCH_DAYS * 86400
             and abs(r["grandtotal"]["amount"] - g["amount"]) <= 1]
        if len(m) == 1:
            gross_to_receipt[g["reference_id"]] = m[0]["receipt_id"]

    skip = {"sales_tax", "billing_payment", "DISBURSE2", "PAYMENT_GROSS"}
    tx_types = {"transaction", "transaction_quantity"}
    receipt_types = {"shipping_transaction": "shipping_transaction",
                     "offsite_ads_fee": "offsite_ads",
                     "vat_on_processing_fees": "vat_processing"}
    listing_types = {"listing": "listing", "renew_sold": "renewal",
                     "renew_sold_auto": "renewal", "renew_expired": "renewal",
                     "auto_renew_expired": "renewal", "listing_refund": "listing_refund"}
    overhead_types = {"prolist": "etsy_ads", "MISC_CR_SL": "misc_credit"}

    def owner(e: dict, depth: int = 0):
        """(fee_type, order_id, listing_id) або None, якщо запис не є витратою."""
        lt, ref = e["ledger_type"], e["reference_id"]
        if lt in skip:
            return None
        if lt in tx_types:
            order, listing = tx_map.get(ref, (None, None))
            return ("transaction", order, listing)
        if lt in receipt_types:
            return (receipt_types[lt], ref, None)
        if lt == "PAYMENT_PROCESSING_FEE":
            return ("processing", gross_to_receipt.get(ref), None)
        if lt in listing_types:
            return (listing_types[lt], None, ref)
        if lt in overhead_types:
            return (overhead_types[lt], None, None)
        if lt.startswith("vat_seller_services"):
            parent = by_entry.get(e.get("parent_entry_id"))
            if parent and depth < 5:
                p = owner(parent, depth + 1)
                if p:
                    return ("vat_on_fees", p[1], p[2])
            return ("vat_on_fees", None, None)
        return ("other", None, None)

    rows, stats = [], Counter()
    for e in ledger:
        o = owner(e)
        if o is None:
            stats["пропущено (не витрата)"] += 1
            continue
        fee_type, order_id, listing_id = o
        if order_id not in valid_orders:
            order_id = None
        rows.append({
            "order_id": order_id,
            "listing_id": listing_id,
            "fee_type": fee_type,
            "amount": round(-e["amount"] / 100, 2),  # витрата додатна, кредит від'ємний
            "created_at": ts(e["created_timestamp"]),
        })
        stats["до замовлення" if order_id else "до товару" if listing_id else "накладні"] += 1

    fees = pd.DataFrame(rows)
    fees["order_id"] = fees["order_id"].astype("Int64")
    fees["listing_id"] = fees["listing_id"].astype("Int64")
    return fees, stats


def main() -> None:
    salt = os.environ["HASH_SALT"]
    receipts = read(RAW / "receipts" / "receipts.json")["results"]
    ledger = read(RAW / "ledger" / "ledger.json")["results"]

    listings = build_listings()
    orders, items = build_orders(receipts, salt)
    fees, stats = build_fees(ledger, receipts)
    if not set(items["listing_id"]) <= set(listings["listing_id"]):
        raise SystemExit("Є продані товари, яких немає в каталозі.")

    ledger_df = pd.DataFrame([{
        "entry_id": e["entry_id"],
        "created_at": ts(e["created_timestamp"]),
        "ledger_type": e["ledger_type"],
        "reference_type": e["reference_type"],
        "amount_usd": e["amount"] / 100,
    } for e in ledger])

    engine = get_engine()
    with engine.begin() as conn:  # одна транзакція: або все, або нічого
        conn.execute(text(
            "TRUNCATE core.fees, core.order_items, core.product_costs, "
            "core.orders, core.listings RESTART IDENTITY CASCADE"
        ))
        opts = dict(schema="core", if_exists="append", index=False,
                    method="multi", chunksize=1000)
        listings.to_sql("listings", conn, dtype={"tags": ARRAY(Text)}, **opts)
        orders.to_sql("orders", conn, **opts)
        items.to_sql("order_items", conn, **opts)
        fees.to_sql("fees", conn, **opts)
        ledger_df.to_sql("ledger_entries", conn, schema="raw",
                         if_exists="replace", index=False)

    print(f"listings: {len(listings)}, orders: {len(orders)}, items: {len(items)}, "
          f"fees: {len(fees)}, ledger: {len(ledger_df)}")
    print("fees розподілено:", dict(stats))
    processed = fees[(fees["fee_type"] == "processing") & fees["order_id"].notna()]
    print("карткових замовлень із комісією обробки:", processed["order_id"].nunique())
    print("замовлень зі знижкою:", sum(1 for r in receipts if r["discount_amt"]["amount"] > 0))


if __name__ == "__main__":
    main()