"""
User models for authentication and profiles
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    """
    email = models.EmailField(unique=True)
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Binance API credentials (encrypted in production)
    binance_api_key = models.CharField(max_length=255, blank=True, null=True)
    binance_api_secret = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']

    def __str__(self):
        return self.username
