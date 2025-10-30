# Auto-Optimization API Reference

Quick reference for Phase 6 Continuous Learning & Optimization endpoints.

---

## Base URL
```
http://localhost:8000/api/learning/
```

---

## Endpoints

### 1. Get Optimization History
**GET** `/api/learning/history/`

View past optimization runs with filtering.

**Auth**: Required (any authenticated user)

**Query Parameters:**
- `volatility` - Filter by level (HIGH, MEDIUM, LOW, ALL)
- `time_range` - Filter by time (7d, 30d, 90d, all) - default: 30d
- `improvement_only` - Show only successful runs (true/false)
- `limit` - Number of results (default: 50)

**Example:**
```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/learning/history/?volatility=HIGH&time_range=30d&improvement_only=true"
```

**Response:**
```json
{
  "runs": [
    {
      "id": 15,
      "run_id": "opt_20251030_030000_abc123",
      "trigger": "SCHEDULED",
      "volatility_level": "HIGH",
      "baseline_score": 78.3,
      "best_score": 88.1,
      "improvement_percentage": 12.5,
      "improvement_found": true,
      "candidates_tested": 8,
      "duration_seconds": 245,
      "started_at": "2025-10-30T03:00:00Z",
      "completed_at": "2025-10-30T03:04:05Z"
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

---

### 2. Get Configuration History
**GET** `/api/learning/configs/`

View strategy configuration versions.

**Auth**: Required

**Query Parameters:**
- `volatility` - Filter by level
- `status` - Filter by status (ACTIVE, TESTING, ARCHIVED, FAILED)
- `improved_only` - Show only improved configs (true/false)
- `limit` - Number of results (default: 50)

**Example:**
```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/learning/configs/?status=ACTIVE"
```

**Response:**
```json
{
  "configs": [
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
      "status": "ACTIVE",
      "applied_at": "2025-10-30T03:15:22Z",
      "created_at": "2025-10-30T03:12:15Z"
    }
  ],
  "count": 1
}
```

---

### 3. Get Active Configurations
**GET** `/api/learning/configs/active/`

Get currently active configs for all volatility levels.

**Auth**: Required

**Example:**
```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/learning/configs/active/"
```

**Response:**
```json
{
  "active_configs": [
    {
      "id": 40,
      "config_name": "LOW_optimized",
      "volatility_level": "LOW",
      "version": 3,
      "parameters": {...},
      "metrics": {...},
      "fitness_score": 82.1,
      "status": "ACTIVE"
    },
    {
      "id": 41,
      "config_name": "MEDIUM_optimized",
      "volatility_level": "MEDIUM",
      "version": 4,
      "parameters": {...},
      "metrics": {...},
      "fitness_score": 79.8,
      "status": "ACTIVE"
    },
    {
      "id": 42,
      "config_name": "HIGH_optimized",
      "volatility_level": "HIGH",
      "version": 5,
      "parameters": {...},
      "metrics": {...},
      "fitness_score": 85.4,
      "status": "ACTIVE"
    }
  ]
}
```

---

### 4. Get Trade Counter Status
**GET** `/api/learning/counters/`

Check progress towards optimization threshold.

**Auth**: Required

**Example:**
```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/learning/counters/"
```

**Response:**
```json
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
    },
    {
      "volatility_level": "LOW",
      "count": 87,
      "threshold": 200,
      "percentage": 43.5,
      "last_optimization": "2025-10-20T03:00:00Z"
    }
  ],
  "timestamp": "2025-10-30T10:30:00Z"
}
```

---

### 5. Trigger Manual Optimization
**POST** `/api/learning/optimize/`

Manually trigger optimization for specific volatility level.

**Auth**: Admin required

**Request Body:**
```json
{
  "volatility_level": "HIGH",
  "lookback_days": 30
}
```

**Validations:**
- `volatility_level`: Must be HIGH, MEDIUM, LOW, or ALL
- `lookback_days`: Must be between 7 and 365

**Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"volatility_level": "HIGH", "lookback_days": 30}' \
  "http://localhost:8000/api/learning/optimize/"
```

