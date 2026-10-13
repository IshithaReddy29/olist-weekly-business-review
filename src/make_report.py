from pathlib import Path
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "olist_business_review.sqlite"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

def read_sql(sql):
    with sqlite3.connect(DB) as conn:
        return pd.read_sql_query(sql, conn)

def safe_save(fig, name):
    path = REPORTS / name
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path

def make_charts():
    monthly = read_sql("""
      SELECT strftime('%Y-%m', order_purchase_timestamp) AS month,
             SUM(order_item_total) AS revenue
      FROM mart_order_summary
      WHERE order_status NOT IN ('canceled','unavailable')
        AND order_purchase_timestamp IS NOT NULL
      GROUP BY 1 ORDER BY 1
    """)
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(monthly["month"], monthly["revenue"], marker="o")
    ax.set_title("Monthly order-item revenue (price + freight)")
    ax.set_xlabel("Purchase month")
    ax.set_ylabel("Revenue (BRL)")
    ax.tick_params(axis="x", rotation=45)
    revenue_chart = safe_save(fig, "chart_monthly_revenue.png")

    delivery = read_sql("""
      SELECT CASE WHEN delivery_delay_days <= 1 THEN 'On time / early'
                  ELSE 'Late by >1 day' END AS delivery_group,
             COUNT(*) AS orders
      FROM mart_order_summary
      WHERE order_status='delivered' AND delivery_delay_days IS NOT NULL
      GROUP BY 1
    """)
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.bar(delivery["delivery_group"], delivery["orders"])
    ax.set_title("Delivered orders by estimated-date performance")
    ax.set_xlabel("Delivery group")
    ax.set_ylabel("Orders")
    delivery_chart = safe_save(fig, "chart_delivery_performance.png")

    reviews = read_sql("""
      SELECT CASE WHEN delivery_delay_days < -1 THEN 'Early (>1 day)'
                  WHEN delivery_delay_days <= 1 THEN 'Within 1 day'
                  ELSE 'Late (>1 day)' END AS delivery_group,
             COUNT(review_score) AS reviewed_orders,
             AVG(review_score) AS avg_review_score
      FROM mart_order_summary
      WHERE order_status='delivered' AND delivery_delay_days IS NOT NULL
      GROUP BY 1
      ORDER BY CASE delivery_group WHEN 'Early (>1 day)' THEN 1
                                  WHEN 'Within 1 day' THEN 2 ELSE 3 END
    """)
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.bar(reviews["delivery_group"], reviews["avg_review_score"])
    ax.set_title("Average review score by delivery timing")
    ax.set_xlabel("Delivery group")
    ax.set_ylabel("Average review score (1–5)")
    ax.set_ylim(0, 5)
    review_chart = safe_save(fig, "chart_reviews_by_delivery.png")

    categories = read_sql("""
      SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
             SUM(oi.price + oi.freight_value) AS revenue
      FROM stg_order_items oi
      JOIN stg_orders o ON o.order_id=oi.order_id
      JOIN stg_products p ON p.product_id=oi.product_id
      LEFT JOIN stg_category_translation t ON t.product_category_name=p.product_category_name
      WHERE o.order_status NOT IN ('canceled','unavailable')
      GROUP BY 1 ORDER BY revenue DESC LIMIT 10
    """)
    categories = categories.sort_values("revenue", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(categories["category"], categories["revenue"])
    ax.set_title("Top 10 product categories by revenue")
    ax.set_xlabel("Revenue (BRL)")
    ax.set_ylabel("Product category")
    category_chart = safe_save(fig, "chart_top_categories.png")
    return [revenue_chart, delivery_chart, review_chart, category_chart], monthly, delivery, reviews, categories

def main():
    if not DB.exists():
        raise SystemExit("Database not found. Run: python src/pipeline.py")
    charts, monthly, delivery, reviews, categories = make_charts()
    summary = read_sql("""
      SELECT COUNT(*) AS all_orders,
             SUM(CASE WHEN order_status='delivered' THEN 1 ELSE 0 END) AS delivered_orders,
             ROUND(AVG(CASE WHEN order_status='delivered' THEN review_score END), 2) AS avg_review_score,
             ROUND(100.0 * AVG(CASE WHEN order_status='delivered' AND delivery_delay_days <= 1 THEN 1.0
                                    WHEN order_status='delivered' AND delivery_delay_days > 1 THEN 0.0 END), 2)
                 AS on_time_pct,
             ROUND(
               100.0 * SUM(CASE WHEN order_status='delivered' AND delivery_delay_days <= 1
                                      AND review_score >= 4 THEN 1 ELSE 0 END)
               / NULLIF(SUM(CASE WHEN order_status='delivered' AND delivery_delay_days IS NOT NULL
                                 THEN 1 ELSE 0 END), 0), 2
             ) AS north_star_pct,
             ROUND(SUM(CASE WHEN order_status NOT IN ('canceled','unavailable') THEN order_item_total ELSE 0 END), 2)
                 AS order_item_revenue
      FROM mart_order_summary
    """).iloc[0].to_dict()
    repeat = read_sql((ROOT / "sql" / "analysis" / "04_repeat_purchase_rate.sql").read_text()).iloc[0].to_dict()
    quality = pd.read_csv(REPORTS / "quality_check_results.csv") if (REPORTS / "quality_check_results.csv").exists() else pd.DataFrame()

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=19, leading=23, spaceAfter=12))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontSize=14, leading=17, spaceBefore=5, spaceAfter=7))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8.5, leading=11))
    story = []
    story += [
        Paragraph("Weekly Business Review: Olist E-commerce", styles["CoverTitle"]),
        Paragraph("Data engineering pipeline, quality checks, and customer-satisfaction analysis", styles["Heading2"]),
        Spacer(1, 8),
        Paragraph("<b>Dataset:</b> Brazilian E-Commerce Public Dataset by Olist (2016–2018). "
                  "This report is generated from the local CSV files by the included pipeline; all results below are calculated from the run database.", styles["BodyText"]),
        Spacer(1, 10),
        Paragraph("Executive snapshot", styles["Section"]),
    ]
    snap = [
        ["Metric", "Result"],
        ["Orders represented in mart", f'{int(summary["all_orders"]):,}'],
        ["Delivered orders", f'{int(summary["delivered_orders"] or 0):,}'],
        ["Order-item revenue (BRL; price + freight)", f'{summary["order_item_revenue"]:,.2f}'],
        ["Average delivered-order review score (1–5)", str(summary["avg_review_score"])],
        ["Delivered on-time/early within 1 day", f'{summary["on_time_pct"]}%'],
        ["North Star: on-time/early with review 4–5", f'{summary["north_star_pct"]}%'],
        ["Repeat-purchase rate", f'{repeat.get("repeat_purchase_rate_pct", "N/A")}%'],
    ]
    tbl = Table(snap, colWidths=[3.5*inch, 2.5*inch], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#243B53")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.4, colors.grey),
        ("FONTSIZE", (0,0), (-1,-1), 8.5),
        ("PADDING", (0,0), (-1,-1), 5),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story += [tbl, Spacer(1, 8),
              Paragraph("<b>Metric definitions.</b> North Star: share of delivered orders delivered no later than one day after the estimated date and receiving a review score of 4 or 5. "
                        "Supporting metrics: order-item revenue = sum(price + freight) for non-canceled/unavailable orders; on-time rate = delivered orders with delay ≤ 1 day / delivered orders with known delivery dates; "
                        "average review = mean review score for delivered orders; repeat-purchase rate = unique customers with ≥2 distinct orders / all unique customers.",
                        styles["Small"]),
              PageBreak()]

    story += [Paragraph("Data quality findings", styles["Section"]),
              Paragraph("The pipeline checks five conditions before analysis. A zero count means the check passed. If any check returns a non-zero count, the pipeline raises a data-quality alarm and stops before query outputs are generated. Review the raw data and the matching SQL before deciding whether to fix, flag, or quarantine records.", styles["BodyText"]),
              Spacer(1, 8)]
    qdata = [["Check", "Failing rows", "Status"]]
    if not quality.empty:
        for _, row in quality.iterrows():
            qdata.append([str(row["check"]), str(int(row["failing_rows"])), str(row["status"])])
    else:
        qdata.append(["No quality results found", "—", "Run pipeline first"])
    qtbl = Table(qdata, colWidths=[3.5*inch, 1.2*inch, 1.3*inch], repeatRows=1)
    qtbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#243B53")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.4, colors.grey),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story += [qtbl, Spacer(1, 10),
              Paragraph("<b>Handling policy:</b> do not silently delete anomalous orders. Keep raw tables unchanged; investigate and correct only when supported by source evidence. "
                        "For legitimate timing gaps (such as orders not yet delivered), preserve NULL delivery dates and exclude them from delivery-delay calculations. "
                        "The payment check compares payment totals with item price plus freight within BRL 0.05; differences should be investigated for vouchers, adjustments, or source-data issues.",
                        styles["Small"]),
              PageBreak()]

    story += [Paragraph("Business trends", styles["Section"]), Image(str(charts[0]), width=6.6*inch, height=2.55*inch),
              Image(str(charts[1]), width=5.5*inch, height=2.5*inch),
              Paragraph("Interpretation: use the monthly trend to identify seasonality and large revenue changes; use the delivery chart to assess fulfillment performance. These charts describe the dataset period and should not be interpreted as current marketplace performance.", styles["Small"]),
              PageBreak()]

    story += [Paragraph("Customer satisfaction and product mix", styles["Section"]),
              Image(str(charts[2]), width=5.5*inch, height=2.55*inch),
              Image(str(charts[3]), width=6.6*inch, height=3.15*inch),
              Paragraph("Review scores are observational and may be affected by factors beyond delivery timing. Compare group sizes as well as averages before acting.", styles["Small"]),
              PageBreak()]

    late = reviews[reviews["delivery_group"].astype(str).str.contains("Late", case=False)]
    early = reviews[reviews["delivery_group"].astype(str).str.contains("Early", case=False)]
    ontime = reviews[reviews["delivery_group"].astype(str).str.contains("Within", case=False)]
    late_score = float(late["avg_review_score"].iloc[0]) if not late.empty and pd.notna(late["avg_review_score"].iloc[0]) else None
    early_score = float(early["avg_review_score"].iloc[0]) if not early.empty and pd.notna(early["avg_review_score"].iloc[0]) else None
    ontime_score = float(ontime["avg_review_score"].iloc[0]) if not ontime.empty and pd.notna(ontime["avg_review_score"].iloc[0]) else None
    if late_score is not None and ontime_score is not None:
        finding = f"Orders delivered more than one day after the estimate averaged {late_score:.2f}/5, versus {ontime_score:.2f}/5 for orders delivered within one day of the estimate."
        recommendation = "Pilot proactive delay alerts for orders forecast to miss their estimated delivery date. Notify customers early, provide a revised ETA, and track the change in late-order share and average review score against a comparable control group."
    else:
        finding = "The available review-by-delivery groups did not contain both late and within-one-day review averages; inspect the generated query results before stating a comparative finding."
        recommendation = "First validate delivery timestamps and review coverage, then pilot proactive delay alerts only after a reliable baseline can be calculated."
    story += [
        Paragraph("VP memo", styles["Section"]),
        Paragraph("<b>To:</b> Vice President, Marketplace Operations<br/><b>Subject:</b> Reduce delivery-related customer dissatisfaction", styles["BodyText"]),
        Spacer(1, 8),
        Paragraph("<b>Finding.</b> " + finding, styles["BodyText"]),
        Spacer(1, 7),
        Paragraph("<b>Evidence.</b> The delivery/review analysis groups delivered orders by how actual delivery compares with the estimated date and calculates both order counts and mean review scores. The monthly revenue and delivery charts provide context for business scale and fulfillment performance. These are historical observational data, so the relationship does not alone prove that delay causes a low review.", styles["BodyText"]),
        Spacer(1, 7),
        Paragraph("<b>Recommendation.</b> " + recommendation, styles["BodyText"]),
        Spacer(1, 7),
        Paragraph("<b>Success measure.</b> Run a time-limited pilot and compare late-delivery rate, average review score, and the North Star metric against a comparable non-pilot group. Set the final target after establishing a validated baseline; do not claim a causal lift from a simple correlation.", styles["BodyText"]),
        Spacer(1, 12),
        Paragraph("<b>Reproducibility.</b> SQL result CSVs, charts, the SQLite database, and pipeline logs are created locally. Keep raw data and generated database/report artifacts out of the public GitHub repository; commit code, SQL, README, and requirements instead.", styles["Small"]),
    ]
    pdf = REPORTS / "olist_weekly_business_review.pdf"
    doc = SimpleDocTemplate(str(pdf), pagesize=A4, rightMargin=0.55*inch, leftMargin=0.55*inch, topMargin=0.45*inch, bottomMargin=0.45*inch)
    doc.build(story)
    print(f"Created PDF: {pdf}")
    print(f"Charts and CSV results are in: {REPORTS}")

if __name__ == "__main__":
    main()
