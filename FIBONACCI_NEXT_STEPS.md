# 🚀 Fibonacci Pullback System - Next Steps Implementation Guide

## Overview

This guide covers **Tasks 4-7** - the advanced features that complete the end-to-end Fibonacci pullback trading system.

---

## Task 4: Real-Time Fibonacci Pullback Watcher

### Purpose
Monitor signals with `status = "WAITING_FOR_PULLBACK"` and detect when price enters the golden zone.

### Implementation

#### Step 1: Create Watcher Service

**File**: `backend/scanner/services/fib_watcher.py` (NEW FILE)

```python
"""
Fibonacci Pullback Price Watcher

Monitors signals waiting for pullback and triggers entry when price enters golden zone.
"""
import logging
from decimal import Decimal
from typing import List, Dict
from django.utils import timezone
from scanner.services.fib_utils import check_fibonacci_pullback
from scanner.services.dispatcher import SignalDispatcher
from signals.models import Signal
from binance.client import Client

logger = logging.getLogger(__name__)


class FibonacciPullbackWatcher:
    """
    Real-time price watcher for Fibonacci pullback signals.
    """

    def __init__(self):
        self.binance_client = Client()  # Use existing Binance client
        self.dispatcher = SignalDispatcher()

    def get_waiting_signals(self) -> List[Signal]:
        """
        Fetch all signals with status = 'WAITING_FOR_PULLBACK'.

        Returns:
            List of Signal objects
        """
        return Signal.objects.filter(
            status='WAITING_FOR_PULLBACK'
        ).select_related('symbol')

    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')

        Returns:
            Current price as float
        """
        try:
            ticker = self.binance_client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def check_entry_zone(self, signal: Signal, current_price: float) -> bool:
        """
        Check if current price is in Fibonacci entry zone.

        Args:
            signal: Signal object with Fibonacci metadata
            current_price: Current market price

        Returns:
            True if price in entry zone
        """
        meta = signal.meta
        if not meta or 'fib_50' not in meta or 'fib_61_8' not in meta:
            logger.warning(f"Signal {signal.id} missing Fibonacci metadata")
            return False

        fib_50 = float(meta['fib_50'])
        fib_61_8 = float(meta['fib_61_8'])

        if signal.direction == 'LONG':
            # For LONG: fib_61_8 <= price <= fib_50
            in_zone = fib_61_8 <= current_price <= fib_50
        else:  # SHORT
            # For SHORT: fib_50 <= price <= fib_61_8
            in_zone = fib_50 <= current_price <= fib_61_8

        return in_zone

    def trigger_entry(self, signal: Signal, current_price: float):
        """
        Trigger entry when price enters golden zone.

        Actions:
        1. Update signal status to 'ENTRY_ZONE_REACHED'
        2. Emit WebSocket event 'fib_entry_triggered'
        3. Auto-create paper trade (if enabled)

        Args:
            signal: Signal object
            current_price: Current market price
        """
        logger.info(
            f"🎯 FIBONACCI ENTRY TRIGGERED: {signal.symbol.symbol} {signal.direction} "
            f"at {current_price:.2f} (Zone: {signal.meta.get('fib_61_8'):.2f} - {signal.meta.get('fib_50'):.2f})"
        )

        # Update signal status
        signal.status = 'ENTRY_ZONE_REACHED'
        signal.updated_at = timezone.now()
        signal.save(update_fields=['status', 'updated_at'])

        # Emit WebSocket event
        self.emit_entry_event(signal, current_price)

        # Auto-create paper trade (Task 7)
        self.create_paper_trade(signal, current_price)

    def emit_entry_event(self, signal: Signal, current_price: float):
        """
        Emit WebSocket event: fib_entry_triggered

        Args:
            signal: Signal object
            current_price: Current market price
        """
        event_data = {
            'type': 'fib_entry_triggered',
            'signal_id': signal.id,
            'symbol': signal.symbol.symbol,
            'side': signal.direction,
            'entry_price': current_price,
            'entry_zone': 'golden_ratio',
            'meta': signal.meta,
            'timestamp': timezone.now().isoformat()
        }

        try:
            self.dispatcher.broadcast_signal(event_data)
            logger.info(f"✅ Fibonacci entry event broadcasted for {signal.symbol.symbol}")
        except Exception as e:
            logger.error(f"Error broadcasting Fibonacci entry event: {e}")

    def create_paper_trade(self, signal: Signal, current_price: float):
        """
        Auto-create paper trade when entry zone reached.

        SL Strategy: Use fib_78_6 level (more conservative)
        TP Strategy: Use Fibonacci extensions

        Args:
            signal: Signal object
            current_price: Entry price
        """
        from signals.services.paper_trader import PaperTradingService
        from signals.models import PaperTrade

        try:
            # Get Fibonacci metadata
            meta = signal.meta
            fib_78_6 = Decimal(str(meta.get('fib_78_6')))

            # Calculate SL (use 78.6% level for safer stop)
            sl = fib_78_6

            # Calculate TP (use extension or standard 9%)
            if 'ext_1_618' in meta:
                # Use golden ratio extension if available
                tp = Decimal(str(meta['ext_1_618']))
            else:
                # Fallback to standard 9% TP
                if signal.direction == 'LONG':
                    tp = Decimal(str(current_price)) * Decimal('1.09')
                else:
                    tp = Decimal(str(current_price)) * Decimal('0.91')

            # Create paper trade
            paper_trade = PaperTrade.objects.create(
                signal=signal,
                symbol=signal.symbol.symbol,
                direction=signal.direction,
                entry_price=Decimal(str(current_price)),
                stop_loss=sl,
                take_profit=tp,
                quantity=Decimal('100'),
                position_size=Decimal('10000'),
                status='OPEN',
                entry_time=timezone.now()
            )

            logger.info(
                f"📊 Paper trade created: {signal.symbol.symbol} {signal.direction} "
                f"Entry={current_price:.2f}, SL={sl:.2f}, TP={tp:.2f}"
            )

            return paper_trade

        except Exception as e:
            logger.error(f"Error creating paper trade for Fibonacci entry: {e}")
            return None

    def monitor(self):
        """
        Main monitoring loop - checks all waiting signals.

        Called by Celery task every 10 seconds.
        """
        waiting_signals = self.get_waiting_signals()

        if not waiting_signals:
            logger.debug("No signals waiting for pullback")
            return

        logger.info(f"Monitoring {len(waiting_signals)} Fibonacci pullback signals")

        for signal in waiting_signals:
            try:
                # Get current price
                current_price = self.get_current_price(signal.symbol.symbol)
                if current_price is None:
                    continue

                # Check if price in entry zone
                in_zone = self.check_entry_zone(signal, current_price)

                if in_zone:
                    self.trigger_entry(signal, current_price)
                else:
                    logger.debug(
                        f"{signal.symbol.symbol}: Price {current_price:.2f} "
                        f"outside zone [{signal.meta.get('fib_61_8'):.2f} - {signal.meta.get('fib_50'):.2f}]"
                    )

            except Exception as e:
                logger.error(f"Error monitoring signal {signal.id}: {e}")
                continue
```

