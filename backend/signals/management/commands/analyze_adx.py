from django.core.management.base import BaseCommand
import pandas as pd
import matplotlib.pyplot as plt

from signals.models_backtest import BacktestRun


class Command(BaseCommand):
    help = "Analyze backtest tuning results (ADX, RSI, ATR, Confidence, etc.)"

    def add_arguments(self, parser):
        parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol")
        parser.add_argument("--timeframe", type=str, default="4h", help="Candle timeframe")
        parser.add_argument("--filter", type=str, default="", help="Keyword filter like ADXTune, RSITune, etc.")
        parser.add_argument("--show", action="store_true", help="Show performance chart")
        parser.add_argument("--csv", action="store_true", help="Export results to CSV")

    def handle(self, *args, **options):
        symbol = options["symbol"]
        timeframe = options["timeframe"]
        keyword = options["filter"]
        show_plot = options["show"]
        export_csv = options["csv"]

        if not keyword:
            self.stdout.write(self.style.WARNING("⚠️ Please provide a filter keyword, e.g. --filter ADXTune or RSITune"))
            return

        self.stdout.write(f"🔍 Fetching {keyword} backtests for {symbol} ({timeframe})...")

        qs = BacktestRun.objects.filter(
            symbols__contains=[symbol],
            timeframe=timeframe,
            status="COMPLETED",
            name__icontains=keyword
        )

        results = []
        for bt in qs:
            params = bt.strategy_params or {}

            # Auto-detect which parameter was tuned
            if "ADX" in keyword.upper():
                adx_long = params.get("long_adx_min")
                adx_short = params.get("short_adx_min")
                param_value = adx_long if adx_long == adx_short else (adx_long, adx_short)
            elif "RSI" in keyword.upper():
                param_value = params.get("long_rsi_min")
            elif "ATR" in keyword.upper():
                param_value = params.get("sl_atr_multiplier")
            elif "CONF" in keyword.upper() or "CONFIDENCE" in keyword.upper():
                param_value = params.get("min_confidence")
            else:
                param_value = None

            if param_value is None:
                continue

            results.append({
                "name": bt.name,
                "long_adx_min": params.get("long_adx_min"),
                "short_adx_min": params.get("short_adx_min"),
                "param_value": param_value if not isinstance(param_value, tuple) else (param_value[0] + param_value[1]) / 2,
                "trades": bt.total_trades,
                "win_rate": float(bt.win_rate),
                "roi": float(bt.roi),
                "pnl": float(bt.total_profit_loss),
                "sharpe": float(bt.sharpe_ratio or 0),
                "profit_factor": float(bt.profit_factor or 0),
            })

        if not results:
            self.stdout.write(self.style.WARNING(f"⚠️ No {keyword} backtests found."))
            return

        df = pd.DataFrame(results).sort_values("param_value")
        self.stdout.write(self.style.SUCCESS(f"\n=== {keyword} Summary ({symbol} {timeframe}) ==="))
        self.stdout.write(str(df[["long_adx_min", "short_adx_min", "trades", "win_rate", "roi", "sharpe", "profit_factor"]]))

        best_roi = df.loc[df["roi"].idxmax()]
        best_win = df.loc[df["win_rate"].idxmax()]
        best_sharpe = df.loc[df["sharpe"].idxmax()]

        self.stdout.write("\n🏆 Best Results:")
        self.stdout.write(f"• Best ROI ADX: L={best_roi['long_adx_min']} S={best_roi['short_adx_min']}  → ROI: {best_roi['roi']:.2f}")
        self.stdout.write(f"• Best Win Rate ADX: L={best_win['long_adx_min']} S={best_win['short_adx_min']}  → Win Rate: {best_win['win_rate']:.2f}%")
        self.stdout.write(f"• Best Sharpe ADX: L={best_sharpe['long_adx_min']} S={best_sharpe['short_adx_min']}  → Sharpe: {best_sharpe['sharpe']:.3f}")

        if export_csv:
            filename = f"{keyword}_{symbol}_{timeframe}.csv"
            df.to_csv(filename, index=False)
            self.stdout.write(self.style.SUCCESS(f"📁 Exported results to {filename}"))

        if show_plot:
            plt.figure(figsize=(8, 4))
            plt.plot(df["long_adx_min"], df["roi"], marker="o", label="ROI (%)")
            plt.plot(df["long_adx_min"], df["win_rate"], marker="s", label="Win Rate (%)")
            plt.title(f"{keyword} Optimization - {symbol} {timeframe}")
            plt.xlabel("ADX (long/short min value)")
            plt.ylabel("Performance")
            plt.legend()
            plt.grid(True)
            plt.show()
