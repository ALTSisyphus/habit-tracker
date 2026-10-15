"""Authenticated endpoint returning a single-use Telegram deep link."""
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, views
from rest_framework.response import Response

from .serializers import TelegramLinkResponseSerializer
from .services import bot_link, create_link_code


class TelegramLinkView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=None,
        responses={201: TelegramLinkResponseSerializer},
        tags=["Telegram"],
        summary="Получить ссылку для привязки Telegram",
    )
    def post(self, request):
        if not settings.TELEGRAM_BOT_USERNAME:
            return Response(
                {"detail": "TELEGRAM_BOT_USERNAME не настроен."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        link = create_link_code(request.user)
        return Response(
            {"deep_link": bot_link(link.code), "expires_at": link.expires_at},
            status=status.HTTP_201_CREATED,
        )
