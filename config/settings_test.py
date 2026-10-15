"""Isolated SQLite settings for fast and repeatable CI tests."""
import os

os.environ["READ_DOT_ENV"] = "False"
os.environ["PRODUCTION"] = "False"
os.environ.setdefault("SECRET_KEY", "only-for-automated-tests-with-at-least-32-bytes")

from .settings import *  # noqa: E402, F403, F401

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
if os.environ.get("TEST_DATABASE_URL"):
    DATABASES = {"default": env.db("TEST_DATABASE_URL")}  # noqa: F405
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
TELEGRAM_BOT_TOKEN = "fake-token-for-tests"
TELEGRAM_BOT_USERNAME = "test_habit_bot"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
WHITENOISE_AUTOREFRESH = True
