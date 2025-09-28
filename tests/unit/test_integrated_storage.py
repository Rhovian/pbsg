"""
Unit tests for IntegratedOHLCStorage
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from src.services.data_sources.storage import IntegratedOHLCStorage
from src.services.data_sources.types import OHLCData


class TestIntegratedOHLCStorage:
    """Test IntegratedOHLCStorage functionality"""

    @pytest.fixture
    def mock_engine(self):
        """Create mock database engine"""
        engine = MagicMock()
        return engine

    @pytest.fixture
    def sample_ohlc_data(self):
        """Create sample OHLC data"""
        return [
            OHLCData(
                symbol="BTC/USD",
                open=Decimal("50000.00"),
                high=Decimal("51000.00"),
                low=Decimal("49500.00"),
                close=Decimal("50500.00"),
                vwap=Decimal("50250.00"),
                trades=150,
                volume=Decimal("1234.56789"),
                interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                interval=15,
            ),
            OHLCData(
                symbol="ETH/USD",
                open=Decimal("3000.00"),
                high=Decimal("3100.00"),
                low=Decimal("2950.00"),
                close=Decimal("3050.00"),
                vwap=Decimal("3025.00"),
                trades=100,
                volume=Decimal("500.123"),
                interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                interval=15,
            ),
        ]

    @pytest.fixture
    def storage(self, mock_engine):
        """Create IntegratedOHLCStorage instance"""
        pause_cb = AsyncMock()
        resume_cb = AsyncMock()
        return IntegratedOHLCStorage(
            engine=mock_engine,
            pause_callback=pause_cb,
            resume_callback=resume_cb,
            max_batch_size=100,
        )

    def test_initialization(self, mock_engine):
        """Test storage initialization"""
        pause_cb = MagicMock()
        resume_cb = MagicMock()

        storage = IntegratedOHLCStorage(
            engine=mock_engine,
            pause_callback=pause_cb,
            resume_callback=resume_cb,
            max_batch_size=500,
        )

        assert storage.storage is not None
        assert storage.backpressure is not None
        assert storage.total_accepted == 0
        assert storage.total_rejected == 0
        assert storage.storage.max_batch_size == 500

    @pytest.mark.asyncio
    async def test_store_batch_success(self, storage, sample_ohlc_data):
        """Test successful batch storage"""
        # Mock storage and backpressure behavior
        storage.storage.store_batch = MagicMock(return_value=(2, 0, 2))
        storage.backpressure.should_accept_data = MagicMock(return_value=True)
        storage.backpressure.handle_storage_result = AsyncMock()

        accepted, rejected, total = await storage.store_batch(sample_ohlc_data)

        assert accepted == 2
        assert rejected == 0
        assert total == 2
        assert storage.total_accepted == 2
        assert storage.total_rejected == 0

        # Verify storage was called
        storage.storage.store_batch.assert_called_once()
        stored_data = storage.storage.store_batch.call_args[0][0]
        assert len(stored_data) == 2

        # Verify backpressure was notified of success
        storage.backpressure.handle_storage_result.assert_called_once_with(success=True)

    @pytest.mark.asyncio
    async def test_store_batch_with_duplicates(self, storage, sample_ohlc_data):
        """Test batch storage with duplicate detection"""
        # Mock first item as duplicate, second as new
        storage.backpressure.should_accept_data = MagicMock(side_effect=[False, True])
        storage.storage.store_batch = MagicMock(return_value=(1, 0, 1))
        storage.backpressure.handle_storage_result = AsyncMock()

        accepted, rejected, total = await storage.store_batch(sample_ohlc_data)

        assert accepted == 1
        assert rejected == 1
        assert total == 2
        assert storage.total_accepted == 1
        assert storage.total_rejected == 1

        # Verify only non-duplicate was stored
        stored_data = storage.storage.store_batch.call_args[0][0]
        assert len(stored_data) == 1

    @pytest.mark.asyncio
    async def test_store_batch_all_duplicates(self, storage, sample_ohlc_data):
        """Test batch storage when all items are duplicates"""
        storage.backpressure.should_accept_data = MagicMock(return_value=False)
        storage.storage.store_batch = MagicMock()

        accepted, rejected, total = await storage.store_batch(sample_ohlc_data)

        assert accepted == 0
        assert rejected == 2
        assert total == 2
        assert storage.total_accepted == 0
        assert storage.total_rejected == 2

        # Verify storage was not called
        storage.storage.store_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_batch_storage_failure(self, storage, sample_ohlc_data):
        """Test handling storage failures"""
        storage.backpressure.should_accept_data = MagicMock(return_value=True)
        storage.storage.store_batch = MagicMock(side_effect=Exception("DB error"))
        storage.backpressure.handle_storage_result = AsyncMock()

        accepted, rejected, total = await storage.store_batch(sample_ohlc_data)

        assert accepted == 0
        assert rejected == 2
        assert total == 2

        # Verify backpressure was notified of failure
        storage.backpressure.handle_storage_result.assert_called_once_with(
            success=False
        )

    @pytest.mark.asyncio
    async def test_store_batch_partial_failure(self, storage, sample_ohlc_data):
        """Test handling partial storage failures"""
        storage.backpressure.should_accept_data = MagicMock(return_value=True)
        # 1 succeeded, 1 failed
        storage.storage.store_batch = MagicMock(return_value=(1, 1, 2))
        storage.backpressure.handle_storage_result = AsyncMock()

        accepted, rejected, total = await storage.store_batch(sample_ohlc_data)

        assert accepted == 1
        assert rejected == 1
        assert total == 2

        # Partial failure still counts as failure for backpressure
        storage.backpressure.handle_storage_result.assert_called_once_with(
            success=False
        )

    @pytest.mark.asyncio
    async def test_store_batch_empty_list(self, storage):
        """Test storing empty batch"""
        accepted, rejected, total = await storage.store_batch([])

        assert accepted == 0
        assert rejected == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_store_single_success(self, storage):
        """Test storing single record successfully"""
        ohlc = OHLCData(
            symbol="BTC/USD",
            open=Decimal("50000.00"),
            high=Decimal("51000.00"),
            low=Decimal("49500.00"),
            close=Decimal("50500.00"),
            vwap=Decimal("50250.00"),
            trades=150,
            volume=Decimal("1234.56789"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        storage.backpressure.should_accept_data = MagicMock(return_value=True)
        storage.storage.store_batch = MagicMock(return_value=(1, 0, 1))
        storage.backpressure.handle_storage_result = AsyncMock()

        result = await storage.store_single(ohlc)

        assert result is True
        assert storage.total_accepted == 1

    @pytest.mark.asyncio
    async def test_store_single_failure(self, storage):
        """Test storing single record failure"""
        ohlc = OHLCData(
            symbol="BTC/USD",
            open=Decimal("50000.00"),
            high=Decimal("51000.00"),
            low=Decimal("49500.00"),
            close=Decimal("50500.00"),
            vwap=Decimal("50250.00"),
            trades=150,
            volume=Decimal("1234.56789"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        storage.backpressure.should_accept_data = MagicMock(return_value=False)

        result = await storage.store_single(ohlc)

        assert result is False
        assert storage.total_rejected == 1

    def test_get_comprehensive_stats(self, storage):
        """Test getting comprehensive statistics"""
        storage.total_accepted = 100
        storage.total_rejected = 10

        storage.storage.get_stats = MagicMock(
            return_value={"total_stored": 100, "total_failed": 10}
        )

        storage.backpressure.get_stats = MagicMock(
            return_value={"health": {"healthy": True}, "failures": 1}
        )

        stats = storage.get_comprehensive_stats()

        assert stats["integrated"]["total_accepted"] == 100
        assert stats["integrated"]["total_rejected"] == 10
        assert stats["integrated"]["acceptance_rate"] == 100 / 110
        assert stats["storage"]["total_stored"] == 100
        assert stats["backpressure"]["health"]["healthy"] is True

    def test_log_comprehensive_stats(self, storage):
        """Test logging comprehensive statistics"""
        storage.total_accepted = 50
        storage.total_rejected = 5

        storage.storage.log_stats = MagicMock()
        storage.backpressure.log_stats = MagicMock()

        storage.log_comprehensive_stats()

        storage.storage.log_stats.assert_called_once()
        storage.backpressure.log_stats.assert_called_once()

    def test_reset_stats(self, storage):
        """Test resetting statistics"""
        storage.total_accepted = 100
        storage.total_rejected = 10

        storage.storage.reset_stats = MagicMock()

        storage.reset_stats()

        assert storage.total_accepted == 0
        assert storage.total_rejected == 0
        storage.storage.reset_stats.assert_called_once()

    def test_is_healthy(self, storage):
        """Test health check"""
        storage.backpressure.get_stats = MagicMock(
            return_value={"health": {"healthy": True}}
        )

        assert storage.is_healthy() is True

        storage.backpressure.get_stats = MagicMock(
            return_value={"health": {"healthy": False}}
        )

        assert storage.is_healthy() is False

    def test_is_paused(self, storage):
        """Test pause state check"""
        storage.backpressure.is_paused = True
        assert storage.is_paused() is True

        storage.backpressure.is_paused = False
        assert storage.is_paused() is False

    def test_acceptance_rate_calculation(self, storage):
        """Test acceptance rate calculation edge cases"""
        # Test with zero values
        stats = storage.get_comprehensive_stats()
        assert stats["integrated"]["acceptance_rate"] == 0

        # Test with only accepted
        storage.total_accepted = 100
        storage.total_rejected = 0
        stats = storage.get_comprehensive_stats()
        assert stats["integrated"]["acceptance_rate"] == 1.0

        # Test with only rejected
        storage.total_accepted = 0
        storage.total_rejected = 100
        stats = storage.get_comprehensive_stats()
        assert stats["integrated"]["acceptance_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_concurrent_store_operations(self, storage, sample_ohlc_data):
        """Test concurrent storage operations"""
        storage.backpressure.should_accept_data = MagicMock(return_value=True)
        storage.storage.store_batch = MagicMock(return_value=(2, 0, 2))
        storage.backpressure.handle_storage_result = AsyncMock()

        # Run multiple concurrent store operations
        tasks = [
            storage.store_batch(sample_ohlc_data),
            storage.store_batch(sample_ohlc_data),
            storage.store_batch(sample_ohlc_data),
        ]

        results = await asyncio.gather(*tasks)

        # Each should succeed
        for accepted, rejected, total in results:
            assert accepted == 2
            assert rejected == 0
            assert total == 2

        # Check cumulative stats
        assert storage.total_accepted == 6
        assert storage.total_rejected == 0


@pytest.mark.asyncio
class TestTimeDelayedStorage:
    """Test time-delayed storage functionality with time manipulation"""

    @pytest.fixture
    def mock_engine(self):
        """Create mock database engine"""
        engine = MagicMock()
        return engine

    @pytest.fixture
    def storage(self, mock_engine):
        """Create IntegratedOHLCStorage with short delay for testing"""
        storage = IntegratedOHLCStorage(
            engine=mock_engine,
            storage_delay_minutes=3,  # 3 minute delay for testing
        )
        # Mock the underlying storage
        storage.storage.store_batch = MagicMock(return_value=(0, 0, 0))
        storage.backpressure.should_accept_data = MagicMock(return_value=True)
        storage.backpressure.handle_storage_result = AsyncMock()
        return storage

    def create_ohlc_data(
        self, symbol: str, timestamp: datetime, volume: float, trades: int, close: float
    ):
        """Helper to create OHLC data"""
        from src.services.data_sources.types import OHLCData
        from decimal import Decimal

        return OHLCData(
            symbol=symbol,
            open=Decimal("50000.00"),
            high=Decimal("51000.00"),
            low=Decimal("49500.00"),
            close=Decimal(str(close)),
            vwap=Decimal("50250.00"),
            trades=trades,
            volume=Decimal(str(volume)),
            interval_begin=timestamp,
            interval=15,
        )

    async def test_basic_buffering_and_flushing(self, storage):
        """Test basic buffering and time-delayed flushing"""
        from datetime import datetime, timezone, timedelta

        # Set up time progression
        start_time = datetime(
            2025, 1, 1, 12, 17, 0, tzinfo=timezone.utc
        )  # Start at 12:17
        interval_time = datetime(
            2025, 1, 1, 12, 15, 0, tzinfo=timezone.utc
        )  # Recent interval (2 min ago)

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            # Initially at start_time (interval is very recent, should buffer)
            mock_dt.now.return_value = start_time
            # Make sure datetime.now(timezone.utc) also returns mocked time
            mock_dt.now.side_effect = lambda tz=None: start_time

            # Create initial data for current interval
            ohlc1 = self.create_ohlc_data(
                "BTC/USD", interval_time, volume=100.0, trades=50, close=50000.0
            )

            # Store should buffer this data
            accepted, rejected, total = await storage.store_batch([ohlc1])

            assert accepted == 1
            assert rejected == 0
            assert len(storage.interval_buffer) == 1

            # Verify it's buffered, not stored
            storage.storage.store_batch.assert_not_called()

            # Advance time by 2 minutes (now 12:19, so 12:15 interval is 4 min old, beyond delay)
            new_time = start_time + timedelta(minutes=2)
            mock_dt.now.side_effect = lambda tz=None: new_time

            # Configure storage mock for both flush and immediate storage
            storage.storage.store_batch.return_value = (1, 0, 1)

            # Update same interval with new data (should flush old + store new immediately)
            ohlc2 = self.create_ohlc_data(
                "BTC/USD", interval_time, volume=150.0, trades=75, close=50500.0
            )

            accepted, rejected, total = await storage.store_batch([ohlc2])

            assert accepted == 1  # New data stored immediately
            assert rejected == 0
            assert (
                len(storage.interval_buffer) == 0
            )  # Buffer should be empty after flush

            # Verify that storage was called (for both flush and immediate storage)
            assert storage.storage.store_batch.call_count >= 1

    async def test_multiple_intervals_multiple_updates(self, storage):
        """Test multiple intervals with multiple updates each"""
        from datetime import datetime, timezone, timedelta

        start_time = datetime(
            2025, 1, 1, 12, 17, 0, tzinfo=timezone.utc
        )  # Start at 12:17

        # Create three different 15-minute intervals
        interval1 = datetime(
            2025, 1, 1, 12, 15, 0, tzinfo=timezone.utc
        )  # 2 min ago (recent)
        interval2 = datetime(2025, 1, 1, 12, 30, 0, tzinfo=timezone.utc)  # Future
        interval3 = datetime(2025, 1, 1, 12, 45, 0, tzinfo=timezone.utc)  # Future

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.side_effect = lambda tz=None: start_time

            # === Test interval1 with multiple updates ===

            # First update
            ohlc1_v1 = self.create_ohlc_data(
                "BTC/USD", interval1, volume=100.0, trades=50, close=50000.0
            )
            await storage.store_batch([ohlc1_v1])

            # Second update (should overwrite)
            ohlc1_v2 = self.create_ohlc_data(
                "BTC/USD", interval1, volume=120.0, trades=60, close=50100.0
            )
            await storage.store_batch([ohlc1_v2])

            # Third update (should overwrite again)
            ohlc1_v3 = self.create_ohlc_data(
                "BTC/USD", interval1, volume=150.0, trades=75, close=50200.0
            )
            await storage.store_batch([ohlc1_v3])

            assert len(storage.interval_buffer) == 1
            buffer_data = storage.interval_buffer[("BTC/USD", interval1)]
            assert buffer_data.volume == Decimal("150.0")  # Latest
            assert buffer_data.trades == 75  # Latest
            assert buffer_data.close == Decimal("50200.0")  # Latest

            # === Test interval2 with multiple updates ===

            ohlc2_v1 = self.create_ohlc_data(
                "BTC/USD", interval2, volume=200.0, trades=80, close=51000.0
            )
            await storage.store_batch([ohlc2_v1])

            ohlc2_v2 = self.create_ohlc_data(
                "BTC/USD", interval2, volume=250.0, trades=95, close=51500.0
            )
            await storage.store_batch([ohlc2_v2])

            assert len(storage.interval_buffer) == 2  # Both intervals buffered

            # === Advance time to flush interval1 ===

            # Move to 2 minutes after start (12:17 + 2min = 12:19, so interval1 @ 12:15 is 4min old)
            flush_time = start_time + timedelta(minutes=2)
            mock_dt.now.side_effect = lambda tz=None: flush_time
            storage.storage.store_batch.return_value = (1, 0, 1)

            # Add data for interval3 (should trigger flush)
            ohlc3_v1 = self.create_ohlc_data(
                "BTC/USD", interval3, volume=300.0, trades=100, close=52000.0
            )
            await storage.store_batch([ohlc3_v1])

            # Should have flushed interval1 with final values
            storage.storage.store_batch.assert_called_once()
            flushed_data = storage.storage.store_batch.call_args[0][0]
            assert len(flushed_data) == 1
            assert flushed_data[0].interval_begin == interval1
            assert flushed_data[0].volume == Decimal("150.0")  # Final value
            assert flushed_data[0].trades == 75  # Final value
            assert flushed_data[0].close == Decimal("50200.0")  # Final value

            # Buffer should now have interval2 and interval3
            assert len(storage.interval_buffer) == 2
            assert ("BTC/USD", interval1) not in storage.interval_buffer
            assert ("BTC/USD", interval2) in storage.interval_buffer
            assert ("BTC/USD", interval3) in storage.interval_buffer

    async def test_force_flush_all(self, storage):
        """Test force flushing all buffered intervals"""
        from datetime import datetime, timezone

        start_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.return_value = start_time

            # Create data for multiple intervals
            interval1 = datetime(2025, 1, 1, 12, 15, 0, tzinfo=timezone.utc)
            interval2 = datetime(2025, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
            interval3 = datetime(2025, 1, 1, 12, 45, 0, tzinfo=timezone.utc)

            # Buffer multiple intervals with final updates
            ohlc1 = self.create_ohlc_data(
                "BTC/USD", interval1, volume=100.0, trades=50, close=50000.0
            )
            ohlc2 = self.create_ohlc_data(
                "ETH/USD", interval2, volume=200.0, trades=75, close=3000.0
            )
            ohlc3 = self.create_ohlc_data(
                "SOL/USD", interval3, volume=300.0, trades=100, close=100.0
            )

            await storage.store_batch([ohlc1])
            await storage.store_batch([ohlc2])
            await storage.store_batch([ohlc3])

            assert len(storage.interval_buffer) == 3

            # Configure mock for force flush
            storage.storage.store_batch.return_value = (3, 0, 3)

            # Force flush all
            flushed_count = await storage.force_flush_all()

            assert flushed_count == 3
            assert len(storage.interval_buffer) == 0  # All cleared

            # Should have called store_batch with all 3 intervals
            storage.storage.store_batch.assert_called_once()
            flushed_data = storage.storage.store_batch.call_args[0][0]
            assert len(flushed_data) == 3

            # Verify all symbols are present
            symbols = [data.symbol for data in flushed_data]
            assert "BTC/USD" in symbols
            assert "ETH/USD" in symbols
            assert "SOL/USD" in symbols

    async def test_old_data_bypasses_buffer(self, storage):
        """Test that very old data bypasses buffer and goes directly to storage"""
        from datetime import datetime, timezone

        current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        old_interval = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)  # 1 hour old

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.return_value = current_time

            # Configure storage mock
            storage.storage.store_batch.return_value = (1, 0, 1)

            # Create old data (more than 3 minutes old)
            old_ohlc = self.create_ohlc_data(
                "BTC/USD", old_interval, volume=100.0, trades=50, close=50000.0
            )

            accepted, rejected, total = await storage.store_batch([old_ohlc])

            assert accepted == 1
            assert rejected == 0
            assert len(storage.interval_buffer) == 0  # Should not be buffered

            # Should have called storage immediately
            storage.storage.store_batch.assert_called_once()
            stored_data = storage.storage.store_batch.call_args[0][0]
            assert len(stored_data) == 1
            assert stored_data[0].interval_begin == old_interval

    async def test_mixed_old_and_recent_data(self, storage):
        """Test batch with mix of old and recent data"""
        from datetime import datetime, timezone

        current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        old_interval = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)  # 1 hour old
        recent_interval = current_time  # Very recent

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.return_value = current_time

            # Configure storage mock
            storage.storage.store_batch.return_value = (1, 0, 1)

            # Create mixed data
            old_ohlc = self.create_ohlc_data(
                "BTC/USD", old_interval, volume=100.0, trades=50, close=50000.0
            )
            recent_ohlc = self.create_ohlc_data(
                "ETH/USD", recent_interval, volume=200.0, trades=75, close=3000.0
            )

            accepted, rejected, total = await storage.store_batch(
                [old_ohlc, recent_ohlc]
            )

            assert accepted == 2  # Both processed
            assert rejected == 0
            assert len(storage.interval_buffer) == 1  # Only recent data buffered

            # Old data should have been stored immediately
            storage.storage.store_batch.assert_called_once()
            stored_data = storage.storage.store_batch.call_args[0][0]
            assert len(stored_data) == 1
            assert stored_data[0].symbol == "BTC/USD"
            assert stored_data[0].interval_begin == old_interval

            # Recent data should be buffered
            assert ("ETH/USD", recent_interval) in storage.interval_buffer
            buffered_data = storage.interval_buffer[("ETH/USD", recent_interval)]
            assert buffered_data.symbol == "ETH/USD"

    async def test_comprehensive_stats_with_buffering(self, storage):
        """Test comprehensive statistics include buffering metrics"""
        from datetime import datetime, timezone

        current_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.return_value = current_time

            # Buffer some data
            interval1 = current_time
            interval2 = current_time + timedelta(minutes=15)

            ohlc1 = self.create_ohlc_data(
                "BTC/USD", interval1, volume=100.0, trades=50, close=50000.0
            )
            ohlc2 = self.create_ohlc_data(
                "ETH/USD", interval2, volume=200.0, trades=75, close=3000.0
            )

            await storage.store_batch([ohlc1, ohlc2])

            # Get stats
            stats = storage.get_comprehensive_stats()

            assert stats["integrated"]["total_buffered"] == 2
            assert stats["integrated"]["currently_buffered"] == 2
            assert stats["integrated"]["total_flushed"] == 0

            # Configure flush and advance time
            storage.storage.store_batch.return_value = (1, 0, 1)
            mock_dt.now.return_value = current_time + timedelta(minutes=5)

            # Trigger flush
            new_ohlc = self.create_ohlc_data(
                "SOL/USD",
                current_time + timedelta(minutes=30),
                volume=300.0,
                trades=100,
                close=100.0,
            )
            await storage.store_batch([new_ohlc])

            # Check updated stats
            stats = storage.get_comprehensive_stats()
            assert stats["integrated"]["total_flushed"] == 1
            assert (
                stats["integrated"]["currently_buffered"] == 2
            )  # interval2 + new SOL interval

    async def test_exact_boundary_timing(self, storage):
        """Test edge case: data exactly at 3-minute boundary"""
        from datetime import datetime, timezone

        current_time = datetime(2025, 1, 1, 12, 18, 0, tzinfo=timezone.utc)
        exact_boundary_time = datetime(
            2025, 1, 1, 12, 15, 0, tzinfo=timezone.utc
        )  # Exactly 3 min old

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.side_effect = lambda tz=None: current_time

            # Configure storage mock
            storage.storage.store_batch.return_value = (1, 0, 1)

            # Create data exactly at boundary
            boundary_ohlc = self.create_ohlc_data(
                "BTC/USD", exact_boundary_time, volume=100.0, trades=50, close=50000.0
            )

            accepted, rejected, total = await storage.store_batch([boundary_ohlc])

            # At exact boundary, should go to immediate storage (>= 3 minutes)
            assert accepted == 1
            assert rejected == 0
            assert len(storage.interval_buffer) == 0  # Not buffered

            # Should have called storage immediately
            storage.storage.store_batch.assert_called_once()
            stored_data = storage.storage.store_batch.call_args[0][0]
            assert len(stored_data) == 1
            assert stored_data[0].interval_begin == exact_boundary_time

    async def test_storage_failure_during_flush(self, storage):
        """Test handling of storage failures during flush operations"""
        from datetime import datetime, timezone, timedelta

        start_time = datetime(2025, 1, 1, 12, 17, 0, tzinfo=timezone.utc)
        interval_time = datetime(2025, 1, 1, 12, 15, 0, tzinfo=timezone.utc)

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.side_effect = lambda tz=None: start_time

            # Buffer some data
            ohlc1 = self.create_ohlc_data(
                "BTC/USD", interval_time, volume=100.0, trades=50, close=50000.0
            )
            await storage.store_batch([ohlc1])

            assert len(storage.interval_buffer) == 1

            # Advance time to trigger flush
            flush_time = start_time + timedelta(minutes=2)
            mock_dt.now.side_effect = lambda tz=None: flush_time

            # Configure storage to fail during flush
            storage.storage.store_batch.side_effect = Exception(
                "Database connection lost"
            )

            # Try to store old data (should go through immediate storage path that fails)
            old_interval = datetime(
                2025, 1, 1, 12, 10, 0, tzinfo=timezone.utc
            )  # 9 min old
            new_ohlc = self.create_ohlc_data(
                "ETH/USD", old_interval, volume=200.0, trades=75, close=3000.0
            )

            accepted, rejected, total = await storage.store_batch([new_ohlc])

            # New data should be rejected due to storage failure
            assert accepted == 0
            assert rejected == 1  # Failed during immediate storage
            assert total == 1

            # Old data should still be in buffer (flush failed)
            assert len(storage.interval_buffer) == 1
            assert ("BTC/USD", interval_time) in storage.interval_buffer

            # Backpressure should have been notified of failure
            storage.backpressure.handle_storage_result.assert_called_with(success=False)

    async def test_buffer_key_conflicts(self, storage):
        """Test buffer key handling with same timestamp, different symbols"""
        from datetime import datetime, timezone

        current_time = datetime(2025, 1, 1, 12, 17, 0, tzinfo=timezone.utc)
        shared_interval = datetime(2025, 1, 1, 12, 15, 0, tzinfo=timezone.utc)

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.side_effect = lambda tz=None: current_time

            # Create data for different symbols at same timestamp
            btc_ohlc = self.create_ohlc_data(
                "BTC/USD", shared_interval, volume=100.0, trades=50, close=50000.0
            )
            eth_ohlc = self.create_ohlc_data(
                "ETH/USD", shared_interval, volume=200.0, trades=75, close=3000.0
            )
            sol_ohlc = self.create_ohlc_data(
                "SOL/USD", shared_interval, volume=300.0, trades=100, close=100.0
            )

            # Store all three
            await storage.store_batch([btc_ohlc, eth_ohlc, sol_ohlc])

            # Should have 3 separate buffer entries (different keys)
            assert len(storage.interval_buffer) == 3

            # Each symbol should have its own buffer key
            assert ("BTC/USD", shared_interval) in storage.interval_buffer
            assert ("ETH/USD", shared_interval) in storage.interval_buffer
            assert ("SOL/USD", shared_interval) in storage.interval_buffer

            # Verify values are correct for each symbol
            btc_data = storage.interval_buffer[("BTC/USD", shared_interval)]
            eth_data = storage.interval_buffer[("ETH/USD", shared_interval)]
            sol_data = storage.interval_buffer[("SOL/USD", shared_interval)]

            assert btc_data.close == Decimal("50000.0")
            assert eth_data.close == Decimal("3000.0")
            assert sol_data.close == Decimal("100.0")

            # Update one symbol - should only affect that entry
            btc_ohlc_v2 = self.create_ohlc_data(
                "BTC/USD", shared_interval, volume=150.0, trades=60, close=51000.0
            )
            await storage.store_batch([btc_ohlc_v2])

            # Still 3 entries
            assert len(storage.interval_buffer) == 3

            # BTC updated, others unchanged
            btc_data = storage.interval_buffer[("BTC/USD", shared_interval)]
            eth_data = storage.interval_buffer[("ETH/USD", shared_interval)]

            assert btc_data.close == Decimal("51000.0")  # Updated
            assert btc_data.volume == Decimal("150.0")  # Updated
            assert eth_data.close == Decimal("3000.0")  # Unchanged

    async def test_empty_buffer_operations(self, storage):
        """Test operations when buffer is empty"""
        from datetime import datetime, timezone

        current_time = datetime(2025, 1, 1, 12, 17, 0, tzinfo=timezone.utc)

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.side_effect = lambda tz=None: current_time

            # Test flush with empty buffer
            await storage._flush_old_intervals()

            # Should not call storage
            storage.storage.store_batch.assert_not_called()

            # Test force flush with empty buffer
            flushed_count = await storage.force_flush_all()

            assert flushed_count == 0
            storage.storage.store_batch.assert_not_called()

            # Test store_batch with empty list
            accepted, rejected, total = await storage.store_batch([])

            assert accepted == 0
            assert rejected == 0
            assert total == 0
            assert len(storage.interval_buffer) == 0

    async def test_buffer_overwrite_behavior(self, storage):
        """Test detailed buffer overwrite behavior"""
        from datetime import datetime, timezone

        current_time = datetime(2025, 1, 1, 12, 17, 0, tzinfo=timezone.utc)
        interval_time = datetime(2025, 1, 1, 12, 15, 0, tzinfo=timezone.utc)

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.side_effect = lambda tz=None: current_time

            # Store initial data
            ohlc1 = self.create_ohlc_data(
                "BTC/USD", interval_time, volume=100.0, trades=50, close=50000.0
            )
            accepted1, rejected1, total1 = await storage.store_batch([ohlc1])

            assert accepted1 == 1
            assert len(storage.interval_buffer) == 1

            # Store update (should overwrite)
            ohlc2 = self.create_ohlc_data(
                "BTC/USD", interval_time, volume=200.0, trades=100, close=51000.0
            )
            accepted2, rejected2, total2 = await storage.store_batch([ohlc2])

            assert accepted2 == 1  # Still counts as accepted
            assert len(storage.interval_buffer) == 1  # Still only one entry

            # Verify overwrite worked
            buffer_key = ("BTC/USD", interval_time)
            buffered_data = storage.interval_buffer[buffer_key]
            assert buffered_data.volume == Decimal("200.0")  # Latest value
            assert buffered_data.trades == 100  # Latest value
            assert buffered_data.close == Decimal("51000.0")  # Latest value

            # Statistics should count both as buffered
            stats = storage.get_comprehensive_stats()
            assert stats["integrated"]["total_buffered"] == 2  # Both operations counted
            assert (
                stats["integrated"]["currently_buffered"] == 1
            )  # But only one entry in buffer

    async def test_flush_partial_failure(self, storage):
        """Test partial failure during flush (some intervals succeed, some fail)"""
        from datetime import datetime, timezone

        start_time = datetime(2025, 1, 1, 12, 20, 0, tzinfo=timezone.utc)

        with patch("src.services.data_sources.storage.datetime") as mock_dt:
            mock_dt.now.side_effect = lambda tz=None: start_time

            # Buffer multiple old intervals
            interval1 = datetime(
                2025, 1, 1, 12, 15, 0, tzinfo=timezone.utc
            )  # 5 min old
            interval2 = datetime(
                2025, 1, 1, 12, 16, 0, tzinfo=timezone.utc
            )  # 4 min old

            ohlc1 = self.create_ohlc_data(
                "BTC/USD", interval1, volume=100.0, trades=50, close=50000.0
            )
            ohlc2 = self.create_ohlc_data(
                "ETH/USD", interval2, volume=200.0, trades=75, close=3000.0
            )

            # First buffer them when they're recent
            old_time = datetime(2025, 1, 1, 12, 17, 0, tzinfo=timezone.utc)
            mock_dt.now.side_effect = lambda tz=None: old_time

            await storage.store_batch([ohlc1, ohlc2])
            assert len(storage.interval_buffer) == 2

            # Now advance time and simulate partial storage failure
            mock_dt.now.side_effect = lambda tz=None: start_time

            # Configure storage to partially succeed (1 success, 1 failure)
            storage.storage.store_batch.return_value = (1, 1, 2)

            # Trigger flush with new data
            new_ohlc = self.create_ohlc_data(
                "SOL/USD",
                datetime(2025, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
                volume=300.0,
                trades=100,
                close=100.0,
            )
            accepted, rejected, total = await storage.store_batch([new_ohlc])

            # Should have attempted to flush old intervals
            storage.storage.store_batch.assert_called()

            # Backpressure should be notified of failure (partial failure = failure)
            storage.backpressure.handle_storage_result.assert_called_with(success=False)
