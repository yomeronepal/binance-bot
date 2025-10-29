"""Signal generation strategy with confidence scoring."""
import pandas as pd
from typing import Optional, Dict
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates trading signals based on technical indicators."""
    
    def __init__(self, min_confidence: float = 0.6):
        self.min_confidence = min_confidence
    
    def generate_signal(self, symbol: str, df: pd.DataFrame, timeframe: str = '5m') -> Optional[Dict]:
        """Generate trading signal based on indicator analysis."""
        if len(df) < 2:
            return None
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        long_signal, long_conf = self._check_long_conditions(df, current, previous)
        if long_signal and long_conf >= self.min_confidence:
            entry = float(current['close'])
            sl, tp = self._calculate_long_levels(df, entry)
            return {
                'symbol': symbol, 'direction': 'LONG',
                'entry': Decimal(str(entry)), 'sl': Decimal(str(sl)), 'tp': Decimal(str(tp)),
                'confidence': long_conf, 'timeframe': timeframe,
                'description': self._generate_description('LONG', df, current)
            }
        
        short_signal, short_conf = self._check_short_conditions(df, current, previous)
        if short_signal and short_conf >= self.min_confidence:
            entry = float(current['close'])
            sl, tp = self._calculate_short_levels(df, entry)
            return {
                'symbol': symbol, 'direction': 'SHORT',
                'entry': Decimal(str(entry)), 'sl': Decimal(str(sl)), 'tp': Decimal(str(tp)),
                'confidence': short_conf, 'timeframe': timeframe,
                'description': self._generate_description('SHORT', df, current)
            }
        
        return None
    
    def _check_long_conditions(self, df, current, previous):
        score, max_score = 0.0, 8.0
        try:
            if previous['macd_hist'] <= 0 and current['macd_hist'] > 0:
                score += 1.5
            if 50 < current['rsi'] < 70:
                score += 1.0
            elif current['rsi'] > previous['rsi']:
                score += 0.5
            if current['close'] > current['ema_50']:
                score += 1.0
            if current['adx'] > 20:
                score += 1.0
            if current['ha_bullish']:
                score += 1.5
            if current['volume_trend'] > 1.2:
                score += 1.0
            elif current['volume_trend'] > 1.0:
                score += 0.5
            if current['ema_9'] > current['ema_21'] > current['ema_50']:
                score += 0.5
            if current['plus_di'] > current['minus_di']:
                score += 0.5
            
            confidence = min(score / max_score, 1.0)
            triggered = score >= (max_score * self.min_confidence)
            return triggered, confidence
        except Exception as e:
            logger.error(f"Error checking LONG: {e}")
            return False, 0.0
    
    def _check_short_conditions(self, df, current, previous):
        score, max_score = 0.0, 8.0
        try:
            if previous['macd_hist'] >= 0 and current['macd_hist'] < 0:
                score += 1.5
            if 30 < current['rsi'] < 50:
                score += 1.0
            elif current['rsi'] < previous['rsi']:
                score += 0.5
            if current['close'] < current['ema_50']:
                score += 1.0
            if current['adx'] > 20:
                score += 1.0
            if not current['ha_bullish']:
                score += 1.5
            if current['volume_trend'] > 1.2:
                score += 1.0
            elif current['volume_trend'] > 1.0:
                score += 0.5
            if current['ema_9'] < current['ema_21'] < current['ema_50']:
                score += 0.5
            if current['minus_di'] > current['plus_di']:
                score += 0.5
            
            confidence = min(score / max_score, 1.0)
            triggered = score >= (max_score * self.min_confidence)
            return triggered, confidence
        except Exception as e:
            logger.error(f"Error checking SHORT: {e}")
            return False, 0.0
    
    def _calculate_long_levels(self, df, entry):
        atr = float(df.iloc[-1]['atr'])
        sl = entry - (1.5 * atr)
        tp = entry + (2.5 * atr)
        return sl, tp
    
    def _calculate_short_levels(self, df, entry):
        atr = float(df.iloc[-1]['atr'])
        sl = entry + (1.5 * atr)
        tp = entry - (2.5 * atr)
        return sl, tp
    
    def _generate_description(self, direction, df, current):
        parts = []
        if direction == 'LONG':
            parts.append("Bullish setup:")
            if current['macd_hist'] > 0:
                parts.append("MACD+")
            if current['rsi'] > 50:
                parts.append(f"RSI {current['rsi']:.1f}")
        else:
            parts.append("Bearish setup:")
            if current['macd_hist'] < 0:
                parts.append("MACD-")
            if current['rsi'] < 50:
                parts.append(f"RSI {current['rsi']:.1f}")
        return ", ".join(parts)
