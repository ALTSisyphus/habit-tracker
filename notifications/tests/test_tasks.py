"""Schedule calculation, durable Celery queue and Telegram error handling."""
from datetime import datetime, time, timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from habits.models import Habit
from habits.scheduling import next_occurrence
from notifications.models import Reminder
from notifications.tasks import (
    check_due_habits,
    dispatch_pending_reminders,
    reminder_text,
    send_telegram_reminder,
)
from notifications.telegram import TelegramAPIError, send_telegram_message


@pytest.fixture
def habit(user):
    return Habit.objects.create(
        owner=user, place="Парк", time=time(8, 0), action="Прогулка",
        duration=120, periodicity=1,
    )


@pytest.mark.django_db
def test_recurrence_and_pleasant_habits(habit):
    reference = timezone.make_aware(datetime(2026, 10, 14, 8, 0))
    assert next_occurrence(habit, after=reference).date().isoformat() == "2026-10-15"
    habit.periodicity = 7
    previous = timezone.make_aware(datetime(2026, 10, 14, 8, 0))
    assert next_occurrence(
        habit, after=previous, previous=previous
    ).date().isoformat() == "2026-10-21"
    habit.is_pleasant = True
    assert next_occurrence(habit) is None


@pytest.mark.django_db(transaction=True)
def test_due_habit_creates_one_reminder_and_advances_schedule(habit, user):
    user.telegram_chat_id = 1234567
    user.save(update_fields=["telegram_chat_id"])
    habit.next_reminder_at = timezone.now() - timedelta(minutes=1)
    habit.save(update_fields=["next_reminder_at"])
    with patch("notifications.tasks.dispatch_pending_reminders.delay") as dispatch:
        assert check_due_habits() == 1
        assert check_due_habits() == 0
        dispatch.assert_called_once()
    assert Reminder.objects.count() == 1
    assert Reminder.objects.first().text == reminder_text(habit)
    habit.refresh_from_db()
    assert habit.next_reminder_at > timezone.now()


@pytest.mark.django_db
def test_due_habit_without_chat_advances_but_does_not_send(habit):
    habit.next_reminder_at = timezone.now() - timedelta(hours=1)
    habit.save(update_fields=["next_reminder_at"])
    assert check_due_habits() == 0
    assert Reminder.objects.count() == 0
    habit.refresh_from_db()
    assert habit.next_reminder_at > timezone.now()


@pytest.mark.django_db
def test_pleasant_habit_is_skipped_even_if_due(habit):
    habit.is_pleasant = True
    habit.next_reminder_at = timezone.now() - timedelta(minutes=1)
    habit.save(update_fields=["is_pleasant", "next_reminder_at"])
    assert check_due_habits() == 0


@pytest.mark.django_db
def test_dispatch_resubmits_pending_and_recovers_stale_claim(habit):
    past = timezone.now() - timedelta(minutes=8)
    pending = Reminder.objects.create(
        habit=habit, chat_id=111, scheduled_for=past, text="hello"
    )
    processing = Reminder.objects.create(
        habit=habit, chat_id=111, scheduled_for=past - timedelta(days=1),
        text="retry", status=Reminder.PROCESSING,
    )
    Reminder.objects.filter(pk=processing.pk).update(updated_at=past)
    with patch("notifications.tasks.send_telegram_reminder.delay") as send:
        assert dispatch_pending_reminders() == 2
        assert send.call_count == 2
        assert {c.args[0] for c in send.call_args_list} == {pending.pk, processing.pk}
    processing.refresh_from_db()
    assert processing.status == Reminder.PENDING


@pytest.mark.django_db
def test_successful_delivery_claims_only_once(habit, user):
    user.telegram_chat_id = 777
    user.save(update_fields=["telegram_chat_id"])
    reminder = Reminder.objects.create(
        habit=habit, scheduled_for=timezone.now(), chat_id=777, text="Прогулка"
    )
    with patch("notifications.tasks.send_telegram_message") as send:
        assert send_telegram_reminder(reminder.id) is True
        assert send_telegram_reminder(reminder.id) is False
        send.assert_called_once_with(777, "Прогулка")
    reminder.refresh_from_db()
    assert reminder.status == Reminder.SENT
    assert reminder.attempts == 1
    assert reminder.sent_at is not None


