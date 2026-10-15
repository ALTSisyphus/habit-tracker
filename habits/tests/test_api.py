"""HTTP API, pagination and object-level privacy."""
import pytest
from rest_framework.test import APIClient

from habits.models import Habit


@pytest.mark.django_db
def test_create_habit_sets_owner_and_schedule(api_client, user, other_user, habit_data):
    response = api_client.post(
        "/api/habits/", {**habit_data, "owner": other_user.pk}, format="json"
    )
    assert response.status_code == 201, response.data
    record = Habit.objects.get(pk=response.data["id"])
    assert record.owner_id == user.pk
    assert record.next_reminder_at is not None
    assert response.data["periodicity"] == 1


@pytest.mark.django_db
def test_private_crud_and_partial_update(api_client, habit_data):
    create = api_client.post("/api/habits/", habit_data, format="json")
    pk = create.data["id"]
    assert api_client.get(f"/api/habits/{pk}/").status_code == 200
    patch = api_client.patch(
        f"/api/habits/{pk}/", {"action": "Новая привычка"}, format="json"
    )
    assert patch.status_code == 200
    assert patch.data["action"] == "Новая привычка"
    put = api_client.put(
        f"/api/habits/{pk}/", {**habit_data, "place": "Парк"}, format="json"
    )
    assert put.status_code == 200
    assert put.data["place"] == "Парк"
    assert api_client.delete(f"/api/habits/{pk}/").status_code == 204
    assert api_client.get(f"/api/habits/{pk}/").status_code == 404


@pytest.mark.django_db
def test_owner_cannot_view_patch_or_delete_others_habit(
    api_client, other_user, habit_data
):
    record = Habit.objects.create(
        owner=other_user, place="Дом", time="08:00", action="Скрытая",
        duration=30, reward="Чай",
    )
    assert api_client.get(f"/api/habits/{record.pk}/").status_code == 404
    assert api_client.patch(
        f"/api/habits/{record.pk}/", {"action": "Взлом"}, format="json"
    ).status_code == 404
    assert api_client.delete(f"/api/habits/{record.pk}/").status_code == 404
    assert api_client.get("/api/habits/").data["count"] == 0
    assert Habit.objects.get(pk=record.pk).action == "Скрытая"


@pytest.mark.django_db
def test_limit_offset_pagination_five_per_page(api_client, user):
    for index in range(12):
        Habit.objects.create(
            owner=user, place="Дома", time="09:00", action=f"Привычка {index}",
            duration=30,
        )
    first = api_client.get("/api/habits/")
    second = api_client.get("/api/habits/?limit=5&offset=5")
    last = api_client.get("/api/habits/?limit=50&offset=10")
    assert first.status_code == second.status_code == last.status_code == 200
    assert first.data["count"] == 12
    assert len(first.data["results"]) == len(second.data["results"]) == 5
    assert len(last.data["results"]) == 2
    assert first.data["next"] and second.data["previous"]
    ids = {item["id"] for item in first.data["results"] + second.data["results"]}
    assert len(ids) == 10


@pytest.mark.django_db
def test_public_listing_can_be_read_anonymously_but_not_mutated(
    api_client, user, other_user
):
    public = Habit.objects.create(
        owner=other_user, place="Кухня", time="07:00", action="Публичная",
        duration=50, is_public=True,
    )
    Habit.objects.create(
        owner=other_user, place="Дом", time="09:00", action="Секретная",
        duration=50, is_public=False,
    )
    public_list = APIClient().get("/api/public-habits/")
    assert public_list.status_code == 200
    assert public_list.data["count"] == 1
    assert public_list.data["results"][0]["id"] == public.pk
    assert "next_reminder_at" not in public_list.data["results"][0]
    assert APIClient().post("/api/public-habits/", {}, format="json").status_code == 405
    assert api_client.delete(f"/api/habits/{public.pk}/").status_code == 404


@pytest.mark.django_db
def test_public_listing_is_paginated(user):
    for i in range(7):
        Habit.objects.create(
            owner=user, place="Парк", time="10:00", action=f"Публичная {i}",
            duration=50, is_public=True,
        )
    response = APIClient().get("/api/public-habits/?offset=5")
    assert response.status_code == 200
    assert response.data["count"] == 7
    assert len(response.data["results"]) == 2


@pytest.mark.django_db
def test_anonymous_private_api_rejected(habit_data):
    client = APIClient()
    assert client.get("/api/habits/").status_code == 401
    assert client.post("/api/habits/", habit_data, format="json").status_code == 401


@pytest.mark.django_db
def test_docs_and_health_available():
    client = APIClient()
    assert client.get("/health/").json() == {"status": "ok"}
    assert client.get("/api/schema/").status_code == 200
    assert client.get("/api/docs/").status_code == 200
    assert client.get("/api/redoc/").status_code == 200

@pytest.mark.django_db
def test_owner_cannot_be_reassigned_via_patch(api_client, user, other_user, habit_data):
    pk = api_client.post("/api/habits/", habit_data, format="json").data["id"]
    result = api_client.patch(
        f"/api/habits/{pk}/", {"owner": other_user.username}, format="json"
    )
    assert result.status_code == 200
    assert Habit.objects.get(pk=pk).owner_id == user.pk


@pytest.mark.django_db
def test_cors_accepts_allowed_origin_but_not_unknown_origin():
    from django.test import override_settings

    client = APIClient()
    with override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:5173"]):
        allowed = client.options(
            "/api/habits/", HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        unknown = client.options(
            "/api/habits/", HTTP_ORIGIN="https://untrusted.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
    assert allowed.status_code == 200
    assert allowed["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in unknown
