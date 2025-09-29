"""Data manager for dashboard service - handles data retrieval and caching"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy import text
from loguru import logger

from ..data_sources.storage import IntegratedOHLCStorage


class DataManager:
    """Manages data retrieval for dashboard components"""

    def __init__(self, engine: Engine, storage: Optional[IntegratedOHLCStorage] = None):
        self.engine = engine
        self.storage = storage
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = timedelta(seconds=30)  # 30 second cache TTL
        self._last_cache_update: Dict[str, datetime] = {}

    def get_latest_ohlc_data(
        self, symbol: str, limit: int = 5000, interval_minutes: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Get latest OHLC data for a symbol

        Args:
            symbol: Trading symbol (e.g., 'BTC/USD', 'XBTUSD')
            limit: Number of records to return
            interval_minutes: Interval in minutes (default 15)

        Returns:
            List of OHLC data dictionaries
        """
        cache_key = f"ohlc_{symbol}_{limit}_{interval_minutes}"

        # Check cache first
        if self._is_cache_valid(cache_key):
            logger.debug(f"Returning cached data for {cache_key}")
            return self._cache[cache_key]

        # Normalize symbol format
        normalized_symbol = self._normalize_symbol(symbol)
        table_name = self._get_table_name(normalized_symbol)

        if not table_name:
            logger.warning(f"No table found for symbol: {symbol}")
            return []

        try:
            with Session(self.engine) as session:
                # Query the appropriate TimescaleDB hypertable
                query = text(f"""
                    SELECT
                        symbol,
                        time,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        trades
                    FROM {table_name}
                    WHERE symbol = :symbol
                    AND timeframe = :timeframe
                    ORDER BY time DESC
                    LIMIT :limit
                """)

                result = session.execute(
                    query,
                    {"symbol": normalized_symbol, "timeframe": "15m", "limit": limit},
                )

                data = []
                for row in result:
                    data.append(
                        {
                            "symbol": row.symbol,
                            "timestamp": row.time.isoformat(),
                            "open": float(row.open),
                            "high": float(row.high),
                            "low": float(row.low),
                            "close": float(row.close),
                            "volume": float(row.volume),
                            "trades": row.trades,
                        }
                    )

                # Reverse to get chronological order (oldest first)
                data.reverse()

                # Cache the result
                self._cache[cache_key] = data
                self._last_cache_update[cache_key] = datetime.now(timezone.utc)

                logger.debug(
                    f"Retrieved {len(data)} OHLC records for {normalized_symbol} from {table_name}"
                )
                return data

        except Exception as e:
            logger.error(f"Error retrieving OHLC data for {symbol}: {e}")
            return []

    def get_volume_data(
        self, symbol: str, limit: int = 100, interval_minutes: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Get volume data for a symbol

        Args:
            symbol: Trading symbol
            limit: Number of records to return
            interval_minutes: Interval in minutes

        Returns:
            List of volume data dictionaries
        """
        cache_key = f"volume_{symbol}_{limit}_{interval_minutes}"

        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Normalize symbol format
        normalized_symbol = self._normalize_symbol(symbol)
        table_name = self._get_table_name(normalized_symbol)

        if not table_name:
            logger.warning(f"No table found for symbol: {symbol}")
            return []

        try:
            with Session(self.engine) as session:
                query = text(f"""
                    SELECT
                        time,
                        volume,
                        trades
                    FROM {table_name}
                    WHERE symbol = :symbol
                    AND timeframe = :timeframe
                    ORDER BY time DESC
                    LIMIT :limit
                """)

                result = session.execute(
                    query,
                    {"symbol": normalized_symbol, "timeframe": "15m", "limit": limit},
                )

                data = []
                for row in result:
                    data.append(
                        {
                            "timestamp": row.time.isoformat(),
                            "volume": float(row.volume),
                            "trades": row.trades,
                        }
                    )

                data.reverse()  # Chronological order

                self._cache[cache_key] = data
                self._last_cache_update[cache_key] = datetime.now(timezone.utc)

                return data

        except Exception as e:
            logger.error(f"Error retrieving volume data for {symbol}: {e}")
            return []

    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols from the database"""
        cache_key = "available_symbols"

        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Check each supported table for data
        supported_symbols = []
        tables_to_check = [
            ("BTC/USD", "btc_ohlc"),
            ("ETH/USD", "eth_ohlc"),
            ("SOL/USD", "sol_ohlc"),
        ]

        try:
            with Session(self.engine) as session:
                for symbol, table_name in tables_to_check:
                    try:
                        # Check if table exists and has data
                        query = text(f"""
                            SELECT COUNT(*) as count
                            FROM {table_name}
                            LIMIT 1
                        """)
                        result = session.execute(query)
                        count = result.fetchone()
                        if count and count.count > 0:
                            supported_symbols.append(symbol)
                    except Exception as table_error:
                        logger.debug(f"Table {table_name} not available: {table_error}")
                        continue

                if not supported_symbols:
                    # Return default symbols if no tables have data
                    supported_symbols = ["BTC/USD", "ETH/USD"]

                self._cache[cache_key] = supported_symbols
                self._last_cache_update[cache_key] = datetime.now(timezone.utc)

                return supported_symbols

        except Exception as e:
            logger.error(f"Error retrieving available symbols: {e}")
            # Return default symbols if database query fails
            return ["BTC/USD", "ETH/USD"]

    def get_latest_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the latest price for a symbol"""
        cache_key = f"latest_price_{symbol}"

        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Normalize symbol format
        normalized_symbol = self._normalize_symbol(symbol)
        table_name = self._get_table_name(normalized_symbol)

        if not table_name:
            logger.warning(f"No table found for symbol: {symbol}")
            return None

        try:
            with Session(self.engine) as session:
                query = text(f"""
                    SELECT
                        close,
                        volume,
                        time
                    FROM {table_name}
                    WHERE symbol = :symbol
                    ORDER BY time DESC
                    LIMIT 1
                """)

                result = session.execute(query, {"symbol": normalized_symbol})
                row = result.fetchone()

                if row:
                    data = {
                        "price": float(row.close),
                        "volume": float(row.volume),
                        "timestamp": row.time.isoformat(),
                    }

                    self._cache[cache_key] = data
                    self._last_cache_update[cache_key] = datetime.now(timezone.utc)

                    return data

        except Exception as e:
            logger.error(f"Error retrieving latest price for {symbol}: {e}")

        return None

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics if available"""
        if self.storage:
            return self.storage.get_comprehensive_stats()
        return {}

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self._cache:
            return False

        if cache_key not in self._last_cache_update:
            return False

        age = datetime.now(timezone.utc) - self._last_cache_update[cache_key]
        return age < self._cache_ttl

    def clear_cache(self) -> None:
        """Clear all cached data"""
        self._cache.clear()
        self._last_cache_update.clear()
        logger.debug("Cache cleared")

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format for database queries

        Args:
            symbol: Input symbol (e.g., 'XBTUSD', 'BTC/USD')

        Returns:
            Normalized symbol (e.g., 'BTC/USD')
        """
        # Convert Kraken format to standard format
        symbol_map = {
            "XBTUSD": "BTC/USD",
            "ETHUSD": "ETH/USD",
            "SOLUSD": "SOL/USD",
        }

        # Return mapped symbol or the original if no mapping exists
        return symbol_map.get(symbol, symbol)

    def _get_table_name(self, symbol: str) -> Optional[str]:
        """
        Get the table name for a given symbol

        Args:
            symbol: Normalized symbol (e.g., 'BTC/USD')

        Returns:
            Table name or None if symbol not supported
        """
        table_map = {
            "BTC/USD": "btc_ohlc",
            "ETH/USD": "eth_ohlc",
            "SOL/USD": "sol_ohlc",
        }

        return table_map.get(symbol)

    def get_total_record_count(self, symbol: str) -> int:
        """Get total number of records for a symbol"""
        normalized_symbol = self._normalize_symbol(symbol)
        table_name = self._get_table_name(normalized_symbol)

        if not table_name:
            return 0

        try:
            with Session(self.engine) as session:
                query = text(f"""
                    SELECT COUNT(*) as total
                    FROM {table_name}
                    WHERE symbol = :symbol
                    AND timeframe = '15m'
                """)

                result = session.execute(query, {"symbol": normalized_symbol})
                count = result.fetchone()
                return count.total if count else 0

        except Exception as e:
            logger.error(f"Error getting record count for {symbol}: {e}")
            return 0

    def get_ohlc_data_chunk(
        self, symbol: str, offset: int = 0, limit: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Get a chunk of OHLC data with offset (for progressive loading)

        Args:
            symbol: Trading symbol
            offset: Number of records to skip (from most recent)
            limit: Number of records to return

        Returns:
            List of OHLC data dictionaries
        """
        normalized_symbol = self._normalize_symbol(symbol)
        table_name = self._get_table_name(normalized_symbol)

        if not table_name:
            return []

        try:
            with Session(self.engine) as session:
                query = text(f"""
                    SELECT
                        symbol, time, open, high, low, close, volume, trades
                    FROM {table_name}
                    WHERE symbol = :symbol
                    AND timeframe = '15m'
                    ORDER BY time DESC
                    LIMIT :limit OFFSET :offset
                """)

                result = session.execute(
                    query,
                    {"symbol": normalized_symbol, "limit": limit, "offset": offset},
                )

                data = []
                for row in result:
                    data.append({
                        "symbol": row.symbol,
                        "timestamp": row.time.isoformat(),
                        "open": float(row.open),
                        "high": float(row.high),
                        "low": float(row.low),
                        "close": float(row.close),
                        "volume": float(row.volume),
                        "trades": row.trades,
                    })

                # Reverse to get chronological order (oldest first)
                data.reverse()
                return data

        except Exception as e:
            logger.error(f"Error retrieving OHLC chunk for {symbol}: {e}")
            return []
