"""Celery scheduler and durable delivery pipeline."""
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from habits.models import Habit
from habits.scheduling import next_occurrence

from .models import Reminder
from .telegram import TelegramAPIError, send_telegram_message

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def reminder_text(habit):
    return (
        "⏰ Напоминание о привычке!\n"
        f"Действие: {habit.action}\n"
        f"📍 Место: {habit.place}\n"
        f"🕒 Время: {habit.time.strftime('%H:%M')}\n"
        f"⏱ Длительность: {habit.duration} сек."
    )


@shared_task
def check_due_habits():
    """Materialize due notifications and advance each habit's cadence.

    The database row lock prevents two concurrent schedulers from creating
    duplicate outbox records. The unique constraint is a second line of defense.
    """
    now = timezone.now()
    created = 0
    with transaction.atomic():
        habits = list(
            Habit.objects.select_for_update(skip_locked=True)
            .select_related("owner")
            .filter(is_pleasant=False, next_reminder_at__lte=now)
            .order_by("next_reminder_at", "id")[:200]
        )
        for habit in habits:
            scheduled_at = habit.next_reminder_at
            if habit.owner.telegram_chat_id is not None:
                _, was_created = Reminder.objects.get_or_create(
                    habit=habit,
                    scheduled_for=scheduled_at,
                    defaults={
                        "chat_id": habit.owner.telegram_chat_id,
                        "text": reminder_text(habit),
                    },
                )
                created += int(was_created)
            habit.next_reminder_at = next_occurrence(
                habit, after=now, previous=scheduled_at
            )
            habit.save(update_fields=["next_reminder_at"])
        if created:
            transaction.on_commit(lambda: dispatch_pending_reminders.delay())
    return created


@shared_task
def dispatch_pending_reminders():
    """Requeue unsent messages, also recovering interrupted worker claims."""
    expired = timezone.now() - timedelta(minutes=5)
    Reminder.objects.filter(
        status=Reminder.PROCESSING, updated_at__lt=expired
    ).update(status=Reminder.PENDING)
    Reminder.objects.filter(
        status=Reminder.PENDING, attempts__gte=MAX_ATTEMPTS
    ).update(status=Reminder.FAILED, updated_at=timezone.now())
    ids = list(
        Reminder.objects.filter(status=Reminder.PENDING)
        .order_by("scheduled_for", "id")
        .values_list("id", flat=True)[:100]
    )
    for reminder_id in ids:
        send_telegram_reminder.delay(reminder_id)
    return len(ids)


@shared_task
def send_telegram_reminder(reminder_id):
    """Claim a record atomically before sending; retries happen on next scan."""
    with transaction.atomic():
        reminder = (
            Reminder.objects.select_for_update()
            .filter(pk=reminder_id, status=Reminder.PENDING)
            .first()
        )
        if reminder is None:
            return False
        if reminder.attempts >= MAX_ATTEMPTS:
            reminder.status = Reminder.FAILED
            reminder.save(update_fields=["status", "updated_at"])
            return False
        # A user may have re-linked a different Telegram account since queueing.
        if reminder.habit.owner.telegram_chat_id != reminder.chat_id:
            reminder.status = Reminder.CANCELED
            reminder.save(update_fields=["status", "updated_at"])
            return False
        reminder.status = Reminder.PROCESSING
        reminder.attempts += 1
        reminder.save(update_fields=["status", "attempts", "updated_at"])
    try:
        send_telegram_message(reminder.chat_id, reminder.text)
    except TelegramAPIError as exc:
        logger.warning("Reminder %s failed: %s", reminder_id, str(exc))
        Reminder.objects.filter(pk=reminder_id, status=Reminder.PROCESSING).update(
            status=(
                Reminder.FAILED
                if reminder.attempts >= MAX_ATTEMPTS
                else Reminder.PENDING
            ),
            last_error=str(exc)[:255],
            updated_at=timezone.now(),
        )
        return False
    Reminder.objects.filter(pk=reminder_id, status=Reminder.PROCESSING).update(
        status=Reminder.SENT,
        sent_at=timezone.now(),
        last_error="",
        updated_at=timezone.now(),
    )
    return True
