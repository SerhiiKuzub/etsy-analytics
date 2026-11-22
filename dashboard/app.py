"""Дашборд аналітики Etsy-магазину (демо на синтетичних даних).

Запуск (з кореня проекту): streamlit run dashboard/app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from data_layer import read_df, use_demo

st.set_page_config(page_title="Etsy Shop Analytics", page_icon="📊", layout="wide")


@st.cache_data(ttl=600)
def load_facts() -> pd.DataFrame:
    """Читає факт-view та приводить типи (Postgres NUMERIC -> float, дати -> datetime)."""
    df = read_df("SELECT * FROM analytics.v_item_facts")
    for col in ["quantity", "revenue", "etsy_fees", "cogs", "profit"]:
        df[col] = df[col].astype(float)
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["month"] = pd.to_datetime(df["month"])
    return df


facts = load_facts()

# ---------- Бокова панель: фільтри ----------
st.sidebar.header("Фільтри")
d_min = facts["order_date"].min().date()
d_max = facts["order_date"].max().date()
period = st.sidebar.date_input("Період", value=(d_min, d_max),
                               min_value=d_min, max_value=d_max)
if len(period) != 2:
    st.info("Оберіть кінцеву дату періоду.")
    st.stop()

all_categories = sorted(facts["category"].unique())
chosen = st.sidebar.multiselect("Категорії", all_categories, default=all_categories)

mask = (
    (facts["order_date"] >= pd.Timestamp(period[0]))
    & (facts["order_date"] <= pd.Timestamp(period[1]))
    & facts["category"].isin(chosen)
)
df = facts[mask]
if df.empty:
    st.warning("Для обраних фільтрів даних немає.")
    st.stop()

# ---------- Заголовок і KPI ----------
st.title("📊 Etsy Shop Analytics")
st.caption("Демо на синтетичних даних. Виручка рахується по товарах (без доставки); "
           "прибуток = виручка − комісії Etsy − собівартість. Не враховано: "
           "доставку, рекламу поза Etsy, податки й працю.")

revenue = df["revenue"].sum()
profit = df["profit"].sum()
orders = df["order_id"].nunique()
orders_per_buyer = df.groupby("buyer_hash")["order_id"].nunique()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Виручка", f"${revenue:,.0f}")
k2.metric("Прибуток", f"${profit:,.0f}")
k3.metric("Маржа", f"{100 * profit / revenue:.1f}%")
k4.metric("Замовлень", f"{orders:,}")
k5.metric("Середній чек", f"${revenue / orders:,.2f}")
k6.metric("Повторні покупці", f"{100 * (orders_per_buyer > 1).mean():.0f}%")

st.divider()
tab1, tab2, tab3 = st.tabs(["Огляд", "Товари", "Покупці"])

# ---------- Вкладка 1: Огляд ----------
with tab1:
    st.subheader("Виручка і прибуток по місяцях")
    hide_partial = st.checkbox(
        "Приховати неповні місяці", value=True,
        help="Місяці, які обрізані початком/кінцем даних або вашим фільтром періоду, "
             "спотворюють тренд")
    monthly = df.groupby("month", as_index=False)[["revenue", "profit"]].sum()
    lo = max(pd.Timestamp(period[0]), facts["order_date"].min())
    hi = min(pd.Timestamp(period[1]), facts["order_date"].max())
    month_end = monthly["month"] + pd.offsets.MonthEnd(0)
    monthly["is_full"] = (monthly["month"] >= lo) & (month_end <= hi)
    if hide_partial:
        monthly = monthly[monthly["is_full"]]

    fig = px.line(
        monthly.melt(id_vars="month", value_vars=["revenue", "profit"],
                     var_name="metric", value_name="usd"),
        x="month", y="usd", color="metric", markers=True,
        labels={"month": "Місяць", "usd": "USD", "metric": ""},
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("Категорії: виручка vs прибуток")
    cat = (df.groupby("category", as_index=False)[["revenue", "profit"]].sum()
           .sort_values("profit", ascending=False))
    fig2 = px.bar(
        cat.melt(id_vars="category", var_name="metric", value_name="usd"),
        x="category", y="usd", color="metric", barmode="group",
        labels={"category": "Категорія", "usd": "USD", "metric": ""},
    )
    st.plotly_chart(fig2, width="stretch")

# ---------- Вкладка 2: Товари ----------
with tab2:
    prod = (df.groupby(["listing_id", "title", "category"], as_index=False)
            .agg(units=("quantity", "sum"), revenue=("revenue", "sum"),
                 etsy_fees=("etsy_fees", "sum"), cogs=("cogs", "sum"),
                 profit=("profit", "sum")))
    prod["margin_pct"] = 100 * prod["profit"] / prod["revenue"]

    loss = prod[prod["profit"] < 0]
    if not loss.empty:
        st.warning(f"Збиткових товарів: {len(loss)}. Сумарний збиток: "
                   f"${-loss['profit'].sum():,.0f}. Вони приносять "
                   f"${loss['revenue'].sum():,.0f} виручки, тож за виручкою "
                   f"виглядають успішними.")

    st.subheader("Виручка проти маржі")
    fig3 = px.scatter(
        prod, x="revenue", y="margin_pct", size="units", color="category",
        hover_name="title",
        labels={"revenue": "Виручка, USD", "margin_pct": "Маржа, %",
                "category": "Категорія", "units": "Продано, шт."},
    )
    fig3.add_hline(y=0, line_dash="dash")
    st.plotly_chart(fig3, width="stretch")
    st.caption("Праворуч-внизу найнебезпечніші товари: великі продажі при нульовій "
               "або від'ємній марджі.")

    st.subheader("Парето-аналіз: внесок товарів у виручку")
    par = prod.sort_values("revenue", ascending=False).reset_index(drop=True)
    par["cum_pct"] = 100 * par["revenue"].cumsum() / par["revenue"].sum()
    n80 = int((par["cum_pct"] < 80).sum()) + 1
    fig4 = go.Figure()
    fig4.add_bar(x=par["title"], y=par["revenue"], name="Виручка, USD")
    fig4.add_scatter(x=par["title"], y=par["cum_pct"], name="Накопичено, %",
                     yaxis="y2", mode="lines+markers")
    fig4.update_layout(
        yaxis=dict(title="Виручка, USD"),
        yaxis2=dict(title="Накопичено, %", overlaying="y", side="right",
                    range=[0, 105]),
        xaxis=dict(tickangle=-60),
        legend=dict(orientation="h"),
    )
    st.plotly_chart(fig4, width="stretch")
    st.caption(f"{n80} із {len(par)} товарів дають ~80% виручки.")

    st.subheader("Товари: маржинальність")
    table = (prod[["title", "category", "units", "revenue", "etsy_fees",
                   "cogs", "profit", "margin_pct"]]
             .sort_values("margin_pct").round(2))

    def highlight_loss(row):
        color = "background-color: #ffd6d6; color: #000" if row["profit"] < 0 else ""
        return [color] * len(row)

    st.dataframe(table.style.apply(highlight_loss, axis=1),
                 width="stretch", hide_index=True)
    st.caption("Червоним підсвічено збиткові товари.")

# ---------- Вкладка 3: Покупці ----------
with tab3:
    geo = (df.groupby("buyer_country", as_index=False)
           .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
           .sort_values("revenue", ascending=False))
    geo["avg_order"] = (geo["revenue"] / geo["orders"]).round(2)

    st.subheader("Виручка за країнами покупців")
    fig5 = px.bar(geo, x="buyer_country", y="revenue",
                  labels={"buyer_country": "Країна", "revenue": "Виручка, USD"})
    st.plotly_chart(fig5, width="stretch")
    st.dataframe(geo.round(2), width="stretch", hide_index=True)