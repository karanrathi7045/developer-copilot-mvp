from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

LOCALITIES = [
    "Andheri West",
    "Bandra East",
    "Borivali",
    "Chembur",
    "Dadar",
    "Ghatkopar",
    "Kandivali",
    "Lower Parel",
    "Mulund",
    "Powai",
    "Thane West",
    "Vikhroli",
]
PROJECT_NAMES = [
    "Sky Heights",
    "Lakeview Enclave",
    "Metro Nest",
    "Orchid Plaza",
    "Cedar Grove",
    "Palm Vista",
    "Aurum Square",
    "Harbor Crest",
    "Nova Residences",
    "Iris Habitat",
    "Saffron Park",
    "Emerald Bay",
    "Zenith Towers",
    "Willow Walk",
    "Crescent Arena",
    "Maple County",
    "Pearl Gateway",
    "Solace Gardens",
    "Amber One",
    "Prism Estate",
]
CONFIGURATIONS = ["1 BHK", "2 BHK", "3 BHK", "4 BHK", "Studio", "Retail Shop"]
DEVELOPER_CATEGORIES = ["A", "B", "C"]
LEAD_STATUSES = [
    "New",
    "Qualified",
    "Site Visit Scheduled",
    "Negotiation",
    "Booked",
    "Lost - Budget",
    "Lost - Timing",
    "Lost - Authority",
    "Lost - Competition",
    "Inactive",
]
PROJECT_STAGES = ["Planning", "Pre-Launch", "Launched", "Under Construction", "Ready to Move"]
FIRST_NAMES = [
    "Aarav",
    "Aditi",
    "Akash",
    "Anaya",
    "Arjun",
    "Diya",
    "Ishaan",
    "Kabir",
    "Meera",
    "Naina",
    "Rohan",
    "Saanvi",
    "Tara",
    "Vihaan",
    "Zoya",
]
LAST_NAMES = [
    "Agarwal",
    "Bose",
    "Chopra",
    "Desai",
    "Iyer",
    "Kapoor",
    "Khan",
    "Mehta",
    "Nair",
    "Patel",
    "Rao",
    "Shah",
    "Singh",
    "Trivedi",
    "Verma",
]
CP_PREFIXES = [
    "NorthStar",
    "Metro",
    "Summit",
    "Legacy",
    "Prime",
    "Apex",
    "Nexus",
    "Pinnacle",
    "Urban",
    "Keystone",
]
CP_SUFFIXES = ["Realty", "Brokers", "Homes", "Channel", "Estates", "Partners"]


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    developers = build_developers()
    projects = build_projects(developers)
    inventory = build_inventory(projects)
    leads = build_leads(projects)
    bookings = build_bookings(leads)
    channel_partners = build_channel_partners(projects)

    write_csv(
        DATA_DIR / "developers.csv",
        ["id", "developer_name", "country_code", "developer_phone", "category"],
        developers,
    )
    write_csv(DATA_DIR / "projects.csv", ["id", "name", "developer_id", "stage"], projects)
    write_csv(DATA_DIR / "inventory.csv", ["id", "project_id", "configuration", "total_units", "available_units"], inventory)
    write_csv(DATA_DIR / "leads.csv", ["id", "name", "status", "project_id"], leads)
    write_csv(
        DATA_DIR / "bookings.csv",
        ["id", "lead_id", "configuration", "booking_date", "agreement_value", "brokerage_amount"],
        bookings,
    )
    write_csv(
        DATA_DIR / "channel_partner.csv",
        ["id", "cp_name", "operation_locality", "projects_working_on"],
        channel_partners,
    )
    write_snowflake_seed(developers, projects, inventory, leads, bookings, channel_partners)


