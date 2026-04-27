"""
Per-user Binance API connection storage.

One row per User. Credentials are stored encrypted (Fernet, see
``signals.services.credential_crypto``); the row also tracks the
permissions the key was found to have when last validated, so the UI
can warn about overly broad keys without repeatedly hitting Binance.

Slice 1 scope: the row exists, can be created/updated/deleted, and is
read by a health-check task. It is NOT yet used to place orders — the
trading fan-out lives in slice 4.
"""
from django.conf import settings
from django.db import models


class UserBinanceConnection(models.Model):
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PAUSED = 'PAUSED'
    STATUS_REVOKED = 'REVOKED'
    STATUS_BROKEN = 'BROKEN'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_REVOKED, 'Revoked'),
        (STATUS_BROKEN, 'Broken'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='binance_connection',
    )
    api_key_enc = models.BinaryField()
    api_secret_enc = models.BinaryField()
    api_key_hint = models.CharField(max_length=12, blank=True)

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PAUSED
    )
    permissions = models.JSONField(default=dict, blank=True)
    ip_check_passed = models.BooleanField(default=False)

    last_check_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_binance_connection'
        verbose_name = 'User Binance Connection'
        verbose_name_plural = 'User Binance Connections'

    def __str__(self):
        return f"BinanceConnection({self.user_id}, {self.status})"

    @property
    def is_healthy(self):
        return self.status == self.STATUS_ACTIVE and self.ip_check_passed

    @property
    def can_withdraw(self):
        return bool(self.permissions.get('canWithdraw', False))
