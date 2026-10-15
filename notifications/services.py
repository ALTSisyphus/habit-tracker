"""One-time code generation and private-chat Telegram linking."""
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from users.models import TelegramLinkCode, User


@transaction.atomic
def create_link_code(user):
    User.objects.select_for_update().get(pk=user.pk)
    TelegramLinkCode.objects.filter(user=user).delete()
    return TelegramLinkCode.objects.create(
        user=user,
        code=secrets.token_urlsafe(24),
        expires_at=timezone.now() + timedelta(minutes=10),
    )


@transaction.atomic
def link_telegram_chat(code, chat_id):
    """Consume a valid one-time code; returns True if chat was linked."""
    link = (
        TelegramLinkCode.objects
        .filter(code=code, expires_at__gt=timezone.now())
        .first()
    )
    if not link:
        return False
    # Serialize issuing and consuming codes on the same user, in the same order.
    user = User.objects.select_for_update().get(pk=link.user_id)
    if not TelegramLinkCode.objects.filter(
        pk=link.pk, expires_at__gt=timezone.now()
    ).exists():
        return False
    try:
        # A chat can belong to only one user.
        with transaction.atomic():
            user.telegram_chat_id = chat_id
            user.save(update_fields=["telegram_chat_id"])
    except IntegrityError:
        return False
    TelegramLinkCode.objects.filter(user_id=link.user_id).delete()
    return True


def bot_link(code):
    username = settings.TELEGRAM_BOT_USERNAME.lstrip("@")
    return f"https://t.me/{username}?start={code}"
