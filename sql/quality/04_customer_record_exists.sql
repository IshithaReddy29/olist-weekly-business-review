SELECT COUNT(*) AS failing_rows
FROM stg_orders o
LEFT JOIN stg_customers c ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL;
