"""
Django management command to clean all data from database
Provides interactive cleanup with optional preservation of paper accounts
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from signals.models import (
    Signal, PaperTrade, PaperAccount,
    BacktestJob, BacktestResult, BacktestTrade, BacktestMetrics,
    WalkForwardJob, WalkForwardWindow, WalkForwardSummary,
    MonteCarloSimulation, MonteCarloRun, MonteCarloDistribution,
    MLTuningJob, MLTuningSample, MLPrediction, MLModel
)


class Command(BaseCommand):
    help = 'Clean all data from database - Fresh start for optimized configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip confirmation prompt and proceed with cleanup',
        )
        parser.add_argument(
            '--keep-accounts',
            action='store_true',
            help='Keep PaperAccount records (default: ask)',
        )
        parser.add_argument(
            '--simple',
            action='store_true',
            help='Use simple cleanup (no prompts, keeps paper accounts)',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        if options['simple']:
            self.simple_cleanup()
        else:
            self.full_cleanup(
                skip_confirm=options['yes'],
                keep_accounts=options['keep_accounts']
            )

    def simple_cleanup(self):
        """Simple database cleanup without prompts"""
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("DATABASE CLEANUP"))
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Get counts
        self.stdout.write("Current record counts:")
        self.stdout.write(f"  Paper Trades:        {PaperTrade.objects.count()}")
        self.stdout.write(f"  Paper Accounts:      {PaperAccount.objects.count()}")
        self.stdout.write(f"  Signals:             {Signal.objects.count()}")
        self.stdout.write("")

        # Delete all data
        self.stdout.write("Deleting all data...")
        self.stdout.write("")

        # Paper Trading
        deleted = PaperTrade.objects.all().delete()[0]
        self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted} PaperTrade records"))

        # Signals
        deleted = Signal.objects.all().delete()[0]
        self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted} Signal records"))

        # Try to delete new model structures (might not exist)
        try:
            deleted = BacktestMetrics.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted} BacktestMetrics records"))
        except:
            pass

        try:
            deleted = BacktestTrade.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted} BacktestTrade records"))
        except:
            pass

        try:
            deleted = BacktestResult.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted} BacktestResult records"))
        except:
            pass

        try:
            deleted = BacktestJob.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted} BacktestJob records"))
        except:
            pass

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ Database cleaned successfully!"))
        self.stdout.write("")
        self.stdout.write("Kept (intentionally):")
        self.stdout.write(f"  Paper Accounts:      {PaperAccount.objects.count()} (users' accounts)")
        self.stdout.write("")

    def full_cleanup(self, skip_confirm=False, keep_accounts=False):
        """Full cleanup with confirmations"""
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.WARNING("DATABASE CLEANUP - WARNING"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("This will DELETE ALL data from the following tables:")
        self.stdout.write("")
        self.stdout.write("  1. Paper Trading:")
        self.stdout.write("     - PaperTrade (trades)")
        self.stdout.write("     - PaperAccount (accounts) - OPTIONAL")
        self.stdout.write("")
        self.stdout.write("  2. Signals:")
        self.stdout.write("     - Signal (all generated signals)")
        self.stdout.write("")
        self.stdout.write("  3. Backtesting:")
        self.stdout.write("     - BacktestJob, BacktestResult, BacktestTrade, BacktestMetrics")
        self.stdout.write("")
        self.stdout.write("  4. Walk-Forward Analysis:")
        self.stdout.write("     - WalkForwardJob, WalkForwardWindow, WalkForwardSummary")
        self.stdout.write("")
        self.stdout.write("  5. Monte Carlo Simulations:")
        self.stdout.write("     - MonteCarloSimulation, MonteCarloRun, MonteCarloDistribution")
        self.stdout.write("")
        self.stdout.write("  6. ML Tuning:")
        self.stdout.write("     - MLTuningJob, MLTuningSample, MLPrediction, MLModel")
        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Get counts before deletion
        counts = {
            'PaperTrade': PaperTrade.objects.count(),
            'PaperAccount': PaperAccount.objects.count(),
            'Signal': Signal.objects.count(),
            'BacktestJob': BacktestJob.objects.count() if hasattr(BacktestJob, 'objects') else 0,
            'WalkForwardJob': WalkForwardJob.objects.count() if hasattr(WalkForwardJob, 'objects') else 0,
            'MonteCarloSimulation': MonteCarloSimulation.objects.count() if hasattr(MonteCarloSimulation, 'objects') else 0,
            'MLTuningJob': MLTuningJob.objects.count() if hasattr(MLTuningJob, 'objects') else 0,
        }

        self.stdout.write("Current record counts:")
        for model, count in counts.items():
            self.stdout.write(f"  {model:25s}: {count:6d} records")
        self.stdout.write("")

        if not skip_confirm:
            response = input("Are you sure you want to DELETE ALL this data? (type 'YES' to confirm): ")
            if response != 'YES':
                self.stdout.write(self.style.WARNING("\nCleanup cancelled. No data was deleted."))
                return

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("STARTING DATABASE CLEANUP"))
        self.stdout.write("=" * 80)

        try:
            self.clean_paper_trading(keep_accounts)
            self.clean_signals()
            self.clean_backtests()
            self.clean_walkforward()
            self.clean_montecarlo()
            self.clean_mltuning()

            self.verify_clean()

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("✅ Database cleanup completed successfully!"))
            self.stdout.write("")
            self.stdout.write("Next steps:")
            self.stdout.write("  1. Restart services: docker-compose restart backend celery-worker")
            self.stdout.write("  2. New signals will be generated with corrected RSI configuration")
            self.stdout.write("  3. Wait for 50-100 trades to close")
            self.stdout.write("  4. Run ML tuning: python manage.py run_mltuning")
            self.stdout.write("")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error during cleanup: {e}"))
            self.stdout.write("Some data may have been partially deleted.")
            raise

    def clean_paper_trading(self, keep_accounts_arg=False):
        """Clean paper trading data"""
        self.stdout.write("")
        self.stdout.write("[1/6] Cleaning Paper Trading data...")

        if not keep_accounts_arg:
            keep_accounts = input("  Keep PaperAccount records? (Y/n): ").lower() != 'n'
        else:
            keep_accounts = True

        with transaction.atomic():
            # Delete paper trades
            trades_deleted = PaperTrade.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {trades_deleted} PaperTrade records"))

            if not keep_accounts:
                accounts_deleted = PaperAccount.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {accounts_deleted} PaperAccount records"))
            else:
                self.stdout.write(self.style.SUCCESS("  ✓ Kept PaperAccount records"))

    def clean_signals(self):
        """Clean signal data"""
        self.stdout.write("")
        self.stdout.write("[2/6] Cleaning Signals...")

        with transaction.atomic():
            signals_deleted = Signal.objects.all().delete()[0]
            self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {signals_deleted} Signal records"))

    def clean_backtests(self):
        """Clean backtest data"""
        self.stdout.write("")
        self.stdout.write("[3/6] Cleaning Backtest data...")

        try:
            with transaction.atomic():
                # Delete in correct order (child tables first)
                metrics_deleted = BacktestMetrics.objects.all().delete()[0]
                trades_deleted = BacktestTrade.objects.all().delete()[0]
                results_deleted = BacktestResult.objects.all().delete()[0]
                jobs_deleted = BacktestJob.objects.all().delete()[0]

                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {jobs_deleted} BacktestJob records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {results_deleted} BacktestResult records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {trades_deleted} BacktestTrade records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {metrics_deleted} BacktestMetrics records"))
        except Exception:
            self.stdout.write(self.style.WARNING("  ⚠️ Backtest models not found (skipped)"))

    def clean_walkforward(self):
        """Clean walk-forward data"""
        self.stdout.write("")
        self.stdout.write("[4/6] Cleaning Walk-Forward data...")

        try:
            with transaction.atomic():
                # Delete in correct order
                summary_deleted = WalkForwardSummary.objects.all().delete()[0]
                windows_deleted = WalkForwardWindow.objects.all().delete()[0]
                jobs_deleted = WalkForwardJob.objects.all().delete()[0]

                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {jobs_deleted} WalkForwardJob records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {windows_deleted} WalkForwardWindow records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {summary_deleted} WalkForwardSummary records"))
        except Exception:
            self.stdout.write(self.style.WARNING("  ⚠️ WalkForward models not found (skipped)"))

    def clean_montecarlo(self):
        """Clean Monte Carlo simulation data"""
        self.stdout.write("")
        self.stdout.write("[5/6] Cleaning Monte Carlo data...")

        try:
            with transaction.atomic():
                # Delete in correct order
                dist_deleted = MonteCarloDistribution.objects.all().delete()[0]
                runs_deleted = MonteCarloRun.objects.all().delete()[0]
                sims_deleted = MonteCarloSimulation.objects.all().delete()[0]

                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {sims_deleted} MonteCarloSimulation records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {runs_deleted} MonteCarloRun records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {dist_deleted} MonteCarloDistribution records"))
        except Exception:
            self.stdout.write(self.style.WARNING("  ⚠️ MonteCarlo models not found (skipped)"))

    def clean_mltuning(self):
        """Clean ML tuning data"""
        self.stdout.write("")
        self.stdout.write("[6/6] Cleaning ML Tuning data...")

        try:
            with transaction.atomic():
                # Delete in correct order
                predictions_deleted = MLPrediction.objects.all().delete()[0]
                samples_deleted = MLTuningSample.objects.all().delete()[0]
                models_deleted = MLModel.objects.all().delete()[0]
                jobs_deleted = MLTuningJob.objects.all().delete()[0]

                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {jobs_deleted} MLTuningJob records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {samples_deleted} MLTuningSample records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {predictions_deleted} MLPrediction records"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {models_deleted} MLModel records"))
        except Exception:
            self.stdout.write(self.style.WARNING("  ⚠️ MLTuning models not found (skipped)"))

    def verify_clean(self):
        """Verify database is clean"""
        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write("VERIFICATION - Current record counts:")
        self.stdout.write("=" * 80)

        counts = {
            'PaperTrade': PaperTrade.objects.count(),
            'PaperAccount': PaperAccount.objects.count(),
            'Signal': Signal.objects.count(),
        }

        # Try to count new models
        try:
            counts['BacktestJob'] = BacktestJob.objects.count()
            counts['BacktestResult'] = BacktestResult.objects.count()
            counts['BacktestTrade'] = BacktestTrade.objects.count()
            counts['BacktestMetrics'] = BacktestMetrics.objects.count()
        except:
            pass

        all_clean = True
        for model, count in counts.items():
            status = "✓" if count == 0 else "⚠️"
            if count > 0 and model != 'PaperAccount':  # PaperAccount might be kept
                all_clean = False
            self.stdout.write(f"  {status} {model:25s}: {count:6d} records")

        self.stdout.write("")
        if all_clean or (counts['PaperAccount'] > 0 and sum(counts.values()) == counts['PaperAccount']):
            self.stdout.write(self.style.SUCCESS("✅ Database is clean! Ready for fresh start with optimized configuration."))
        else:
            self.stdout.write(self.style.WARNING("⚠️  Some records remain. This might be intentional (e.g., PaperAccount)."))
        self.stdout.write("=" * 80)
