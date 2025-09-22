# Relative Strength Index (RSI)

## Overview

RSI is a momentum oscillator that measures the speed and magnitude of price changes. It oscillates between 0 and 100, providing insights into overbought/oversold conditions and momentum shifts. The indicator is particularly effective for identifying divergences and momentum-based entry points.

## Core Components

The RSI implementation requires these variables:

- **`rsi_value`**: Current RSI calculation (typically 14-period)
- **`rsi_length`**: Period setting for RSI (e.g., 14)
- **`rsi_ma_value`**: Moving average of the RSI for smoothed signals
- **`level_70`**: Overbought threshold (constant: 70)
- **`level_50`**: Neutral/momentum threshold (constant: 50)
- **`level_30`**: Oversold threshold (constant: 30)

## Signal Categories

### 1. Momentum Signals (50 Level Analysis)

The 50 level is crucial for determining directional bias and momentum shifts.

#### 🐂 Bullish Momentum Signals

##### Bullish Momentum Shift
- **Type**: Entry Trigger
- **Description**: RSI crosses above 50, signaling shift to bullish momentum
- **Trigger**: `rsi_value` crosses above `level_50`
- **Use Case**: Initial entry into bullish positions

##### Bullish Retest/Continuation
- **Type**: Entry Trigger
- **Description**: RSI pulls back to 50 in uptrend, then bounces for continuation
- **Prerequisites**: RSI was above 50 within recent X bars
- **Setup**: RSI touches/crosses below 50
- **Trigger**: RSI crosses back above 50 shortly after
- **Use Case**: Adding to positions or re-entry in trends

##### Bullish Momentum State
- **Type**: Confluence Filter
- **Description**: Overall bullish bias for trade filtering
- **Condition**: `rsi_value > 50`
- **Use Case**: Filter to only take long signals

#### 🐻 Bearish Momentum Signals

##### Bearish Momentum Shift
- **Type**: Entry Trigger
- **Description**: RSI crosses below 50, signaling shift to bearish momentum
- **Trigger**: `rsi_value` crosses below `level_50`
- **Use Case**: Initial entry into bearish positions

##### Bearish Retest/Continuation
- **Type**: Entry Trigger
- **Description**: RSI rallies to 50 in downtrend, then rejected for continuation
- **Prerequisites**: RSI was below 50 within recent X bars
- **Setup**: RSI touches/crosses above 50
- **Trigger**: RSI crosses back below 50 shortly after
- **Use Case**: Adding to positions or re-entry in trends

##### Bearish Momentum State
- **Type**: Confluence Filter
- **Description**: Overall bearish bias for trade filtering
- **Condition**: `rsi_value < 50`
- **Use Case**: Filter to only take short signals

### 2. Divergence Signals (Reversal Patterns)

Divergences identify momentum/price disagreements, signaling potential reversals.

#### 🐂 Bullish Divergence
- **Type**: Reversal Trigger
- **Price Condition**: Makes a lower low
- **RSI Condition**: Makes a higher low
- **Significance Filter**: First (previous) RSI trough must be below 30
- **Time Filter**: Troughs must be within `rsi_length` bars of each other
- **Detection**:
  ```
  price_low[current] < price_low[previous] AND
  rsi_low[current] > rsi_low[previous] AND
  rsi_low[previous] < 30 AND
  bars_between_troughs <= rsi_length
  ```

#### 🐻 Bearish Divergence
- **Type**: Reversal Trigger
- **Price Condition**: Makes a higher high
- **RSI Condition**: Makes a lower high
- **Significance Filter**: First (previous) RSI peak must be above 70
- **Time Filter**: Peaks must be within `rsi_length` bars of each other
- **Detection**:
  ```
  price_high[current] > price_high[previous] AND
  rsi_high[current] < rsi_high[previous] AND
  rsi_high[previous] > 70 AND
  bars_between_peaks <= rsi_length
  ```

### 3. RSI + Moving Average Signals

Using an MA of RSI provides smoother, more reliable signals.

#### 🐂 Bullish MA Signals

##### Smoothed Momentum Shift
- **Type**: Entry Trigger
- **Description**: RSI MA crosses above 50 for confirmed momentum shift
- **Trigger**: `rsi_ma_value` crosses above `level_50`
- **Use Case**: More conservative bullish entries

