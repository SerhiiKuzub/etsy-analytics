SELECT
    date_trunc('month', created_at)::date AS month,
    count(*)                              AS orders,
    round(sum(total_amount), 2)           AS revenue,
    round(avg(total_amount), 2)           AS avg_order_value
FROM core.orders
GROUP BY 1
ORDER BY 1;