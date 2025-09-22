# Stochastic Oscillator

## Overview

The Stochastic Oscillator is a momentum indicator that compares a security's closing price to its price range over a specific period. It oscillates between 0 and 100, providing insights into overbought/oversold conditions and momentum shifts. The indicator is particularly effective when combined with divergence analysis and zone-based trading strategies.

## Core Components

The Stochastic Oscillator provides these essential values:

- **`k_value`**: Fast %K line (primary line)
- **`d_value`**: Slow %D line (signal line, usually SMA of %K)
- **`level_80`**: Overbought threshold (constant: 80)
- **`level_20`**: Oversold threshold (constant: 20)

## Signal Categories

### 1. Basic Crossover Signals

Simple momentum shifts indicated by %K and %D line crossovers.

#### 🐂 Bullish Crossover
- **Type**: Momentum Signal
- **Description**: %K crosses above %D, suggesting potential upward momentum
- **Trigger**: `k_value` crosses above `d_value`
- **Use Case**: Basic bullish momentum confirmation

#### 🐻 Bearish Crossover
- **Type**: Momentum Signal
- **Description**: %K crosses below %D, suggesting potential downward momentum
- **Trigger**: `k_value` crosses below `d_value`
- **Use Case**: Basic bearish momentum confirmation

### 2. Overbought/Oversold Reversal Strategy

Enhanced crossover signals that require extreme zone confirmation for higher probability setups.

#### 🐂 Bullish Oversold Reversal
- **Type**: Reversal Signal
- **Description**: Bullish crossover in oversold zone followed by momentum recovery
- **Setup Requirements**:
  - Bullish crossover (`k_value` crosses above `d_value`)
  - Both values must be below 20 when crossover occurs
- **Trigger**: `k_value` crosses back above `level_20`
- **Use Case**: High-probability reversal from oversold conditions

#### 🐻 Bearish Overbought Reversal
- **Type**: Reversal Signal
- **Description**: Bearish crossover in overbought zone followed by momentum decline
- **Setup Requirements**:
  - Bearish crossover (`k_value` crosses below `d_value`)
  - Both values must be above 80 when crossover occurs
- **Trigger**: `k_value` crosses back below `level_80`
- **Use Case**: High-probability reversal from overbought conditions

### 3. Divergence Signals

Classic divergence patterns between price action and stochastic momentum.

#### 🐂 Bullish Divergence
- **Type**: Reversal Signal
- **Price Condition**: Makes a lower low
- **Stochastic Condition**: %K makes a higher low
- **Detection**:
  ```
  price_low[current] < price_low[previous] AND
  k_value[current_trough] > k_value[previous_trough]
  ```
- **Implication**: Downtrend losing momentum, potential reversal

#### 🐻 Bearish Divergence
- **Type**: Reversal Signal
- **Price Condition**: Makes a higher high
- **Stochastic Condition**: %K makes a lower high
- **Detection**:
  ```
  price_high[current] > price_high[previous] AND
  k_value[current_peak] < k_value[previous_peak]
  ```
- **Implication**: Uptrend losing momentum, potential reversal

### 4. Confirmed Divergence Strategy

Advanced multi-step reversal confirmation requiring both oscillator and price structure validation.

#### 🐂 Bullish Confirmed Setup
- **Step 1**: Bullish divergence detected
- **Step 2**: %K crosses back above 20 (oscillator confirmation)
- **Step 3**: Price creates higher high, breaking previous swing high (structure confirmation)
- **Entry Signal**: Retest of broken swing high
- **Use Case**: High-confidence reversal setup with multiple confirmations

#### 🐻 Bearish Confirmed Setup
- **Step 1**: Bearish divergence detected
- **Step 2**: %K crosses back below 80 (oscillator confirmation)
- **Step 3**: Price creates lower low, breaking previous swing low (structure confirmation)
- **Entry Signal**: Retest of broken swing low
- **Use Case**: High-confidence reversal setup with multiple confirmations

### 5. Neutral State

