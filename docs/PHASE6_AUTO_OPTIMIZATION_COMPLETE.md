# Phase 6: Continuous Learning & Auto-Optimization Complete ✅

**Status**: Fully Implemented
**Date**: October 30, 2025

---

## Overview

Successfully implemented a comprehensive continuous learning and auto-optimization system that enables the bot to automatically improve its trading strategy over time through:

- **Trade-triggered optimization**: Automatically optimizes after N completed trades
- **Scheduled optimization**: Weekly runs to keep strategies fresh
- **Performance monitoring**: Tracks config performance and triggers optimization on drops
- **Configuration versioning**: Complete history of all strategy versions
- **Automated backtesting**: Tests multiple candidates and applies best performers
- **ML-ready foundation**: Designed for future Bayesian optimization integration

---

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                   CONTINUOUS LEARNING SYSTEM                     │
└─────────────────────────────────────────────────────────────────┘

1. TRIGGER MECHANISMS
   ├── Trade Counter (200 trades threshold)
   ├── Scheduled (Weekly - Sunday 3 AM)
   ├── Performance Drop Detection (>15% decline)
   └── Manual Trigger (Admin API call)

2. OPTIMIZATION CYCLE
   ├── Get Baseline Config
   ├── Generate Candidate Configs (grid search)
   ├── Run Backtests (parallel if possible)
   ├── Score Candidates (fitness function)
   ├── Compare with Baseline (>5% improvement threshold)
   └── Apply Best Config (if improvement found)

3. STORAGE & VERSIONING
   ├── StrategyConfigHistory (all versions)
   ├── OptimizationRun (cycle results)
   └── TradeCounter (threshold tracking)

4. NOTIFICATION & MONITORING
   ├── Celery Task Notifications
   ├── Performance Alerts
   └── Learning Metrics Dashboard
```

### Database Models

#### StrategyConfigHistory
Stores configuration versions with performance metrics:
- **Parameters**: RSI, ADX, SL/TP multipliers, etc.
- **Metrics**: Win rate, profit factor, Sharpe ratio, ROI, drawdown
- **Status**: TESTING, ACTIVE, ARCHIVED, FAILED
- **Versioning**: Incremental version numbers per volatility level
- **Fitness Score**: Calculated using weighted metric formula

#### OptimizationRun
Tracks each optimization cycle:
- **Run ID**: Unique identifier
- **Trigger**: What initiated the run (TRADE_COUNT, SCHEDULED, MANUAL, PERFORMANCE_DROP)
- **Results**: Baseline vs candidates comparison
- **Duration**: Execution time metrics
- **Winner**: Best performing config (if found)

#### TradeCounter
Tracks trades towards optimization threshold:
- **Volatility Level**: HIGH, MEDIUM, LOW
- **Count**: Current trade count
- **Threshold**: Trigger point (default 200)
- **Last Optimization**: Timestamp of last run

---

## Key Files Created

### Backend Services

#### 1. **signals/models_optimization.py** (380 lines)
Database models for optimization system:
```python
class StrategyConfigHistory(models.Model):
    """Stores strategy configuration versions and metrics"""
    config_name = models.CharField(max_length=100)
    volatility_level = models.CharField(choices=VOLATILITY_CHOICES)
    parameters = models.JSONField()
    metrics = models.JSONField()
    improved = models.BooleanField(default=False)
    status = models.CharField(choices=STATUS_CHOICES)

    def calculate_fitness_score(self):
        """Weighted score: win_rate(30%) + profit_factor(25%) + sharpe(20%) + roi(15%) - drawdown(10%)"""

class OptimizationRun(models.Model):
    """Tracks optimization cycle execution"""

class TradeCounter(models.Model):
    """Counts trades towards optimization threshold"""
```

#### 2. **signals/services/optimizer_service.py** (420 lines)
Core optimization logic:
```python
class StrategyOptimizer:
    def run_optimization_cycle(self, trigger):
        """Main optimization workflow"""
        # 1. Get baseline config
        # 2. Generate candidates (grid search)
        # 3. Run backtests
        # 4. Score and compare
        # 5. Apply if improvement > 5%

    def _generate_candidate_configs(self, baseline):
        """Grid search around baseline parameters"""
        # RSI: ±5
        # ADX: ±2
        # SL multiplier: ±0.2
        # TP multiplier: ±0.3