##### RSI/MA Crossover
- **Type**: Entry Trigger
- **Description**: RSI crosses above its MA, showing momentum acceleration
- **Trigger**: `rsi_value` crosses above `rsi_ma_value`
- **Use Case**: Short-term bullish momentum plays

#### 🐻 Bearish MA Signals

##### Smoothed Momentum Shift
- **Type**: Entry Trigger
- **Description**: RSI MA crosses below 50 for confirmed momentum shift
- **Trigger**: `rsi_ma_value` crosses below `level_50`
- **Use Case**: More conservative bearish entries

##### RSI/MA Crossunder
- **Type**: Entry Trigger
- **Description**: RSI crosses below its MA, showing momentum deceleration
- **Trigger**: `rsi_value` crosses below `rsi_ma_value`
- **Use Case**: Short-term bearish momentum plays

### 4. Neutral State

#### 😐 No Clear Signal
Conditions indicating no tradeable signal:
- RSI hovering in neutral zone (45-55) without clear crosses
- No valid divergences detected
- RSI and RSI MA intertwined and moving sideways
- Lack of clear momentum direction

## Database Storage Implementation

### PointIndicator Table

RSI values are stored as point-in-time indicators, updated with each candle.

```json
{
    "indicator": "RSI",
    "time": "2024-01-01 12:00:00",
    "symbol": "BTC/USD",
    "timeframe": "15m",
    "value": {
        "rsi": 58.5,
        "rsi_ma": 55.2,
        "rsi_length": 14,

        // Momentum analysis
        "momentum_state": "bullish",  // "bullish", "bearish", or "neutral"
        "fifty_cross": null,  // "bullish" or "bearish" when crossing occurs
        "ma_cross": null,  // "bullish" or "bearish" when RSI crosses MA

        // Zone tracking
        "zone": "neutral",  // "overbought" (>70), "oversold" (<30), or "neutral"
        "zone_duration": 3,  // Bars in current zone

        // Retest tracking
        "recent_high": {"value": 72.5, "bars_ago": 5},
        "recent_low": {"value": 28.3, "bars_ago": 10},
        "retest_setup": null,  // "bullish" or "bearish" when retest conditions met

        // Divergence tracking
        "rsi_peaks": [
            {"time": "2024-01-01 11:00", "value": 75.2, "price": 46000}
        ],
        "rsi_troughs": [
            {"time": "2024-01-01 10:00", "value": 25.5, "price": 45000}
        ],
        "divergence": null,  // "bullish" or "bearish" when detected
        "divergence_strength": null  // Based on oversold/overbought conditions
    }
}
```

## Signal Generation Logic

### Momentum Cross Detection
```python
def detect_rsi_momentum_cross(current, previous):
    # Bullish momentum shift
    if previous.rsi <= 50 and current.rsi > 50:
        return "BULLISH_MOMENTUM_SHIFT"

    # Bearish momentum shift
    if previous.rsi >= 50 and current.rsi < 50:
        return "BEARISH_MOMENTUM_SHIFT"

    return None
```

### Retest Detection
```python
def detect_rsi_retest(rsi_history, lookback=10):
    current = rsi_history[-1]

    # Check for bullish retest setup
    if current.rsi < 50:
        # Was RSI recently above 50?
        recent_above = any(r.rsi > 55 for r in rsi_history[-lookback:-1])
        if recent_above:
            return "BULLISH_RETEST_SETUP"

    # Check for bearish retest setup
    elif current.rsi > 50:
        # Was RSI recently below 50?
        recent_below = any(r.rsi < 45 for r in rsi_history[-lookback:-1])
        if recent_below:
            return "BEARISH_RETEST_SETUP"

    return None
```

