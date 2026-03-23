"""
Management command to send test push notifications.

Usage:
    python manage.py test_push
    python manage.py test_push --title "Custom Title" --body "Custom body"
    python manage.py test_push --signal  (simulates a priority signal notification)
    python manage.py test_push --session (simulates a trading session activation)
"""
from django.core.management.base import BaseCommand

from signals.services.push_notification import broadcast, get_firebase_app
from signals.models_push import PushSubscription


class Command(BaseCommand):
    """Send test push notifications to all active subscribers."""

    help = 'Send a test push notification to all subscribers'

    def add_arguments(self, parser):
        parser.add_argument('--title', type=str, default=None)
        parser.add_argument('--body', type=str, default=None)
        parser.add_argument('--signal', action='store_true', help='Simulate a priority signal notification')
        parser.add_argument('--session', action='store_true', help='Simulate a session activation notification')

    def handle(self, *args, **options):
        app = get_firebase_app()
        if not app:
            self.stderr.write(self.style.ERROR('Firebase not initialized. Check FIREBASE_CREDENTIALS_JSON env var.'))
            return

        active = PushSubscription.objects.filter(is_active=True).count()
        self.stdout.write(f'Active subscribers: {active}')

        if active == 0:
            self.stderr.write(self.style.WARNING('No subscribers. Enable notifications in the app first.'))
            return

        title, body, data = self._build_notification(options)

        self.stdout.write(f'Sending: "{title}"')
        result = broadcast(title, body, data=data)

        self.stdout.write(
            self.style.SUCCESS(f'Sent: {result["sent"]}/{result["total"]} | Failed: {result["failed"]}')
        )
        if result['error']:
            self.stderr.write(self.style.ERROR(f'Error: {result["error"]}'))

    def _build_notification(self, options):
        """Build notification payload based on command options."""
        if options['signal']:
            return (
                '\U0001F7E2 LONG BTCUSDT [PRIORITY]',
                'Entry: $84,500 | SL: $83,200 | TP: $87,000 | Conf: 85%',
                {'type': 'NEW_SIGNAL', 'symbol': 'BTCUSDT', 'direction': 'LONG', 'is_priority': 'true', 'url': '/bot-performance'},
            )

        if options['session']:
            return (
                'Trading Session Active - GW1',
                'Started at 10:15 AM NPT | Ends at 11:30 NPT | Priority signals will auto-trade',
                {'type': 'SESSION_ACTIVE', 'session_name': 'GW1', 'url': '/bot-performance'},
            )

        return (
            options['title'] or 'RevX Test Notification',
            options['body'] or 'Push notifications are working!',
            {'type': 'TEST', 'url': '/bot-performance'},
        )
