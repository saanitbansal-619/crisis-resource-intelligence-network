"""
OR-Tools constrained optimization for resource transfer planning.

Minimizes simulated transport cost while respecting supply and demand limits.
Keeps the deterministic reallocation engine as the baseline method.

Run: python -m analytics.optimization_engine
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from analytics.reallocation_engine import (
    build_shortage_records,
    build_surplus_records,
)

try:
    from ortools.linear_solver import pywraplp

    ORTOOLS_AVAILABLE = True
except ImportError:  # pragma: no cover - graceful degradation when ortools missing
    ORTOOLS_AVAILABLE = False
    pywraplp = None  # type: ignore[assignment,misc]

SAME_COUNTRY_BASE_COST = 10.0
CROSS_COUNTRY_BASE_COST = 100.0
DISTANCE_COST_PER_KM = 0.5
SIMULATED_SAME_COUNTRY_KM = 120.0
SIMULATED_CROSS_COUNTRY_KM = 850.0
UNMET_DEMAND_PENALTY = 1_000_000.0

METHOD_NOTE = (
    "Optimized transfer plan uses Google OR-Tools to minimize simulated transport cost "
    "under supply and demand constraints. Cost assumptions are simulated for portfolio "
    "and demo purposes."
)
VALIDATION_NOTE = (
    "Recommendations require human validation before operational use."
)
COST_NOTE = (
    "Optimization cost is based on simulated distance and logistics assumptions for demonstration purposes. "
    "Values are relative cost units, not real-world USD estimates."
)


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_zone_coordinate_lookup(mismatch_rows: list[dict]) -> dict[str, tuple[float, float]]:
    lookup: dict[str, tuple[float, float]] = {}
    for row in mismatch_rows:
        zone_id = row.get("zone_id")
        if not zone_id:
            continue
        lat = row.get("latitude")
        lon = row.get("longitude")
        if lat is None or lon is None:
            continue
        lookup[str(zone_id)] = (_to_float(lat), _to_float(lon))
    return lookup


def _attach_coordinates(records: list[dict], zone_coords: dict[str, tuple[float, float]]) -> None:
    for record in records:
        coords = zone_coords.get(str(record.get("zone_id") or ""))
        if coords:
            record["latitude"], record["longitude"] = coords
        else:
            record["latitude"] = None
            record["longitude"] = None


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Great-circle distance in kilometers."""
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _same_country(source: dict, destination: dict) -> bool:
    source_country = (source.get("country") or "").strip().lower()
    dest_country = (destination.get("country") or "").strip().lower()
    return bool(source_country and dest_country and source_country == dest_country)


def estimate_distance_km(source: dict, destination: dict) -> float:
    """Use coordinates when available; otherwise apply a simple simulated distance."""
    lat1 = source.get("latitude")
    lon1 = source.get("longitude")
    lat2 = destination.get("latitude")
    lon2 = destination.get("longitude")
    if None not in (lat1, lon1, lat2, lon2):
        return haversine_km(
            _to_float(lat1),
            _to_float(lon1),
            _to_float(lat2),
            _to_float(lon2),
        )
    return SIMULATED_SAME_COUNTRY_KM if _same_country(source, destination) else SIMULATED_CROSS_COUNTRY_KM


def estimate_unit_transport_cost(source: dict, destination: dict) -> float:
    """Lower cost for same-country routes; higher for cross-country fallback."""
    base = SAME_COUNTRY_BASE_COST if _same_country(source, destination) else CROSS_COUNTRY_BASE_COST
    return base + (DISTANCE_COST_PER_KM * estimate_distance_km(source, destination))


def _match_type(source: dict, destination: dict) -> str:
    return "same_country" if _same_country(source, destination) else "cross_country_fallback"


def _confidence_for_match(match_type: str) -> str:
    return "high" if match_type == "same_country" else "low"