#### 😐 No Clear Signal
Conditions indicating no tradeable signal:
- %K and %D moving sideways between 20-80 levels
- Lines intertwined/tangled indicating choppy momentum
- No clear crossovers or divergences present
- Oscillator in middle range (40-60) without direction

## Database Storage Implementation

### PointIndicator Table

Stochastic values are stored as point-in-time indicators with state tracking.

```json
{
    "indicator": "STOCHASTIC",
    "time": "2024-01-01 12:00:00",
    "symbol": "BTC/USD",
    "timeframe": "15m",
    "value": {
        "k_value": 65.5,
        "d_value": 62.3,
        "k_length": 14,  // %K period
        "d_length": 3,   // %D smoothing

        // Zone analysis
        "zone": "neutral",  // "overbought" (>80), "oversold" (<20), "neutral"
        "zone_duration": 2,  // Bars in current zone

        // Crossover tracking
        "crossover": null,  // "bullish" or "bearish" when it occurs
        "crossover_in_zone": null,  // Track if crossover occurred in extreme zone

        // Zone exit tracking
        "zone_exit": null,  // "above_20" or "below_80" when exiting extreme zones

        // Divergence tracking
        "stoch_peaks": [
            {"time": "2024-01-01 11:00", "k_value": 85.2, "price": 46000}
        ],
        "stoch_troughs": [
            {"time": "2024-01-01 10:00", "k_value": 15.5, "price": 45000}
        ],
        "divergence": null,  // "bullish" or "bearish" when detected

        // Confirmed setup tracking
        "pending_setup": null,  // Track multi-step setup progress
        "setup_step": 0,  // Current step in confirmed divergence strategy
        "setup_data": {
            "divergence_detected": null,
            "oscillator_confirmed": null,
            "structure_confirmed": null
        }
    }
}
```

## Signal Generation Logic

### Basic Crossover Detection
```python
def detect_stochastic_crossover(current, previous):
    # Bullish crossover
    if previous.k_value <= previous.d_value and current.k_value > current.d_value:
        return "BULLISH_CROSSOVER"

    # Bearish crossover
    if previous.k_value >= previous.d_value and current.k_value < current.d_value:
        return "BEARISH_CROSSOVER"

    return None
```

### Zone-Based Reversal Detection
```python
def detect_zone_reversal(current, previous, crossover_history):
    """Detect overbought/oversold reversal signals"""

    # Check for bullish setup
    recent_oversold_cross = any(
        cross.type == "bullish" and cross.k_value < 20 and cross.d_value < 20
        for cross in crossover_history[-5:]  # Last 5 crossovers
    )

    if recent_oversold_cross and previous.k_value <= 20 and current.k_value > 20:
        return "BULLISH_OVERSOLD_REVERSAL"

    # Check for bearish setup
    recent_overbought_cross = any(
        cross.type == "bearish" and cross.k_value > 80 and cross.d_value > 80
        for cross in crossover_history[-5:]
    )

    if recent_overbought_cross and previous.k_value >= 80 and current.k_value < 80:
        return "BEARISH_OVERBOUGHT_REVERSAL"

    return None
```

### Divergence Detection
```python
def detect_stochastic_divergence(price_swings, stoch_swings):
    """Detect divergences between price and stochastic"""

    # Bullish divergence
    if len(price_swings.lows) >= 2 and len(stoch_swings.troughs) >= 2:
        price_ll = price_swings.lows[-1] < price_swings.lows[-2]
        stoch_hl = stoch_swings.troughs[-1] > stoch_swings.troughs[-2]

        if price_ll and stoch_hl:
            return "BULLISH_DIVERGENCE"

    # Bearish divergence
    if len(price_swings.highs) >= 2 and len(stoch_swings.peaks) >= 2:
        price_hh = price_swings.highs[-1] > price_swings.highs[-2]
        stoch_lh = stoch_swings.peaks[-1] < stoch_swings.peaks[-2]

        if price_hh and stoch_lh:
            return "BEARISH_DIVERGENCE"

    return None
```

