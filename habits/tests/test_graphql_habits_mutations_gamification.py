import json
from datetime import timedelta
import pytest
from django.utils import timezone

from habits.models import CheckIn, Habit

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="u1",
        password="pass12345",
        email="u1@example.com",
    )


def _post_graphql(client, query: str, variables=None):
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables

    response = client.post("/graphql/", data=payload, content_type="application/json")
    assert response.status_code == 200
    data = json.loads(response.content)

    # helpful assertion message if graphql errors happen
    assert "errors" not in data, data.get("errors")
    return data["data"]


def test_check_in_today_awards_xp_and_minutes(client, user):
    assert client.login(username="u1", password="pass12345")

    habit = Habit.objects.create(owner=user, name="Gym")
    today = timezone.localdate()

    query = """
      mutation($habitId: ID!, $date: Date, $m: Int!) {
        checkInToday(habitId: $habitId, date: $date, minutesSpent: $m) {
          created
          checkin { id date minutesSpent xpAwarded }
          profile { totalXp level totalMinutesLogged }
        }
      }
    """
    data = _post_graphql(client, query, {"habitId": str(habit.id), "date": str(today), "m": 45})
    payload = data["checkInToday"]

    assert payload["created"] is True
    assert payload["checkin"]["minutesSpent"] == 45
    assert payload["checkin"]["xpAwarded"] >= 10
    assert payload["profile"]["totalMinutesLogged"] == 45
    assert payload["profile"]["totalXp"] >= 10


def test_check_in_today_duplicate_does_not_double_award_xp(client, user):
    assert client.login(username="u1", password="pass12345")

    habit = Habit.objects.create(owner=user, name="Read")
    today = timezone.localdate()

    query = """
      mutation($habitId: ID!, $date: Date, $m: Int!) {
        checkInToday(habitId: $habitId, date: $date, minutesSpent: $m) {
          created
          profile { totalXp totalMinutesLogged }
        }
      }
    """

    first = _post_graphql(client, query, {"habitId": str(habit.id), "date": str(today), "m": 30})["checkInToday"]
    second = _post_graphql(client, query, {"habitId": str(habit.id), "date": str(today), "m": 30})["checkInToday"]

    assert first["created"] is True
    assert second["created"] is False

    assert second["profile"]["totalXp"] == first["profile"]["totalXp"]
    assert second["profile"]["totalMinutesLogged"] == first["profile"]["totalMinutesLogged"]


def test_check_in_today_upgrades_freeze_protected_entry(client, user):
    assert client.login(username="u1", password="pass12345")

    habit = Habit.objects.create(owner=user, name="FreezeUpgraded")
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    habit.checkins.create(date=yesterday)

    freeze_mutation = """
      mutation($habitId: ID!) {
        consumeStreakFreeze(habitId: $habitId) {
          consumed
          reason
        }
      }
    """
    freeze = _post_graphql(client, freeze_mutation, {"habitId": str(habit.id)})["consumeStreakFreeze"]
    assert freeze["consumed"] is True

    checkin_mutation = """
      mutation($habitId: ID!, $m: Int!) {
        checkInToday(habitId: $habitId, minutesSpent: $m) {
          created
          checkin { xpAwarded }
        }
      }
    """
    upgraded = _post_graphql(client, checkin_mutation, {"habitId": str(habit.id), "m": 20})["checkInToday"]
    habit.refresh_from_db()
    today_checkin = habit.checkins.get(date=today)

    assert upgraded["created"] is True
    assert upgraded["checkin"]["xpAwarded"] > 0
    assert today_checkin.used_freeze is False


def test_check_in_today_requires_minutes(client, user):
    assert client.login(username="u1", password="pass12345")
    habit = Habit.objects.create(owner=user, name="MinutesRequired")

    query = """
      mutation($habitId: ID!) {
        checkInToday(habitId: $habitId) {
          created
        }
      }
    """
    response = client.post(
        "/graphql/",
        data={"query": query, "variables": {"habitId": str(habit.id)}},
        content_type="application/json",
    )
    assert response.status_code == 400
    body = json.loads(response.content)
    assert "errors" in body
    assert "minutesSpent" in body["errors"][0]["message"]


def test_check_in_today_rejects_out_of_range_minutes(client, user):
    assert client.login(username="u1", password="pass12345")
    habit = Habit.objects.create(owner=user, name="MinutesRange")

    query = """
      mutation($habitId: ID!, $m: Int!) {
        checkInToday(habitId: $habitId, minutesSpent: $m) {
          created
        }
      }
    """
    response = client.post(
        "/graphql/",
        data={"query": query, "variables": {"habitId": str(habit.id), "m": 2000}},
        content_type="application/json",
    )
    assert response.status_code == 200
    body = json.loads(response.content)
    assert "errors" in body
    assert "between" in body["errors"][0]["message"]


def test_toggle_habit_active_does_not_delete_habit_or_checkins(client, user):
    assert client.login(username="u1", password="pass12345")

    habit = Habit.objects.create(owner=user, name="Meditate")
    checkin = CheckIn.objects.create(habit=habit, date=timezone.localdate())

    mutation = """
      mutation($id: ID!, $isActive: Boolean!) {
        toggleHabitActive(id: $id, isActive: $isActive) {
          habit { id isActive }
        }
      }
    """
    payload = _post_graphql(client, mutation, {"id": str(habit.id), "isActive": False})["toggleHabitActive"]

    habit.refresh_from_db()
    assert payload["habit"]["id"] == str(habit.id)
    assert payload["habit"]["isActive"] is False
    assert Habit.objects.filter(id=habit.id, owner=user).exists()
    assert CheckIn.objects.filter(id=checkin.id, habit=habit).exists()
