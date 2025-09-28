"""
Simple backpressure control for low-volume OHLC data streams.
Focused on infrastructure health rather than complex data prioritization.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from typing import Set, Tuple
from collections import deque
from loguru import logger

from .types import OHLCData


class DuplicateDetector:
    """Simple in-memory cache to detect duplicate OHLC records"""

    def __init__(self, cache_size: int = 1000):
        self.cache: Set[Tuple[str, datetime, str]] = set()
        self.cache_order = deque(maxlen=cache_size)

    def is_duplicate(self, ohlc: OHLCData) -> bool:
        """Check if we've already seen this exact record"""
        key = (ohlc.symbol, ohlc.interval_begin, "15m")
        return key in self.cache

    def mark_seen(self, ohlc: OHLCData) -> None:
        """Mark this record as seen"""
        key = (ohlc.symbol, ohlc.interval_begin, "15m")

        # Remove oldest if cache is full
        if len(self.cache_order) == self.cache_order.maxlen and self.cache_order:
            oldest = self.cache_order[0]
            self.cache.discard(oldest)

        self.cache.add(key)
        self.cache_order.append(key)


class StorageHealthMonitor:
    """Monitor storage health and implement circuit breaker pattern"""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # 5 minutes
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        self.is_healthy = True

    def record_success(self) -> None:
        """Record successful storage operation"""
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        if not self.is_healthy:
            logger.info("Storage health restored")
            self.is_healthy = True

    def record_failure(self) -> None:
        """Record storage failure and check if circuit should open"""
        self.consecutive_failures += 1

        if self.consecutive_failures >= self.failure_threshold:
            self.is_healthy = False
            logger.error(
                f"Storage unhealthy: {self.consecutive_failures} consecutive failures"
            )

    def should_fail_fast(self) -> bool:
        """Check if we should give up and exit"""
        if not self.is_healthy:
            time_since_last_success = datetime.now() - self.last_success
            if time_since_last_success.total_seconds() > self.recovery_timeout:
                return True
        return False

    def get_status(self) -> dict:
        """Get current health status"""
        return {
            "healthy": self.is_healthy,
            "consecutive_failures": self.consecutive_failures,
            "time_since_last_success": (
                datetime.now() - self.last_success
            ).total_seconds(),
        }


class SimpleBackpressureController:
    """
    Simple backpressure controller for 15-minute OHLC data.

    Focus: Infrastructure health, not complex data management.
    Reality: 12 records/hour shouldn't need sophisticated backpressure.
    """

    def __init__(self, pause_callback=None, resume_callback=None):
        self.duplicate_detector = DuplicateDetector()
        self.health_monitor = StorageHealthMonitor()
        self.pause_callback = pause_callback
        self.resume_callback = resume_callback
        self.is_paused = False

        # Stats
        self.stats = {
            "duplicates_dropped": 0,
            "storage_failures": 0,
            "pause_events": 0,
            "total_processed": 0,
        }

    def should_accept_data(self, ohlc: OHLCData) -> bool:
        """
        Simple decision: accept data unless it's a duplicate

        Returns False only for duplicates - we don't drop real data
        """
        self.stats["total_processed"] += 1

        if self.duplicate_detector.is_duplicate(ohlc):
            self.stats["duplicates_dropped"] += 1
            logger.debug(f"Dropping duplicate: {ohlc.symbol} @ {ohlc.interval_begin}")
            return False

        # Mark as seen for future duplicate detection
        self.duplicate_detector.mark_seen(ohlc)
        return True

    async def handle_storage_result(self, success: bool) -> None:
        """
        Handle storage operation result and manage system health
        """
        if success:
            self.health_monitor.record_success()

            # Resume if we were paused
            if self.is_paused:
                await self._resume_ingestion()

        else:
            self.stats["storage_failures"] += 1
            self.health_monitor.record_failure()

            # Check if we should pause or fail
            if not self.health_monitor.is_healthy and not self.is_paused:
                await self._pause_ingestion()

            # Check if we should give up entirely
            if self.health_monitor.should_fail_fast():
                await self._fail_fast()

    async def _pause_ingestion(self) -> None:
        """Pause data ingestion due to storage issues"""
        if self.is_paused:
            return

        self.is_paused = True
        self.stats["pause_events"] += 1

        logger.warning("Pausing data ingestion - storage health degraded")

        if self.pause_callback:
            try:
                await self.pause_callback()
            except Exception as e:
                logger.error(f"Error in pause callback: {e}")

    async def _resume_ingestion(self) -> None:
        """Resume data ingestion after storage recovery"""
        if not self.is_paused:
            return

        self.is_paused = False
        logger.info("Resuming data ingestion - storage health restored")

        if self.resume_callback:
            try:
                await self.resume_callback()
            except Exception as e:
                logger.error(f"Error in resume callback: {e}")

    async def _fail_fast(self) -> None:
        """Give up and exit the system - storage is unrecoverable"""
        status = self.health_monitor.get_status()

        logger.critical(
            f"Storage unrecoverable after {status['time_since_last_success']:.0f}s "
            f"({status['consecutive_failures']} failures). Shutting down system."
        )

        # Log final stats
        self.log_stats()

        # Exit cleanly
        sys.exit(1)

    def log_stats(self) -> None:
        """Log backpressure statistics"""
        health_status = self.health_monitor.get_status()

        logger.info(
            f"Backpressure Stats - "
            f"Processed: {self.stats['total_processed']}, "
            f"Duplicates: {self.stats['duplicates_dropped']}, "
            f"Storage Failures: {self.stats['storage_failures']}, "
            f"Pauses: {self.stats['pause_events']}, "
            f"Health: {'OK' if health_status['healthy'] else 'DEGRADED'}"
        )

    def get_stats(self) -> dict:
        """Get current statistics"""
        return {
            **self.stats,
            "health": self.health_monitor.get_status(),
            "is_paused": self.is_paused,
        }
