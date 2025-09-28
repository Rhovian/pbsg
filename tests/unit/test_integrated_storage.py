"""
Unit tests for IntegratedOHLCStorage
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from decimal import Decimal

from src.services.data_sources.integrated_storage import IntegratedOHLCStorage
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
                interval=15
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
                interval=15
            )
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
            max_batch_size=100
        )

    def test_initialization(self, mock_engine):
        """Test storage initialization"""
        pause_cb = MagicMock()
        resume_cb = MagicMock()

        storage = IntegratedOHLCStorage(
            engine=mock_engine,
            pause_callback=pause_cb,
            resume_callback=resume_cb,
            max_batch_size=500
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
        storage.backpressure.should_accept_data = MagicMock(
            side_effect=[False, True]
        )
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
        storage.backpressure.handle_storage_result.assert_called_once_with(success=False)

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
        storage.backpressure.handle_storage_result.assert_called_once_with(success=False)

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
            interval=15
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
            interval=15
        )

        storage.backpressure.should_accept_data = MagicMock(return_value=False)

        result = await storage.store_single(ohlc)

        assert result is False
        assert storage.total_rejected == 1

    def test_get_comprehensive_stats(self, storage):
        """Test getting comprehensive statistics"""
        storage.total_accepted = 100
        storage.total_rejected = 10

        storage.storage.get_stats = MagicMock(return_value={
            "total_stored": 100,
            "total_failed": 10
        })

        storage.backpressure.get_stats = MagicMock(return_value={
            "health": {"healthy": True},
            "failures": 1
        })

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
        storage.backpressure.get_stats = MagicMock(return_value={
            "health": {"healthy": True}
        })

        assert storage.is_healthy() is True

        storage.backpressure.get_stats = MagicMock(return_value={
            "health": {"healthy": False}
        })

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
            storage.store_batch(sample_ohlc_data)
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