import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from habits.models import Habit, CheckIn

pytestmark = pytest.mark.django_db


@pytest.fixture()
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="u1",
        password="pass12345",
        email="u1@example.com",
    )


@pytest.fixture()
def other_user(django_user_model):
    return django_user_model.objects.create_user(
        username="u2",
        password="pass12345",
        email="u2@example.com",
    )


def _post_graphql(client: Client, query: str, variables=None):
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    response = client.post("/graphql/", data=payload, content_type="application/json")
    assert response.status_code == 200
    data = json.loads(response.content)
    assert "errors" not in data, data.get("errors")
    return data["data"]


def test_graphql_habits__anonymous__returns_empty_list():
    client = Client()

    query = """
      query {
        habits {
          id
          name
        }
      }
    """
    data = _post_graphql(client, query)
    assert data["habits"] == []


def test_graphql_habits__returns_only_logged_in_users_habits(user, other_user):
    today = timezone.localdate()

    # User habit
    habit_u1 = Habit.objects.create(owner=user, name="GraphQLHabit")
    CheckIn.objects.bulk_create(
        [
            CheckIn(habit=habit_u1, date=today),
            CheckIn(habit=habit_u1, date=today - timedelta(days=1)),
        ]
    )

    # Other user's habit (should NOT show up)
    habit_u2 = Habit.objects.create(owner=other_user, name="OtherUsersHabit")
    CheckIn.objects.create(habit=habit_u2, date=today)

    client = Client()
    client.force_login(user)

    query = """
      query {
        habits {
          id
          name
          totalCheckins
          checkedInToday
          last7DaysCount
          currentStreak
          bestStreak
        }
      }
    """
    data = _post_graphql(client, query)
    habits = data["habits"]

    assert len(habits) == 1
    h = habits[0]

    assert h["name"] == "GraphQLHabit"
    assert h["totalCheckins"] == 2
    assert h["checkedInToday"] is True
    assert h["last7DaysCount"] == 2
    assert h["currentStreak"] == 2
    assert h["bestStreak"] == 2


def test_graphql_habit__by_id__returns_checkins_and_derived_fields_for_owner(user, other_user):
    today = timezone.localdate()

    habit = Habit.objects.create(owner=user, name="SingleHabit")

    # Dates:
    # - today..today-2 => currentStreak 3
    # - also add an older run today-10..today-6 => bestStreak 5
    dates = [
        today,
        today - timedelta(days=1),
        today - timedelta(days=2),
        today - timedelta(days=6),
        today - timedelta(days=7),
        today - timedelta(days=8),
        today - timedelta(days=9),
        today - timedelta(days=10),
    ]
    CheckIn.objects.bulk_create([CheckIn(habit=habit, date=d) for d in dates])

    # Other user's habit (ensure not accessible by user)
    other = Habit.objects.create(owner=other_user, name="NotYours")

    client = Client()
    client.force_login(user)

    query = """
      query($id: ID!) {
        habit(id: $id) {
          id
          name
          totalCheckins
          checkedInToday
          last7DaysCount
          currentStreak
          bestStreak
          checkins {
            date
          }
        }
      }
    """

    data = _post_graphql(client, query, variables={"id": str(habit.id)})
    h = data["habit"]

    assert h["name"] == "SingleHabit"
    assert h["totalCheckins"] == 8
    assert h["checkedInToday"] is True
    assert h["last7DaysCount"] == 4  # today, -1, -2, -6
    assert h["currentStreak"] == 3
    assert h["bestStreak"] == 5
    assert h["checkins"][0]["date"] == str(today)

    # OPTIONAL: access control check — depends on your backend behavior.
    # If your resolver raises when habit isn't owned, GraphQL will return errors.
    # We'll assert that querying other user's habit produces an error.
    response = client.post(
        "/graphql/",
        data={"query": query, "variables": {"id": str(other.id)}},
        content_type="application/json",
    )
    payload = json.loads(response.content)

    # Either data.habit is null with errors, or habit isn't returned at all depending on your resolver.
    assert payload.get("data", {}).get("habit") is None
    assert "errors" in payload