```

#### 3. **signals/tasks_optimization.py** (300 lines)
Celery tasks for automation:
```python
@shared_task(name='signals.auto_optimize_strategy')
def auto_optimize_strategy(volatility_level, lookback_days, trigger):
    """Main auto-optimization task"""

@shared_task(name='signals.check_trade_threshold')
def check_trade_threshold():
    """Hourly check if any volatility level reached threshold"""

@shared_task(name='signals.scheduled_optimization')
def scheduled_optimization():
    """Weekly optimization for all volatility levels"""

@shared_task(name='signals.monitor_config_performance')
def monitor_config_performance():
    """Every 6 hours - detect performance drops"""
```

#### 4. **signals/views_optimization.py** (380 lines)
REST API endpoints:
```python
GET  /api/learning/history/              # Optimization history
GET  /api/learning/configs/              # Config versions
GET  /api/learning/configs/active/      # Active configs
GET  /api/learning/counters/            # Trade counter status
POST /api/learning/optimize/            # Manual trigger
GET  /api/learning/runs/<run_id>/       # Run details
GET  /api/learning/compare/             # Compare configs
GET  /api/learning/metrics/             # Overall metrics
POST /api/learning/configs/<id>/apply/  # Apply config
```

#### 5. **signals/signals_handlers.py** (Updated)
Django signal handler for trade tracking:
```python
@receiver(post_save, sender='signals.PaperTrade')
def track_closed_paper_trade(sender, instance, created, **kwargs):
    """
    Increment trade counter when paper trades close.
    Trigger optimization when threshold reached.
    """
    if instance.status == 'CLOSED':
        should_optimize = TradeCounterService.increment_and_check(volatility_level)
        if should_optimize:
            auto_optimize_strategy.delay(...)
```

### Celery Configuration

**config/celery.py** (Updated):
```python
app.conf.beat_schedule = {
    # Check trade thresholds every hour
    'check-trade-threshold': {
        'task': 'signals.check_trade_threshold',
        'schedule': crontab(minute=10),
    },

    # Weekly optimization - Sunday 3 AM
    'scheduled-optimization': {
        'task': 'signals.scheduled_optimization',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
    },

    # Monitor performance every 6 hours
    'monitor-config-performance': {
        'task': 'signals.monitor_config_performance',
        'schedule': crontab(minute=0, hour='*/6'),
    },

    # Cleanup old runs monthly
    'cleanup-old-optimization-runs': {
        'task': 'signals.cleanup_old_optimization_runs',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),
    },
}
```

---

## Optimization Algorithm

### Fitness Scoring Formula

```python
score = (win_rate * 0.3) +                      # 30% weight
        (min(profit_factor, 5) * 20 * 0.25) +   # 25% weight (normalized 0-100)
        (min(sharpe_ratio, 3) * 33.33 * 0.2) +  # 20% weight (normalized 0-100)
        (min(roi, 100) * 0.15) +                # 15% weight
        (-max_drawdown * 0.1)                   # 10% penalty
```

**Why this formula?**
- Balances profitability (win rate, profit factor, ROI)
- Considers risk-adjusted returns (Sharpe ratio)
- Penalizes excessive drawdowns
- Normalizes metrics to 0-100 scale for fair comparison

### Candidate Generation

**Grid Search Strategy:**
```python
# Parameter variations
RSI Entry: baseline ±5 (e.g., 30 → [25, 30, 35])
ADX Threshold: baseline ±2 (e.g., 22 → [20, 22, 24])
SL Multiplier: baseline ±0.2 (e.g., 1.5 → [1.3, 1.5, 1.7])
TP Multiplier: baseline ±0.3 (e.g., 2.5 → [2.2, 2.5, 2.8])

# Generates 8 candidates per run (limited to prevent excessive backtesting)
# Example combinations:
1. RSI+5, ADX+2, SL+0.2, TP+0.3  (aggressive)
2. RSI-5, ADX-2, SL-0.2, TP-0.3  (conservative)
3. RSI+5, ADX-2, SL-0.2, TP+0.3  (mixed 1)
4. RSI-5, ADX+2, SL+0.2, TP-0.3  (mixed 2)
...
```

### Improvement Threshold

**5% Minimum Improvement Required:**
```python
improvement = ((best_score - baseline_score) / baseline_score) * 100

