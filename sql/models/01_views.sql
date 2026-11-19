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