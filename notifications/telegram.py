"""Tiny synchronous Telegram Bot API client (no bot framework required)."""
import requests
from django.conf import settings


class TelegramAPIError(Exception):
    """An unsuccessful Telegram Bot API operation."""


def send_telegram_message(chat_id, text):
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token.startswith("replace-"):
        raise TelegramAPIError("Токен Telegram-бота не настроен")
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        data = response.json()
    except (requests.RequestException, ValueError):
        # Do not log `exc`: requests errors may contain the secret token in URL.
        raise TelegramAPIError("Сетевая ошибка Telegram API") from None
    if not isinstance(data, dict):
        raise TelegramAPIError("Некорректный ответ Telegram API")
    if response.status_code != 200 or not data.get("ok"):
        description = str(data.get("description", "Telegram API rejected request"))
        raise TelegramAPIError(description.replace(token, "[REDACTED]")[:255])
    return data
