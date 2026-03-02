import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from habits.models import CheckIn, Habit

pytestmark = pytest.mark.django_db


@pytest.fixture()
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="activity_user",
        password="pass12345",
        email="activity@example.com",
    )


def _post_graphql(client: Client, query: str, variables=None):
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    response = client.post("/graphql/", data=payload, content_type="application/json")
    assert response.status_code == 200
    return json.loads(response.content)


def test_recent_activity_anonymous_returns_empty_list():
    client = Client()
    query = "query { recentActivity { id action habitName xpAwarded } }"
    payload = _post_graphql(client, query)
    assert "errors" not in payload, payload.get("errors")
    assert payload["data"]["recentActivity"] == []


def test_recent_activity_returns_latest_user_checkins(user):
    client = Client()
    client.force_login(user)

    h1 = Habit.objects.create(owner=user, name="Read")
    h2 = Habit.objects.create(owner=user, name="Code")
    today = timezone.localdate()

    old = CheckIn.objects.create(habit=h1, date=today - timedelta(days=2), xp_awarded=11)
    mid = CheckIn.objects.create(habit=h2, date=today - timedelta(days=1), xp_awarded=12, used_freeze=True)
    new = CheckIn.objects.create(habit=h1, date=today, xp_awarded=13, minutes_spent=25)

    query = """
      query Activity($limit: Int) {
        recentActivity(limit: $limit) {
          id
          action
          habitName
          date
          xpAwarded
          minutesSpent
          usedFreeze
        }
      }
    """
    payload = _post_graphql(client, query, {"limit": 2})
    assert "errors" not in payload, payload.get("errors")
    events = payload["data"]["recentActivity"]

    assert len(events) == 2
    assert [e["id"] for e in events] == [str(new.id), str(mid.id)]
    assert events[0]["action"] == "checkin"
    assert events[0]["habitName"] == "Read"
    assert events[0]["xpAwarded"] == 13
    assert events[0]["minutesSpent"] == 25
    assert events[1]["usedFreeze"] is True
    assert str(old.id) not in [e["id"] for e in events]


def test_recent_activity_includes_created_quest_event(user):
    client = Client()
    client.force_login(user)
    h = Habit.objects.create(owner=user, name="Created Quest")

    query = """
      query {
        recentActivity(limit: 5) {
          id
          action
          habitName
          xpAwarded
        }
      }
    """
    payload = _post_graphql(client, query)
    assert "errors" not in payload, payload.get("errors")
    events = payload["data"]["recentActivity"]

    created = next((e for e in events if e["action"] == "habit_created"), None)
    assert created is not None
    assert created["id"] == f"habit-{h.id}"
    assert created["habitName"] == "Created Quest"
    assert created["xpAwarded"] == 0
