# Ichimoku Cloud

## Overview

The Ichimoku Cloud (Ichimoku Kinko Hyo) is a comprehensive technical analysis system that defines support/resistance, trend direction, momentum, and trading signals in a single indicator. It provides a complete picture of price action through five key components and their interactions, making it particularly powerful for trend-following strategies.

## Core Components

The Ichimoku Cloud consists of five essential lines:

- **`tenkan_sen`** (Conversion Line): (9-period high + 9-period low) / 2
- **`kijun_sen`** (Base Line): (26-period high + 26-period low) / 2
- **`senkou_span_a`** (Leading Span A): (Tenkan-sen + Kijun-sen) / 2, plotted 26 periods ahead
- **`senkou_span_b`** (Leading Span B): (52-period high + 52-period low) / 2, plotted 26 periods ahead
- **`chikou_span`** (Lagging Span): Current close plotted 26 periods behind
- **`kumo`** (Cloud): Area between Senkou Span A and Senkou Span B

## Signal Categories

### 1. Kumo (Cloud) Relationship - Primary Trend Filter

The most fundamental aspect determining overall market bias and trend strength.

#### 🐂 Bullish Cloud Signals

##### Bullish Trend State
- **Type**: Confluence Filter
- **Description**: Market in confirmed uptrend, favor long positions only
- **Condition**: `close > senkou_span_a AND close > senkou_span_b`
- **Use Case**: Primary trend filter for all other signals

##### Strong Bullish Momentum
- **Type**: Trend Strength Indicator
- **Description**: Strong accelerating uptrend
- **Condition**: Large/increasing distance between close and top of cloud
- **Measurement**: `distance = close - max(senkou_span_a, senkou_span_b)`
- **Use Case**: Position sizing and confidence level

#### 🐻 Bearish Cloud Signals

##### Bearish Trend State
- **Type**: Confluence Filter
- **Description**: Market in confirmed downtrend, favor short positions only
- **Condition**: `close < senkou_span_a AND close < senkou_span_b`
- **Use Case**: Primary trend filter for all other signals

##### Strong Bearish Momentum
- **Type**: Trend Strength Indicator
- **Description**: Strong accelerating downtrend
- **Condition**: Large/increasing distance between close and bottom of cloud
- **Measurement**: `distance = min(senkou_span_a, senkou_span_b) - close`
- **Use Case**: Position sizing and confidence level

### 2. Tenkan/Kijun Crossover - Momentum Signals

Short-term momentum shifts similar to moving average crossovers.

#### 🐂 Bullish Crossover
- **Type**: Entry Trigger
- **Description**: Short-term momentum shift to upside
- **Trigger**: `tenkan_sen` crosses above `kijun_sen`
- **Best Used**: When price above cloud for trend confirmation

#### 🐻 Bearish Crossover
- **Type**: Entry Trigger
- **Description**: Short-term momentum shift to downside
- **Trigger**: `tenkan_sen` crosses below `kijun_sen`
- **Best Used**: When price below cloud for trend confirmation

### 3. Kumo Break & Retest Strategy - Primary Trading Setup

The signature Ichimoku trading strategy for trend continuation entries.

#### 🐂 Bullish Break & Retest
- **Type**: Multi-Step Setup
- **Step 1 (Trend Shift)**: Candle closes above both Span A and Span B after being below cloud
- **Step 2 (Entry Setup)**: Subsequent pullback where `low ≤ max(senkou_span_a, senkou_span_b)`
- **Step 3 (Optional Confirmation)**: Price makes new higher high after cloud retest
- **Entry**: On cloud retest (Step 2) or after confirmation (Step 3)
- **Use Case**: High-probability trend continuation trades

#### 🐻 Bearish Break & Retest
- **Type**: Multi-Step Setup
- **Step 1 (Trend Shift)**: Candle closes below both Span A and Span B after being above cloud
- **Step 2 (Entry Setup)**: Subsequent pullback where `high ≥ min(senkou_span_a, senkou_span_b)`
- **Step 3 (Optional Confirmation)**: Price makes new lower low after cloud retest
- **Entry**: On cloud retest (Step 2) or after confirmation (Step 3)
- **Use Case**: High-probability trend continuation trades

### 4. Chikou Span Confirmation - Additional Filter

Lagging span provides historical context and additional confirmation.

#### 🐂 Bullish Chikou Confirmation
- **Type**: Confluence Filter
- **Description**: No significant resistance in price history
- **Condition**: `chikou_span > senkou_span_a[-26] AND chikou_span > senkou_span_b[-26]`
- **Use Case**: Additional confirmation for bullish setups

#### 🐻 Bearish Chikou Confirmation
- **Type**: Confluence Filter
- **Description**: No significant support in price history
- **Condition**: `chikou_span < senkou_span_a[-26] AND chikou_span < senkou_span_b[-26]`
- **Use Case**: Additional confirmation for bearish setups

