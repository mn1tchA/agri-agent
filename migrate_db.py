"""
Database migration script — adds new columns to the existing DecisionLog table.
Safe to run multiple times (uses IF NOT EXISTS logic).

New columns added in v2.0:
  - farm_area_sqm REAL DEFAULT 0.0
  - latitude REAL DEFAULT 0.0
  - longitude REAL DEFAULT 0.0
  - plant_growth_stage TEXT DEFAULT ''
  - weather_forecast TEXT DEFAULT ''
  - meteorologist_analysis TEXT DEFAULT ''
  - botanist_analysis TEXT DEFAULT ''
  - financial_analysis TEXT DEFAULT ''
  - reasoning_confidence REAL DEFAULT 0.0
  - crop_value_at_risk_dzd REAL DEFAULT 0.0
  - outcome_rating INTEGER (nullable)
"""
import sqlite3
import logging

log = logging.getLogger("agri_agent.migrate")

NEW_COLUMNS = [
    ("farm_area_sqm", "REAL", "0.0"),
    ("latitude", "REAL", "0.0"),
    ("longitude", "REAL", "0.0"),
    ("plant_growth_stage", "TEXT", "''"),
    ("weather_forecast", "TEXT", "''"),
    ("meteorologist_analysis", "TEXT", "''"),
    ("botanist_analysis", "TEXT", "''"),
    ("financial_analysis", "TEXT", "''"),
    ("reasoning_confidence", "REAL", "0.0"),
    ("crop_value_at_risk_dzd", "REAL", "0.0"),
    ("outcome_rating", "INTEGER", "NULL"),
]


def migrate(db_path: str = "history.db") -> None:
    """Add missing columns to decisionlog table if they don't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get existing column names
    cursor.execute("PRAGMA table_info(decisionlog)")
    existing = {row[1] for row in cursor.fetchall()}

    added = []
    for col_name, col_type, default in NEW_COLUMNS:
        if col_name not in existing:
            default_clause = f"DEFAULT {default}" if default != "NULL" else ""
            sql = f"ALTER TABLE decisionlog ADD COLUMN {col_name} {col_type} {default_clause}"
            cursor.execute(sql)
            added.append(col_name)
            log.info("Added column: %s %s", col_name, col_type)

    conn.commit()
    conn.close()

    if added:
        log.info("Migration complete. Added %d columns: %s", len(added), ", ".join(added))
    else:
        log.info("Database schema is up-to-date. No migration needed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    migrate()
    print("Migration complete.")
