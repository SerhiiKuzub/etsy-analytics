"""Що змінилось у 2025-2026: регіони, ціна доставки, активність, життєвий цикл хітів.

Запуск: python -m src.analysis.what_changed
"""
import pandas as pd

from src.load.load_real_data import EU, get_engine


def half(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s)
    return d.dt.year.astype(str) + "H" + ((d.dt.month - 1) // 6 + 1).astype(str)


def main() -> None:
    eng = get_engine()
    orders = pd.read_sql("SELECT created_at, buyer_country, shipping_amount FROM core.orders", eng)
    fees = pd.read_sql("SELECT created_at, fee_type FROM core.fees", eng)
    facts = pd.read_sql("SELECT listing_id, order_date, quantity FROM analytics.v_item_facts", eng)

    orders["period"] = half(orders["created_at"])
    orders["region"] = orders["buyer_country"].map(
        lambda c: "US" if c == "US" else "EU" if c in EU else "OTHER")
    orders["shipping_amount"] = orders["shipping_amount"].astype(float)
    orders = orders[orders["period"] >= "2022H1"]

    t1 = orders.pivot_table(index="period", columns="region", values="created_at",
                            aggfunc="count", fill_value=0)
    t1["ALL"] = t1.sum(axis=1)
    print("1) Замовлень за півріччями й регіонами (2026H2 неповне: до листопада)")
    print(t1.to_string())

    paid_us = orders[(orders["region"] == "US") & (orders["shipping_amount"] > 0)]
    print("\n2) Типова плата покупця зі США за доставку (медіана) і кількість таких замовлень")
    print(paid_us.groupby("period")["shipping_amount"].agg(["median", "count"]).round(2).to_string())

    fees["period"] = half(fees["created_at"])
    fees = fees[fees["period"] >= "2022H1"]
    act = fees[fees["fee_type"].isin(["etsy_ads", "renewal", "listing"])]
    t3 = act.pivot_table(index="period", columns="fee_type", values="created_at",
                         aggfunc="count", fill_value=0)
    print("\n3) Активність у журналі (кількість записів): etsy_ads = реклама, renewal = поновлення, listing = нові розміщення")
    print(t3.to_string())

    facts["year"] = pd.to_datetime(facts["order_date"]).dt.year
    facts["quantity"] = facts["quantity"].astype(float)
    by = facts.pivot_table(index="listing_id", columns="year", values="quantity",
                           aggfunc="sum", fill_value=0)
    by["total"] = by.sum(axis=1)
    top_ids = by["total"].nlargest(8).index
    top = by.loc[top_ids].copy()
    rest = by.drop(index=top_ids).sum().rename("others")
    top.index = list("ABCDEFGH")
    out = pd.concat([top, rest.to_frame().T]).astype(int)
    print("\n4) Продано штук по роках: вісім найкращих товарів (A-H, назви приховано) і решта")
    print(out.to_string())


if __name__ == "__main__":
    main()