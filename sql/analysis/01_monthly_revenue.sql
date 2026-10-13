WITH monthly AS (
    SELECT
        strftime('%Y-%m', o.order_purchase_timestamp) AS month,
        ROUND(SUM(oi.price + oi.freight_value), 2) AS revenue
    FROM stg_orders o
    JOIN stg_order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
      AND o.order_purchase_timestamp IS NOT NULL
    GROUP BY strftime('%Y-%m', o.order_purchase_timestamp)
),
with_previous AS (
    SELECT
        month,
        revenue,
        LAG(revenue) OVER (ORDER BY month) AS previous_month_revenue
    FROM monthly
)
SELECT
    month,
    revenue,
    previous_month_revenue,
    ROUND(
        100.0 * (revenue - previous_month_revenue) / NULLIF(previous_month_revenue, 0),
        2
    ) AS growth_pct
FROM with_previous
ORDER BY month;
