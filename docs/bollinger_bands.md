# Bollinger Bands

## Overview

Bollinger Bands consist of a moving average (middle line) with two standard deviation bands above and below it. They provide insights into volatility, trend direction, and potential breakout opportunities. The most powerful strategy involves trading breakouts from low-volatility squeezes, using volume divergence to predict direction.

## Core Components

The Bollinger Bands system requires these essential components:

- **`middle_line`**: 20-period Simple Moving Average (trend baseline)
- **`upper_band`**: Middle line + (2 × standard deviation)
- **`lower_band`**: Middle line - (2 × standard deviation)
- **`bbw_value`**: Bollinger BandWidth (distance between bands)
- **`obv_value`**: On-Balance Volume (for divergence analysis)

## Market State Analysis

### 1. Trend States (Middle Line Analysis)

The slope of the middle line determines the underlying trend bias.

#### 🐂 Bullish Trend State
- **Condition**: `middle_line[0] > middle_line[1]` (upward sloping)
- **Implication**: Favor long positions and upside breakouts
- **Use Case**: Trend filter for directional bias

#### 🐻 Bearish Trend State
- **Condition**: `middle_line[0] < middle_line[1]` (downward sloping)
- **Implication**: Favor short positions and downside breakouts
- **Use Case**: Trend filter for directional bias

#### 😐 Sideways/Ranging State
- **Condition**: Middle line relatively flat over recent periods
- **Implication**: Expect range-bound trading, prepare for breakout
- **Use Case**: Identify consolidation before major moves

### 2. Volatility States (Band Analysis)

Band width and BBW indicator reveal market volatility conditions.

#### High Volatility (Expansion)
- **Condition**: Bands widening, `bbw_value` high and/or rising
- **Characteristics**: Strong trending moves, momentum trades
- **Trading Approach**: Trend following, avoid countertrend

#### Low Volatility (Squeeze)
- **Condition**: Bands narrow, `bbw_value` at multi-period lows
- **Characteristics**: Consolidation before major breakout
- **Trading Approach**: Prepare for breakout strategy
- **Detection**: `bbw_value` at lowest level in X periods (e.g., 100)

## The Bollinger Band Squeeze Strategy

The signature high-probability setup: trading breakouts from low-volatility periods using volume divergence for direction.

### 🐂 Bullish Squeeze Breakout Setup

#### Step 1: Squeeze Precondition
- **Requirement**: Market in Low Volatility State
- **Indicators**: Narrow bands, low BBW reading
- **Duration**: Typically 10-30 periods of compression
- **State**: "SQUEEZE_ACTIVE"

#### Step 2: Bullish Divergence Signal
- **Price Action**: Makes a lower low during squeeze
- **Volume Action**: OBV makes a higher low at same time
- **Detection**:
  ```
  price_low[current] < price_low[previous] AND
  obv_value[current_trough] > obv_value[previous_trough]
  ```
- **State**: "BULLISH_DIVERGENCE_DETECTED"

#### Step 3: Breakout Trigger
- **Requirement**: Bands begin expanding (BBW rising)
- **Trigger**: Candle closes above upper band
- **Confirmation**: Increasing volume on breakout
- **State**: "BULLISH_BREAKOUT_TRIGGERED"

#### Step 4: Entry Signal
- **Strategy**: Wait for retest of key level
- **Entry Levels**:
  - Middle line retest (conservative)
  - Broken resistance retest (aggressive)
  - Upper band pullback (momentum)
- **State**: "BULLISH_ENTRY_READY"

### 🐻 Bearish Squeeze Breakout Setup

#### Step 1: Squeeze Precondition
- **Requirement**: Market in Low Volatility State
- **Indicators**: Narrow bands, low BBW reading
- **Duration**: Compression period before expansion
- **State**: "SQUEEZE_ACTIVE"

#### Step 2: Bearish Divergence Signal
- **Price Action**: Makes a higher high during squeeze
- **Volume Action**: OBV makes a lower high at same time
- **Detection**:
  ```
  price_high[current] > price_high[previous] AND
  obv_value[current_peak] < obv_value[previous_peak]
  ```
- **State**: "BEARISH_DIVERGENCE_DETECTED"

#### Step 3: Breakout Trigger
- **Requirement**: Bands begin expanding (BBW rising)
- **Trigger**: Candle closes below lower band
- **Confirmation**: Increasing volume on breakout
- **State**: "BEARISH_BREAKOUT_TRIGGERED"

#### Step 4: Entry Signal
- **Strategy**: Wait for retest of key level
- **Entry Levels**:
  - Middle line retest (conservative)
  - Broken support retest (aggressive)
  - Lower band pullback (momentum)
- **State**: "BEARISH_ENTRY_READY"

### 😐 Neutral States

#### Squeeze Without Divergence
- **Condition**: Low volatility squeeze present
- **Missing Element**: No clear OBV divergence
- **Action**: Monitor and wait for directional clue
- **State**: "SQUEEZE_NO_BIAS"

