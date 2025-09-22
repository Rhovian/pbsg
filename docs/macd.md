# Moving Average Convergence Divergence (MACD)

## Overview

MACD is a momentum oscillator that shows the relationship between two moving averages of prices. It consists of the MACD line, signal line, and histogram, providing multiple layers of momentum analysis.

## Core Components

The MACD indicator provides four essential values:

- **`macd_line`**: Main MACD line (12-period EMA - 26-period EMA)
- **`signal_line`**: Signal line (9-period EMA of the MACD line)
- **`histogram_value`**: Histogram (MACD line - Signal line)
- **`zero_line`**: Constant value of 0 (reference line)

## Signal Types

### 1. Crossover Signals (Primary Entry Triggers)

Crossovers between MACD and signal lines indicate momentum shifts. These signals must be filtered by higher timeframe trend.

#### 🐂 Bullish Crossover
- **Description**: MACD line crosses above signal line, indicating short-term bullish momentum
- **Prerequisites**: HTF trend must be bullish
- **Trigger**: `macd_line` crosses above `signal_line`
- **Use Case**: Primary entry signal for long positions

#### 🐻 Bearish Crossover
- **Description**: MACD line crosses below signal line, indicating short-term bearish momentum
- **Prerequisites**: HTF trend must be bearish
- **Trigger**: `macd_line` crosses below `signal_line`
- **Use Case**: Primary entry signal for short positions

### 2. Zero Line Analysis (Market Regime)

The MACD line's position relative to zero defines the overall momentum bias.

#### 🐂 Bullish Zero Line Signals
- **Bullish Regime** (State):
  - Condition: `macd_line > 0`
  - Implication: Overall bullish momentum, favor long positions

- **Bullish Momentum Shift** (Trigger):
  - Condition: `macd_line` crosses above `0`
  - Implication: Major shift from bearish to bullish momentum

#### 🐻 Bearish Zero Line Signals
- **Bearish Regime** (State):
  - Condition: `macd_line < 0`
  - Implication: Overall bearish momentum, favor short positions

- **Bearish Momentum Shift** (Trigger):
  - Condition: `macd_line` crosses below `0`
  - Implication: Major shift from bullish to bearish momentum

### 3. Histogram Analysis (Momentum Strength)

The histogram reveals momentum acceleration/deceleration, useful for confirmation and early warnings.

#### 🐂 Bullish Histogram States
- **Expanding Bullish Momentum**:
  - Condition: `histogram > 0` AND `histogram[0] > histogram[1]`
  - Implication: Strengthening bullish momentum, confirms long bias

- **Weakening Bullish Momentum**:
  - Condition: `histogram > 0` AND `histogram[0] < histogram[1]`
  - Implication: Fading bullish momentum, potential pullback warning

#### 🐻 Bearish Histogram States
- **Expanding Bearish Momentum**:
  - Condition: `histogram < 0` AND `abs(histogram[0]) > abs(histogram[1])`
  - Implication: Strengthening bearish momentum, confirms short bias

- **Weakening Bearish Momentum**:
  - Condition: `histogram < 0` AND `abs(histogram[0]) < abs(histogram[1])`
  - Implication: Fading bearish momentum, potential bounce warning

### 4. Divergence Signals (Reversal Patterns)

Divergences occur when price and MACD momentum contradict, signaling potential reversals.

#### 🐂 Bullish Divergence
- **Price Action**: Makes a lower low
- **MACD Action**: Makes a higher low
- **Detection**:
  ```
  price_low[current] < price_low[previous] AND
  macd_low[current] > macd_low[previous]
  ```
- **Implication**: Downtrend losing momentum, potential bullish reversal

#### 🐻 Bearish Divergence
- **Price Action**: Makes a higher high
- **MACD Action**: Makes a lower high
- **Detection**:
  ```
  price_high[current] > price_high[previous] AND
  macd_high[current] < macd_high[previous]
  ```
- **Implication**: Uptrend losing momentum, potential bearish reversal

### 5. Neutral State

#### 😐 No Clear Signal
Conditions indicating no tradeable signal:
- HTF trend is ranging/neutral
- MACD and signal lines are intertwined near zero
- Histogram values are minimal and frequently changing sign
- No clear divergences present

## Database Storage Implementation

### PointIndicator Table

MACD values are stored as point-in-time indicators, updated with each new candle.