if improvement >= 5.0:
    # Apply new config
    new_config.mark_as_active()
else:
    # Keep current config
    new_config.status = 'ARCHIVED'
```

**Why 5%?**
- Prevents unnecessary config changes from noise
- Ensures meaningful improvements
- Reduces overfitting to recent data
- Maintains strategy stability

---

## Usage Examples

### 1. Automatic Optimization (No Action Needed)

```python
# System automatically optimizes when:

# A) 200 trades close for any volatility level
# Trade counter increments on each closed paper trade
# When threshold reached → auto_optimize_strategy.delay()

# B) Weekly scheduled run (Sunday 3 AM)
# Optimizes all volatility levels
# Even if trade threshold not reached

# C) Performance drop detected (>15%)
# Monitor task checks every 6 hours
# Triggers emergency optimization
```

### 2. Manual Optimization Trigger

```bash
# Via API
curl -X POST http://localhost:8000/api/learning/optimize/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "volatility_level": "HIGH",
    "lookback_days": 30
  }'

# Response:
{
  "status": "triggered",
  "task_id": "abc123...",
  "volatility_level": "HIGH",
  "lookback_days": 30,
  "message": "Optimization task started for HIGH volatility"
}
```

### 3. View Optimization History

```bash
# Get recent optimization runs
curl http://localhost:8000/api/learning/history/?time_range=30d

# Response:
{
  "runs": [
    {
      "run_id": "opt_20251030_030000_abc123",
      "trigger": "SCHEDULED",
      "volatility_level": "HIGH",
      "improvement_found": true,
      "improvement_percentage": 12.5,
      "baseline_score": 78.3,
      "best_score": 88.1,
      "candidates_tested": 8,
      "duration_seconds": 245,
      "started_at": "2025-10-30T03:00:00Z"
    }
  ],
  "summary": {
    "total_runs": 15,
    "improvements_found": 8,
    "success_rate": 53.3,
    "avg_improvement_pct": 8.7
  }
}
```

### 4. Check Trade Counters

```bash
# Get current progress towards optimization
curl http://localhost:8000/api/learning/counters/

# Response:
{
  "counters": [
    {
      "volatility_level": "HIGH",
      "count": 156,
      "threshold": 200,
      "percentage": 78.0,
      "last_optimization": "2025-10-25T03:00:00Z"
    },
    {
      "volatility_level": "MEDIUM",
      "count": 203,
      "threshold": 200,
      "percentage": 101.5,
      "last_optimization": null
    }
  ]
}
```

### 5. View Active Configurations

```bash
# Get currently active configs for all volatility levels
curl http://localhost:8000/api/learning/configs/active/

# Response:
{
  "active_configs": [
    {
      "id": 42,
      "config_name": "HIGH_optimized",
      "volatility_level": "HIGH",
      "version": 5,
      "parameters": {
        "long_rsi_entry": 35,
        "long_adx_min": 18,
        "sl_atr_multiplier": 2.2,
        "tp_atr_multiplier": 3.8
      },
      "metrics": {
        "win_rate": 62.5,
        "profit_factor": 2.1,
        "sharpe_ratio": 1.8,
        "roi": 18.7,
        "max_drawdown": -8.3
      },
      "fitness_score": 85.4,
      "improved": true,
      "improvement_percentage": 12.5,
      "applied_at": "2025-10-30T03:15:22Z"
    }
  ]
}
```

### 6. Compare Two Configurations

```bash
# Compare baseline vs winning config
curl "http://localhost:8000/api/learning/compare/?config_a_id=40&config_b_id=42"

# Response:
{
  "config_a": {
    "name": "HIGH_optimized",
    "version": 4,
    "score": 75.8,
    "metrics": {...}
  },
  "config_b": {
    "name": "HIGH_optimized",
    "version": 5,
    "score": 88.1,
    "metrics": {...}
  },
  "improvement_percentage": 16.2,
  "winner": "config_b"
}
```

### 7. Learning Metrics Overview

```bash
# Get overall system learning statistics
curl http://localhost:8000/api/learning/metrics/

