"""
Integrated storage with backpressure control.
Combines efficient bulk storage with infrastructure health monitoring.
"""

from typing import List, Tuple, Optional, Callable
from loguru import logger
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .backpressure import SimpleBackpressureController
from .types import OHLCData
from .transformer import KrakenToTimescaleTransformer


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
            'total_stored': self.total_stored,
            'total_failed': self.total_failed,
            'success_rate': self.total_stored / max(self.total_stored + self.total_failed, 1)
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
    Storage layer with integrated backpressure control.

    Combines:
    - Efficient bulk storage (psycopg2 execute_values)
    - Duplicate detection and dropping
    - Storage health monitoring
    - Automatic pause/resume of ingestion
    - Fail-fast on unrecoverable storage issues
    """

    def __init__(
        self,
        engine: Engine,
        pause_callback: Optional[Callable] = None,
        resume_callback: Optional[Callable] = None,
        max_batch_size: int = 1000
    ):
        """
        Initialize integrated storage

        Args:
            engine: SQLAlchemy database engine
            pause_callback: Function to call when pausing ingestion
            resume_callback: Function to call when resuming ingestion
            max_batch_size: Maximum records per batch for bulk storage
        """
        # Core storage
        self.storage = OHLCStorage(engine, max_batch_size)

        # Backpressure controller
        self.backpressure = SimpleBackpressureController(
            pause_callback=pause_callback,
            resume_callback=resume_callback
        )

        # Combined stats
        self.total_accepted = 0
        self.total_rejected = 0

    async def store_batch(self, ohlc_data_list: List[OHLCData]) -> Tuple[int, int, int]:
        """
        Store batch with backpressure control

        Args:
            ohlc_data_list: List of OHLC data to store

        Returns:
            Tuple of (accepted, rejected, total_input)
        """
        if not ohlc_data_list:
            return 0, 0, 0

        # Filter out duplicates
        accepted_data = []
        rejected_count = 0

        for ohlc in ohlc_data_list:
            if self.backpressure.should_accept_data(ohlc):
                accepted_data.append(ohlc)
                self.total_accepted += 1
            else:
                rejected_count += 1
                self.total_rejected += 1

        if not accepted_data:
            logger.debug(f"All {len(ohlc_data_list)} records rejected (duplicates)")
            return 0, rejected_count, len(ohlc_data_list)

        # Attempt to store accepted data
        try:
            success_count, failed_count, processed_count = self.storage.store_batch(accepted_data)

            # Report success to backpressure controller
            await self.backpressure.handle_storage_result(success=(failed_count == 0))

            return success_count, rejected_count + failed_count, len(ohlc_data_list)

        except Exception as e:
            logger.error(f"Storage batch failed: {e}")

            # Report failure to backpressure controller
            await self.backpressure.handle_storage_result(success=False)

            return 0, len(ohlc_data_list), len(ohlc_data_list)

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
            'integrated': {
                'total_accepted': self.total_accepted,
                'total_rejected': self.total_rejected,
                'acceptance_rate': self.total_accepted / max(self.total_accepted + self.total_rejected, 1)
            },
            'storage': storage_stats,
            'backpressure': backpressure_stats
        }

    def log_comprehensive_stats(self) -> None:
        """Log statistics from all components"""
        logger.info(
            f"Integrated Storage - Accepted: {self.total_accepted}, "
            f"Rejected: {self.total_rejected}, "
            f"Rate: {(self.total_accepted / max(self.total_accepted + self.total_rejected, 1) * 100):.1f}%"
        )

        self.storage.log_stats()
        self.backpressure.log_stats()

    def reset_stats(self) -> None:
        """Reset all statistics"""
        self.total_accepted = 0
        self.total_rejected = 0
        self.storage.reset_stats()
        # Note: Backpressure controller stats track health, so we don't reset those

    def is_healthy(self) -> bool:
        """Check if storage system is healthy"""
        backpressure_stats = self.backpressure.get_stats()
        return backpressure_stats['health']['healthy']

    def is_paused(self) -> bool:
        """Check if ingestion is currently paused"""
        return self.backpressure.is_paused