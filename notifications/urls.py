from django.urls import path

from .views import TelegramLinkView

urlpatterns = [
    path("link/", TelegramLinkView.as_view(), name="telegram-link"),
]
