import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("habits", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Reminder",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("scheduled_for", models.DateTimeField()),
                ("chat_id", models.BigIntegerField()),
                ("text", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Ожидает"), ("processing", "Отправляется"), ("sent", "Отправлено"), ("failed", "Не удалось"), ("canceled", "Отменено")], default="pending", max_length=12)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, default="", max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("habit", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reminders", to="habits.habit")),
            ],
            options={"ordering": ("-scheduled_for", "-id")},
        ),
        migrations.AddConstraint(
            model_name="reminder",
            constraint=models.UniqueConstraint(fields=("habit", "scheduled_for"), name="unique_habit_reminder"),
        ),
        migrations.AddIndex(
            model_name="reminder",
            index=models.Index(fields=["status", "updated_at"], name="notificatio_status_c27771_idx"),
        ),
    ]
