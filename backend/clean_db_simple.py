#!/usr/bin/env python
"""Simple database cleanup script"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from signals.models import (
    Signal, PaperTrade, PaperAccount,
    BacktestRun, BacktestTrade, BacktestMetric,
    WalkForwardOptimization, WalkForwardWindow, WalkForwardMetric,
    MonteCarloSimulation, MonteCarloRun, MonteCarloDistribution,
    MLTuningJob, MLTuningSample, MLPrediction, MLModel,
    StrategyOptimization, OptimizationRecommendation
)

print("=" * 80)
print("DATABASE CLEANUP")
print("=" * 80)
print()

# Get counts
print("Current record counts:")
print(f"  Paper Trades:        {PaperTrade.objects.count()}")
print(f"  Paper Accounts:      {PaperAccount.objects.count()}")
print(f"  Signals:             {Signal.objects.count()}")
print(f"  Backtest Runs:       {BacktestRun.objects.count()}")
print(f"  Walk-Forward Jobs:   {WalkForwardOptimization.objects.count()}")
print(f"  Monte Carlo Sims:    {MonteCarloSimulation.objects.count()}")
print(f"  ML Tuning Jobs:      {MLTuningJob.objects.count()}")
print()

# Delete all data
print("Deleting all data...")
print()

# Paper Trading
deleted = PaperTrade.objects.all().delete()[0]
print(f"✓ Deleted {deleted} PaperTrade records")

# Signals
deleted = Signal.objects.all().delete()[0]
print(f"✓ Deleted {deleted} Signal records")

# Backtests
deleted = BacktestMetric.objects.all().delete()[0]
print(f"✓ Deleted {deleted} BacktestMetric records")
deleted = BacktestTrade.objects.all().delete()[0]
print(f"✓ Deleted {deleted} BacktestTrade records")
deleted = BacktestRun.objects.all().delete()[0]
print(f"✓ Deleted {deleted} BacktestRun records")

# Walk-Forward
deleted = WalkForwardMetric.objects.all().delete()[0]
print(f"✓ Deleted {deleted} WalkForwardMetric records")
deleted = WalkForwardWindow.objects.all().delete()[0]
print(f"✓ Deleted {deleted} WalkForwardWindow records")
deleted = WalkForwardOptimization.objects.all().delete()[0]
print(f"✓ Deleted {deleted} WalkForwardOptimization records")

# Monte Carlo
deleted = MonteCarloDistribution.objects.all().delete()[0]
print(f"✓ Deleted {deleted} MonteCarloDistribution records")
deleted = MonteCarloRun.objects.all().delete()[0]
print(f"✓ Deleted {deleted} MonteCarloRun records")
deleted = MonteCarloSimulation.objects.all().delete()[0]
print(f"✓ Deleted {deleted} MonteCarloSimulation records")

# ML Tuning
deleted = MLPrediction.objects.all().delete()[0]
print(f"✓ Deleted {deleted} MLPrediction records")
deleted = MLTuningSample.objects.all().delete()[0]
print(f"✓ Deleted {deleted} MLTuningSample records")
deleted = MLModel.objects.all().delete()[0]
print(f"✓ Deleted {deleted} MLModel records")
deleted = MLTuningJob.objects.all().delete()[0]
print(f"✓ Deleted {deleted} MLTuningJob records")

# Strategy Optimization
deleted = OptimizationRecommendation.objects.all().delete()[0]
print(f"✓ Deleted {deleted} OptimizationRecommendation records")
deleted = StrategyOptimization.objects.all().delete()[0]
print(f"✓ Deleted {deleted} StrategyOptimization records")

print()
print("=" * 80)
print("VERIFICATION")
print("=" * 80)
print()
print("Remaining records:")
print(f"  Paper Trades:        {PaperTrade.objects.count()}")
print(f"  Signals:             {Signal.objects.count()}")
print(f"  Backtest Runs:       {BacktestRun.objects.count()}")
print(f"  Walk-Forward Jobs:   {WalkForwardOptimization.objects.count()}")
print(f"  Monte Carlo Sims:    {MonteCarloSimulation.objects.count()}")
print(f"  ML Tuning Jobs:      {MLTuningJob.objects.count()}")
print()
print("✅ Database cleaned successfully!")
print()
print("Kept (intentionally):")
print(f"  Paper Accounts:      {PaperAccount.objects.count()} (users' accounts)")
print()
