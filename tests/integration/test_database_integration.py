"""
Real TimescaleDB integration tests
"""

import pytest
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from src.models.schema import (
    Base,
    BTCOHLC,
    ETHOHLC,
    SOLOHLC,
    PointIndicator,
    RangeIndicator,
    VolumeProfile,
    Signal,
    get_ohlc_model,
    create_hypertables,
)
from src.services.data_sources.transformer import KrakenToTimescaleTransformer
from src.services.data_sources.integrated_storage import IntegratedOHLCStorage


@pytest.mark.integration
@pytest.mark.database
class TestTimescaleDBIntegration:
    """Test database operations with real TimescaleDB"""

    @pytest.fixture(scope="class")
    def db_engine(self):
        """Create TimescaleDB engine"""
        db_url = "postgresql://pbsg:pbsg_password@localhost:5432/pbsg"
        engine = create_engine(db_url)
        yield engine
        engine.dispose()

    @pytest.fixture
    def db_session(self, db_engine):
        """Create database session"""
        session = Session(db_engine)
        yield session
        session.close()

    @pytest.fixture
    def storage(self, db_engine):
        """Create integrated storage"""
        return IntegratedOHLCStorage(db_engine, max_batch_size=100)

    def test_hypertable_functionality(self, db_session, seed_generator):
        """Test TimescaleDB hypertable-specific functionality"""
        # Generate time-series data
        btc_data = seed_generator.generate_market_scenario(
            scenario="normal", symbol="BTC/USD", duration_minutes=240  # 4 hours of data
        )

        # Transform and store data
        models = []
        for ohlc in btc_data:
            model = KrakenToTimescaleTransformer.transform(ohlc)
            if model:
                models.append(model)

        db_session.add_all(models)
        db_session.commit()

        # Test time-based queries (hypertable benefit)
        start_time = models[0].time
        mid_time = start_time + timedelta(hours=2)

        # Query first half
        first_half = (
            db_session.query(BTCOHLC)
            .filter(BTCOHLC.time >= start_time, BTCOHLC.time < mid_time)
            .all()
        )

        # Query second half
        second_half = db_session.query(BTCOHLC).filter(BTCOHLC.time >= mid_time).all()

        assert len(first_half) + len(second_half) == len(models)
        assert len(first_half) > 0
        assert len(second_half) > 0

    def test_bulk_insert_performance(self, db_session, seed_generator):
        """Test bulk insert performance with large datasets"""
        # Generate large dataset with unique timestamps
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        all_models = []

        base_time = datetime(
            2020, 1, 1, tzinfo=timezone.utc
        )  # Use 2020 to avoid conflicts

        for i, symbol in enumerate(symbols):
            start_time = base_time + timedelta(days=i * 30)  # 30 days apart
            ohlc_data = seed_generator.generate_ohlc_data(
                symbol=symbol,
                start_time=start_time,
                count=96,  # 24 hours of 15-min data
                interval_minutes=15,
            )

            for ohlc in ohlc_data:
                model = KrakenToTimescaleTransformer.transform(ohlc)
                if model:
                    all_models.append(model)

        # Bulk insert
        start_time = datetime.now()
        db_session.add_all(all_models)
        db_session.commit()
        insert_duration = datetime.now() - start_time

        print(
            f"Inserted {len(all_models)} records in {insert_duration.total_seconds():.2f}s"
        )

        # Verify data integrity
        for symbol in symbols:
            model_class = get_ohlc_model(symbol)
            count = db_session.query(func.count(model_class.time)).scalar()
            assert count > 0

    def test_time_bucket_aggregation(self, db_session, seed_generator):
        """Test TimescaleDB time_bucket functionality"""
        # Use a very specific time range for isolation
        test_start = datetime(2022, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        ohlc_data = seed_generator.generate_ohlc_data(
            symbol="BTC/USD",
            start_time=test_start,
            count=96,  # 24 hours of 15-min data
            interval_minutes=15,
        )

        # Store data
        for ohlc in ohlc_data:
            model = KrakenToTimescaleTransformer.transform(ohlc)
            if model:
                db_session.add(model)
        db_session.commit()

        # Test time_bucket aggregation (1-hour buckets) with specific time range
        from sqlalchemy import text

        test_end = test_start + timedelta(hours=24)
        result = db_session.execute(
            text(
                """
            SELECT
                time_bucket('1 hour', time) as hour_bucket,
                AVG(close) as avg_close,
                MAX(high) as max_high,
                MIN(low) as min_low,
                SUM(volume) as total_volume
            FROM btc_ohlc
            WHERE symbol = 'BTC/USD'
              AND time >= :start_time
              AND time < :end_time
            GROUP BY hour_bucket
            ORDER BY hour_bucket
        """
            ),
            {"start_time": test_start, "end_time": test_end},
        ).fetchall()

        assert len(result) == 24  # 24 hours

        # Verify each hour has aggregated data
        for row in result:
            assert row.avg_close is not None
            assert row.max_high is not None
            assert row.min_low is not None
            assert row.total_volume is not None

    def test_compression(self, db_session, seed_generator):
        """Test TimescaleDB compression"""
        from sqlalchemy import text

        try:
            # Generate old data that could be compressed
            old_data = seed_generator.generate_ohlc_data(
                symbol="BTC/USD",
                start_time=datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                count=100,
            )

            # Store old data
            for ohlc in old_data:
                model = KrakenToTimescaleTransformer.transform(ohlc)
                if model:
                    db_session.add(model)
            db_session.commit()

            # Enable compression
            db_session.execute(
                text(
                    """
                ALTER TABLE btc_ohlc SET (
                    timescaledb.compress,
                    timescaledb.compress_segmentby = 'symbol',
                    timescaledb.compress_orderby = 'time DESC'
                );
            """
                )
            )

            # Add compression policy
            db_session.execute(
                text(
                    """
                SELECT add_compression_policy('btc_ohlc', INTERVAL '7 days');
            """
                )
            )

            db_session.commit()

        except Exception as e:
            # Skip if compression not available or already configured
            if "already" not in str(e).lower():
                pytest.skip(f"TimescaleDB compression not available: {e}")

    def test_multi_symbol_storage(self, db_session, seed_generator):
        """Test storing and querying multiple symbols"""
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        # Use very specific test times for isolation
        base_time = datetime(2022, 8, 20, 14, 30, 0, tzinfo=timezone.utc)

        # Generate data for each symbol with different time periods
        for i, symbol in enumerate(symbols):
            start_time = base_time + timedelta(hours=i * 3)  # 3 hours apart
            ohlc_data = seed_generator.generate_ohlc_data(
                symbol=symbol,
                start_time=start_time,
                count=8,  # 2 hours of data
                interval_minutes=15,
            )

            for ohlc in ohlc_data:
                model = KrakenToTimescaleTransformer.transform(ohlc)
                if model:
                    db_session.add(model)

        db_session.commit()

        # Verify each symbol has correct data using time-based filtering
        for i, symbol in enumerate(symbols):
            model_class = get_ohlc_model(symbol)
            start_time = base_time + timedelta(hours=i * 3)
            end_time = start_time + timedelta(hours=2)

            symbol_data = (
                db_session.query(model_class)
                .filter(
                    model_class.symbol == symbol,
                    model_class.time >= start_time,
                    model_class.time < end_time,
                )
                .all()
            )

            assert len(symbol_data) == 8
            # Verify all records have correct symbol
            for record in symbol_data:
                assert record.symbol == symbol

    def test_concurrent_writes(self, db_session, seed_generator):
        """Test concurrent write performance"""
        import threading
        import queue

        results = queue.Queue()

        def write_data(symbol_suffix: str):
            try:
                # Create separate session for thread
                from sqlalchemy.orm import sessionmaker

                SessionLocal = sessionmaker(bind=db_session.bind)
                thread_session = SessionLocal()

                symbol = f"BTC/USD-{symbol_suffix}"
                ohlc_data = seed_generator.generate_ohlc_data(symbol=symbol, count=20)

                for ohlc in ohlc_data:
                    # Use BTC model for all test data
                    btc_model = BTCOHLC(
                        time=ohlc.interval_begin,
                        symbol=ohlc.symbol,
                        timeframe="15m",
                        open=ohlc.open,
                        high=ohlc.high,
                        low=ohlc.low,
                        close=ohlc.close,
                        volume=ohlc.volume,
                        trades=ohlc.trades,
                    )
                    thread_session.add(btc_model)

                thread_session.commit()
                thread_session.close()
                results.put(("success", symbol_suffix))

            except Exception as e:
                results.put(("error", str(e)))

        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=write_data, args=(str(i),))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        success_count = 0
        while not results.empty():
            status, data = results.get()
            if status == "success":
                success_count += 1
            else:
                print(f"Thread error: {data}")

        assert success_count == 3