### 5. Neutral State

#### 😐 No Clear Trend
Conditions indicating sideways/consolidating market:
- Price trading inside the cloud (between Span A and Span B)
- Tenkan-sen and Kijun-sen intertwined and sideways
- Very thin/flat cloud indicating low volatility
- Conflicting signals from different components

## Database Storage Implementation

### PointIndicator Table

Ichimoku components stored as point-in-time data with future cloud projection.

```json
{
    "indicator": "ICHIMOKU",
    "time": "2024-01-01 12:00:00",
    "symbol": "BTC/USD",
    "timeframe": "1h",
    "value": {
        // Current values
        "tenkan_sen": 45800,
        "kijun_sen": 45600,
        "senkou_span_a": 45900,  // Current period's span A
        "senkou_span_b": 45500,  // Current period's span B
        "chikou_span": 45750,    // Current close plotted back

        // Cloud analysis
        "cloud_top": 45900,      // max(span_a, span_b)
        "cloud_bottom": 45500,   // min(span_a, span_b)
        "cloud_thickness": 400,  // Cloud width
        "cloud_color": "bullish", // "bullish" (span_a > span_b) or "bearish"

        // Price relationship
        "price_to_cloud": "above", // "above", "below", "inside"
        "cloud_distance": 200,   // Distance from price to cloud
        "trend_strength": "strong", // Based on distance and duration

        // Component relationships
        "tk_cross": null,        // "bullish" or "bearish" when crossover occurs
        "tk_relationship": "bullish", // Current tenkan vs kijun

        // Future cloud projection (next 26 periods)
        "future_cloud": [
            {"period": 1, "span_a": 45950, "span_b": 45550, "thick": 400},
            {"period": 2, "span_a": 46000, "span_b": 45600, "thick": 400},
            // ... up to period 26
        ],

        // Break & retest tracking
        "recent_break": null,    // Track recent cloud breaks
        "retest_setup": null,    // "bullish" or "bearish" when setup present
        "break_confirmed": false, // Track if break has been retested

        // Chikou analysis
        "chikou_cloud_position": "above", // Chikou vs historical cloud
        "chikou_confirmation": true,      // Clean vs conflicted

        // State tracking
        "setup_phase": 0,        // Track multi-step setup progress
        "last_cloud_break": null, // Time of last cloud break
        "time_above_cloud": 5,   // Periods above/below cloud
        "time_below_cloud": 0
    }
}
```

## Signal Generation Logic

### Cloud Relationship Analysis
```python
def analyze_cloud_relationship(current_price, span_a, span_b):
    """Determine price relationship to cloud"""
    cloud_top = max(span_a, span_b)
    cloud_bottom = min(span_a, span_b)

    if current_price > cloud_top:
        distance = current_price - cloud_top
        return {"position": "above", "distance": distance}
    elif current_price < cloud_bottom:
        distance = cloud_bottom - current_price
        return {"position": "below", "distance": distance}
    else:
        return {"position": "inside", "distance": 0}
```

### Tenkan/Kijun Crossover Detection
```python
def detect_tk_crossover(current, previous):
    """Detect Tenkan-sen / Kijun-sen crossovers"""
    if (previous.tenkan_sen <= previous.kijun_sen and
        current.tenkan_sen > current.kijun_sen):
        return "BULLISH_TK_CROSS"

    if (previous.tenkan_sen >= previous.kijun_sen and
        current.tenkan_sen < current.kijun_sen):
        return "BEARISH_TK_CROSS"

    return None
```

### Cloud Break Detection
```python
def detect_cloud_break(price_history, ichimoku_history):
    """Detect cloud breaks for break & retest setups"""
    current = price_history[-1]
    previous = price_history[-2]
    current_ich = ichimoku_history[-1]

    # Bullish cloud break
    if (previous.close <= min(current_ich.span_a, current_ich.span_b) and
        current.close > max(current_ich.span_a, current_ich.span_b)):
        return {"type": "bullish_break", "time": current.time}

    # Bearish cloud break
    if (previous.close >= max(current_ich.span_a, current_ich.span_b) and
        current.close < min(current_ich.span_a, current_ich.span_b)):
        return {"type": "bearish_break", "time": current.time}

    return None
```

### Break & Retest Setup Detection
```python
def detect_retest_setup(recent_break, current_candle, current_ichimoku):
    """Detect cloud retest opportunities after break"""
    if not recent_break:
        return None

    cloud_top = max(current_ichimoku.span_a, current_ichimoku.span_b)
    cloud_bottom = min(current_ichimoku.span_a, current_ichimoku.span_b)

    if recent_break.type == "bullish_break":
        # Look for pullback to cloud as support
        if current_candle.low <= cloud_top:
            return "BULLISH_RETEST_SETUP"

    elif recent_break.type == "bearish_break":
        # Look for pullback to cloud as resistance
        if current_candle.high >= cloud_bottom:
            return "BEARISH_RETEST_SETUP"

    return None
```

