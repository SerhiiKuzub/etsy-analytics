"""Швидка перевірка реальної бази: узгодженість і частки (без абсолютних сум).

Запуск: python -m src.load.check_real
"""
import json
from pathlib import Path

from sqlalchemy import text

from src.load.load_real_data import RAW, get_engine

REGION_SQL = """CASE WHEN buyer_country = 'US' THEN 'US'
 WHEN buyer_country IN ('AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE',
  'IT','LV','LT','LU','MT','NL','PL','PT','RO','SK','SI','ES','SE') THEN 'EU'
 ELSE 'OTHER' END"""


def main() -> None:
    receipts = json.loads((RAW / "receipts" / "receipts.json").read_text(encoding="utf-8"))["results"]
    expected_rev = sum(r["subtotal"]["amount"] / r["subtotal"]["divisor"] for r in receipts)

    with get_engine().connect() as c:
        one = lambda s: float(c.execute(text(s)).scalar() or 0)
        rev = one("SELECT sum(revenue) FROM analytics.v_item_facts")
        fees_alloc = one("SELECT sum(etsy_fees) FROM analytics.v_item_facts")
        fees_orders = one("SELECT sum(amount) FROM core.fees WHERE order_id IS NOT NULL")
        overhead = one("SELECT sum(amount) FROM core.fees WHERE order_id IS NULL")
        rows = c.execute(text(f"""
            SELECT {REGION_SQL} AS region, count(DISTINCT order_id) AS orders,
                   sum(revenue) AS revenue, sum(shipping_net) AS shipping_net,
                   sum(revenue) FILTER (WHERE cost_known) AS rev_known,
                   sum(profit)  FILTER (WHERE cost_known) AS profit_known
            FROM analytics.v_item_facts GROUP BY 1 ORDER BY 1""")).mappings().all()

    print("revenue check:", "OK" if abs(rev - expected_rev) < 2 else "MISMATCH")
    print("fee allocation check:", "OK" if abs(fees_alloc - fees_orders) < 1 else "MISMATCH")
    print(f"sale-related fees: {100 * fees_alloc / rev:.1f}% of revenue | "
          f"overhead fees: {100 * overhead / rev:.1f}% of revenue")

    f = lambda x: float(x or 0)
    print("\nregion | orders | shipping result, % of revenue | margin before overhead")
    for r in rows:
        print(f"{r['region']:5} | {r['orders']:3} | {100 * f(r['shipping_net']) / f(r['revenue']):+.1f}% | "
              f"{100 * f(r['profit_known']) / (f(r['rev_known']) or 1):.1f}%")
    tot_rev, tot_net = sum(f(r["revenue"]) for r in rows), sum(f(r["shipping_net"]) for r in rows)
    tot_rk, tot_pk = sum(f(r["rev_known"]) for r in rows), sum(f(r["profit_known"]) for r in rows)
    print(f"ALL   |     | {100 * tot_net / tot_rev:+.1f}% | {100 * tot_pk / tot_rk:.1f}%")


if __name__ == "__main__":
    main()