def _solver_status_label(status_code: int) -> str:
    if not ORTOOLS_AVAILABLE or pywraplp is None:
        return "unavailable"
    mapping = {
        pywraplp.Solver.OPTIMAL: "optimal",
        pywraplp.Solver.FEASIBLE: "feasible",
        pywraplp.Solver.INFEASIBLE: "infeasible",
        pywraplp.Solver.UNBOUNDED: "unbounded",
        pywraplp.Solver.ABNORMAL: "abnormal",
        pywraplp.Solver.NOT_SOLVED: "not_solved",
    }
    return mapping.get(status_code, "unknown")


def _solve_resource_type_flow(
    resource_type: str,
    surplus_nodes: list[dict],
    shortage_nodes: list[dict],
) -> tuple[str, list[dict], dict[tuple[str, str], int]]:
    """Solve a minimum-cost flow for one resource type."""
    if not ORTOOLS_AVAILABLE or pywraplp is None:
        return "unavailable", [], {}

    if not surplus_nodes or not shortage_nodes:
        return "no_problem", [], {}

    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        return "unavailable", [], {}

    shipment_vars: dict[tuple[int, int], object] = {}
    costs: dict[tuple[int, int], float] = {}
    unmet_vars: list[object] = []

    for supply_index, source in enumerate(surplus_nodes):
        for demand_index, destination in enumerate(shortage_nodes):
            if source.get("zone_id") == destination.get("zone_id"):
                continue
            unit_cost = estimate_unit_transport_cost(source, destination)
            var_name = f"x_{resource_type}_{supply_index}_{demand_index}"
            shipment_vars[(supply_index, demand_index)] = solver.NumVar(
                0.0,
                solver.infinity(),
                var_name,
            )
            costs[(supply_index, demand_index)] = unit_cost

    for demand_index, destination in enumerate(shortage_nodes):
        unmet_vars.append(
            solver.NumVar(
                0.0,
                _to_float(destination.get("shortage_gap")),
                f"unmet_{resource_type}_{demand_index}",
            )
        )

    if not shipment_vars:
        return "no_feasible_routes", [], {}

    objective = solver.Objective()
    for key, variable in shipment_vars.items():
        objective.SetCoefficient(variable, costs[key])
    for unmet_var in unmet_vars:
        objective.SetCoefficient(unmet_var, UNMET_DEMAND_PENALTY)
    objective.SetMinimization()

    for supply_index, source in enumerate(surplus_nodes):
        constraint = solver.Constraint(0.0, _to_float(source.get("surplus_amount")))
        for demand_index in range(len(shortage_nodes)):
            variable = shipment_vars.get((supply_index, demand_index))
            if variable is not None:
                constraint.SetCoefficient(variable, 1.0)

    for demand_index, destination in enumerate(shortage_nodes):
        demand_limit = _to_float(destination.get("shortage_gap"))
        constraint = solver.Constraint(demand_limit, demand_limit)
        for supply_index in range(len(surplus_nodes)):
            variable = shipment_vars.get((supply_index, demand_index))
            if variable is not None:
                constraint.SetCoefficient(variable, 1.0)
        constraint.SetCoefficient(unmet_vars[demand_index], 1.0)

    status_code = solver.Solve()
    status_label = _solver_status_label(status_code)
    if status_label not in {"optimal", "feasible"}:
        return status_label, [], {}

    recommendations: list[dict] = []
    received_by_dest: dict[tuple[str, str], int] = {}

    for (supply_index, demand_index), variable in shipment_vars.items():
        quantity = max(0, int(round(variable.solution_value())))
        if quantity <= 0:
            continue

        source = surplus_nodes[supply_index]
        destination = shortage_nodes[demand_index]
        match = _match_type(source, destination)
        unit_cost = costs[(supply_index, demand_index)]
        line_cost = round(unit_cost * quantity, 2)

        recommendations.append(
            {
                "source_zone_id": source.get("zone_id"),
                "source_zone_name": source.get("zone_name"),
                "destination_zone_id": destination.get("zone_id"),
                "destination_zone_name": destination.get("zone_name"),
                "resource_type": resource_type,
                "optimized_quantity": quantity,
                # Backwards-compatible numeric fields (do not imply USD).
                "estimated_cost": line_cost,
                "unit_transport_cost": round(unit_cost, 4),
                # Preferred naming for UI/API consumers.
                "simulated_transport_cost": line_cost,
                "simulated_unit_cost": round(unit_cost, 4),
                "match_type": match,
                "confidence": _confidence_for_match(match),
            }
        )

        dest_key = (str(destination.get("zone_id")), resource_type)
        received_by_dest[dest_key] = received_by_dest.get(dest_key, 0) + quantity

    return status_label, recommendations, received_by_dest


