"""
Transformer to convert Kraken OHLC data to TimescaleDB format
"""

from typing import Optional, Type, Dict, Any
from datetime import datetime
from decimal import Decimal

from src.models.schema import BTCOHLC, ETHOHLC, SOLOHLC, OHLCBase, get_ohlc_model
from .types import OHLCData


class KrakenToTimescaleTransformer:
    """Transform Kraken WebSocket OHLC data to TimescaleDB models"""

    # Map Kraken symbols to database models
    SYMBOL_MODEL_MAP: Dict[str, Type[OHLCBase]] = {
        "BTC/USD": BTCOHLC,
        "ETH/USD": ETHOHLC,
        "SOL/USD": SOLOHLC,
    }

    @classmethod
    def transform(cls, ohlc_data: OHLCData) -> Optional[OHLCBase]:
        """
        Transform Kraken OHLCData to appropriate TimescaleDB model

        Args:
            ohlc_data: OHLCData object from Kraken WebSocket

        Returns:
            Database model instance or None if symbol not supported
        """
        # Get the appropriate model for the symbol
        model_class = cls.SYMBOL_MODEL_MAP.get(ohlc_data.symbol)
        if not model_class:
            # Could extend to support dynamic model creation
            return None

        # Create model instance with transformed data
        return model_class(
            time=ohlc_data.interval_begin,
            symbol=ohlc_data.symbol,
            timeframe="15m",  # Fixed 15-minute timeframe
            open=ohlc_data.open,
            high=ohlc_data.high,
            low=ohlc_data.low,
            close=ohlc_data.close,
            volume=ohlc_data.volume,
            trades=ohlc_data.trades,
        )

    @classmethod
    def transform_batch(cls, ohlc_data_list: list[OHLCData]) -> list[OHLCBase]:
        """
        Transform a batch of Kraken OHLC data

        Args:
            ohlc_data_list: List of OHLCData objects

        Returns:
            List of database model instances (skips unsupported symbols)
        """
        transformed = []
        for ohlc_data in ohlc_data_list:
            model = cls.transform(ohlc_data)
            if model:
                transformed.append(model)
        return transformed

    @classmethod
    def to_dict(cls, ohlc_data: OHLCData) -> Dict[str, Any]:
        """
        Convert OHLCData to dictionary for bulk insert

        Args:
            ohlc_data: OHLCData object from Kraken WebSocket

        Returns:
            Dictionary representation for database insert
        """
        return {
            "time": ohlc_data.interval_begin,
            "symbol": ohlc_data.symbol,
            "timeframe": "15m",
            "open": ohlc_data.open,
            "high": ohlc_data.high,
            "low": ohlc_data.low,
            "close": ohlc_data.close,
            "volume": ohlc_data.volume,
            "trades": ohlc_data.trades,
        }

    @classmethod
    def get_table_name(cls, symbol: str) -> Optional[str]:
        """
        Get the table name for a given symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USD')

        Returns:
            Table name or None if symbol not supported
        """
        symbol_map = {
            "BTC/USD": "btc_ohlc",
            "ETH/USD": "eth_ohlc",
            "SOL/USD": "sol_ohlc",
        }
        return symbol_map.get(symbol)

    @classmethod
    def is_supported_symbol(cls, symbol: str) -> bool:
        """Check if symbol is supported for storage"""
        return symbol in cls.SYMBOL_MODEL_MAP
