-- Surplus resources available for redistribution.

SELECT
    m.zone_id,
    z.zone_name,
    z.country,
    m.resource_type,
    m.total_available,
    m.total_needed,
    m.shortage_gap,
    m.status_label
FROM mismatch_scores m
JOIN zones z ON m.zone_id = z.zone_id
WHERE m.status_label = 'surplus'
ORDER BY m.shortage_gap ASC;
