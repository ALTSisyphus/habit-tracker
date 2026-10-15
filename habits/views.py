"""Private CRUD and public read-only habits."""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, viewsets

from .models import Habit
from .serializers import HabitSerializer, PublicHabitSerializer


@extend_schema_view(
    list=extend_schema(tags=["Habits"], summary="Мои привычки (5 на страницу)"),
    retrieve=extend_schema(tags=["Habits"], summary="Просмотр своей привычки"),
    create=extend_schema(tags=["Habits"], summary="Создать привычку"),
    update=extend_schema(tags=["Habits"], summary="Изменить привычку"),
    partial_update=extend_schema(tags=["Habits"], summary="Изменить часть полей"),
    destroy=extend_schema(tags=["Habits"], summary="Удалить привычку"),
)
class HabitViewSet(viewsets.ModelViewSet):
    queryset = Habit.objects.none()
    serializer_class = HabitSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Habit.objects.none()
        return Habit.objects.filter(owner=self.request.user).select_related(
            "owner", "related_habit"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(tags=["Habits"], summary="Список публичных привычек")
class PublicHabitListView(generics.ListAPIView):
    queryset = Habit.objects.filter(is_public=True).select_related("owner")
    serializer_class = PublicHabitSerializer
    permission_classes = [permissions.AllowAny]