### Chikou Span Analysis
```python
def analyze_chikou_confirmation(chikou_span, historical_cloud, periods_back=26):
    """Analyze chikou span for confirmation"""
    # Get cloud values from 26 periods ago
    hist_span_a = historical_cloud[-periods_back].span_a
    hist_span_b = historical_cloud[-periods_back].span_b
    hist_cloud_top = max(hist_span_a, hist_span_b)
    hist_cloud_bottom = min(hist_span_a, hist_span_b)

    if chikou_span > hist_cloud_top:
        return "BULLISH_CONFIRMATION"
    elif chikou_span < hist_cloud_bottom:
        return "BEARISH_CONFIRMATION"
    else:
        return "NEUTRAL_CONFIRMATION"
```

## Trading Strategies

### Primary Strategy: Cloud Break & Retest

#### Bullish Setup
1. **Wait**: For price to break above cloud after being below
2. **Confirm**: Clean break with close above both spans
3. **Entry**: On pullback retest of cloud as support
4. **Stop Loss**: Below cloud or recent swing low
5. **Target**: Previous high or resistance level

#### Bearish Setup
1. **Wait**: For price to break below cloud after being above
2. **Confirm**: Clean break with close below both spans
3. **Entry**: On pullback retest of cloud as resistance
4. **Stop Loss**: Above cloud or recent swing high
5. **Target**: Previous low or support level

### Secondary Strategy: Tenkan/Kijun Crossover

#### Entry Conditions
- Crossover in direction of cloud bias
- Price already above/below cloud for trend confirmation
- Volume confirmation on crossover

#### Exit Conditions
- Opposite crossover
- Price returns to cloud
- Momentum divergence

### Advanced Strategy: Multiple Timeframe Ichimoku

#### HTF Bias
- Use daily/weekly cloud for primary trend
- Only trade in direction of HTF cloud position

#### LTF Entries
- Use 1H/4H for precise entries
- Wait for cloud break & retest on lower timeframe
- Align with HTF trend direction

## Key Parameters

### Standard Settings
- **Tenkan-sen**: 9 periods
- **Kijun-sen**: 26 periods
- **Senkou Span B**: 52 periods
- **Displacement**: 26 periods ahead/behind

### Alternative Settings
- **Faster**: 7, 22, 44 (more sensitive)
- **Slower**: 10, 30, 60 (smoother, less noise)
- **Crypto-optimized**: 20, 60, 120 (for 24/7 markets)

## Implementation Notes

1. **Future Cloud**: Essential for determining trend bias
2. **Clean Breaks**: Require decisive closes, not just wicks
3. **Retest Timing**: Usually occurs within 3-10 periods after break
4. **Multiple Touches**: Cloud may be tested multiple times before break
5. **Thick vs Thin Cloud**: Thicker clouds provide stronger support/resistance

## Best Practices

1. **Respect the cloud** - It's the primary trend filter
2. **Wait for clean breaks** - Avoid false breakouts with small wicks
3. **Use multiple timeframes** - Align cloud bias across timeframes
4. **Combine with volume** - Confirm breaks with volume spikes
5. **Be patient** - Wait for proper retest setups

## Common Pitfalls

- Trading against cloud bias
- Entering immediately on break without waiting for retest
- Ignoring chikou span confirmation
- Over-trading in neutral/choppy conditions
- Not adjusting parameters for different markets

## Advanced Concepts

### Cloud Twist
- When Span A crosses Span B (cloud changes color)
- Often indicates trend change
- More significant on higher timeframes

### Kumo Shadow
- Thin cloud areas that provide weaker support/resistance
- Price moves through these more easily
- Look for thicker cloud areas for stronger levels

### Time Elements
- Ichimoku incorporates time cycles (9, 26, 52)
- These periods often mark significant trend changes
- Monitor for confluence at these intervals

### Multiple Cloud Analysis
- Track clouds across multiple timeframes
- Daily cloud for bias, hourly for entries
- Weekly cloud for major trend context

## Risk Management

### Position Sizing
- Larger positions when all components align
- Smaller positions on basic crossovers
- Avoid trading when signals conflict

### Stop Loss Guidelines
- Basic setups: Other side of cloud
- Retest setups: Beyond recent swing
- Tight stops: Just outside cloud boundary

### Profit Targets
- Conservative: Previous swing high/low
- Moderate: Next significant resistance/support
- Aggressive: Measured moves or Fibonacci extensions