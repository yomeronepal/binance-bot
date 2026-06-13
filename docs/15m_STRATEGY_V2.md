# 15-Minute Market Structure Pullback Strategy

## Overview

The Market Structure Pullback Strategy is a trend-following algorithmic trading system designed for cryptocurrency markets on the 15-minute timeframe.

Unlike traditional RSI mean-reversion systems, this strategy focuses on trading in the direction of higher-timeframe trends while entering during temporary pullbacks.

The strategy combines:

* Multi-timeframe trend analysis
* Market structure confirmation
* EMA/VWAP pullback entries
* Volume confirmation
* Momentum validation
* ATR-based risk management

The objective is to capture trend continuation moves while avoiding counter-trend trades and low-quality market conditions.

---

# Strategy Logic

## Trading Philosophy

The strategy assumes:

1. Strong trends tend to continue.
2. Pullbacks provide better risk/reward entries.
3. Volume confirms institutional participation.
4. Market structure provides the most reliable directional information.
5. Higher-timeframe alignment improves trade quality.

---

# Multi-Timeframe Trend Filter

## Primary Trend (1H)

The strategy first determines the dominant trend using the 1-hour timeframe.

### Bullish Trend

Conditions:

* EMA50 > EMA200

### Bearish Trend

Conditions:

* EMA50 < EMA200

### Trading Rules

LONG trades are only allowed during bullish trends.

SHORT trades are only allowed during bearish trends.

If trend direction is unclear, no trade is generated.

---

# Market Structure Analysis

## Bullish Structure

Required:

* Higher High (HH)
* Higher Low (HL)

Structure definition:

Current Swing High > Previous Swing High

AND

Current Swing Low > Previous Swing Low

---

## Bearish Structure

Required:

* Lower High (LH)
* Lower Low (LL)

Structure definition:

Current Swing High < Previous Swing High

AND

Current Swing Low < Previous Swing Low

---

# Entry Conditions

## LONG Setup

All conditions must be satisfied:

### Trend Filter

* 1H EMA50 > EMA200

### Structure Filter

* Higher High
* Higher Low

### Pullback Zone

Price retraces into one of:

* EMA20
* VWAP
* EMA50

### Momentum Confirmation

* RSI > 50
* MACD Histogram Rising

### Volume Confirmation

Volume > 1.3 × 20-period Average Volume

### Trend Strength

ADX > 20

### Liquidity Sweep (Optional but Recommended)

Price sweeps previous low and closes back above it.

---

## SHORT Setup

All conditions must be satisfied:

### Trend Filter

* 1H EMA50 < EMA200

### Structure Filter

* Lower High
* Lower Low

### Pullback Zone

Price retraces into one of:

* EMA20
* VWAP
* EMA50

### Momentum Confirmation

* RSI < 50
* MACD Histogram Falling

### Volume Confirmation

Volume > 1.3 × 20-period Average Volume

### Trend Strength

ADX > 20

### Liquidity Sweep (Optional but Recommended)

Price sweeps previous high and closes back below it.

---

# Signal Scoring System

| Component           | Weight |
| ------------------- | ------ |
| 1H Trend Filter     | 3.0    |
| Market Structure    | 3.0    |
| Volume Confirmation | 2.0    |
| Pullback Zone       | 2.0    |
| MACD Momentum       | 1.5    |
| RSI Momentum        | 1.0    |
| ATR Regime          | 1.0    |

Maximum Score = 13.5

---

# Signal Requirements

Minimum Score:

8.5 / 13.5

Equivalent Confidence:

63%+

Signals below this threshold are ignored.

---

# Risk Management

## Stop Loss

ATR-based dynamic stop:

Stop Loss = Entry Price ± (1.8 × ATR)

LONG:

SL = Entry − (1.8 × ATR)

SHORT:

SL = Entry + (1.8 × ATR)

---

## Take Profit

### TP1

2 × ATR

Close 50% position

---

### TP2

4 × ATR

Close 30% position

---

### Runner Position

20% position remains open.

Managed with ATR trailing stop.

---

# Trailing Stop

## LONG

Highest Price − (2 × ATR)

## SHORT

Lowest Price + (2 × ATR)

The trailing stop allows profits to run during strong trends.

---

# Position Sizing

Maximum risk per trade:

0.5% – 1.0% of account balance.

Position Size Formula:

Position Size =
(Account Risk) ÷ (Stop Loss Distance)

Example:

Account Size: $10,000

Risk: 1%

Maximum Loss: $100

If stop distance = $50

Position Size = 2 Contracts

---

# Market Conditions to Avoid

Do not trade when:

* ADX < 20
* Volume below average
* Trend direction unclear
* Major news events
* Extremely high ATR spikes
* Spread exceeds acceptable limits

---

# Recommended Markets

Suitable:

* BTCUSDT
* ETHUSDT
* SOLUSDT
* BNBUSDT
* High-liquidity futures pairs

Avoid:

* Low-volume altcoins
* Newly listed tokens
* Illiquid meme coins

---

# Performance Goals

Target Metrics:

| Metric        | Target     |
| ------------- | ---------- |
| Win Rate      | 35% – 50%  |
| Profit Factor | > 1.4      |
| Risk Reward   | 1:2 to 1:4 |
| Max Drawdown  | < 15%      |
| Sharpe Ratio  | > 1.5      |

---

# Future Enhancements

Planned improvements:

* Funding Rate Filter
* Open Interest Confirmation
* Volume Profile Analysis
* Order Flow Integration
* Liquidation Heatmap Detection
* Dynamic ATR Multipliers
* Regime Classification Engine

---

# Disclaimer

This strategy is intended for research and educational purposes only.

Past performance does not guarantee future results.

Always forward-test and paper trade before deploying capital.
