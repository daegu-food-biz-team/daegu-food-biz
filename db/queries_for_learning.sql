-- Run these after: python scripts/sync_data.py --apply
-- 1. Confirm current model snapshot and its history.
SELECT run_id,model_version,as_of,officer_count,founder_count,inserted_at
FROM raw.ingestion_runs ORDER BY inserted_at DESC;

-- 2. The key contest validation counts: 31 entry / 34 survival / 65 not stagnant.
SELECT CASE WHEN is_stagnant THEN bottleneck ELSE '정체 동 아님' END AS category,
       count(*) AS dong_count
FROM mart.officer_latest
GROUP BY 1 ORDER BY 1;

-- 3. Confidence levels and historical accuracy (NOT a probability for each dong).
SELECT bottleneck, confidence, COUNT(*) AS dong_count,
       ROUND((AVG(val_accuracy)*100)::numeric,1) AS historic_accuracy_pct
FROM mart.officer_latest
WHERE is_stagnant = TRUE
GROUP BY bottleneck,confidence
ORDER BY bottleneck,confidence;

-- 4. JOIN officer diagnosis and founder cafe survival (same legal-dong key).
SELECT o.unit,o.bottleneck,o.confidence,o.n_active,
       f.surv2_adj,f.cohort_n,f.small_sample
FROM mart.officer_latest o
JOIN mart.founder_cafe_latest f USING(unit)
WHERE o.is_stagnant
ORDER BY f.surv2_adj ASC;

-- 5. Spatial risk: several legal dongs may share one administrative dong.
-- Never treat these HJD polygons as unique legal-dong boundaries.
SELECT hjd_code,MAX(hjd_name) AS hjd_name,COUNT(*) AS legal_dong_count
FROM mart.unit_hjd_latest
GROUP BY hjd_code HAVING COUNT(*)>1
ORDER BY legal_dong_count DESC;

-- 6. Current trend, not a future prioritization score.
SELECT unit,growth_past3,n_active
FROM mart.officer_latest
ORDER BY growth_past3 ASC;
