from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass
from enum import IntEnum
from decimal import Decimal


class OHLCInterval(IntEnum):
    """Fixed 15-minute interval for base data storage"""

    M15 = 15


@dataclass
class OHLCData:
    """OHLC candle data from WebSocket feed"""

    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    vwap: Decimal
    trades: int
    volume: Decimal
    interval_begin: datetime
    interval: int

    @staticmethod
    def _parse_datetime(timestamp_str: str) -> datetime:
        """Parse datetime string handling both microseconds and nanoseconds"""
        # Replace Z with timezone
        timestamp_str = timestamp_str.replace("Z", "+00:00")

        # Handle nanoseconds by truncating to microseconds
        if "." in timestamp_str and len(timestamp_str.split(".")[1].split("+")[0]) > 6:
            # Find the decimal point and timezone
            parts = timestamp_str.split(".")
            fractional_and_tz = parts[1]

            if "+" in fractional_and_tz:
                fractional, tz = fractional_and_tz.split("+", 1)
                # Truncate to 6 digits (microseconds)
                fractional = fractional[:6]
                timestamp_str = f"{parts[0]}.{fractional}+{tz}"
            elif "-" in fractional_and_tz:
                fractional, tz = fractional_and_tz.split("-", 1)
                fractional = fractional[:6]
                timestamp_str = f"{parts[0]}.{fractional}-{tz}"

        return datetime.fromisoformat(timestamp_str)

    @classmethod
    def from_kraken(cls, data: Dict[str, Any]) -> "OHLCData":
        """Convert Kraken WebSocket candle data to OHLCData"""
        return cls(
            symbol=data["symbol"],
            open=Decimal(str(data["open"])),
            high=Decimal(str(data["high"])),
            low=Decimal(str(data["low"])),
            close=Decimal(str(data["close"])),
            vwap=Decimal(str(data["vwap"])),
            trades=int(data["trades"]),
            volume=Decimal(str(data["volume"])),
            interval_begin=cls._parse_datetime(data["interval_begin"]),
            interval=int(data["interval"]),
        )


@dataclass
class SubscriptionRequest:
    symbols: List[str]
    interval: OHLCInterval
    snapshot: bool = True
    req_id: Optional[int] = None


@dataclass
class UnsubscribeRequest:
    symbols: List[str]
    interval: OHLCInterval
    req_id: Optional[int] = None


MessageType = Literal["snapshot", "update", "subscribe", "unsubscribe", "error"]


@dataclass
class WebSocketMessage:
    type: MessageType
    channel: str
    data: Any
    req_id: Optional[int] = None
    error: Optional[str] = None
