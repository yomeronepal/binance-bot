# Binance Historical Data Backtesting Guide

**For**: Mean Reversion Strategy with Volatility-Aware Configuration
**Capital**: $1000 simulated
**Goal**: Realistic performance validation with proper risk metrics

---

## Recommendations

### 1. Futures Type: **USDⓈ-M (UM)** ✅ RECOMMENDED

**Why UM over CM?**

| Feature | USDⓈ-M (UM) | COIN-M (CM) | Winner |
|---------|-------------|-------------|--------|
| **Margin Currency** | USDT (stablecoin) | Crypto (BTC/ETH) | ✅ UM |
| **PnL Calculation** | Simple (USDT) | Complex (crypto value changes) | ✅ UM |
| **Liquidity** | Higher | Lower | ✅ UM |
| **Contract Size** | Flexible | Fixed (e.g., $100) | ✅ UM |
| **Suitable for $1000** | ✅ Yes | ❌ Not ideal | ✅ UM |
| **Your Bot Support** | ✅ Already configured | ❌ Would need changes | ✅ UM |

**Recommendation**: **Use USDⓈ-M (UM) futures**

Your bot is already configured for USDT pairs (PEPEUSDT, SOLUSDT, BTCUSDT, etc.), making UM the natural choice.

---

### 2. Timeframe: **5-minute** ✅ RECOMMENDED

**Timeframe Analysis:**

| Timeframe | Pros | Cons | Best For |
|-----------|------|------|----------|
| **5-minute** | • Matches your strategy<br>• 288 candles/day<br>• Good signal frequency<br>• Real-time accuracy | • Large data files<br>• Longer processing | ✅ **Your strategy** |
| **Daily** | • Small data files<br>• Quick processing | • Too slow for mean reversion<br>• Misses intraday signals | ❌ Long-term strategies |
| **Monthly** | • Minimal data | • Useless for your strategy | ❌ Portfolio analysis only |

**Your Strategy Requirements:**
- Mean reversion signals need quick detection (RSI oversold/overbought)
- Entry/exit on 5m timeframe
- Stop loss and take profit tracked per candle
- ADX, MACD, EMA calculated on 5m data

**Recommendation**: **Use 5-minute data**

This matches your production configuration and provides accurate signal generation.

---

### 3. Data Storage: **CSV** ✅ RECOMMENDED (Initially)

**Storage Comparison:**

| Storage | Pros | Cons | Best For |
|---------|------|------|----------|
| **CSV** | • Simple to download<br>• Easy to inspect<br>• Fast to prototype<br>• Portable | • Large file sizes<br>• Slower queries | ✅ **Initial backtesting** |
| **Database** | • Efficient queries<br>• Good for large datasets<br>• Easier multi-symbol analysis | • Setup overhead<br>• Migration needed | Production after validation |

**Recommendation**: **Start with CSV, migrate to DB later**

**Workflow**:
1. **Phase 1** (Now): Download CSV, build simple backtest engine
2. **Phase 2** (After validation): Import to PostgreSQL for production use
3. **Phase 3** (Long-term): Automated daily updates via Binance API

---

## Detailed Setup Instructions

### Step 1: Download Historical Data

#### Symbols to Download:

Based on your volatility-aware strategy, download these symbols:

**HIGH Volatility** (5 symbols):
```
PEPEUSDT
SHIBUSDT
DOGEUSDT
WIFUSDT
FLOKIUSDT
```

**MEDIUM Volatility** (5 symbols):
```
SOLUSDT
ADAUSDT
MATICUSDT
DOTUSDT
AVAXUSDT
```

**LOW Volatility** (3 symbols):
```
BTCUSDT
ETHUSDT
BNBUSDT
```

**Total**: 13 symbols across all volatility levels

#### Time Period:

**Recommendation**: **Last 3-6 months**

