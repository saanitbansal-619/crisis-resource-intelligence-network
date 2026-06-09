-- Top resource shortages ranked by urgency-weighted mismatch score.

SELECT
    m.zone_id,
    z.zone_name,
    z.country,
    m.resource_type,
    m.total_available,
    m.total_needed,
    m.shortage_gap,
    m.urgency_level,
    m.mismatch_score,
    m.status_label
FROM mismatch_scores m
JOIN zones z ON m.zone_id = z.zone_id
WHERE m.shortage_gap > 0
ORDER BY m.mismatch_score DESC;