def _aggregate_status(statuses: list[str]) -> str:
    if not statuses:
        return "no_problem"
    if "unavailable" in statuses:
        return "unavailable"
    if all(status in {"no_problem", "no_feasible_routes"} for status in statuses):
        return "no_problem"
    if "infeasible" in statuses and not any(status in {"optimal", "feasible"} for status in statuses):
        return "infeasible"
    if any(status in {"optimal", "feasible"} for status in statuses):
        return "optimal"
    return statuses[0]


def _build_demand_satisfied_summary(
    shortage_records: list[dict],
    received_by_dest: dict[tuple[str, str], int],
) -> list[dict]:
    summary: list[dict] = []
    for shortage in shortage_records:
        resource_type = shortage.get("resource_type")
        zone_id = str(shortage.get("zone_id"))
        requested_gap = _to_int(shortage.get("shortage_gap"))
        satisfied = received_by_dest.get((zone_id, resource_type), 0)
        remaining = max(0, requested_gap - satisfied)
        satisfaction_pct = round((satisfied / requested_gap) * 100, 1) if requested_gap > 0 else 0.0
        summary.append(
            {
                "zone_id": shortage.get("zone_id"),
                "zone_name": shortage.get("zone_name"),
                "resource_type": resource_type,
                "requested_gap": requested_gap,
                "satisfied_quantity": satisfied,
                "remaining_gap": remaining,
                "satisfaction_pct": satisfaction_pct,
            }
        )
    summary.sort(key=lambda item: (-item["remaining_gap"], -item["requested_gap"]))
    return summary


