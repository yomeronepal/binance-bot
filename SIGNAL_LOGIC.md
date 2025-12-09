# Signal Generation Logic

## Overview

The trading bot uses a **weighted multi-indicator scoring system** to generate LONG and SHORT signals. Each signal requires meeting a minimum confidence threshold calculated from 14 technical indicators.

## Strategy Type

**RSI-based Mean Reversion with Trend Confirmation**

- LONG signals: Buy when oversold (RSI 25-35) with bullish confirmation
- SHORT signals: Sell when overbought (RSI 65-75) with bearish confirmation

## Signal Flow

```
Market Data → Indicator Calculation → Condition Checks → Weighted Scoring → Confidence Calculation → Signal Generation
```

## Technical Indicators Used (14 Total)

| Indicator | Weight | Purpose |
|-----------|--------|---------|
| Fibonacci Pullback | 2.5 | Golden ratio zone confirmation |
| MACD | 2.0 | Momentum crossover detection |
| SuperTrend | 1.9 | Trend following confirmation |
| Price vs EMA50 | 1.8 | Trend direction |
| ADX | 1.7 | Trend strength measurement |
| Heikin Ashi | 1.6 | Smoothed trend direction |
| RSI | 1.5 | Overbought/oversold levels |
| Volume | 1.4 | Interest confirmation |
| MFI | 1.3 | Volume-weighted momentum |
| EMA Alignment | 1.2 | Multi-timeframe alignment |
| Parabolic SAR | 1.1 | Trend reversal detection |
| +DI/-DI | 1.0 | Directional movement |
| Bollinger Bands | 0.8 | Volatility and price extremes |
| Volatility (ATR) | 0.5 | Market condition adjustment |

## LONG Signal Conditions

A LONG signal is generated when:

1. **MACD Crossover** - MACD histogram crosses from negative to positive
2. **RSI Favorable** - RSI between 25-35 (oversold) OR rising RSI
3. **Price Above EMA50** - Close price > 50-period EMA
4. **Strong Trend** - ADX > 22
5. **Heikin Ashi Bullish** - Green Heikin Ashi candle
6. **Volume Spike** - Volume > 1.2x average
7. **EMA Alignment** - EMA9 > EMA21 > EMA50
8. **Positive DI** - +DI > -DI
9. **Bollinger Favorable** - Price in lower-middle band area
10. **Low Volatility** - ATR% < 2-4%
11. **SuperTrend Bullish** - Price above SuperTrend line
12. **MFI Favorable** - MFI between 20-50 or rising
13. **PSAR Bullish** - Price above Parabolic SAR
14. **Fibonacci Pullback** - Price in 50%-61.8% retracement zone

## SHORT Signal Conditions

A SHORT signal is generated when:

1. **MACD Crossover** - MACD histogram crosses from positive to negative
2. **RSI Favorable** - RSI between 65-75 (overbought) OR falling RSI
3. **Price Below EMA50** - Close price < 50-period EMA
4. **Strong Trend** - ADX > 22
5. **Heikin Ashi Bearish** - Red Heikin Ashi candle
6. **Volume Spike** - Volume > 1.2x average
7. **EMA Alignment** - EMA9 < EMA21 < EMA50
8. **Negative DI** - -DI > +DI
9. **Bollinger Favorable** - Price in upper-middle band area
10. **Low Volatility** - ATR% < 2-4%
11. **SuperTrend Bearish** - Price below SuperTrend line
12. **MFI Favorable** - MFI between 50-80 or falling
13. **PSAR Bearish** - Price below Parabolic SAR
14. **Fibonacci Pullback** - Price in 50%-61.8% retracement zone

## Confidence Calculation

```
Raw Confidence = (Sum of Triggered Weights) / (Maximum Possible Score)
```

A non-linear transformation is applied to prevent unrealistically high confidence:
- Raw 88-100% → Adjusted 78-92%
- Raw 75-88% → Adjusted 68-78%
- Raw 0-75% → Adjusted 0-68%

**Maximum confidence is capped at 92%**

## Signal Filters (Pre-Checks)

Before checking indicator conditions, signals must pass these filters:

