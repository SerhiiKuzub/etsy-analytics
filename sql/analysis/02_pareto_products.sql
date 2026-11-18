WITH product_revenue AS (
    SELECT
        l.title,
        sum(oi.quantity)                   AS units,
        sum(oi.quantity * oi.unit_price)   AS revenue
    FROM core.order_items oi
    JOIN core.listings l ON l.listing_id = oi.listing_id
    GROUP BY l.title
)
SELECT
    title,
    units,
    round(revenue, 2)                                              AS revenue,
    round(100 * revenue / sum(revenue) OVER (), 1)                 AS share_pct,
    round(100 * sum(revenue) OVER (ORDER BY revenue DESC)
              / sum(revenue) OVER (), 1)                           AS cumulative_pct
FROM product_revenue
ORDER BY revenue DESC;