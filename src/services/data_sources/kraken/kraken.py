import json
from typing import List, Optional
from loguru import logger

from ..base import BaseWebSocketHandler
from ..types import OHLCData, WebSocketMessage


class KrakenOHLCHandler(BaseWebSocketHandler):
    """Kraken WebSocket handler for 15-minute OHLC data"""

    def __init__(self) -> None:
        super().__init__("wss://ws.kraken.com/v2")
        self.request_id: int = 0

    async def subscribe(self, symbols: List[str], snapshot: bool = True) -> None:
        """Subscribe to 15-minute OHLC data for specified symbols"""
        self.request_id += 1
        message = {
            "method": "subscribe",
            "params": {
                "channel": "ohlc",
                "symbol": symbols,
                "interval": 15,  # Fixed 15-minute interval
                "snapshot": snapshot,
            },
            "req_id": self.request_id,
        }

        # Store subscription info for reconnection
        sub_key = "ohlc_15"
        if sub_key not in self.subscriptions:
            self.subscriptions[sub_key] = {"symbols": [], "snapshot": snapshot}

        # Add symbols to subscription (avoid duplicates)
        for symbol in symbols:
            if symbol not in self.subscriptions[sub_key]["symbols"]:
                self.subscriptions[sub_key]["symbols"].append(symbol)

        await self.send_message(message)
        logger.info(f"Subscribed to 15-minute OHLC data for {symbols}")

    async def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from 15-minute OHLC data"""
        self.request_id += 1
        message = {
            "method": "unsubscribe",
            "params": {
                "channel": "ohlc",
                "symbol": symbols,
                "interval": 15,  # Fixed 15-minute interval
            },
            "req_id": self.request_id,
        }

        # Remove from subscriptions
        sub_key = "ohlc_15"
        if sub_key in self.subscriptions:
            for symbol in symbols:
                if symbol in self.subscriptions[sub_key]["symbols"]:
                    self.subscriptions[sub_key]["symbols"].remove(symbol)

            # Remove subscription key if no symbols left
            if not self.subscriptions[sub_key]["symbols"]:
                del self.subscriptions[sub_key]

        await self.send_message(message)
        logger.info(f"Unsubscribed from 15-minute OHLC data for {symbols}")

    async def parse_message(self, message: str) -> Optional[WebSocketMessage]:
        """Parse Kraken WebSocket message"""
        try:
            data = json.loads(message)

            # Handle subscription acknowledgment
            if "method" in data and data["method"] in ["subscribe", "unsubscribe"]:
                msg_type = data["method"]
                if "success" in data and data["success"]:
                    logger.debug(f"{msg_type} acknowledgment: {data}")
                    return WebSocketMessage(
                        type=msg_type,
                        channel="ohlc",
                        data=data.get("result"),
                        req_id=data.get("req_id"),
                    )
                elif "error" in data:
                    return WebSocketMessage(
                        type="error",
                        channel="ohlc",
                        data=None,
                        error=data["error"],
                        req_id=data.get("req_id"),
                    )

            # Handle OHLC data
            if "channel" in data and data["channel"] == "ohlc":
                msg_type = data.get("type", "update")
                ohlc_data = []

                # Parse OHLC candles
                if "data" in data and isinstance(data["data"], list):
                    for candle in data["data"]:
                        try:
                            # Only add successfully parsed OHLC data
                            ohlc = OHLCData.from_kraken(candle)
                            ohlc_data.append(ohlc)
                        except Exception as e:
                            logger.error(f"Error parsing OHLC candle: {e}")
                            # Don't add malformed data to ohlc_data list

                return WebSocketMessage(type=msg_type, channel="ohlc", data=ohlc_data)

            # Handle error messages
            if "error" in data:
                return WebSocketMessage(
                    type="error", channel="ohlc", data=None, error=data["error"]
                )

            # Handle heartbeat - server status message, no response needed
            if "channel" in data and data["channel"] == "heartbeat":
                logger.debug("Received heartbeat")
                return None

            # Unhandled message type
            logger.debug(f"Unhandled message: {data}")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None

    async def _resubscribe(self) -> None:
        """Resubscribe to all previous subscriptions after reconnection"""
        for sub_key, sub_info in self.subscriptions.copy().items():
            if sub_info["symbols"]:
                await self.subscribe(
                    symbols=sub_info["symbols"], snapshot=sub_info["snapshot"]
                )