### 1. Ranging Market Filter (ADX < 18)
Signals are skipped when ADX < 18 to avoid false breakouts in choppy markets.

### 2. Volume Spike Confirmation
Requires volume > 1.2x the 20-period moving average to confirm momentum.

### 3. Multi-Timeframe Confirmation (Phase 2)
- 15m signals require 1h trend alignment
- 1h signals require 4h trend alignment
- 4h and 1d signals proceed without higher TF check

LONG signals are skipped if higher timeframe shows BEARISH trend.
SHORT signals are skipped if higher timeframe shows BULLISH trend.

## Risk Management

### Fixed Percentage-Based Stop Loss and Take Profit

| Parameter | Value |
|-----------|-------|
| Risk (Stop Loss) | 3% from entry |
| Reward (Take Profit) | 9% from entry |
| Risk/Reward Ratio | 1:3 |

### Calculation Examples

**LONG Signal at $100:**
- Entry: $100.00
- Stop Loss: $97.00 (3% below entry)
- Take Profit: $109.00 (9% above entry)

**SHORT Signal at $100:**
- Entry: $100.00
- Stop Loss: $103.00 (3% above entry)
- Take Profit: $91.00 (9% below entry)

## Configuration Parameters

```python
SignalConfig:
    long_rsi_min: 25.0          # Minimum RSI for LONG
    long_rsi_max: 35.0          # Maximum RSI for LONG
    short_rsi_min: 65.0         # Minimum RSI for SHORT
    short_rsi_max: 75.0         # Maximum RSI for SHORT
    long_adx_min: 22.0          # Minimum ADX for LONG
    short_adx_min: 22.0         # Minimum ADX for SHORT
    min_confidence: 0.75        # 75% minimum confidence required
    signal_expiry_minutes: 60   # Signal valid for 60 minutes
```

## Fibonacci Pullback Detection

The bot identifies swing high/low points and calculates Fibonacci retracement levels:

- **38.2%** - Shallow retracement
- **50.0%** - Half retracement
- **61.8%** - Golden ratio (primary entry zone)
- **78.6%** - Deep retracement

**Entry Zone: 50% to 61.8% retracement (Golden Zone)**

When price pulls back to this zone after a trend move, it confirms a high-probability entry.

## Signal Lifecycle

```
1. CREATED    → New signal detected, meets all criteria
2. UPDATED    → Confidence changed by more than 5%
3. INVALIDATED → Conditions no longer valid (confidence dropped 30%+)
4. EXPIRED    → Signal older than 60 minutes
```

## Timeframes Supported

| Timeframe | Use Case |
|-----------|----------|
| 15m | Scalping (requires 1h confirmation) |
| 1h | Intraday (requires 4h confirmation) |
| 4h | Swing trading (no confirmation needed) |
| 1d | Position trading (no confirmation needed) |

## Volatility-Aware Mode (Optional)

When enabled, parameters auto-adjust based on symbol volatility:

- **Low Volatility** (BTC): Tighter SL/TP, lower ADX threshold
- **Medium Volatility** (ETH, SOL): Standard parameters
- **High Volatility** (DOGE, SHIB): Wider SL/TP, higher ADX threshold

## Mathematical Requirements for Profitability

With 1:3 Risk/Reward ratio:
```
Breakeven Win Rate = 1 / (1 + R/R) = 1 / (1 + 3) = 25%
```

Any win rate above 25% will be profitable with this strategy.

## Signal Output Format

```json
{
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "entry_price": 42000.00,
  "stop_loss": 40740.00,
  "take_profit": 45780.00,
  "confidence": 0.78,
  "timeframe": "4h",
  "status": "ACTIVE",
  "description": "LONG setup: MACD crossover, RSI 28.5, ADX 24.3 (12/14 conditions)",
  "created_at": "2024-12-09T10:30:00Z"
}
```

## Performance Metrics

With optimized parameters (OPT6):
- **Win Rate**: ~25-30%
- **Risk/Reward**: 1:3
- **Expected Value**: Positive at >25% win rate
- **Best Timeframe**: 4h
- **Best Symbol**: BTCUSDT (lower volatility)
