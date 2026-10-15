"""Habit model and database-independent business rules."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Habit(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="habits"
    )
    place = models.CharField(max_length=255)
    time = models.TimeField()
    action = models.CharField(max_length=255)
    is_pleasant = models.BooleanField(default=False)
    related_habit = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reward_for",
    )
    periodicity = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(7)]
    )
    reward = models.CharField(max_length=255, blank=True, default="")
    duration = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(120)]
    )
    is_public = models.BooleanField(default=False)
    next_reminder_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(periodicity__gte=1, periodicity__lte=7),
                name="habit_periodicity_1_7",
            ),
            models.CheckConstraint(
                condition=models.Q(duration__gte=1, duration__lte=120),
                name="habit_duration_1_120",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.reward and self.related_habit_id:
            errors["reward"] = "Выберите вознаграждение ИЛИ связанную привычку."
        if self.is_pleasant and (self.reward or self.related_habit_id):
            errors["is_pleasant"] = "У приятной привычки нет вознаграждения."
        if self.related_habit_id:
            if self.pk and self.pk == self.related_habit_id:
                errors["related_habit"] = "Привычку нельзя связать с собой."
            else:
                related = self.related_habit
                if not related.is_pleasant:
                    errors["related_habit"] = "Связанная привычка должна быть приятной."
                elif self.owner_id and related.owner_id != self.owner_id:
                    errors["related_habit"] = "Можно связывать только свои привычки."
        if self.pk and not self.is_pleasant:
            if Habit.objects.filter(related_habit_id=self.pk).exists():
                errors["is_pleasant"] = (
                    "Сначала удалите ссылки на эту приятную привычку."
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.owner_id}: {self.action} ({self.time})"