@pytest.mark.django_db
def test_delivery_retries_then_marks_failed(habit, user):
    user.telegram_chat_id = 777
    user.save(update_fields=["telegram_chat_id"])
    reminder = Reminder.objects.create(
        habit=habit, scheduled_for=timezone.now(), chat_id=777, text="Прогулка"
    )
    with patch(
        "notifications.tasks.send_telegram_message",
        side_effect=TelegramAPIError("Blocked by user"),
    ):
        for attempt in range(1, 4):
            assert send_telegram_reminder(reminder.id) is False
            reminder.refresh_from_db()
            assert reminder.attempts == attempt
    assert reminder.status == Reminder.FAILED
    assert "Blocked" in reminder.last_error


@pytest.mark.django_db
def test_canceled_message_not_delivered(habit):
    reminder = Reminder.objects.create(
        habit=habit, scheduled_for=timezone.now(), chat_id=777,
        text="old", status=Reminder.CANCELED,
    )
    with patch("notifications.tasks.send_telegram_message") as send:
        assert not send_telegram_reminder(reminder.pk)
        send.assert_not_called()


def test_telegram_http_success(settings):
    settings.TELEGRAM_BOT_TOKEN = "valid-test-token"
    response = Mock(status_code=200)
    response.json.return_value = {"ok": True, "result": {"message_id": 1}}
    with patch("notifications.telegram.requests.post", return_value=response) as post:
        assert send_telegram_message(12, "Test")["ok"]
        assert post.call_args.kwargs["timeout"] == 15


def test_telegram_http_api_failure(settings):
    settings.TELEGRAM_BOT_TOKEN = "valid-test-token"
    response = Mock(status_code=400)
    response.json.return_value = {"ok": False, "description": "Bad Request"}
    with patch("notifications.telegram.requests.post", return_value=response):
        with pytest.raises(TelegramAPIError, match="Bad Request"):
            send_telegram_message(12, "Test")


def test_telegram_json_failure(settings):
    settings.TELEGRAM_BOT_TOKEN = "valid-test-token"
    response = Mock(status_code=500)
    response.json.side_effect = ValueError("bad JSON")
    with patch("notifications.telegram.requests.post", return_value=response):
        with pytest.raises(TelegramAPIError, match="Сетевая ошибка"):
            send_telegram_message(12, "Test")


