WITH category_revenue AS (
    SELECT
        c.customer_state AS state,
        COALESCE(pt.product_category_name_english, p.product_category_name, 'unknown') AS category,
        ROUND(SUM(oi.price + oi.freight_value), 2) AS revenue
    FROM stg_order_items oi
    JOIN stg_orders o ON o.order_id = oi.order_id
    JOIN stg_customers c ON c.customer_id = o.customer_id
    JOIN stg_products p ON p.product_id = oi.product_id
    LEFT JOIN stg_category_translation pt
      ON pt.product_category_name = p.product_category_name
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY c.customer_state,
             COALESCE(pt.product_category_name_english, p.product_category_name, 'unknown')
),
ranked AS (
    SELECT
        state, category, revenue,
        DENSE_RANK() OVER (PARTITION BY state ORDER BY revenue DESC) AS category_rank
    FROM category_revenue
)
SELECT state, category, revenue, category_rank
FROM ranked
WHERE category_rank <= 3
ORDER BY state, category_rank, category;
