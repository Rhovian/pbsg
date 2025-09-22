from sqlalchemy import Column, String, Numeric, Integer, DateTime, Index, text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from .database import Base


class OHLCBase:
    """Base class for OHLC models with common columns"""
    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String, primary_key=True, nullable=False)
    timeframe = Column(String, primary_key=True, nullable=False)
    open = Column(Numeric(18, 8))
    high = Column(Numeric(18, 8))
    low = Column(Numeric(18, 8))
    close = Column(Numeric(18, 8))
    volume = Column(Numeric(18, 8))
    trades = Column(Integer)


class BTCOHLC(Base, OHLCBase):
    __tablename__ = "btc_ohlc"

    __table_args__ = (
        Index('idx_btc_ohlc_symbol_time', 'symbol', 'time'),
        Index('idx_btc_ohlc_timeframe_time', 'timeframe', 'time'),
    )

    def __repr__(self):
        return f"<BTCOHLC(time={self.time}, symbol={self.symbol}, close={self.close})>"


class ETHOHLC(Base, OHLCBase):
    __tablename__ = "eth_ohlc"

    __table_args__ = (
        Index('idx_eth_ohlc_symbol_time', 'symbol', 'time'),
        Index('idx_eth_ohlc_timeframe_time', 'timeframe', 'time'),
    )

    def __repr__(self):
        return f"<ETHOHLC(time={self.time}, symbol={self.symbol}, close={self.close})>"


class SOLOHLC(Base, OHLCBase):
    __tablename__ = "sol_ohlc"

    __table_args__ = (
        Index('idx_sol_ohlc_symbol_time', 'symbol', 'time'),
        Index('idx_sol_ohlc_timeframe_time', 'timeframe', 'time'),
    )

    def __repr__(self):
        return f"<SOLOHLC(time={self.time}, symbol={self.symbol}, close={self.close})>"


def get_ohlc_model(symbol: str):
    """Get the appropriate OHLC model for a symbol"""
    models = {
        'BTC/USD': BTCOHLC,
        'ETH/USD': ETHOHLC,
        'SOL/USD': SOLOHLC,
    }
    return models.get(symbol)


def create_hypertables(engine, symbol_prefixes: list = None, include_indicators: bool = False):
    """
    Convert OHLC tables to TimescaleDB hypertables after creation
    Call this after create_all()

    Usage:
        create_hypertables(engine)  # Creates OHLC tables only
        create_hypertables(engine, ['btc', 'eth', 'sol'])  # Specific tables
        create_hypertables(engine, include_indicators=True)  # Include indicators table
    """
    if symbol_prefixes is None:
        symbol_prefixes = ['btc', 'eth', 'sol']

    with engine.connect() as conn:
        for prefix in symbol_prefixes:
            table_name = f"{prefix.lower()}_ohlc"
            conn.execute(text(
                f"SELECT create_hypertable('{table_name}', 'time', "
                f"if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day')"
            ))
            conn.commit()
            print(f"✅ Created hypertable for {table_name}")

        # Optionally make indicators table a hypertable (usually not needed)
        if include_indicators:
            conn.execute(text(
                "SELECT create_hypertable('indicators', 'time', "
                "if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days')"
            ))
            conn.commit()
            print("✅ Created hypertable for indicators")


class PointIndicator(Base):
    """
    Point-in-time indicators (RSI, MACD, Moving Averages, etc.)
    Typically only keep recent values, updated frequently
    """
    __tablename__ = "point_indicators"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String, primary_key=True, nullable=False)
    timeframe = Column(String, primary_key=True, nullable=False)
    indicator = Column(String, primary_key=True, nullable=False)
    value = Column(JSONB, nullable=False)

    __table_args__ = (
        Index('idx_point_indicators_symbol_time', 'symbol', 'time'),
        Index('idx_point_indicators_indicator', 'indicator'),
    )

    def __repr__(self):
        return f"<PointIndicator(time={self.time}, symbol={self.symbol}, indicator={self.indicator})>"


class RangeIndicator(Base):
    """
    Range/level indicators that persist until invalidated
    (FVGs, Support/Resistance levels, Supply/Demand zones, etc.)
    """
    __tablename__ = "range_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    indicator = Column(String, nullable=False)  # 'FVG', 'SUPPORT', 'RESISTANCE', etc.
    range_high = Column(Numeric(18, 8))
    range_low = Column(Numeric(18, 8))
    strength = Column(Float)  # 0.0 to 1.0 confidence/strength
    invalidated = Column(Boolean, default=False)
    invalidated_at = Column(DateTime(timezone=True))
    metadata = Column(JSONB)  # Additional context

    __table_args__ = (
        Index('idx_range_indicators_symbol', 'symbol'),
        Index('idx_range_indicators_active', 'symbol', 'invalidated'),
        Index('idx_range_indicators_created', 'created_at'),
    )

    def __repr__(self):
        return f"<RangeIndicator(symbol={self.symbol}, indicator={self.indicator}, range=[{self.range_low}-{self.range_high}])>"


class VolumeProfile(Base):
    """
    Volume profiles showing distribution of volume across price levels
    Used for identifying high-volume nodes, POC, and value areas
    """
    __tablename__ = "volume_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)  # '24h', '7d', '30d', 'session'
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # Key levels
    poc_price = Column(Numeric(18, 8))  # Point of Control (highest volume price)
    poc_volume = Column(Numeric(18, 8))  # Volume at POC
    vah = Column(Numeric(18, 8))  # Value Area High (70% of volume above)
    val = Column(Numeric(18, 8))  # Value Area Low (70% of volume below)
    total_volume = Column(Numeric(18, 8))  # Total volume in profile

    # Profile configuration
    price_step = Column(Numeric(18, 8))  # Price increment between levels (e.g., 10, 100)
    num_levels = Column(Integer)  # Number of price levels in profile

    # Full distribution - array of {price: float, volume: float, percentage: float}
    profile_data = Column(JSONB, nullable=False)

    __table_args__ = (
        Index('idx_volume_profiles_symbol_period', 'symbol', 'period_end'),
        Index('idx_volume_profiles_timeframe', 'timeframe'),
    )

    def __repr__(self):
        return f"<VolumeProfile(symbol={self.symbol}, period={self.period_start}-{self.period_end}, poc={self.poc_price})>"


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    signal_type = Column(String, nullable=False)  # 'BUY', 'SELL', 'ALERT'
    confidence = Column(Float)  # 0.0 to 1.0 or however you want to score it
    context = Column(JSONB)  # Additional context about the signal

    __table_args__ = (
        Index('idx_signals_created', 'created_at'),
        Index('idx_signals_symbol', 'symbol'),
    )

    def __repr__(self):
        return f"<Signal(id={self.id}, symbol={self.symbol}, type={self.signal_type}, confidence={self.confidence})>"