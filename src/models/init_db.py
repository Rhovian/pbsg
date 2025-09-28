import asyncio
import asyncpg
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import engine, Base
from models.schema import (
    create_hypertables,
)
from loguru import logger


async def create_timescale_extensions():
    """Create TimescaleDB extension"""
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://pbsg:pbsg_password@localhost:5432/pbsg"
    )

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
        logger.info("TimescaleDB extension created")
    except Exception as e:
        logger.warning(f"Could not create TimescaleDB extension: {e}")
    finally:
        await conn.close()


async def init_database():
    """Initialize database with tables and TimescaleDB extensions"""
    await create_timescale_extensions()

    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    # Convert to hypertables
    create_hypertables(engine)
    logger.info("Database initialization complete")


if __name__ == "__main__":
    asyncio.run(init_database())
