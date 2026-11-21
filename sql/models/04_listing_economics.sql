-- Економіка лістингів: прибуток від продажів проти витрат на утримання (поновлення, розміщення)
CREATE OR REPLACE VIEW analytics.v_listing_economics AS
WITH sales AS (
    SELECT listing_id,
           sum(quantity) AS units,
           sum(revenue)  AS revenue,
           sum(profit)   AS profit_before_upkeep
    FROM analytics.v_item_facts
    GROUP BY listing_id
),
upkeep AS (
    SELECT listing_id,
           sum(amount) AS upkeep_fees,
           count(*)    AS fee_events
    FROM core.fees
    WHERE order_id IS NULL AND listing_id IS NOT NULL
    GROUP BY listing_id
)
SELECT
    coalesce(s.listing_id, u.listing_id)  AS listing_id,
    l.title,
    l.state,
    coalesce(s.units, 0)                  AS units,
    coalesce(s.revenue, 0)                AS revenue,
    coalesce(s.profit_before_upkeep, 0)   AS profit_before_upkeep,
    coalesce(u.upkeep_fees, 0)            AS upkeep_fees,
    coalesce(u.fee_events, 0)             AS fee_events,
    (s.listing_id IS NOT NULL)            AS has_sales,
    coalesce(s.profit_before_upkeep, 0) - coalesce(u.upkeep_fees, 0) AS net_after_upkeep
FROM sales s
FULL OUTER JOIN upkeep u ON u.listing_id = s.listing_id
LEFT JOIN core.listings l ON l.listing_id = coalesce(s.listing_id, u.listing_id);