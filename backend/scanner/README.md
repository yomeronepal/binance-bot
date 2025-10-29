# Binance Scanner - Real-Time Signal Generation System

A sophisticated async trading signal generation system that polls Binance REST API, computes technical indicators, and broadcasts trading signals via WebSocket to connected clients.

## Features

- ✅ **Async Binance REST API Client** with rate limiting and retry logic
- ✅ **Technical Indicators**: RSI, MACD, EMA, ATR, ADX, Bollinger Bands, Heikin Ashi
- ✅ **Rule-Based Signal Generation** with confidence scoring (0-100%)
- ✅ **Real-Time WebSocket Broadcasting** via Django Channels
- ✅ **Automatic Database Persistence** of generated signals
- ✅ **Top Volume Pair Selection** to focus on liquid markets
- ✅ **Configurable Parameters** via environment variables
- ✅ **Comprehensive Unit Tests**

## Architecture

```
Binance API (REST)
    ↓
BinanceClient (async, rate-limited)
    ↓
Polling Worker (asyncio loop)
    ↓
Indicator Calculator (pandas/numpy)
    ↓
Signal Generator (rule-based strategy)
    ↓
WebSocket Dispatcher (Django Channels)
    ↓
React Frontend (real-time updates)
```

## Installation

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
# Binance Scanner Settings
BINANCE_INTERVAL=5m              # Candlestick interval
POLLING_INTERVAL=60              # Seconds between polling cycles
BINANCE_BATCH_SIZE=20            # Concurrent API requests
TOP_PAIRS=50                     # Number of top volume pairs to monitor
MIN_CONFIDENCE=0.7               # Minimum confidence score (0.0-1.0)
```

### 3. Run Migrations

```bash
python manage.py migrate
```

## Usage

### Start the Scanner

Using Django management command:

```bash
python manage.py run_scanner
```

With custom parameters:

```bash
python manage.py run_scanner \
    --interval 15m \
    --poll-interval 120 \
    --min-confidence 0.75 \
    --top-pairs 30
```

### Run as Standalone Script

```bash
cd scanner/tasks
python polling_worker.py
```

## Signal Generation Logic

### LONG Signal Conditions (Max 8.0 points)

| Condition | Weight | Description |
|-----------|--------|-------------|
| MACD Crossover | 1.5 | Histogram crosses above zero |
| RSI Range | 1.0 | RSI between 50-70 |
| Price > EMA50 | 1.0 | Price above 50-period EMA |
| Strong Trend | 1.0 | ADX > 20 |
| Heikin Ashi Bullish | 1.5 | HA candle is bullish |
| Volume Increase | 1.0 | Volume > 1.2x average |
| EMA Alignment | 0.5 | EMA9 > EMA21 > EMA50 |
| +DI > -DI | 0.5 | Positive directional movement |

**Minimum Score**: `8.0 * min_confidence` (e.g., 4.8 points with 0.6 confidence)

### SHORT Signal Conditions (Max 8.0 points)

| Condition | Weight | Description |
|-----------|--------|-------------|
| MACD Crossover | 1.5 | Histogram crosses below zero |
| RSI Range | 1.0 | RSI between 30-50 |
| Price < EMA50 | 1.0 | Price below 50-period EMA |
| Strong Trend | 1.0 | ADX > 20 |
| Heikin Ashi Bearish | 1.5 | HA candle is bearish |
| Volume Increase | 1.0 | Volume > 1.2x average |
| EMA Alignment | 0.5 | EMA9 < EMA21 < EMA50 |
| -DI > +DI | 0.5 | Negative directional movement |

### Stop Loss & Take Profit

Dynamic levels based on **ATR (Average True Range)**:

- **Stop Loss**: 1.5 × ATR from entry
- **Take Profit**: 2.5 × ATR from entry
- **Risk/Reward Ratio**: ~1.67

## Technical Indicators

### RSI (Relative Strength Index)
- **Period**: 14
- **Range**: 0-100
- **Signals**: Overbought (>70), Oversold (<30)

### MACD (Moving Average Convergence Divergence)
- **Fast EMA**: 12
- **Slow EMA**: 26
- **Signal Line**: 9
- **Crossover Detection**: Bullish/Bearish

### EMA (Exponential Moving Average)
- **Periods**: 9, 21, 50, 200
- **Use**: Trend direction and support/resistance

### ATR (Average True Range)
- **Period**: 14
- **Use**: Volatility measurement, SL/TP calculation

### ADX (Average Directional Index)
- **Period**: 14
- **Range**: 0-100
- **Threshold**: >20 for strong trend

### Bollinger Bands
- **Period**: 20
- **Std Dev**: 2.0
- **Use**: Volatility and overbought/oversold

### Heikin Ashi
- Smoothed candlestick representation
- **Use**: Trend identification

## WebSocket Integration

### Message Format

When a signal is generated, it's broadcast to all connected clients:

```json
{
  "type": "signal_created",
  "signal": {
    "symbol": "BTCUSDT",
    "direction": "LONG",
    "entry": 42500.50,
    "sl": 42100.00,
    "tp": 43300.00,
    "confidence": 0.85,
    "timeframe": "5m",
    "description": "Bullish setup: MACD+, RSI 62.5, strong trend (ADX 24.3)"
  },
  "timestamp": "2025-10-29T12:00:00Z"
}
```

### Connect from Frontend

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/signals/');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'signal_created') {
    console.log('New signal:', data.signal);
    // Update UI with new signal
  }
};
```

