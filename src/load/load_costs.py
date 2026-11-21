"""Завантажує собівартість із data/raw/costs.xlsx у базу etsy_real.

Пакування додається окремою колонкою для фізичних товарів (не для цифрових).
Запуск: python -m src.load.load_costs
"""
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.load.load_real_data import get_engine

from src.load.params import load_params

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "data" / "raw" / "costs.xlsx"
RECEIPTS = ROOT / "data" / "raw" / "receipts" / "receipts.json"
PACKAGING_COST_USD = load_params()["packaging_usd"]  # пакування на штуку фізичного товару


def main() -> None:
    if not FILE.exists():
        raise SystemExit("Немає data/raw/costs.xlsx")
    df = pd.read_excel(FILE, sheet_name="Собівартість").iloc[:, [0, 4]]
    df.columns = ["listing_id", "unit_cost"]
    df = df.dropna(subset=["listing_id"])
    df["listing_id"] = df["listing_id"].astype("int64")

    empty = int(df["unit_cost"].isna().sum())
    df = df.dropna(subset=["unit_cost"])
    if (df["unit_cost"] < 0).any():
        raise SystemExit("Є від'ємна собівартість, перевірте файл.")

    # Цифрові товари (PDF) Etsy позначає в замовленнях полем is_digital
    receipts = json.loads(RECEIPTS.read_text(encoding="utf-8"))["results"]
    digital = {t["listing_id"] for r in receipts
               for t in r["transactions"] if t.get("is_digital")}
    df["packaging_cost"] = [0.0 if lid in digital else PACKAGING_COST_USD
                            for lid in df["listing_id"]]
    df["updated_at"] = pd.Timestamp.today().date()

    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE core.product_costs"))
        df.to_sql("product_costs", conn, schema="core",
                  if_exists="append", index=False)
    print(f"собівартість завантажено: {len(df)} товарів, без собівартості: {empty}, "
          f"цифрових (без пакування): {int(df['listing_id'].isin(digital).sum())}")


if __name__ == "__main__":
    main()