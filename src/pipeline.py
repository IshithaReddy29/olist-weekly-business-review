from pathlib import Path
import logging
import sqlite3
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "olist_business_review.sqlite"
LOG_PATH = ROOT / "reports" / "pipeline.log"
SQL_DIR = ROOT / "sql"
REPORT_DIR = ROOT / "reports"

EXPECTED_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

REQUIRED_COLUMNS = {
    "orders": ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
               "order_delivered_customer_date", "order_estimated_delivery_date"],
    "order_items": ["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"],
    "order_payments": ["order_id", "payment_value", "payment_type"],
    "order_reviews": ["review_id", "order_id", "review_score"],
    "customers": ["customer_id", "customer_unique_id", "customer_state"],
    "products": ["product_id", "product_category_name"],
    "sellers": ["seller_id", "seller_state"],
    "geolocation": ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
    "category_translation": ["product_category_name", "product_category_name_english"],
}

def setup_logging():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
        force=True,
    )

def read_and_validate_csvs():
    data = {}
    for table, filename in EXPECTED_FILES.items():
        path = RAW_DIR / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Required dataset file is missing: {path}\n"
                f"Download/extract the Olist dataset and copy {filename} into data/raw/."
            )
        df = pd.read_csv(path)
        missing = sorted(set(REQUIRED_COLUMNS[table]) - set(df.columns))
        if missing:
            raise ValueError(f"{filename} is missing required columns: {missing}")
        data[table] = df
        logging.info("Validated %s: %s rows, %s columns", filename, len(df), len(df.columns))
    return data

def load_raw(conn, data):
    for table, df in data.items():
        # Replace makes each run idempotent: raw tables mirror the current source CSVs.
        df.to_sql(f"raw_{table}", conn, if_exists="replace", index=False)
        logging.info("Loaded raw_%s (%s rows)", table, len(df))

def build_staging_and_mart(conn):
    statements = [
        "DROP TABLE IF EXISTS stg_orders",
        """CREATE TABLE stg_orders AS
           SELECT order_id, customer_id, LOWER(TRIM(order_status)) AS order_status,
                  NULLIF(TRIM(order_purchase_timestamp), '') AS order_purchase_timestamp,
                  NULLIF(TRIM(order_approved_at), '') AS order_approved_at,
                  NULLIF(TRIM(order_delivered_carrier_date), '') AS order_delivered_carrier_date,
                  NULLIF(TRIM(order_delivered_customer_date), '') AS order_delivered_customer_date,
                  NULLIF(TRIM(order_estimated_delivery_date), '') AS order_estimated_delivery_date
           FROM raw_orders""",
        "DROP TABLE IF EXISTS stg_order_items",
        """CREATE TABLE stg_order_items AS
           SELECT order_id, CAST(order_item_id AS INTEGER) AS order_item_id,
                  product_id, seller_id, CAST(price AS REAL) AS price,
                  CAST(freight_value AS REAL) AS freight_value
           FROM raw_order_items""",
        "DROP TABLE IF EXISTS stg_order_payments",
        """CREATE TABLE stg_order_payments AS
           SELECT order_id, payment_type, CAST(payment_installments AS INTEGER) AS payment_installments,
                  CAST(payment_value AS REAL) AS payment_value
           FROM raw_order_payments""",
        "DROP TABLE IF EXISTS stg_reviews",
        """CREATE TABLE stg_reviews AS
           SELECT review_id, order_id, CAST(review_score AS INTEGER) AS review_score,
                  NULLIF(TRIM(review_comment_title), '') AS review_comment_title,
                  NULLIF(TRIM(review_comment_message), '') AS review_comment_message,
                  NULLIF(TRIM(review_creation_date), '') AS review_creation_date,
                  NULLIF(TRIM(review_answer_timestamp), '') AS review_answer_timestamp
           FROM raw_order_reviews""",
        "DROP TABLE IF EXISTS stg_customers",
        """CREATE TABLE stg_customers AS
           SELECT customer_id, customer_unique_id, customer_zip_code_prefix,
                  customer_city, UPPER(TRIM(customer_state)) AS customer_state
           FROM raw_customers""",
        "DROP TABLE IF EXISTS stg_products",
        """CREATE TABLE stg_products AS
           SELECT product_id, product_category_name,
                  CAST(product_name_lenght AS INTEGER) AS product_name_length,
                  CAST(product_description_lenght AS INTEGER) AS product_description_length,
                  CAST(product_photos_qty AS INTEGER) AS product_photos_qty,
                  CAST(product_weight_g AS REAL) AS product_weight_g,
                  CAST(product_length_cm AS REAL) AS product_length_cm,
                  CAST(product_height_cm AS REAL) AS product_height_cm,
                  CAST(product_width_cm AS REAL) AS product_width_cm
           FROM raw_products""",
        "DROP TABLE IF EXISTS stg_sellers",
        """CREATE TABLE stg_sellers AS
           SELECT seller_id, seller_zip_code_prefix, seller_city, UPPER(TRIM(seller_state)) AS seller_state
           FROM raw_sellers""",
        "DROP TABLE IF EXISTS stg_geolocation",
        """CREATE TABLE stg_geolocation AS
           SELECT CAST(geolocation_zip_code_prefix AS TEXT) AS geolocation_zip_code_prefix,
                  CAST(geolocation_lat AS REAL) AS geolocation_lat,
                  CAST(geolocation_lng AS REAL) AS geolocation_lng,
                  geolocation_city, UPPER(TRIM(geolocation_state)) AS geolocation_state
           FROM raw_geolocation""",
        "DROP TABLE IF EXISTS stg_category_translation",
        """CREATE TABLE stg_category_translation AS
           SELECT product_category_name, product_category_name_english
           FROM raw_category_translation""",
        "DROP TABLE IF EXISTS mart_order_summary",
        """CREATE TABLE mart_order_summary AS
           WITH item_totals AS (
             SELECT order_id, SUM(price) AS item_price_total,
                    SUM(freight_value) AS freight_total,
                    SUM(price + freight_value) AS order_item_total,
                    COUNT(*) AS item_count
             FROM stg_order_items GROUP BY order_id
           ),
           payment_totals AS (
             SELECT order_id, SUM(payment_value) AS payment_total
             FROM stg_order_payments GROUP BY order_id
           ),
           review_totals AS (
             SELECT order_id, AVG(review_score) AS review_score
             FROM stg_reviews GROUP BY order_id
           )
           SELECT o.order_id, o.customer_id, c.customer_unique_id, c.customer_state,
                  o.order_status, o.order_purchase_timestamp,
                  o.order_delivered_customer_date, o.order_estimated_delivery_date,
                  ROUND((julianday(o.order_delivered_customer_date) -
                         julianday(o.order_estimated_delivery_date)), 2) AS delivery_delay_days,
                  COALESCE(i.item_price_total, 0) AS item_price_total,
                  COALESCE(i.freight_total, 0) AS freight_total,
                  COALESCE(i.order_item_total, 0) AS order_item_total,
                  COALESCE(i.item_count, 0) AS item_count,
                  COALESCE(p.payment_total, 0) AS payment_total,
                  r.review_score
           FROM stg_orders o
           LEFT JOIN stg_customers c ON c.customer_id = o.customer_id
           LEFT JOIN item_totals i ON i.order_id = o.order_id
           LEFT JOIN payment_totals p ON p.order_id = o.order_id
           LEFT JOIN review_totals r ON r.order_id = o.order_id"""
    ]
    for sql in statements:
        conn.execute(sql)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mart_order_id ON mart_order_summary(order_id)")
    logging.info("Built staging tables and mart_order_summary")

