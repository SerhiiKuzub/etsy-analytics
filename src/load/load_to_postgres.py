"""Завантажує CSV з data/sample у PostgreSQL (схема core).

Запуск: python -m src.load.load_to_postgres
"""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Text, create_engine, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "sample"
load_dotenv(ROOT / ".env")


def get_engine():
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )
    return create_engine(url)


def main():
    listings = pd.read_csv(DATA_DIR / "listings.csv", parse_dates=["created_at"])
    listings["tags"] = listings["tags"].str.split("|")
    costs = pd.read_csv(DATA_DIR / "product_costs.csv", parse_dates=["updated_at"])
    orders = pd.read_csv(DATA_DIR / "orders.csv", parse_dates=["created_at"])
    items = pd.read_csv(DATA_DIR / "order_items.csv")
    fees = pd.read_csv(DATA_DIR / "fees.csv", parse_dates=["created_at"])

    engine = get_engine()
    with engine.begin() as conn:  # одна транзакція: або все, або нічого
        conn.execute(text(
            "TRUNCATE core.fees, core.order_items, core.product_costs, "
            "core.orders, core.listings RESTART IDENTITY CASCADE"
        ))
        opts = dict(schema="core", if_exists="append", index=False,
                    method="multi", chunksize=1000)
        listings.to_sql("listings", conn, dtype={"tags": ARRAY(Text)}, **opts)
        costs.to_sql("product_costs", conn, **opts)
        orders.to_sql("orders", conn, **opts)
        items.to_sql("order_items", conn, **opts)
        fees.to_sql("fees", conn, **opts)

    print("Готово: дані завантажено в core.*")


if __name__ == "__main__":
    main()