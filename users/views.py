from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions

from .serializers import RegisterSerializer


@extend_schema(tags=["Authentication"], summary="Регистрация пользователя")
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
