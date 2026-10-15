"""All mandatory business validation cases, including PATCH bypasses."""
import pytest
from django.core.exceptions import ValidationError

from habits.models import Habit


@pytest.mark.django_db
def test_cannot_choose_related_habit_and_reward(api_client, habit_data):
    pleasant = api_client.post(
        "/api/habits/", {**habit_data, "reward": "", "is_pleasant": True},
        format="json",
    ).data["id"]
    response = api_client.post(
        "/api/habits/", {**habit_data, "related_habit": pleasant}, format="json"
    )
    assert response.status_code == 400
    assert "reward" in response.data


@pytest.mark.django_db
@pytest.mark.parametrize("duration", [0, 121, -1])
def test_invalid_duration(api_client, habit_data, duration):
    response = api_client.post(
        "/api/habits/", {**habit_data, "duration": duration}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("periodicity", [0, 8, -1])
def test_invalid_periodicity(api_client, habit_data, periodicity):
    response = api_client.post(
        "/api/habits/", {**habit_data, "periodicity": periodicity}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_related_habit_must_be_pleasant(api_client, habit_data):
    useful = api_client.post("/api/habits/", habit_data, format="json").data["id"]
    response = api_client.post(
        "/api/habits/",
        {**habit_data, "reward": "", "related_habit": useful},
        format="json",
    )
    assert response.status_code == 400
    assert "related_habit" in response.data


@pytest.mark.django_db
def test_cannot_link_someone_elses_pleasant_habit(
    api_client, other_user, habit_data
):
    other_pleasant = Habit.objects.create(
        owner=other_user, place="Дом", time="10:00", action="Ванна",
        duration=40, is_pleasant=True,
    )
    response = api_client.post(
        "/api/habits/",
        {**habit_data, "reward": "", "related_habit": other_pleasant.pk},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_pleasant_habit_cannot_have_reward_or_related(api_client, habit_data):
    pleasant = api_client.post(
        "/api/habits/", {**habit_data, "reward": "", "is_pleasant": True},
        format="json",
    )
    assert pleasant.status_code == 201
    assert pleasant.data["next_reminder_at"] is None
    response = api_client.post(
        "/api/habits/", {**habit_data, "is_pleasant": True}, format="json"
    )
    assert response.status_code == 400
    response = api_client.patch(
        f"/api/habits/{pleasant.data['id']}/",
        {"related_habit": pleasant.data["id"]}, format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_partial_update_detects_conflict_with_existing_reward(
    api_client, habit_data
):
    pleasant = api_client.post(
        "/api/habits/", {**habit_data, "reward": "", "is_pleasant": True},
        format="json",
    ).data["id"]
    useful = api_client.post("/api/habits/", habit_data, format="json").data["id"]
    response = api_client.patch(
        f"/api/habits/{useful}/", {"related_habit": pleasant}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_related_pleasant_cannot_be_reclassified(api_client, habit_data):
    pleasant = api_client.post(
        "/api/habits/", {**habit_data, "reward": "", "is_pleasant": True},
        format="json",
    ).data["id"]
    useful = api_client.post(
        "/api/habits/", {**habit_data, "reward": "", "related_habit": pleasant},
        format="json",
    )
    assert useful.status_code == 201
    forbidden = api_client.patch(
        f"/api/habits/{pleasant}/", {"is_pleasant": False}, format="json"
    )
    assert forbidden.status_code == 400


@pytest.mark.django_db
def test_model_full_clean_enforces_cross_field_validation(user):
    habit = Habit(
        owner=user, place="Дом", time="08:00", action="Чтение",
        duration=121, periodicity=8, reward="Чай", is_pleasant=True,
    )
    with pytest.raises(ValidationError):
        habit.full_clean()


@pytest.mark.django_db
def test_scheduling_changes_and_pending_reminders_are_canceled(
    api_client, user, habit_data
):
    from django.utils import timezone

    from notifications.models import Reminder

    response = api_client.post("/api/habits/", habit_data, format="json")
    pk = response.data["id"]
    old_date = Habit.objects.get(pk=pk).next_reminder_at
    pending = Reminder.objects.create(
        habit_id=pk, scheduled_for=old_date, chat_id=123, text="test"
    )
    result = api_client.patch(
        f"/api/habits/{pk}/", {"time": "22:00:00"}, format="json"
    )
    assert result.status_code == 200
    assert Habit.objects.get(pk=pk).next_reminder_at != old_date
    pending.refresh_from_db()
    assert pending.status == Reminder.CANCELED
    assert timezone.is_aware(Habit.objects.get(pk=pk).next_reminder_at)
