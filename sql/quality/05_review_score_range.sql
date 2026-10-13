SELECT COUNT(*) AS failing_rows
FROM stg_reviews
WHERE review_score IS NULL OR review_score < 1 OR review_score > 5;
