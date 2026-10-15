"""Private Telegram linking, code expiry, and bot commands."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.management.commands.run_telegram_bot import Command
from notifications.services import create_link_code, link_telegram_chat
from users.models import TelegramLinkCode


@pytest.mark.django_db
def test_link_endpoint_requires_authorization_and_returns_deep_link(client_auth):
    assert APIClient().post("/api/telegram/link/").status_code == 401
    response = client_auth.post("/api/telegram/link/", {}, format="json")
    assert response.status_code == 201
    assert response.data["deep_link"].startswith("https://t.me/test_habit_bot?start=")
    assert "expires_at" in response.data


@pytest.mark.django_db
def test_link_code_is_one_time_and_updates_user(user):
    link = create_link_code(user)
    assert link_telegram_chat(link.code, 999123)
    user.refresh_from_db()
    assert user.telegram_chat_id == 999123
    assert not TelegramLinkCode.objects.filter(code=link.code).exists()
    assert not link_telegram_chat(link.code, 999123)


@pytest.mark.django_db
def test_old_code_is_revoked_when_new_link_created(user):
    old = create_link_code(user)
    new = create_link_code(user)
    assert old.code != new.code
    assert not link_telegram_chat(old.code, 777)
    assert link_telegram_chat(new.code, 777)


@pytest.mark.django_db
def test_expired_code_is_rejected(user):
    link = create_link_code(user)
    TelegramLinkCode.objects.filter(pk=link.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    assert not link_telegram_chat(link.code, 321)


@pytest.mark.django_db
def test_one_chat_cannot_be_linked_to_two_users(user):
    other = get_user_model().objects.create_user(
        username="another", password="UniquePass123!", telegram_chat_id=1234
    )
    link = create_link_code(user)
    assert not link_telegram_chat(link.code, other.telegram_chat_id)
    user.refresh_from_db()
    assert user.telegram_chat_id is None


@pytest.mark.django_db
def test_link_api_is_unavailable_without_bot_username(client_auth):
    with override_settings(TELEGRAM_BOT_USERNAME=""):
        assert client_auth.post("/api/telegram/link/").status_code == 503


@pytest.mark.django_db
def test_bot_start_consumes_code_and_confirms(user):
    link = create_link_code(user)
    update = {
        "message": {
            "chat": {"type": "private", "id": 555},
            "text": f"/start {link.code}",
        }
    }
    with patch(
        "notifications.management.commands.run_telegram_bot.send_telegram_message"
    ) as send:
        Command().process_update(update)
    user.refresh_from_db()
    assert user.telegram_chat_id == 555
    assert "✅" in send.call_args.args[1]


@pytest.mark.django_db
def test_bot_ignores_groups_and_other_commands():
    with patch(
        "notifications.management.commands.run_telegram_bot.send_telegram_message"
    ) as send:
        Command().process_update(
            {"message": {"chat": {"type": "group", "id": 4}, "text": "/start"}}
        )
        Command().process_update(
            {"message": {"chat": {"type": "private", "id": 4}, "text": "/help"}}
        )
    send.assert_not_called()


@pytest.mark.django_db
def test_bot_rejects_invalid_link():
    with patch(
        "notifications.management.commands.run_telegram_bot.send_telegram_message"
    ) as send:
        Command().process_update(
            {"message": {"chat": {"type": "private", "id": 77}, "text": "/start bad"}}
        )
    assert "устарела" in send.call_args.args[1]

@pytest.mark.django_db
def test_bot_polling_processes_update_and_stops_on_interrupt():
    from unittest.mock import Mock

    from django.core.management import call_command

    response = Mock(status_code=200)
    response.json.return_value = {
        "ok": True,
        "result": [{"update_id": 12, "message": {"text": "/start"}}],
    }
    with (
        patch(
            "notifications.management.commands.run_telegram_bot.requests.get",
            side_effect=[response, KeyboardInterrupt()],
        ),
        patch.object(Command, "process_update") as process,
    ):
        call_command("run_telegram_bot")
    process.assert_called_once()


@pytest.mark.django_db
def test_bot_polling_handles_network_error_and_recovers():
    from django.core.management import call_command
    from requests import Timeout

    with (
        patch(
            "notifications.management.commands.run_telegram_bot.requests.get",
            side_effect=[Timeout("test timeout"), KeyboardInterrupt()],
        ),
        patch("notifications.management.commands.run_telegram_bot.time.sleep"),
    ):
        call_command("run_telegram_bot")


@pytest.mark.django_db
def test_bot_start_confirmation_failure_does_not_crash(user):
    from notifications.telegram import TelegramAPIError

    link = create_link_code(user)
    with patch(
        "notifications.management.commands.run_telegram_bot.send_telegram_message",
        side_effect=TelegramAPIError("offline"),
    ):
        Command().process_update({
            "message": {
                "chat": {"type": "private", "id": 555},
                "text": f"/start {link.code}",
            }
        })
    user.refresh_from_db()
    assert user.telegram_chat_id == 555


def test_bot_cannot_start_without_valid_token():
    from django.core.management import call_command
    from django.core.management.base import CommandError

    with override_settings(TELEGRAM_BOT_TOKEN=""):
        with pytest.raises(CommandError):
            call_command("run_telegram_bot")