def generate_optimized_transfers(
    shortage_records: list[dict],
    surplus_records: list[dict],
) -> dict:
    """Run OR-Tools minimum-cost transfer optimization across resource types."""
    if not ORTOOLS_AVAILABLE:
        return {
            "optimization_status": "unavailable",
            "message": "OR-Tools is not installed. Install ortools to enable optimized transfer planning.",
            "total_estimated_cost": 0.0,
            "total_simulated_transport_cost": 0.0,
            "total_quantity_moved": 0,
            "demand_satisfied_summary": [],
            "recommendations": [],
            "total_recommendations": 0,
            "method_note": METHOD_NOTE,
            "validation_note": VALIDATION_NOTE,
            "cost_note": COST_NOTE,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    if not shortage_records or not surplus_records:
        return {
            "optimization_status": "no_problem",
            "message": "No shortage and surplus pairs are available for optimization.",
            "total_estimated_cost": 0.0,
            "total_simulated_transport_cost": 0.0,
            "total_quantity_moved": 0,
            "demand_satisfied_summary": _build_demand_satisfied_summary(shortage_records, {}),
            "recommendations": [],
            "total_recommendations": 0,
            "method_note": METHOD_NOTE,
            "validation_note": VALIDATION_NOTE,
            "cost_note": COST_NOTE,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    resource_types = sorted(
        {
            record.get("resource_type")
            for record in shortage_records + surplus_records
            if record.get("resource_type")
        }
    )

    all_recommendations: list[dict] = []
    received_by_dest: dict[tuple[str, str], int] = {}
    statuses: list[str] = []

    for resource_type in resource_types:
        type_shortages = [item for item in shortage_records if item.get("resource_type") == resource_type]
        type_surpluses = [item for item in surplus_records if item.get("resource_type") == resource_type]
        status, recommendations, received = _solve_resource_type_flow(
            str(resource_type),
            type_surpluses,
            type_shortages,
        )
        statuses.append(status)
        all_recommendations.extend(recommendations)
        for key, quantity in received.items():
            received_by_dest[key] = received_by_dest.get(key, 0) + quantity

    optimization_status = _aggregate_status(statuses)
    total_estimated_cost = round(
        sum(_to_float(item.get("estimated_cost")) for item in all_recommendations),
        2,
    )
    total_quantity_moved = sum(_to_int(item.get("optimized_quantity")) for item in all_recommendations)

    message = None
    if optimization_status == "infeasible":
        message = (
            "The optimization model could not find a feasible transfer plan for the current "
            "supply and demand constraints."
        )
    elif optimization_status == "no_problem":
        message = "No optimizable shortage and surplus pairs were found."

    all_recommendations.sort(
        key=lambda item: (
            0 if item.get("match_type") == "same_country" else 1,
            item.get("resource_type") or "",
            -_to_int(item.get("optimized_quantity")),
        )
    )

    return {
        "optimization_status": optimization_status,
        "message": message,
        "total_estimated_cost": total_estimated_cost,
        "total_simulated_transport_cost": total_estimated_cost,
        "total_quantity_moved": total_quantity_moved,
        "demand_satisfied_summary": _build_demand_satisfied_summary(shortage_records, received_by_dest),
        "recommendations": all_recommendations,
        "total_recommendations": len(all_recommendations),
        "method_note": METHOD_NOTE,
        "validation_note": VALIDATION_NOTE,
        "cost_note": COST_NOTE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_optimized_transfers_from_mismatches(mismatch_rows: list[dict]) -> dict:
    """Build optimized transfer payload from raw mismatch score rows."""
    zone_coords = _build_zone_coordinate_lookup(mismatch_rows)
    shortages = build_shortage_records(mismatch_rows)
    surpluses = build_surplus_records(mismatch_rows)
    _attach_coordinates(shortages, zone_coords)
    _attach_coordinates(surpluses, zone_coords)
    return generate_optimized_transfers(shortages, surpluses)


def main() -> None:
    import os
    import sys
    from pathlib import Path

    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text

    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path, override=True, encoding="utf-8-sig")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found.")
        sys.exit(1)

    query = """
        SELECT
            m.zone_id,
            z.zone_name,
            z.country,
            z.latitude,
            z.longitude,
            m.resource_type,
            m.total_available,
            m.total_needed,
            m.shortage_gap,
            m.urgency_level,
            m.mismatch_score,
            m.status_label
        FROM mismatch_scores m
        JOIN zones z ON m.zone_id = z.zone_id
        ORDER BY m.mismatch_score DESC
    """
    engine = create_engine(database_url)
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(text(query)).mappings()]

    result = generate_optimized_transfers_from_mismatches(rows)
    print(f"Optimization status: {result['optimization_status']}")
    print(f"Total simulated transport cost (cost units): {result['total_estimated_cost']}")
    print(f"Total quantity moved: {result['total_quantity_moved']}")
    print(f"Recommendations: {result['total_recommendations']}")
    for index, item in enumerate(result["recommendations"][:10], start=1):
        print("-" * 72)
        print(
            f"{index}. {item['resource_type']}: "
            f"{item['source_zone_name']} -> {item['destination_zone_name']}"
        )
        print(
            f"   Qty: {item['optimized_quantity']} | Simulated cost units: {item['estimated_cost']} | "
            f"Match: {item['match_type']}"
        )


if __name__ == "__main__":
    main()