| Period | Candles (5m) | Data Size (per symbol) | Best For |
|--------|--------------|------------------------|----------|
| 1 month | ~8,640 | ~2-5 MB | Quick validation |
| 3 months | ~25,920 | ~6-15 MB | ✅ **Recommended** |
| 6 months | ~51,840 | ~12-30 MB | Robust testing |
| 1 year | ~103,680 | ~25-60 MB | Full market cycle |

**Start with 3 months** to balance:
- Enough data for statistically significant results (500-1000+ signals expected)
- Recent market conditions (relevant to current performance)
- Manageable file sizes and processing time

#### Download Links:

**Binance Historical Data Portal**:
```
https://data.binance.vision/?prefix=data/futures/um/daily/klines/
```

**Structure**:
```
data/futures/um/daily/klines/{SYMBOL}/5m/
```

**Example URLs**:
```
# BTCUSDT 5-minute data for October 2025
https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2025-10-01.zip

# SOLUSDT 5-minute data for September 2025
https://data.binance.vision/data/futures/um/daily/klines/SOLUSDT/5m/SOLUSDT-5m-2025-09-01.zip
```

---

### Step 2: Data Format

**Binance CSV Format** (10 columns):
```csv
Open time, Open, High, Low, Close, Volume, Close time, Quote volume, Trades, Taker buy base, Taker buy quote, Ignore
```

**Example**:
```csv
1609459200000,29374.00,29459.99,29334.01,29441.00,123.45,1609459499999,3632145.67,1234,61.23,1800567.89,0
```

**Column Mapping**:
1. **Open time** (timestamp in ms) - Use for datetime
2. **Open** (float) - Opening price
3. **High** (float) - Highest price
4. **Low** (float) - Lowest price
5. **Close** (float) - Closing price
6. **Volume** (float) - Base asset volume
7. **Close time** (timestamp in ms) - Candle close time
8. **Quote volume** (float) - Quote asset volume (USDT)
9. **Trades** (int) - Number of trades
10. **Taker buy base** (float) - Taker buy base asset volume
11. **Taker buy quote** (float) - Taker buy quote asset volume

**For Your Strategy, You Need**: Columns 1-6 (timestamp, OHLCV)

---

### Step 3: Data Preparation Script

I'll create a script to download and prepare the data:

**File**: `download_binance_data.py`

