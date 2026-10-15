"""Compute stable reminder recurrence in the project's local time zone."""
from datetime import datetime, timedelta

from django.utils import timezone


def next_occurrence(habit, after=None, previous=None):
    """Return the next aware datetime strictly after `after`.

    On creation, use the closest future local clock time. After a scheduled
    occurrence, preserve the N-day cadence even if a worker starts late.
    """
    if habit.is_pleasant:
        return None
    after = after or timezone.now()
    tz = timezone.get_default_timezone()
    now_local = timezone.localtime(after, tz)
    if previous is None:
        date = now_local.date()
    else:
        date = timezone.localtime(previous, tz).date() + timedelta(
            days=habit.periodicity
        )
    candidate = datetime.combine(date, habit.time, tzinfo=tz)
    step = 1 if previous is None else habit.periodicity
    while candidate <= now_local:
        date += timedelta(days=step)
        candidate = datetime.combine(date, habit.time, tzinfo=tz)
    return candidate
