"""
Unit tests for data types
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from src.services.data_sources.types import (
    OHLCInterval,
    OHLCData,
    SubscriptionRequest,
    UnsubscribeRequest,
    WebSocketMessage,
    MessageType,
)


class TestOHLCInterval:
    """Test OHLCInterval enum"""

    def test_m15_value(self):
        """Test M15 interval value"""
        assert OHLCInterval.M15 == 15
        assert OHLCInterval.M15.value == 15

    def test_enum_comparison(self):
        """Test enum comparison"""
        assert OHLCInterval.M15 == 15
        assert 15 == OHLCInterval.M15


class TestOHLCData:
    """Test OHLCData dataclass"""

    @pytest.fixture
    def sample_ohlc(self):
        """Create sample OHLC data"""
        return OHLCData(
            symbol="BTC/USD",
            open=Decimal("50000.00"),
            high=Decimal("51000.00"),
            low=Decimal("49500.00"),
            close=Decimal("50500.00"),
            vwap=Decimal("50250.00"),
            trades=150,
            volume=Decimal("1234.56789"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

    def test_ohlc_creation(self, sample_ohlc):
        """Test OHLC data creation"""
        assert sample_ohlc.symbol == "BTC/USD"
        assert sample_ohlc.open == Decimal("50000.00")
        assert sample_ohlc.high == Decimal("51000.00")
        assert sample_ohlc.low == Decimal("49500.00")
        assert sample_ohlc.close == Decimal("50500.00")
        assert sample_ohlc.vwap == Decimal("50250.00")
        assert sample_ohlc.trades == 150
        assert sample_ohlc.volume == Decimal("1234.56789")
        assert sample_ohlc.interval_begin == datetime(
            2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc
        )
        assert sample_ohlc.interval == 15

    def test_from_kraken(self):
        """Test creating OHLCData from Kraken format"""
        kraken_data = {
            "symbol": "ETH/USD",
            "open": "3000.00",
            "high": "3100.00",
            "low": "2950.00",
            "close": "3050.00",
            "vwap": "3025.00",
            "trades": 100,
            "volume": "500.123",
            "interval_begin": "2024-01-01T12:00:00Z",
            "interval": 15,
        }

        ohlc = OHLCData.from_kraken(kraken_data)

        assert ohlc.symbol == "ETH/USD"
        assert ohlc.open == Decimal("3000.00")
        assert ohlc.high == Decimal("3100.00")
        assert ohlc.low == Decimal("2950.00")
        assert ohlc.close == Decimal("3050.00")
        assert ohlc.vwap == Decimal("3025.00")
        assert ohlc.trades == 100
        assert ohlc.volume == Decimal("500.123")
        assert ohlc.interval_begin == datetime(
            2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc
        )
        assert ohlc.interval == 15

    def test_from_kraken_with_different_timezone_format(self):
        """Test from_kraken handles different timezone formats"""
        kraken_data = {
            "symbol": "BTC/USD",
            "open": "50000.00",
            "high": "51000.00",
            "low": "49500.00",
            "close": "50500.00",
            "vwap": "50250.00",
            "trades": 150,
            "volume": "1234.56789",
            "interval_begin": "2024-01-01T12:00:00Z",
            "interval": 15,
        }

        ohlc = OHLCData.from_kraken(kraken_data)
        assert ohlc.interval_begin.tzinfo == timezone.utc

    def test_from_kraken_preserves_precision(self):
        """Test that from_kraken preserves decimal precision"""
        kraken_data = {
            "symbol": "BTC/USD",
            "open": "50123.12345678",
            "high": "51234.87654321",
            "low": "49876.11111111",
            "close": "50555.99999999",
            "vwap": "50250.55555555",
            "trades": 12345,
            "volume": "1234.56789012",
            "interval_begin": "2024-01-01T12:00:00Z",
            "interval": 15,
        }

        ohlc = OHLCData.from_kraken(kraken_data)

        assert ohlc.open == Decimal("50123.12345678")
        assert ohlc.high == Decimal("51234.87654321")
        assert ohlc.low == Decimal("49876.11111111")
        assert ohlc.close == Decimal("50555.99999999")
        assert ohlc.vwap == Decimal("50250.55555555")
        assert ohlc.volume == Decimal("1234.56789012")

    def test_from_kraken_handles_string_trades(self):
        """Test from_kraken handles trades as string"""
        kraken_data = {
            "symbol": "BTC/USD",
            "open": "50000.00",
            "high": "51000.00",
            "low": "49500.00",
            "close": "50500.00",
            "vwap": "50250.00",
            "trades": "150",  # String instead of int
            "volume": "1234.56789",
            "interval_begin": "2024-01-01T12:00:00Z",
            "interval": "15",  # String instead of int
        }

        ohlc = OHLCData.from_kraken(kraken_data)
        assert ohlc.trades == 150
        assert ohlc.interval == 15

    def test_ohlc_data_equality(self):
        """Test OHLCData equality"""
        ohlc1 = OHLCData(
            symbol="BTC/USD",
            open=Decimal("50000.00"),
            high=Decimal("51000.00"),
            low=Decimal("49500.00"),
            close=Decimal("50500.00"),
            vwap=Decimal("50250.00"),
            trades=150,
            volume=Decimal("1234.56789"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        ohlc2 = OHLCData(
            symbol="BTC/USD",
            open=Decimal("50000.00"),
            high=Decimal("51000.00"),
            low=Decimal("49500.00"),
            close=Decimal("50500.00"),
            vwap=Decimal("50250.00"),
            trades=150,
            volume=Decimal("1234.56789"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        assert ohlc1 == ohlc2


class TestSubscriptionRequest:
    """Test SubscriptionRequest dataclass"""

    def test_creation_with_defaults(self):
        """Test creating subscription request with defaults"""
        req = SubscriptionRequest(
            symbols=["BTC/USD", "ETH/USD"], interval=OHLCInterval.M15
        )

        assert req.symbols == ["BTC/USD", "ETH/USD"]
        assert req.interval == OHLCInterval.M15
        assert req.snapshot is True
        assert req.req_id is None

    def test_creation_with_all_params(self):
        """Test creating subscription request with all parameters"""
        req = SubscriptionRequest(
            symbols=["BTC/USD"], interval=OHLCInterval.M15, snapshot=False, req_id=123
        )

        assert req.symbols == ["BTC/USD"]
        assert req.interval == OHLCInterval.M15
        assert req.snapshot is False
        assert req.req_id == 123

    def test_interval_as_int(self):
        """Test interval can be accessed as int"""
        req = SubscriptionRequest(symbols=["BTC/USD"], interval=OHLCInterval.M15)

        assert req.interval == 15
        assert req.interval.value == 15


class TestUnsubscribeRequest:
    """Test UnsubscribeRequest dataclass"""

    def test_creation_with_defaults(self):
        """Test creating unsubscribe request with defaults"""
        req = UnsubscribeRequest(
            symbols=["BTC/USD", "ETH/USD"], interval=OHLCInterval.M15
        )

        assert req.symbols == ["BTC/USD", "ETH/USD"]
        assert req.interval == OHLCInterval.M15
        assert req.req_id is None

    def test_creation_with_req_id(self):
        """Test creating unsubscribe request with request ID"""
        req = UnsubscribeRequest(
            symbols=["BTC/USD"], interval=OHLCInterval.M15, req_id=456
        )

        assert req.symbols == ["BTC/USD"]
        assert req.interval == OHLCInterval.M15
        assert req.req_id == 456


class TestWebSocketMessage:
    """Test WebSocketMessage dataclass"""

    def test_creation_minimal(self):
        """Test creating message with minimal parameters"""
        msg = WebSocketMessage(type="update", channel="ohlc", data={"test": "data"})

        assert msg.type == "update"
        assert msg.channel == "ohlc"
        assert msg.data == {"test": "data"}
        assert msg.req_id is None
        assert msg.error is None

    def test_creation_with_all_params(self):
        """Test creating message with all parameters"""
        msg = WebSocketMessage(
            type="error",
            channel="ohlc",
            data=None,
            req_id=789,
            error="Test error message",
        )

        assert msg.type == "error"
        assert msg.channel == "ohlc"
        assert msg.data is None
        assert msg.req_id == 789
        assert msg.error == "Test error message"

    @pytest.mark.parametrize(
        "msg_type", ["snapshot", "update", "subscribe", "unsubscribe", "error"]
    )
    def test_valid_message_types(self, msg_type):
        """Test all valid message types"""
        msg = WebSocketMessage(type=msg_type, channel="test", data=None)

        assert msg.type == msg_type

    def test_message_with_ohlc_data_list(self):
        """Test message containing list of OHLCData"""
        ohlc_list = [
            OHLCData(
                symbol="BTC/USD",
                open=Decimal("50000.00"),
                high=Decimal("51000.00"),
                low=Decimal("49500.00"),
                close=Decimal("50500.00"),
                vwap=Decimal("50250.00"),
                trades=150,
                volume=Decimal("1234.56789"),
                interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                interval=15,
            )
        ]

        msg = WebSocketMessage(type="update", channel="ohlc", data=ohlc_list)

        assert msg.data == ohlc_list
        assert isinstance(msg.data[0], OHLCData)

    def test_message_equality(self):
        """Test WebSocketMessage equality"""
        msg1 = WebSocketMessage(
            type="update", channel="ohlc", data={"value": 123}, req_id=1
        )

        msg2 = WebSocketMessage(
            type="update", channel="ohlc", data={"value": 123}, req_id=1
        )

        assert msg1 == msg2

    def test_message_inequality(self):
        """Test WebSocketMessage inequality"""
        msg1 = WebSocketMessage(type="update", channel="ohlc", data={"value": 123})

        msg2 = WebSocketMessage(type="snapshot", channel="ohlc", data={"value": 123})

        assert msg1 != msg2
