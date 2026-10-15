import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Habit",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("place", models.CharField(max_length=255)),
                ("time", models.TimeField()),
                ("action", models.CharField(max_length=255)),
                ("is_pleasant", models.BooleanField(default=False)),
                ("periodicity", models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(7)])),
                ("reward", models.CharField(blank=True, default="", max_length=255)),
                ("duration", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(120)])),
                ("is_public", models.BooleanField(default=False)),
                ("next_reminder_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="habits", to=settings.AUTH_USER_MODEL)),
                ("related_habit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reward_for", to="habits.habit")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddConstraint(
            model_name="habit",
            constraint=models.CheckConstraint(condition=models.Q(periodicity__gte=1, periodicity__lte=7), name="habit_periodicity_1_7"),
        ),
        migrations.AddConstraint(
            model_name="habit",
            constraint=models.CheckConstraint(condition=models.Q(duration__gte=1, duration__lte=120), name="habit_duration_1_120"),
        ),
    ]
