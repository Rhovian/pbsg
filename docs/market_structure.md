# Market Structure Documentation

## Overview

Market structure analysis is foundational to our trading system. It identifies key price points (swing highs/lows) and determines market state through the relationship between these points. All other signals derive from this structure.

## Core Components

### 1. Swing Points

The algorithm identifies two types of swing points:

- **Swing Highs**: Significant peak price points
- **Swing Lows**: Significant trough price points

#### Structure Types

- **Major (Swing) Structure**: Identified using larger lookback periods (e.g., 20+ candles)
- **Minor (Internal) Structure**: Identified using smaller lookback periods (e.g., 5-10 candles)

> **Note**: Breaks of Major/Swing Structure are more significant signals than Internal Structure breaks.

## Market States

### 🐂 Bullish Trend State

**Definition**: Sustained uptrend with dominant buying pressure. Long positions favored.

**Characteristics**:
- Series of Higher Highs (HH) and Higher Lows (HL)
- `current_swing_high > previous_swing_high`
- `current_swing_low > previous_swing_low`

### 🐻 Bearish Trend State

**Definition**: Sustained downtrend with dominant selling pressure. Short positions favored.

**Characteristics**:
- Series of Lower Lows (LL) and Lower Highs (LH)
- `current_swing_low < previous_swing_low`
- `current_swing_high < previous_swing_high`

### 😐 Neutral State

**Definition**: Market consolidation with no clear directional bias.

**Characteristics**:
- Price oscillating between defined swing high and swing low
- Failure to create new HH/HL or LL/LH
- Sideways range-bound movement

## Structural Events

### Break of Structure (BOS) - Trend Continuation

#### Bullish BOS
- **Prerequisites**: Market in Bullish Trend State
- **Trigger**: Price breaks and **closes above** previous swing high
- **Signal**: Confirms uptrend continuation

#### Bearish BOS
- **Prerequisites**: Market in Bearish Trend State
- **Trigger**: Price breaks and **closes below** previous swing low
- **Signal**: Confirms downtrend continuation

### Change of Character (CHOCH) - Potential Reversal

#### Bullish CHOCH
- **Prerequisites**: Market in Bearish Trend State
- **Trigger**: Price breaks and **closes above** most recent swing high (the LH that created the last LL)
- **Signal**: Potential reversal from bearish to bullish

#### Bearish CHOCH
- **Prerequisites**: Market in Bullish Trend State
- **Trigger**: Price breaks and **closes below** most recent swing low (the HL that created the last HH)
- **Signal**: Potential reversal from bullish to bearish

## Advanced Trading Setups

### Bullish Setup (Liquidity + FVG)

1. **Context**: Market in Bullish Trend or just printed Bullish CHOCH
2. **Setup**: Identify equal lows or significant swing low (liquidity pool)
3. **Liquidity Grab**: Price low trades below liquidity pool
4. **Entry Trigger**: Formation of Bullish FVG after liquidity grab
5. **Action**: Enter long within FVG price range

### Bearish Setup (Liquidity + FVG)

1. **Context**: Market in Bearish Trend or just printed Bearish CHOCH
2. **Setup**: Identify equal highs or significant swing high (liquidity pool)
3. **Liquidity Grab**: Price high trades above liquidity pool
4. **Entry Trigger**: Formation of Bearish FVG after liquidity grab
5. **Action**: Enter short within FVG price range

## Database Storage Implementation

### RangeIndicator Table

Stores individual swing points and structural events that persist over time.

#### Swing Point Storage
```json
{
    "indicator": "SWING_HIGH",  // or "SWING_LOW"
    "range_high": 46000,
    "range_low": 46000,  // Same as high for a point
    "strength": 0.8,  // Major vs minor (based on lookback)
    "invalidated": false,  // True when broken
    "metadata": {
        "structure_type": "major",  // "major" or "minor"
        "lookback_period": 20,
        "formed_at": "2024-01-01 12:00",
        "broken_by": null,  // Reference to break event
        "break_type": null  // "BOS" or "CHOCH" when broken
    }
}
```