**Response:**
```json
{
  "status": "triggered",
  "task_id": "abc123-def456-ghi789",
  "volatility_level": "HIGH",
  "lookback_days": 30,
  "message": "Optimization task started for HIGH volatility"
}
```

---

### 6. Get Optimization Run Details
**GET** `/api/learning/runs/<run_id>/`

Get detailed information about specific optimization run.

**Auth**: Required

**Example:**
```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/learning/runs/opt_20251030_030000_abc123/"
```

**Response:**
```json
{
  "id": 15,
  "run_id": "opt_20251030_030000_abc123",
  "trigger": "SCHEDULED",
  "volatility_level": "HIGH",
  "baseline_config": 40,
  "baseline_config_name": "HIGH_optimized v4",
  "winning_config": 42,
  "winning_config_name": "HIGH_optimized v5",
  "candidates_tested": 8,
  "improvement_found": true,
  "baseline_score": 78.3,
  "best_score": 88.1,
  "improvement_percentage": 12.5,
  "status": "COMPLETED",
  "started_at": "2025-10-30T03:00:00Z",
  "completed_at": "2025-10-30T03:04:05Z",
  "duration_seconds": 245,
  "duration_formatted": "4m 5s",
  "trades_analyzed": 156,
  "lookback_days": 30,
  "results": {
    "baseline": {
      "params": {...},
      "metrics": {...},
      "score": 78.3
    },
    "best_candidate": {
      "params": {...},
      "metrics": {...},
      "score": 88.1
    },
    "improvement_pct": 12.5,
    "all_candidates": [
      {"params": {...}, "score": 82.1},
      {"params": {...}, "score": 88.1},
      {"params": {...}, "score": 79.5},
      ...
    ]
  },
  "logs": "...",
  "notification_sent": true,
  "notification_sent_at": "2025-10-30T03:04:10Z"
}
```

---

### 7. Compare Configurations
**GET** `/api/learning/compare/`

Compare two strategy configurations.

**Auth**: Required

**Query Parameters:**
- `config_a_id` - ID of first config (required)
- `config_b_id` - ID of second config (required)

**Example:**
```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/learning/compare/?config_a_id=40&config_b_id=42"
```

**Response:**
```json
{
  "config_a": {
    "name": "HIGH_optimized",
    "version": 4,
    "score": 78.3,
    "metrics": {
      "win_rate": 58.2,
      "profit_factor": 1.8,
      "sharpe_ratio": 1.5,
      "roi": 15.3,
      "max_drawdown": -12.1
    }
  },
  "config_b": {
    "name": "HIGH_optimized",
    "version": 5,
    "score": 88.1,
    "metrics": {
      "win_rate": 62.5,
      "profit_factor": 2.1,
      "sharpe_ratio": 1.8,
      "roi": 18.7,
      "max_drawdown": -8.3
    }
  },
  "improvement_percentage": 12.5,
  "winner": "config_b"
}
```

---

### 8. Get Learning Metrics
**GET** `/api/learning/metrics/`

Get overall system learning statistics.

**Auth**: Required

**Example:**
```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/learning/metrics/"
```

**Response:**
```json
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
    {
      "volatility": "MEDIUM",
      "total_runs": 16,
      "improvements_found": 7,
      "success_rate": 43.8
    },
    {
      "volatility": "LOW",
      "total_runs": 14,
      "improvements_found": 8,
      "success_rate": 57.1
    }
  ],
  "timestamp": "2025-10-30T10:30:00Z"
}
```

---

### 9. Apply Configuration
**POST** `/api/learning/configs/<config_id>/apply/`

Manually apply a specific configuration (override automatic system).

**Auth**: Admin required

**Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://localhost:8000/api/learning/configs/42/apply/"
```

**Response:**
```json
{
  "status": "success",
  "message": "Configuration HIGH_optimized v5 is now active",
  "config": {
    "id": 42,
    "config_name": "HIGH_optimized",
    "volatility_level": "HIGH",
    "version": 5,
    "parameters": {...},
    "metrics": {...},
    "fitness_score": 85.4,
    "status": "ACTIVE",
    "applied_at": "2025-10-30T10:35:12Z"
  }
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid volatility_level. Must be one of: ['HIGH', 'MEDIUM', 'LOW', 'ALL']"
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden (Admin required)
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
  "error": "Optimization run opt_xyz not found"
}
```

---

## Celery Tasks (Background)

These tasks run automatically - no API calls needed:

### check_trade_threshold
- **Schedule**: Every hour at :10
- **Purpose**: Check if trade counters reached threshold
- **Triggers**: auto_optimize_strategy if needed

### scheduled_optimization
- **Schedule**: Every Sunday at 3:00 AM
- **Purpose**: Weekly optimization for all volatility levels
- **Runs**: Even if trade threshold not reached

### monitor_config_performance
- **Schedule**: Every 6 hours
- **Purpose**: Detect performance degradation (>15% drop)
- **Triggers**: Emergency optimization if needed

### cleanup_old_optimization_runs
- **Schedule**: 1st of each month at 2:00 AM
- **Purpose**: Delete old runs (>90 days, no improvement)
- **Keeps**: All successful improvements

---

## Authentication

All endpoints require JWT authentication:

```bash
# Get token
TOKEN=$(curl -X POST http://localhost:8000/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.access')

# Use token
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/learning/metrics/"
```

---

## Integration Example (Python)

```python
import requests

class OptimizationClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def get_active_configs(self):
        """Get currently active configurations"""
        response = requests.get(
            f'{self.base_url}/learning/configs/active/',
            headers=self.headers
        )
        return response.json()

    def get_trade_counters(self):
        """Check progress towards optimization"""
        response = requests.get(
            f'{self.base_url}/learning/counters/',
            headers=self.headers
        )
        return response.json()

    def trigger_optimization(self, volatility='HIGH', lookback=30):
        """Manually trigger optimization"""
        response = requests.post(
            f'{self.base_url}/learning/optimize/',
            headers=self.headers,
            json={
                'volatility_level': volatility,
                'lookback_days': lookback
            }
        )
        return response.json()

    def get_optimization_history(self, time_range='30d', improvements_only=True):
        """Get recent optimization runs"""
        params = {
            'time_range': time_range,
            'improvement_only': 'true' if improvements_only else 'false'
        }
        response = requests.get(
            f'{self.base_url}/learning/history/',
            headers=self.headers,
            params=params
        )
        return response.json()

    def get_learning_metrics(self):
        """Get overall learning statistics"""
        response = requests.get(
            f'{self.base_url}/learning/metrics/',
            headers=self.headers
        )
        return response.json()


# Usage
client = OptimizationClient('http://localhost:8000/api', 'your-token-here')

# Check active configs
configs = client.get_active_configs()
print(f"Active configs: {len(configs['active_configs'])}")

# Check trade counters
counters = client.get_trade_counters()
for counter in counters['counters']:
    print(f"{counter['volatility_level']}: {counter['percentage']:.1f}%")

# Get metrics
metrics = client.get_learning_metrics()
print(f"Success rate: {metrics['overview']['success_rate']:.1f}%")
print(f"Avg improvement: {metrics['overview']['avg_improvement_pct']:.1f}%")
```

---

## Monitoring Dashboard Integration

```javascript
// React/Vue component example
const OptimizationMonitor = () => {
  const [counters, setCounters] = useState([]);
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      const [countersRes, metricsRes] = await Promise.all([
        fetch('/api/learning/counters/', {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch('/api/learning/metrics/', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);

      setCounters(await countersRes.json());
      setMetrics(await metricsRes.json());
    };

    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute

    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <h2>Learning System Status</h2>

      {/* Trade counters */}
      {counters.counters?.map(counter => (
        <ProgressBar
          key={counter.volatility_level}
          label={counter.volatility_level}
          value={counter.percentage}
          max={100}
        />
      ))}

      {/* Overall metrics */}
      <Stats>
        <Stat label="Success Rate" value={metrics?.overview.success_rate + '%'} />
        <Stat label="Avg Improvement" value={metrics?.overview.avg_improvement_pct + '%'} />
        <Stat label="Total Runs" value={metrics?.overview.total_optimization_runs} />
      </Stats>
    </div>
  );
};
```

---

For complete implementation details, see: `docs/PHASE6_AUTO_OPTIMIZATION_COMPLETE.md`