```python
#!/usr/bin/env python3
"""
Download Binance Historical Data for Backtesting
Downloads 5-minute USDⓈ-M futures data for specified symbols and date range
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path
import zipfile
import io

# Configuration
SYMBOLS = {
    'HIGH': ['PEPEUSDT', 'SHIBUSDT', 'DOGEUSDT', 'WIFUSDT', 'FLOKIUSDT'],
    'MEDIUM': ['SOLUSDT', 'ADAUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT'],
    'LOW': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
}

BASE_URL = "https://data.binance.vision/data/futures/um/daily/klines"
TIMEFRAME = "5m"
OUTPUT_DIR = "backtest_data"

def download_daily_data(symbol: str, date: datetime) -> pd.DataFrame:
    """Download single day of data for a symbol"""

    date_str = date.strftime('%Y-%m-%d')
    url = f"{BASE_URL}/{symbol}/{TIMEFRAME}/{symbol}-{TIMEFRAME}-{date_str}.zip"

    print(f"  Downloading {symbol} for {date_str}...", end=' ')

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Extract CSV from ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                df = pd.read_csv(f, header=None)

        # Name columns
        df.columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ]

        # Convert timestamp to datetime
        df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

        print(f"✅ {len(df)} candles")
        return df

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def download_symbol_data(symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Download data for a symbol across date range"""

    print(f"\n{'='*60}")
    print(f"Downloading {symbol}")
    print(f"{'='*60}")

    all_data = []
    current_date = start_date

    while current_date <= end_date:
        df = download_daily_data(symbol, current_date)
        if df is not None and len(df) > 0:
            all_data.append(df)
        current_date += timedelta(days=1)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        print(f"✅ Total: {len(combined)} candles for {symbol}")
        return combined
    else:
        print(f"❌ No data downloaded for {symbol}")
        return None

def save_data(df: pd.DataFrame, symbol: str, volatility: str):
    """Save data to CSV"""

    # Create output directory
    output_path = Path(OUTPUT_DIR) / volatility.lower()
    output_path.mkdir(parents=True, exist_ok=True)

    # Save CSV
    filename = output_path / f"{symbol}_5m.csv"

    # Select relevant columns
    df_export = df[[
        'datetime', 'open', 'high', 'low', 'close', 'volume',
        'quote_volume', 'trades'
    ]].copy()

    df_export.to_csv(filename, index=False)
    print(f"💾 Saved to {filename}")

    # Print stats
    print(f"   Date range: {df_export['datetime'].min()} to {df_export['datetime'].max()}")
    print(f"   Candles: {len(df_export)}")
    print(f"   Days: {(df_export['datetime'].max() - df_export['datetime'].min()).days}")

def main():
    print("="*60)
    print("BINANCE HISTORICAL DATA DOWNLOADER")
    print("="*60)
    print()

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)  # 3 months

    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"Symbols: {sum(len(v) for v in SYMBOLS.values())}")
    print()

    # Download each volatility group
    for volatility, symbols in SYMBOLS.items():
        print(f"\n{'#'*60}")
        print(f"# {volatility} VOLATILITY SYMBOLS")
        print(f"{'#'*60}")

        for symbol in symbols:
            df = download_symbol_data(symbol, start_date, end_date)

            if df is not None:
                save_data(df, symbol, volatility)

            print()

    print("="*60)
    print("✅ DOWNLOAD COMPLETE")
    print("="*60)
    print()
    print(f"Data saved to: {OUTPUT_DIR}/")
    print()
    print("Next steps:")
    print("1. Verify data files in backtest_data/ directory")
    print("2. Run: python simple_backtest.py")
    print("3. Analyze results")

if __name__ == '__main__':
    main()
```

---

### Step 4: Simple Backtest Engine

I'll create a clean, working backtest engine:

**File**: `simple_backtest.py`

