"""Генератор синтетичних даних для Etsy-аналітики.

Усі дані вигадані: реальних даних магазину тут немає.
Запуск: python -m src.synthetic.generate
"""
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd

SEED = 42
START = pd.Timestamp("2024-11-18")
END = pd.Timestamp("2026-11-17")
N_LISTINGS = 30
N_BUYERS = 7000
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "sample"

# категорія -> (мін. ціна, макс. ціна)
CATEGORIES = {
    "Mugs": (22, 38),
    "Prints": (9, 30),
    "Candles": (14, 28),
    "Jewelry": (20, 70),
    "Textile": (25, 60),
    "Stickers": (3, 8),
}
TAG_POOL = [
    "handmade", "gift", "custom", "minimalist", "vintage", "boho",
    "personalized", "home decor", "eco friendly", "unique", "modern", "cozy",
]
COUNTRIES = ["US", "GB", "CA", "DE", "AU", "FR", "NL", "PL"]
COUNTRY_P = [0.55, 0.12, 0.08, 0.07, 0.05, 0.04, 0.03, 0.06]
# сезонність: пік у листопаді-грудні
SEASON = {1: 0.9, 2: 0.85, 3: 0.9, 4: 0.95, 5: 1.0, 6: 0.85,
          7: 0.8, 8: 0.8, 9: 0.9, 10: 1.1, 11: 1.5, 12: 1.8}


def make_listings(rng):
    cats = list(CATEGORIES)
    rows = []
    for i in range(N_LISTINGS):
        cat = cats[i % len(cats)]
        lo, hi = CATEGORIES[cat]
        rows.append({
            "listing_id": 100_000_000 + i,
            "title": f"Product {i + 1:02d} ({cat})",
            "price": round(float(rng.uniform(lo, hi)), 2),
            "currency": "USD",
            "created_at": pd.Timestamp("2023-06-01")
            + pd.Timedelta(days=int(rng.integers(0, 520))),
            "tags": [str(t) for t in rng.choice(TAG_POOL, size=5, replace=False)],
        })
    df = pd.DataFrame(rows)
    # популярність товарів нерівномірна (кілька хітів і довгий хвіст)
    weights = rng.lognormal(0, 1.0, N_LISTINGS)
    weights = weights / weights.sum()
    df["views"] = (weights * 60000 * rng.uniform(0.8, 1.2, N_LISTINGS)).astype(int)
    df["favorites"] = (df["views"] * rng.uniform(0.02, 0.08, N_LISTINGS)).astype(int)
    return df, weights


def make_costs(rng, listings):
    ratio = rng.uniform(0.25, 0.5, len(listings))
    # 3 товари навмисно майже збиткові, щоб в аналізі було що знайти
    bad = rng.choice(len(listings), size=3, replace=False)
    ratio[bad] = rng.uniform(0.85, 0.95, 3)
    return pd.DataFrame({
        "listing_id": listings["listing_id"],
        "unit_cost": (listings["price"] * ratio).round(2),
        "updated_at": END.date(),
    })


def make_orders(rng, listings, weights):
    days = pd.date_range(START, END, freq="D")
    t = np.arange(len(days)) / len(days)
    season = np.array([SEASON[d.month] for d in days])
    weekend = np.array([1.15 if d.dayofweek >= 5 else 1.0 for d in days])
    lam = 4.0 * season * (1 + 0.5 * t) * weekend  # сезонність + зростання + вихідні
    counts = rng.poisson(lam)

    order_days = pd.to_datetime(np.repeat(days.values, counts))
    secs = rng.integers(0, 86400, size=len(order_days))
    created = (order_days + pd.to_timedelta(secs, unit="s")).sort_values()
    n = len(created)
    order_ids = 1_000_000_000 + np.arange(n)

    buyer_ids = rng.integers(0, N_BUYERS, n)
    buyer_country = rng.choice(COUNTRIES, N_BUYERS, p=COUNTRY_P)

    prices = listings["price"].to_numpy()
    lids = listings["listing_id"].to_numpy()
    order_rows, item_rows, fee_rows = [], [], []

    for idx in range(n):
        oid = int(order_ids[idx])
        ts = created[idx]
        k = int(rng.choice([1, 2, 3], p=[0.75, 0.2, 0.05]))
        chosen = rng.choice(N_LISTINGS, size=k, replace=False, p=weights)

        subtotal = 0.0
        for li in chosen:
            qty = 1 if rng.random() < 0.9 else 2
            unit = round(float(prices[li]) * (0.9 if rng.random() < 0.1 else 1.0), 2)
            subtotal += unit * qty
            item_rows.append({"order_id": oid, "listing_id": int(lids[li]),
                              "quantity": qty, "unit_price": unit})
            fee_rows.append({"order_id": oid, "fee_type": "listing",
                             "amount": 0.20, "created_at": ts})

        country = str(buyer_country[buyer_ids[idx]])
        if country == "US":
            shipping = 0.0 if subtotal >= 35 else 4.5
        else:
            shipping = 9.0
        total = round(subtotal + shipping, 2)

        bid = int(buyer_ids[idx])
        order_rows.append({
            "order_id": oid,
            "created_at": ts,
            "buyer_country": country,
            "buyer_hash": hashlib.sha256(f"buyer-{bid}-{SEED}".encode()).hexdigest()[:16],
            "total_amount": total,
            "shipping_amount": shipping,
            "currency": "USD",
        })

        # Орієнтовні ставки комісій (перевір актуальні в документації Etsy)
        fee_rows.append({"order_id": oid, "fee_type": "transaction",
                         "amount": round(total * 0.065, 2), "created_at": ts})
        fee_rows.append({"order_id": oid, "fee_type": "processing",
                         "amount": round(total * 0.03 + 0.25, 2), "created_at": ts})
        if rng.random() < 0.12:  # частина замовлень прийшла з Offsite Ads
            fee_rows.append({"order_id": oid, "fee_type": "offsite_ads",
                             "amount": round(total * 0.15, 2), "created_at": ts})

    return pd.DataFrame(order_rows), pd.DataFrame(item_rows), pd.DataFrame(fee_rows)


def main():
    rng = np.random.default_rng(SEED)
    listings, weights = make_listings(rng)
    costs = make_costs(rng, listings)
    orders, items, fees = make_orders(rng, listings, weights)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = listings.copy()
    out["tags"] = out["tags"].apply("|".join)
    out.to_csv(OUT_DIR / "listings.csv", index=False)
    costs.to_csv(OUT_DIR / "product_costs.csv", index=False)
    orders.to_csv(OUT_DIR / "orders.csv", index=False)
    items.to_csv(OUT_DIR / "order_items.csv", index=False)
    fees.to_csv(OUT_DIR / "fees.csv", index=False)

    print(f"listings: {len(listings)}, orders: {len(orders)}, "
          f"items: {len(items)}, fees: {len(fees)}")
    print(f"period: {orders['created_at'].min()} -> {orders['created_at'].max()}")
    print(f"revenue (synthetic): {orders['total_amount'].sum():,.2f} USD")


if __name__ == "__main__":
    main()