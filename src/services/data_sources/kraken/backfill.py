"""
Kraken REST API backfill client for historical OHLC data
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from decimal import Decimal

import httpx
from loguru import logger

from ..types import OHLCData


class KrakenBackfillClient:
    """Client for backfilling historical OHLC data from Kraken REST API"""

    BASE_URL = "https://api.kraken.com/0/public"
    RATE_LIMIT_DELAY = 1.0  # 1 second between requests to avoid rate limiting

    # Map our standard symbols to Kraken's REST API format
    SYMBOL_MAP = {
        "BTC/USD": "XBTUSD",
        "ETH/USD": "ETHUSD",
        "SOL/USD": "SOLUSD",
    }

    # Reverse mapping for converting back
    REVERSE_SYMBOL_MAP = {v: k for k, v in SYMBOL_MAP.items()}

    def __init__(self, timeout: float = 30.0):
        """
        Initialize the backfill client

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self._last_request_time = 0.0

    async def _rate_limit(self) -> None:
        """Ensure we don't exceed rate limits"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.RATE_LIMIT_DELAY:
            sleep_time = self.RATE_LIMIT_DELAY - time_since_last
            await asyncio.sleep(sleep_time)

        self._last_request_time = time.time()

    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to Kraken API with error handling

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            API response data

        Raises:
            Exception: If request fails or API returns error
        """
        await self._rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # Check for Kraken API errors
                if "error" in data and data["error"]:
                    raise Exception(f"Kraken API error: {data['error']}")

                return data

            except httpx.TimeoutException:
                raise Exception(f"Request timeout for {url}")
            except httpx.HTTPStatusError as e:
                raise Exception(f"HTTP error {e.response.status_code} for {url}")
            except Exception as e:
                raise Exception(f"Request failed for {url}: {e}")

    def _convert_ohlc_data(self, symbol: str, ohlc_array: List[Any]) -> OHLCData:
        """
        Convert Kraken REST API OHLC array to OHLCData object

        Args:
            symbol: Our standard symbol format (e.g., 'BTC/USD')
            ohlc_array: Kraken OHLC array [time, open, high, low, close, vwap, volume, count]

        Returns:
            OHLCData object
        """
        # Kraken REST API format: [time, open, high, low, close, vwap, volume, count]
        time_unix, open_price, high_price, low_price, close_price, vwap, volume, count = ohlc_array

        # Convert Unix timestamp to datetime
        interval_begin = datetime.fromtimestamp(int(time_unix), tz=timezone.utc)

        return OHLCData(
            symbol=symbol,
            open=Decimal(str(open_price)),
            high=Decimal(str(high_price)),
            low=Decimal(str(low_price)),
            close=Decimal(str(close_price)),
            vwap=Decimal(str(vwap)),
            trades=int(count),
            volume=Decimal(str(volume)),
            interval_begin=interval_begin,
            interval=15,  # Fixed 15-minute interval
        )

    async def get_ohlc_data(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[OHLCData]:
        """
        Get OHLC data for a single symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USD')
            since: Unix timestamp to get data since (for incremental updates)
            limit: Maximum number of records to return (None = all available, max 720)

        Returns:
            List of OHLCData objects

        Raises:
            Exception: If symbol not supported or API request fails
        """
        if symbol not in self.SYMBOL_MAP:
            raise Exception(f"Symbol {symbol} not supported. Supported symbols: {list(self.SYMBOL_MAP.keys())}")

        kraken_symbol = self.SYMBOL_MAP[symbol]

        params = {
            "pair": kraken_symbol,
            "interval": 15,  # 15-minute intervals
        }

        if since is not None:
            params["since"] = since

        logger.info(f"Fetching OHLC data for {symbol} (Kraken: {kraken_symbol})")
        if since:
            logger.info(f"Since timestamp: {since} ({datetime.fromtimestamp(since, tz=timezone.utc)})")

        try:
            response = await self._make_request("OHLC", params)

            # Extract OHLC data from response
            result = response.get("result", {})

            # Kraken returns XXBTZUSD instead of XBTUSD, so find the actual key
            ohlc_arrays = []
            for key in result.keys():
                if key != "last" and isinstance(result[key], list):
                    ohlc_arrays = result[key]
                    logger.debug(f"Using data from key: {key}")
                    break

            if not ohlc_arrays:
                logger.warning(f"No OHLC data returned for {symbol}")
                return []

            # Convert to OHLCData objects
            ohlc_data = []
            for ohlc_array in ohlc_arrays:
                try:
                    ohlc = self._convert_ohlc_data(symbol, ohlc_array)
                    ohlc_data.append(ohlc)
                except Exception as e:
                    logger.error(f"Error converting OHLC data for {symbol}: {e}")
                    continue

            # Apply limit if specified
            if limit and len(ohlc_data) > limit:
                ohlc_data = ohlc_data[:limit]

            logger.info(f"Retrieved {len(ohlc_data)} OHLC records for {symbol}")

            # Log the last timestamp for reference
            if ohlc_data:
                last_timestamp = result.get("last")
                if last_timestamp:
                    last_time = datetime.fromtimestamp(int(last_timestamp), tz=timezone.utc)
                    logger.info(f"Last available timestamp: {last_timestamp} ({last_time})")

            return ohlc_data

        except Exception as e:
            logger.error(f"Failed to fetch OHLC data for {symbol}: {e}")
            raise

    async def backfill_multiple_symbols(
        self,
        symbols: List[str],
        since: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Dict[str, List[OHLCData]]:
        """
        Backfill OHLC data for multiple symbols

        Args:
            symbols: List of trading pair symbols
            since: Unix timestamp to get data since
            limit: Maximum number of records per symbol

        Returns:
            Dictionary mapping symbols to their OHLC data
        """
        results = {}

        for symbol in symbols:
            try:
                ohlc_data = await self.get_ohlc_data(symbol, since, limit)
                results[symbol] = ohlc_data
            except Exception as e:
                logger.error(f"Failed to backfill {symbol}: {e}")
                results[symbol] = []

        total_records = sum(len(data) for data in results.values())
        logger.info(f"Backfill completed: {total_records} total records across {len(symbols)} symbols")

        return results

    async def backfill_since_timestamp(
        self,
        symbols: List[str],
        since_timestamp: int,
        batch_size: int = 720
    ) -> Dict[str, List[OHLCData]]:
        """
        Backfill data since a specific timestamp, handling pagination if needed

        Args:
            symbols: List of trading pair symbols
            since_timestamp: Unix timestamp to start backfill from
            batch_size: Number of records per batch (Kraken max is 720)

        Returns:
            Dictionary mapping symbols to their complete OHLC data
        """
        all_results = {}

        for symbol in symbols:
            logger.info(f"Starting backfill for {symbol} since {since_timestamp}")

            all_data = []
            current_since = since_timestamp

            while True:
                try:
                    # Get batch of data
                    batch_data = await self.get_ohlc_data(symbol, current_since, batch_size)

                    if not batch_data:
                        logger.info(f"No more data available for {symbol}")
                        break

                    all_data.extend(batch_data)

                    # If we got less than the batch size, we're done
                    if len(batch_data) < batch_size:
                        logger.info(f"Reached end of available data for {symbol}")
                        break

                    # Update since timestamp for next batch (last timestamp + 1)
                    last_timestamp = int(batch_data[-1].interval_begin.timestamp())
                    current_since = last_timestamp + 1

                    logger.info(f"Retrieved {len(batch_data)} records for {symbol}, continuing from {current_since}")

                except Exception as e:
                    logger.error(f"Error during backfill for {symbol}: {e}")
                    break

            all_results[symbol] = all_data
            logger.info(f"Completed backfill for {symbol}: {len(all_data)} total records")

        return all_results

    @classmethod
    def get_supported_symbols(cls) -> List[str]:
        """Get list of supported symbols"""
        return list(cls.SYMBOL_MAP.keys())

    @classmethod
    def is_supported_symbol(cls, symbol: str) -> bool:
        """Check if symbol is supported"""
        return symbol in cls.SYMBOL_MAP