```json
{
    "indicator": "MACD",
    "time": "2024-01-01 12:00:00",
    "symbol": "BTC/USD",
    "timeframe": "15m",
    "value": {
        "macd_line": 125.50,
        "signal_line": 115.30,
        "histogram": 10.20,
        "zero_cross": null,  // "bullish" or "bearish" when it occurs
        "signal_cross": null,  // "bullish" or "bearish" when it occurs
        "regime": "bullish",  // Current regime based on zero line
        "momentum_state": "expanding",  // Based on histogram analysis

        // For divergence tracking
        "recent_peaks": [
            {"time": "2024-01-01 11:00", "macd": 150.20, "price": 46000}
        ],
        "recent_troughs": [
            {"time": "2024-01-01 10:00", "macd": -50.30, "price": 45000}
        ],
        "divergence": null  // "bullish" or "bearish" when detected
    }
}
```

## Signal Generation Logic

### Crossover Detection
```python
def detect_macd_crossover(current, previous, htf_trend):
    # Bullish crossover
    if (previous.macd_line <= previous.signal_line and
        current.macd_line > current.signal_line and
        htf_trend == "bullish"):
        return "BULLISH_CROSSOVER"

    # Bearish crossover
    if (previous.macd_line >= previous.signal_line and
        current.macd_line < current.signal_line and
        htf_trend == "bearish"):
        return "BEARISH_CROSSOVER"

    return None
```

### Zero Line Cross Detection
```python
def detect_zero_cross(current, previous):
    if previous.macd_line <= 0 and current.macd_line > 0:
        return "BULLISH_ZERO_CROSS"
    elif previous.macd_line >= 0 and current.macd_line < 0:
        return "BEARISH_ZERO_CROSS"
    return None
```

### Histogram Momentum Analysis
```python
def analyze_histogram_momentum(current, previous):
    if current.histogram > 0:
        if current.histogram > previous.histogram:
            return "BULLISH_EXPANDING"
        else:
            return "BULLISH_WEAKENING"
    elif current.histogram < 0:
        if abs(current.histogram) > abs(previous.histogram):
            return "BEARISH_EXPANDING"
        else:
            return "BEARISH_WEAKENING"
    return "NEUTRAL"
```

### Divergence Detection
```python
def detect_divergence(price_peaks, macd_peaks, price_troughs, macd_troughs):
    # Bearish divergence: Higher high in price, lower high in MACD
    if (len(price_peaks) >= 2 and len(macd_peaks) >= 2):
        if (price_peaks[-1] > price_peaks[-2] and
            macd_peaks[-1] < macd_peaks[-2]):
            return "BEARISH_DIVERGENCE"

    # Bullish divergence: Lower low in price, higher low in MACD
    if (len(price_troughs) >= 2 and len(macd_troughs) >= 2):
        if (price_troughs[-1] < price_troughs[-2] and
            macd_troughs[-1] > macd_troughs[-2]):
            return "BULLISH_DIVERGENCE"

    return None
```

## Trading Rules

### Entry Conditions

#### Long Entry
1. **Primary**: Bullish crossover with HTF bullish trend
2. **Confirmation**: MACD > 0 (bullish regime)
3. **Strength**: Histogram expanding (momentum increasing)
4. **Alternative**: Bullish divergence at support level

#### Short Entry
1. **Primary**: Bearish crossover with HTF bearish trend
2. **Confirmation**: MACD < 0 (bearish regime)
3. **Strength**: Histogram expanding negative (momentum increasing)
4. **Alternative**: Bearish divergence at resistance level

### Exit Conditions
- Opposite crossover signal
- Histogram momentum weakening significantly
- Zero line cross against position
- Divergence against position

## Key Parameters

### Standard Settings
- Fast EMA: 12 periods
- Slow EMA: 26 periods
- Signal EMA: 9 periods

### Optimization Considerations
- Shorter periods (e.g., 5, 10, 5) for scalping
- Longer periods (e.g., 21, 55, 9) for position trading
- Adjust based on market volatility and timeframe

## Implementation Notes

1. **Crossover Lag**: MACD is a lagging indicator; crossovers confirm rather than predict
2. **False Signals**: Filter with HTF trend to reduce whipsaws in ranging markets
3. **Divergence Complexity**: Requires peak/trough detection algorithm
4. **Multiple Timeframes**: Consider MACD alignment across timeframes
5. **Volume Confirmation**: Combine with volume analysis for stronger signals

## Best Practices

1. **Never trade crossovers in isolation** - Always confirm with trend context
2. **Watch histogram for early warnings** - Weakening momentum often precedes crossovers
3. **Respect zero line** - Major momentum shifts occur at zero crosses
4. **Track divergences carefully** - Require clear, well-defined peaks/troughs
5. **Combine with price action** - MACD works best with support/resistance levels

## Common Pitfalls

- Trading every crossover without trend filter
- Ignoring histogram momentum changes
- Missing divergence signals due to poor peak/trough detection
- Over-relying on MACD in choppy/ranging markets
- Not adjusting parameters for different market conditions