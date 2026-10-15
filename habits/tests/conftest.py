import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="anna", password="StrongPass123!"
    )


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(
        username="boris", password="StrongPass123!"
    )


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def habit_data():
    return {
        "place": "Дом",
        "time": "08:00:00",
        "action": "Прочитать две страницы",
        "duration": 110,
        "periodicity": 1,
        "reward": "Чашка чая",
        "is_public": False,
    }