### Divergence Detection
```python
def detect_rsi_divergence(price_swings, rsi_swings, rsi_length=14):
    # Bullish divergence
    if len(price_swings.lows) >= 2 and len(rsi_swings.troughs) >= 2:
        price_ll = price_swings.lows[-1] < price_swings.lows[-2]
        rsi_hl = rsi_swings.troughs[-1] > rsi_swings.troughs[-2]
        oversold = rsi_swings.troughs[-2] < 30
        time_valid = (rsi_swings.troughs[-1].time - rsi_swings.troughs[-2].time).bars <= rsi_length

        if price_ll and rsi_hl and oversold and time_valid:
            return "BULLISH_DIVERGENCE"

    # Bearish divergence
    if len(price_swings.highs) >= 2 and len(rsi_swings.peaks) >= 2:
        price_hh = price_swings.highs[-1] > price_swings.highs[-2]
        rsi_lh = rsi_swings.peaks[-1] < rsi_swings.peaks[-2]
        overbought = rsi_swings.peaks[-2] > 70
        time_valid = (rsi_swings.peaks[-1].time - rsi_swings.peaks[-2].time).bars <= rsi_length

        if price_hh and rsi_lh and overbought and time_valid:
            return "BEARISH_DIVERGENCE"

    return None
```

### MA Cross Detection
```python
def detect_rsi_ma_signals(current, previous):
    signals = []

    # RSI vs MA cross
    if previous.rsi <= previous.rsi_ma and current.rsi > current.rsi_ma:
        signals.append("RSI_MA_BULLISH_CROSS")
    elif previous.rsi >= previous.rsi_ma and current.rsi < current.rsi_ma:
        signals.append("RSI_MA_BEARISH_CROSS")

    # MA vs 50 level
    if previous.rsi_ma <= 50 and current.rsi_ma > 50:
        signals.append("MA_BULLISH_MOMENTUM")
    elif previous.rsi_ma >= 50 and current.rsi_ma < 50:
        signals.append("MA_BEARISH_MOMENTUM")

    return signals
```

## Trading Rules

### Entry Strategies

#### Trend Following
1. **Bullish Entry**: RSI crosses above 50 + price above key MA
2. **Bearish Entry**: RSI crosses below 50 + price below key MA
3. **Confirmation**: Wait for RSI MA to also cross 50 level

#### Mean Reversion
1. **Oversold Bounce**: RSI < 30 + bullish divergence + support level
2. **Overbought Reversal**: RSI > 70 + bearish divergence + resistance level
3. **Exit**: When RSI returns to neutral (50) zone

#### Continuation Patterns
1. **Bullish Continuation**: RSI retest of 50 from above in uptrend
2. **Bearish Continuation**: RSI retest of 50 from below in downtrend
3. **Filter**: Confirm trend with price structure

### Exit Strategies
- RSI crosses back through 50 against position
- Divergence forms against position
- RSI reaches extreme levels (>70 or <30)
- RSI/MA cross against position

## Key Parameters

### Standard Settings
- **RSI Period**: 14 (default)
- **RSI MA Period**: 9 or 14
- **Overbought Level**: 70
- **Neutral Level**: 50
- **Oversold Level**: 30

### Alternative Settings
- **Shorter Period** (5-9): More sensitive, good for scalping
- **Longer Period** (21-25): Smoother, good for position trading
- **Custom Levels**: 80/20 for stronger signals, 60/40 for earlier entries

## Implementation Notes

1. **Peak/Trough Detection**: Use pivot points or swing detection algorithm
2. **Divergence Validation**: Require clear, well-defined swings
3. **Time Filter Importance**: Divergences too far apart lose relevance
4. **MA Type**: EMA typically used for RSI MA (more responsive)
5. **Multiple Timeframe**: Confirm signals across timeframes

## Best Practices

1. **Never trade RSI in isolation** - Always confirm with price action
2. **Respect the 50 level** - It's the most important momentum threshold
3. **Quality over quantity** - Wait for high-probability setups
4. **Zone duration matters** - Extended time in extreme zones increases reversal probability
5. **Combine with support/resistance** - RSI signals work best at key levels

## Common Pitfalls

- Trading every overbought/oversold reading without context
- Ignoring the trend when taking divergence trades
- Missing the importance of the 50 level for momentum
- Not validating divergences with proper swing detection
- Over-optimizing RSI period for historical data

## Advanced Techniques

### Hidden Divergences
- **Bullish Hidden**: Higher low in price, lower low in RSI (trend continuation)
- **Bearish Hidden**: Lower high in price, higher high in RSI (trend continuation)

### Multiple RSI Strategy
- Use different periods (e.g., RSI(7) and RSI(14))
- Faster RSI for entries, slower for trend filter

### RSI Patterns
- Double bottom/top formations in RSI
- RSI channel breaks
- RSI support/resistance levels