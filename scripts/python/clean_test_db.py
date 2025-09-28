#!/usr/bin/env python3
"""
Clean test database by dropping and recreating all tables
"""

from sqlalchemy import create_engine, text
from src.models.schema import Base


def main():
    db_url = "postgresql://pbsg:pbsg_password@localhost:5432/pbsg"

    try:
        engine = create_engine(db_url)

        print("Cleaning database...")

        # Drop all tables
        with engine.connect() as conn:
            # Drop TimescaleDB continuous aggregates first
            try:
                conn.execute(
                    text("DROP MATERIALIZED VIEW IF EXISTS btc_hourly_ohlc CASCADE;")
                )
                conn.commit()
            except Exception:
                pass

            # Drop all tables (this will also drop hypertables)
            Base.metadata.drop_all(engine)
            conn.commit()

        print("✅ Database cleaned successfully!")

    except Exception as e:
        print(f"❌ Cleaning failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
