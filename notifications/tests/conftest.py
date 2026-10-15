import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="messenger", password="UniquePass123!"
    )


@pytest.fixture
def client_auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client
