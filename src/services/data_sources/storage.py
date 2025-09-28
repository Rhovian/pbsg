"""
Integrated storage with backpressure control.
Combines efficient bulk storage with infrastructure health monitoring.
"""

from typing import List, Tuple, Optional, Callable, Dict
from datetime import datetime, timezone, timedelta
from loguru import logger
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .backpressure import SimpleBackpressureController
from .types import OHLCData
from .kraken.transformer import KrakenToTimescaleTransformer


class OHLCStorage:
    """Basic OHLC storage using SQLAlchemy bulk operations"""

    def __init__(self, engine: Engine, max_batch_size: int = 1000):
        self.engine = engine
        self.max_batch_size = max_batch_size
        self.total_stored = 0
        self.total_failed = 0

    def store_batch(self, ohlc_data_list: List[OHLCData]) -> Tuple[int, int, int]:
        """
        Store batch of OHLC data

        Returns:
            Tuple of (success_count, failed_count, processed_count)
        """
        if not ohlc_data_list:
            return 0, 0, 0

        success_count = 0
        failed_count = 0

        with Session(self.engine) as session:
            try:
                for ohlc in ohlc_data_list:
                    try:
                        model = KrakenToTimescaleTransformer.transform(ohlc)
                        if model:
                            session.add(model)
                            success_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Error transforming OHLC data: {e}")
                        failed_count += 1

                session.commit()
                self.total_stored += success_count
                self.total_failed += failed_count

            except Exception as e:
                logger.error(f"Database error in store_batch: {e}")
                session.rollback()
                failed_count = len(ohlc_data_list)
                success_count = 0
                self.total_failed += failed_count

        return success_count, failed_count, len(ohlc_data_list)

    def get_stats(self) -> dict:
        """Get storage statistics"""
        return {
            "total_stored": self.total_stored,
            "total_failed": self.total_failed,
            "success_rate": self.total_stored
            / max(self.total_stored + self.total_failed, 1),
        }

    def log_stats(self) -> None:
        """Log storage statistics"""
        stats = self.get_stats()
        logger.info(
            f"Storage Stats - Stored: {stats['total_stored']}, "
            f"Failed: {stats['total_failed']}, "
            f"Success Rate: {stats['success_rate']:.1%}"
        )

    def reset_stats(self) -> None:
        """Reset storage statistics"""
        self.total_stored = 0
        self.total_failed = 0


