#!/usr/bin/env python3
"""
Setup test database schema and seed data
"""
import os
from src.models.schema import Base, create_hypertables
from sqlalchemy import create_engine


def main():
    # Use the existing database
    db_url = "postgresql://pbsg:pbsg_password@localhost:5432/pbsg"

    try:
        engine = create_engine(db_url)

        # Create all tables
        print("Creating database schema...")
        Base.metadata.create_all(engine)

        # Create hypertables
        print("Creating hypertables...")
        create_hypertables(engine)

        print("✅ Database setup complete!")

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
