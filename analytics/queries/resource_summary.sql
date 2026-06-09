-- Aggregated supply, demand, and gap summary by resource type.

SELECT
    resource_type,
    SUM(total_available) AS total_available,
    SUM(total_needed) AS total_needed,
    SUM(shortage_gap) AS total_shortage_gap,
    COUNT(*) AS number_of_zones,
    COUNT(*) FILTER (WHERE status_label = 'critical shortage') AS critical_shortage_count,
    COUNT(*) FILTER (WHERE status_label = 'surplus') AS surplus_count
FROM mismatch_scores
GROUP BY resource_type
ORDER BY total_shortage_gap DESC;
