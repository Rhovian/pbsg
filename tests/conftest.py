"""
Global pytest fixtures and configuration for all tests
"""
import pytest
import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, Mock
import random

from src.services.data_sources.types import OHLCData, WebSocketMessage
from src.models.schema import BTCOHLC, ETHOHLC, SOLOHLC


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_websocket():
    """Mock websocket connection"""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    ws.__aiter__ = AsyncMock(return_value=iter([]))
    return ws


class SeedDataGenerator:
    """Generate realistic seed data for testing"""

    @staticmethod
    def generate_ohlc_data(
        symbol: str = "BTC/USD",
        base_price: float = 50000.0,
        volatility: float = 0.02,
        start_time: Optional[datetime] = None,
        count: int = 1,
        interval_minutes: int = 15
    ) -> List[OHLCData]:
        """Generate realistic OHLC data with random walk"""
        if start_time is None:
            start_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        ohlc_list = []
        current_price = base_price

        for i in range(count):
            # Random walk for price movement
            change_percent = random.gauss(0, volatility)
            new_price = current_price * (1 + change_percent)

            # Generate OHLC values
            open_price = current_price
            close_price = new_price

            # High and low with some variance
            high_variance = abs(random.gauss(0, volatility/2))
            low_variance = abs(random.gauss(0, volatility/2))

            high_price = max(open_price, close_price) * (1 + high_variance)
            low_price = min(open_price, close_price) * (1 - low_variance)

            # Volume with random variation
            base_volume = 1000 + random.randint(-500, 500)
            volume = max(100, base_volume + random.gauss(0, 100))

            # Number of trades
            trades = random.randint(50, 500)

            # VWAP calculation (simplified)
            vwap = (high_price + low_price + close_price) / 3

            ohlc = OHLCData(
                symbol=symbol,
                open=Decimal(str(round(open_price, 8))),
                high=Decimal(str(round(high_price, 8))),
                low=Decimal(str(round(low_price, 8))),
                close=Decimal(str(round(close_price, 8))),
                vwap=Decimal(str(round(vwap, 8))),
                trades=trades,
                volume=Decimal(str(round(volume, 8))),
                interval_begin=start_time + timedelta(minutes=i * interval_minutes),
                interval=interval_minutes
            )

            ohlc_list.append(ohlc)
            current_price = new_price

        return ohlc_list

    @staticmethod
    def generate_kraken_ohlc_message(
        ohlc_data: List[OHLCData],
        message_type: str = "snapshot"
    ) -> Dict[str, Any]:
        """Generate Kraken-format WebSocket OHLC message"""
        candles = []
        for ohlc in ohlc_data:
            candle = {
                "symbol": ohlc.symbol,
                "open": str(ohlc.open),
                "high": str(ohlc.high),
                "low": str(ohlc.low),
                "close": str(ohlc.close),
                "vwap": str(ohlc.vwap),
                "trades": ohlc.trades,
                "volume": str(ohlc.volume),
                "interval_begin": ohlc.interval_begin.isoformat().replace("+00:00", "Z"),
                "interval": ohlc.interval
            }
            candles.append(candle)

        return {
            "channel": "ohlc",
            "type": message_type,
            "data": candles
        }

    @staticmethod
    def generate_subscription_response(
        success: bool = True,
        symbols: List[str] = None,
        error: Optional[str] = None,
        req_id: int = 1
    ) -> Dict[str, Any]:
        """Generate Kraken subscription response"""
        if success:
            return {
                "method": "subscribe",
                "success": True,
                "result": {
                    "channel": "ohlc",
                    "interval": 15,
                    "snapshot": True,
                    "symbol": symbols or ["BTC/USD"]
                },
                "req_id": req_id
            }
        else:
            return {
                "method": "subscribe",
                "success": False,
                "error": error or "Subscription failed",
                "req_id": req_id
            }

    @staticmethod
    def generate_error_message(
        error_msg: str = "Invalid request",
        req_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate error message"""
        msg = {"error": error_msg}
        if req_id:
            msg["req_id"] = req_id
        return msg

    @staticmethod
    def generate_heartbeat() -> Dict[str, Any]:
        """Generate heartbeat message"""
        return {"channel": "heartbeat"}

    @staticmethod
    def generate_market_scenario(
        scenario: str = "normal",
        symbol: str = "BTC/USD",
        duration_minutes: int = 60,
        interval_minutes: int = 15
    ) -> List[OHLCData]:
        """Generate market scenarios for testing

        Scenarios:
        - normal: Normal market conditions with moderate volatility
        - bull: Strong upward trend
        - bear: Strong downward trend
        - volatile: High volatility with large price swings
        - flash_crash: Sudden drop followed by recovery
        - pump: Sudden spike followed by correction
        """
        count = duration_minutes // interval_minutes
        base_price = 50000.0 if "BTC" in symbol else 3000.0 if "ETH" in symbol else 100.0

        scenarios_config = {
            "normal": {"volatility": 0.01, "trend": 0},
            "bull": {"volatility": 0.015, "trend": 0.002},
            "bear": {"volatility": 0.015, "trend": -0.002},
            "volatile": {"volatility": 0.05, "trend": 0},
            "flash_crash": {"volatility": 0.03, "trend": -0.01, "recovery_at": 0.5},
            "pump": {"volatility": 0.03, "trend": 0.01, "correction_at": 0.5}
        }

        config = scenarios_config.get(scenario, scenarios_config["normal"])
        ohlc_list = []
        current_price = base_price
        start_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        for i in range(count):
            # Apply scenario-specific logic
            if scenario == "flash_crash" and i >= count * config.get("recovery_at", 0.5):
                config["trend"] = 0.005  # Recovery phase
            elif scenario == "pump" and i >= count * config.get("correction_at", 0.5):
                config["trend"] = -0.005  # Correction phase

            # Calculate price movement
            trend_component = config["trend"]
            random_component = random.gauss(0, config["volatility"])
            change_percent = trend_component + random_component

            new_price = current_price * (1 + change_percent)

            # Generate OHLC
            open_price = current_price
            close_price = new_price

            high_variance = abs(random.gauss(0, config["volatility"]/2))
            low_variance = abs(random.gauss(0, config["volatility"]/2))

            high_price = max(open_price, close_price) * (1 + high_variance)
            low_price = min(open_price, close_price) * (1 - low_variance)

            # Volume increases with volatility
            base_volume = 1000 * (1 + abs(change_percent) * 10)
            volume = max(100, base_volume + random.gauss(0, 100))

            trades = int(50 + abs(change_percent) * 1000)
            vwap = (high_price + low_price + close_price) / 3

            ohlc = OHLCData(
                symbol=symbol,
                open=Decimal(str(round(open_price, 8))),
                high=Decimal(str(round(high_price, 8))),
                low=Decimal(str(round(low_price, 8))),
                close=Decimal(str(round(close_price, 8))),
                vwap=Decimal(str(round(vwap, 8))),
                trades=trades,
                volume=Decimal(str(round(volume, 8))),
                interval_begin=start_time + timedelta(minutes=i * interval_minutes),
                interval=interval_minutes
            )

            ohlc_list.append(ohlc)
            current_price = new_price

        return ohlc_list


@pytest.fixture
def seed_generator():
    """Provide seed data generator"""
    return SeedDataGenerator()


@pytest.fixture
def sample_ohlc_data(seed_generator):
    """Generate sample OHLC data"""
    return seed_generator.generate_ohlc_data(count=10)


@pytest.fixture
def sample_kraken_message(seed_generator, sample_ohlc_data):
    """Generate sample Kraken WebSocket message"""
    return seed_generator.generate_kraken_ohlc_message(sample_ohlc_data[:1])


@pytest.fixture
def mock_database_session():
    """Mock database session"""
    session = MagicMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.query = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy engine"""
    engine = MagicMock()
    engine.connect = MagicMock()
    engine.execute = MagicMock()
    return engine