#### Choppy Expansion
- **Condition**: Wide bands but sideways price action
- **Characteristics**: High volatility without clear direction
- **Action**: Avoid trading until clear trend emerges
- **State**: "VOLATILE_RANGING"

## Database Storage Implementation

### PointIndicator Table

Bollinger Bands data with squeeze tracking and state management.

```json
{
    "indicator": "BOLLINGER_BANDS",
    "time": "2024-01-01 12:00:00",
    "symbol": "BTC/USD",
    "timeframe": "1h",
    "value": {
        // Core band values
        "middle_line": 45500,
        "upper_band": 46200,
        "lower_band": 44800,
        "bbw_value": 1400,        // Band width
        "bb_position": 0.65,      // Price position within bands (0-1)

        // Trend analysis
        "middle_slope": "bullish", // "bullish", "bearish", "flat"
        "trend_strength": 0.7,     // Based on slope consistency

        // Volatility analysis
        "volatility_state": "normal", // "squeeze", "expansion", "normal"
        "bbw_percentile": 25,      // BBW ranking vs historical (0-100)
        "squeeze_duration": 0,     // Periods in squeeze (0 if not squeezing)

        // OBV integration
        "obv_value": 1250000,
        "obv_trend": "bullish",    // OBV direction

        // Divergence tracking
        "price_swings": [
            {"type": "high", "time": "11:00", "price": 46000, "obv": 1240000},
            {"type": "low", "time": "10:00", "price": 45000, "obv": 1230000}
        ],
        "divergence": null,        // "bullish" or "bearish" when detected

        // Squeeze strategy state machine
        "squeeze_setup": {
            "active": false,
            "phase": 0,            // 0=none, 1=squeeze, 2=divergence, 3=breakout, 4=entry
            "bias": null,          // "bullish" or "bearish" after divergence
            "breakout_level": null, // Level that was broken
            "entry_levels": [],    // Potential retest levels
            "setup_start": null,   // When squeeze began
            "divergence_time": null
        },

        // Band interaction
        "band_touches": {
            "upper_touches": 0,    // Recent upper band touches
            "lower_touches": 0,    // Recent lower band touches
            "last_breakout": null  // Last band breakout direction
        }
    }
}
```

## Signal Generation Logic

### Volatility State Detection
```python
def detect_volatility_state(bbw_history, lookback=100):
    """Determine current volatility state"""
    current_bbw = bbw_history[-1]
    historical_bbw = bbw_history[-lookback:]

    # Calculate percentile ranking
    percentile = sum(1 for x in historical_bbw if x < current_bbw) / len(historical_bbw)

    if percentile <= 0.20:  # Bottom 20%
        return "SQUEEZE"
    elif percentile >= 0.80:  # Top 20%
        return "EXPANSION"
    else:
        return "NORMAL"
```

### Squeeze Detection and Tracking
```python
def track_squeeze_duration(volatility_states):
    """Track how long we've been in a squeeze"""
    squeeze_count = 0

    # Count consecutive squeeze periods from end
    for state in reversed(volatility_states):
        if state == "SQUEEZE":
            squeeze_count += 1
        else:
            break

    return squeeze_count
```

### OBV Divergence Detection
```python
def detect_obv_divergence(price_swings, obv_swings, in_squeeze=True):
    """Detect OBV divergences during squeeze periods"""
    if not in_squeeze or len(price_swings) < 2:
        return None

    # Bullish divergence: Lower low in price, higher low in OBV
    if (price_swings[-1].type == "low" and len([s for s in price_swings if s.type == "low"]) >= 2):
        recent_lows = [s for s in price_swings if s.type == "low"][-2:]
        if (recent_lows[1].price < recent_lows[0].price and
            recent_lows[1].obv > recent_lows[0].obv):
            return "BULLISH_DIVERGENCE"

    # Bearish divergence: Higher high in price, lower high in OBV
    if (price_swings[-1].type == "high" and len([s for s in price_swings if s.type == "high"]) >= 2):
        recent_highs = [s for s in price_swings if s.type == "high"][-2:]
        if (recent_highs[1].price > recent_highs[0].price and
            recent_highs[1].obv < recent_highs[0].obv):
            return "BEARISH_DIVERGENCE"

    return None
```

### Breakout Detection
```python
def detect_band_breakout(current_candle, bands, previous_close):
    """Detect closes beyond Bollinger Bands"""
    # Bullish breakout
    if (previous_close <= bands.upper_band and
        current_candle.close > bands.upper_band):
        return "BULLISH_BREAKOUT"

    # Bearish breakout
    if (previous_close >= bands.lower_band and
        current_candle.close < bands.lower_band):
        return "BEARISH_BREAKOUT"

    return None
```

