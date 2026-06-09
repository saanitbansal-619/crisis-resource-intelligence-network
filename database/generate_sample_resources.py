"""
Generate simulated humanitarian coordination data.

Real NGO resource inventories are not publicly available for privacy,
security, and operational reasons. This script creates deterministic
sample data for organizations, zones, inventory, and requests so the
supply-demand mismatch workflow can be prototyped locally.

Run: python -m database.generate_sample_resources
"""

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"

RANDOM_SEED = 42

RESOURCE_UNITS = {
    "food_kits": "kits",
    "water_kits": "kits",
    "insulin": "units",
    "antibiotics": "units",
    "shelter_tents": "tents",
    "blankets": "units",
    "hygiene_kits": "kits",
    "medical_staff": "staff",
    "volunteers": "people",
}

URGENCY_LEVELS = ["low", "medium", "high", "critical"]

ORGANIZATIONS = [
    {
        "org_id": "ORG001",
        "org_name": "Médecins Sans Frontières",
        "org_type": "International NGO",
        "country": "Switzerland",
        "contact_email": "field.ops@msf-sim.example.org",
    },
    {
        "org_id": "ORG002",
        "org_name": "Qatar Charity",
        "org_type": "Non-governmental Organization",
        "country": "Qatar",
        "contact_email": "relief@qcharity-sim.example.org",
    },
    {
        "org_id": "ORG003",
        "org_name": "UN High Commissioner for Refugees",
        "org_type": "International Organization",
        "country": "Switzerland",
        "contact_email": "coordination@unhcr-sim.example.org",
    },
    {
        "org_id": "ORG004",
        "org_name": "Philippines Local Relief Coalition",
        "org_type": "Local NGO",
        "country": "Philippines",
        "contact_email": "dispatch@ph-relief-sim.example.org",
    },
    {
        "org_id": "ORG005",
        "org_name": "Türkiye Disaster Response Network",
        "org_type": "Government Agency",
        "country": "Türkiye",
        "contact_email": "logistics@tdrn-sim.example.org",
    },
    {
        "org_id": "ORG006",
        "org_name": "World Food Programme Field Unit",
        "org_type": "UN Agency",
        "country": "Italy",
        "contact_email": "supply@wfp-sim.example.org",
    },
    {
        "org_id": "ORG007",
        "org_name": "Chad Sahel Coordination Desk",
        "org_type": "Regional NGO",
        "country": "Chad",
        "contact_email": "ops@sahel-desk-sim.example.org",
    },
]

