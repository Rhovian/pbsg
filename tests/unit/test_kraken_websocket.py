"""
Unit tests for KrakenOHLCHandler
"""

import pytest
import json
from unittest.mock import AsyncMock
from decimal import Decimal

from src.services.data_sources.kraken import KrakenOHLCHandler
from src.services.data_sources.types import OHLCData


class TestKrakenOHLCHandler:
    """Test KrakenOHLCHandler functionality"""

    @pytest.fixture
    def handler(self):
        """Create handler instance"""
        return KrakenOHLCHandler()

    @pytest.fixture
    def sample_ohlc_candle(self):
        """Create sample OHLC candle data"""
        return {
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

    def test_initialization(self, handler):
        """Test handler initialization"""
        assert handler.url == "wss://ws.kraken.com/v2"
        assert handler.request_id == 0

    @pytest.mark.asyncio
    async def test_subscribe(self, handler):
        """Test subscription to symbols"""
        handler.websocket = AsyncMock()
        handler.is_connected = True

        symbols = ["BTC/USD", "ETH/USD"]
        await handler.subscribe(symbols, snapshot=True)

        # Check request ID incremented
        assert handler.request_id == 1

        # Check subscriptions stored
        assert "ohlc_15" in handler.subscriptions
        assert handler.subscriptions["ohlc_15"]["symbols"] == symbols
        assert handler.subscriptions["ohlc_15"]["snapshot"] is True

        # Verify message sent
        handler.websocket.send.assert_called_once()
        sent_data = json.loads(handler.websocket.send.call_args[0][0])

        assert sent_data["method"] == "subscribe"
        assert sent_data["params"]["channel"] == "ohlc"
        assert sent_data["params"]["symbol"] == symbols
        assert sent_data["params"]["interval"] == 15
        assert sent_data["params"]["snapshot"] is True
        assert sent_data["req_id"] == 1

    @pytest.mark.asyncio
    async def test_subscribe_no_duplicates(self, handler):
        """Test that duplicate symbols are not added"""
        handler.websocket = AsyncMock()
        handler.is_connected = True

        await handler.subscribe(["BTC/USD"])
        await handler.subscribe(["BTC/USD", "ETH/USD"])

        assert handler.subscriptions["ohlc_15"]["symbols"] == ["BTC/USD", "ETH/USD"]

    @pytest.mark.asyncio
    async def test_unsubscribe(self, handler):
        """Test unsubscription from symbols"""
        handler.websocket = AsyncMock()
        handler.is_connected = True

        # Setup existing subscription
        handler.subscriptions["ohlc_15"] = {
            "symbols": ["BTC/USD", "ETH/USD", "SOL/USD"],
            "snapshot": True,
        }

        await handler.unsubscribe(["BTC/USD", "ETH/USD"])

        # Check only SOL/USD remains
        assert handler.subscriptions["ohlc_15"]["symbols"] == ["SOL/USD"]

        # Verify unsubscribe message sent
        handler.websocket.send.assert_called_once()
        sent_data = json.loads(handler.websocket.send.call_args[0][0])

        assert sent_data["method"] == "unsubscribe"
        assert sent_data["params"]["channel"] == "ohlc"
        assert sent_data["params"]["symbol"] == ["BTC/USD", "ETH/USD"]
        assert sent_data["params"]["interval"] == 15

    @pytest.mark.asyncio
    async def test_unsubscribe_all(self, handler):
        """Test unsubscribing all symbols removes subscription key"""
        handler.websocket = AsyncMock()
        handler.is_connected = True

        handler.subscriptions["ohlc_15"] = {"symbols": ["BTC/USD"], "snapshot": True}

        await handler.unsubscribe(["BTC/USD"])

        assert "ohlc_15" not in handler.subscriptions

    @pytest.mark.asyncio
    async def test_parse_subscription_success(self, handler):
        """Test parsing successful subscription response"""
        message = json.dumps(
            {
                "method": "subscribe",
                "success": True,
                "result": {
                    "channel": "ohlc",
                    "interval": 15,
                    "snapshot": True,
                    "symbol": ["BTC/USD"],
                },
                "req_id": 1,
            }
        )

        result = await handler.parse_message(message)

        assert result is not None
        assert result.type == "subscribe"
        assert result.channel == "ohlc"
        assert result.data["channel"] == "ohlc"
        assert result.req_id == 1

    @pytest.mark.asyncio
    async def test_parse_subscription_error(self, handler):
        """Test parsing subscription error"""
        message = json.dumps(
            {
                "method": "subscribe",
                "success": False,
                "error": "Invalid symbol",
                "req_id": 1,
            }
        )

        result = await handler.parse_message(message)

        assert result is not None
        assert result.type == "error"
        assert result.channel == "ohlc"
        assert result.error == "Invalid symbol"
        assert result.req_id == 1

    @pytest.mark.asyncio
    async def test_parse_ohlc_snapshot(self, handler, sample_ohlc_candle):
        """Test parsing OHLC snapshot data"""
        message = json.dumps(
            {"channel": "ohlc", "type": "snapshot", "data": [sample_ohlc_candle]}
        )

        result = await handler.parse_message(message)

        assert result is not None
        assert result.type == "snapshot"
        assert result.channel == "ohlc"
        assert len(result.data) == 1

        ohlc = result.data[0]
        assert isinstance(ohlc, OHLCData)
        assert ohlc.symbol == "BTC/USD"
        assert ohlc.open == Decimal("50000.00")
        assert ohlc.high == Decimal("51000.00")
        assert ohlc.low == Decimal("49500.00")
        assert ohlc.close == Decimal("50500.00")
        assert ohlc.vwap == Decimal("50250.00")
        assert ohlc.trades == 150
        assert ohlc.volume == Decimal("1234.56789")
        assert ohlc.interval == 15

    @pytest.mark.asyncio
    async def test_parse_ohlc_update(self, handler, sample_ohlc_candle):
        """Test parsing OHLC update data"""
        message = json.dumps(
            {"channel": "ohlc", "type": "update", "data": [sample_ohlc_candle]}
        )

        result = await handler.parse_message(message)

        assert result is not None
        assert result.type == "update"
        assert result.channel == "ohlc"
        assert len(result.data) == 1
        assert isinstance(result.data[0], OHLCData)

    @pytest.mark.asyncio
    async def test_parse_multiple_candles(self, handler, sample_ohlc_candle):
        """Test parsing multiple OHLC candles"""
        candle2 = sample_ohlc_candle.copy()
        candle2["symbol"] = "ETH/USD"
        candle2["open"] = "3000.00"

        message = json.dumps(
            {"channel": "ohlc", "type": "update", "data": [sample_ohlc_candle, candle2]}
        )

        result = await handler.parse_message(message)

        assert result is not None
        assert len(result.data) == 2
        assert result.data[0].symbol == "BTC/USD"
        assert result.data[1].symbol == "ETH/USD"
        assert result.data[0].open == Decimal("50000.00")
        assert result.data[1].open == Decimal("3000.00")

    @pytest.mark.asyncio
    async def test_parse_invalid_candle(self, handler):
        """Test handling invalid candle data"""
        message = json.dumps(
            {
                "channel": "ohlc",
                "type": "update",
                "data": [
                    {"invalid": "data"},  # Invalid candle
                    {  # Valid candle
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
                    },
                ],
            }
        )

        result = await handler.parse_message(message)

        assert result is not None
        assert len(result.data) == 1  # Only valid candle
        assert result.data[0].symbol == "BTC/USD"

    @pytest.mark.asyncio
    async def test_parse_error_message(self, handler):
        """Test parsing error messages"""
        message = json.dumps({"error": "Rate limit exceeded"})

        result = await handler.parse_message(message)

        assert result is not None
        assert result.type == "error"
        assert result.channel == "ohlc"
        assert result.error == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_parse_heartbeat(self, handler):
        """Test parsing heartbeat messages"""
        message = json.dumps({"channel": "heartbeat"})

        result = await handler.parse_message(message)
        assert result is None  # Heartbeats return None

    @pytest.mark.asyncio
    async def test_parse_unhandled_message(self, handler):
        """Test parsing unhandled message types"""
        message = json.dumps({"channel": "unknown", "data": "some data"})

        result = await handler.parse_message(message)
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, handler):
        """Test handling invalid JSON"""
        message = "invalid json {"

        result = await handler.parse_message(message)
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_exception_handling(self, handler):
        """Test exception handling in parse_message"""
        message = json.dumps(
            {"channel": "ohlc", "data": None}  # Will cause exception when iterating
        )

        result = await handler.parse_message(message)
        # Should handle exception and return valid message
        assert result is not None
        assert result.type == "update"
        assert result.data == []

    @pytest.mark.asyncio
    async def test_resubscribe(self, handler):
        """Test resubscription after reconnection"""
        handler.websocket = AsyncMock()
        handler.is_connected = True

        handler.subscriptions = {
            "ohlc_15": {"symbols": ["BTC/USD", "ETH/USD"], "snapshot": False}
        }

        await handler._resubscribe()

        # Verify subscribe message sent
        handler.websocket.send.assert_called_once()
        sent_data = json.loads(handler.websocket.send.call_args[0][0])

        assert sent_data["method"] == "subscribe"
        assert sent_data["params"]["symbol"] == ["BTC/USD", "ETH/USD"]
        assert sent_data["params"]["snapshot"] is False

    @pytest.mark.asyncio
    async def test_request_id_increment(self, handler):
        """Test request ID increments correctly"""
        handler.websocket = AsyncMock()
        handler.is_connected = True

        initial_id = handler.request_id

        await handler.subscribe(["BTC/USD"])
        assert handler.request_id == initial_id + 1

        await handler.unsubscribe(["BTC/USD"])
        assert handler.request_id == initial_id + 2

        await handler.subscribe(["ETH/USD"])
        assert handler.request_id == initial_id + 3

    @pytest.mark.asyncio
    async def test_parse_ohlc_with_missing_type(self, handler, sample_ohlc_candle):
        """Test parsing OHLC data without explicit type field"""
        message = json.dumps({"channel": "ohlc", "data": [sample_ohlc_candle]})

        result = await handler.parse_message(message)

        assert result is not None
        assert result.type == "update"  # Default type
        assert result.channel == "ohlc"
        assert len(result.data) == 1

    @pytest.mark.parametrize(
        "method,success,expected_type",
        [
            ("subscribe", True, "subscribe"),
            ("subscribe", False, "error"),
            ("unsubscribe", True, "unsubscribe"),
            ("unsubscribe", False, "error"),
        ],
    )
    @pytest.mark.asyncio
    async def test_parse_method_responses(
        self, handler, method, success, expected_type
    ):
        """Test parsing various method responses"""
        message_data = {"method": method, "success": success, "req_id": 1}

        if success:
            message_data["result"] = {"channel": "ohlc"}
        else:
            message_data["error"] = "Test error"

        message = json.dumps(message_data)
        result = await handler.parse_message(message)

        assert result is not None
        assert result.type == expected_type
        assert result.req_id == 1
