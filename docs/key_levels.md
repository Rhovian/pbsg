# Key Levels (Support & Resistance)

## Overview

Key Levels represent significant price points derived from Higher Timeframe (HTF) OHLC data that act as support and resistance zones. These levels are created by institutional activity and major market events, making them highly respected by market participants. The strategy focuses on trading reactions at these levels or their role reversals after breaks.

## Core Components

### HTF OHLC Data Sources

The system tracks OHLC values across multiple timeframes:

**Daily Levels:**
- `prev_daily_high`, `prev_daily_low`, `prev_daily_open`, `prev_daily_close`
- `current_daily_high`, `current_daily_low`, `current_daily_open`

**Weekly Levels:**
- `prev_week_high`, `prev_week_low`, `prev_week_open`, `prev_week_close`
- `current_week_high`, `current_week_low`, `current_week_open`

**Monthly Levels:**
- `prev_month_high`, `prev_month_low`, `prev_month_open`, `prev_month_close`
- `current_month_high`, `current_month_low`, `current_month_open`

### Level Classification

#### Support Zones
- **Definition**: HTF levels below current price
- **Function**: Expected buying pressure and potential bounce zones
- **Examples**: Previous week low when price is above it

#### Resistance Zones
- **Definition**: HTF levels above current price
- **Function**: Expected selling pressure and potential rejection zones
- **Examples**: Previous month high when price is below it

#### Confluence Zones
- **Definition**: Multiple HTF levels clustered at similar prices
- **Significance**: Higher probability zones due to multiple confluences
- **Examples**: Previous week high = Current month open

## Trading Strategies

### 1. Rejection/Fade Strategy

Trading reversals directly from key HTF levels with price action confirmation.

### 🐂 Bullish Rejection Setup

Trading bounces from support levels.

#### Step 1: Context Identification
- **Requirement**: Price trending down toward HTF support zone
- **Support Examples**:
  - Previous daily/weekly/monthly lows
  - Previous session closes
  - Current period opens
- **State**: "APPROACHING_SUPPORT"

#### Step 2: Level Test
- **Condition**: Current candle's `low` touches or trades below support level
- **Tolerance**: Small penetration acceptable (1-2 pips/ticks)
- **Volume**: Monitor for absorption at level
- **State**: "SUPPORT_TESTED"

#### Step 3: Bullish Confirmation
- **Requirements**: Clear bullish price action confirmation at support
- **Confirmation Signals**:
  - Bullish Engulfing candle
  - Hammer/Doji formation
  - Strong close back above level
  - Volume spike on reversal
- **Entry**: On confirmation candle completion
- **State**: "BULLISH_REJECTION_CONFIRMED"

### 🐻 Bearish Rejection Setup

Trading rejections from resistance levels.

#### Step 1: Context Identification
- **Requirement**: Price trending up toward HTF resistance zone
- **Resistance Examples**:
  - Previous daily/weekly/monthly highs
  - Previous session closes
  - Current period opens
- **State**: "APPROACHING_RESISTANCE"

#### Step 2: Level Test
- **Condition**: Current candle's `high` touches or trades above resistance level
- **Tolerance**: Small penetration acceptable
- **Volume**: Monitor for distribution at level
- **State**: "RESISTANCE_TESTED"

#### Step 3: Bearish Confirmation
- **Requirements**: Clear bearish price action confirmation at resistance
- **Confirmation Signals**:
  - Bearish Engulfing candle
  - Shooting Star/Doji formation
  - Strong close back below level
  - Volume spike on rejection
- **Entry**: On confirmation candle completion
- **State**: "BEARISH_REJECTION_CONFIRMED"

### 2. Break & Retest (S/R Flip) Strategy

Trading continuation moves after key level breaks with role reversal.

### 🐂 Bullish S/R Flip Setup

Trading retests of broken resistance as new support.

#### Step 1: Resistance Break
- **Requirement**: Decisive close above HTF resistance level
- **Confirmation**: Full candle body close, not just wick
- **Volume**: Preferably higher volume on break
- **Role Change**: Level now becomes potential support
- **State**: "RESISTANCE_BROKEN_BULLISH"

#### Step 2: Retest Wait
- **Condition**: Subsequent pullback to the broken level
- **Trigger**: Candle `low` touches the now-support level
- **Timing**: Usually occurs within 3-10 periods after break
- **Patience**: Don't chase if no retest occurs
- **State**: "SUPPORT_RETEST_SETUP"

