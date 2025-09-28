"""
Unit tests for BaseWebSocketHandler
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import websockets

from src.services.data_sources.base import BaseWebSocketHandler
from src.services.data_sources.types import WebSocketMessage


class ConcreteWebSocketHandler(BaseWebSocketHandler):
    """Concrete implementation for testing"""

    async def subscribe(self, symbols, snapshot=True):
        self.subscriptions["test"] = {"symbols": symbols, "snapshot": snapshot}
        await self.send_message({"method": "subscribe", "symbols": symbols})

    async def unsubscribe(self, symbols):
        if "test" in self.subscriptions:
            del self.subscriptions["test"]
        await self.send_message({"method": "unsubscribe", "symbols": symbols})

    async def parse_message(self, message):
        try:
            data = json.loads(message)
            if "error" in data:
                return WebSocketMessage(
                    type="error", channel="test", data=None, error=data["error"]
                )
            return WebSocketMessage(type="update", channel="test", data=data)
        except json.JSONDecodeError:
            return None


@pytest.mark.asyncio
class TestBaseWebSocketHandler:
    """Test BaseWebSocketHandler functionality"""

    @pytest.fixture
    def handler(self):
        """Create handler instance"""
        return ConcreteWebSocketHandler("wss://test.example.com")

    @pytest.fixture
    def mock_connect(self):
        """Mock websockets.connect"""
        with patch("websockets.connect") as mock:
            yield mock

    async def test_initialization(self, handler):
        """Test handler initialization"""
        assert handler.url == "wss://test.example.com"
        assert handler.websocket is None
        assert handler.subscriptions == {}
        assert handler.callbacks == {}
        assert handler.is_connected is False
        assert handler.reconnect_attempts == 0
        assert handler.max_reconnect_attempts == 10
        assert handler.reconnect_delay == 5
        assert handler._tasks == []
        assert handler.is_paused is False
        assert handler._pause_event.is_set()

    async def test_successful_connection(self, handler, mock_connect):
        """Test successful WebSocket connection"""
        mock_ws = AsyncMock()
        mock_ws.__aiter__ = AsyncMock(return_value=iter([]))

        # Make mock_connect return a proper awaitable
        async def mock_connect_func(url):
            return mock_ws

        mock_connect.side_effect = mock_connect_func

        await handler.connect()

        try:
            assert handler.is_connected is True
            assert handler.websocket == mock_ws
            assert handler.reconnect_attempts == 0
            mock_connect.assert_called_once_with("wss://test.example.com")
            assert len(handler._tasks) == 1
        finally:
            # Clean up the background task
            await handler.disconnect()

    async def test_connection_failure(self, handler, mock_connect):
        """Test connection failure handling"""
        mock_connect.side_effect = Exception("Connection failed")

        with patch.object(handler, "_handle_reconnection") as mock_reconnect:
            await handler.connect()
            mock_reconnect.assert_called_once()

    async def test_disconnect(self, handler, mock_connect):
        """Test disconnection"""
        mock_ws = AsyncMock()
        handler.websocket = mock_ws
        handler.is_connected = True

        # Create mock tasks - use regular Mock since cancel() is not async
        mock_task = MagicMock()
        handler._tasks = [mock_task]

        await handler.disconnect()

        assert handler.is_connected is False
        assert handler.websocket is None
        mock_task.cancel.assert_called_once()
        mock_ws.close.assert_called_once()

    async def test_send_message(self, handler):
        """Test sending messages"""
        mock_ws = AsyncMock()
        handler.websocket = mock_ws
        handler.is_connected = True

        message = {"test": "data"}
        await handler.send_message(message)

        mock_ws.send.assert_called_once_with(json.dumps(message))

    async def test_send_message_not_connected(self, handler):
        """Test sending message when not connected"""
        handler.is_connected = False
        message = {"test": "data"}

        # Should not raise error, just log warning
        await handler.send_message(message)

    async def test_add_callback(self, handler):
        """Test adding callbacks"""
        callback = AsyncMock()
        handler.add_callback("test_channel", callback)

        assert "test_channel" in handler.callbacks
        assert callback in handler.callbacks["test_channel"]

    async def test_remove_callback(self, handler):
        """Test removing callbacks"""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        handler.add_callback("test_channel", callback1)
        handler.add_callback("test_channel", callback2)

        handler.remove_callback("test_channel", callback1)

        assert callback1 not in handler.callbacks["test_channel"]
        assert callback2 in handler.callbacks["test_channel"]

    async def test_remove_last_callback(self, handler):
        """Test removing last callback removes channel"""
        callback = AsyncMock()
        handler.add_callback("test_channel", callback)
        handler.remove_callback("test_channel", callback)

        assert "test_channel" not in handler.callbacks

    async def test_pause_resume(self, handler):
        """Test pause and resume functionality"""
        assert handler.is_paused is False
        assert handler._pause_event.is_set()

        await handler.pause()
        assert handler.is_paused is True
        assert not handler._pause_event.is_set()

        await handler.resume()
        assert handler.is_paused is False
        assert handler._pause_event.is_set()

    async def test_process_message_with_callback(self, handler):
        """Test processing message with registered callback"""
        callback = AsyncMock()
        handler.add_callback("test", callback)

        message = WebSocketMessage(type="update", channel="test", data={"value": 123})

        await handler._process_message(message)
        callback.assert_called_once_with(message)

    async def test_process_error_message(self, handler):
        """Test processing error message"""
        message = WebSocketMessage(
            type="error", channel="test", data=None, error="Test error"
        )

        # Should not raise, just log
        await handler._process_message(message)

    async def test_process_message_callback_error(self, handler):
        """Test callback error handling"""
        callback = AsyncMock(side_effect=Exception("Callback failed"))
        handler.add_callback("test", callback)

        message = WebSocketMessage(type="update", channel="test", data={"value": 123})

        # Should not raise, error should be logged
        await handler._process_message(message)
        callback.assert_called_once()

    async def test_process_message_while_paused(self, handler):
        """Test message processing waits when paused"""
        # Create fresh event for this test instance
        handler._pause_event = asyncio.Event()
        handler._pause_event.clear()  # Start paused
        handler.is_paused = True

        callback = AsyncMock()
        handler.add_callback("test", callback)

        message = WebSocketMessage(type="update", channel="test", data={"value": 123})

        # Create task with current event loop
        process_task = asyncio.create_task(handler._process_message(message))

        # Give it a moment
        await asyncio.sleep(0.01)

        # Callback should not be called yet
        callback.assert_not_called()

        # Resume by setting the event
        handler.is_paused = False
        handler._pause_event.set()

        # Wait for processing to complete
        await process_task

        # Now callback should be called
        callback.assert_called_once_with(message)

    @pytest.mark.parametrize(
        "reconnect_attempt,should_reconnect",
        [
            (0, True),
            (5, True),
            (9, True),
            (10, False),
        ],
    )
    async def test_reconnection_attempts(
        self, handler, reconnect_attempt, should_reconnect
    ):
        """Test reconnection attempt limits"""
        handler.reconnect_attempts = reconnect_attempt

        with patch.object(handler, "connect") as mock_connect:
            with patch("asyncio.sleep"):
                await handler._handle_reconnection()

                if should_reconnect:
                    mock_connect.assert_called_once()
                    assert handler.reconnect_attempts == reconnect_attempt + 1
                else:
                    mock_connect.assert_not_called()

    async def test_resubscribe_after_reconnection(self, handler, mock_connect):
        """Test resubscription after reconnection"""
        handler.subscriptions = {"test": {"symbols": ["BTC/USD"], "snapshot": True}}

        # Mock successful connection
        mock_ws = AsyncMock()
        mock_ws.__aiter__ = AsyncMock(return_value=iter([]))

        async def mock_connect_func(url):
            return mock_ws

        mock_connect.side_effect = mock_connect_func

        with patch.object(handler, "_resubscribe") as mock_resubscribe:
            with patch("asyncio.sleep"):
                await handler._handle_reconnection()
                mock_resubscribe.assert_called_once()

        # Clean up
        await handler.disconnect()

    async def test_handle_messages_connection_closed(self, handler, mock_connect):
        """Test handling connection closed during message processing"""
        mock_ws = AsyncMock()

        # Simulate connection closed exception
        async def message_generator():
            yield '{"data": "test"}'
            raise websockets.exceptions.ConnectionClosed(None, None)

        mock_ws.__aiter__ = lambda self: message_generator()
        handler.websocket = mock_ws

        with patch.object(handler, "_handle_reconnection") as mock_reconnect:
            await handler._handle_messages()
            mock_reconnect.assert_called_once()

    async def test_handle_messages_parse_error(self, handler):
        """Test handling parse errors in messages"""
        mock_ws = AsyncMock()

        async def message_generator():
            yield '{"valid": "json"}'
            yield "invalid json"
            yield '{"another": "valid"}'

        mock_ws.__aiter__ = lambda self: message_generator()
        handler.websocket = mock_ws

        processed = []

        async def capture_message(msg):
            processed.append(msg.data)

        handler.add_callback("test", capture_message)

        # Run for a short time then stop
        task = asyncio.create_task(handler._handle_messages())
        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have processed valid messages only
        assert len(processed) == 2

    async def test_subscribe_unsubscribe(self, handler):
        """Test subscribe and unsubscribe methods"""
        mock_ws = AsyncMock()
        handler.websocket = mock_ws
        handler.is_connected = True

        # Test subscribe
        await handler.subscribe(["BTC/USD", "ETH/USD"], snapshot=True)

        assert "test" in handler.subscriptions
        assert handler.subscriptions["test"]["symbols"] == ["BTC/USD", "ETH/USD"]
        assert handler.subscriptions["test"]["snapshot"] is True

        # Verify message sent
        mock_ws.send.assert_called()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["method"] == "subscribe"
        assert sent_data["symbols"] == ["BTC/USD", "ETH/USD"]

        # Test unsubscribe
        mock_ws.reset_mock()
        await handler.unsubscribe(["BTC/USD", "ETH/USD"])

        assert "test" not in handler.subscriptions

        # Verify unsubscribe message sent
        mock_ws.send.assert_called()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["method"] == "unsubscribe"

    async def test_concurrent_callbacks(self, handler):
        """Test multiple callbacks executed sequentially"""
        results = []

        async def callback1(msg):
            results.append("callback1")

        async def callback2(msg):
            results.append("callback2")

        handler.add_callback("test", callback1)
        handler.add_callback("test", callback2)

        message = WebSocketMessage(type="update", channel="test", data={"value": 123})

        await handler._process_message(message)

        # Callbacks execute in order they were added
        assert results == ["callback1", "callback2"]
