-- High-level crisis resource coordination overview.

SELECT
    (SELECT COUNT(*) FROM zones) AS total_zones,
    (SELECT COUNT(*) FROM organizations) AS total_organizations,
    (SELECT COUNT(*) FROM resource_inventory) AS total_inventory_records,
    (SELECT COUNT(*) FROM resource_requests) AS total_request_records,
    (SELECT COUNT(*) FROM mismatch_scores) AS total_mismatch_records,
    (SELECT COUNT(*) FROM mismatch_scores WHERE status_label = 'critical shortage') AS critical_shortage_count,
    (SELECT COUNT(*) FROM mismatch_scores WHERE status_label = 'severe shortage') AS severe_shortage_count,
    (SELECT COUNT(*) FROM mismatch_scores WHERE status_label = 'surplus') AS surplus_count;