#### Step 3: Bullish Retest Confirmation
- **Requirements**: Bullish price action at new support level
- **Confirmation Signals**:
  - Bullish reversal patterns
  - Strong rejection from level
  - Volume increase on bounce
- **Entry**: On confirmed bounce from new support
- **State**: "BULLISH_FLIP_CONFIRMED"

### 🐻 Bearish S/R Flip Setup

Trading retests of broken support as new resistance.

#### Step 1: Support Break
- **Requirement**: Decisive close below HTF support level
- **Confirmation**: Full candle body close, not just wick
- **Volume**: Preferably higher volume on break
- **Role Change**: Level now becomes potential resistance
- **State**: "SUPPORT_BROKEN_BEARISH"

#### Step 2: Retest Wait
- **Condition**: Subsequent rally to the broken level
- **Trigger**: Candle `high` touches the now-resistance level
- **Timing**: Usually occurs within 3-10 periods after break
- **Patience**: Don't chase if no retest occurs
- **State**: "RESISTANCE_RETEST_SETUP"

#### Step 3: Bearish Retest Confirmation
- **Requirements**: Bearish price action at new resistance level
- **Confirmation Signals**:
  - Bearish reversal patterns
  - Strong rejection from level
  - Volume increase on rejection
- **Entry**: On confirmed rejection from new resistance
- **State**: "BEARISH_FLIP_CONFIRMED"

### 😐 Neutral States

#### No Man's Land
- **Condition**: Price trading between widely spaced HTF levels
- **Characteristics**: No nearby key decision points
- **Action**: Wait for approach to significant levels
- **State**: "NO_KEY_LEVELS_NEARBY"

#### Indecision at Level
- **Condition**: Price chopping around HTF level without clear direction
- **Characteristics**: Multiple touches without decisive action
- **Action**: Wait for clear break or rejection
- **State**: "LEVEL_INDECISION"

## Database Storage Implementation

### RangeIndicator Table

Store HTF levels as range indicators with metadata.

```json
{
    "indicator": "HTF_LEVEL",
    "symbol": "BTC/USD",
    "timeframe": "15m",  // Current trading timeframe
    "range_high": 46050,  // Small range around level
    "range_low": 45950,
    "strength": 0.85,     // Based on timeframe and confluence
    "invalidated": false,
    "metadata": {
        "level_type": "previous_week_high",  // Specific level type
        "source_timeframe": "1W",            // Origin timeframe
        "exact_price": 46000,                // Precise level price
        "created_time": "2024-01-08 00:00:00", // When level was established
        "confluence_count": 2,               // Number of levels at same price
        "confluence_levels": [              // Other levels nearby
            "current_month_open",
            "previous_daily_high"
        ],

        // Historical performance
        "touch_count": 3,                    // Times level has been tested
        "hold_count": 2,                     // Times level held
        "break_count": 1,                    // Times level was broken
        "reliability": 0.67,                 // hold_count / touch_count

        // Recent interactions
        "last_test": "2024-01-15 10:00:00",
        "last_reaction": "bounce",           // "bounce", "break", "absorption"
        "current_role": "resistance",        // "support", "resistance", "neutral"

        // Level quality metrics
        "formation_volume": "high",          // Volume when level was created
        "institutional_level": true,         // If formed by major market event
        "time_significance": "high"          // How long level has been relevant
    }
}
```

### PointIndicator Table

Current key level context and active setups.

