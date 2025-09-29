#!/usr/bin/env python3
"""
Core Kraken Backfill Tool - moved from kraken_backfill.py
"""

import asyncio
import sys
import time
import argparse
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import traceback

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.services.data_sources.kraken.backfill import KrakenBackfillClient
from src.services.data_sources.storage import IntegratedOHLCStorage
from src.services.data_sources.types import OHLCData
from scripts.python.data_integrity_check import DataIntegrityChecker, DataGap


class BackfillMetrics:
    """Track comprehensive backfill metrics"""

    def __init__(self):
        self.start_time = time.time()
        self.total_records_fetched = 0
        self.total_records_stored = 0
        self.total_api_calls = 0
        self.failed_api_calls = 0
        self.symbols_completed = 0
        self.symbols_failed = 0
        self.chunks_processed = 0
        self.chunks_failed = 0
        self.total_bytes_transferred = 0
        self.rate_limit_delays = 0
        self.error_delays = 0
        self.last_successful_timestamp = None

        # Per-symbol metrics
        self.symbol_metrics = {}

    def add_symbol_metrics(
        self, symbol: str, records_fetched: int, records_stored: int, api_calls: int
    ):
        """Add metrics for a specific symbol"""
        if symbol not in self.symbol_metrics:
            self.symbol_metrics[symbol] = {
                "records_fetched": 0,
                "records_stored": 0,
                "api_calls": 0,
                "chunks": 0,
            }

        self.symbol_metrics[symbol]["records_fetched"] += records_fetched
        self.symbol_metrics[symbol]["records_stored"] += records_stored
        self.symbol_metrics[symbol]["api_calls"] += api_calls
        self.symbol_metrics[symbol]["chunks"] += 1

    def get_duration(self) -> float:
        """Get elapsed time in seconds"""
        return time.time() - self.start_time

    def get_rate_metrics(self) -> Dict[str, float]:
        """Calculate rate metrics"""
        duration = self.get_duration()
        return {
            "records_per_second": self.total_records_fetched / duration
            if duration > 0
            else 0,
            "api_calls_per_second": self.total_api_calls / duration
            if duration > 0
            else 0,
            "storage_rate": self.total_records_stored / duration if duration > 0 else 0,
        }


