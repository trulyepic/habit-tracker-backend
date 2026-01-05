import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from habits.models import Habit, CheckIn

pytestmark = pytest.mark.django_db


def _post_graphql(client: Client, query: str, variables=None):
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    response = client.post("/graphql/", data=payload, content_type="application/json")
    assert response.status_code == 200
    data = json.loads(response.content)
    assert "errors" not in data, data.get("errors")
    return data["data"]


def test_graphql_habits__returns_derived_fields_for_each_habit():
    today = timezone.localdate()

    habit = Habit.objects.create(name="GraphQLHabit")
    # today + yesterday => streak 2, best 2, total 2, last7 2, checkedInToday true
    CheckIn.objects.bulk_create(
        [
            CheckIn(habit=habit, date=today),
            CheckIn(habit=habit, date=today - timedelta(days=1)),
        ]
    )

    client = Client()

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


def test_graphql_habits__checked_in_today_false__current_streak_zero():
    today = timezone.localdate()

    habit = Habit.objects.create(name="NoTodayGraphQL")
    CheckIn.objects.bulk_create(
        [
            CheckIn(habit=habit, date=today - timedelta(days=1)),
            CheckIn(habit=habit, date=today - timedelta(days=2)),
        ]
    )

    client = Client()

    query = """
      query {
        habits {
          name
          checkedInToday
          currentStreak
          totalCheckins
        }
      }
    """
    data = _post_graphql(client, query)
    h = data["habits"][0]

    assert h["name"] == "NoTodayGraphQL"
    assert h["checkedInToday"] is False
    assert h["currentStreak"] == 0
    assert h["totalCheckins"] == 2


def test_graphql_habit__by_id__returns_checkins_and_derived_fields():
    today = timezone.localdate()

    habit = Habit.objects.create(name="SingleHabit")
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

    client = Client()

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

    # last7DaysCount includes dates from today-6..today (7 days window)
    # In our data we have: today, -1, -2, -6 => 4 within last 7 days
    assert h["last7DaysCount"] == 4

    assert h["currentStreak"] == 3
    assert h["bestStreak"] == 5

    # checkins is ordered by your model Meta ordering (-date, -created_at)
    # So the first checkin date should be today
    assert h["checkins"][0]["date"] == str(today)








