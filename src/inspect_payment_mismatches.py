
from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "olist_business_review.sqlite"

query = """
WITH item_totals AS (
    SELECT order_id, SUM(price) AS item_price,
           SUM(freight_value) AS freight
    FROM stg_order_items
    GROUP BY order_id
),
payment_totals AS (
    SELECT order_id, SUM(payment_value) AS payment_total,
           COUNT(*) AS payment_rows
    FROM stg_order_payments
    GROUP BY order_id
)
SELECT
    o.order_id,
    o.order_status,
    o.order_purchase_timestamp,
    COALESCE(i.item_price, 0) AS item_price,
    COALESCE(i.freight, 0) AS freight,
    COALESCE(p.payment_total, 0) AS payment_total,
    COALESCE(p.payment_rows, 0) AS payment_rows,
    ROUND(
        COALESCE(p.payment_total, 0)
        - COALESCE(i.item_price, 0)
        - COALESCE(i.freight, 0), 2
    ) AS difference
FROM stg_orders o
LEFT JOIN item_totals i ON i.order_id = o.order_id
LEFT JOIN payment_totals p ON p.order_id = o.order_id
WHERE o.order_id IN (
    'ce6d150fb29ada17d2082f4847107665',
    'bfbd0f9bdef84302105ad712db648a6c',
    '90ab3e7d52544ec7bc3363c82689965f',
    '6e5fe7366a2e1bfbf3257dba0af1267f'
)
ORDER BY o.order_id;
"""

with sqlite3.connect(DB_PATH) as conn:
    print("\n--- Selected order details ---")
    print(pd.read_sql_query(query, conn).to_string(index=False))

    print("\n--- Item rows for selected orders ---")
    print(pd.read_sql_query("""
        SELECT order_id, order_item_id, product_id,
               price, freight_value
        FROM stg_order_items
        WHERE order_id IN (
            'ce6d150fb29ada17d2082f4847107665',
            'bfbd0f9bdef84302105ad712db648a6c',
            '90ab3e7d52544ec7bc3363c82689965f',
            '6e5fe7366a2e1bfbf3257dba0af1267f'
        )
        ORDER BY order_id, order_item_id
    """, conn).to_string(index=False))

    print("\n--- Payment rows for selected orders ---")
    print(pd.read_sql_query("""
        SELECT order_id, payment_sequential,
               payment_type, payment_installments, payment_value
        FROM stg_order_payments
        WHERE order_id IN (
            'ce6d150fb29ada17d2082f4847107665',
            'bfbd0f9bdef84302105ad712db648a6c',
            '90ab3e7d52544ec7bc3363c82689965f',
            '6e5fe7366a2e1bfbf3257dba0af1267f'
        )
        ORDER BY order_id, payment_sequential
    """, conn).to_string(index=False))
