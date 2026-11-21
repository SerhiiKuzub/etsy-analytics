"""Перевірка гіпотез про спад продажів: чесна статистика для малих вибірок.

Запуск: python -m src.analysis.decline_checks
"""
import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

from src.load.load_real_data import RAW, get_engine

TODAY = date.today()


def days_in(year: int, first: date) -> int:
    start, end = max(date(year, 1, 1), first), min(date(year, 12, 31), TODAY)
    return (end - start).days + 1


def rate_ci(k: int, days: int) -> tuple[float, float]:
    """Точний 95% інтервал Пуассона для замовлень на 30 днів."""
    lo = stats.chi2.ppf(0.025, 2 * k) / 2 if k else 0.0
    hi = stats.chi2.ppf(0.975, 2 * (k + 1)) / 2
    return 30 * lo / days, 30 * hi / days


def main() -> None:
    eng = get_engine()
    orders = pd.read_sql("SELECT created_at FROM core.orders", eng)
    orders["year"] = pd.to_datetime(orders["created_at"]).dt.year
    first = pd.to_datetime(orders["created_at"].min()).date()
    counts = orders["year"].value_counts().sort_index()
    days = {y: days_in(y, first) for y in counts.index}

    print("1) Замовлень на 30 днів, 95% довірчий інтервал")
    for y, k in counts.items():
        lo, hi = rate_ci(int(k), days[y])
        print(f"   {y}: {k:3d} замовлень | {30 * k / days[y]:.1f} [{lo:.1f}; {hi:.1f}]")

    print("\n2) Чи випадкова різниця між роками (точний біноміальний тест)")
    for a, b in [(2022, 2023), (2023, 2024), (2024, 2025), (2025, 2026)]:
        k1, k2 = int(counts[a]), int(counts[b])
        p = stats.binomtest(k2, k1 + k2, days[b] / (days[a] + days[b])).pvalue
        ratio = (k2 / days[b]) / (k1 / days[a])
        print(f"   {a} -> {b}: інтенсивність x{ratio:.2f}, p = {p:.3f}")

    # Склад замовлень по роках (за сирими даними)
    receipts = json.loads((RAW / "receipts" / "receipts.json").read_text(encoding="utf-8"))["results"]
    rows = []
    for r in receipts:
        txs = r["transactions"]
        units = sum(t["quantity"] for t in txs)
        gross = sum(t["price"]["amount"] / t["price"]["divisor"] * t["quantity"] for t in txs)
        digital = sum(t["quantity"] for t in txs if t.get("is_digital"))
        rows.append({
            "year": datetime.fromtimestamp(r["created_timestamp"], timezone.utc).year,
            "units": units, "list_price": gross / units, "digital": digital / units,
        })
    comp = pd.DataFrame(rows).groupby("year").agg(
        units_per_order=("units", "mean"),
        list_price_per_unit=("list_price", "mean"),
        digital_share_pct=("digital", "mean"),
    )
    comp["list_price_idx_2023=100"] = 100 * comp["list_price_per_unit"] / comp.loc[2023, "list_price_per_unit"]
    comp["digital_share_pct"] *= 100
    print("\n3) Склад замовлень (ціна показана індексом, 2023 = 100)")
    print(comp.drop(columns="list_price_per_unit").round(1).to_string())

    # Вік лістингів у момент продажу
    facts = pd.read_sql("SELECT listing_id, order_date, revenue FROM analytics.v_item_facts", eng)
    listings = pd.read_sql("SELECT listing_id, created_at FROM core.listings", eng)
    facts["revenue"] = facts["revenue"].astype(float)
    df = facts.merge(listings, on="listing_id")
    df["age"] = pd.to_datetime(df["order_date"]).dt.year - pd.to_datetime(df["created_at"]).dt.year
    df["bucket"] = np.select([df["age"] <= 0, df["age"] == 1], ["same year", "1 year"], "2+ years")
    df["year"] = pd.to_datetime(df["order_date"]).dt.year
    share = df.pivot_table(index="year", columns="bucket", values="revenue", aggfunc="sum", fill_value=0)
    share = 100 * share.div(share.sum(axis=1), axis=0)
    print("\n4) Частка виручки за віком товару на момент продажу, %")
    print(share.round(1).to_string())


if __name__ == "__main__":
    main()