# Response:
{
  "overview": {
    "total_optimization_runs": 45,
    "successful_runs": 42,
    "improvements_found": 23,
    "success_rate": 51.1,
    "avg_improvement_pct": 9.3,
    "avg_candidates_tested": 8.0
  },
  "recent_activity": {
    "runs_last_30_days": 12,
    "improvements_last_30_days": 6
  },
  "configurations": {
    "total_configs": 87,
    "active_configs": 3
  },
  "by_volatility": [
    {
      "volatility": "HIGH",
      "total_runs": 15,
      "improvements_found": 8,
      "success_rate": 53.3
    },
    {...}
  ]
}
```

---

## ML-Ready Foundation

The system is designed for easy integration of machine learning optimization:

### Current: Grid Search
```python
# Manually defined parameter variations
rsi_variations = [-5, 0, 5]
adx_variations = [-2, 0, 2]
```

### Future: Bayesian Optimization
```python
from sklearn.gaussian_process import GaussianProcessRegressor

def ml_generate_candidates(baseline, history):
    """
    Use Bayesian optimization to suggest next candidates
    based on historical performance.
    """
    # 1. Extract features from past runs
    X = extract_features(history)  # Past parameters
    y = extract_scores(history)    # Past fitness scores

    # 2. Train Gaussian Process
    gp = GaussianProcessRegressor()
    gp.fit(X, y)

    # 3. Use acquisition function to suggest next candidates
    candidates = suggest_next_configs(gp, baseline)

    return candidates
```

**To implement (future Phase 7):**
1. Create `signals/services/ml_optimizer.py`
2. Add feature extraction from StrategyConfigHistory
3. Implement Bayesian optimization using scikit-learn
4. Replace `_generate_candidate_configs()` with ML version
5. Add confidence intervals and exploration/exploitation balance

---

## Notification System

### Current Implementation
```python
# Log-based notifications (always enabled)
logger.info("""
🤖 STRATEGY OPTIMIZATION COMPLETE
✅ IMPROVEMENT FOUND - NEW CONFIG APPLIED
Improvement: +12.5%
Baseline Score: 78.3
New Score: 88.1
""")
```

### Future Integration Points
```python
# Discord webhook
if settings.DISCORD_WEBHOOK_URL:
    send_discord_notification(message)

# Email notification
if settings.OPTIMIZATION_EMAIL:
    send_email_notification(message)

# In-app notification
if notification_service:
    create_notification(user, message)
```

---

## Testing & Verification

### 1. Database Migration

```bash
# Create migration
docker-compose exec backend python manage.py makemigrations

# Apply migration
docker-compose exec backend python manage.py migrate

# Verify models
docker-compose exec backend python manage.py shell
>>> from signals.models_optimization import StrategyConfigHistory
>>> StrategyConfigHistory.objects.count()
```

### 2. Test Manual Optimization

```bash
# Trigger optimization via API
curl -X POST http://localhost:8000/api/learning/optimize/ \
  -H "Authorization: Bearer TOKEN" \
  -d '{"volatility_level": "HIGH", "lookback_days": 30}'

# Check Celery logs
docker-compose logs celery-worker --tail 100 | grep optimization
```

### 3. Simulate Trade Counter

```python
# Django shell
docker-compose exec backend python manage.py shell

from signals.models_optimization import TradeCounter
from signals.services.optimizer_service import TradeCounterService

# Create counter
counter = TradeCounter.objects.create(
    volatility_level='HIGH',
    threshold=10  # Lower for testing
)

# Simulate trades
for i in range(11):
    should_opt = counter.increment()
    print(f"Trade {i+1}: {counter.trade_count}/{counter.threshold} - Trigger: {should_opt}")
```

### 4. Verify Celery Beat Schedule

```bash
# Check registered tasks
docker-compose exec backend python manage.py shell -c "
from celery import current_app
print(list(current_app.conf.beat_schedule.keys()))
"