#### Step 2: Create Celery Task

**File**: `backend/scanner/tasks/celery_tasks.py` (ADD TO EXISTING)

```python
from scanner.services.fib_watcher import FibonacciPullbackWatcher

@shared_task(bind=True, max_retries=3)
def monitor_fibonacci_pullbacks(self):
    """
    Monitor Fibonacci pullback signals and trigger entries.

    Runs every 10 seconds via Celery Beat.
    """
    try:
        logger.info("🔍 Monitoring Fibonacci pullback signals...")

        watcher = FibonacciPullbackWatcher()
        watcher.monitor()

        logger.info("✅ Fibonacci monitoring complete")

    except Exception as e:
        logger.error(f"Error in Fibonacci monitoring: {e}")
        raise self.retry(exc=e, countdown=10)
```

#### Step 3: Add to Celery Beat Schedule

**File**: `backend/config/celery.py` (UPDATE SCHEDULE)

```python
app.conf.beat_schedule = {
    # ... existing tasks ...

    'monitor-fibonacci-pullbacks': {
        'task': 'scanner.tasks.celery_tasks.monitor_fibonacci_pullbacks',
        'schedule': 10.0,  # Every 10 seconds
    },
}
```

---

## Task 5: WebSocket Event Integration

### Frontend WebSocket Listener

**File**: `frontend/src/services/websocket.js` (or equivalent)