def test_telegram_missing_token(settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    with pytest.raises(TelegramAPIError, match="не настроен"):
        send_telegram_message(12, "Test")

@pytest.mark.django_db
def test_pending_message_to_old_telegram_account_is_canceled(habit, user):
    user.telegram_chat_id = 991
    user.save(update_fields=["telegram_chat_id"])
    reminder = Reminder.objects.create(
        habit=habit, scheduled_for=timezone.now(), chat_id=777, text="Old chat"
    )
    with patch("notifications.tasks.send_telegram_message") as send:
        assert send_telegram_reminder(reminder.pk) is False
        send.assert_not_called()
    reminder.refresh_from_db()
    assert reminder.status == Reminder.CANCELED


@pytest.mark.parametrize('payload', [None, [], 'unexpected'])
def test_malformed_telegram_response_is_recoverable(settings, payload):
    settings.TELEGRAM_BOT_TOKEN = 'synthetic-test-token'
    response = Mock(status_code=200)
    response.json.return_value = payload
    with patch('notifications.telegram.requests.post', return_value=response):
        with pytest.raises(TelegramAPIError, match='Некорректный ответ'):
            send_telegram_message(12, 'Test')


def test_telegram_error_redacts_token(settings):
    settings.TELEGRAM_BOT_TOKEN = 'synthetic-test-token'
    response = Mock(status_code=400)
    response.json.return_value = {
        'ok': False, 'description': 'URL /botsynthetic-test-token/sendMessage',
    }
    with patch('notifications.telegram.requests.post', return_value=response):
        with pytest.raises(TelegramAPIError) as error:
            send_telegram_message(12, 'Test')
    assert settings.TELEGRAM_BOT_TOKEN not in str(error.value)


def test_network_failure_does_not_expose_secret(settings):
    import requests

    settings.TELEGRAM_BOT_TOKEN = 'synthetic-test-token'
    with patch('notifications.telegram.requests.post', side_effect=requests.Timeout(
        'https://api.telegram.org/botsynthetic-test-token/sendMessage'
    )):
        with pytest.raises(TelegramAPIError) as error:
            send_telegram_message(12, 'Test')
    assert settings.TELEGRAM_BOT_TOKEN not in str(error.value)


@pytest.mark.django_db
def test_crashed_delivery_cannot_retry_forever(habit):
    reminder = Reminder.objects.create(
        habit=habit, scheduled_for=timezone.now(), chat_id=123, text='Test',
        status=Reminder.PROCESSING, attempts=3,
    )
    Reminder.objects.filter(pk=reminder.pk).update(
        updated_at=timezone.now() - timedelta(minutes=6)
    )
    with patch('notifications.tasks.send_telegram_reminder.delay') as send:
        assert dispatch_pending_reminders() == 0
        send.assert_not_called()
    reminder.refresh_from_db()
    assert reminder.status == Reminder.FAILED


@pytest.mark.django_db
def test_pending_exhausted_delivery_not_sent(habit):
    reminder = Reminder.objects.create(
        habit=habit, scheduled_for=timezone.now(), chat_id=123, text='Test', attempts=3,
    )
    with patch('notifications.tasks.send_telegram_message') as send:
        assert not send_telegram_reminder(reminder.pk)
        send.assert_not_called()
    reminder.refresh_from_db()
    assert reminder.status == Reminder.FAILED


@pytest.mark.django_db(transaction=True)
def test_broker_failure_preserves_outbox(habit, user):
    from kombu.exceptions import OperationalError

    user.telegram_chat_id = 123
    user.save(update_fields=['telegram_chat_id'])
    habit.next_reminder_at = timezone.now() - timedelta(minutes=1)
    habit.save(update_fields=['next_reminder_at'])
    with patch('notifications.tasks.dispatch_pending_reminders.delay',
               side_effect=OperationalError('offline')):
        with pytest.raises(OperationalError):
            check_due_habits()
    assert Reminder.objects.filter(status=Reminder.PENDING).count() == 1
    with patch('notifications.tasks.send_telegram_reminder.delay') as send:
        assert dispatch_pending_reminders() == 1
        send.assert_called_once()


@pytest.mark.django_db
def test_delayed_scheduler_preserves_seven_day_cadence(habit):
    habit.periodicity = 7
    previous = timezone.make_aware(datetime(2026, 10, 1, 8))
    now = timezone.make_aware(datetime(2026, 10, 20, 12))
    assert next_occurrence(habit, after=now, previous=previous) == (
        timezone.make_aware(datetime(2026, 10, 22, 8))
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_delivery_postgresql(habit, user):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connection, connections

    if connection.vendor != 'postgresql':
        pytest.skip('Requires PostgreSQL row locks; configured for CI')
    user.telegram_chat_id = 777
    user.save(update_fields=['telegram_chat_id'])
    reminder = Reminder.objects.create(
        habit=habit, scheduled_for=timezone.now(), chat_id=777, text='Concurrent',
    )

    def deliver():
        try:
            return send_telegram_reminder(reminder.pk)
        finally:
            connections.close_all()

    with patch('notifications.tasks.send_telegram_message') as send:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: deliver(), range(2)))
        assert sorted(results) == [False, True]
        send.assert_called_once()