def build_developers() -> list[dict[str, Any]]:
    rows = [
        {
            "id": 101,
            "developer_name": "Karan Rathi",
            "country_code": "91",
            "developer_phone": "7045706453",
            "category": "A",
        }
    ]
    for index in range(1, 100):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index * 5) % len(LAST_NAMES)]
        rows.append(
            {
                "id": 101 + index,
                "developer_name": f"{first} {last} Developers",
                "country_code": "91",
                "developer_phone": f"98{(70000000 + index * 3917) % 100000000:08d}",
                "category": DEVELOPER_CATEGORIES[index % len(DEVELOPER_CATEGORIES)],
            }
        )
    return rows


def build_projects(developers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index in range(100):
        base_name = PROJECT_NAMES[index % len(PROJECT_NAMES)]
        locality = LOCALITIES[index % len(LOCALITIES)]
        if index % 20 == 0:
            developer_id = 101
        else:
            developer_id = developers[index % len(developers)]["id"]
        rows.append(
            {
                "id": 101 + index,
                "name": f"{base_name} {index // len(PROJECT_NAMES) + 1}",
                "developer_id": developer_id,
                "stage": PROJECT_STAGES[index % len(PROJECT_STAGES)],
                "_locality": locality,
            }
        )
    return rows


def build_inventory(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, project in enumerate(projects):
        total_units = 72 + ((index * 19) % 230)
        available_units = max(4, min(total_units, 8 + ((index * 11) % 72)))
        if index % 17 == 0:
            available_units = min(total_units, available_units + 42)
        rows.append(
            {
                "id": 301 + index,
                "project_id": project["id"],
                "configuration": CONFIGURATIONS[index % len(CONFIGURATIONS)],
                "total_units": total_units,
                "available_units": available_units,
            }
        )
    return rows


def build_leads(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    demo_projects = [project for project in projects if project["developer_id"] == 101]
    demo_statuses = [
        "Lost - Budget",
        "Booked",
        "Lost - Budget",
        "Qualified",
        "Negotiation",
        "Lost - Timing",
        "Site Visit Scheduled",
        "Lost - Budget",
        "New",
        "Booked",
    ]
    for index in range(100):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index * 3) % len(LAST_NAMES)]
        if index < len(demo_statuses):
            project_id = demo_projects[index % len(demo_projects)]["id"]
            status = demo_statuses[index]
        else:
            project_id = projects[(index * 7) % len(projects)]["id"]
            status = LEAD_STATUSES[index % len(LEAD_STATUSES)]
        rows.append(
            {
                "id": 1001 + index,
                "name": f"{first} {last}",
                "status": status,
                "project_id": project_id,
            }
        )
    return rows


def build_bookings(leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    booked_leads = [lead for lead in leads if lead["status"] == "Booked"]
    base_date = date(2026, 1, 2)
    rows = []
    for index in range(100):
        lead = booked_leads[index % len(booked_leads)]
        agreement_value = 5_800_000 + ((index * 375_000) % 24_000_000)
        brokerage_amount = round(agreement_value * (0.015 + ((index % 4) * 0.0025)), 2)
        rows.append(
            {
                "id": 7001 + index,
                "lead_id": lead["id"],
                "configuration": CONFIGURATIONS[(index + 1) % 4],
                "booking_date": (base_date + timedelta(days=index)).isoformat(),
                "agreement_value": agreement_value,
                "brokerage_amount": brokerage_amount,
            }
        )
    return rows


def build_channel_partners(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index in range(100):
        project_slice = [
            projects[(index * 3 + offset * 11) % len(projects)]["name"]
            for offset in range(3 + (index % 2))
        ]
        locality_slice = [
            LOCALITIES[(index + offset * 4) % len(LOCALITIES)]
            for offset in range(2 + (index % 3))
        ]
        rows.append(
            {
                "id": 9001 + index,
                "cp_name": f"{CP_PREFIXES[index % len(CP_PREFIXES)]} {CP_SUFFIXES[index % len(CP_SUFFIXES)]} {index + 1}",
                "operation_locality": locality_slice,
                "projects_working_on": project_slice,
            }
        )
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: encode_csv_value(row[field]) for field in fieldnames})


def encode_csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return json.dumps(value)
    return value


def write_snowflake_seed(
    developers: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    leads: list[dict[str, Any]],
    bookings: list[dict[str, Any]],
    channel_partners: list[dict[str, Any]],
) -> None:
    lines = [
        "-- Snowflake seed data for Developer Co-pilot.",
        "-- Run inside the target database and schema.",
        "",
        "CREATE OR REPLACE TABLE DEVELOPERS (ID NUMBER, DEVELOPER_NAME TEXT, COUNTRY_CODE TEXT, DEVELOPER_PHONE TEXT, CATEGORY TEXT);",
        "CREATE OR REPLACE TABLE PROJECTS (ID NUMBER, NAME TEXT, DEVELOPER_ID NUMBER, STAGE TEXT);",
        "CREATE OR REPLACE TABLE INVENTORY (ID NUMBER, PROJECT_ID NUMBER, CONFIGURATION TEXT, TOTAL_UNITS NUMBER, AVAILABLE_UNITS NUMBER);",
        "CREATE OR REPLACE TABLE LEADS (ID NUMBER, NAME TEXT, STATUS TEXT, PROJECT_ID NUMBER);",
        "CREATE OR REPLACE TABLE BOOKINGS (ID NUMBER, LEAD_ID NUMBER, CONFIGURATION TEXT, BOOKING_DATE DATE, AGREEMENT_VALUE NUMBER(14,2), BROKERAGE_AMOUNT NUMBER(14,2));",
        "CREATE OR REPLACE TABLE CHANNEL_PARTNER (ID NUMBER, CP_NAME TEXT, OPERATION_LOCALITY ARRAY, PROJECTS_WORKING_ON ARRAY);",
        "",
        insert_statement(
            "DEVELOPERS",
            ["ID", "DEVELOPER_NAME", "COUNTRY_CODE", "DEVELOPER_PHONE", "CATEGORY"],
            developers,
            ["id", "developer_name", "country_code", "developer_phone", "category"],
        ),
        insert_statement("PROJECTS", ["ID", "NAME", "DEVELOPER_ID", "STAGE"], projects, ["id", "name", "developer_id", "stage"]),
        insert_statement(
            "INVENTORY",
            ["ID", "PROJECT_ID", "CONFIGURATION", "TOTAL_UNITS", "AVAILABLE_UNITS"],
            inventory,
            ["id", "project_id", "configuration", "total_units", "available_units"],
        ),
        insert_statement("LEADS", ["ID", "NAME", "STATUS", "PROJECT_ID"], leads, ["id", "name", "status", "project_id"]),
        insert_statement(
            "BOOKINGS",
            ["ID", "LEAD_ID", "CONFIGURATION", "BOOKING_DATE", "AGREEMENT_VALUE", "BROKERAGE_AMOUNT"],
            bookings,
            ["id", "lead_id", "configuration", "booking_date", "agreement_value", "brokerage_amount"],
            date_columns={"booking_date"},
        ),
        insert_statement(
            "CHANNEL_PARTNER",
            ["ID", "CP_NAME", "OPERATION_LOCALITY", "PROJECTS_WORKING_ON"],
            channel_partners,
            ["id", "cp_name", "operation_locality", "projects_working_on"],
        ),
        "",
    ]
    (DATA_DIR / "snowflake_seed.sql").write_text("\n".join(lines), encoding="utf-8")


def insert_statement(
    table: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    fields: list[str],
    date_columns: set[str] | None = None,
) -> str:
    date_columns = date_columns or set()
    values = []
    for row in rows:
        values.append("(" + ", ".join(sql_value(row[field], field in date_columns) for field in fields) + ")")
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n" + ",\n".join(values) + ";"


def sql_value(value: Any, is_date: bool = False) -> str:
    if isinstance(value, list):
        return "ARRAY_CONSTRUCT(" + ", ".join(sql_value(item) for item in value) + ")"
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        if is_date:
            return f"TO_DATE('{escaped}')"
        return f"'{escaped}'"
    return str(value)


if __name__ == "__main__":
    main()
