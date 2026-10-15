from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path(
        "token/",
        extend_schema(tags=["Authentication"])(TokenObtainPairView).as_view(),
        name="token_obtain_pair",
    ),
    path(
        "token/refresh/",
        extend_schema(tags=["Authentication"])(TokenRefreshView).as_view(),
        name="token_refresh",
    ),
]
