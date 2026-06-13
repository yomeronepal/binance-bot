"""
Push notification subscription model for Firebase Cloud Messaging.
"""
from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """
    Stores FCM tokens for sending push notifications to users.

    Args:
        user: The user who subscribed.
        fcm_token: Firebase Cloud Messaging device token.
        device_name: Optional label for the device.
        is_active: Whether this subscription is still valid.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )
    fcm_token = models.TextField(unique=True)
    device_name = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'push_subscriptions'
        ordering = ['-created_at']

    def __str__(self):
        label = self.device_name or self.fcm_token[:20]
        return f"{self.user.username} - {label}"


class NotificationLog(models.Model):
    """
    Audit log for every push notification sent.

    Args:
        user: Recipient user.
        title: Notification title.
        body: Notification body text.
        data: Extra JSON payload sent with the notification.
        status: Whether the send succeeded or failed.
        error_message: Error details if the send failed.
        signal: Optional link to the trading signal that triggered the notification.
    """
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partial'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_logs',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SENT')
    error_message = models.TextField(blank=True, default='')
    signal = models.ForeignKey(
        'signals.Signal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notification_logs',
    )
    tokens_targeted = models.IntegerField(default=0)
    tokens_succeeded = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.title} ({self.created_at:%Y-%m-%d %H:%M})"
