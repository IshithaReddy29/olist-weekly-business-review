WITH RECURSIVE calendar(day) AS (
    SELECT date(MIN(order_purchase_timestamp))
    FROM stg_orders
    WHERE order_purchase_timestamp IS NOT NULL
    UNION ALL
    SELECT date(day, '+1 day')
    FROM calendar
    WHERE day < (SELECT date(MAX(order_purchase_timestamp))
                 FROM stg_orders WHERE order_purchase_timestamp IS NOT NULL)
),
daily AS (
    SELECT
        calendar.day,
        COUNT(o.order_id) AS order_count
    FROM calendar
    LEFT JOIN stg_orders o
      ON date(o.order_purchase_timestamp) = calendar.day
    GROUP BY calendar.day
),
rolling AS (
    SELECT
        day,
        order_count,
        AVG(order_count) OVER (
            ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7_day_avg
    FROM daily
)
SELECT day, order_count, ROUND(rolling_7_day_avg, 2) AS rolling_7_day_avg
FROM rolling
ORDER BY day;
