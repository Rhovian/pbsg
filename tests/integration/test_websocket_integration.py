"""
Integration tests for WebSocket data flow using seed data
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.services.data_sources.kraken import KrakenOHLCHandler
from src.services.data_sources.integrated_storage import IntegratedOHLCStorage
from src.services.data_sources.transformer import KrakenToTimescaleTransformer


@pytest.mark.integration
@pytest.mark.asyncio
class TestWebSocketDataFlow:
    """Test complete WebSocket data flow from reception to storage"""

    @pytest.fixture
    async def handler(self):
        """Create Kraken handler"""
        handler = KrakenOHLCHandler()
        yield handler
        if handler.is_connected:
            await handler.disconnect()

    @pytest.fixture
    def mock_storage(self):
        """Create mock integrated storage"""
        engine = MagicMock()
        storage = IntegratedOHLCStorage(engine)
        storage.store_batch = AsyncMock(return_value=(10, 0, 10))
        return storage

    async def test_full_data_pipeline(self, handler, mock_storage, seed_generator):
        """Test complete data pipeline from WebSocket to storage"""
        # Generate market scenario data
        ohlc_data = seed_generator.generate_market_scenario(
            scenario="normal",
            symbol="BTC/USD",
            duration_minutes=60
        )

        # Convert to Kraken messages
        messages = []
        for ohlc in ohlc_data:
            msg = seed_generator.generate_kraken_ohlc_message([ohlc], "update")
            messages.append(json.dumps(msg))

        # Mock WebSocket connection
        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: iter(messages)
        handler.websocket = mock_ws
        handler.is_connected = True

        # Setup callback to capture processed data
        processed_data = []

        async def process_callback(msg):
            if msg.type == "update":
                # Transform data
                for ohlc in msg.data:
                    model = KrakenToTimescaleTransformer.transform(ohlc)
                    if model:
                        processed_data.append(model)

                # Store in batches
                if len(processed_data) >= 10:
                    await mock_storage.store_batch(msg.data[:10])
                    processed_data[:10] = []

        handler.add_callback("ohlc", process_callback)

        # Process messages
        with patch.object(handler, "_handle_reconnection"):
            await handler._handle_messages()

        # Verify data was processed
        assert len(processed_data) > 0
        assert mock_storage.store_batch.called

    async def test_bull_market_scenario(self, handler, seed_generator):
        """Test handling bull market scenario"""
        # Generate bull market data
        ohlc_data = seed_generator.generate_market_scenario(
            scenario="bull",
            symbol="ETH/USD",
            duration_minutes=120
        )

        processed = []

        async def capture_callback(msg):
            if msg.type == "update":
                processed.extend(msg.data)

        handler.add_callback("ohlc", capture_callback)

        # Process each message
        for ohlc in ohlc_data:
            msg = seed_generator.generate_kraken_ohlc_message([ohlc], "update")
            parsed = await handler.parse_message(json.dumps(msg))
            if parsed:
                await handler._process_message(parsed)

        # Verify bull trend (prices generally increasing)
        if len(processed) >= 2:
            first_close = processed[0].close
            last_close = processed[-1].close
            assert last_close > first_close  # Bull market should end higher

    async def test_flash_crash_scenario(self, handler, seed_generator):
        """Test handling flash crash scenario"""
        ohlc_data = seed_generator.generate_market_scenario(
            scenario="flash_crash",
            symbol="BTC/USD",
            duration_minutes=60
        )

        processed = []

        async def capture_callback(msg):
            if msg.type == "update":
                processed.extend(msg.data)

        handler.add_callback("ohlc", capture_callback)

        # Process messages
        for ohlc in ohlc_data:
            msg = seed_generator.generate_kraken_ohlc_message([ohlc], "update")
            parsed = await handler.parse_message(json.dumps(msg))
            if parsed:
                await handler._process_message(parsed)

        # Verify flash crash pattern (drop then recovery)
        if len(processed) >= 3:
            prices = [float(p.close) for p in processed]
            min_price_idx = prices.index(min(prices))
            # Minimum should be in middle portion (flash crash)
            assert 0 < min_price_idx < len(prices) - 1

    async def test_high_volatility_scenario(self, handler, mock_storage, seed_generator):
        """Test handling high volatility market conditions"""
        ohlc_data = seed_generator.generate_market_scenario(
            scenario="volatile",
            symbol="SOL/USD",
            duration_minutes=30
        )

        volume_spikes = 0
        large_ranges = 0

        async def analyze_callback(msg):
            if msg.type == "update":
                for ohlc in msg.data:
                    # Check for volume spikes
                    if ohlc.volume > Decimal("2000"):
                        volume_spikes += 1

                    # Check for large price ranges
                    range_pct = float((ohlc.high - ohlc.low) / ohlc.low) * 100
                    if range_pct > 2:  # More than 2% range
                        large_ranges += 1

        handler.add_callback("ohlc", analyze_callback)

        # Process volatile market data
        for ohlc in ohlc_data:
            msg = seed_generator.generate_kraken_ohlc_message([ohlc], "update")
            parsed = await handler.parse_message(json.dumps(msg))
            if parsed:
                await handler._process_message(parsed)

        # Volatile markets should have spikes and large ranges
        assert volume_spikes > 0
        assert large_ranges > 0

    async def test_multi_symbol_processing(self, handler, seed_generator):
        """Test processing multiple symbols simultaneously"""
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        all_data = {}

        # Generate data for each symbol
        for symbol in symbols:
            all_data[symbol] = seed_generator.generate_ohlc_data(
                symbol=symbol,
                count=5
            )

        processed_by_symbol = {s: [] for s in symbols}

        async def categorize_callback(msg):
            if msg.type == "update":
                for ohlc in msg.data:
                    processed_by_symbol[ohlc.symbol].append(ohlc)

        handler.add_callback("ohlc", categorize_callback)

        # Mix messages from different symbols
        for i in range(5):
            for symbol in symbols:
                ohlc = all_data[symbol][i]
                msg = seed_generator.generate_kraken_ohlc_message([ohlc], "update")
                parsed = await handler.parse_message(json.dumps(msg))
                if parsed:
                    await handler._process_message(parsed)

        # Verify all symbols processed correctly
        for symbol in symbols:
            assert len(processed_by_symbol[symbol]) == 5
            # Verify symbol consistency
            for ohlc in processed_by_symbol[symbol]:
                assert ohlc.symbol == symbol

    async def test_snapshot_then_updates(self, handler, seed_generator):
        """Test handling snapshot followed by updates"""
        # Generate initial snapshot
        snapshot_data = seed_generator.generate_ohlc_data(
            symbol="BTC/USD",
            count=10
        )

        # Generate updates
        update_data = seed_generator.generate_ohlc_data(
            symbol="BTC/USD",
            base_price=float(snapshot_data[-1].close),
            count=5,
            start_time=snapshot_data[-1].interval_begin + timedelta(minutes=15)
        )

        all_processed = []

        async def collect_callback(msg):
            all_processed.append({
                "type": msg.type,
                "data": msg.data
            })

        handler.add_callback("ohlc", collect_callback)

        # Process snapshot
        snapshot_msg = seed_generator.generate_kraken_ohlc_message(
            snapshot_data, "snapshot"
        )
        parsed = await handler.parse_message(json.dumps(snapshot_msg))
        await handler._process_message(parsed)

        # Process updates
        for ohlc in update_data:
            update_msg = seed_generator.generate_kraken_ohlc_message(
                [ohlc], "update"
            )
            parsed = await handler.parse_message(json.dumps(update_msg))
            await handler._process_message(parsed)

        # Verify snapshot and updates processed
        assert len(all_processed) == 6  # 1 snapshot + 5 updates
        assert all_processed[0]["type"] == "snapshot"
        assert len(all_processed[0]["data"]) == 10

        for i in range(1, 6):
            assert all_processed[i]["type"] == "update"

    async def test_error_recovery_flow(self, handler, seed_generator):
        """Test error handling and recovery in data flow"""
        processed_successfully = []
        errors_caught = []

        async def resilient_callback(msg):
            if msg.type == "error":
                errors_caught.append(msg.error)
            elif msg.type == "update":
                for ohlc in msg.data:
                    # Simulate occasional processing errors
                    if ohlc.trades > 200:  # Arbitrary condition
                        raise ValueError("Simulated processing error")
                    processed_successfully.append(ohlc)

        handler.add_callback("ohlc", resilient_callback)

        # Generate mixed messages
        messages = []

        # Add error message
        error_msg = seed_generator.generate_error_message("Test error", req_id=1)
        messages.append(json.dumps(error_msg))

        # Add normal data
        ohlc_data = seed_generator.generate_ohlc_data(count=5)
        for ohlc in ohlc_data:
            # Make some have high trade counts to trigger errors
            if len(messages) % 2 == 0:
                ohlc.trades = 250
            msg = seed_generator.generate_kraken_ohlc_message([ohlc], "update")
            messages.append(json.dumps(msg))

        # Process all messages
        for msg_str in messages:
            parsed = await handler.parse_message(msg_str)
            if parsed:
                try:
                    await handler._process_message(parsed)
                except:
                    pass  # Handler should handle callback errors

        # Verify error handling
        assert len(errors_caught) == 1
        assert errors_caught[0] == "Test error"
        # Some messages should have been processed successfully
        assert len(processed_successfully) > 0

    async def test_subscription_lifecycle(self, handler, seed_generator):
        """Test complete subscription lifecycle"""
        handler.websocket = AsyncMock()
        handler.is_connected = True

        # Subscribe
        await handler.subscribe(["BTC/USD", "ETH/USD"], snapshot=True)

        # Process subscription response
        sub_response = seed_generator.generate_subscription_response(
            success=True,
            symbols=["BTC/USD", "ETH/USD"],
            req_id=handler.request_id
        )
        parsed = await handler.parse_message(json.dumps(sub_response))
        assert parsed.type == "subscribe"

        # Process data
        received_symbols = set()

        async def track_symbols(msg):
            if msg.type == "update":
                for ohlc in msg.data:
                    received_symbols.add(ohlc.symbol)

        handler.add_callback("ohlc", track_symbols)

        # Send data for subscribed symbols
        for symbol in ["BTC/USD", "ETH/USD"]:
            ohlc = seed_generator.generate_ohlc_data(symbol=symbol, count=1)[0]
            msg = seed_generator.generate_kraken_ohlc_message([ohlc], "update")
            parsed = await handler.parse_message(json.dumps(msg))
            await handler._process_message(parsed)

        assert "BTC/USD" in received_symbols
        assert "ETH/USD" in received_symbols

        # Unsubscribe from one symbol
        await handler.unsubscribe(["BTC/USD"])

        # Verify subscription state
        assert "ETH/USD" in handler.subscriptions["ohlc_15"]["symbols"]
        assert "BTC/USD" not in handler.subscriptions["ohlc_15"]["symbols"]