class KrakenBackfillTool:
    """Production tool for backfilling Kraken historical data"""

    def __init__(self, config: Dict):
        self.config = config
        self.client = KrakenBackfillClient(timeout=config.get("request_timeout", 30.0))
        self.metrics = BackfillMetrics()
        self.running = True

        # Database setup
        db_url = config.get(
            "database_url", "postgresql://pbsg:pbsg_password@localhost:5432/pbsg"
        )
        self.engine = create_engine(db_url)
        self.storage = IntegratedOHLCStorage(
            self.engine, max_batch_size=config.get("batch_size", 100)
        )

        # Backoff configuration
        self.base_delay = config.get("base_delay", 1.0)
        self.max_delay = config.get("max_delay", 60.0)
        self.backoff_multiplier = config.get("backoff_multiplier", 2.0)
        self.max_retries = config.get("max_retries", 5)

        # Chunking configuration
        self.chunk_size_hours = config.get(
            "chunk_size_hours", 24
        )  # Process 1 day at a time
        self.max_records_per_request = config.get(
            "max_records_per_request", 720
        )  # Kraken's limit

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Configure comprehensive logging"""
        log_level = self.config.get("log_level", "INFO")
        log_file = self.config.get("log_file")

        # Remove default logger
        logger.remove()

        # Console logging
        logger.add(
            sys.stdout,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )

        # File logging if specified
        if log_file:
            logger.add(
                log_file,
                level=log_level,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                rotation="100 MB",
                retention="30 days",
            )

    async def exponential_backoff(
        self, attempt: int, base_delay: Optional[float] = None
    ) -> None:
        """Implement exponential backoff with jitter"""
        if base_delay is None:
            base_delay = self.base_delay

        delay = min(base_delay * (self.backoff_multiplier**attempt), self.max_delay)

        # Add jitter (±20%)
        import random

        jitter = delay * 0.2 * (random.random() - 0.5)
        delay += jitter

        logger.warning(f"Backing off for {delay:.2f} seconds (attempt {attempt + 1})")
        await asyncio.sleep(delay)
        self.metrics.error_delays += 1

    async def fetch_chunk_with_retry(
        self, symbol: str, since_timestamp: int, chunk_end: Optional[int] = None
    ) -> Tuple[List[OHLCData], bool]:
        """Fetch a chunk of data with retry logic"""

        for attempt in range(self.max_retries):
            try:
                self.metrics.total_api_calls += 1
                logger.debug(
                    f"Fetching {symbol} since {since_timestamp} (attempt {attempt + 1})"
                )

                data = await self.client.get_ohlc_data(
                    symbol=symbol,
                    since=since_timestamp,
                    limit=self.max_records_per_request,
                )

                # Filter data to chunk boundaries if specified
                if chunk_end and data:
                    data = [
                        d
                        for d in data
                        if int(d.interval_begin.timestamp()) <= chunk_end
                    ]

                self.metrics.total_records_fetched += len(data)
                logger.info(f"✅ Fetched {len(data)} records for {symbol}")

                return data, True

            except Exception as e:
                self.metrics.failed_api_calls += 1
                logger.warning(
                    f"❌ API call failed for {symbol} (attempt {attempt + 1}): {e}"
                )

                if attempt < self.max_retries - 1:
                    # Check if it's a rate limit error
                    if "rate limit" in str(e).lower() or "429" in str(e):
                        logger.warning("Rate limit detected, using longer backoff")
                        await self.exponential_backoff(attempt, base_delay=5.0)
                        self.metrics.rate_limit_delays += 1
                    else:
                        await self.exponential_backoff(attempt)
                else:
                    logger.error(
                        f"❌ Max retries exceeded for {symbol} since {since_timestamp}"
                    )
                    return [], False

        return [], False

    async def store_data_with_retry(self, data: List[OHLCData]) -> Tuple[int, int]:
        """Store data with retry logic"""
        for attempt in range(self.max_retries):
            try:
                (
                    success_count,
                    failed_count,
                    total_count,
                ) = await self.storage.store_batch(data)
                self.metrics.total_records_stored += success_count

                if failed_count > 0:
                    logger.warning(
                        f"⚠️ {failed_count}/{total_count} records failed to store"
                    )

                return success_count, failed_count

            except Exception as e:
                logger.warning(f"❌ Storage failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await self.exponential_backoff(attempt)
                else:
                    logger.error("❌ Max retries exceeded for storage")
                    raise

        return 0, len(data)

    async def backfill_symbol_range(
        self, symbol: str, start_timestamp: int, end_timestamp: int
    ) -> bool:
        """Backfill a specific symbol for a date range using chunked processing"""

        logger.info(f"🚀 Starting backfill for {symbol}")
        logger.info(
            f"   Range: {datetime.fromtimestamp(start_timestamp, tz=timezone.utc)} to {datetime.fromtimestamp(end_timestamp, tz=timezone.utc)}"
        )

        symbol_start_time = time.time()
        symbol_records_fetched = 0
        symbol_records_stored = 0
        symbol_api_calls = 0

        current_timestamp = start_timestamp
        chunk_size_seconds = self.chunk_size_hours * 3600

        while current_timestamp < end_timestamp and self.running:
            chunk_end = min(current_timestamp + chunk_size_seconds, end_timestamp)

            chunk_start_time = datetime.fromtimestamp(
                current_timestamp, tz=timezone.utc
            )
            chunk_end_time = datetime.fromtimestamp(chunk_end, tz=timezone.utc)

            logger.info(f"📦 Processing chunk: {chunk_start_time} to {chunk_end_time}")

            try:
                # Fetch data for this chunk
                data, success = await self.fetch_chunk_with_retry(
                    symbol, current_timestamp, chunk_end
                )
                symbol_api_calls += 1

                if not success:
                    logger.error(f"❌ Failed to fetch chunk for {symbol}")
                    self.metrics.chunks_failed += 1
                    return False

                if not data:
                    logger.info("📭 No data in chunk, moving to next")
                    current_timestamp = chunk_end + 1
                    continue

                symbol_records_fetched += len(data)

                # Store the data
                if data:
                    success_count, failed_count = await self.store_data_with_retry(data)
                    symbol_records_stored += success_count

                    logger.info(f"💾 Stored {success_count}/{len(data)} records")

                    # Update last successful timestamp
                    if data:
                        self.metrics.last_successful_timestamp = int(
                            data[-1].interval_begin.timestamp()
                        )

                self.metrics.chunks_processed += 1

                # Move to next chunk
                if data:
                    # Use the last data point timestamp + 1 to avoid gaps
                    last_timestamp = int(data[-1].interval_begin.timestamp())
                    current_timestamp = last_timestamp + 900  # 15 minutes in seconds
                else:
                    current_timestamp = chunk_end + 1

                # Progress logging
                progress = (
                    (current_timestamp - start_timestamp)
                    / (end_timestamp - start_timestamp)
                    * 100
                )
                logger.info(f"📊 Progress for {symbol}: {progress:.1f}%")

            except Exception as e:
                logger.error(f"❌ Chunk processing failed for {symbol}: {e}")
                logger.error(traceback.format_exc())
                self.metrics.chunks_failed += 1
                return False

        # Symbol completion metrics
        symbol_duration = time.time() - symbol_start_time

        self.metrics.add_symbol_metrics(
            symbol, symbol_records_fetched, symbol_records_stored, symbol_api_calls
        )
        self.metrics.symbols_completed += 1

        logger.success(f"✅ Completed {symbol} in {symbol_duration:.1f}s")
        logger.info(f"   📊 Fetched: {symbol_records_fetched} records")
        logger.info(f"   💾 Stored: {symbol_records_stored} records")
        logger.info(f"   🔗 API calls: {symbol_api_calls}")

        return True

    async def run_backfill(
        self, symbols: List[str], start_date: datetime, end_date: datetime
    ) -> bool:
        """Run the complete backfill process"""

        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())

        logger.info("🚀 Starting Kraken Historical Data Backfill")
        logger.info(f"📅 Date Range: {start_date} to {end_date}")
        logger.info(f"💱 Symbols: {', '.join(symbols)}")
        logger.info(
            f"⚙️ Config: {self.chunk_size_hours}h chunks, {self.max_records_per_request} records/request"
        )

        overall_success = True

        for symbol in symbols:
            if not self.running:
                logger.warning("🛑 Backfill interrupted")
                break

            try:
                success = await self.backfill_symbol_range(
                    symbol, start_timestamp, end_timestamp
                )
                if not success:
                    overall_success = False
                    self.metrics.symbols_failed += 1
                    logger.error(f"❌ Failed to complete backfill for {symbol}")

            except Exception as e:
                overall_success = False
                self.metrics.symbols_failed += 1
                logger.error(f"❌ Exception during {symbol} backfill: {e}")
                logger.error(traceback.format_exc())

        # Final flush
        try:
            logger.info("🔄 Flushing remaining buffered data...")
            flushed_count = await self.storage.force_flush_all()
            if flushed_count > 0:
                logger.info(f"💾 Flushed {flushed_count} additional records")
        except Exception as e:
            logger.error(f"❌ Error during final flush: {e}")

        return overall_success

    def print_final_metrics(self, success: bool):
        """Print comprehensive final metrics"""
        duration = self.metrics.get_duration()
        rates = self.metrics.get_rate_metrics()

        logger.info("\n" + "=" * 80)
        logger.info("📊 KRAKEN BACKFILL METRICS")
        logger.info("=" * 80)

        # Overall metrics
        logger.info(
            f"⏱️  Duration:              {duration:.1f} seconds ({duration / 60:.1f} minutes)"
        )
        logger.info(
            f"📦 Total Records Fetched:  {self.metrics.total_records_fetched:,}"
        )
        logger.info(f"💾 Total Records Stored:   {self.metrics.total_records_stored:,}")
        logger.info(f"🔗 Total API Calls:        {self.metrics.total_api_calls}")
        logger.info(f"❌ Failed API Calls:       {self.metrics.failed_api_calls}")
        logger.info(f"💱 Symbols Completed:      {self.metrics.symbols_completed}")
        logger.info(f"❌ Symbols Failed:         {self.metrics.symbols_failed}")
        logger.info(f"📦 Chunks Processed:       {self.metrics.chunks_processed}")
        logger.info(f"❌ Chunks Failed:          {self.metrics.chunks_failed}")

        # Rate metrics
        logger.info(f"📈 Records/Second:         {rates['records_per_second']:.2f}")
        logger.info(f"🔗 API Calls/Second:       {rates['api_calls_per_second']:.2f}")
        logger.info(
            f"💾 Storage Rate:           {rates['storage_rate']:.2f} records/sec"
        )

        # Error metrics
        logger.info(f"⏳ Rate Limit Delays:      {self.metrics.rate_limit_delays}")
        logger.info(f"🔄 Error Backoff Delays:   {self.metrics.error_delays}")

        if self.metrics.last_successful_timestamp:
            last_time = datetime.fromtimestamp(
                self.metrics.last_successful_timestamp, tz=timezone.utc
            )
            logger.info(f"🕐 Last Successful Time:   {last_time}")

        # Per-symbol breakdown
        if self.metrics.symbol_metrics:
            logger.info("\n📊 Per-Symbol Metrics:")
            for symbol, metrics in self.metrics.symbol_metrics.items():
                logger.info(f"   {symbol}:")
                logger.info(f"     📦 Fetched: {metrics['records_fetched']:,} records")
                logger.info(f"     💾 Stored:  {metrics['records_stored']:,} records")
                logger.info(f"     🔗 API:     {metrics['api_calls']} calls")
                logger.info(f"     📦 Chunks:  {metrics['chunks']}")

        logger.info("=" * 80)

        if success:
            logger.success("✅ BACKFILL COMPLETED SUCCESSFULLY")
        else:
            logger.error("❌ BACKFILL COMPLETED WITH ERRORS")


class SmartBackfillTool:
    """Intelligent backfill tool with gap detection and oldest-data logic"""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or "postgresql://pbsg:pbsg_password@localhost:5432/pbsg"
        self.engine = create_engine(self.database_url)
        self.integrity_checker = DataIntegrityChecker(self.database_url)
        self.symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]

    def get_oldest_data_timestamp(self, symbol: str) -> Optional[datetime]:
        """Get the oldest data timestamp for a symbol"""
        table_map = {
            "BTC/USD": "btc_ohlc",
            "ETH/USD": "eth_ohlc",
            "SOL/USD": "sol_ohlc"
        }

        table_name = table_map.get(symbol)
        if not table_name:
            return None

        try:
            with Session(self.engine) as session:
                query = text(f"""
                    SELECT MIN(time) as oldest_time
                    FROM {table_name}
                    WHERE symbol = :symbol
                    AND timeframe = '15m'
                """)

                result = session.execute(query, {"symbol": symbol})
                row = result.fetchone()
                return row.oldest_time if row and row.oldest_time else None

        except Exception as e:
            logger.error(f"Error getting oldest timestamp for {symbol}: {e}")
            return None

    def analyze_data_status(self) -> Dict[str, Dict]:
        """Analyze current data status for all symbols"""
        status = {}

        for symbol in self.symbols:
            oldest_timestamp = self.get_oldest_data_timestamp(symbol)

            if oldest_timestamp:
                status[symbol] = {
                    "has_data": True,
                    "oldest_timestamp": oldest_timestamp,
                    "oldest_date": oldest_timestamp.strftime("%Y-%m-%d %H:%M"),
                }
            else:
                status[symbol] = {
                    "has_data": False,
                    "oldest_timestamp": None,
                    "oldest_date": "No data",
                }

        return status

    async def detect_and_show_gaps(self) -> Dict[str, List[DataGap]]:
        """Detect and display gaps for all symbols"""
        logger.info("🔍 Detecting data gaps...")

        reports = self.integrity_checker.check_all_symbols()
        all_gaps = {}

        print("\n" + "="*60)
        print("📊 GAP ANALYSIS")
        print("="*60)

        total_gaps = 0
        total_missing_intervals = 0

        for symbol, report in reports.items():
            gaps = report.gaps
            all_gaps[symbol] = gaps

            if report.total_records == 0:
                print(f"\n❌ {symbol}: No data found")
                continue

            print(f"\n📈 {symbol}")
            print(f"   Records: {report.total_records:,} ({report.completeness_percentage:.1f}% complete)")

            if gaps:
                total_gaps += len(gaps)
                symbol_missing = sum(gap.missing_intervals for gap in gaps)
                total_missing_intervals += symbol_missing

                print(f"   Gaps: {len(gaps)} gaps, {symbol_missing:,} missing intervals")

                # Show largest gaps
                sorted_gaps = sorted(gaps, key=lambda g: g.missing_intervals, reverse=True)
                for i, gap in enumerate(sorted_gaps[:3], 1):
                    start_time = gap.start_time.strftime("%m-%d %H:%M")
                    end_time = gap.end_time.strftime("%m-%d %H:%M")
                    print(f"     {i}. {start_time} → {end_time} ({gap.missing_intervals} intervals, {gap.duration_hours:.1f}h)")

                if len(gaps) > 3:
                    print(f"     ... and {len(gaps) - 3} more gaps")
            else:
                print("   ✅ No gaps found")

        print(f"\n📊 SUMMARY")
        print(f"   Total gaps: {total_gaps}")
        print(f"   Total missing intervals: {total_missing_intervals:,}")
        print(f"   Estimated time to fill: ~{total_missing_intervals * 15 / 60:.1f} hours of data")

        return all_gaps

    async def fill_gaps(self, gaps: Dict[str, List[DataGap]]) -> bool:
        """Fill detected gaps using targeted backfill"""
        symbols_with_gaps = [symbol for symbol, symbol_gaps in gaps.items() if symbol_gaps]

        if not symbols_with_gaps:
            print("\n✅ No gaps to fill!")
            return True

        total_gaps = sum(len(symbol_gaps) for symbol_gaps in gaps.values())
        print(f"\n🎯 FILLING {total_gaps} GAPS")
        print("="*40)

        # Create backfill config optimized for gap filling
        config = {
            "log_level": "INFO",
            "chunk_size_hours": 1,  # Smaller chunks for precise gap filling
            "batch_size": 100,
            "request_timeout": 30.0,
            "base_delay": 1.0,
            "max_retries": 3
        }

        tool = KrakenBackfillTool(config)
        overall_success = True
        filled_intervals = 0

        for symbol in symbols_with_gaps:
            symbol_gaps = gaps[symbol]
            print(f"\n🔧 Filling gaps for {symbol} ({len(symbol_gaps)} gaps)")

            for i, gap in enumerate(symbol_gaps, 1):
                # Add small buffer to ensure we don't miss intervals at boundaries
                gap_start = gap.start_time - timedelta(minutes=15)
                gap_end = gap.end_time + timedelta(minutes=15)

                start_timestamp = int(gap_start.timestamp())
                end_timestamp = int(gap_end.timestamp())

                start_str = gap_start.strftime("%m-%d %H:%M")
                end_str = gap_end.strftime("%m-%d %H:%M")

                print(f"   Gap {i}/{len(symbol_gaps)}: {start_str} → {end_str}")

                try:
                    success = await tool.backfill_symbol_range(
                        symbol, start_timestamp, end_timestamp
                    )

                    if success:
                        filled_intervals += gap.missing_intervals
                        print(f"   ✅ Filled {gap.missing_intervals} intervals")
                    else:
                        print(f"   ❌ Failed to fill gap")
                        overall_success = False

                except Exception as e:
                    logger.error(f"   ❌ Error filling gap: {e}")
                    overall_success = False

                # Brief pause between gaps
                await asyncio.sleep(0.5)

        # Final flush
        try:
            flushed_count = await tool.storage.force_flush_all()
            if flushed_count > 0:
                print(f"\n💾 Flushed {flushed_count} additional records")
        except Exception as e:
            logger.error(f"Error during final flush: {e}")

        print(f"\n📊 GAP FILLING SUMMARY")
        print(f"   Filled intervals: {filled_intervals:,}")
        print(f"   Success: {'✅ Complete' if overall_success else '❌ Partial'}")

        return overall_success

    async def extend_from_oldest(self, days_back: int, symbols: List[str]) -> bool:
        """Extend data backwards from oldest existing data"""
        print(f"\n🚀 EXTENDING DATA {days_back} DAYS BACKWARDS")
        print("="*50)

        # Get oldest data for each symbol
        extension_plan = {}

        for symbol in symbols:
            oldest_timestamp = self.get_oldest_data_timestamp(symbol)

            if oldest_timestamp:
                # Calculate new start date
                new_start = oldest_timestamp - timedelta(days=days_back)
                extension_plan[symbol] = {
                    "oldest_existing": oldest_timestamp,
                    "new_start": new_start,
                    "days_to_add": days_back,
                    "estimated_intervals": days_back * 96  # 96 intervals per day
                }

                print(f"📈 {symbol}")
                print(f"   Current oldest: {oldest_timestamp.strftime('%Y-%m-%d %H:%M')}")
                print(f"   Extending to:   {new_start.strftime('%Y-%m-%d %H:%M')}")
                print(f"   New intervals:  ~{days_back * 96:,}")
            else:
                print(f"❌ {symbol}: No existing data, skipping")

        if not extension_plan:
            print("\n❌ No symbols with existing data to extend")
            return False

        # Confirm with user
        total_intervals = sum(plan["estimated_intervals"] for plan in extension_plan.values())
        print(f"\n📊 EXTENSION SUMMARY")
        print(f"   Symbols: {len(extension_plan)}")
        print(f"   Total estimated intervals: {total_intervals:,}")
        print(f"   Estimated data: ~{total_intervals * 15 / 60 / 24:.1f} days")

        confirm = input(f"\nProceed with extension? (Y/n): ").strip().lower()
        if confirm not in ("", "y", "yes"):
            print("👋 Extension cancelled")
            return False

        # Run backfill for each symbol
        config = {
            "log_level": "INFO",
            "chunk_size_hours": 24,  # Larger chunks for bulk backfill
            "batch_size": 500,
            "request_timeout": 30.0,
        }

        tool = KrakenBackfillTool(config)
        overall_success = True

        for symbol, plan in extension_plan.items():
            print(f"\n🔧 Extending {symbol}...")

            start_timestamp = int(plan["new_start"].timestamp())
            end_timestamp = int(plan["oldest_existing"].timestamp())

            try:
                success = await tool.backfill_symbol_range(
                    symbol, start_timestamp, end_timestamp
                )

                if success:
                    print(f"   ✅ Successfully extended {symbol}")
                else:
                    print(f"   ❌ Failed to extend {symbol}")
                    overall_success = False

            except Exception as e:
                logger.error(f"   ❌ Error extending {symbol}: {e}")
                overall_success = False

        # Final flush
        try:
            flushed_count = await tool.storage.force_flush_all()
            if flushed_count > 0:
                print(f"\n💾 Flushed {flushed_count} additional records")
        except Exception as e:
            logger.error(f"Error during final flush: {e}")

        return overall_success

    def prompt_for_mode(self) -> Tuple[str, Optional[int], Optional[List[str]]]:
        """Interactive prompt for backfill mode"""
        print("\n🚀 Smart Kraken Backfill Tool")
        print("="*40)

        # Show current data status
        status = self.analyze_data_status()
        print("\n📊 CURRENT DATA STATUS")
        for symbol, info in status.items():
            if info["has_data"]:
                print(f"   {symbol}: {info['oldest_date']} (oldest)")
            else:
                print(f"   {symbol}: No data")

        print("\n🎯 BACKFILL MODES:")
        print("   • Type 'gap' to fill missing intervals")
        print("   • Type '7 days', '30 days', etc. to extend backwards from oldest data")
        print("   • Type 'cancel' to exit")

        while True:
            try:
                mode_input = input("\nBackfill mode: ").strip().lower()

                if mode_input == "cancel":
                    return "cancel", None, None

                elif mode_input == "gap":
                    return "gap", None, None

                elif mode_input.endswith(" days") or mode_input.endswith(" day"):
                    # Parse days
                    try:
                        days_str = mode_input.replace(" days", "").replace(" day", "").strip()
                        days_back = int(days_str)

                        if days_back <= 0:
                            print("❌ Please enter a positive number of days")
                            continue

                        if days_back > 365:
                            confirm = input(f"⚠️  {days_back} days is a lot of data. Continue? (y/N): ").strip().lower()
                            if confirm != "y":
                                continue

                        # Get symbols to extend
                        symbols_with_data = [s for s, info in status.items() if info["has_data"]]

                        if not symbols_with_data:
                            print("❌ No symbols with existing data to extend")
                            continue

                        print(f"\nSymbols with data: {', '.join(symbols_with_data)}")
                        symbol_input = input("Extend which symbols? (comma-separated or 'all'): ").strip()

                        if symbol_input.lower() == "all":
                            selected_symbols = symbols_with_data
                        else:
                            selected_symbols = [s.strip() for s in symbol_input.split(",")]
                            invalid = [s for s in selected_symbols if s not in symbols_with_data]
                            if invalid:
                                print(f"❌ Invalid/no-data symbols: {', '.join(invalid)}")
                                continue

                        return "extend", days_back, selected_symbols

                    except ValueError:
                        print("❌ Invalid format. Use '7 days', '30 days', etc.")
                        continue

                else:
                    print("❌ Invalid mode. Type 'gap', 'X days', or 'cancel'")
                    continue

            except KeyboardInterrupt:
                print("\n👋 Cancelled")
                return "cancel", None, None


async def main():
    """Main function"""
    tool = SmartBackfillTool()

    try:
        # Get mode from user
        mode, days_back, symbols = tool.prompt_for_mode()

        if mode == "cancel":
            print("👋 Goodbye!")
            return 0

        elif mode == "gap":
            # Gap filling mode
            gaps = await tool.detect_and_show_gaps()

            # Ask for confirmation
            total_gaps = sum(len(symbol_gaps) for symbol_gaps in gaps.values())
            if total_gaps == 0:
                return 0

            confirm = input(f"\nFill {total_gaps} detected gaps? (Y/n): ").strip().lower()
            if confirm not in ("", "y", "yes"):
                print("👋 Gap filling cancelled")
                return 0

            success = await tool.fill_gaps(gaps)
            return 0 if success else 1

        elif mode == "extend":
            # Extension mode
            success = await tool.extend_from_oldest(days_back, symbols)
            return 0 if success else 1

    except Exception as e:
        logger.error(f"❌ Smart backfill failed: {e}")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("👋 Cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)