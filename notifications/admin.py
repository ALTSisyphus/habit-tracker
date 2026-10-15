from django.contrib import admin

from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("id", "habit", "scheduled_for", "status", "attempts")
    list_filter = ("status",)
    readonly_fields = ("habit", "chat_id", "text", "scheduled_for", "sent_at")
