-- Видаляємо у зворотному порядку залежностей, щоб можна було змінювати набір колонок
DROP VIEW IF EXISTS analytics.v_product_margin;
DROP VIEW IF EXISTS analytics.v_item_facts;

-- Факт на рівні позиції замовлення: єдине джерело для всіх розрахунків
CREATE VIEW analytics.v_item_facts AS
WITH items AS (
    SELECT
        order_id,
        listing_id,
        quantity,
        quantity * unit_price AS revenue,
        sum(quantity * unit_price) OVER (PARTITION BY order_id) AS order_revenue
    FROM core.order_items
),
direct_fees AS (   -- комісії, прив'язані до конкретної позиції
    SELECT order_id, listing_id, sum(amount) AS fees
    FROM core.fees
    WHERE order_id IS NOT NULL AND listing_id IS NOT NULL
    GROUP BY order_id, listing_id
),
order_fees AS (    -- комісії на все замовлення (ділимо між позиціями за виручкою)
    SELECT order_id, sum(amount) AS fees
    FROM core.fees
    WHERE order_id IS NOT NULL AND listing_id IS NULL
    GROUP BY order_id
),
calc AS (
    SELECT
        o.order_id,
        o.created_at::date                       AS order_date,
        date_trunc('month', o.created_at)::date  AS month,
        o.buyer_country,
        o.buyer_hash,
        l.listing_id,
        l.title,
        coalesce(substring(l.title from '\((.*)\)'), 'Uncategorized') AS category,
        i.quantity,
        i.revenue,
        coalesce(df.fees, 0)
          + coalesce(ofe.fees, 0) * i.revenue / nullif(i.order_revenue, 0) AS etsy_fees,
        i.quantity * (pc.unit_cost + pc.packaging_cost)                    AS cogs,
        -- плата покупця за доставку мінус пересилка, яку платить мама (у демо = 0)
        coalesce(o.shipping_amount - o.shipping_cost_est, 0)
          * i.revenue / nullif(i.order_revenue, 0)                         AS shipping_net,
        (pc.listing_id IS NOT NULL)                                        AS cost_known
    FROM items i
    JOIN core.orders o                ON o.order_id = i.order_id
    JOIN core.listings l              ON l.listing_id = i.listing_id
    LEFT JOIN core.product_costs pc   ON pc.listing_id = i.listing_id
    LEFT JOIN direct_fees df          ON df.order_id = i.order_id AND df.listing_id = i.listing_id
    LEFT JOIN order_fees ofe          ON ofe.order_id = i.order_id
)
SELECT
    *,
    -- прибуток невідомий, якщо немає собівартості (cogs = NULL)
    revenue - etsy_fees - cogs + shipping_net AS profit
FROM calc;

-- Підсумок по товарах (маржа лише по позиціях із відомою собівартістю)
CREATE VIEW analytics.v_product_margin AS
SELECT
    listing_id,
    title,
    category,
    sum(quantity)                                  AS units,
    round(sum(revenue), 2)                         AS revenue,
    round(sum(etsy_fees), 2)                       AS etsy_fees,
    round(sum(cogs), 2)                            AS cogs,
    round(sum(shipping_net), 2)                    AS shipping_net,
    round(sum(profit), 2)                          AS profit,
    bool_and(cost_known)                           AS cost_known,
    round(100 * sum(profit)
          / nullif(sum(revenue) FILTER (WHERE cost_known), 0), 1) AS margin_pct
FROM analytics.v_item_facts
GROUP BY listing_id, title, category;