def run_quality_checks(conn):
    check_files = sorted((SQL_DIR / "quality").glob("*.sql"))
    if len(check_files) < 5:
        raise RuntimeError(f"Expected at least 5 quality SQL files in {SQL_DIR / 'quality'}")
    results = []
    for path in check_files:
        sql = path.read_text(encoding="utf-8")
        failing = int(pd.read_sql_query(sql, conn).iloc[0, 0])
        results.append({"check": path.stem, "failing_rows": failing, "status": "PASS" if failing == 0 else "FAIL"})
        logging.info("QUALITY %s: %s failing rows", path.stem, failing)
    pd.DataFrame(results).to_csv(REPORT_DIR / "quality_check_results.csv", index=False)
    failures = [r for r in results if r["failing_rows"] > 0]
    if failures:
        details = "; ".join(f'{r["check"]}: {r["failing_rows"]} rows' for r in failures)
        raise RuntimeError(
            "DATA QUALITY ALARM: one or more blocking checks failed. "
            f"See reports/quality_check_results.csv. Details: {details}"
        )
    logging.info("All five blocking data-quality checks passed")

def run_analysis_queries(conn):
    for path in sorted((SQL_DIR / "analysis").glob("*.sql")):
        df = pd.read_sql_query(path.read_text(encoding="utf-8"), conn)
        out = REPORT_DIR / f"{path.stem}_results.csv"
        df.to_csv(out, index=False)
        logging.info("Ran %s: %s result rows -> %s", path.name, len(df), out.name)

def main():
    setup_logging()
    logging.info("Starting Olist ELT pipeline")
    try:
        data = read_and_validate_csvs()
        with sqlite3.connect(DB_PATH) as conn:
            load_raw(conn, data)
            build_staging_and_mart(conn)
            run_quality_checks(conn)
            run_analysis_queries(conn)
        logging.info("Pipeline completed successfully. Database: %s", DB_PATH)
        print("\nSUCCESS: pipeline completed.")
        print(f"Database: {DB_PATH}")
        print(f"Results:  {REPORT_DIR}")
    except Exception as exc:
        logging.exception("PIPELINE FAILED: %s", exc)
        print(f"\nPIPELINE FAILED: {exc}", file=sys.stderr)
        print(f"Check the log: {LOG_PATH}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
