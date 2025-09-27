import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
import websockets
from websockets.client import WebSocketClientProtocol
from loguru import logger

from .types import OHLCData, WebSocketMessage


class BaseWebSocketHandler(ABC):
    """Base class for WebSocket data source handlers"""

    def __init__(self, url: str):
        self.url = url
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.subscriptions: Dict[str, Any] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5
        self._tasks: List[asyncio.Task] = []
        self.is_paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Start unpaused

    @abstractmethod
    async def subscribe(self, symbols: List[str], snapshot: bool = True) -> None:
        """Subscribe to data feed"""
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from data feed"""
        pass

    @abstractmethod
    async def parse_message(self, message: str) -> Optional[WebSocketMessage]:
        """Parse incoming message from WebSocket"""
        pass

    async def connect(self) -> None:
        """Establish WebSocket connection"""
        try:
            self.websocket = await websockets.connect(self.url)
            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info(f"Connected to {self.url}")

            # Start message handler
            task = asyncio.create_task(self._handle_messages())
            self._tasks.append(task)

        except Exception as e:
            logger.error(f"Failed to connect to {self.url}: {e}")
            await self._handle_reconnection()

    async def disconnect(self) -> None:
        """Close WebSocket connection"""
        self.is_connected = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        logger.info(f"Disconnected from {self.url}")

    async def _handle_messages(self) -> None:
        """Handle incoming WebSocket messages"""
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                try:
                    parsed = await self.parse_message(message)
                    if parsed:
                        await self._process_message(parsed)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            await self._handle_reconnection()
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            await self._handle_reconnection()

    async def _process_message(self, message: WebSocketMessage) -> None:
        """Process parsed WebSocket message"""
        # Wait if paused
        await self._pause_event.wait()

        # Handle different message types
        if message.type == "error":
            logger.error(f"Received error message: {message.error}")
            return

        # Notify callbacks
        if message.channel in self.callbacks:
            for callback in self.callbacks[message.channel]:
                try:
                    await callback(message)
                except Exception as e:
                    logger.error(f"Error in callback: {e}")

    async def _handle_reconnection(self) -> None:
        """Handle reconnection logic"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts reached ({self.max_reconnect_attempts})")
            return

        self.reconnect_attempts += 1
        logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")

        await asyncio.sleep(self.reconnect_delay)
        await self.connect()

        # Resubscribe to previous subscriptions
        if self.is_connected and self.subscriptions:
            await self._resubscribe()

    async def _resubscribe(self) -> None:
        """Resubscribe to previous subscriptions after reconnection"""
        logger.info("Resubscribing to previous subscriptions")
        # Implementation depends on specific exchange
        pass

    def add_callback(self, channel: str, callback: Callable) -> None:
        """Add callback for specific channel"""
        if channel not in self.callbacks:
            self.callbacks[channel] = []
        self.callbacks[channel].append(callback)

    def remove_callback(self, channel: str, callback: Callable) -> None:
        """Remove callback for specific channel"""
        if channel in self.callbacks:
            self.callbacks[channel].remove(callback)
            if not self.callbacks[channel]:
                del self.callbacks[channel]

    async def pause(self) -> None:
        """Pause message processing"""
        if not self.is_paused:
            self.is_paused = True
            self._pause_event.clear()
            logger.info("WebSocket message processing paused")

    async def resume(self) -> None:
        """Resume message processing"""
        if self.is_paused:
            self.is_paused = False
            self._pause_event.set()
            logger.info("WebSocket message processing resumed")

    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send message through WebSocket"""
        if not self.websocket or not self.is_connected:
            logger.warning("WebSocket not connected")
            return

        try:
            await self.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message: {e}")