ZONES = [
    {
        "zone_id": "ZONE001",
        "zone_name": "Metro Manila Response Zone",
        "country": "Philippines",
        "admin_region": "National Capital Region",
        "latitude": 14.5995,
        "longitude": 120.9842,
        "population_estimate": 13500000,
        "crisis_event_id": "1544854",
    },
    {
        "zone_id": "ZONE002",
        "zone_name": "Eastern Mindanao Coastal Corridor",
        "country": "Philippines",
        "admin_region": "Davao Region",
        "latitude": 7.0731,
        "longitude": 125.6128,
        "population_estimate": 5200000,
        "crisis_event_id": "1544800",
    },
    {
        "zone_id": "ZONE003",
        "zone_name": "Hatay Province Relief Zone",
        "country": "Türkiye",
        "admin_region": "Hatay",
        "latitude": 36.4018,
        "longitude": 36.3498,
        "population_estimate": 1680000,
        "crisis_event_id": "1103920",
    },
    {
        "zone_id": "ZONE004",
        "zone_name": "Gaziantep Support Hub",
        "country": "Türkiye",
        "admin_region": "Gaziantep",
        "latitude": 37.0662,
        "longitude": 37.3833,
        "population_estimate": 2130000,
        "crisis_event_id": "1103920",
    },
    {
        "zone_id": "ZONE005",
        "zone_name": "Chad Sahel Transit Zone",
        "country": "Chad",
        "admin_region": "Logone Oriental",
        "latitude": 8.6733,
        "longitude": 16.0750,
        "population_estimate": 780000,
        "crisis_event_id": None,
    },
    {
        "zone_id": "ZONE006",
        "zone_name": "Kabul Returnee Corridor",
        "country": "Afghanistan",
        "admin_region": "Kabul",
        "latitude": 34.5553,
        "longitude": 69.2075,
        "population_estimate": 4600000,
        "crisis_event_id": None,
    },
    {
        "zone_id": "ZONE007",
        "zone_name": "Sarajevo Returnee Support Zone",
        "country": "Bosnia and Herzegovina",
        "admin_region": "Federation of Bosnia and Herzegovina",
        "latitude": 43.8563,
        "longitude": 18.4131,
        "population_estimate": 275000,
        "crisis_event_id": None,
    },
    {
        "zone_id": "ZONE008",
        "zone_name": "Cebu Surplus Warehouse Hub",
        "country": "Philippines",
        "admin_region": "Central Visayas",
        "latitude": 10.3157,
        "longitude": 123.8854,
        "population_estimate": 3200000,
        "crisis_event_id": None,
    },
    {
        "zone_id": "ZONE009",
        "zone_name": "Ankara Medical Reserve Zone",
        "country": "Türkiye",
        "admin_region": "Ankara",
        "latitude": 39.9334,
        "longitude": 32.8597,
        "population_estimate": 5800000,
        "crisis_event_id": None,
    },
    {
        "zone_id": "ZONE010",
        "zone_name": "Surigao Field Response Site",
        "country": "Philippines",
        "admin_region": "Caraga",
        "latitude": 9.7853,
        "longitude": 125.4950,
        "population_estimate": 510000,
        "crisis_event_id": "1544740",
    },
]


def _timestamp(days_ago: int) -> datetime:
    """Return a deterministic UTC timestamp."""
    base = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    return base - timedelta(days=days_ago)


def build_inventory_records() -> list[dict]:
    """
    Build inventory records with intentional shortage and surplus patterns.

    Shortage zones: ZONE001, ZONE002, ZONE010
    Surplus zones: ZONE008, ZONE009
    """
    random.seed(RANDOM_SEED)
    records = []
    counter = 1

    # Shortage zone inventory (low supply)
    shortage_inventory = [
        ("ZONE001", "ORG004", "food_kits", 800),
        ("ZONE001", "ORG003", "water_kits", 1200),
        ("ZONE001", "ORG001", "medical_staff", 45),
        ("ZONE002", "ORG004", "water_kits", 400),
        ("ZONE002", "ORG006", "food_kits", 950),
        ("ZONE010", "ORG004", "antibiotics", 150),
        ("ZONE010", "ORG001", "insulin", 90),
        ("ZONE010", "ORG004", "hygiene_kits", 220),
    ]

    # Surplus zone inventory (high supply)
    surplus_inventory = [
        ("ZONE008", "ORG006", "shelter_tents", 1500),
        ("ZONE008", "ORG004", "blankets", 4200),
        ("ZONE008", "ORG006", "food_kits", 6800),
        ("ZONE009", "ORG005", "blankets", 3200),
        ("ZONE009", "ORG001", "insulin", 2400),
        ("ZONE009", "ORG005", "antibiotics", 5100),
    ]

    # Balanced inventory for other zones
    balanced_inventory = [
        ("ZONE003", "ORG005", "shelter_tents", 900),
        ("ZONE003", "ORG002", "hygiene_kits", 1100),
        ("ZONE004", "ORG005", "water_kits", 1600),
        ("ZONE004", "ORG002", "food_kits", 1400),
        ("ZONE005", "ORG007", "food_kits", 700),
        ("ZONE005", "ORG007", "water_kits", 650),
        ("ZONE006", "ORG003", "hygiene_kits", 800),
        ("ZONE006", "ORG003", "blankets", 950),
        ("ZONE007", "ORG002", "shelter_tents", 300),
        ("ZONE007", "ORG003", "volunteers", 120),
    ]

    for zone_id, org_id, resource_type, quantity in (
        shortage_inventory + surplus_inventory + balanced_inventory
    ):
        records.append(
            {
                "inventory_id": f"INV{counter:04d}",
                "org_id": org_id,
                "zone_id": zone_id,
                "resource_type": resource_type,
                "quantity_available": quantity,
                "unit": RESOURCE_UNITS[resource_type],
                "last_updated": _timestamp(random.randint(1, 14)),
            }
        )
        counter += 1

    return records


