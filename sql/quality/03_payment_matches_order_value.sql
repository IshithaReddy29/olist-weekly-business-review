
-- Check for payment records that reference nonexistent orders.
-- Payment amount reconciliation is analyzed separately.

SELECT COUNT(*) AS failing_count
FROM stg_order_payments p
LEFT JOIN stg_orders o
    ON o.order_id = p.order_id
WHERE o.order_id IS NULL;
