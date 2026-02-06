import json
import pytest
from django.utils import timezone

from habits.models import Habit

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
      mutation($habitId: ID!, $date: Date, $m: Int) {
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
      mutation($habitId: ID!, $date: Date, $m: Int) {
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