class IntegratedOHLCStorage:
    """
    Storage layer with integrated backpressure control and time-delayed storage.

    Combines:
    - Time-delayed storage (buffers incomplete intervals in memory)
    - Efficient bulk storage (psycopg2 execute_values)
    - Duplicate detection and overwriting (latest wins)
    - Storage health monitoring
    - Automatic pause/resume of ingestion
    - Fail-fast on unrecoverable storage issues
    """

    def __init__(
        self,
        engine: Engine,
        pause_callback: Optional[Callable] = None,
        resume_callback: Optional[Callable] = None,
        max_batch_size: int = 1000,
        storage_delay_minutes: int = 3,
    ):
        """
        Initialize integrated storage

        Args:
            engine: SQLAlchemy database engine
            pause_callback: Function to call when pausing ingestion
            resume_callback: Function to call when resuming ingestion
            max_batch_size: Maximum records per batch for bulk storage
            storage_delay_minutes: Minutes to wait before storing completed intervals
        """
        # Core storage
        self.storage = OHLCStorage(engine, max_batch_size)

        # Backpressure controller
        self.backpressure = SimpleBackpressureController(
            pause_callback=pause_callback, resume_callback=resume_callback
        )

        # Time-delayed storage
        self.storage_delay = timedelta(minutes=storage_delay_minutes)
        self.interval_buffer: Dict[
            Tuple[str, datetime], OHLCData
        ] = {}  # (symbol, timestamp) -> latest_data

        # Combined stats
        self.total_accepted = 0
        self.total_rejected = 0
        self.total_buffered = 0
        self.total_flushed = 0

    async def store_batch(self, ohlc_data_list: List[OHLCData]) -> Tuple[int, int, int]:
        """
        Store batch with time-delayed storage and backpressure control

        Args:
            ohlc_data_list: List of OHLC data to store

        Returns:
            Tuple of (stored_or_buffered, rejected, total_input)
        """
        if not ohlc_data_list:
            return 0, 0, 0

        # Flush old intervals to database first
        await self._flush_old_intervals()

        now = datetime.now(timezone.utc)
        immediate_store = []  # Old intervals to store immediately
        buffered_count = 0
        rejected_count = 0

        for ohlc in ohlc_data_list:
            buffer_key = (ohlc.symbol, ohlc.interval_begin)
            time_since_interval = now - ohlc.interval_begin

            # Determine if interval is recent (buffer) or old (store immediately)
            if time_since_interval < self.storage_delay:
                # Recent interval - store in buffer (overwrite existing)
                self.interval_buffer[buffer_key] = ohlc
                buffered_count += 1
                self.total_buffered += 1
                self.total_accepted += 1
                logger.debug(f"Buffered: {ohlc.symbol} @ {ohlc.interval_begin}")
            else:
                # Old interval - check backpressure and store immediately
                if self.backpressure.should_accept_data(ohlc):
                    immediate_store.append(ohlc)
                    self.total_accepted += 1
                else:
                    rejected_count += 1
                    self.total_rejected += 1

        # Store old intervals immediately
        stored_count = 0
        storage_failed = False
        if immediate_store:
            try:
                success_count, failed_count, _ = self.storage.store_batch(
                    immediate_store
                )
                stored_count = success_count
                rejected_count += failed_count
                await self.backpressure.handle_storage_result(
                    success=(failed_count == 0)
                )
            except Exception as e:
                logger.error(f"Immediate storage failed: {e}")
                rejected_count += len(immediate_store)
                storage_failed = True
                await self.backpressure.handle_storage_result(success=False)

        # If storage infrastructure failed, don't count buffered items as processed
        if storage_failed:
            # Storage failed completely - return buffered items back to rejected
            rejected_count += buffered_count
            # Don't count buffered items since we can't trust the storage system
            total_processed = 0
        else:
            total_processed = stored_count + buffered_count

        return total_processed, rejected_count, len(ohlc_data_list)

    async def _flush_old_intervals(self) -> None:
        """Flush buffered intervals that are older than storage delay"""
        if not self.interval_buffer:
            return

        now = datetime.now(timezone.utc)
        intervals_to_flush = []
        keys_to_remove = []

        # Find intervals ready for storage
        for buffer_key, ohlc_data in self.interval_buffer.items():
            time_since_interval = now - ohlc_data.interval_begin
            if time_since_interval >= self.storage_delay:
                intervals_to_flush.append(ohlc_data)
                keys_to_remove.append(buffer_key)

        # Store old intervals to database
        if intervals_to_flush:
            try:
                success_count, failed_count, _ = self.storage.store_batch(
                    intervals_to_flush
                )
                self.total_flushed += success_count

                logger.debug(f"Flushed {success_count} intervals to database")

                # Remove successfully stored intervals from buffer
                for key in keys_to_remove:
                    del self.interval_buffer[key]

                await self.backpressure.handle_storage_result(
                    success=(failed_count == 0)
                )

            except Exception as e:
                logger.error(f"Failed to flush intervals: {e}")
                # Don't remove items from buffer since storage failed
                await self.backpressure.handle_storage_result(success=False)

    async def force_flush_all(self) -> int:
        """Force flush all buffered intervals to database (for shutdown/testing)"""
        if not self.interval_buffer:
            return 0

        intervals_to_flush = list(self.interval_buffer.values())
        keys_to_remove = list(self.interval_buffer.keys())

        try:
            success_count, failed_count, _ = self.storage.store_batch(
                intervals_to_flush
            )
            self.total_flushed += success_count

            logger.info(f"Force flushed {success_count} intervals to database")

            # Clear the buffer only if storage succeeded
            for key in keys_to_remove:
                del self.interval_buffer[key]

            await self.backpressure.handle_storage_result(success=(failed_count == 0))
            return success_count

        except Exception as e:
            logger.error(f"Failed to force flush intervals: {e}")
            # Don't clear buffer since storage failed
            await self.backpressure.handle_storage_result(success=False)
            return 0

    async def store_single(self, ohlc_data: OHLCData) -> bool:
        """
        Store single record with backpressure control

        Args:
            ohlc_data: Single OHLC data record

        Returns:
            True if successfully stored, False otherwise
        """
        success_count, _, _ = await self.store_batch([ohlc_data])
        return success_count > 0

    def get_comprehensive_stats(self) -> dict:
        """Get comprehensive statistics from all components"""
        storage_stats = self.storage.get_stats()
        backpressure_stats = self.backpressure.get_stats()

        return {
            "integrated": {
                "total_accepted": self.total_accepted,
                "total_rejected": self.total_rejected,
                "total_buffered": self.total_buffered,
                "total_flushed": self.total_flushed,
                "currently_buffered": len(self.interval_buffer),
                "acceptance_rate": self.total_accepted
                / max(self.total_accepted + self.total_rejected, 1),
            },
            "storage": storage_stats,
            "backpressure": backpressure_stats,
        }

    def log_comprehensive_stats(self) -> None:
        """Log statistics from all components"""
        logger.info(
            f"Integrated Storage - Accepted: {self.total_accepted}, "
            f"Rejected: {self.total_rejected}, "
            f"Buffered: {self.total_buffered}, "
            f"Flushed: {self.total_flushed}, "
            f"Currently Buffered: {len(self.interval_buffer)}, "
            f"Rate: {(self.total_accepted / max(self.total_accepted + self.total_rejected, 1) * 100):.1f}%"
        )

        self.storage.log_stats()
        self.backpressure.log_stats()

    def reset_stats(self) -> None:
        """Reset all statistics (but keep buffered intervals)"""
        self.total_accepted = 0
        self.total_rejected = 0
        self.total_buffered = 0
        self.total_flushed = 0
        self.storage.reset_stats()
        # Note: Backpressure controller stats track health, so we don't reset those
        # Note: interval_buffer is preserved as it contains real data

    def is_healthy(self) -> bool:
        """Check if storage system is healthy"""
        backpressure_stats = self.backpressure.get_stats()
        return backpressure_stats["health"]["healthy"]

    def is_paused(self) -> bool:
        """Check if ingestion is currently paused"""
        return self.backpressure.is_paused
