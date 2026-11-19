-- Факт на рівні позиції замовлення: єдине джерело для всіх розрахунків
CREATE OR REPLACE VIEW analytics.v_item_facts AS
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
    o.order_id,
    o.created_at::date                        AS order_date,
    date_trunc('month', o.created_at)::date   AS month,
    o.buyer_country,
    o.buyer_hash,
    l.listing_id,
    l.title,
    substring(l.title from '\((.*)\)')        AS category,
    ir.quantity,
    ir.revenue,
    ofe.fees * ir.revenue / ir.order_revenue  AS etsy_fees,
    ir.quantity * pc.unit_cost                AS cogs,
    ir.revenue
      - ofe.fees * ir.revenue / ir.order_revenue
      - ir.quantity * pc.unit_cost            AS profit
FROM item_revenue ir
JOIN core.orders o         ON o.order_id = ir.order_id
JOIN core.listings l       ON l.listing_id = ir.listing_id
JOIN core.product_costs pc ON pc.listing_id = ir.listing_id
JOIN order_fees ofe        ON ofe.order_id = ir.order_id;

-- Підсумок по товарах тепер будується з факту
DROP VIEW IF EXISTS analytics.v_product_margin;
CREATE VIEW analytics.v_product_margin AS
SELECT
    listing_id,
    title,
    category,
    sum(quantity)                                    AS units,
    round(sum(revenue), 2)                           AS revenue,
    round(sum(etsy_fees), 2)                         AS etsy_fees,
    round(sum(cogs), 2)                              AS cogs,
    round(sum(profit), 2)                            AS profit,
    round(100 * sum(profit) / sum(revenue), 1)       AS margin_pct
FROM analytics.v_item_facts
GROUP BY listing_id, title, category;