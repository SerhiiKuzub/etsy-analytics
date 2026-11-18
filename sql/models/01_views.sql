CREATE SCHEMA IF NOT EXISTS analytics;

-- Виручка по місяцях з позначкою повноти місяця
CREATE OR REPLACE VIEW analytics.v_monthly_revenue AS
WITH m AS (
    SELECT
        date_trunc('month', created_at)::date AS month,
        count(*)                              AS orders,
        round(sum(total_amount), 2)           AS revenue,
        round(avg(total_amount), 2)           AS avg_order_value
    FROM core.orders
    GROUP BY 1
)
SELECT
    m.*,
    (month > (SELECT min(month) FROM m)
     AND month < (SELECT max(month) FROM m)) AS is_full_month
FROM m;

-- Прибуток і маржа по товарах
CREATE OR REPLACE VIEW analytics.v_product_margin AS
WITH item_revenue AS (
    SELECT
        order_id,
        listing_id,
        quantity,
        quantity * unit_price AS revenue,
        sum(quantity * unit_price) OVER (PARTITION BY order_id) AS order_revenue
    FROM core.order_items
),
order_fees AS (
    SELECT order_id, sum(amount) AS fees
    FROM core.fees
    GROUP BY order_id
)
SELECT
    l.listing_id,
    l.title,
    substring(l.title from '\((.*)\)')                    AS category,
    sum(ir.quantity)                                      AS units,
    round(sum(ir.revenue), 2)                             AS revenue,
    round(sum(ofe.fees * ir.revenue / ir.order_revenue), 2) AS etsy_fees,
    round(sum(ir.quantity * pc.unit_cost), 2)             AS cogs,
    round(sum(ir.revenue)
          - sum(ofe.fees * ir.revenue / ir.order_revenue)
          - sum(ir.quantity * pc.unit_cost), 2)           AS profit,
    round(100 * (sum(ir.revenue)
          - sum(ofe.fees * ir.revenue / ir.order_revenue)
          - sum(ir.quantity * pc.unit_cost)) / sum(ir.revenue), 1) AS margin_pct
FROM item_revenue ir
JOIN core.listings l       ON l.listing_id = ir.listing_id
JOIN core.product_costs pc ON pc.listing_id = ir.listing_id
JOIN order_fees ofe        ON ofe.order_id = ir.order_id
GROUP BY l.listing_id, l.title;