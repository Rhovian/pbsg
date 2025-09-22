# Fair Value Gaps (FVG)

## Overview

Fair Value Gaps represent price inefficiencies where the market moved so quickly that it left an imbalance between buyers and sellers. These gaps often act as magnets for price, providing high-probability support/resistance zones for entries and exits. FVGs are particularly powerful when identified on higher timeframes and traded on lower timeframes.

## Core Concepts

### What is an FVG?

A Fair Value Gap is created when there's a price gap between candles, specifically:
- **Bullish FVG**: Gap up where Candle 3's low > Candle 1's high
- **Bearish FVG**: Gap down where Candle 3's high < Candle 1's low

### Required Variables

For each active FVG, the system tracks:
- **`fvg_type`**: Direction of the gap ("bullish" or "bearish")
- **`fvg_high`**: Upper boundary of the FVG zone
- **`fvg_low`**: Lower boundary of the FVG zone
- **`fvg_created_at`**: When the FVG was formed
- **`fvg_timeframe`**: Timeframe where FVG was identified (HTF preferred)
- **`fvg_mitigated`**: Whether the gap has been filled/mitigated

## Signal Types

### 🐂 Bullish FVG Signals

Bullish FVGs act as support zones where price is expected to bounce.

#### 1. Bullish Rejection Signal (Entry Trigger)
- **Description**: Price tests bullish FVG from above and rejects, confirming support
- **Setup Requirements**:
  - FVG type must be "bullish"
  - Prior/current candle's `low ≤ fvg_high` (price entered the zone)
- **Trigger**: `close > fvg_high` (price closes back above the zone)
- **Trading Implication**: Strong long entry signal

#### 2. Bullish Acceptance State (Confluence Filter)
- **Description**: Price trading within bullish FVG zone
- **Condition**: `high > fvg_low AND low < fvg_high`
- **State Variable**: `in_bullish_fvg_zone = true`
- **Trading Implication**: Increases probability of other bullish signals

### 🐻 Bearish FVG Signals

Bearish FVGs act as resistance zones where price is expected to reverse.

#### 1. Bearish Rejection Signal (Entry Trigger)
- **Description**: Price tests bearish FVG from below and rejects, confirming resistance
- **Setup Requirements**:
  - FVG type must be "bearish"
  - Prior/current candle's `high ≥ fvg_low` (price entered the zone)
- **Trigger**: `close < fvg_low` (price closes back below the zone)
- **Trading Implication**: Strong short entry signal

#### 2. Bearish Acceptance State (Confluence Filter)
- **Description**: Price trading within bearish FVG zone
- **Condition**: `high > fvg_low AND low < fvg_high`
- **State Variable**: `in_bearish_fvg_zone = true`
- **Trading Implication**: Increases probability of other bearish signals

### 😐 Neutral State

No FVG influence when:
- No active FVG present (`fvg_type` is null)
- Price trading entirely above bullish FVG (no recent test)
- Price trading entirely below bearish FVG (no recent test)
- FVG has been fully mitigated/filled

## FVG Detection Algorithm

### Bullish FVG Formation
```python
def detect_bullish_fvg(candles):
    """
    Bullish FVG: Gap between candle 1 high and candle 3 low
    """
    if len(candles) < 3:
        return None

    candle1, candle2, candle3 = candles[-3:]

    # Bullish momentum required
    if not (candle3.close > candle3.open and
            candle2.close > candle2.open):
        return None

    # Check for gap
    if candle3.low > candle1.high:
        return {
            "type": "bullish",
            "high": candle3.low,    # Top of FVG
            "low": candle1.high,     # Bottom of FVG
            "created_at": candle3.time,
            "candle_indices": [-3, -2, -1]
        }

    return None
```

### Bearish FVG Formation
```python
def detect_bearish_fvg(candles):
    """
    Bearish FVG: Gap between candle 1 low and candle 3 high
    """
    if len(candles) < 3:
        return None

    candle1, candle2, candle3 = candles[-3:]

    # Bearish momentum required
    if not (candle3.close < candle3.open and
            candle2.close < candle2.open):
        return None

    # Check for gap
    if candle3.high < candle1.low:
        return {
            "type": "bearish",
            "high": candle1.low,     # Top of FVG
            "low": candle3.high,     # Bottom of FVG
            "created_at": candle3.time,
            "candle_indices": [-3, -2, -1]
        }

    return None
```

## Database Storage Implementation

### RangeIndicator Table

FVGs are stored as range indicators since they persist until mitigated.

```json
{
    "indicator": "FVG",
    "symbol": "BTC/USD",
    "timeframe": "1h",  // HTF where FVG was detected
    "range_high": 46500,  // fvg_high
    "range_low": 46200,   // fvg_low
    "strength": 0.8,  // Based on gap size and timeframe
    "invalidated": false,  // Becomes true when mitigated
    "metadata": {
        "fvg_type": "bullish",  // or "bearish"
        "gap_size": 300,  // Price difference
        "gap_percentage": 0.65,  // Percentage of price
        "created_at": "2024-01-01 12:00",
        "forming_candles": [  // The 3 candles that created FVG
            {"time": "11:00", "high": 46200, "low": 46000},
            {"time": "11:15", "high": 46400, "low": 46100},
            {"time": "11:30", "high": 46700, "low": 46500}
        ],
        "tests": [  // Track each time price tests the FVG
            {"time": "13:00", "touched": true, "rejected": true},
            {"time": "14:00", "touched": true, "rejected": false}
        ],
        "mitigation": {
            "partial": false,  // True if partially filled
            "full": false,     // True if completely filled
            "mitigation_time": null,
            "mitigation_price": null
        }
    }
}
```

