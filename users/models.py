"""Custom users and expiring one-time Telegram linking codes."""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    telegram_chat_id = models.BigIntegerField(
        unique=True, null=True, blank=True, verbose_name="Telegram chat ID"
    )


class TelegramLinkCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_link_codes",
    )
    code = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Telegram link code for user {self.user_id}"
