from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "snowflake_seed.sql"


def main() -> None:
    missing = [
        name
        for name in [
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USER",
            "SNOWFLAKE_PASSWORD",
            "SNOWFLAKE_WAREHOUSE",
            "SNOWFLAKE_DATABASE",
            "SNOWFLAKE_SCHEMA",
        ]
        if not os.getenv(name)
    ]
    if missing:
        raise SystemExit(f"Missing Snowflake env vars: {', '.join(missing)}")

    import snowflake.connector

    connection = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.getenv("SNOWFLAKE_ROLE"),
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )
    try:
        cursor = connection.cursor()
        try:
            for statement in split_sql(SEED_PATH.read_text(encoding="utf-8")):
                cursor.execute(statement)
        finally:
            cursor.close()
    finally:
        connection.close()

    print("Loaded Developer Co-pilot mock tables into Snowflake.")


def split_sql(sql: str) -> list[str]:
    sql = "\n".join(
        line for line in sql.splitlines()
        if not line.strip().startswith("--")
    )
    statements: list[str] = []
    buffer: list[str] = []
    in_string = False
    index = 0
    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""
        if char == "'" and next_char == "'":
            buffer.append(char)
            buffer.append(next_char)
            index += 2
            continue
        if char == "'":
            in_string = not in_string
        if char == ";" and not in_string:
            statement = "".join(buffer).strip()
            if statement and not statement.startswith("--"):
                statements.append(statement)
            buffer = []
        else:
            buffer.append(char)
        index += 1

    tail = "".join(buffer).strip()
    if tail and not tail.startswith("--"):
        statements.append(tail)
    return statements


if __name__ == "__main__":
    main()
