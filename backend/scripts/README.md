# Trading Bot Scripts

This directory contains all optimization and testing scripts for the trading bot.

## Directory Structure

```
scripts/
├── data/
│   ├── download_data_fast.py       # Fast parallel downloader (3 months)
│   └── download_long_period.py     # Extended period downloader (11 months)
├── optimization/
│   ├── optimize_parameters_final.py # Parameter optimization (8 configs)
│   ├── test_volume_filter.py       # Volume filter testing
│   └── test_timeframes_balanced.py # Timeframe comparison
├── testing/
│   └── test_extended_period.py     # Extended period backtesting
└── README.md                        # This file
```

## Quick Start

### Using Makefile (Recommended)

```bash
# Download 11-month data
make download-long

# Run parameter optimization
make optimize-params

# Test on extended period
make test-long

# See all commands
make help
```

### Manual Execution

```bash
# Inside Docker container
docker exec binance-bot-backend python scripts/data/download_long_period.py
docker exec binance-bot-backend python scripts/optimization/optimize_parameters_final.py
docker exec binance-bot-backend python scripts/testing/test_extended_period.py
```

## Script Descriptions

### Data Download

**download_data_fast.py**
- Downloads 3-month historical data (Aug-Nov 2024)
- Parallel async downloads (very fast)
- Timeframes: 15m, 1h, 4h
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, ADAUSDT, DOGEUSDT

**download_long_period.py**
- Downloads 11-month historical data (Jan-Nov 2024)
- All timeframes: 5m, 15m, 1h, 4h, 1d
- All symbols with volatility classification
- ~1.1M candles total

### Optimization

**optimize_parameters_final.py**
- Tests 8 different parameter configurations
- Compares: RSI ranges, confidence, ADX, R/R ratios
- Identifies best configuration (OPT6)
- Shows detailed comparison with baseline

**test_volume_filter.py**
- Tests volume filtering (1.5x threshold)
- Compares baseline vs filtered signals
- Result: Volume filter not effective (removed winners)

**test_timeframes_balanced.py**
- Tests strategy across 15m, 1h, 4h timeframes
- Moderate parameters to avoid 0-trade scenarios
- Identified 4h as optimal timeframe

### Testing

**test_extended_period.py**
- Main testing script for extended period
- Compares 3-month vs 11-month performance
- Tests all symbols: BTC, ETH, SOL, DOGE
- Shows detailed analysis and profitability verdict

## Key Findings

### Best Configuration (OPT6)
```python
{
    "min_confidence": 0.73,      # Higher threshold
    "long_adx_min": 22.0,        # Stronger trends
    "long_rsi_min": 23.0,        # Tighter range (23-33)
    "long_rsi_max": 33.0,
    "short_rsi_min": 67.0,       # Tighter range (67-77)
    "short_rsi_max": 77.0,
    "sl_atr_multiplier": 1.5,
    "tp_atr_multiplier": 5.25    # 1:3.5 R/R
}
```

### Performance
- **Timeframe**: 4h (best performer)
- **3-month**: -0.03% ROI, 16.7% win rate, 6 trades
- **11-month**: Pending test (run `make test-long`)

## Obsolete Scripts (Removed)

The following scripts were removed during cleanup:
- `analyze_performance.py` - Replaced by test_extended_period.py
- `backtest_*.py` - Old manual backtest scripts
- `create_paper_account.py` - Moved to Django management command
- `download_binance_data*.py` - Replaced by optimized downloaders
- `run_*.py` - Replaced by Makefile commands
- `test_*.sh/bat` - Replaced by Makefile

## Development

### Adding New Scripts

1. Place in appropriate subdirectory (data/optimization/testing)
2. Add docstring explaining purpose
3. Update this README
4. Add Makefile target if frequently used

### Script Conventions

- Use `#!/usr/bin/env python3` shebang
- Add descriptive docstring at top
- Include expected runtime in docstring
- Print progress and results clearly
- Handle errors gracefully

## Troubleshooting

### "No data found"
```bash
make download-long  # Re-download data
```

### "Container not running"
```bash
docker-compose up -d
make setup
```

### "Parameters not changing"
Make sure volatility-aware mode is disabled in backtest_tasks.py:
```python
engine = SignalDetectionEngine(signal_config, use_volatility_aware=False)
```

## Next Steps

1. **Test on 11-month period**: `make test-long`
2. **If not profitable**: Implement multi-timeframe confirmation (Phase 2)
3. **If profitable**: Deploy to paper trading
4. **Paper trading successful**: Deploy to live with small capital

See [OPTIMIZATION_COMPLETE_SUMMARY.md](../OPTIMIZATION_COMPLETE_SUMMARY.md) for detailed optimization journey.
