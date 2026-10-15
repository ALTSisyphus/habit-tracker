"""Request serializers for user registration."""
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from rest_framework import serializers


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email", "password")
        read_only_fields = ("id",)

    def validate(self, attrs):
        user = get_user_model()(
            username=attrs.get("username", ""), email=attrs.get("email", "")
        )
        try:
            password_validation.validate_password(attrs["password"], user=user)
        except ValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data)