```json
{
    "indicator": "KEY_LEVELS_STATE",
    "time": "2024-01-15 12:00:00",
    "symbol": "BTC/USD",
    "timeframe": "15m",
    "value": {
        // Nearby levels analysis
        "nearest_support": {
            "level": 45300,
            "type": "previous_week_low",
            "distance": 200,
            "strength": 0.9,
            "confluence": true
        },
        "nearest_resistance": {
            "level": 46000,
            "type": "previous_month_high",
            "distance": 450,
            "strength": 0.85,
            "confluence": false
        },

        // Current market position
        "position_context": "mid_range",     // "approaching_support", "at_resistance", "mid_range"
        "trend_direction": "bullish",        // Overall trend bias
        "in_no_mans_land": false,           // Between widely spaced levels

        // Active setups
        "active_setup": {
            "type": "rejection",             // "rejection" or "break_retest"
            "bias": "bullish",               // Expected direction
            "target_level": 45300,
            "setup_phase": 2,                // Current step in process
            "confirmation_pending": true,
            "invalidation_level": 45250,
            "setup_start": "2024-01-15 11:30:00"
        },

        // Recent level interactions
        "recent_breaks": [
            {
                "level": 45800,
                "type": "previous_daily_high",
                "direction": "bullish",
                "time": "2024-01-14 15:00:00",
                "retest_pending": true
            }
        ],

        // Price action context
        "approaching_level": {
            "level": 45300,
            "type": "previous_week_low",
            "approach_angle": "steep",       // "gradual", "steep", "sideways"
            "approach_volume": "increasing",
            "time_to_level": 2              // Estimated periods to reach
        },

        // Confluence analysis
        "high_confluence_zones": [
            {
                "price_range": [45980, 46020],
                "levels": ["previous_month_high", "current_week_open"],
                "total_strength": 1.7,
                "zone_type": "resistance"
            }
        ]
    }
}
```

## Signal Generation Logic

### HTF Level Extraction
```python
def extract_htf_levels(ohlc_data):
    """Extract all relevant HTF levels from OHLC data"""
    levels = {}

    # Daily levels
    levels.update({
        "prev_daily_high": ohlc_data.daily.previous.high,
        "prev_daily_low": ohlc_data.daily.previous.low,
        "prev_daily_open": ohlc_data.daily.previous.open,
        "prev_daily_close": ohlc_data.daily.previous.close,
        "current_daily_open": ohlc_data.daily.current.open
    })

    # Weekly levels
    levels.update({
        "prev_week_high": ohlc_data.weekly.previous.high,
        "prev_week_low": ohlc_data.weekly.previous.low,
        "prev_week_open": ohlc_data.weekly.previous.open,
        "prev_week_close": ohlc_data.weekly.previous.close,
        "current_week_open": ohlc_data.weekly.current.open
    })

    # Monthly levels
    levels.update({
        "prev_month_high": ohlc_data.monthly.previous.high,
        "prev_month_low": ohlc_data.monthly.previous.low,
        "prev_month_open": ohlc_data.monthly.previous.open,
        "prev_month_close": ohlc_data.monthly.previous.close,
        "current_month_open": ohlc_data.monthly.current.open
    })

    return levels
```

### Confluence Detection
```python
def detect_confluence_zones(levels, tolerance_pct=0.1):
    """Identify clusters of HTF levels"""
    confluence_zones = []
    level_items = list(levels.items())

    for i, (name1, price1) in enumerate(level_items):
        confluent_levels = [name1]

        for j, (name2, price2) in enumerate(level_items[i+1:], i+1):
            if abs(price1 - price2) / price1 * 100 <= tolerance_pct:
                confluent_levels.append(name2)

        if len(confluent_levels) > 1:
            confluence_zones.append({
                "price": price1,
                "levels": confluent_levels,
                "strength": len(confluent_levels),
                "tolerance": tolerance_pct
            })

    return confluence_zones
```

### Level Role Classification
```python
def classify_level_roles(levels, current_price):
    """Classify levels as support or resistance based on current price"""
    classified = {
        "support_levels": [],
        "resistance_levels": [],
        "neutral_levels": []
    }

    for name, price in levels.items():
        distance_pct = abs(current_price - price) / current_price * 100

        if price < current_price:
            classified["support_levels"].append({
                "name": name,
                "price": price,
                "distance": current_price - price,
                "distance_pct": distance_pct
            })
        elif price > current_price:
            classified["resistance_levels"].append({
                "name": name,
                "price": price,
                "distance": price - current_price,
                "distance_pct": distance_pct
            })
        else:
            classified["neutral_levels"].append({
                "name": name,
                "price": price,
                "distance": 0
            })

    # Sort by distance
    classified["support_levels"].sort(key=lambda x: x["distance"])
    classified["resistance_levels"].sort(key=lambda x: x["distance"])

    return classified
```

