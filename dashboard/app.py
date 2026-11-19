"""Дашборд аналітики Etsy-магазину (демо на синтетичних даних).

Запуск (з кореня проекту): streamlit run dashboard/app.py
"""
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

st.set_page_config(page_title="Etsy Shop Analytics", page_icon="📊", layout="wide")


@st.cache_resource
def get_engine():
    """Одне підключення до БД на весь час роботи дашборду."""
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )
    return create_engine(url)


@st.cache_data(ttl=600)
def load(query: str) -> pd.DataFrame:
    """Виконує SQL і кешує результат на 10 хвилин."""
    df = pd.read_sql(query, get_engine())
    # Postgres повертає NUMERIC як Decimal, перетворюємо на звичайні числа
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = df[col].astype(float)
            except (TypeError, ValueError):
                pass
    return df


monthly = load("SELECT * FROM analytics.v_monthly_revenue ORDER BY month")
products = load("SELECT * FROM analytics.v_product_margin")

# ---------- Заголовок ----------
st.title("📊 Etsy Shop Analytics")
st.caption("Демо на синтетичних даних. Показники прибутку не враховують доставку, "
           "рекламу поза Etsy, податки й працю.")

# ---------- KPI (за весь період) ----------
revenue = products["revenue"].sum()
profit = products["profit"].sum()
orders = int(monthly["orders"].sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Виручка", f"${revenue:,.0f}")
c2.metric("Прибуток", f"${profit:,.0f}")
c3.metric("Маржа", f"{100 * profit / revenue:.1f}%")
c4.metric("Замовлень", f"{orders:,}")

st.divider()

# ---------- Виручка по місяцях ----------
st.subheader("Виручка по місяцях")
only_full = st.checkbox("Тільки повні місяці", value=True,
                        help="Перший і останній місяці неповні й спотворюють тренд")
m = monthly[monthly["is_full_month"]] if only_full else monthly
fig = px.bar(m, x="month", y="revenue",
             labels={"month": "Місяць", "revenue": "Виручка, USD"})
st.plotly_chart(fig, use_container_width=True)

# ---------- Категорії ----------
st.subheader("Категорії: виручка vs прибуток")
cat = (products.groupby("category")[["revenue", "profit"]].sum()
       .reset_index().sort_values("profit", ascending=False))
fig2 = px.bar(cat.melt(id_vars="category", var_name="metric", value_name="usd"),
              x="category", y="usd", color="metric", barmode="group",
              labels={"category": "Категорія", "usd": "USD", "metric": ""})
st.plotly_chart(fig2, use_container_width=True)

# ---------- Таблиця товарів ----------
st.subheader("Товари: маржинальність")
table = products[["title", "category", "units", "revenue", "etsy_fees",
                  "cogs", "profit", "margin_pct"]].sort_values("margin_pct")


def highlight_loss(row):
    color = "background-color: #ffd6d6" if row["profit"] < 0 else ""
    return [color] * len(row)


st.dataframe(table.style.apply(highlight_loss, axis=1),
             use_container_width=True, hide_index=True)
st.caption("Червоним підсвічено збиткові товари.")