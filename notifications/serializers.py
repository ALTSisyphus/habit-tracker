from rest_framework import serializers


class TelegramLinkResponseSerializer(serializers.Serializer):
    deep_link = serializers.URLField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
