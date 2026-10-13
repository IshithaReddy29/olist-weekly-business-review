SELECT COUNT(*) AS failing_rows
FROM (
    SELECT order_id
    FROM stg_orders
    GROUP BY order_id
    HAVING order_id IS NULL OR COUNT(*) > 1
);
