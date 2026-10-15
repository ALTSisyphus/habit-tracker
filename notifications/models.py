"""Durable reminder outbox to avoid losing notifications on broker errors."""
from django.db import models


class Reminder(models.Model):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELED = "canceled"
    STATUSES = [
        (PENDING, "Ожидает"),
        (PROCESSING, "Отправляется"),
        (SENT, "Отправлено"),
        (FAILED, "Не удалось"),
        (CANCELED, "Отменено"),
    ]

    habit = models.ForeignKey(
        "habits.Habit", on_delete=models.CASCADE, related_name="reminders"
    )
    scheduled_for = models.DateTimeField()
    chat_id = models.BigIntegerField()
    text = models.TextField()
    status = models.CharField(max_length=12, choices=STATUSES, default=PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-scheduled_for", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("habit", "scheduled_for"), name="unique_habit_reminder"
            ),
        ]
        indexes = [models.Index(
            fields=("status", "updated_at"),
            name="notificatio_status_c27771_idx",
        )]

    def __str__(self):
        return f"Reminder #{self.pk} ({self.status})"