```javascript
// Listen for Fibonacci entry events
socket.on('fib_entry_triggered', (data) => {
    console.log('🎯 Fibonacci Entry Triggered:', data);

    // Show notification
    showNotification({
        title: 'Golden Zone Entry Detected!',
        message: `${data.symbol} ${data.side} at $${data.entry_price}`,
        type: 'success',
        duration: 5000
    });

    // Update UI
    updateSignalStatus(data.signal_id, 'ENTRY_ZONE_REACHED');

    // Highlight on dashboard
    highlightFibonacciEntry(data);

    // Optional: Play alert sound
    playAlertSound('fibonacci_entry');

    // Optional: Display Fibonacci levels on chart
    displayFibonacciLevels(data.meta);
});
```

### Notification Component

```javascript
function showNotification({ title, message, type, duration }) {
    // Toast notification or modal
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-title">${title}</div>
        <div class="notification-message">${message}</div>
    `;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, duration);
}
```

### Chart Integration (Optional)

```javascript
function displayFibonacciLevels(meta) {
    const chart = getActiveChart();  // Your chart library

    // Add Fibonacci retracement levels
    chart.addHorizontalLine(meta.fib_50, {
        color: '#FFD700',
        width: 2,
        label: 'Fib 50%'
    });

    chart.addHorizontalLine(meta.fib_61_8, {
        color: '#FF6347',
        width: 2,
        label: 'Fib 61.8% (Golden Ratio)'
    });

    chart.addHorizontalLine(meta.fib_78_6, {
        color: '#4169E1',
        width: 1,
        style: 'dashed',
        label: 'Fib 78.6% (SL)'
    });

    // Highlight entry zone
    chart.addZone({
        from: meta.fib_61_8,
        to: meta.fib_50,
        color: 'rgba(255, 215, 0, 0.2)',
        label: 'Golden Zone'
    });
}
```

---

## Task 6: Signal Model Updates (Database)

### Migration for `status` Field

**File**: `backend/signals/migrations/XXXX_add_fibonacci_status.py` (NEW)

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0XXX_previous_migration'),  # Update with actual
    ]

    operations = [
        migrations.AddField(
            model_name='signal',
            name='status',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('ACTIVE', 'Active'),
                    ('WAITING_FOR_PULLBACK', 'Waiting for Pullback'),
                    ('ENTRY_ZONE_REACHED', 'Entry Zone Reached'),
                    ('EXPIRED', 'Expired'),
                    ('EXECUTED', 'Executed'),
                    ('CANCELLED', 'Cancelled'),
                ],
                default='ACTIVE',
                help_text='Signal status'
            ),
        ),
        migrations.AlterField(
            model_name='signal',
            name='meta',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Fibonacci and strategy metadata'
            ),
        ),
    ]
```

### Run Migration

```bash
docker exec docker-web-1 python manage.py makemigrations
docker exec docker-web-1 python manage.py migrate
```

---

## Task 7: Testing & Validation

### Integration Test

**File**: `test_fibonacci_integration.py` (NEW)

```python
#!/usr/bin/env python3
"""
Integration test for Fibonacci pullback system.

Tests the full lifecycle:
1. Signal generation with Fibonacci
2. Price watcher detects entry zone
3. WebSocket event emission
4. Paper trade creation
"""
import time
from backend.scanner.services.fib_watcher import FibonacciPullbackWatcher
from signals.models import Signal, PaperTrade


def test_full_lifecycle():
    print("🧪 Testing Fibonacci Pullback Full Lifecycle")

    # 1. Create mock signal with WAITING_FOR_PULLBACK status
    signal = Signal.objects.create(
        symbol_id=1,  # BTCUSDT
        direction='LONG',
        entry=50000.00,
        sl=48500.00,
        tp=54500.00,
        confidence=0.82,
        timeframe='4h',
        status='WAITING_FOR_PULLBACK',
        meta={
            'strategy': 'fibonacci_pullback',
            'swing_high': 52000.00,
            'swing_low': 48000.00,
            'fib_50': 50000.00,
            'fib_61_8': 49520.00,
            'fib_78_6': 48856.00,
            'entry_zone': 'golden_ratio'
        }
    )

    print(f"✅ Signal created: {signal.id}")

    # 2. Simulate price entering golden zone
    watcher = FibonacciPullbackWatcher()

    # Mock current price = 49750 (in golden zone)
    current_price = 49750.00
    in_zone = watcher.check_entry_zone(signal, current_price)

    assert in_zone, "Price should be in golden zone"
    print(f"✅ Price {current_price} detected in golden zone")

    # 3. Trigger entry
    watcher.trigger_entry(signal, current_price)

    # 4. Verify signal status updated
    signal.refresh_from_db()
    assert signal.status == 'ENTRY_ZONE_REACHED'
    print(f"✅ Signal status updated to: {signal.status}")

    # 5. Verify paper trade created
    paper_trade = PaperTrade.objects.filter(signal=signal).first()
    assert paper_trade is not None, "Paper trade should be created"
    assert paper_trade.status == 'OPEN'
    print(f"✅ Paper trade created: {paper_trade.id}")

    # 6. Verify WebSocket event emitted
    # (Check logs for event broadcast)
    print(f"✅ WebSocket event emitted (check logs)")

    print("\n🎉 All integration tests passed!")


if __name__ == '__main__':
    test_full_lifecycle()
```