### PointIndicator Table

Current FVG interaction state for quick signal generation.

```json
{
    "indicator": "FVG_STATE",
    "symbol": "BTC/USD",
    "timeframe": "15m",
    "value": {
        "active_fvgs": [
            {
                "id": 123,
                "type": "bullish",
                "high": 46500,
                "low": 46200,
                "timeframe": "1h",
                "distance_from_price": 150,  // Current price distance
                "in_zone": false
            }
        ],
        "current_state": {
            "in_bullish_zone": false,
            "in_bearish_zone": false,
            "last_test": null,
            "last_rejection": null
        },
        "recent_signals": [
            {
                "type": "bullish_rejection",
                "time": "2024-01-01 14:00",
                "fvg_id": 123,
                "entry_price": 46510
            }
        ]
    }
}
```

## Signal Generation Logic

### FVG Rejection Detection
```python
def detect_fvg_rejection(current_candle, previous_candle, fvg):
    """Detect if price rejected from FVG zone"""

    if fvg.type == "bullish":
        # Price entered from above?
        entered = previous_candle.low <= fvg.high
        # Price closed back above?
        rejected = current_candle.close > fvg.high

        if entered and rejected:
            return "BULLISH_REJECTION"

    elif fvg.type == "bearish":
        # Price entered from below?
        entered = previous_candle.high >= fvg.low
        # Price closed back below?
        rejected = current_candle.close < fvg.low

        if entered and rejected:
            return "BEARISH_REJECTION"

    return None
```

### FVG Zone Detection
```python
def check_fvg_zone(current_price, fvg):
    """Check if price is within FVG zone"""

    in_zone = (current_price.high > fvg.low and
               current_price.low < fvg.high)

    if in_zone:
        if fvg.type == "bullish":
            return "IN_BULLISH_FVG_ZONE"
        else:
            return "IN_BEARISH_FVG_ZONE"

    return None
```

### FVG Mitigation Tracking
```python
def check_fvg_mitigation(candle, fvg):
    """Check if FVG has been mitigated/filled"""

    if fvg.type == "bullish":
        # Bullish FVG mitigated if price trades through bottom
        if candle.low < fvg.low:
            return {"mitigated": True, "type": "full"}
        elif candle.low < (fvg.low + fvg.high) / 2:
            return {"mitigated": False, "type": "partial"}

    elif fvg.type == "bearish":
        # Bearish FVG mitigated if price trades through top
        if candle.high > fvg.high:
            return {"mitigated": True, "type": "full"}
        elif candle.high > (fvg.low + fvg.high) / 2:
            return {"mitigated": False, "type": "partial"}

    return {"mitigated": False, "type": None}
```

## Trading Strategies

### Primary FVG Trading

#### Bullish FVG Trade
1. **Identify**: Bullish FVG on HTF (1h, 4h, Daily)
2. **Wait**: For price to retrace to FVG zone
3. **Entry**: When price rejects from zone (closes above)
4. **Stop Loss**: Below FVG low
5. **Target**: Previous high or next resistance

#### Bearish FVG Trade
1. **Identify**: Bearish FVG on HTF
2. **Wait**: For price to retrace to FVG zone
3. **Entry**: When price rejects from zone (closes below)
4. **Stop Loss**: Above FVG high
5. **Target**: Previous low or next support

### FVG Confluence Trading

#### With Market Structure
- Bullish FVG + Higher Low = Strong long signal
- Bearish FVG + Lower High = Strong short signal

#### With Other Indicators
- FVG + RSI divergence = High probability reversal
- FVG + MACD cross = Confirmed entry
- FVG + Volume spike = Institutional interest

### Advanced FVG Concepts

#### Nested FVGs
- Multiple FVGs at different timeframes
- Higher timeframe FVGs have priority
- Stack FVGs for stronger zones

#### FVG Mitigation Levels
- 25% fill = Weak mitigation
- 50% fill = Partial mitigation (monitor closely)
- 75% fill = Strong mitigation (likely to fill completely)
- 100% fill = FVG invalidated

## Implementation Notes

1. **HTF Priority**: Always prioritize higher timeframe FVGs
2. **Multiple FVGs**: Track multiple active FVGs simultaneously
3. **Mitigation Tracking**: Update FVG status in real-time
4. **Zone Respect**: Some FVGs act as zones repeatedly before mitigation
5. **Context Matters**: FVGs in trending markets more reliable than ranging

## Best Practices

1. **Wait for confirmation** - Don't enter immediately when price touches FVG
2. **Use HTF FVGs** - Daily and 4H FVGs are most reliable
3. **Combine with structure** - FVGs work best at key structural levels
4. **Track mitigation** - Remove or update FVGs once mitigated
5. **Size matters** - Larger gaps (>0.5% of price) are more significant

## Common Pitfalls

- Trading every FVG regardless of context
- Ignoring partial mitigation
- Not waiting for rejection confirmation
- Using too low timeframes (noise)
- Not considering overall trend

## Quality Metrics

### FVG Strength Factors
1. **Gap Size**: Larger gaps = stronger zones
2. **Timeframe**: Higher timeframe = more significant
3. **Volume**: High volume during formation = institutional
4. **Clean Formation**: Clear 3-candle pattern
5. **First Test**: Untested FVGs have highest probability

### FVG Weakness Signs
- Multiple tests without clear rejection
- Partial mitigation on first test
- Formation in choppy/ranging market
- Very small gap size (<0.2% of price)
- Counter to dominant trend