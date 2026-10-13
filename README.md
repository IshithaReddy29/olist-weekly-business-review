# Olist Weekly Business Review

A small ELT pipeline and SQL analysis project using the Brazilian E-Commerce Public Dataset by Olist.

## Stack
- Python + pandas for CSV ingestion and report orchestration
- SQLite for raw, staging, and mart tables
- SQL CTEs/window functions for Part C
- Matplotlib for charts
- ReportLab for the five-page PDF report

SQLite is used to make the project reproducible without a separate database server. SQLite supports the CTEs and window functions used in the queries.

## 1. Dataset setup
Download and extract the dataset from:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Copy these nine CSVs into `data/raw/`:
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `olist_geolocation_dataset.csv`
- `product_category_name_translation.csv`

Do not commit the raw data or generated database to GitHub.

## 2. Install
Windows PowerShell, from the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, use Command Prompt:
```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Run pipeline and checks
```powershell
python src/pipeline.py
```

The pipeline:
1. checks required files and columns,
2. replaces raw tables from the source CSVs (idempotent),
3. rebuilds staging tables and one-row-per-order `mart_order_summary`,
4. runs five blocking data-quality checks,
5. writes query outputs to `reports/`.

If a quality check returns any failing rows, the pipeline stops with an alarm. Inspect `reports/quality_check_results.csv` and `reports/pipeline.log`; do not silently delete data. Investigate whether the discrepancy is a true error or a legitimate source-data exception. If a check fails, the SQL query result files for Part C may not be refreshed during that run.

## 4. Create the PDF report
Only after the pipeline finishes successfully:
```powershell
python src/make_report.py
```
Output: `reports/olist_weekly_business_review.pdf` (five pages) plus four PNG charts.

## 5. SQL deliverables
- `sql/quality/`: five Part B checks
- `sql/analysis/`: five Part C queries

Part C is executed directly in SQL using SQLite CTEs/window functions. pandas is only used to save query results, not to calculate the SQL answers.

## 6. Idempotency
Raw tables are replaced from the source CSVs on each run. Staging and mart tables are dropped and recreated from raw tables. This prevents duplicate rows when rerunning the pipeline.

## 7. Notes and metric definitions
- Revenue is defined as item price + freight, excluding orders with status `canceled` or `unavailable`. Payment totals are stored separately for reconciliation.
- Repeat customers are counted with `customer_unique_id`, not `customer_id`.
- Delivery delay days = actual delivered timestamp − estimated delivery timestamp. Positive means late; negative means early.
- The report's delivery performance threshold is within one day of the estimated date. State this definition when presenting results.
- Data-quality check results and the memo are generated from the local run. Review all results before submission and be prepared to explain them in a viva.

## 8. GitHub hygiene
Commit source code, SQL, README, and requirements. Do not commit `data/raw/`, SQLite databases, logs, generated charts, CSV outputs, or the PDF unless your assignment explicitly requires the PDF in the repository. Submit the PDF separately if requested.
