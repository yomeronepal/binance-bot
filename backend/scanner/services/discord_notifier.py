"""
Discord Webhook Notifier for Trading Signals
Sends beautifully formatted signal alerts to Discord channels.
"""
import requests
import logging
from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """
    Discord webhook notifier for trading signals.

    Setup:
    1. Create a webhook in your Discord channel:
       - Discord Channel → Settings → Integrations → Webhooks → New Webhook
    2. Copy the webhook URL
    3. Add to environment variables or Django settings:
       DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
    """

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Discord notifier.

        Args:
            webhook_url: Discord webhook URL. If not provided, reads from settings.
        """
        self.webhook_url = webhook_url or getattr(settings, 'DISCORD_WEBHOOK_URL', None)

        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured. Notifications will be disabled.")

    def is_enabled(self) -> bool:
        """Check if Discord notifications are enabled."""
        return bool(self.webhook_url)

    def send_signal(self, signal_data: Dict) -> bool:
        """
        Send trading signal to Discord.

        Args:
            signal_data: Signal dictionary with keys:
                - symbol: str
                - direction: str ('LONG' or 'SHORT')
                - entry: Decimal/float
                - sl: Decimal/float
                - tp: Decimal/float
                - confidence: float
                - timeframe: str
                - market_type: str (optional, 'SPOT' or 'FUTURES')
                - leverage: int (optional, for futures)

        Returns:
            bool: True if sent successfully
        """
        if not self.is_enabled():
            return False

        try:
            # Extract data
            symbol = signal_data['symbol']
            direction = signal_data['direction']
            entry = float(signal_data['entry'])
            sl = float(signal_data['sl'])
            tp = float(signal_data['tp'])
            confidence = float(signal_data['confidence']) * 100  # Convert to percentage
            timeframe = signal_data['timeframe']
            market_type = signal_data.get('market_type', 'SPOT')
            leverage = signal_data.get('leverage', 1)

            # Calculate risk/reward
            if direction == 'LONG':
                risk = entry - sl
                reward = tp - entry
            else:  # SHORT
                risk = sl - entry
                reward = entry - tp

            risk_reward = reward / risk if risk > 0 else 0

            # Choose color based on direction
            color = 0x00FF00 if direction == 'LONG' else 0xFF0000  # Green for LONG, Red for SHORT

            # Create emoji indicators
            direction_emoji = "🟢" if direction == 'LONG' else "🔴"
            market_emoji = "📊" if market_type == 'SPOT' else "⚡"

            # Build embed
            embed = {
                "title": f"{direction_emoji} **{direction} Signal - {symbol}** {market_emoji}",
                "description": f"New {direction} opportunity detected on {timeframe} timeframe",
                "color": color,
                "fields": [
                    {
                        "name": "📍 Entry Price",
                        "value": f"`${entry:,.4f}`",
                        "inline": True
                    },
                    {
                        "name": "🎯 Take Profit",
                        "value": f"`${tp:,.4f}`",
                        "inline": True
                    },
                    {
                        "name": "🛑 Stop Loss",
                        "value": f"`${sl:,.4f}`",
                        "inline": True
                    },
                    {
                        "name": "📊 Risk/Reward",
                        "value": f"`1:{risk_reward:.2f}`",
                        "inline": True
                    },
                    {
                        "name": "✨ Confidence",
                        "value": f"`{confidence:.1f}%`",
                        "inline": True
                    },
                    {
                        "name": "⏰ Timeframe",
                        "value": f"`{timeframe}`",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": f"{market_type} Market" + (f" • {leverage}x Leverage" if leverage > 1 else "")
                },
                "timestamp": datetime.utcnow().isoformat()
            }

            # Add potential profit/loss percentages
            profit_pct = (reward / entry) * 100
            loss_pct = (risk / entry) * 100

            embed["fields"].append({
                "name": "💰 Potential Profit",
                "value": f"`+{profit_pct:.2f}%`" + (f" (`+{profit_pct * leverage:.2f}%` with {leverage}x)" if leverage > 1 else ""),
                "inline": True
            })
            embed["fields"].append({
                "name": "⚠️ Potential Loss",
                "value": f"`-{loss_pct:.2f}%`" + (f" (`-{loss_pct * leverage:.2f}%` with {leverage}x)" if leverage > 1 else ""),
                "inline": True
            })

            # Create message payload
            payload = {
                "embeds": [embed],
                "username": "Trading Bot",
                "avatar_url": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"  # Robot icon
            }

            # Send to Discord
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            logger.info(f"✅ Sent {direction} signal for {symbol} to Discord")
            return True

        except requests.RequestException as e:
            logger.error(f"❌ Failed to send Discord notification: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error creating Discord message: {e}", exc_info=True)
            return False

    def send_custom_message(self, message: str, title: Optional[str] = None,
                           color: int = 0x3498db) -> bool:
        """
        Send a custom message to Discord.

        Args:
            message: Message content
            title: Optional title for the embed
            color: Discord color (hex integer, default: blue)

        Returns:
            bool: True if sent successfully
        """
        if not self.is_enabled():
            return False

        try:
            embed = {
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }

            if title:
                embed["title"] = title

            payload = {
                "embeds": [embed],
                "username": "Trading Bot"
            }

            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Failed to send custom Discord message: {e}")
            return False

    def send_alert(self, alert_type: str, message: str) -> bool:
        """
        Send an alert notification.

        Args:
            alert_type: Type of alert ('info', 'warning', 'error', 'success')
            message: Alert message

        Returns:
            bool: True if sent successfully
        """
        colors = {
            'info': 0x3498db,      # Blue
            'warning': 0xf39c12,   # Orange
            'error': 0xe74c3c,     # Red
            'success': 0x2ecc71    # Green
        }

        emojis = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'success': '✅'
        }

        color = colors.get(alert_type, 0x3498db)
        emoji = emojis.get(alert_type, 'ℹ️')

        return self.send_custom_message(
            message=f"{emoji} {message}",
            title=f"{alert_type.upper()} Alert",
            color=color
        )

    def send_daily_summary(self, stats: Dict) -> bool:
        """
        Send daily trading summary.

        Args:
            stats: Dictionary with keys:
                - total_signals: int
                - long_signals: int
                - short_signals: int
                - avg_confidence: float
                - symbols: list

        Returns:
            bool: True if sent successfully
        """
        if not self.is_enabled():
            return False

        try:
            total = stats.get('total_signals', 0)
            long_count = stats.get('long_signals', 0)
            short_count = stats.get('short_signals', 0)
            avg_conf = stats.get('avg_confidence', 0) * 100
            symbols = stats.get('symbols', [])

            embed = {
                "title": "📊 Daily Trading Summary",
                "color": 0x3498db,
                "fields": [
                    {
                        "name": "📈 Total Signals",
                        "value": f"`{total}`",
                        "inline": True
                    },
                    {
                        "name": "🟢 LONG Signals",
                        "value": f"`{long_count}`",
                        "inline": True
                    },
                    {
                        "name": "🔴 SHORT Signals",
                        "value": f"`{short_count}`",
                        "inline": True
                    },
                    {
                        "name": "✨ Avg Confidence",
                        "value": f"`{avg_conf:.1f}%`",
                        "inline": True
                    },
                    {
                        "name": "💱 Active Symbols",
                        "value": f"`{len(symbols)}`",
                        "inline": True
                    }
                ],
                "timestamp": datetime.utcnow().isoformat()
            }

            if symbols:
                top_symbols = ', '.join(symbols[:5])
                embed["fields"].append({
                    "name": "🔥 Top Symbols",
                    "value": f"`{top_symbols}`",
                    "inline": False
                })

            payload = {
                "embeds": [embed],
                "username": "Trading Bot"
            }

            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test Discord webhook connection.

        Returns:
            bool: True if connection successful
        """
        return self.send_custom_message(
            message="🔔 Test notification successful! Discord integration is working.",
            title="Connection Test",
            color=0x2ecc71
        )


# Global Discord notifier instance
discord_notifier = DiscordNotifier()