### Squeeze Strategy State Machine
```python
def update_squeeze_strategy(setup_state, current_signals, market_data):
    """Manage the multi-step squeeze strategy"""

    if setup_state.phase == 0:
        # Look for squeeze initiation
        if current_signals.volatility_state == "SQUEEZE":
            setup_state.phase = 1
            setup_state.setup_start = current_time
            setup_state.active = True

    elif setup_state.phase == 1:
        # In squeeze, look for divergence
        if current_signals.divergence:
            setup_state.phase = 2
            setup_state.bias = current_signals.divergence.split("_")[0].lower()
            setup_state.divergence_time = current_time

    elif setup_state.phase == 2:
        # Have divergence, wait for breakout
        breakout = current_signals.breakout
        if breakout and breakout.split("_")[0].lower() == setup_state.bias:
            setup_state.phase = 3
            setup_state.breakout_level = current_signals.breakout_level
            setup_state.entry_levels = calculate_entry_levels(market_data, setup_state.bias)

    elif setup_state.phase == 3:
        # Breakout occurred, wait for entry opportunity
        if detect_entry_opportunity(market_data, setup_state.entry_levels):
            setup_state.phase = 4
            return f"{setup_state.bias.upper()}_SQUEEZE_ENTRY"

    return None
```

## Trading Strategies

### Primary Strategy: Squeeze Breakout

#### Setup Requirements
1. **Volatility Squeeze**: BBW at multi-period lows
2. **Divergence Signal**: OBV diverges from price during squeeze
3. **Breakout Confirmation**: Close beyond appropriate band
4. **Entry Timing**: Retest of key level after breakout

#### Risk Management
- **Stop Loss**: Other side of middle line or recent swing
- **Position Size**: Larger for confirmed setups with strong divergence
- **Profit Target**: Previous swing, measured move, or next resistance

### Secondary Strategy: Band Bounces

#### Mean Reversion Approach
- **Entry**: Price touches band in trending market
- **Direction**: Against the touch (expecting reversion to middle)
- **Filter**: Only in established trends with sloping middle line
- **Exit**: Return to middle line or opposite band

### Advanced Strategy: Multiple Timeframe

#### HTF Context
- Use daily/weekly for major squeeze identification
- Confirm trend direction with higher timeframe middle line

#### LTF Execution
- Use 1H/4H for precise entries within HTF squeeze
- Look for micro-squeezes within larger compression

## Key Parameters

### Standard Settings
- **Period**: 20 (for middle line SMA)
- **Standard Deviations**: 2.0 (for upper/lower bands)
- **BBW Lookback**: 100 periods (for squeeze detection)
- **OBV**: Standard calculation

### Alternative Settings
- **Shorter Period**: 10, 1.5 std dev (more sensitive)
- **Longer Period**: 50, 2.5 std dev (smoother)
- **Dynamic Bands**: Adaptive period based on volatility

## Implementation Notes

1. **Squeeze Identification**: Use percentile ranking for objective measurement
2. **Divergence Quality**: Require clear, well-defined swings
3. **Breakout Confirmation**: Volume should increase on breakout
4. **Entry Patience**: Wait for retest rather than immediate entry
5. **False Breakouts**: Common in low-volume or news-driven markets

## Best Practices

1. **Quality over quantity** - Wait for textbook squeeze setups
2. **Volume confirmation** - Breakouts need volume support
3. **Trend context** - Align with higher timeframe trend
4. **Patience for entries** - Don't chase breakouts, wait for pullbacks
5. **Multiple confirmations** - Combine with other technical factors

## Common Pitfalls

- Trading every band touch without considering trend
- Entering immediately on breakout without retest
- Ignoring volume during breakouts
- Missing the importance of the divergence signal
- Not waiting for proper squeeze development

## Advanced Concepts

### Squeeze Variations
- **Narrow Range**: Price compresses within bands
- **Coiling Pattern**: Decreasing volatility over time
- **Multi-Timeframe Squeeze**: Compression across multiple timeframes

### Band Walk
- **Upper Band Walk**: Sustained moves along upper band (strong uptrend)
- **Lower Band Walk**: Sustained moves along lower band (strong downtrend)
- **Trading Approach**: Don't fade these moves, wait for clear reversal

### Bollinger %B
- **Calculation**: (Close - Lower Band) / (Upper Band - Lower Band)
- **Range**: 0 to 1 (outside bands = >1 or <0)
- **Use**: Relative position within bands for momentum analysis

## Risk Management

### Position Sizing
- **Maximum Size**: Confirmed squeeze setups with strong divergence
- **Reduced Size**: Band bounces in ranging markets
- **Avoid**: Choppy expansion periods

### Stop Loss Guidelines
- **Squeeze Breakouts**: Beyond middle line or setup invalidation level
- **Band Bounces**: Beyond the band that was touched
- **Breakout Failures**: Quick exit if retest fails

### Profit Targets
- **Conservative**: Return to middle line
- **Moderate**: Previous swing high/low
- **Aggressive**: Measured move based on average breakout distance

## Market Context

### Best Markets
- **Trending with Pullbacks**: Clear directional bias with retracements
- **Post-Consolidation**: After extended sideways periods
- **Institutional Participation**: High volume and clean price action

### Avoid Trading
- **News Events**: Can cause false breakouts
- **Low Volume**: Breakouts may lack follow-through
- **Multiple Rejections**: Bands that have been tested many times
- **Extreme Market Conditions**: During major volatility events