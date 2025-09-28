"""
Unit tests for KrakenToTimescaleTransformer
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from src.services.data_sources.transformer import KrakenToTimescaleTransformer
from src.services.data_sources.types import OHLCData
from src.models.schema import BTCOHLC, ETHOHLC, SOLOHLC


class TestKrakenToTimescaleTransformer:
    """Test KrakenToTimescaleTransformer functionality"""

    @pytest.fixture
    def sample_ohlc_data(self):
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

    def test_transform_btc(self, sample_ohlc_data):
        """Test transforming BTC/USD data"""
        result = KrakenToTimescaleTransformer.transform(sample_ohlc_data)

        assert isinstance(result, BTCOHLC)
        assert result.time == sample_ohlc_data.interval_begin
        assert result.symbol == "BTC/USD"
        assert result.timeframe == "15m"
        assert result.open == sample_ohlc_data.open
        assert result.high == sample_ohlc_data.high
        assert result.low == sample_ohlc_data.low
        assert result.close == sample_ohlc_data.close
        assert result.volume == sample_ohlc_data.volume
        assert result.trades == sample_ohlc_data.trades

    def test_transform_eth(self):
        """Test transforming ETH/USD data"""
        ohlc_data = OHLCData(
            symbol="ETH/USD",
            open=Decimal("3000.00"),
            high=Decimal("3100.00"),
            low=Decimal("2950.00"),
            close=Decimal("3050.00"),
            vwap=Decimal("3025.00"),
            trades=100,
            volume=Decimal("500.123"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        result = KrakenToTimescaleTransformer.transform(ohlc_data)

        assert isinstance(result, ETHOHLC)
        assert result.symbol == "ETH/USD"
        assert result.close == Decimal("3050.00")

    def test_transform_sol(self):
        """Test transforming SOL/USD data"""
        ohlc_data = OHLCData(
            symbol="SOL/USD",
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("98.00"),
            close=Decimal("102.00"),
            vwap=Decimal("101.00"),
            trades=50,
            volume=Decimal("1000.0"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        result = KrakenToTimescaleTransformer.transform(ohlc_data)

        assert isinstance(result, SOLOHLC)
        assert result.symbol == "SOL/USD"
        assert result.close == Decimal("102.00")

    def test_transform_unsupported_symbol(self):
        """Test transforming unsupported symbol returns None"""
        ohlc_data = OHLCData(
            symbol="DOGE/USD",
            open=Decimal("0.10"),
            high=Decimal("0.11"),
            low=Decimal("0.09"),
            close=Decimal("0.105"),
            vwap=Decimal("0.10"),
            trades=10,
            volume=Decimal("10000.0"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        result = KrakenToTimescaleTransformer.transform(ohlc_data)
        assert result is None

    def test_transform_batch(self):
        """Test batch transformation"""
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
            ),
            OHLCData(
                symbol="ETH/USD",
                open=Decimal("3000.00"),
                high=Decimal("3100.00"),
                low=Decimal("2950.00"),
                close=Decimal("3050.00"),
                vwap=Decimal("3025.00"),
                trades=100,
                volume=Decimal("500.123"),
                interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                interval=15,
            ),
            OHLCData(
                symbol="DOGE/USD",  # Unsupported
                open=Decimal("0.10"),
                high=Decimal("0.11"),
                low=Decimal("0.09"),
                close=Decimal("0.105"),
                vwap=Decimal("0.10"),
                trades=10,
                volume=Decimal("10000.0"),
                interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                interval=15,
            ),
        ]

        results = KrakenToTimescaleTransformer.transform_batch(ohlc_list)

        assert len(results) == 2  # DOGE should be skipped
        assert isinstance(results[0], BTCOHLC)
        assert isinstance(results[1], ETHOHLC)

    def test_to_dict(self, sample_ohlc_data):
        """Test converting OHLC data to dictionary"""
        result = KrakenToTimescaleTransformer.to_dict(sample_ohlc_data)

        assert isinstance(result, dict)
        assert result["time"] == sample_ohlc_data.interval_begin
        assert result["symbol"] == "BTC/USD"
        assert result["timeframe"] == "15m"
        assert result["open"] == sample_ohlc_data.open
        assert result["high"] == sample_ohlc_data.high
        assert result["low"] == sample_ohlc_data.low
        assert result["close"] == sample_ohlc_data.close
        assert result["volume"] == sample_ohlc_data.volume
        assert result["trades"] == sample_ohlc_data.trades

    def test_get_table_name(self):
        """Test getting table names for symbols"""
        assert KrakenToTimescaleTransformer.get_table_name("BTC/USD") == "btc_ohlc"
        assert KrakenToTimescaleTransformer.get_table_name("ETH/USD") == "eth_ohlc"
        assert KrakenToTimescaleTransformer.get_table_name("SOL/USD") == "sol_ohlc"
        assert KrakenToTimescaleTransformer.get_table_name("DOGE/USD") is None

    def test_is_supported_symbol(self):
        """Test checking if symbol is supported"""
        assert KrakenToTimescaleTransformer.is_supported_symbol("BTC/USD") is True
        assert KrakenToTimescaleTransformer.is_supported_symbol("ETH/USD") is True
        assert KrakenToTimescaleTransformer.is_supported_symbol("SOL/USD") is True
        assert KrakenToTimescaleTransformer.is_supported_symbol("DOGE/USD") is False

    def test_transform_preserves_precision(self):
        """Test that decimal precision is preserved"""
        ohlc_data = OHLCData(
            symbol="BTC/USD",
            open=Decimal("50123.12345678"),
            high=Decimal("51234.87654321"),
            low=Decimal("49876.11111111"),
            close=Decimal("50555.99999999"),
            vwap=Decimal("50250.55555555"),
            trades=150,
            volume=Decimal("1234.56789012"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        result = KrakenToTimescaleTransformer.transform(ohlc_data)

        assert result.open == Decimal("50123.12345678")
        assert result.high == Decimal("51234.87654321")
        assert result.low == Decimal("49876.11111111")
        assert result.close == Decimal("50555.99999999")
        assert result.volume == Decimal("1234.56789012")

    def test_transform_handles_zero_values(self):
        """Test handling zero values"""
        ohlc_data = OHLCData(
            symbol="BTC/USD",
            open=Decimal("50000.00"),
            high=Decimal("50000.00"),
            low=Decimal("50000.00"),
            close=Decimal("50000.00"),
            vwap=Decimal("50000.00"),
            trades=0,
            volume=Decimal("0.0"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        result = KrakenToTimescaleTransformer.transform(ohlc_data)

        assert result is not None
        assert result.trades == 0
        assert result.volume == Decimal("0.0")

    def test_symbol_model_map_completeness(self):
        """Test that SYMBOL_MODEL_MAP matches expected models"""
        expected_mapping = {
            "BTC/USD": BTCOHLC,
            "ETH/USD": ETHOHLC,
            "SOL/USD": SOLOHLC,
        }

        assert KrakenToTimescaleTransformer.SYMBOL_MODEL_MAP == expected_mapping

    @pytest.mark.parametrize(
        "symbol,expected_model",
        [
            ("BTC/USD", BTCOHLC),
            ("ETH/USD", ETHOHLC),
            ("SOL/USD", SOLOHLC),
        ],
    )
    def test_transform_returns_correct_model(self, symbol, expected_model):
        """Test that transform returns the correct model type"""
        ohlc_data = OHLCData(
            symbol=symbol,
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("98.00"),
            close=Decimal("102.00"),
            vwap=Decimal("101.00"),
            trades=50,
            volume=Decimal("1000.0"),
            interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            interval=15,
        )

        result = KrakenToTimescaleTransformer.transform(ohlc_data)
        assert isinstance(result, expected_model)

    def test_batch_transform_preserves_order(self):
        """Test that batch transformation preserves order"""
        ohlc_list = [
            OHLCData(
                symbol="ETH/USD",
                open=Decimal("3000.00"),
                high=Decimal("3100.00"),
                low=Decimal("2950.00"),
                close=Decimal("3050.00"),
                vwap=Decimal("3025.00"),
                trades=100,
                volume=Decimal("500.123"),
                interval_begin=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                interval=15,
            ),
            OHLCData(
                symbol="BTC/USD",
                open=Decimal("50000.00"),
                high=Decimal("51000.00"),
                low=Decimal("49500.00"),
                close=Decimal("50500.00"),
                vwap=Decimal("50250.00"),
                trades=150,
                volume=Decimal("1234.56789"),
                interval_begin=datetime(2024, 1, 1, 12, 15, 0, tzinfo=timezone.utc),
                interval=15,
            ),
            OHLCData(
                symbol="SOL/USD",
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("98.00"),
                close=Decimal("102.00"),
                vwap=Decimal("101.00"),
                trades=50,
                volume=Decimal("1000.0"),
                interval_begin=datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
                interval=15,
            ),
        ]

        results = KrakenToTimescaleTransformer.transform_batch(ohlc_list)

        assert len(results) == 3
        assert isinstance(results[0], ETHOHLC)
        assert isinstance(results[1], BTCOHLC)
        assert isinstance(results[2], SOLOHLC)
        assert results[0].symbol == "ETH/USD"
        assert results[1].symbol == "BTC/USD"
        assert results[2].symbol == "SOL/USD"
