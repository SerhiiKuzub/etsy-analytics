"""Економіка лістингів у реальній базі: частки й кількості, без абсолютних сум.

Запуск: python -m src.load.check_listings
"""
from sqlalchemy import text

from src.load.load_real_data import get_engine


def main() -> None:
    with get_engine().connect() as c:
        one = lambda s: float(c.execute(text(s)).scalar() or 0)
        rev = one("SELECT sum(revenue) FROM analytics.v_item_facts")
        up_total = one("SELECT sum(upkeep_fees) FROM analytics.v_listing_economics")
        up_never = one("SELECT sum(upkeep_fees) FROM analytics.v_listing_economics WHERE NOT has_sales")
        shop_level = one("SELECT sum(amount) FROM core.fees WHERE order_id IS NULL AND listing_id IS NULL")
        n_up = one("SELECT count(*) FROM analytics.v_listing_economics WHERE upkeep_fees > 0")
        n_never = one("SELECT count(*) FROM analytics.v_listing_economics WHERE upkeep_fees > 0 AND NOT has_sales")
        n_sold = one("SELECT count(*) FROM analytics.v_listing_economics WHERE has_sales")
        n_loss = one("SELECT count(*) FROM analytics.v_listing_economics WHERE has_sales AND net_after_upkeep < 0")
        by_type = c.execute(text(
            "SELECT fee_type, sum(amount) AS amt FROM core.fees "
            "WHERE order_id IS NULL GROUP BY 1 ORDER BY 2 DESC")).all()
        rev12 = one("SELECT sum(revenue) FROM analytics.v_item_facts "
                    "WHERE order_date >= current_date - 365")
        over12 = one("SELECT sum(amount) FROM core.fees "
                     "WHERE order_id IS NULL AND created_at >= current_date - 365")

    overhead = sum(float(a) for _, a in by_type)
    print(f"listing-level upkeep: {100 * up_total / rev:.1f}% of revenue | "
          f"shop-level (ads etc.): {100 * shop_level / rev:.1f}% of revenue")
    print(f"upkeep spent on listings that NEVER sold: {100 * up_never / (up_total or 1):.1f}%")
    print(f"listings with upkeep fees: {n_up:.0f} (never sold: {n_never:.0f}) | listings with sales: {n_sold:.0f}")
    print(f"sold listings where upkeep exceeded profit: {n_loss:.0f} of {n_sold:.0f}")
    print("overhead by type, % of overhead:",
          {t: round(100 * float(a) / overhead, 1) for t, a in by_type})
    print(f"last 12 months: overhead = {100 * over12 / (rev12 or 1):.1f}% of last 12 months revenue")


if __name__ == "__main__":
    main()