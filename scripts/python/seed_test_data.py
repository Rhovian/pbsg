#!/usr/bin/env python3
"""
Seed test database with sample data
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.services.data_sources.kraken.transformer import KrakenToTimescaleTransformer
from tests.conftest import SeedDataGenerator


def main():
    db_url = "postgresql://pbsg:pbsg_password@localhost:5432/pbsg"

    try:
        engine = create_engine(db_url)
        session = Session(engine)
        generator = SeedDataGenerator()

        print("Seeding test data...")

        # Generate sample data for each symbol
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        scenarios = ["normal", "bull", "bear", "volatile"]

        from datetime import datetime, timezone, timedelta

        for symbol_idx, symbol in enumerate(symbols):
            for scenario_idx, scenario in enumerate(scenarios):
                print(f"  Generating {scenario} data for {symbol}...")

                # Offset start times to avoid duplicates
                base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
                start_time = base_time + timedelta(
                    days=symbol_idx * 10 + scenario_idx * 2
                )

                ohlc_data = generator.generate_ohlc_data(
                    symbol=symbol,
                    start_time=start_time,
                    count=16,  # 4 hours of 15-min data
                    interval_minutes=15,
                )

                # Transform and store
                for ohlc in ohlc_data:
                    model = KrakenToTimescaleTransformer.transform(ohlc)
                    if model:
                        session.add(model)

        session.commit()
        session.close()

        print("✅ Test data seeded successfully!")

    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
