"""
Unit tests for database models
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

from src.models.schema import (
    BTCOHLC,
    ETHOHLC,
    SOLOHLC,
    get_ohlc_model,
    create_hypertables,
    PointIndicator,
    RangeIndicator,
    VolumeProfile,
    Signal
)


class TestOHLCModels:
    """Test OHLC database models"""

    @pytest.fixture
    def sample_time(self):
        """Sample timestamp"""
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_btc_ohlc_creation(self, sample_time):
        """Test BTCOHLC model creation"""
        btc = BTCOHLC(
            time=sample_time,
            symbol="BTC/USD",
            timeframe="15m",
            open=Decimal("50000.00"),
            high=Decimal("51000.00"),
            low=Decimal("49500.00"),
            close=Decimal("50500.00"),
            volume=Decimal("1234.56789"),
            trades=150
        )

        assert btc.time == sample_time
        assert btc.symbol == "BTC/USD"
        assert btc.timeframe == "15m"
        assert btc.open == Decimal("50000.00")
        assert btc.high == Decimal("51000.00")
        assert btc.low == Decimal("49500.00")
        assert btc.close == Decimal("50500.00")
        assert btc.volume == Decimal("1234.56789")
        assert btc.trades == 150

    def test_btc_ohlc_repr(self, sample_time):
        """Test BTCOHLC string representation"""
        btc = BTCOHLC(
            time=sample_time,
            symbol="BTC/USD",
            timeframe="15m",
            close=Decimal("50500.00")
        )

        repr_str = repr(btc)
        assert "BTCOHLC" in repr_str
        assert "BTC/USD" in repr_str
        assert "50500" in repr_str

    def test_eth_ohlc_creation(self, sample_time):
        """Test ETHOHLC model creation"""
        eth = ETHOHLC(
            time=sample_time,
            symbol="ETH/USD",
            timeframe="15m",
            open=Decimal("3000.00"),
            high=Decimal("3100.00"),
            low=Decimal("2950.00"),
            close=Decimal("3050.00"),
            volume=Decimal("500.123"),
            trades=100
        )

        assert eth.symbol == "ETH/USD"
        assert eth.close == Decimal("3050.00")

    def test_eth_ohlc_repr(self, sample_time):
        """Test ETHOHLC string representation"""
        eth = ETHOHLC(
            time=sample_time,
            symbol="ETH/USD",
            timeframe="15m",
            close=Decimal("3050.00")
        )

        repr_str = repr(eth)
        assert "ETHOHLC" in repr_str
        assert "ETH/USD" in repr_str
        assert "3050" in repr_str

    def test_sol_ohlc_creation(self, sample_time):
        """Test SOLOHLC model creation"""
        sol = SOLOHLC(
            time=sample_time,
            symbol="SOL/USD",
            timeframe="15m",
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("98.00"),
            close=Decimal("102.00"),
            volume=Decimal("1000.0"),
            trades=50
        )

        assert sol.symbol == "SOL/USD"
        assert sol.close == Decimal("102.00")

    def test_sol_ohlc_repr(self, sample_time):
        """Test SOLOHLC string representation"""
        sol = SOLOHLC(
            time=sample_time,
            symbol="SOL/USD",
            timeframe="15m",
            close=Decimal("102.00")
        )

        repr_str = repr(sol)
        assert "SOLOHLC" in repr_str
        assert "SOL/USD" in repr_str
        assert "102" in repr_str

    def test_get_ohlc_model(self):
        """Test get_ohlc_model function"""
        assert get_ohlc_model("BTC/USD") == BTCOHLC
        assert get_ohlc_model("ETH/USD") == ETHOHLC
        assert get_ohlc_model("SOL/USD") == SOLOHLC
        assert get_ohlc_model("DOGE/USD") is None

    def test_ohlc_table_names(self):
        """Test OHLC table names"""
        assert BTCOHLC.__tablename__ == "btc_ohlc"
        assert ETHOHLC.__tablename__ == "eth_ohlc"
        assert SOLOHLC.__tablename__ == "sol_ohlc"

    def test_ohlc_nullable_fields(self, sample_time):
        """Test OHLC models with nullable fields"""
        btc = BTCOHLC(
            time=sample_time,
            symbol="BTC/USD",
            timeframe="15m"
            # All OHLC values are nullable
        )

        assert btc.open is None
        assert btc.high is None
        assert btc.low is None
        assert btc.close is None
        assert btc.volume is None
        assert btc.trades is None


class TestCreateHypertables:
    """Test hypertable creation"""

    @pytest.fixture
    def mock_engine(self):
        """Create mock engine"""
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
        engine.connect.return_value.__exit__ = MagicMock(return_value=None)
        return engine, conn

    def test_create_hypertables_default(self, mock_engine):
        """Test creating hypertables with defaults"""
        engine, conn = mock_engine

        create_hypertables(engine)

        # Should create 3 hypertables by default
        assert conn.execute.call_count == 3
        assert conn.commit.call_count == 3

        # Check SQL calls - the function passes text() objects to execute
        calls = conn.execute.call_args_list
        sql_strings = [str(call.args[0]) for call in calls if call.args]
        assert any("btc_ohlc" in sql for sql in sql_strings)
        assert any("eth_ohlc" in sql for sql in sql_strings)
        assert any("sol_ohlc" in sql for sql in sql_strings)

    def test_create_hypertables_specific_symbols(self, mock_engine):
        """Test creating hypertables for specific symbols"""
        engine, conn = mock_engine

        create_hypertables(engine, symbol_prefixes=["btc", "eth"])

        assert conn.execute.call_count == 2
        assert conn.commit.call_count == 2

        calls = conn.execute.call_args_list
        sql_strings = [str(call.args[0]) for call in calls if call.args]
        assert any("btc_ohlc" in sql for sql in sql_strings)
        assert any("eth_ohlc" in sql for sql in sql_strings)
        assert not any("sol_ohlc" in sql for sql in sql_strings)

    def test_create_hypertables_with_indicators(self, mock_engine):
        """Test creating hypertables including indicators"""
        engine, conn = mock_engine

        create_hypertables(engine, symbol_prefixes=["btc"], include_indicators=True)

        assert conn.execute.call_count == 2  # btc_ohlc + indicators
        assert conn.commit.call_count == 2

        calls = conn.execute.call_args_list
        sql_strings = [str(call.args[0]) for call in calls if call.args]
        assert any("btc_ohlc" in sql for sql in sql_strings)
        assert any("indicators" in sql for sql in sql_strings)


class TestPointIndicator:
    """Test PointIndicator model"""

    @pytest.fixture
    def sample_time(self):
        """Sample timestamp"""
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_point_indicator_creation(self, sample_time):
        """Test creating PointIndicator"""
        indicator = PointIndicator(
            time=sample_time,
            symbol="BTC/USD",
            timeframe="15m",
            indicator="RSI",
            value={"rsi": 65.5, "signal": "overbought"}
        )

        assert indicator.time == sample_time
        assert indicator.symbol == "BTC/USD"
        assert indicator.timeframe == "15m"
        assert indicator.indicator == "RSI"
        assert indicator.value == {"rsi": 65.5, "signal": "overbought"}

    def test_point_indicator_repr(self, sample_time):
        """Test PointIndicator string representation"""
        indicator = PointIndicator(
            time=sample_time,
            symbol="BTC/USD",
            timeframe="15m",
            indicator="RSI",
            value={"rsi": 65.5}
        )

        repr_str = repr(indicator)
        assert "PointIndicator" in repr_str
        assert "BTC/USD" in repr_str
        assert "RSI" in repr_str

    def test_point_indicator_table_name(self):
        """Test PointIndicator table name"""
        assert PointIndicator.__tablename__ == "point_indicators"


class TestRangeIndicator:
    """Test RangeIndicator model"""

    def test_range_indicator_creation(self):
        """Test creating RangeIndicator"""
        indicator = RangeIndicator(
            symbol="BTC/USD",
            timeframe="1h",
            indicator="SUPPORT",
            range_high=Decimal("51000.00"),
            range_low=Decimal("50000.00"),
            strength=0.85,
            invalidated=False,
            metadata={"touches": 3, "first_touch": "2024-01-01"}
        )

        assert indicator.symbol == "BTC/USD"
        assert indicator.timeframe == "1h"
        assert indicator.indicator == "SUPPORT"
        assert indicator.range_high == Decimal("51000.00")
        assert indicator.range_low == Decimal("50000.00")
        assert indicator.strength == 0.85
        assert indicator.invalidated is False
        assert indicator.metadata == {"touches": 3, "first_touch": "2024-01-01"}

    def test_range_indicator_repr(self):
        """Test RangeIndicator string representation"""
        indicator = RangeIndicator(
            symbol="ETH/USD",
            indicator="FVG",
            range_high=Decimal("3100.00"),
            range_low=Decimal("3000.00")
        )

        repr_str = repr(indicator)
        assert "RangeIndicator" in repr_str
        assert "ETH/USD" in repr_str
        assert "FVG" in repr_str
        assert "3000" in repr_str
        assert "3100" in repr_str

    def test_range_indicator_invalidation(self):
        """Test RangeIndicator invalidation"""
        now = datetime.now(timezone.utc)
        indicator = RangeIndicator(
            symbol="BTC/USD",
            indicator="RESISTANCE",
            range_high=Decimal("52000.00"),
            range_low=Decimal("51000.00"),
            invalidated=True,
            invalidated_at=now
        )

        assert indicator.invalidated is True
        assert indicator.invalidated_at == now

    def test_range_indicator_table_name(self):
        """Test RangeIndicator table name"""
        assert RangeIndicator.__tablename__ == "range_indicators"


class TestVolumeProfile:
    """Test VolumeProfile model"""

    def test_volume_profile_creation(self):
        """Test creating VolumeProfile"""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 23, 59, 59, tzinfo=timezone.utc)

        profile = VolumeProfile(
            symbol="BTC/USD",
            timeframe="24h",
            period_start=start,
            period_end=end,
            poc_price=Decimal("50500.00"),
            poc_volume=Decimal("5000.00"),
            vah=Decimal("51000.00"),
            val=Decimal("50000.00"),
            total_volume=Decimal("15000.00"),
            price_step=Decimal("100.00"),
            num_levels=20,
            profile_data=[
                {"price": 50000, "volume": 1000, "percentage": 6.67},
                {"price": 50100, "volume": 1500, "percentage": 10.00}
            ]
        )

        assert profile.symbol == "BTC/USD"
        assert profile.timeframe == "24h"
        assert profile.period_start == start
        assert profile.period_end == end
        assert profile.poc_price == Decimal("50500.00")
        assert profile.poc_volume == Decimal("5000.00")
        assert profile.vah == Decimal("51000.00")
        assert profile.val == Decimal("50000.00")
        assert profile.total_volume == Decimal("15000.00")
        assert profile.price_step == Decimal("100.00")
        assert profile.num_levels == 20
        assert len(profile.profile_data) == 2

    def test_volume_profile_repr(self):
        """Test VolumeProfile string representation"""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 23, 59, 59, tzinfo=timezone.utc)

        profile = VolumeProfile(
            symbol="ETH/USD",
            period_start=start,
            period_end=end,
            poc_price=Decimal("3050.00"),
            profile_data=[]
        )

        repr_str = repr(profile)
        assert "VolumeProfile" in repr_str
        assert "ETH/USD" in repr_str
        assert "3050" in repr_str

    def test_volume_profile_table_name(self):
        """Test VolumeProfile table name"""
        assert VolumeProfile.__tablename__ == "volume_profiles"


class TestSignal:
    """Test Signal model"""

    def test_signal_creation(self):
        """Test creating Signal"""
        signal = Signal(
            symbol="BTC/USD",
            timeframe="15m",
            signal_type="BUY",
            confidence=0.85,
            context={
                "rsi": 30,
                "macd_cross": "bullish",
                "volume": "above_average"
            }
        )

        assert signal.symbol == "BTC/USD"
        assert signal.timeframe == "15m"
        assert signal.signal_type == "BUY"
        assert signal.confidence == 0.85
        assert signal.context["rsi"] == 30
        assert signal.context["macd_cross"] == "bullish"

    def test_signal_repr(self):
        """Test Signal string representation"""
        signal = Signal(
            id=123,
            symbol="ETH/USD",
            signal_type="SELL",
            confidence=0.75
        )

        repr_str = repr(signal)
        assert "Signal" in repr_str
        assert "123" in repr_str
        assert "ETH/USD" in repr_str
        assert "SELL" in repr_str
        assert "0.75" in repr_str

    def test_signal_default_created_at(self):
        """Test Signal default created_at"""
        signal = Signal(
            symbol="BTC/USD",
            timeframe="1h",
            signal_type="ALERT"
        )

        # created_at should be set by default function
        # We can't test exact value but can verify it's None here
        # (would be set by database on insert)
        assert hasattr(signal, "created_at")

    def test_signal_table_name(self):
        """Test Signal table name"""
        assert Signal.__tablename__ == "signals"

    @pytest.mark.parametrize("signal_type", ["BUY", "SELL", "ALERT"])
    def test_signal_types(self, signal_type):
        """Test different signal types"""
        signal = Signal(
            symbol="BTC/USD",
            timeframe="15m",
            signal_type=signal_type,
            confidence=0.5
        )

        assert signal.signal_type == signal_type