"""Когорти лістингів, порівняння однакових періодів і сезонність (лише кількості).

Запуск: python -m src.analysis.listing_cohorts
"""
from datetime import date

import pandas as pd
from scipy import stats

from src.load.load_real_data import get_engine


def main() -> None:
    eng = get_engine()
    facts = pd.read_sql(
        "SELECT order_date, listing_id, quantity FROM analytics.v_item_facts", eng)
    listings = pd.read_sql("SELECT listing_id, created_at FROM core.listings", eng)
    orders = pd.read_sql("SELECT created_at FROM core.orders", eng)

    facts["quantity"] = facts["quantity"].astype(float)
    facts["sale_year"] = pd.to_datetime(facts["order_date"]).dt.year
    listings["cohort"] = pd.to_datetime(listings["created_at"]).dt.year
    df = facts.merge(listings[["listing_id", "cohort"]], on="listing_id")

    units = df.pivot_table(index="cohort", columns="sale_year", values="quantity",
                           aggfunc="sum", fill_value=0)
    size = listings.groupby("cohort").size().rename("listings_in_catalog")
    sold = df.groupby("cohort")["listing_id"].nunique().rename("listings_that_sold")
    table = size.to_frame().join(units).join(sold).fillna(0).astype(int)
    print("1) Когорти лістингів: продано штук")
    print("   (рядок = рік створення товару, стовпці = рік продажу)")
    print(table.to_string())
    print("   Увага: видалені лістинги в каталозі відсутні, тому розміри когорт занижені.\n")

    d = pd.to_datetime(orders["created_at"])
    today = date.today()
    in_period = (d.dt.month * 100 + d.dt.day) <= today.month * 100 + today.day
    same = d[in_period].dt.year.value_counts().sort_index()
    print(f"2) Замовлень за 1 січня - {today:%d.%m} кожного року")
    print(same.to_string())
    if 2025 in same.index and 2026 in same.index:
        p = stats.binomtest(int(same[2026]), int(same[2025] + same[2026]), 0.5).pvalue
        print(f"   2025 -> 2026 за однаковий період: x{same[2026] / same[2025]:.2f}, p = {p:.3f}\n")

    print("3) Замовлень по кварталах")
    print(pd.crosstab(d.dt.year, d.dt.quarter).rename(columns=lambda q: f"Q{q}").to_string())


if __name__ == "__main__":
    main()