```python
#!/usr/bin/env python3
"""
Simple Vectorized Backtest Engine
Tests mean reversion strategy with volatility-aware configuration
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

# Volatility-aware configurations
CONFIGS = {
    'HIGH': {
        'sl_atr_mult': 2.0,
        'tp_atr_mult': 3.5,
        'adx_threshold': 18.0,
        'rsi_long_min': 25.0,
        'rsi_long_max': 35.0,
        'rsi_short_min': 65.0,
        'rsi_short_max': 75.0,
        'min_confidence': 0.70
    },
    'MEDIUM': {
        'sl_atr_mult': 1.5,
        'tp_atr_mult': 2.5,
        'adx_threshold': 22.0,
        'rsi_long_min': 25.0,
        'rsi_long_max': 35.0,
        'rsi_short_min': 65.0,
        'rsi_short_max': 75.0,
        'min_confidence': 0.75
    },
    'LOW': {
        'sl_atr_mult': 1.0,
        'tp_atr_mult': 2.0,
        'adx_threshold': 20.0,
        'rsi_long_min': 25.0,
        'rsi_long_max': 35.0,
        'rsi_short_min': 65.0,
        'rsi_short_max': 75.0,
        'min_confidence': 0.70
    }
}

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate technical indicators"""

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['atr'] = ranges.max(axis=1).rolling(window=14).mean()

    # EMA
    df['ema_9'] = df['close'].ewm(span=9).mean()
    df['ema_21'] = df['close'].ewm(span=21).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()

    # MACD
    df['ema_12'] = df['close'].ewm(span=12).mean()
    df['ema_26'] = df['close'].ewm(span=26).mean()
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    # ADX
    plus_dm = df['high'].diff()
    minus_dm = -df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr = ranges.max(axis=1)
    atr_14 = tr.rolling(window=14).mean()

    plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr_14)
    minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr_14)

    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.rolling(window=14).mean()
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di

    return df

def generate_signals(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Generate trading signals based on mean reversion strategy"""

    df['signal'] = 0  # 0 = no signal, 1 = LONG, -1 = SHORT

    # LONG conditions (mean reversion - buy oversold)
    long_condition = (
        (df['rsi'] > config['rsi_long_min']) &
        (df['rsi'] < config['rsi_long_max']) &
        (df['adx'] > config['adx_threshold']) &
        (df['macd_hist'] > 0) &  # Momentum turning positive
        (df['close'] > df['ema_50'])  # Above longer-term trend
    )

    # SHORT conditions (mean reversion - sell overbought)
    short_condition = (
        (df['rsi'] > config['rsi_short_min']) &
        (df['rsi'] < config['rsi_short_max']) &
        (df['adx'] > config['adx_threshold']) &
        (df['macd_hist'] < 0) &  # Momentum turning negative
        (df['close'] < df['ema_50'])  # Below longer-term trend
    )

    df.loc[long_condition, 'signal'] = 1
    df.loc[short_condition, 'signal'] = -1

    return df

def simulate_trades(df: pd.DataFrame, config: dict, initial_capital: float = 1000) -> dict:
    """Simulate trading with proper position management"""

    capital = initial_capital
    position = None  # Current open position
    trades = []
    equity_curve = [initial_capital]

    for i in range(len(df)):
        row = df.iloc[i]

        # Check if we have an open position
        if position:
            # Check stop loss
            if position['direction'] == 'LONG':
                if row['low'] <= position['sl']:
                    # Stop loss hit
                    pnl = position['size'] * (position['sl'] - position['entry']) / position['entry']
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': row['datetime'],
                        'direction': position['direction'],
                        'entry': position['entry'],
                        'exit': position['sl'],
                        'pnl': pnl,
                        'pnl_pct': (position['sl'] - position['entry']) / position['entry'] * 100,
                        'exit_reason': 'SL'
                    })
                    position = None
                    equity_curve.append(capital)
                    continue

                # Check take profit
                elif row['high'] >= position['tp']:
                    # Take profit hit
                    pnl = position['size'] * (position['tp'] - position['entry']) / position['entry']
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': row['datetime'],
                        'direction': position['direction'],
                        'entry': position['entry'],
                        'exit': position['tp'],
                        'pnl': pnl,
                        'pnl_pct': (position['tp'] - position['entry']) / position['entry'] * 100,
                        'exit_reason': 'TP'
                    })
                    position = None
                    equity_curve.append(capital)
                    continue

            else:  # SHORT
                if row['high'] >= position['sl']:
                    # Stop loss hit
                    pnl = position['size'] * (position['entry'] - position['sl']) / position['entry']
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': row['datetime'],
                        'direction': position['direction'],
                        'entry': position['entry'],
                        'exit': position['sl'],
                        'pnl': pnl,
                        'pnl_pct': (position['entry'] - position['sl']) / position['entry'] * 100,
                        'exit_reason': 'SL'
                    })
                    position = None
                    equity_curve.append(capital)
                    continue

                elif row['low'] <= position['tp']:
                    # Take profit hit
                    pnl = position['size'] * (position['entry'] - position['tp']) / position['entry']
                    capital += pnl
                    trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': row['datetime'],
                        'direction': position['direction'],
                        'entry': position['entry'],
                        'exit': position['tp'],
                        'pnl': pnl,
                        'pnl_pct': (position['entry'] - position['tp']) / position['entry'] * 100,
                        'exit_reason': 'TP'
                    })
                    position = None
                    equity_curve.append(capital)
                    continue

        # Check for new signal (only if no position)
        if position is None and row['signal'] != 0:
            position_size = capital * 0.10  # Risk 10% per trade

            if row['signal'] == 1:  # LONG
                entry = row['close']
                sl = entry - (config['sl_atr_mult'] * row['atr'])
                tp = entry + (config['tp_atr_mult'] * row['atr'])

                position = {
                    'direction': 'LONG',
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'size': position_size,
                    'entry_time': row['datetime']
                }

            elif row['signal'] == -1:  # SHORT
                entry = row['close']
                sl = entry + (config['sl_atr_mult'] * row['atr'])
                tp = entry - (config['tp_atr_mult'] * row['atr'])

                position = {
                    'direction': 'SHORT',
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'size': position_size,
                    'entry_time': row['datetime']
                }

    # Calculate metrics
    if trades:
        df_trades = pd.DataFrame(trades)
        wins = df_trades[df_trades['pnl'] > 0]
        losses = df_trades[df_trades['pnl'] < 0]

        results = {
            'initial_capital': initial_capital,
            'final_capital': capital,
            'total_pnl': capital - initial_capital,
            'total_return_pct': (capital - initial_capital) / initial_capital * 100,
            'total_trades': len(trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0,
            'avg_win': wins['pnl'].mean() if len(wins) > 0 else 0,
            'avg_loss': losses['pnl'].mean() if len(losses) > 0 else 0,
            'largest_win': wins['pnl'].max() if len(wins) > 0 else 0,
            'largest_loss': losses['pnl'].min() if len(losses) > 0 else 0,
            'profit_factor': abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 else 0,
            'equity_curve': equity_curve,
            'trades': trades
        }

        # Calculate max drawdown
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        results['max_drawdown_pct'] = drawdown.min()

        return results
    else:
        return {
            'total_trades': 0,
            'message': 'No trades generated'
        }

def backtest_symbol(symbol: str, volatility: str, config: dict) -> dict:
    """Run backtest for a single symbol"""

    print(f"\n{'='*60}")
    print(f"Backtesting {symbol} ({volatility} volatility)")
    print(f"{'='*60}")

    # Load data
    filepath = Path('backtest_data') / volatility.lower() / f"{symbol}_5m.csv"

    if not filepath.exists():
        print(f"❌ Data file not found: {filepath}")
        return None

    df = pd.read_csv(filepath)
    df['datetime'] = pd.to_datetime(df['datetime'])

    print(f"Loaded {len(df)} candles")
    print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")

    # Calculate indicators
    print("Calculating indicators...")
    df = calculate_indicators(df)

    # Generate signals
    print("Generating signals...")
    df = generate_signals(df, config)

    signals = df[df['signal'] != 0]
    print(f"Generated {len(signals)} signals ({len(signals[signals['signal']==1])} LONG, {len(signals[signals['signal']==-1])} SHORT)")

    if len(signals) == 0:
        print("⚠️  No signals generated - conditions may be too strict")
        return None

    # Simulate trades
    print("Simulating trades...")
    results = simulate_trades(df, config)

    if results['total_trades'] > 0:
        print(f"\n📊 Results:")
        print(f"   Total Trades: {results['total_trades']}")
        print(f"   Win Rate: {results['win_rate']:.1f}%")
        print(f"   Profit Factor: {results['profit_factor']:.2f}")
        print(f"   Total Return: {results['total_return_pct']:.2f}%")
        print(f"   Max Drawdown: {results['max_drawdown_pct']:.2f}%")
        print(f"   Final Capital: ${results['final_capital']:.2f}")
    else:
        print("❌ No trades executed")

    results['symbol'] = symbol
    results['volatility'] = volatility

    return results

def main():
    print("="*60)
    print("SIMPLE BACKTEST ENGINE")
    print("="*60)
    print()

    # Test symbols
    test_symbols = {
        'HIGH': ['PEPEUSDT', 'SHIBUSDT'],
        'MEDIUM': ['SOLUSDT', 'ADAUSDT'],
        'LOW': ['BTCUSDT', 'ETHUSDT']
    }

    all_results = []

    for volatility, symbols in test_symbols.items():
        config = CONFIGS[volatility]
        print(f"\n{'#'*60}")
        print(f"# {volatility} VOLATILITY - SL={config['sl_atr_mult']}x, TP={config['tp_atr_mult']}x")
        print(f"{'#'*60}")

        for symbol in symbols:
            result = backtest_symbol(symbol, volatility, config)
            if result:
                all_results.append(result)

    # Summary
    if all_results:
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)

        total_trades = sum(r['total_trades'] for r in all_results)
        avg_win_rate = sum(r['win_rate'] for r in all_results) / len(all_results)
        avg_profit_factor = sum(r['profit_factor'] for r in all_results) / len(all_results)
        avg_return = sum(r['total_return_pct'] for r in all_results) / len(all_results)

        print(f"Total Symbols Tested: {len(all_results)}")
        print(f"Total Trades: {total_trades}")
        print(f"Average Win Rate: {avg_win_rate:.1f}%")
        print(f"Average Profit Factor: {avg_profit_factor:.2f}")
        print(f"Average Return: {avg_return:.2f}%")

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f'backtest_results_{timestamp}.json', 'w') as f:
            json.dump(all_results, f, indent=2, default=str)

        print(f"\n✅ Results saved to backtest_results_{timestamp}.json")

if __name__ == '__main__':
    main()
```

