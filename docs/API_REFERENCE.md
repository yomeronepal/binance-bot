# API Reference

Complete REST API documentation for the Binance Trading Bot.

## Table of Contents
1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Backtest API](#backtest-api)
4. [Signal API](#signal-api)
5. [Paper Trading API](#paper-trading-api)
6. [Walk-Forward Optimization API](#walk-forward-optimization-api)
7. [Monte Carlo API](#monte-carlo-api)
8. [ML Tuning API](#ml-tuning-api)
9. [Error Handling](#error-handling)
10. [Rate Limits](#rate-limits)

---

## Overview

**Base URL**: `http://localhost:8000/api/`

**Content Type**: `application/json`

**Date Format**: ISO 8601 (`2024-11-01T00:00:00Z`)

**Response Format**:
```json
{
  "success": true,
  "data": {...},
  "message": "Operation completed successfully"
}
```

**Error Format**:
```json
{
  "success": false,
  "error": "Error message",
  "details": {...}
}
```

---

## Authentication

**Status**: Not implemented yet (all endpoints are currently public)

**Future Implementation**: JWT Bearer Token
```http
Authorization: Bearer <token>
```

---

## Backtest API

### Create Backtest

**Endpoint**: `POST /api/backtest/`

**Description**: Submit a new backtest job with custom strategy parameters

**Request Body**:
```json
{
  "name": "OPT6 Extended Test",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "timeframe": "4h",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-11-01T00:00:00Z",
  "strategy_params": {
    "min_confidence": 0.73,
    "long_rsi_min": 23.0,
    "long_rsi_max": 33.0,
    "short_rsi_min": 67.0,
    "short_rsi_max": 77.0,
    "long_adx_min": 22.0,
    "short_adx_min": 22.0,
    "sl_atr_multiplier": 1.5,
    "tp_atr_multiplier": 5.25,
    "long_volume_multiplier": 1.2,
    "short_volume_multiplier": 1.2
  },
  "initial_capital": 10000,
  "position_size": 100
}
```

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Backtest run name |
| `symbols` | array | Yes | List of trading pairs (e.g., ["BTCUSDT"]) |
| `timeframe` | string | Yes | Candle interval: "5m", "15m", "1h", "4h", "1d" |
| `start_date` | string | Yes | Start date (ISO 8601) |
| `end_date` | string | Yes | End date (ISO 8601) |
| `strategy_params` | object | Yes | Strategy configuration |
| `initial_capital` | number | Yes | Starting capital in USD |
| `position_size` | number | Yes | Position size in USD per trade |

**Strategy Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_confidence` | float | 0.73 | Minimum signal confidence (0-1) |
| `long_rsi_min` | float | 23.0 | LONG entry RSI minimum |
| `long_rsi_max` | float | 33.0 | LONG entry RSI maximum |
| `short_rsi_min` | float | 67.0 | SHORT entry RSI minimum |
| `short_rsi_max` | float | 77.0 | SHORT entry RSI maximum |
| `long_adx_min` | float | 22.0 | ADX minimum for LONG |
| `short_adx_min` | float | 22.0 | ADX minimum for SHORT |
| `sl_atr_multiplier` | float | 1.5 | Stop loss distance (× ATR) |
| `tp_atr_multiplier` | float | 5.25 | Take profit distance (× ATR) |
| `long_volume_multiplier` | float | 1.2 | Volume threshold for LONG |
| `short_volume_multiplier` | float | 1.2 | Volume threshold for SHORT |

**Response**: `201 Created`
```json
{
  "id": 123,
  "name": "OPT6 Extended Test",
  "status": "PENDING",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "timeframe": "4h",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-11-01T00:00:00Z",
  "strategy_params": {...},
  "initial_capital": 10000.00,
  "created_at": "2024-11-06T10:30:00Z",
  "completed_at": null,
  "results": null
}
```

**Status Values**:
- `PENDING`: Queued for execution
- `RUNNING`: Currently executing
- `COMPLETED`: Finished successfully
- `FAILED`: Error occurred

---

### Get Backtest Results

**Endpoint**: `GET /api/backtest/{id}/`

**Description**: Retrieve backtest results by ID

**Path Parameters**:
- `id` (integer): Backtest run ID

**Response**: `200 OK`
```json
{
  "id": 123,
  "name": "OPT6 Extended Test",
  "status": "COMPLETED",
  "symbols": ["BTCUSDT"],
  "timeframe": "4h",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-11-01T00:00:00Z",
  "strategy_params": {...},
  "initial_capital": 10000.00,
  "created_at": "2024-11-06T10:30:00Z",
  "completed_at": "2024-11-06T10:35:00Z",
  "results": {
    "summary": {
      "roi": -0.03,
      "win_rate": 16.7,
      "profit_factor": 0.85,
      "sharpe_ratio": -0.12,
      "max_drawdown": 2.5,
      "total_trades": 6,
      "winning_trades": 1,
      "losing_trades": 5,
      "avg_win": 175.00,
      "avg_loss": -35.62,
      "avg_trade_duration_hours": 48.5,
      "final_capital": 9996.88,
      "total_pnl": -3.12,
      "total_fees": 0.00
    },
    "trades": [
      {
        "trade_id": 1,
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_time": "2024-08-15T08:00:00Z",
        "exit_time": "2024-08-17T12:00:00Z",
        "entry_price": 58500.00,
        "exit_price": 60250.00,
        "position_size": 100.00,
        "stop_loss": 57500.00,
        "take_profit": 62125.00,
        "pnl": 175.00,
        "pnl_percent": 2.99,
        "exit_reason": "TAKE_PROFIT",
        "duration_hours": 52,
        "confidence": 0.78
      },
      // ... more trades
    ],
    "equity_curve": [
      {"date": "2024-01-01", "equity": 10000.00},
      {"date": "2024-01-02", "equity": 10015.50},
      // ... daily equity values
    ],
    "signals_generated": 6,
    "signals_filtered": 12
  }
}
```

**Error Response**: `404 Not Found`
```json
{
  "error": "Backtest run not found"
}
```

---

### List All Backtests

**Endpoint**: `GET /api/backtest/`

**Description**: List all backtest runs with pagination

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Results per page |
| `status` | string | - | Filter by status |
| `symbol` | string | - | Filter by symbol |
| `ordering` | string | `-created_at` | Sort field |

**Example Request**:
```http
GET /api/backtest/?page=1&page_size=10&status=COMPLETED&ordering=-created_at
```

**Response**: `200 OK`
```json
{
  "count": 45,
  "next": "/api/backtest/?page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "name": "OPT6 Extended Test",
      "status": "COMPLETED",
      "symbols": ["BTCUSDT"],
      "timeframe": "4h",
      "created_at": "2024-11-06T10:30:00Z",
      "completed_at": "2024-11-06T10:35:00Z",
      "results": {
        "summary": {
          "roi": -0.03,
          "win_rate": 16.7,
          "total_trades": 6
        }
      }
    },
    // ... more backtests
  ]
}
```

---

### Delete Backtest

**Endpoint**: `DELETE /api/backtest/{id}/`

**Description**: Delete a backtest run

**Response**: `204 No Content`

---

## Signal API

### Get Active Signals

**Endpoint**: `GET /api/signals/`

**Description**: Retrieve all active trading signals

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | string | - | Filter by symbol |
| `signal_type` | string | - | Filter by type (LONG/SHORT) |
| `timeframe` | string | - | Filter by timeframe |
| `is_active` | boolean | true | Show only active signals |

**Response**: `200 OK`
```json
{
  "count": 3,
  "results": [
    {
      "id": 456,
      "symbol": "BTCUSDT",
      "signal_type": "LONG",
      "entry_price": 62500.00,
      "stop_loss": 61500.00,
      "take_profit": 66125.00,
      "confidence": 0.78,
      "timeframe": "4h",
      "description": "RSI oversold (28.5), MACD bullish, ADX strong (25.3)",
      "created_at": "2024-11-06T14:30:00Z",
      "is_active": true,
      "conditions_met": {
        "macd_bullish": true,
        "rsi_oversold": true,
        "adx_strong": true,
        "price_above_ema": true,
        "volume_spike": true,
        "supertrend_bullish": true,
        "mfi_bullish": true,
        "psar_bullish": true,
        "ha_bullish": true,
        "ema_alignment": true,
        "di_bullish": true,
        "bb_oversold": true,
        "volatility_normal": true
      }
    },
    // ... more signals
  ]
}
```

---

### Get Signal Details

**Endpoint**: `GET /api/signals/{id}/`

**Description**: Get detailed information about a specific signal

**Response**: `200 OK`
```json
{
  "id": 456,
  "symbol": "BTCUSDT",
  "signal_type": "LONG",
  "entry_price": 62500.00,
  "stop_loss": 61500.00,
  "take_profit": 66125.00,
  "confidence": 0.78,
  "timeframe": "4h",
  "description": "RSI oversold (28.5), MACD bullish, ADX strong (25.3)",
  "created_at": "2024-11-06T14:30:00Z",
  "is_active": true,
  "conditions_met": {...},
  "indicator_values": {
    "rsi": 28.5,
    "macd": 125.50,
    "macd_signal": 98.30,
    "adx": 25.3,
    "plus_di": 28.5,
    "minus_di": 15.2,
    "atr": 666.67,
    "ema_9": 62100.00,
    "ema_21": 61800.00,
    "ema_50": 61500.00,
    "volume": 1234.56,
    "volume_ma": 980.25,
    "bb_upper": 64500.00,
    "bb_middle": 62500.00,
    "bb_lower": 60500.00,
    "supertrend": 61000.00,
    "mfi": 55.5,
    "psar": 60800.00
  },
  "paper_trade": {
    "id": 789,
    "status": "OPEN",
    "entry_price": 62500.00,
    "current_price": 63200.00,
    "unrealized_pnl": 112.00,
    "unrealized_pnl_percent": 1.12
  }
}
```

---

### Create Manual Signal

**Endpoint**: `POST /api/signals/`

**Description**: Create a manual trading signal

**Request Body**:
```json
{
  "symbol": "BTCUSDT",
  "signal_type": "LONG",
  "entry_price": 62500.00,
  "stop_loss": 61500.00,
  "take_profit": 66125.00,
  "timeframe": "4h",
  "description": "Manual entry based on technical analysis"
}
```

**Response**: `201 Created`
```json
{
  "id": 457,
  "symbol": "BTCUSDT",
  "signal_type": "LONG",
  "entry_price": 62500.00,
  "stop_loss": 61500.00,
  "take_profit": 66125.00,
  "confidence": 1.0,
  "timeframe": "4h",
  "description": "Manual entry based on technical analysis",
  "created_at": "2024-11-06T15:00:00Z",
  "is_active": true
}
```

---

## Paper Trading API

### Enable Paper Trading

**Endpoint**: `POST /api/paper-trading/enable`

**Description**: Enable paper trading mode

**Request Body**:
```json
{
  "initial_capital": 10000,
  "position_size_percent": 10,
  "max_open_positions": 3,
  "auto_close_on_sl_tp": true
}
```

**Response**: `200 OK`
```json
{
  "message": "Paper trading enabled",
  "settings": {
    "initial_capital": 10000.00,
    "position_size_percent": 10,
    "max_open_positions": 3,
    "auto_close_on_sl_tp": true
  }
}
```

---

### Disable Paper Trading

**Endpoint**: `POST /api/paper-trading/disable`

**Description**: Disable paper trading mode (closes all positions)

**Response**: `200 OK`
```json
{
  "message": "Paper trading disabled",
  "closed_positions": 2,
  "final_capital": 10450.50,
  "total_pnl": 450.50
}
```

---

### Get Performance Metrics

**Endpoint**: `GET /api/paper-trading/performance`

**Description**: Get overall paper trading performance

**Response**: `200 OK`
```json
{
  "enabled": true,
  "initial_capital": 10000.00,
  "current_capital": 10450.50,
  "total_pnl": 450.50,
  "roi": 4.51,
  "total_trades": 15,
  "winning_trades": 8,
  "losing_trades": 7,
  "win_rate": 53.33,
  "profit_factor": 1.85,
  "avg_win": 125.00,
  "avg_loss": -65.50,
  "largest_win": 350.00,
  "largest_loss": -120.00,
  "active_positions": 2,
  "available_capital": 8200.00,
  "equity": 10450.50,
  "max_drawdown": 3.5,
  "sharpe_ratio": 1.25,
  "started_at": "2024-11-01T00:00:00Z"
}
```

---

### Get Active Positions

**Endpoint**: `GET /api/paper-trading/positions`

**Description**: List all open paper trading positions

**Response**: `200 OK`
```json
{
  "count": 2,
  "positions": [
    {
      "id": 789,
      "signal_id": 456,
      "symbol": "BTCUSDT",
      "direction": "LONG",
      "entry_price": 62500.00,
      "current_price": 63200.00,
      "position_size": 0.16,
      "position_value": 1000.00,
      "stop_loss": 61500.00,
      "take_profit": 66125.00,
      "unrealized_pnl": 112.00,
      "unrealized_pnl_percent": 1.12,
      "opened_at": "2024-11-06T14:30:00Z",
      "duration_hours": 2.5
    },
    {
      "id": 790,
      "signal_id": 458,
      "symbol": "ETHUSDT",
      "direction": "SHORT",
      "entry_price": 3200.00,
      "current_price": 3150.00,
      "position_size": 0.3125,
      "position_value": 1000.00,
      "stop_loss": 3280.00,
      "take_profit": 2880.00,
      "unrealized_pnl": 50.00,
      "unrealized_pnl_percent": 1.56,
      "opened_at": "2024-11-06T16:00:00Z",
      "duration_hours": 1.0
    }
  ]
}
```

---

### Get Trade History

**Endpoint**: `GET /api/paper-trading/history`

**Description**: Get closed paper trading positions

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Results per page |
| `symbol` | string | - | Filter by symbol |
| `direction` | string | - | Filter by direction |
| `exit_reason` | string | - | Filter by exit reason |

**Response**: `200 OK`
```json
{
  "count": 13,
  "next": "/api/paper-trading/history?page=2",
  "previous": null,
  "results": [
    {
      "id": 785,
      "signal_id": 450,
      "symbol": "BTCUSDT",
      "direction": "LONG",
      "entry_price": 58500.00,
      "exit_price": 60250.00,
      "position_size": 0.17,
      "realized_pnl": 175.00,
      "realized_pnl_percent": 2.99,
      "exit_reason": "TAKE_PROFIT",
      "opened_at": "2024-08-15T08:00:00Z",
      "closed_at": "2024-08-17T12:00:00Z",
      "duration_hours": 52
    },
    // ... more trades
  ]
}
```

---

### Close Position Manually

**Endpoint**: `POST /api/paper-trading/positions/{id}/close`

**Description**: Manually close an open position

**Path Parameters**:
- `id` (integer): Position ID

**Response**: `200 OK`
```json
{
  "message": "Position closed",
  "position": {
    "id": 789,
    "symbol": "BTCUSDT",
    "direction": "LONG",
    "entry_price": 62500.00,
    "exit_price": 63200.00,
    "realized_pnl": 112.00,
    "realized_pnl_percent": 1.12,
    "exit_reason": "MANUAL",
    "closed_at": "2024-11-06T17:00:00Z"
  }
}
```

---

## Walk-Forward Optimization API

### Create Walk-Forward Test

**Endpoint**: `POST /api/walkforward/`

**Description**: Run walk-forward optimization

**Request Body**:
```json
{
  "name": "Q4 2024 Walk-Forward",
  "symbols": ["BTCUSDT"],
  "timeframe": "4h",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-11-01T00:00:00Z",
  "in_sample_days": 60,
  "out_sample_days": 30,
  "parameter_ranges": {
    "long_rsi_min": [20, 23, 25, 28],
    "long_rsi_max": [30, 33, 35, 38],
    "long_adx_min": [20, 22, 25, 28],
    "min_confidence": [0.70, 0.73, 0.75, 0.78]
  },
  "optimization_metric": "sharpe_ratio",
  "initial_capital": 10000
}
```

**Response**: `201 Created`
```json
{
  "id": 50,
  "name": "Q4 2024 Walk-Forward",
  "status": "PENDING",
  "created_at": "2024-11-06T10:00:00Z"
}
```

---

### Get Walk-Forward Results

**Endpoint**: `GET /api/walkforward/{id}/`

**Description**: Get walk-forward optimization results

**Response**: `200 OK`
```json
{
  "id": 50,
  "name": "Q4 2024 Walk-Forward",
  "status": "COMPLETED",
  "completed_at": "2024-11-06T12:30:00Z",
  "results": {
    "windows": [
      {
        "window_id": 1,
        "in_sample_start": "2024-01-01",
        "in_sample_end": "2024-03-01",
        "out_sample_start": "2024-03-02",
        "out_sample_end": "2024-04-01",
        "best_params": {
          "long_rsi_min": 23.0,
          "long_rsi_max": 33.0,
          "long_adx_min": 22.0,
          "min_confidence": 0.73
        },
        "in_sample_metrics": {
          "roi": 2.5,
          "sharpe_ratio": 1.2,
          "win_rate": 55.0
        },
        "out_sample_metrics": {
          "roi": 1.8,
          "sharpe_ratio": 0.9,
          "win_rate": 52.0
        }
      },
      // ... more windows
    ],
    "overall_metrics": {
      "total_roi": 8.5,
      "avg_sharpe": 1.05,
      "avg_win_rate": 53.5,
      "consistency_score": 0.85
    }
  }
}
```

---

## Monte Carlo API

### Run Monte Carlo Simulation

**Endpoint**: `POST /api/montecarlo/`

**Description**: Run Monte Carlo simulation on backtest results

**Request Body**:
```json
{
  "backtest_id": 123,
  "num_simulations": 1000,
  "confidence_levels": [0.90, 0.95, 0.99]
}
```

**Response**: `201 Created`
```json
{
  "id": 25,
  "backtest_id": 123,
  "status": "PENDING",
  "num_simulations": 1000,
  "created_at": "2024-11-06T11:00:00Z"
}
```

---

### Get Monte Carlo Results

**Endpoint**: `GET /api/montecarlo/{id}/`

**Description**: Get Monte Carlo simulation results

**Response**: `200 OK`
```json
{
  "id": 25,
  "backtest_id": 123,
  "status": "COMPLETED",
  "num_simulations": 1000,
  "completed_at": "2024-11-06T11:05:00Z",
  "results": {
    "expected_roi": 2.5,
    "median_roi": 2.2,
    "best_case": 15.8,
    "worst_case": -8.5,
    "confidence_intervals": {
      "90%": {"lower": -2.5, "upper": 8.5},
      "95%": {"lower": -4.0, "upper": 10.2},
      "99%": {"lower": -6.5, "upper": 12.8}
    },
    "probability_of_profit": 65.5,
    "probability_of_ruin": 2.5,
    "value_at_risk": {
      "95%": -4.0,
      "99%": -6.5
    },
    "distribution": [
      {"roi": -10.0, "frequency": 5},
      {"roi": -9.0, "frequency": 8},
      // ... histogram data
    ]
  }
}
```

---

## ML Tuning API

### Create ML Tuning Job

**Endpoint**: `POST /api/mltuning/`

**Description**: Run machine learning hyperparameter optimization

**Request Body**:
```json
{
  "name": "Random Forest Optimization",
  "symbols": ["BTCUSDT"],
  "timeframe": "4h",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-11-01T00:00:00Z",
  "algorithm": "random_forest",
  "n_trials": 100,
  "optimization_metric": "sharpe_ratio",
  "feature_engineering": {
    "lookback_periods": [5, 10, 20, 50],
    "include_ta_features": true,
    "include_price_patterns": true
  }
}
```

**Algorithms**:
- `random_forest`: Random Forest Classifier
- `xgboost`: XGBoost Classifier
- `lightgbm`: LightGBM Classifier
- `neural_network`: Deep Learning (LSTM)

**Response**: `201 Created`
```json
{
  "id": 15,
  "name": "Random Forest Optimization",
  "status": "PENDING",
  "created_at": "2024-11-06T09:00:00Z"
}
```

---

### Get ML Tuning Results

**Endpoint**: `GET /api/mltuning/{id}/`

**Description**: Get ML tuning results

**Response**: `200 OK`
```json
{
  "id": 15,
  "name": "Random Forest Optimization",
  "status": "COMPLETED",
  "algorithm": "random_forest",
  "completed_at": "2024-11-06T10:30:00Z",
  "results": {
    "best_params": {
      "n_estimators": 200,
      "max_depth": 10,
      "min_samples_split": 5,
      "min_samples_leaf": 2
    },
    "best_score": 1.45,
    "training_metrics": {
      "accuracy": 0.68,
      "precision": 0.72,
      "recall": 0.65,
      "f1_score": 0.68
    },
    "backtest_metrics": {
      "roi": 12.5,
      "sharpe_ratio": 1.45,
      "win_rate": 58.5,
      "total_trades": 45
    },
    "feature_importance": {
      "rsi_14": 0.18,
      "macd_histogram": 0.15,
      "adx_14": 0.12,
      "volume_ratio": 0.10,
      // ... more features
    }
  }
}
```

---

## Error Handling

### Error Response Format

```json
{
  "success": false,
  "error": "Validation error",
  "details": {
    "field": "timeframe",
    "message": "Invalid timeframe. Must be one of: 5m, 15m, 1h, 4h, 1d"
  }
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 204 | No Content | Resource deleted successfully |
| 400 | Bad Request | Invalid request parameters |
| 404 | Not Found | Resource not found |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Celery worker not responding |

### Common Errors

**Invalid Timeframe**:
```json
{
  "error": "Invalid timeframe",
  "details": {
    "valid_options": ["5m", "15m", "1h", "4h", "1d"]
  }
}
```

**Insufficient Data**:
```json
{
  "error": "Insufficient historical data",
  "details": {
    "symbol": "BTCUSDT",
    "timeframe": "4h",
    "available_from": "2024-01-15T00:00:00Z",
    "requested_from": "2024-01-01T00:00:00Z"
  }
}
```

**Backtest Running**:
```json
{
  "error": "Backtest already running",
  "details": {
    "running_backtests": 3,
    "max_concurrent": 5
  }
}
```

---

## Rate Limits

**Current**: No rate limits (development)

**Future Production Limits**:
- 100 requests per minute per IP
- 10 backtest submissions per hour
- 5 concurrent backtests per user

**Rate Limit Response**: `429 Too Many Requests`
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## Webhooks (Future Feature)

### Register Webhook

**Endpoint**: `POST /api/webhooks/`

**Request Body**:
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["signal.created", "backtest.completed", "position.closed"],
  "secret": "your-webhook-secret"
}
```

**Webhook Payload**:
```json
{
  "event": "signal.created",
  "timestamp": "2024-11-06T14:30:00Z",
  "data": {
    "signal_id": 456,
    "symbol": "BTCUSDT",
    "signal_type": "LONG",
    "confidence": 0.78
  },
  "signature": "sha256=abc123..."
}
```

---

## Examples

### Python Example

```python
import requests

API_BASE = "http://localhost:8000/api"

# Create backtest
response = requests.post(
    f"{API_BASE}/backtest/",
    json={
        "name": "Test Run",
        "symbols": ["BTCUSDT"],
        "timeframe": "4h",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-11-01T00:00:00Z",
        "strategy_params": {
            "min_confidence": 0.73,
            "long_rsi_min": 23.0,
            "long_rsi_max": 33.0,
            "long_adx_min": 22.0,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 5.25
        },
        "initial_capital": 10000,
        "position_size": 100
    }
)

backtest_id = response.json()["id"]
print(f"Backtest created: {backtest_id}")

# Poll for results
import time
while True:
    response = requests.get(f"{API_BASE}/backtest/{backtest_id}/")
    data = response.json()

    if data["status"] == "COMPLETED":
        print(f"ROI: {data['results']['summary']['roi']}%")
        print(f"Win Rate: {data['results']['summary']['win_rate']}%")
        break
    elif data["status"] == "FAILED":
        print("Backtest failed")
        break

    time.sleep(5)
```

### cURL Example

```bash
# Create backtest
curl -X POST http://localhost:8000/api/backtest/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Run",
    "symbols": ["BTCUSDT"],
    "timeframe": "4h",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-11-01T00:00:00Z",
    "strategy_params": {
      "min_confidence": 0.73,
      "long_rsi_min": 23.0,
      "long_rsi_max": 33.0,
      "long_adx_min": 22.0,
      "sl_atr_multiplier": 1.5,
      "tp_atr_multiplier": 5.25
    },
    "initial_capital": 10000,
    "position_size": 100
  }'

# Get results
curl http://localhost:8000/api/backtest/123/

# List signals
curl http://localhost:8000/api/signals/?symbol=BTCUSDT&is_active=true

# Get paper trading performance
curl http://localhost:8000/api/paper-trading/performance
```

---

## Additional Resources

- [Technical Documentation](TECHNICAL_DOCUMENTATION.md)
- [Development Guide](DEVELOPMENT_GUIDE.md)
- [Testing Guide](TESTING_GUIDE.md)

---

**Last Updated**: November 6, 2025
**Version**: 1.0.0
**API Version**: v1
