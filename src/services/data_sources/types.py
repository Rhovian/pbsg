from datetime import datetime
from typing import List, Optional, Dict, Any, Literal, Union
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
            interval_begin=datetime.fromisoformat(data["interval_begin"].replace("Z", "+00:00")),
            interval=int(data["interval"])
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