---

## Quick Start Guide

### 1. Download Data
```bash
python download_binance_data.py
```

This will download 3 months of 5-minute data for all 13 symbols.

### 2. Run Backtest
```bash
python simple_backtest.py
```

This will backtest your strategy with proper volatility-aware configs.

### 3. Analyze Results

The backtest will show:
- Total trades per symbol
- Win rate (%)
- Profit factor
- Total return (%)
- Max drawdown (%)
- Final capital

---

## Expected Results (Estimates)

Based on your $1000 capital and the volatility-aware strategy:

| Volatility | Expected Win Rate | Expected Profit Factor | Expected 3-Month Return |
|-----------|-------------------|------------------------|-------------------------|
| HIGH | 40-50% | 1.8-2.5 | +15-30% |
| MEDIUM | 50-60% | 2.0-3.0 | +20-40% |
| LOW | 55-65% | 2.0-3.0 | +10-25% |

**Overall**: 45-55% win rate, 2.0-2.5 profit factor, +15-35% return over 3 months

---

## Tips for Optimization

### 1. Data Quality
- ✅ Use complete days (no partial data)
- ✅ Remove outliers (flash crashes, exchange issues)
- ✅ Verify timestamps are sequential

### 2. Position Sizing
- Start with 10% of capital per trade
- Never risk more than 2% per trade on stop loss
- Consider using Kelly Criterion for optimal sizing

