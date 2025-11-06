# Quick Reference Card

**Trading Bot - Most Common Commands**

---

## 🚀 Quick Start (First Time)

```bash
# 1. Start Docker
docker-compose up -d

# 2. Download data
make download-long      # Linux/Mac
run.bat download-long   # Windows

# 3. Run test
make test-long
run.bat test-long
```

---

## 📊 Main Commands

### Linux/Mac
```bash
make help           # Show all commands
make download-long  # Get 11-month data
make test-long      # Run extended backtest
make optimize-params # Optimize parameters
make docker-restart # Restart containers
```

### Windows
```bash
run.bat help           # Show all commands
run.bat download-long  # Get 11-month data
run.bat test-long      # Run extended backtest
run.bat optimize       # Optimize parameters
run.bat docker-restart # Restart containers
```

---

## 🎯 Current Best Configuration (OPT6)

```python
{
    "min_confidence": 0.73,
    "long_adx_min": 22.0,
    "long_rsi_min": 23.0,
    "long_rsi_max": 33.0,
    "short_rsi_min": 67.0,
    "short_rsi_max": 77.0,
    "sl_atr_multiplier": 1.5,
    "tp_atr_multiplier": 5.25
}
```

**Performance**:
- ROI: -0.03% (only $3.12 loss on $10K)
- Win Rate: 16.7%
- Timeframe: 4h
- Status: 🔥 Very close to profitability!

---

## 📁 File Locations

**Scripts**:
- Data: `scripts/data/`
- Optimization: `scripts/optimization/`
- Testing: `scripts/testing/`

**Documentation**:
- Overview: `README.md`
- Complete Report: `FINAL_REPORT.md`
- Strategy Details: `STRATEFY_ANALYSIS_DETAILED.md`
- Technical Summary: `OPTIMIZATION_COMPLETE_SUMMARY.md`

**Core Code**:
- Strategy: `backend/scanner/strategies/signal_engine.py`
- Backtest: `backend/scanner/services/backtest_engine.py`
- Tasks: `backend/scanner/tasks/backtest_tasks.py`

---

## 🐛 Troubleshooting

**Containers not running?**
```bash
docker-compose up -d
```

**No data found?**
```bash
make download-long
```

**Parameters not working?**
Check: `backtest_tasks.py:72` has `use_volatility_aware=False`

**Need to restart?**
```bash
make docker-restart
```

---

## 📈 What's Next?

1. **Phase 2**: Implement multi-timeframe confirmation
   - Expected: +10-15% win rate
   - Should push into profitability

2. **Paper Trading**: Test in real-time (if profitable)

3. **Live Trading**: Deploy with small capital ($100-500)

---

## 📞 Quick Help

- **All commands**: `make help` or `run.bat help`
- **Documentation**: See `README.md`
- **Scripts**: See `scripts/README.md`
- **Full report**: See `FINAL_REPORT.md`

---

**Status**: ✅ Optimized & Ready
**Version**: 1.0.0
**Last Updated**: Nov 2, 2025
