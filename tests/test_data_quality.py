"""Перевірки якості синтетичних даних (data/sample)."""
from pathlib import Path

import pandas as pd
import pytest

DATA = Path(__file__).resolve().parents[1] / "data" / "sample"
TABLES = ["listings", "product_costs", "orders", "order_items", "fees"]


@pytest.fixture(scope="module")
def t():
    out = {name: pd.read_csv(DATA / f"{name}.csv") for name in TABLES}
    out["orders"]["created_at"] = pd.to_datetime(out["orders"]["created_at"])
    return out


def test_primary_keys_are_unique(t):
    assert t["listings"]["listing_id"].is_unique
    assert t["orders"]["order_id"].is_unique
    assert not t["order_items"].duplicated(["order_id", "listing_id"]).any()


def test_no_nulls_in_key_columns(t):
    keys = {
        "listings": ["listing_id", "title", "price"],
        "product_costs": ["listing_id", "unit_cost"],
        "orders": ["order_id", "created_at", "total_amount", "buyer_hash"],
        "order_items": ["order_id", "listing_id", "quantity", "unit_price"],
        "fees": ["order_id", "fee_type", "amount"],
    }
    for table, cols in keys.items():
        assert not t[table][cols].isna().any().any(), f"NULL у {table}"


def test_foreign_keys_are_valid(t):
    assert t["order_items"]["order_id"].isin(t["orders"]["order_id"]).all()
    assert t["order_items"]["listing_id"].isin(t["listings"]["listing_id"]).all()
    assert t["fees"]["order_id"].isin(t["orders"]["order_id"]).all()
    assert t["product_costs"]["listing_id"].isin(t["listings"]["listing_id"]).all()


def test_every_listing_has_a_cost(t):
    assert set(t["listings"]["listing_id"]) == set(t["product_costs"]["listing_id"])


def test_amounts_are_positive(t):
    assert (t["listings"]["price"] > 0).all()
    assert (t["product_costs"]["unit_cost"] > 0).all()
    assert (t["order_items"]["quantity"] >= 1).all()
    assert (t["order_items"]["unit_price"] > 0).all()
    assert (t["fees"]["amount"] > 0).all()


def test_order_total_equals_items_plus_shipping(t):
    items = t["order_items"].assign(line=lambda d: d["quantity"] * d["unit_price"])
    subtotal = items.groupby("order_id")["line"].sum()
    orders = t["orders"].set_index("order_id")
    diff = (orders["total_amount"] - orders["shipping_amount"] - subtotal).abs()
    assert (diff < 0.02).all()


def test_dates_are_in_expected_range(t):
    created = t["orders"]["created_at"]
    assert created.min() >= pd.Timestamp("2024-11-18")
    assert created.max() < pd.Timestamp("2026-11-19")


def test_fee_types_are_known(t):
    allowed = {"listing", "transaction", "processing", "offsite_ads"}
    assert set(t["fees"]["fee_type"]) <= allowed


def test_seeded_loss_makers_exist(t):
    """У генераторі навмисно закладено 3 товари з собівартістю понад 80% ціни."""
    m = t["product_costs"].merge(t["listings"], on="listing_id")
    assert (m["unit_cost"] / m["price"] > 0.8).sum() == 3


def test_repeat_buyer_rate_is_realistic(t):
    per_buyer = t["orders"].groupby("buyer_hash")["order_id"].nunique()
    rate = (per_buyer > 1).mean()
    assert 0.10 <= rate <= 0.40, f"повторних покупців {rate:.0%}"