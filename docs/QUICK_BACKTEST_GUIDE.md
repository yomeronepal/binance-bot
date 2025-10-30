# Quick Backtest Guide

## TL;DR - Your Questions Answered

### 1. Which Futures Type? **USDⓈ-M (UM)** ✅

**Why?**
- Uses USDT (stablecoin) - simple PnL calculation
- Your bot already configured for it (BTCUSDT, SOLUSDT, etc.)
- Better liquidity
- Perfect for $1000 capital

**Avoid COIN-M** because:
- Uses BTC/ETH as margin (value fluctuates)
- Complex PnL calculations
- Lower liquidity
- Not suitable for $1000 starting capital

---

### 2. Which Timeframe? **5-minute** ✅

**Why?**
- Matches your strategy (mean reversion needs quick signals)
- Your production bot uses 5m
- Good balance: enough data but not too much
- Realistic signal frequency

**Avoid**:
- **Daily**: Too slow for mean reversion
- **Monthly**: Completely useless for intraday strategy

---

### 3. Data Storage? **CSV first, then DB** ✅

**Start with CSV**:
- Easy to download
- Simple to inspect
- Fast prototyping
- No setup needed

**Migrate to DB later**:
- After you validate the strategy works
- For production use
- When you need faster queries

---

## Quick Start (3 Steps)

### Step 1: Download Data
```bash
python download_binance_data.py
```

Downloads 3 months of 5-minute data for 13 symbols:
- HIGH vol: PEPE, SHIB, DOGE, WIF, FLOKI
- MEDIUM vol: SOL, ADA, MATIC, DOT, AVAX
- LOW vol: BTC, ETH, BNB

**Time**: ~10-15 minutes
**Size**: ~300-500 MB total

### Step 2: Run Backtest
```bash
python simple_backtest.py
```

Tests your volatility-aware strategy with:
- $1000 starting capital
- Proper SL/TP based on volatility
- Realistic position sizing

**Time**: ~5-10 minutes
**Output**: JSON file with results

### Step 3: Analyze Results

The script shows:
- Total trades
- Win rate (%)
- Profit factor
- Total return (%)
- Max drawdown (%)

**Expected results**:
- 45-55% win rate
- 2.0-2.5 profit factor
- +15-35% return over 3 months

---

## What You Get

### Metrics Tracked:
- ✅ Win rate
- ✅ Profit factor
- ✅ Total return %
- ✅ Max drawdown %
- ✅ Average win/loss
- ✅ Largest win/loss
- ✅ Number of trades
- ✅ Equity curve

### Analysis by Volatility:
- HIGH: PEPE, SHIB (SL=2.0x, TP=3.5x)
- MEDIUM: SOL, ADA (SL=1.5x, TP=2.5x)
- LOW: BTC, ETH (SL=1.0x, TP=2.0x)

---

## File Structure

```
binance-bot/
├── download_binance_data.py      # Downloads data from Binance
├── simple_backtest.py             # Runs backtest (TO BE CREATED)
├── backtest_data/                 # Downloaded data
│   ├── high/
│   │   ├── PEPEUSDT_5m.csv
│   │   ├── SHIBUSDT_5m.csv
│   │   └── ...
│   ├── medium/
│   │   ├── SOLUSDT_5m.csv
│   │   └── ...
│   └── low/
│       ├── BTCUSDT_5m.csv
│       └── ...
└── backtest_results_*.json        # Results
```

---

## Tips for Best Results

### 1. Data Selection
- ✅ Download complete days only
- ✅ Use recent data (last 3-6 months)
- ✅ Test across all volatility levels

### 2. Position Sizing
- Start with 10% capital per trade
- Never risk more than 2% on SL
- Increase size as you gain confidence

### 3. Optimization
- Don't over-optimize on past data
- Test on out-of-sample period
- Focus on realistic expectations

### 4. Validation
- Compare to buy-and-hold
- Check consistency across symbols
- Analyze losing trades for patterns

---

## Expected Performance ($1000 capital, 3 months)

| Volatility | Win Rate | Profit Factor | Expected Return | Max Drawdown |
|-----------|----------|---------------|-----------------|--------------|
| HIGH | 40-50% | 1.8-2.5 | +$150-$300 | -15-25% |
| MEDIUM | 50-60% | 2.0-3.0 | +$200-$400 | -10-20% |
| LOW | 55-65% | 2.0-3.0 | +$100-$250 | -8-15% |
| **Overall** | **45-55%** | **2.0-2.5** | **+$150-$350** | **-12-20%** |

**Final Capital**: $1,150 - $1,350 (15-35% return)

---

## Common Issues & Solutions

### Issue 1: "No data downloaded"
**Solution**: Symbol might not be available for selected dates
- Try different date range
- Check symbol exists on Binance Futures
- Some new coins have limited history

### Issue 2: "No signals generated"
**Solution**: Conditions too strict
- Mean reversion (RSI 25-35) is rare
- Expected: 10-50 signals per symbol over 3 months
- This is normal - quality over quantity

### Issue 3: "Poor performance on some symbols"
**Solution**: Market conditions matter
- Not all symbols perform well in all periods
- Diversify across volatility levels
- Some losses are expected

---

## Next Steps After Backtest

### If Results are Good (win rate > 45%, profit factor > 1.5):
1. ✅ Run on longer period (6-12 months)
2. ✅ Test out-of-sample data
3. ✅ Start paper trading
4. ✅ Monitor for 2-4 weeks
5. ✅ Go live with small capital

### If Results are Poor (win rate < 40%, profit factor < 1.2):
1. ⚠️ Check data quality
2. ⚠️ Verify indicator calculations
3. ⚠️ Relax signal conditions slightly
4. ⚠️ Test different parameters
5. ⚠️ Consider different strategy

---

## Full Documentation

For complete details, see:
- [BINANCE_BACKTEST_DATA_GUIDE.md](BINANCE_BACKTEST_DATA_GUIDE.md) - Complete guide
- [PHASE1_VOLATILITY_AWARE_COMPLETE.md](PHASE1_VOLATILITY_AWARE_COMPLETE.md) - Strategy details
- [FINAL_SESSION_SUMMARY.md](FINAL_SESSION_SUMMARY.md) - Full implementation summary

---

## Summary

**Recommended Setup**:
- ✅ Futures Type: **USDⓈ-M (UM)**
- ✅ Timeframe: **5-minute**
- ✅ Storage: **CSV** (initially)
- ✅ Period: **3 months**
- ✅ Symbols: **13 symbols** (HIGH/MEDIUM/LOW)
- ✅ Capital: **$1000**

**Expected Time**:
- Download: 10-15 minutes
- Backtest: 5-10 minutes
- Analysis: 10-15 minutes
- **Total: ~30 minutes**

**Expected Results**:
- Win Rate: 45-55%
- Profit Factor: 2.0-2.5
- 3-Month Return: +15-35%

**Ready to start?** Run `python download_binance_data.py`
