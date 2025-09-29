#!/usr/bin/env python3
"""
Run the dashboard with database connectivity
"""

from dotenv import load_dotenv
from src.services.dash_service import DashService
from src.models.database import engine
from loguru import logger

load_dotenv()


def main():
    """Run the dashboard connected to the database"""
    try:
        logger.info("Starting dashboard with database connectivity...")

        # Create dashboard service with database engine
        dashboard = DashService(engine=engine, debug=True)

        # Run on all interfaces so it's accessible from host
        dashboard.run(host="0.0.0.0", port=8050)

    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