### Confirmed Setup State Machine
```python
def update_confirmed_setup(setup_state, current_signals, price_structure):
    """Track multi-step confirmed divergence setups"""

    if setup_state.step == 0:
        # Look for divergence
        if "BULLISH_DIVERGENCE" in current_signals:
            setup_state.step = 1
            setup_state.type = "bullish"
            setup_state.divergence_time = current_time

    elif setup_state.step == 1:
        # Wait for oscillator confirmation
        if setup_state.type == "bullish" and current_signals.get("zone_exit") == "above_20":
            setup_state.step = 2
            setup_state.oscillator_confirmed = True

    elif setup_state.step == 2:
        # Wait for structure confirmation
        if setup_state.type == "bullish" and price_structure.new_higher_high:
            setup_state.step = 3
            setup_state.structure_confirmed = True
            return "BULLISH_CONFIRMED_SETUP"

    # Similar logic for bearish setups...
    return None
```

## Trading Strategies

### Basic Momentum Trading
- **Entry**: Stochastic crossover in trend direction
- **Filter**: Only trade crossovers above/below 50 level
- **Exit**: Opposite crossover or extreme zone reached

### Mean Reversion Trading
- **Setup**: Overbought/oversold crossover strategy
- **Entry**: Zone exit confirmation
- **Target**: Return to 50 level or opposite extreme
- **Stop**: Beyond recent swing high/low

### Divergence Trading
- **Setup**: Clear divergence at swing points
- **Entry**: Oscillator zone exit after divergence
- **Confirmation**: Price structure break
- **Target**: Previous swing or trend line

### Confirmed Reversal Strategy
- **Phase 1**: Identify divergence
- **Phase 2**: Wait for oscillator confirmation
- **Phase 3**: Wait for structure break
- **Entry**: Retest of broken level
- **High probability but requires patience**

## Key Parameters

### Standard Settings
- **%K Period**: 14 (lookback for high/low range)
- **%K Smoothing**: 1 (fast stochastic) or 3 (slow stochastic)
- **%D Period**: 3 (SMA of %K)
- **Overbought Level**: 80
- **Oversold Level**: 20

### Alternative Settings
- **Faster**: 5, 1, 3 (more sensitive, good for scalping)
- **Slower**: 21, 3, 5 (smoother, good for position trading)
- **Custom Levels**: 85/15 for stronger signals, 70/30 for earlier entries

## Implementation Notes

1. **Smooth vs Fast**: Slow stochastic (%K smoothed) produces fewer false signals
2. **Zone Duration**: Time spent in extreme zones increases reversal probability
3. **Multiple Timeframes**: Confirm signals across timeframes
4. **Volume Confirmation**: High volume during zone exits strengthens signals
5. **Trend Context**: Divergences more reliable against exhausted trends

## Best Practices

1. **Filter with trend** - Align signals with higher timeframe trend
2. **Wait for zone exits** - Don't enter immediately at crossovers
3. **Combine with price action** - Use at key support/resistance levels
4. **Quality divergences** - Require clear, well-defined swings
5. **Multi-step confirmation** - Use confirmed setups for highest probability

## Common Pitfalls

- Trading every crossover without zone context
- Ignoring the strength of divergences (clear vs weak)
- Not waiting for complete setup confirmation
- Over-optimizing parameters for historical data
- Missing the importance of zone duration

## Advanced Techniques

### Hidden Divergences
- **Bullish Hidden**: Higher low in price, lower low in stochastic (continuation)
- **Bearish Hidden**: Lower high in price, higher high in stochastic (continuation)

### Multiple Stochastic Strategy
- Use different periods (e.g., Stoch(5) and Stoch(14))
- Faster for entries, slower for trend confirmation

### Stochastic Patterns
- Double bottom/top in stochastic
- Failure swings (inability to reach opposite extreme)
- Hook patterns after extreme readings

## Risk Management

### Position Sizing
- Smaller size for basic crossovers
- Standard size for zone-based signals
- Larger size for confirmed setups

### Stop Loss Placement
- Basic signals: Beyond recent swing
- Zone signals: Beyond zone boundary
- Confirmed setups: Beyond structure break level

### Profit Targets
- Conservative: Return to 50 level
- Moderate: Opposite extreme zone
- Aggressive: Previous significant swing