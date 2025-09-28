"""
Integration tests for database operations with seed data
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from src.models.schema import (
    Base, BTCOHLC, ETHOHLC, SOLOHLC,
    PointIndicator, RangeIndicator, VolumeProfile, Signal,
    get_ohlc_model, create_hypertables
)
from src.services.data_sources.transformer import KrakenToTimescaleTransformer
from src.services.data_sources.integrated_storage import IntegratedOHLCStorage


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseIntegration:
    """Test database operations with realistic seed data"""

    @pytest.fixture(scope="class")
    def test_db_engine(self):
        """Create test database engine (use SQLite for tests)"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()

    @pytest.fixture
    def db_session(self, test_db_engine):
        """Create database session"""
        session = Session(test_db_engine)
        yield session
        session.close()

    @pytest.fixture
    def storage(self, test_db_engine):
        """Create integrated storage"""
        return IntegratedOHLCStorage(test_db_engine, max_batch_size=100)

    def test_bulk_insert_ohlc_data(self, db_session, seed_generator):
        """Test bulk inserting OHLC data"""
        # Generate diverse market data
        btc_data = seed_generator.generate_market_scenario(
            scenario="normal",
            symbol="BTC/USD",
            duration_minutes=240  # 4 hours
        )

        # Transform to database models
        models = []
        for ohlc in btc_data:
            model = KrakenToTimescaleTransformer.transform(ohlc)
            if model:
                models.append(model)

        # Bulk insert
        db_session.add_all(models)
        db_session.commit()

        # Verify data inserted
        count = db_session.query(func.count(BTCOHLC.time)).scalar()
        assert count == len(models)

        # Verify data integrity
        first_record = db_session.query(BTCOHLC).order_by(BTCOHLC.time).first()
        assert first_record.symbol == "BTC/USD"
        assert first_record.timeframe == "15m"

    def test_multi_symbol_storage(self, db_session, seed_generator):
        """Test storing data for multiple symbols"""
        symbols_data = {
            "BTC/USD": seed_generator.generate_market_scenario(
                "bull", "BTC/USD", 60
            ),
            "ETH/USD": seed_generator.generate_market_scenario(
                "bear", "ETH/USD", 60
            ),
            "SOL/USD": seed_generator.generate_market_scenario(
                "volatile", "SOL/USD", 60
            )
        }

        # Store all data
        for symbol, ohlc_list in symbols_data.items():
            for ohlc in ohlc_list:
                model = KrakenToTimescaleTransformer.transform(ohlc)
                if model:
                    db_session.add(model)

        db_session.commit()

        # Verify each symbol stored correctly
        btc_count = db_session.query(func.count(BTCOHLC.time)).scalar()
        eth_count = db_session.query(func.count(ETHOHLC.time)).scalar()
        sol_count = db_session.query(func.count(SOLOHLC.time)).scalar()

        assert btc_count == 4  # 60 min / 15 min = 4
        assert eth_count == 4
        assert sol_count == 4

    def test_query_time_range(self, db_session, seed_generator):
        """Test querying OHLC data by time range"""
        start_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Generate data with known timestamps
        ohlc_data = seed_generator.generate_ohlc_data(
            symbol="BTC/USD",
            start_time=start_time,
            count=10,
            interval_minutes=15
        )

        # Store data
        for ohlc in ohlc_data:
            model = KrakenToTimescaleTransformer.transform(ohlc)
            if model:
                db_session.add(model)
        db_session.commit()

        # Query specific time range (middle 5 candles)
        range_start = start_time + timedelta(minutes=30)
        range_end = start_time + timedelta(minutes=105)

        results = db_session.query(BTCOHLC).filter(
            BTCOHLC.time >= range_start,
            BTCOHLC.time <= range_end
        ).all()

        assert len(results) == 5

    def test_aggregate_calculations(self, db_session, seed_generator):
        """Test aggregate calculations on OHLC data"""
        # Generate known data
        ohlc_data = seed_generator.generate_ohlc_data(
            symbol="ETH/USD",
            base_price=3000,
            count=20
        )

        # Store data
        for ohlc in ohlc_data:
            model = KrakenToTimescaleTransformer.transform(ohlc)
            if model:
                db_session.add(model)
        db_session.commit()

        # Calculate aggregates
        stats = db_session.query(
            func.min(ETHOHLC.low).label("min_low"),
            func.max(ETHOHLC.high).label("max_high"),
            func.avg(ETHOHLC.close).label("avg_close"),
            func.sum(ETHOHLC.volume).label("total_volume")
        ).first()

        assert stats.min_low is not None
        assert stats.max_high is not None
        assert stats.avg_close is not None
        assert stats.total_volume is not None

    def test_store_point_indicators(self, db_session, seed_generator):
        """Test storing point-in-time indicators"""
        # Generate OHLC data
        ohlc_data = seed_generator.generate_ohlc_data(
            symbol="BTC/USD",
            count=10
        )

        # Calculate and store indicators
        for i, ohlc in enumerate(ohlc_data):
            # Mock RSI calculation
            rsi_value = 30 + (i * 5)  # Increasing RSI

            indicator = PointIndicator(
                time=ohlc.interval_begin,
                symbol=ohlc.symbol,
                timeframe="15m",
                indicator="RSI",
                value={"value": rsi_value, "signal": "neutral"}
            )
            db_session.add(indicator)

            # Mock MACD
            macd_indicator = PointIndicator(
                time=ohlc.interval_begin,
                symbol=ohlc.symbol,
                timeframe="15m",
                indicator="MACD",
                value={
                    "macd": float(ohlc.close) * 0.001,
                    "signal": float(ohlc.close) * 0.0009,
                    "histogram": float(ohlc.close) * 0.0001
                }
            )
            db_session.add(macd_indicator)

        db_session.commit()

        # Query indicators
        rsi_indicators = db_session.query(PointIndicator).filter(
            PointIndicator.indicator == "RSI"
        ).all()

        assert len(rsi_indicators) == 10
        # Verify RSI values are increasing
        rsi_values = [ind.value["value"] for ind in rsi_indicators]
        assert rsi_values == sorted(rsi_values)

    def test_store_range_indicators(self, db_session):
        """Test storing range indicators like support/resistance"""
        # Create support/resistance levels
        levels = [
            RangeIndicator(
                symbol="BTC/USD",
                timeframe="1h",
                indicator="SUPPORT",
                range_high=Decimal("48500"),
                range_low=Decimal("48000"),
                strength=0.85,
                metadata={"touches": 4, "type": "historical"}
            ),
            RangeIndicator(
                symbol="BTC/USD",
                timeframe="1h",
                indicator="RESISTANCE",
                range_high=Decimal("52500"),
                range_low=Decimal("52000"),
                strength=0.90,
                metadata={"touches": 3, "type": "psychological"}
            ),
            RangeIndicator(
                symbol="BTC/USD",
                timeframe="15m",
                indicator="FVG",
                range_high=Decimal("50200"),
                range_low=Decimal("49800"),
                strength=0.70,
                metadata={"direction": "bullish", "filled": False}
            )
        ]

        db_session.add_all(levels)
        db_session.commit()

        # Query active levels
        active_levels = db_session.query(RangeIndicator).filter(
            RangeIndicator.symbol == "BTC/USD",
            RangeIndicator.invalidated == False
        ).all()

        assert len(active_levels) == 3

        # Test invalidation
        fvg = db_session.query(RangeIndicator).filter(
            RangeIndicator.indicator == "FVG"
        ).first()

        fvg.invalidated = True
        fvg.invalidated_at = datetime.now(timezone.utc)
        db_session.commit()

        # Check active levels again
        active_levels = db_session.query(RangeIndicator).filter(
            RangeIndicator.invalidated == False
        ).all()

        assert len(active_levels) == 2

    def test_volume_profile_storage(self, db_session):
        """Test storing volume profile data"""
        profile_data = []
        total_volume = 0

        # Generate profile levels
        for price in range(49000, 52000, 100):
            volume = 1000 + (price % 1000)  # Varying volume
            total_volume += volume
            profile_data.append({
                "price": price,
                "volume": volume,
                "percentage": 0  # Will calculate
            })

        # Calculate percentages
        for level in profile_data:
            level["percentage"] = (level["volume"] / total_volume) * 100

        # Find POC (highest volume level)
        poc_level = max(profile_data, key=lambda x: x["volume"])

        profile = VolumeProfile(
            symbol="BTC/USD",
            timeframe="24h",
            period_start=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc),
            poc_price=Decimal(str(poc_level["price"])),
            poc_volume=Decimal(str(poc_level["volume"])),
            vah=Decimal("51500"),
            val=Decimal("49500"),
            total_volume=Decimal(str(total_volume)),
            price_step=Decimal("100"),
            num_levels=len(profile_data),
            profile_data=profile_data
        )

        db_session.add(profile)
        db_session.commit()

        # Query and verify
        stored_profile = db_session.query(VolumeProfile).filter(
            VolumeProfile.symbol == "BTC/USD"
        ).first()

        assert stored_profile is not None
        assert stored_profile.num_levels == len(profile_data)
        assert len(stored_profile.profile_data) == len(profile_data)
        assert stored_profile.poc_price == Decimal(str(poc_level["price"]))

    def test_signal_generation_and_storage(self, db_session, seed_generator):
        """Test generating and storing trading signals"""
        # Generate market data
        ohlc_data = seed_generator.generate_market_scenario(
            scenario="volatile",
            symbol="ETH/USD",
            duration_minutes=120
        )

        signals_generated = []

        # Analyze data and generate signals
        for i, ohlc in enumerate(ohlc_data):
            if i < 2:
                continue  # Need history

            # Simple signal generation logic
            prev_close = ohlc_data[i-1].close
            curr_close = ohlc.close

            change_pct = float((curr_close - prev_close) / prev_close) * 100

            signal = None
            if change_pct > 2:  # Strong upward move
                signal = Signal(
                    symbol=ohlc.symbol,
                    timeframe="15m",
                    signal_type="BUY",
                    confidence=min(0.9, change_pct / 5),
                    context={
                        "trigger": "price_surge",
                        "change_pct": change_pct,
                        "volume": float(ohlc.volume)
                    }
                )
            elif change_pct < -2:  # Strong downward move
                signal = Signal(
                    symbol=ohlc.symbol,
                    timeframe="15m",
                    signal_type="SELL",
                    confidence=min(0.9, abs(change_pct) / 5),
                    context={
                        "trigger": "price_drop",
                        "change_pct": change_pct,
                        "volume": float(ohlc.volume)
                    }
                )

            if signal:
                signals_generated.append(signal)
                db_session.add(signal)

        db_session.commit()

        # Verify signals stored
        stored_signals = db_session.query(Signal).filter(
            Signal.symbol == "ETH/USD"
        ).all()

        assert len(stored_signals) == len(signals_generated)

        # Check signal quality
        high_confidence = db_session.query(Signal).filter(
            Signal.confidence > 0.7
        ).all()

        # In volatile market, should have some high confidence signals
        assert len(high_confidence) > 0

    def test_data_consistency_across_tables(self, db_session, seed_generator):
        """Test data consistency when storing related data"""
        start_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

        # Generate OHLC data
        ohlc_data = seed_generator.generate_ohlc_data(
            symbol="SOL/USD",
            start_time=start_time,
            count=5
        )

        # Store OHLC and related indicators
        for ohlc in ohlc_data:
            # Store OHLC
            model = KrakenToTimescaleTransformer.transform(ohlc)
            if model:
                db_session.add(model)

            # Store indicator
            indicator = PointIndicator(
                time=ohlc.interval_begin,
                symbol=ohlc.symbol,
                timeframe="15m",
                indicator="VOLUME_MA",
                value={"ma": float(ohlc.volume), "trend": "neutral"}
            )
            db_session.add(indicator)

        db_session.commit()

        # Verify consistency
        ohlc_times = db_session.query(SOLOHLC.time).all()
        indicator_times = db_session.query(PointIndicator.time).filter(
            PointIndicator.symbol == "SOL/USD"
        ).all()

        # Should have matching timestamps
        ohlc_time_set = {t[0] for t in ohlc_times}
        indicator_time_set = {t[0] for t in indicator_times}

        assert ohlc_time_set == indicator_time_set