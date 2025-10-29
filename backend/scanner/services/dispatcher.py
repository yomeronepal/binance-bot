"""WebSocket dispatcher for broadcasting trading signals."""
import logging
from typing import Dict
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

logger = logging.getLogger(__name__)


class SignalDispatcher:
    """Dispatches trading signals via Django Channels WebSocket."""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def broadcast_signal(self, signal_data: Dict):
        """
        Broadcast signal to all connected WebSocket clients.
        
        Args:
            signal_data: Signal dictionary with keys:
                - symbol: str
                - direction: str ('LONG' or 'SHORT')
                - entry: Decimal
                - sl: Decimal
                - tp: Decimal
                - confidence: float
                - timeframe: str
                - description: str (optional)
        """
        if not self.channel_layer:
            logger.error("Channel layer not configured")
            return
        
        try:
            # Convert Decimal to float for JSON serialization
            broadcast_data = {
                'symbol': signal_data['symbol'],
                'direction': signal_data['direction'],
                'entry': float(signal_data['entry']),
                'sl': float(signal_data['sl']),
                'tp': float(signal_data['tp']),
                'confidence': float(signal_data['confidence']),
                'timeframe': signal_data['timeframe'],
                'description': signal_data.get('description', ''),
            }
            
            # Send to signals_global group (all connected clients)
            async_to_sync(self.channel_layer.group_send)(
                'signals_global',
                {
                    'type': 'signal_created',
                    'signal': broadcast_data
                }
            )
            
            logger.info(
                f"Broadcasted {broadcast_data['direction']} signal for {broadcast_data['symbol']} "
                f"(confidence: {broadcast_data['confidence']:.2%})"
            )
            
        except Exception as e:
            logger.error(f"Failed to broadcast signal: {e}", exc_info=True)
    
    def broadcast_scanner_status(self, status: str, message: str = ""):
        """
        Broadcast scanner status update.
        
        Args:
            status: Status string ('running', 'stopped', 'error')
            message: Optional status message
        """
        if not self.channel_layer:
            return
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                'signals_global',
                {
                    'type': 'scanner_status',
                    'status': status,
                    'message': message
                }
            )
            logger.debug(f"Broadcasted scanner status: {status}")
        except Exception as e:
            logger.error(f"Failed to broadcast status: {e}")


# Global dispatcher instance
signal_dispatcher = SignalDispatcher()