#### Structural Event Storage
```json
{
    "indicator": "BULLISH_BOS",  // or BEARISH_BOS, BULLISH_CHOCH, BEARISH_CHOCH
    "range_high": 46100,  // Break level
    "range_low": 46000,   // The swing that was broken
    "strength": 1.0,  // Major breaks have higher strength
    "metadata": {
        "broke_swing_id": 123,
        "structure_type": "major",
        "close_price": 46050,  // Confirmation close
        "confirmed_at": "2024-01-01 14:00"
    }
}
```

#### Liquidity Pool Storage
```json
{
    "indicator": "EQUAL_HIGHS",  // or "EQUAL_LOWS"
    "range_high": 46000,
    "range_low": 45990,  // Small tolerance for "equal"
    "metadata": {
        "touch_count": 3,
        "swing_ids": [123, 456]  // Which swings form this level
    }
}
```

### PointIndicator Table

Stores current market structure state for quick access during signal generation.

```json
{
    "indicator": "MARKET_STRUCTURE",
    "value": {
        "trend_state": "BULLISH",  // BULLISH, BEARISH, or NEUTRAL
        "last_hh": {"price": 46000, "time": "2024-01-01 12:00", "id": 123},
        "last_hl": {"price": 45000, "time": "2024-01-01 10:00", "id": 122},
        "last_lh": null,
        "last_ll": null,
        "last_bos": {
            "type": "BULLISH_BOS",
            "price": 46000,
            "time": "2024-01-01 14:00"
        },
        "last_choch": null,
        "major_swings": [123, 122, 121],  // Recent major swing IDs
        "minor_swings": [456, 455, 454],  // Recent minor swing IDs
        "liquidity_pools": {
            "equal_highs": [{"price": 46000, "ids": [123, 124]}],
            "equal_lows": [{"price": 45000, "ids": [122, 121]}]
        }
    }
}
```

## Signal Generation Logic

### BOS Detection
```python
def detect_bos(current_price, market_state, swing_points):
    if market_state == "BULLISH":
        if current_price.close > previous_swing_high:
            return "BULLISH_BOS"
    elif market_state == "BEARISH":
        if current_price.close < previous_swing_low:
            return "BEARISH_BOS"
```

### CHOCH Detection
```python
def detect_choch(current_price, market_state, swing_points):
    if market_state == "BEARISH":
        # Breaking above LH indicates potential reversal
        if current_price.close > last_lower_high:
            return "BULLISH_CHOCH"
    elif market_state == "BULLISH":
        # Breaking below HL indicates potential reversal
        if current_price.close < last_higher_low:
            return "BEARISH_CHOCH"
```

### Advanced Setup Detection
```python
def detect_advanced_setup(market_structure, liquidity_pools, fvgs):
    # Check for liquidity grab
    liquidity_grabbed = check_liquidity_grab(current_price, liquidity_pools)

    if liquidity_grabbed:
        # Look for FVG formation after liquidity grab
        new_fvg = detect_fvg(recent_candles)

        if new_fvg and market_structure.trend_state == "BULLISH":
            return "BULLISH_SETUP"
        elif new_fvg and market_structure.trend_state == "BEARISH":
            return "BEARISH_SETUP"
```

## Key Considerations

1. **Close Confirmation**: All structural breaks require close above/below levels, not just wicks
2. **Major vs Minor**: Prioritize major structure breaks for primary signals
3. **Liquidity Pools**: Equal highs/lows act as magnets for price
4. **Multi-Timeframe**: Consider structure across multiple timeframes for confluence
5. **Invalidation**: Update swing points when broken and track the type of break

## Implementation Priority

1. **Phase 1**: Basic swing point detection and trend state determination
2. **Phase 2**: BOS and CHOCH detection
3. **Phase 3**: Liquidity pool identification
4. **Phase 4**: Advanced setups with FVG integration
5. **Phase 5**: Multi-timeframe structure analysis