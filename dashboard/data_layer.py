"""Доступ до даних дашборду: Postgres локально або DuckDB з CSV у демо-режимі.

Демо-режим вмикається, коли немає налаштувань Postgres (наприклад, у Streamlit Cloud)
або задано DEMO_MODE=1. Тоді SQL-моделі з sql/models виконуються над data/sample/*.csv.
"""
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SAMPLE = ROOT / "data" / "sample"
MODELS = sorted((ROOT / "sql" / "models").glob("*.sql"))
TABLES = ["listings", "product_costs", "orders", "order_items", "fees"]


def use_demo() -> bool:
    return os.getenv("DEMO_MODE") == "1" or not os.getenv("POSTGRES_USER")


@st.cache_resource
def _demo_connection():
    import duckdb

    con = duckdb.connect()  # база в пам'яті
    con.execute("CREATE SCHEMA core")
    for name in TABLES:
        path = (SAMPLE / f"{name}.csv").as_posix()
        con.execute(f"CREATE TABLE core.{name} AS SELECT * FROM read_csv_auto('{path}')")
    # Колонки, які є в схемі Postgres, але яких немає в синтетичних CSV
    con.execute("ALTER TABLE core.orders ADD COLUMN shipping_cost_est DOUBLE")
    con.execute("ALTER TABLE core.product_costs ADD COLUMN packaging_cost DOUBLE DEFAULT 0")
    con.execute("UPDATE core.product_costs SET packaging_cost = 0")
    con.execute("ALTER TABLE core.fees ADD COLUMN listing_id BIGINT")
    con.execute("ALTER TABLE core.listings ADD COLUMN state VARCHAR")
    for model in MODELS:
        con.execute(model.read_text(encoding="utf-8"))
    return con


@st.cache_resource
def _pg_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL

    return create_engine(URL.create(
        "postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    ))


def read_df(sql: str) -> pd.DataFrame:
    if use_demo():
        # cursor() дає окреме з'єднання для кожного запиту, це безпечно для потоків Streamlit
        return _demo_connection().cursor().execute(sql).df()
    return pd.read_sql(sql, _pg_engine())