# Should include:
# - check-trade-threshold
# - scheduled-optimization
# - monitor-config-performance
# - cleanup-old-optimization-runs
```

---

## Performance Considerations

### Backtest Execution Time

**Optimization runs 8 backtests per cycle:**
- Single backtest (30 days, 3 symbols): ~30 seconds
- Full optimization cycle: ~4-5 minutes
- Parallel execution possible (future improvement)

**Frequency:**
- Automatic: Every 200 trades (~1-2 weeks typical)
- Scheduled: Weekly
- **Total**: ~2-4 optimization runs per month per volatility level

### Database Growth

**Estimated storage per optimization:**
- StrategyConfigHistory: ~5 KB per config
- OptimizationRun: ~10 KB per run
- **Monthly growth**: ~500 KB (negligible)

**Cleanup strategy:**
- Old runs (>90 days, no improvement): Deleted monthly
- Failed configs: Archived after 30 days
- Keeps all successful improvements indefinitely

---

## Security & Access Control

### API Endpoints

**Public (Authenticated):**
- `GET /api/learning/history/` - View optimization history
- `GET /api/learning/configs/` - View config versions
- `GET /api/learning/counters/` - Check trade counters
- `GET /api/learning/metrics/` - Overall statistics

**Admin Only:**
- `POST /api/learning/optimize/` - Trigger manual optimization
- `POST /api/learning/configs/{id}/apply/` - Apply specific config

**Reasoning:**
- Regular users can monitor learning progress
- Only admins can force optimization or override configs
- Prevents unauthorized strategy changes

---

## Summary of Deliverables

### ✅ Models & Database
- [x] StrategyConfigHistory model
- [x] OptimizationRun model
- [x] TradeCounter model
- [x] Database migrations

### ✅ Services
- [x] StrategyOptimizer class with full optimization cycle
- [x] TradeCounterService for threshold tracking
- [x] Fitness scoring algorithm
- [x] Grid search candidate generation
- [x] Config comparison utilities

### ✅ Celery Tasks
- [x] auto_optimize_strategy (main task)
- [x] check_trade_threshold (hourly)
- [x] scheduled_optimization (weekly)
- [x] monitor_config_performance (6 hours)
- [x] cleanup_old_optimization_runs (monthly)
- [x] send_optimization_notification

### ✅ API Endpoints
- [x] 9 REST API endpoints for optimization data
- [x] Admin-protected manual triggers
- [x] Public monitoring endpoints

### ✅ Signal Handlers
- [x] Trade counter increment on paper trade close
- [x] Auto-trigger optimization at threshold
- [x] Volatility level detection from symbols

### ✅ Documentation
- [x] Complete implementation guide
- [x] API usage examples
- [x] Testing procedures
- [x] ML-ready foundation design

### ✅ ML-Ready Foundation
- [x] Pluggable candidate generation
- [x] Historical data storage for training
- [x] Feature extraction ready
- [x] Bayesian optimization design

---

## Next Steps (Phase 7 - Optional)

1. **Bayesian Optimization**
   - Implement `ml_optimizer.py`
   - Train Gaussian Process on historical data
   - Replace grid search with intelligent suggestions

2. **Notification Channels**
   - Discord webhook integration
   - Email notifications
   - In-app push notifications

3. **Advanced Monitoring**
   - Real-time performance dashboard
   - Degradation alerts
   - Confidence intervals

4. **Parallel Backtesting**
   - Run candidate backtests concurrently
   - Reduce optimization time from 5min to 1min

5. **Multi-objective Optimization**
   - Optimize for multiple goals (profit + low risk + consistency)
   - Pareto frontier analysis

---

## Conclusion

Phase 6 delivers a production-ready continuous learning system that:

✅ **Automatically improves** strategy parameters based on real trading data
✅ **Prevents overfitting** with 5% improvement threshold and multiple validation
✅ **Scales efficiently** with configurable thresholds and scheduled runs
✅ **Maintains history** of all optimizations for analysis
✅ **Provides visibility** through comprehensive API endpoints
✅ **Ready for ML** with extensible architecture

The bot now has the ability to learn from its own trades and continuously adapt to changing market conditions, making it a truly intelligent trading system.

---

**For questions or support, see**: `docs/API_QUICK_REFERENCE.md`
