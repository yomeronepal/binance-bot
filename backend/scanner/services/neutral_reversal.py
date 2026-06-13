"""
Neutral Market Signal Adjustment.

When Fear & Greed index is in the neutral zone (between short and long thresholds):
- If neutral_reversal_enabled: reverse direction + tight SL/TP
- If neutral_reversal_disabled: keep direction + tight SL/TP

Either way, neutral market always uses the tight SL/TP percentages.
"""
import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def apply_neutral_adjustment(
    direction: str,
    entry_price,
    sl,
    tp,
    market_type: str = 'FUTURES'
) -> Tuple[str, Decimal, Decimal, Optional[Dict]]:
    """
    Check if neutral market adjustment should be applied.

    In neutral F&G zone:
    - Always applies tight SL/TP (neutral_reversal_sl_pct / neutral_reversal_tp_pct)
    - Reverses direction only if neutral_reversal_enabled=True

    Args:
        direction: Original signal direction (LONG/SHORT)
        entry_price: Entry price
        sl: Original stop loss
        tp: Original take profit
        market_type: SPOT or FUTURES

    Returns:
        Tuple of (direction, sl, tp, neutral_meta)
        neutral_meta is None if not in neutral zone
    """
    if market_type != 'FUTURES':
        return direction, Decimal(str(sl)), Decimal(str(tp)), None

    try:
        from signals.models.futures import FuturesTradingSettings
        settings = FuturesTradingSettings.get_settings()

        if not settings.fear_greed_enabled:
            return direction, Decimal(str(sl)), Decimal(str(tp)), None

        from signals.services.fear_greed import get_fear_greed_value
        fg_value = get_fear_greed_value()

        if fg_value is None:
            return direction, Decimal(str(sl)), Decimal(str(tp)), None

        is_neutral = (
            settings.fear_greed_short_threshold
            < fg_value
            < settings.fear_greed_long_threshold
        )

        if not is_neutral:
            return direction, Decimal(str(sl)), Decimal(str(tp)), None

        original_direction = direction
        final_direction = direction
        is_reversed = False

        if settings.neutral_reversal_enabled:
            final_direction = 'SHORT' if direction == 'LONG' else 'LONG'
            is_reversed = True

        price = float(entry_price)
        sl_pct = float(settings.neutral_reversal_sl_pct) / 100
        tp_pct = float(settings.neutral_reversal_tp_pct) / 100

        if final_direction == 'LONG':
            new_sl = Decimal(str(round(price * (1 - sl_pct), 8)))
            new_tp = Decimal(str(round(price * (1 + tp_pct), 8)))
        else:
            new_sl = Decimal(str(round(price * (1 + sl_pct), 8)))
            new_tp = Decimal(str(round(price * (1 - tp_pct), 8)))

        neutral_meta = {
            'neutral_reversal': {
                'original_direction': original_direction,
                'final_direction': final_direction,
                'is_reversed': is_reversed,
                'fg_value': fg_value,
                'sl_pct': str(settings.neutral_reversal_sl_pct),
                'tp_pct': str(settings.neutral_reversal_tp_pct),
            }
        }

        action = f"{original_direction}->{final_direction} (REVERSED)" if is_reversed else f"{final_direction} (KEPT, tight SL/TP)"
        logger.info(
            f"NEUTRAL MARKET: F&G={fg_value}, {action}, "
            f"SL={new_sl} ({settings.neutral_reversal_sl_pct}%), "
            f"TP={new_tp} ({settings.neutral_reversal_tp_pct}%)"
        )

        return final_direction, new_sl, new_tp, neutral_meta

    except Exception as e:
        logger.error(f"Neutral adjustment check failed: {e}", exc_info=True)
        return direction, Decimal(str(sl)), Decimal(str(tp)), None


apply_neutral_reversal = apply_neutral_adjustment
