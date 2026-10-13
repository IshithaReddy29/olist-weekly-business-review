WITH order_delivery AS (
    SELECT
        o.order_id,
        CAST(julianday(o.order_delivered_customer_date) -
             julianday(o.order_estimated_delivery_date) AS REAL) AS delay_days
    FROM stg_orders o
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
),
order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM stg_reviews
    WHERE review_score BETWEEN 1 AND 5
    GROUP BY order_id
)
SELECT
    CASE
        WHEN d.delay_days < -1 THEN 'Early (>1 day)'
        WHEN d.delay_days <= 1 THEN 'On time (within 1 day)'
        ELSE 'Late (>1 day)'
    END AS delivery_group,
    COUNT(*) AS orders,
    ROUND(AVG(d.delay_days), 2) AS avg_delay_days,
    ROUND(AVG(r.review_score), 2) AS avg_review_score
FROM order_delivery d
LEFT JOIN order_review r ON r.order_id = d.order_id
GROUP BY delivery_group
ORDER BY CASE delivery_group
    WHEN 'Early (>1 day)' THEN 1
    WHEN 'On time (within 1 day)' THEN 2
    ELSE 3
END;
