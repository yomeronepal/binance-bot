# scripts/analyze_adx.py
import django
import os
import pandas as pd
import matplotlib.pyplot as plt

from backend.signals.models_backtest import BacktestRun

# --- Setup Django environment ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project.settings")
django.setup()


# --- Fetch ADX tuning backtests ---
def fetch_adx_backtests(symbol="DOGEUSDT", timeframe="4h"):
    # Filter backtests with ADXTune in name
    qs = BacktestRun.objects.filter(
        symbols__contains=[symbol],
        timeframe=timeframe,
        status="COMPLETED",
        name__icontains="ADXTune"
    )
    
    results = []
    for bt in qs:
        adx_long = bt.strategy_params.get("long_adx_min")
        adx_short = bt.strategy_params.get("short_adx_min")
        if adx_long is not None and adx_short is not None:
            results.append({
                "name": bt.name,
                "adx_value": adx_long,  # assume long_adx_min = short_adx_min
                "trades": bt.total_trades,
                "win_rate": float(bt.win_rate),
                "roi": float(bt.roi),
                "pnl": float(bt.total_profit_loss),
                "sharpe": float(bt.sharpe_ratio) if bt.sharpe_ratio else None,
                "profit_factor": float(bt.profit_factor) if bt.profit_factor else None
            })
    return results

# --- Analysis ---
def analyze(results):
    if not results:
        print("No ADXTune backtests found.")
        return

    df = pd.DataFrame(results)
    df = df.sort_values("adx_value")

    print("\n=== ADX Tuning Summary ===")
    print(df[["adx_value", "trades", "win_rate", "roi", "sharpe", "profit_factor"]])

    best_roi = df.loc[df["roi"].idxmax()]
    best_win = df.loc[df["win_rate"].idxmax()]
    best_sharpe = df.loc[df["sharpe"].idxmax()]

    print("\nBest ROI ADX:", best_roi["adx_value"])
    print("Best Win Rate ADX:", best_win["adx_value"])
    print("Best Sharpe ADX:", best_sharpe["adx_value"])

    # Plot
    plt.figure(figsize=(8, 4))
    plt.plot(df["adx_value"], df["roi"], marker="o", label="ROI (%)")
    plt.plot(df["adx_value"], df["win_rate"], marker="s", label="Win Rate (%)")
    plt.title(f"ADX Optimization - {symbol} {timeframe}")
    plt.xlabel("ADX Minimum Value")
    plt.ylabel("Performance")
    plt.legend()
    plt.grid(True)
    plt.show()


if __name__ == "__main__":
    symbol = "DOGEUSDT"
    timeframe = "4h"
    results = fetch_adx_backtests(symbol=symbol, timeframe=timeframe)
    analyze(results)
