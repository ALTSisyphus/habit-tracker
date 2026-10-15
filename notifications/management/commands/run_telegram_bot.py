"""Long-polling bot for secure /start <code> account linking."""
import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from notifications.services import link_telegram_chat
from notifications.telegram import TelegramAPIError, send_telegram_message

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Start Telegram /start linking bot (getUpdates long polling)"

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token or token.startswith("replace-"):
            raise CommandError("Set TELEGRAM_BOT_TOKEN in .env first")
        offset = None
        self.stdout.write("Telegram bot is polling for /start commands")
        while True:
            try:
                response = requests.get(
                    f"https://api.telegram.org/bot{token}/getUpdates",
                    params={
                        "offset": offset,
                        "timeout": 25,
                        "allowed_updates": '["message"]',
                    },
                    timeout=35,
                )
                result = response.json()
                if response.status_code != 200 or not result.get("ok"):
                    logger.warning("Telegram getUpdates returned an error")
                    time.sleep(5)
                    continue
                for update in result.get("result", []):
                    offset = update["update_id"] + 1
                    self.process_update(update)
            except (requests.RequestException, ValueError):
                # Exception representations may contain the secret URL/token.
                logger.warning("Telegram polling network or JSON error")
                time.sleep(5)
            except KeyboardInterrupt:
                self.stdout.write("Telegram bot stopped")
                break

    def process_update(self, update):
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") != "private":
            return
        chat_id = chat.get("id")
        command = (message.get("text") or "").split(maxsplit=1)
        if not command or command[0].split("@")[0] != "/start":
            return
        linked = len(command) == 2 and link_telegram_chat(command[1], chat_id)
        answer = (
            "✅ Telegram привязан! Вы будете получать напоминания."
            if linked else
            "Ссылка неверна или устарела. Получите новую в личном кабинете."
        )
        try:
            send_telegram_message(chat_id, answer)
        except TelegramAPIError:
            logger.warning("Failed to send linking confirmation")
