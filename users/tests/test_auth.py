"""Registration and JWT authentication contracts."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_registration_hashes_password_and_returns_user_id():
    client = APIClient()
    response = client.post(
        "/api/auth/register/",
        {"username": "alice", "email": "a@example.org", "password": "UniqueS3cret!"},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["username"] == "alice"
    assert "password" not in response.data
    assert get_user_model().objects.get(username="alice").check_password(
        "UniqueS3cret!"
    )


@pytest.mark.django_db
def test_registration_rejects_weak_password_and_duplicate_username():
    client = APIClient()
    client.post(
        "/api/auth/register/",
        {"username": "alice", "password": "UniqueS3cret!"},
        format="json",
    )
    weak = client.post(
        "/api/auth/register/", {"username": "bob", "password": "123"},
        format="json",
    )
    duplicate = client.post(
        "/api/auth/register/",
        {"username": "alice", "password": "UniqueS3cret!"},
        format="json",
    )
    assert weak.status_code == 400
    assert duplicate.status_code == 400


@pytest.mark.django_db
def test_jwt_issue_refresh_and_authentication():
    get_user_model().objects.create_user(username="alice", password="UniqueS3cret!")
    client = APIClient()
    tokens = client.post(
        "/api/auth/token/", {"username": "alice", "password": "UniqueS3cret!"},
        format="json",
    )
    assert tokens.status_code == 200
    assert tokens.data["access"] and tokens.data["refresh"]
    refresh = client.post(
        "/api/auth/token/refresh/", {"refresh": tokens.data["refresh"]},
        format="json",
    )
    assert refresh.status_code == 200
    client.credentials(HTTP_AUTHORIZATION="Bearer " + tokens.data["access"])
    assert client.get("/api/habits/").status_code == 200
    client.credentials()
    assert client.get("/api/habits/").status_code == 401


@pytest.mark.django_db
def test_invalid_login_credentials():
    result = APIClient().post(
        "/api/auth/token/", {"username": "missing", "password": "wrong"},
        format="json",
    )
    assert result.status_code == 401


@pytest.mark.django_db
def test_registration_rejects_password_similar_to_username():
    response = APIClient().post(
        '/api/auth/register/',
        {'username': 'UnusualLongUsername', 'password': 'UnusualLongUsername!'},
        format='json',
    )
    assert response.status_code == 400
    assert 'password' in response.data
