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
    l.title,
    sum(ir.quantity)                                   AS units,
    round(sum(ir.revenue), 2)                          AS revenue,
    round(sum(of.fees * ir.revenue / ir.order_revenue), 2) AS etsy_fees,
    round(sum(ir.quantity * pc.unit_cost), 2)          AS cogs,
    round(sum(ir.revenue)
          - sum(of.fees * ir.revenue / ir.order_revenue)
          - sum(ir.quantity * pc.unit_cost), 2)        AS profit,
    round(100 * (sum(ir.revenue)
          - sum(of.fees * ir.revenue / ir.order_revenue)
          - sum(ir.quantity * pc.unit_cost)) / sum(ir.revenue), 1) AS margin_pct
FROM item_revenue ir
JOIN core.listings l       ON l.listing_id = ir.listing_id
JOIN core.product_costs pc ON pc.listing_id = ir.listing_id
JOIN order_fees of         ON of.order_id = ir.order_id
GROUP BY l.title
ORDER BY margin_pct;