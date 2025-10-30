#!/usr/bin/env python
"""
Clean all data from database - Fresh start for optimized configuration
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from signals.models import (
    Signal, PaperTrade, PaperAccount,
    BacktestJob, BacktestResult, BacktestTrade, BacktestMetrics,
    WalkForwardJob, WalkForwardWindow, WalkForwardSummary,
    MonteCarloSimulation, MonteCarloRun, MonteCarloDistribution,
    MLTuningJob, MLTuningSample, MLPrediction, MLModel
)
from django.db import transaction

def confirm_deletion():
    """Ask for confirmation before deleting all data"""
    print("=" * 80)
    print("DATABASE CLEANUP - WARNING")
    print("=" * 80)
    print()
    print("This will DELETE ALL data from the following tables:")
    print()
    print("  1. Paper Trading:")
    print("     - PaperTrade (trades)")
    print("     - PaperAccount (accounts) - OPTIONAL")
    print()
    print("  2. Signals:")
    print("     - Signal (all generated signals)")
    print()
    print("  3. Backtesting:")
    print("     - BacktestJob, BacktestResult, BacktestTrade, BacktestMetrics")
    print()
    print("  4. Walk-Forward Analysis:")
    print("     - WalkForwardJob, WalkForwardWindow, WalkForwardSummary")
    print()
    print("  5. Monte Carlo Simulations:")
    print("     - MonteCarloSimulation, MonteCarloRun, MonteCarloDistribution")
    print()
    print("  6. ML Tuning:")
    print("     - MLTuningJob, MLTuningSample, MLPrediction, MLModel")
    print()
    print("=" * 80)
    print()

    # Get counts before deletion
    counts = {
        'PaperTrade': PaperTrade.objects.count(),
        'PaperAccount': PaperAccount.objects.count(),
        'Signal': Signal.objects.count(),
        'BacktestJob': BacktestJob.objects.count(),
        'WalkForwardJob': WalkForwardJob.objects.count(),
        'MonteCarloSimulation': MonteCarloSimulation.objects.count(),
        'MLTuningJob': MLTuningJob.objects.count(),
    }

    print("Current record counts:")
    for model, count in counts.items():
        print(f"  {model:25s}: {count:6d} records")
    print()

    response = input("Are you sure you want to DELETE ALL this data? (type 'YES' to confirm): ")
    return response == 'YES'

def clean_paper_trading():
    """Clean paper trading data"""
    print("\n[1/6] Cleaning Paper Trading data...")

    # Ask about PaperAccount
    keep_accounts = input("  Keep PaperAccount records? (Y/n): ").lower() != 'n'

    with transaction.atomic():
        # Delete paper trades
        trades_deleted = PaperTrade.objects.all().delete()[0]
        print(f"  ✓ Deleted {trades_deleted} PaperTrade records")

        if not keep_accounts:
            accounts_deleted = PaperAccount.objects.all().delete()[0]
            print(f"  ✓ Deleted {accounts_deleted} PaperAccount records")
        else:
            print(f"  ✓ Kept PaperAccount records")

def clean_signals():
    """Clean signal data"""
    print("\n[2/6] Cleaning Signals...")

    with transaction.atomic():
        signals_deleted = Signal.objects.all().delete()[0]
        print(f"  ✓ Deleted {signals_deleted} Signal records")

def clean_backtests():
    """Clean backtest data"""
    print("\n[3/6] Cleaning Backtest data...")

    with transaction.atomic():
        # Delete in correct order (child tables first)
        metrics_deleted = BacktestMetrics.objects.all().delete()[0]
        trades_deleted = BacktestTrade.objects.all().delete()[0]
        results_deleted = BacktestResult.objects.all().delete()[0]
        jobs_deleted = BacktestJob.objects.all().delete()[0]

        print(f"  ✓ Deleted {jobs_deleted} BacktestJob records")
        print(f"  ✓ Deleted {results_deleted} BacktestResult records")
        print(f"  ✓ Deleted {trades_deleted} BacktestTrade records")
        print(f"  ✓ Deleted {metrics_deleted} BacktestMetrics records")

def clean_walkforward():
    """Clean walk-forward data"""
    print("\n[4/6] Cleaning Walk-Forward data...")

    with transaction.atomic():
        # Delete in correct order
        summary_deleted = WalkForwardSummary.objects.all().delete()[0]
        windows_deleted = WalkForwardWindow.objects.all().delete()[0]
        jobs_deleted = WalkForwardJob.objects.all().delete()[0]

        print(f"  ✓ Deleted {jobs_deleted} WalkForwardJob records")
        print(f"  ✓ Deleted {windows_deleted} WalkForwardWindow records")
        print(f"  ✓ Deleted {summary_deleted} WalkForwardSummary records")

def clean_montecarlo():
    """Clean Monte Carlo simulation data"""
    print("\n[5/6] Cleaning Monte Carlo data...")

    with transaction.atomic():
        # Delete in correct order
        dist_deleted = MonteCarloDistribution.objects.all().delete()[0]
        runs_deleted = MonteCarloRun.objects.all().delete()[0]
        sims_deleted = MonteCarloSimulation.objects.all().delete()[0]

        print(f"  ✓ Deleted {sims_deleted} MonteCarloSimulation records")
        print(f"  ✓ Deleted {runs_deleted} MonteCarloRun records")
        print(f"  ✓ Deleted {dist_deleted} MonteCarloDistribution records")

def clean_mltuning():
    """Clean ML tuning data"""
    print("\n[6/6] Cleaning ML Tuning data...")

    with transaction.atomic():
        # Delete in correct order
        predictions_deleted = MLPrediction.objects.all().delete()[0]
        samples_deleted = MLTuningSample.objects.all().delete()[0]
        models_deleted = MLModel.objects.all().delete()[0]
        jobs_deleted = MLTuningJob.objects.all().delete()[0]

        print(f"  ✓ Deleted {jobs_deleted} MLTuningJob records")
        print(f"  ✓ Deleted {samples_deleted} MLTuningSample records")
        print(f"  ✓ Deleted {predictions_deleted} MLPrediction records")
        print(f"  ✓ Deleted {models_deleted} MLModel records")

def verify_clean():
    """Verify database is clean"""
    print("\n" + "=" * 80)
    print("VERIFICATION - Current record counts:")
    print("=" * 80)

    counts = {
        'PaperTrade': PaperTrade.objects.count(),
        'PaperAccount': PaperAccount.objects.count(),
        'Signal': Signal.objects.count(),
        'BacktestJob': BacktestJob.objects.count(),
        'BacktestResult': BacktestResult.objects.count(),
        'BacktestTrade': BacktestTrade.objects.count(),
        'BacktestMetrics': BacktestMetrics.objects.count(),
        'WalkForwardJob': WalkForwardJob.objects.count(),
        'WalkForwardWindow': WalkForwardWindow.objects.count(),
        'WalkForwardSummary': WalkForwardSummary.objects.count(),
        'MonteCarloSimulation': MonteCarloSimulation.objects.count(),
        'MonteCarloRun': MonteCarloRun.objects.count(),
        'MonteCarloDistribution': MonteCarloDistribution.objects.count(),
        'MLTuningJob': MLTuningJob.objects.count(),
        'MLTuningSample': MLTuningSample.objects.count(),
        'MLPrediction': MLPrediction.objects.count(),
        'MLModel': MLModel.objects.count(),
    }

    all_clean = True
    for model, count in counts.items():
        status = "✓" if count == 0 else "⚠️"
        if count > 0 and model != 'PaperAccount':  # PaperAccount might be kept
            all_clean = False
        print(f"  {status} {model:25s}: {count:6d} records")

    print()
    if all_clean or (counts['PaperAccount'] > 0 and sum(counts.values()) == counts['PaperAccount']):
        print("✅ Database is clean! Ready for fresh start with optimized configuration.")
    else:
        print("⚠️  Some records remain. This might be intentional (e.g., PaperAccount).")
    print("=" * 80)

def main():
    """Main cleanup function"""
    if not confirm_deletion():
        print("\nCleanup cancelled. No data was deleted.")
        return

    print("\n" + "=" * 80)
    print("STARTING DATABASE CLEANUP")
    print("=" * 80)

    try:
        clean_paper_trading()
        clean_signals()
        clean_backtests()
        clean_walkforward()
        clean_montecarlo()
        clean_mltuning()

        verify_clean()

        print("\n✅ Database cleanup completed successfully!")
        print()
        print("Next steps:")
        print("  1. Restart services: docker-compose restart backend celery-worker")
        print("  2. New signals will be generated with corrected RSI configuration")
        print("  3. Wait for 50-100 trades to close")
        print("  4. Run ML tuning: ./test_mltuning.sh")
        print()

    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        print("Some data may have been partially deleted.")
        raise

if __name__ == '__main__':
    main()
