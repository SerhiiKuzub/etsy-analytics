-- Витрати, не пов'язані з конкретним продажем: поновлення, реклама тощо
CREATE OR REPLACE VIEW analytics.v_overhead_fees AS
SELECT
    date_trunc('month', created_at)::date AS month,
    CASE WHEN listing_id IS NOT NULL THEN 'listing-level' ELSE 'shop-level' END AS level,
    fee_type,
    round(sum(amount), 2) AS amount,
    count(*)              AS entries
FROM core.fees
WHERE order_id IS NULL
GROUP BY 1, 2, 3;