### Rejection Signal Detection
```python
def detect_level_rejection(candle, level_price, level_type, tolerance=0.001):
    """Detect rejection signals at key levels"""

    if level_type == "support":
        # Check if low touched/broke level
        if candle.low <= level_price * (1 + tolerance):
            # Look for bullish confirmation
            if detect_bullish_reversal_pattern(candle):
                return "BULLISH_REJECTION"
            elif candle.close > level_price:
                return "POTENTIAL_BULLISH_REJECTION"

    elif level_type == "resistance":
        # Check if high touched/broke level
        if candle.high >= level_price * (1 - tolerance):
            # Look for bearish confirmation
            if detect_bearish_reversal_pattern(candle):
                return "BEARISH_REJECTION"
            elif candle.close < level_price:
                return "POTENTIAL_BEARISH_REJECTION"

    return None
```

### Break & Retest Detection
```python
def detect_break_and_retest(price_history, level_price, level_type):
    """Detect break and retest setups"""
    current_candle = price_history[-1]

    # Look for recent breaks
    for i in range(len(price_history) - 10, len(price_history)):
        candle = price_history[i]

        if level_type == "resistance":
            # Check for bullish break
            if candle.close > level_price:
                # Now look for retest
                if current_candle.low <= level_price and current_candle.close > level_price:
                    return "BULLISH_RETEST_SETUP"

        elif level_type == "support":
            # Check for bearish break
            if candle.close < level_price:
                # Now look for retest
                if current_candle.high >= level_price and current_candle.close < level_price:
                    return "BEARISH_RETEST_SETUP"

    return None
```

## Trading Rules

### Entry Conditions

#### Rejection Strategy
1. **Level Approach**: Price approaches key HTF level
2. **Level Test**: Price touches/slightly penetrates level
3. **Confirmation**: Clear reversal price action at level
4. **Volume**: Preferably higher volume on rejection
5. **Entry**: On confirmation candle close

#### Break & Retest Strategy
1. **Clean Break**: Decisive close beyond HTF level
2. **Role Reversal**: Broken level changes function
3. **Retest Wait**: Patience for pullback to level
4. **Confirmation**: Reversal signal at new role level
5. **Entry**: On confirmed bounce/rejection

### Risk Management

#### Stop Loss Placement
- **Rejection Trades**: Beyond the key level being tested
- **Retest Trades**: Beyond the retest level with buffer
- **Confluence Zones**: Wider stops due to higher significance

#### Position Sizing
- **Standard Levels**: Normal position size
- **Confluence Zones**: Larger size due to higher probability
- **Weak Levels**: Smaller size for levels with poor history

#### Profit Targets
- **Conservative**: Next HTF level
- **Moderate**: Previous swing high/low
- **Aggressive**: Measured moves or Fibonacci extensions

## Implementation Notes

1. **Level Precision**: Allow small tolerance around exact prices
2. **Timeframe Hierarchy**: Higher timeframes = more significant levels
3. **Historical Performance**: Track success rate of each level
4. **Multiple Touches**: Levels become stronger with successful tests
5. **Context Sensitivity**: Consider overall market structure

## Best Practices

1. **Quality over quantity** - Focus on the most significant levels
2. **Wait for confirmation** - Never enter on level touch alone
3. **Respect confluence** - Higher probability at clustered levels
4. **Track performance** - Monitor which levels work best
5. **Stay patient** - Best setups require waiting for proper conditions

## Common Pitfalls

- Trading every level regardless of significance
- Entering immediately on level touch without confirmation
- Ignoring the strength difference between timeframes
- Not tracking historical performance of levels
- Forgetting about confluence zones

## Advanced Concepts

### Level Hierarchy
- **Monthly**: Strongest, major institutional levels
- **Weekly**: Strong, significant for swing trading
- **Daily**: Moderate, good for day trading
- **Session**: Weakest, intraday reference points

### Level Evolution
- **Fresh Levels**: Newly created, untested
- **Respected Levels**: Successfully held multiple times
- **Broken Levels**: Failed, now serve opposite role
- **Forgotten Levels**: Too old to be relevant

### Institutional Behavior
- **Round Numbers**: Psychological levels (45000, 46000)
- **Previous Day Close**: Important for gap analysis
- **Session Opens**: Key reference points for institutions
- **Weekly/Monthly Opens**: Major algorithmic reference levels

### Multi-Timeframe Integration
- **HTF Bias**: Use monthly/weekly for major trend
- **Intermediate Levels**: Daily levels for swing context
- **Entry Timing**: Hourly levels for precise entries
- **Confluence Power**: Multiple timeframe level alignment