def build_request_records() -> list[dict]:
    """
    Build request records with intentional shortage and surplus patterns.

    Requests exceed inventory in shortage zones and stay below inventory in surplus zones.
    """
    random.seed(RANDOM_SEED)
    records = []
    counter = 1

    shortage_requests = [
        ("ZONE001", "food_kits", 5000, "critical", "ORG004"),
        ("ZONE001", "water_kits", 4200, "high", "ORG003"),
        ("ZONE001", "medical_staff", 180, "high", "ORG001"),
        ("ZONE002", "water_kits", 3000, "critical", "ORG004"),
        ("ZONE002", "food_kits", 2800, "high", "ORG006"),
        ("ZONE010", "antibiotics", 2000, "critical", "ORG004"),
        ("ZONE010", "insulin", 850, "critical", "ORG001"),
        ("ZONE010", "hygiene_kits", 1400, "high", "ORG004"),
    ]

    surplus_requests = [
        ("ZONE008", "shelter_tents", 200, "low", "ORG006"),
        ("ZONE008", "blankets", 500, "low", "ORG004"),
        ("ZONE008", "food_kits", 900, "medium", "ORG006"),
        ("ZONE009", "blankets", 500, "low", "ORG005"),
        ("ZONE009", "insulin", 400, "medium", "ORG001"),
        ("ZONE009", "antibiotics", 600, "low", "ORG005"),
    ]

    balanced_requests = [
        ("ZONE003", "shelter_tents", 1100, "high", "ORG005"),
        ("ZONE003", "hygiene_kits", 1300, "medium", "ORG002"),
        ("ZONE004", "water_kits", 1800, "medium", "ORG005"),
        ("ZONE005", "food_kits", 900, "high", "ORG007"),
        ("ZONE006", "hygiene_kits", 950, "medium", "ORG003"),
        ("ZONE007", "shelter_tents", 350, "medium", "ORG002"),
        ("ZONE007", "volunteers", 200, "low", "ORG003"),
    ]

    for zone_id, resource_type, quantity, urgency, requested_by in (
        shortage_requests + surplus_requests + balanced_requests
    ):
        records.append(
            {
                "request_id": f"REQ{counter:04d}",
                "zone_id": zone_id,
                "resource_type": resource_type,
                "quantity_needed": quantity,
                "urgency_level": urgency,
                "requested_by": requested_by,
                "request_timestamp": _timestamp(random.randint(0, 7)),
            }
        )
        counter += 1

    return records


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    orgs_df = pd.DataFrame(ORGANIZATIONS)
    zones_df = pd.DataFrame(ZONES)
    inventory_df = pd.DataFrame(build_inventory_records())
    requests_df = pd.DataFrame(build_request_records())

    orgs_path = SAMPLE_DIR / "organizations.csv"
    zones_path = SAMPLE_DIR / "zones.csv"
    inventory_path = SAMPLE_DIR / "resource_inventory.csv"
    requests_path = SAMPLE_DIR / "resource_requests.csv"

    orgs_df.to_csv(orgs_path, index=False)
    zones_df.to_csv(zones_path, index=False)
    inventory_df.to_csv(inventory_path, index=False)
    requests_df.to_csv(requests_path, index=False)

    print(f"Generated {len(orgs_df)} organizations.")
    print(f"Generated {len(zones_df)} zones.")
    print(f"Generated {len(inventory_df)} inventory records.")
    print(f"Generated {len(requests_df)} request records.")
    print("Saved CSV files to:")
    print(f"  {orgs_path}")
    print(f"  {zones_path}")
    print(f"  {inventory_path}")
    print(f"  {requests_path}")


if __name__ == "__main__":
    main()
