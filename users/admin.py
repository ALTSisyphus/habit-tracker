from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import TelegramLinkCode, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Telegram", {"fields": ("telegram_chat_id",)}),
    )


@admin.register(TelegramLinkCode)
class TelegramLinkCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at")
    readonly_fields = ("user", "code", "created_at", "expires_at")