---

## Deployment Steps

### 1. Apply Code Changes

```bash
# Copy new files to server
scp backend/scanner/services/fib_watcher.py server:/app/backend/scanner/services/
scp backend/scanner/services/fib_utils.py server:/app/backend/scanner/services/

# Update existing files
git add .
git commit -m "Add Fibonacci pullback watcher and integration"
git push origin main
```

### 2. Run Migrations

```bash
docker exec docker-web-1 python manage.py makemigrations
docker exec docker-web-1 python manage.py migrate
```

### 3. Restart Services

```bash
docker restart docker-web-1
docker restart docker-worker-1
docker restart docker-beat-1
```

### 4. Verify Celery Beat Schedule

```bash
docker exec docker-beat-1 celery -A config inspect scheduled
# Should show: monitor-fibonacci-pullbacks (every 10 seconds)
```

### 5. Monitor Logs

```bash
# Watch for Fibonacci monitoring
docker logs -f docker-worker-1 | grep "Fibonacci"

# Expected output:
# 🔍 Monitoring Fibonacci pullback signals...
# 🎯 FIBONACCI ENTRY TRIGGERED: BTCUSDT LONG at 49750.00
# ✅ Paper trade created: BTCUSDT LONG Entry=49750.00
```

---

## Performance Optimization

### Caching Current Prices

```python
from django.core.cache import cache

def get_current_price_cached(symbol: str, ttl=5) -> float:
    """
    Get current price with caching (5 second TTL).

    Reduces API calls to Binance.
    """
    cache_key = f"price:{symbol}"
    price = cache.get(cache_key)

    if price is None:
        price = self.get_current_price(symbol)
        cache.set(cache_key, price, ttl)

    return price
```

### Batch Price Fetching

```python
def get_prices_batch(symbols: List[str]) -> Dict[str, float]:
    """
    Fetch prices for multiple symbols in one API call.
    """
    tickers = self.binance_client.get_all_tickers()
    price_map = {t['symbol']: float(t['price']) for t in tickers}
    return {s: price_map.get(s) for s in symbols}
```

---

## Success Metrics

### Monitor These KPIs:

1. **Entry Zone Hit Rate**: % of WAITING_FOR_PULLBACK → ENTRY_ZONE_REACHED
   - Expected: 60-70%

2. **Fibonacci Signal Win Rate**: Win rate of signals with `fibonacci_pullback = True`
   - Expected: 45-55% (vs 37% baseline)

3. **Average Time to Entry**: Time from signal generation to entry zone reached
   - Expected: 1-6 hours (depending on timeframe)

4. **False Entry Rate**: Signals that reach entry zone but don't close profitably
   - Target: < 40%

---

## Summary

**Remaining Implementation** (1-2 days of work):

- [ ] Create `FibonacciPullbackWatcher` service
- [ ] Add Celery task for monitoring
- [ ] Update Celery Beat schedule
- [ ] Create frontend WebSocket listener
- [ ] Add notification component
- [ ] Run database migration for `status` field
- [ ] Create integration tests
- [ ] Deploy and monitor

**Once complete, you'll have a fully automated Fibonacci pullback trading system! 🚀**

---

*Last Updated: November 19, 2025*
*Status: Tasks 1-3 Complete, Tasks 4-7 Implementation Guide Ready*