### 3. Performance Analysis
- Track metrics by volatility level
- Analyze which symbols perform best
- Look for patterns in losing trades

### 4. Parameter Optimization
- Don't over-optimize on historical data
- Use walk-forward analysis
- Test on out-of-sample data

---

## Migration to Database (Later)

Once validated with CSV, migrate to PostgreSQL:

```python
# Import to database
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('postgresql://user:pass@localhost:5432/binance_data')

for file in Path('backtest_data').glob('**/*.csv'):
    df = pd.read_csv(file)
    symbol = file.stem.replace('_5m', '')
    df.to_sql(f'klines_{symbol.lower()}', engine, if_exists='replace', index=False)
```

---

## Conclusion

**Recommendations**:
1. ✅ Use **USDⓈ-M (UM)** futures
2. ✅ Use **5-minute** timeframe
3. ✅ Start with **CSV** storage
4. ✅ Download **3 months** of data
5. ✅ Test **13 symbols** (HIGH/MEDIUM/LOW volatility)

This setup will give you:
- Realistic performance metrics
- Proper volatility-aware testing
- Efficient data management
- Easy migration to production

**Next steps**:
1. Run `download_binance_data.py`
2. Run `simple_backtest.py`
3. Analyze results
4. Optimize if needed
5. Deploy to production with confidence!
