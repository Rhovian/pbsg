#!/usr/bin/env python3
"""
Kraken Historical Data Backfill Tool

Production tool for backfilling historical OHLC data from Kraken's REST API.
Supports date range specification, chunked processing, error handling with backoff,
and comprehensive logging with ingestion metrics.

Usage:
    python scripts/python/kraken_backfill.py --start-date 2024-01-01 --end-date 2024-01-31 --symbols BTC/USD,ETH/USD
    python scripts/python/kraken_backfill.py --days-back 30 --symbols SOL/USD
    python scripts/python/kraken_backfill.py --config config.json
"""

import argparse
import asyncio
import json
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import traceback

from loguru import logger
from sqlalchemy import create_engine

from src.services.data_sources.kraken.backfill import KrakenBackfillClient
from src.services.data_sources.storage import IntegratedOHLCStorage
from src.services.data_sources.types import OHLCData


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


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Kraken Historical Data Backfill Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backfill specific date range
  %(prog)s --start-date 2024-01-01 --end-date 2024-01-31 --symbols BTC/USD,ETH/USD

  # Backfill last 30 days
  %(prog)s --days-back 30 --symbols SOL/USD

  # Use config file
  %(prog)s --config backfill-config.json

  # All supported symbols for last week
  %(prog)s --days-back 7 --all-symbols
        """,
    )

    # Date specification (mutually exclusive)
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    date_group.add_argument(
        "--days-back", type=int, help="Number of days back from now"
    )
    date_group.add_argument("--config", type=str, help="JSON config file path")

    parser.add_argument(
        "--end-date", type=str, help="End date (YYYY-MM-DD), defaults to now"
    )

    # Symbol specification
    symbol_group = parser.add_mutually_exclusive_group()
    symbol_group.add_argument(
        "--symbols",
        type=str,
        help="Comma-separated list of symbols (e.g., BTC/USD,ETH/USD)",
    )
    symbol_group.add_argument(
        "--all-symbols", action="store_true", help="Backfill all supported symbols"
    )

    # Optional configuration
    parser.add_argument(
        "--chunk-hours", type=int, default=24, help="Chunk size in hours (default: 24)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Database batch size (default: 100)"
    )
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )
    parser.add_argument("--log-file", type=str, help="Log file path")
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch data but don't store to database"
    )

    return parser.parse_args()


def load_config_file(config_path: str) -> Dict:
    """Load configuration from JSON file"""
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config file {config_path}: {e}")
        sys.exit(1)


def parse_date(date_str: str) -> datetime:
    """Parse date string to datetime object"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        logger.error(f"Invalid date format '{date_str}': {e}")
        logger.error("Expected format: YYYY-MM-DD")
        sys.exit(1)


def prompt_for_input():
    """Prompt user for backfill parameters"""
    print("🚀 Kraken Historical Data Backfill Tool")
    print("=" * 50)

    # Get days back
    while True:
        try:
            days_input = input(
                "How many days back to backfill? (e.g., 7, 30, 90): "
            ).strip()
            days_back = int(days_input)
            if days_back <= 0:
                print("❌ Please enter a positive number of days")
                continue
            if days_back > 365:
                confirm = (
                    input(f"⚠️  {days_back} days is a lot of data. Continue? (y/N): ")
                    .strip()
                    .lower()
                )
                if confirm != "y":
                    continue
            break
        except ValueError:
            print("❌ Please enter a valid number")
        except KeyboardInterrupt:
            print("\n👋 Cancelled")
            sys.exit(1)

    # Get symbols
    supported_symbols = KrakenBackfillClient.get_supported_symbols()
    print(f"\nSupported symbols: {', '.join(supported_symbols)}")

    while True:
        symbols_input = input(
            "\nSymbols to backfill (comma-separated, or 'all' for all symbols): "
        ).strip()

        if not symbols_input:
            print("❌ Please enter symbols or 'all'")
            continue

        if symbols_input.lower() == "all":
            symbols = supported_symbols
            break
        else:
            symbols = [s.strip() for s in symbols_input.split(",")]
            invalid_symbols = [s for s in symbols if s not in supported_symbols]
            if invalid_symbols:
                print(f"❌ Invalid symbols: {', '.join(invalid_symbols)}")
                continue
            break

    # Calculate dates
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_back)

    # Show summary
    print("\n📋 Backfill Summary:")
    print(
        f"   📅 Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )
    print(f"   💱 Symbols: {', '.join(symbols)}")
    print(f"   📦 Estimated 15min intervals: ~{days_back * 96:,} per symbol")

    confirm = input("\nProceed with backfill? (Y/n): ").strip().lower()
    if confirm in ("", "y", "yes"):
        return symbols, start_date, end_date
    else:
        print("👋 Cancelled")
        sys.exit(0)


async def main():
    """Main function"""
    # Check if we have command line arguments (for backwards compatibility)
    if len(sys.argv) > 1:
        args = parse_arguments()

        # Load configuration from args (existing logic)
        if args.config:
            config = load_config_file(args.config)
            symbols = config.get("symbols", [])
            start_date = parse_date(config["start_date"])
            end_date = parse_date(
                config.get("end_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            )
        else:
            # Build config from arguments
            config = {
                "log_level": args.log_level,
                "chunk_size_hours": args.chunk_hours,
                "batch_size": args.batch_size,
            }

            if args.log_file:
                config["log_file"] = args.log_file

            # Parse symbols
            if args.all_symbols:
                symbols = KrakenBackfillClient.get_supported_symbols()
            elif args.symbols:
                symbols = [s.strip() for s in args.symbols.split(",")]
            else:
                logger.error("Must specify either --symbols or --all-symbols")
                sys.exit(1)

            # Parse dates
            if args.days_back:
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(days=args.days_back)
            else:
                start_date = parse_date(args.start_date)
                if args.end_date:
                    end_date = parse_date(args.end_date)
                else:
                    end_date = datetime.now(timezone.utc)
    else:
        # Interactive mode - prompt for input
        symbols, start_date, end_date = prompt_for_input()

        # Use default config for interactive mode
        config = {
            "log_level": "INFO",
            "chunk_size_hours": 24,
            "batch_size": 100,
        }

    # Validate dates
    if start_date >= end_date:
        logger.error("Start date must be before end date")
        sys.exit(1)

    # Create backfill tool
    tool = KrakenBackfillTool(config)

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.warning(f"Received signal {signum}, initiating graceful shutdown...")
        tool.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Run backfill
        success = await tool.run_backfill(symbols, start_date, end_date)

        # Print final metrics
        tool.print_final_metrics(success)

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"❌ Backfill failed with exception: {e}")
        logger.error(traceback.format_exc())
        tool.print_final_metrics(False)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("👋 Backfill cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
