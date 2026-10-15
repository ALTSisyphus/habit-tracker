"""Habit API serialization and cross-field validation."""
from django.db import transaction
from rest_framework import serializers

from notifications.models import Reminder

from .models import Habit
from .scheduling import next_occurrence


class HabitSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Habit
        fields = (
            "id", "owner", "place", "time", "action", "is_pleasant",
            "related_habit", "periodicity", "reward", "duration",
            "is_public", "next_reminder_at", "created_at",
        )
        read_only_fields = ("id", "owner", "next_reminder_at", "created_at")

    def validate_duration(self, value):
        if not 1 <= value <= 120:
            raise serializers.ValidationError("Длительность от 1 до 120 секунд.")
        return value

    def validate_periodicity(self, value):
        if not 1 <= value <= 7:
            raise serializers.ValidationError("Периодичность от 1 до 7 дней.")
        return value

    def validate(self, attrs):
        instance = self.instance
        pleasant = attrs.get(
            "is_pleasant", instance.is_pleasant if instance else False
        )
        reward = attrs.get("reward", instance.reward if instance else "")
        related = attrs.get(
            "related_habit", instance.related_habit if instance else None
        )
        user = self.context["request"].user
        errors = {}
        if reward and related:
            errors["reward"] = "Нельзя совместить награду и связанную привычку."
        if pleasant and (reward or related):
            errors["is_pleasant"] = "У приятной привычки не бывает награды."
        if related:
            if instance and related.pk == instance.pk:
                errors["related_habit"] = "Нельзя привязать привычку к самой себе."
            elif related.owner_id != user.pk:
                errors["related_habit"] = "Выберите собственную приятную привычку."
            elif not related.is_pleasant:
                errors["related_habit"] = "Связанная привычка должна быть приятной."
        if instance and not pleasant and instance.reward_for.exists():
            errors["is_pleasant"] = "На эту привычку уже ссылаются другие."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        habit = Habit(**validated_data)
        habit.next_reminder_at = next_occurrence(habit)
        habit.full_clean()
        habit.save()
        return habit

    @transaction.atomic
    def update(self, instance, validated_data):
        must_reschedule = any(
            key in validated_data and getattr(instance, key) != validated_data[key]
            for key in ("time", "periodicity", "is_pleasant")
        )
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if must_reschedule:
            instance.next_reminder_at = next_occurrence(instance)
            Reminder.objects.filter(habit=instance, status=Reminder.PENDING).update(
                status=Reminder.CANCELED
            )
        instance.full_clean()
        instance.save()
        return instance


class PublicHabitSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Habit
        fields = (
            "id", "owner", "place", "time", "action", "is_pleasant",
            "periodicity", "reward", "duration", "is_public",
        )
        read_only_fields = fields
