"""Regression checks for PATCH validation, cycles, and browser contracts."""
import pytest
from rest_framework.test import APIClient

from habits.models import Habit

pytestmark = pytest.mark.django_db


def create(client, data, **changes):
    response = client.post('/api/habits/', {**data, **changes}, format='json')
    assert response.status_code == 201, response.data
    return response.data['id']


@pytest.mark.parametrize('changes', [
    {'duration': 0}, {'duration': 121}, {'periodicity': 0}, {'periodicity': 8},
    {'is_pleasant': True},
])
def test_patch_cannot_bypass_rules(api_client, habit_data, changes):
    pk = create(api_client, habit_data)
    response = api_client.patch(f'/api/habits/{pk}/', changes, format='json')
    assert response.status_code == 400
    habit = Habit.objects.get(pk=pk)
    assert habit.duration == habit_data['duration']
    assert habit.periodicity == 1
    assert habit.is_pleasant is False


@pytest.mark.parametrize('duration,periodicity', [(1, 1), (120, 7)])
def test_valid_boundaries(api_client, habit_data, duration, periodicity):
    create(api_client, habit_data, duration=duration, periodicity=periodicity)


def test_patch_existing_relation_cannot_add_reward(api_client, habit_data):
    pleasant = create(api_client, habit_data, reward='', is_pleasant=True)
    useful = create(api_client, habit_data, reward='', related_habit=pleasant)
    response = api_client.patch(
        f'/api/habits/{useful}/', {'reward': 'Tea'}, format='json'
    )
    assert response.status_code == 400
    assert Habit.objects.get(pk=useful).reward == ''


def test_patch_cannot_link_foreign_habit(api_client, habit_data, other_user):
    foreign = Habit.objects.create(
        owner=other_user, place='Home', time='08:00', action='Tea',
        duration=30, is_pleasant=True,
    )
    own = create(api_client, habit_data, reward='')
    response = api_client.patch(
        f'/api/habits/{own}/', {'related_habit': foreign.pk}, format='json'
    )
    assert response.status_code == 400


def test_self_reference_and_two_node_cycle_rejected(api_client, habit_data):
    pleasant = create(api_client, habit_data, reward='', is_pleasant=True)
    useful = create(api_client, habit_data, reward='', related_habit=pleasant)
    for pk, changes in [
        (useful, {'related_habit': useful}),
        (pleasant, {'related_habit': useful}),
        (pleasant, {'is_pleasant': False, 'related_habit': useful}),
    ]:
        assert api_client.patch(
            f'/api/habits/{pk}/', changes, format='json'
        ).status_code == 400
    assert Habit.objects.get(pk=pleasant).related_habit_id is None


def test_pleasant_cannot_link_another_pleasant(api_client, habit_data):
    a = create(api_client, habit_data, reward='', is_pleasant=True)
    b = create(api_client, habit_data, reward='', is_pleasant=True)
    assert api_client.patch(
        f'/api/habits/{a}/', {'related_habit': b}, format='json'
    ).status_code == 400


def test_foreign_put_rejected(api_client, habit_data, other_user):
    foreign = Habit.objects.create(
        owner=other_user, place='Home', time='08:00', action='Tea', duration=30,
        is_public=True,
    )
    assert api_client.put(
        f'/api/habits/{foreign.pk}/', habit_data, format='json'
    ).status_code == 404


def test_cors_preflight(settings):
    settings.CORS_ALLOWED_ORIGINS = ['https://frontend.example']
    for origin, allowed in [('https://frontend.example', True),
                            ('https://attacker.example', False)]:
        response = APIClient().options(
            '/api/habits/', HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='PATCH',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization,content-type',
        )
        assert response.status_code == 200
        assert ('access-control-allow-origin' in response) is allowed
        if allowed:
            assert response['access-control-allow-origin'] == origin
            assert 'PATCH' in response['access-control-allow-methods']
            assert 'authorization' in response['access-control-allow-headers']


def test_pagination_navigation(api_client, habit_data):
    for i in range(11):
        create(api_client, habit_data, action=f'Habit {i}')
    first = api_client.get('/api/habits/').data
    assert set(first) == {'count', 'next', 'previous', 'results'}
    assert first['previous'] is None
    second = api_client.get(first['next']).data
    assert len(second['results']) == 5
    last = api_client.get(second['next']).data
    assert last['next'] is None
    assert len(last['results']) == 1
    assert api_client.get(last['previous']).data == second