## API Rate Limiting

The Binance client implements sophisticated rate limiting:

- **Max Requests**: 1200 per minute (Binance limit)
- **Retry Logic**: Exponential backoff (1s, 2s, 4s)
- **IP Ban Detection**: HTTP 418 handling
- **429 Handling**: Respects `Retry-After` header

## Testing

Run unit tests:

```bash
pytest scanner/tests/ -v
```

Run with coverage:

```bash
pytest scanner/tests/ --cov=scanner --cov-report=html
```

Test specific module:

```bash
pytest scanner/tests/test_indicators.py -v
pytest scanner/tests/test_signal_generator.py -v
```

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_INTERVAL` | `5m` | Candlestick interval |
| `POLLING_INTERVAL` | `60` | Seconds between cycles |
| `BINANCE_BATCH_SIZE` | `20` | Concurrent API requests |
| `TOP_PAIRS` | `50` | Top volume pairs to monitor |
| `MIN_CONFIDENCE` | `0.7` | Minimum signal confidence |
| `BINANCE_API_KEY` | - | Optional API key |
| `BINANCE_API_SECRET` | - | Optional API secret |

### Command-Line Arguments

```bash
python manage.py run_scanner --help

Options:
  --interval TEXT           Candlestick interval (5m, 15m, 1h, etc.)
  --poll-interval INTEGER   Seconds between polling cycles
  --min-confidence FLOAT    Minimum confidence score (0.0-1.0)
  --batch-size INTEGER      Number of concurrent API requests
  --top-pairs INTEGER       Number of top volume pairs to monitor
```

## Performance Considerations

- **Memory Usage**: ~100-200MB for 50 pairs with 200 candles each
- **CPU Usage**: Moderate during indicator calculation, low during polling
- **Network**: ~100-500 requests per cycle depending on `TOP_PAIRS`
- **Database**: ~1-10 signals generated per cycle (varies by market conditions)

## Logging

Logs are output to console and can be configured in Django settings:

```python
LOGGING = {
    'loggers': {
        'scanner': {
            'level': 'INFO',  # Change to DEBUG for verbose output
            'handlers': ['console'],
        },
    },
}
```

## Troubleshooting

### No signals generated

- Check `MIN_CONFIDENCE` is not too high
- Verify market conditions (low volatility = fewer signals)
- Review logs for indicator calculation errors

### Rate limit errors

- Reduce `BATCH_SIZE`
- Increase `POLLING_INTERVAL`
- Reduce `TOP_PAIRS`

### WebSocket not connecting

- Verify Django Channels is running (use Daphne)
- Check Redis is running
- Confirm `CHANNEL_LAYERS` in settings.py

### Database errors

- Run migrations: `python manage.py migrate`
- Check database connection in `.env`

## Future Enhancements

- [ ] Redis caching for candle data
- [ ] Celery beat integration for scheduled polling
- [ ] ML-based confidence scoring
- [ ] Backtesting framework
- [ ] Performance metrics tracking
- [ ] Multi-timeframe analysis
- [ ] More indicator combinations

## License

This project is part of the Binance Trading Bot system.

## Contributing

1. Write tests for new features
2. Follow PEP 8 style guide
3. Update documentation
4. Submit pull request

## Support

For issues and questions, please open a GitHub issue.
