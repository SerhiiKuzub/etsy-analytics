"""Динаміка магазину по роках: індекси й відсотки, без абсолютних сум.

Запуск: python -m src.analysis.yearly_dynamics
"""
from datetime import date

import pandas as pd

from src.load.load_real_data import get_engine


def main() -> None:
    eng = get_engine()
    facts = pd.read_sql(
        "SELECT order_id, order_date, listing_id, revenue, profit, cost_known "
        "FROM analytics.v_item_facts", eng)
    orders = pd.read_sql("SELECT order_id, created_at, discount_amount FROM core.orders", eng)
    listings = pd.read_sql("SELECT listing_id, created_at FROM core.listings", eng)

    for col in ["revenue", "profit"]:
        facts[col] = facts[col].astype(float)
    orders["discount_amount"] = orders["discount_amount"].astype(float)
    facts["year"] = pd.to_datetime(facts["order_date"]).dt.year
    orders["year"] = pd.to_datetime(orders["created_at"]).dt.year
    listings["year"] = pd.to_datetime(listings["created_at"]).dt.year

    first = pd.to_datetime(orders["created_at"].min()).date()
    today = date.today()

    def days_covered(y: int) -> int:
        start, end = max(date(y, 1, 1), first), min(date(y, 12, 31), today)
        return (end - start).days + 1

    rows = []
    for y, g in facts.groupby("year"):
        o = orders[orders["year"] == y]
        d = days_covered(y)
        known = g[g["cost_known"]]
        by_listing = g.groupby("listing_id")["revenue"].sum().sort_values(ascending=False)
        rows.append({
            "year": y,
            "orders_per_30d": 30 * g["order_id"].nunique() / d,
            "revenue_per_day": g["revenue"].sum() / d,
            "margin_%": 100 * known["profit"].sum() / known["revenue"].sum(),
            "orders_with_discount_%": 100 * (o["discount_amount"] > 0).mean(),
            "discount_%_of_list": 100 * o["discount_amount"].sum()
                                  / (g["revenue"].sum() + o["discount_amount"].sum()),
            "top3_listings_share_%": 100 * by_listing.head(3).sum() / by_listing.sum(),
            "listings_sold": g["listing_id"].nunique(),
            "new_listings": int((listings["year"] == y).sum()),
        })

    t = pd.DataFrame(rows).set_index("year")
    t["revenue_index"] = 100 * t["revenue_per_day"] / t["revenue_per_day"].max()
    print(t.drop(columns="revenue_per_day").round(1).to_string())
    print("\nrevenue_index: 100 = найкращий рік за виручкою на день (2021 і 2026 неповні роки,")
    print("тому всі показники нормовано на кількість днів із даними)")


if __name__ == "__main__":
    main()