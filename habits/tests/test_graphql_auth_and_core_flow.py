import json

import pytest
from django.test import Client
from django.utils import timezone

from habits.models import CheckIn, Habit

pytestmark = pytest.mark.django_db


@pytest.fixture()
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="auth_flow_user",
        password="pass12345",
        email="auth_flow@example.com",
    )


def _post_graphql(client: Client, query: str, variables=None):
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    response = client.post("/graphql/", data=payload, content_type="application/json")
    assert response.status_code == 200
    return json.loads(response.content)


def test_me_and_habits_queries_reflect_auth_state(user):
    anon_client = Client()
    query = """
      query {
        me { id username }
        habits { id name }
      }
    """
    anon_payload = _post_graphql(anon_client, query)
    assert "errors" not in anon_payload, anon_payload.get("errors")
    assert anon_payload["data"]["me"] is None
    assert anon_payload["data"]["habits"] == []

    Habit.objects.create(owner=user, name="Authenticated Quest")

    authed_client = Client()
    authed_client.force_login(user)
    authed_payload = _post_graphql(authed_client, query)
    assert "errors" not in authed_payload, authed_payload.get("errors")
    assert authed_payload["data"]["me"]["username"] == "auth_flow_user"
    assert len(authed_payload["data"]["habits"]) == 1
    assert authed_payload["data"]["habits"][0]["name"] == "Authenticated Quest"


@pytest.mark.parametrize(
    "mutation, variables, field_name",
    [
        (
            """
              mutation($id: ID!, $isActive: Boolean!) {
                toggleHabitActive(id: $id, isActive: $isActive) {
                  habit { id }
                }
              }
            """,
            {"id": "1", "isActive": False},
            "toggleHabitActive",
        ),
        (
            """
              mutation($id: ID!) {
                deleteHabit(id: $id) { ok deletedId }
              }
            """,
            {"id": "1"},
            "deleteHabit",
        ),
        (
            """
              mutation {
                claimDailyQuestReward { claimed awardedXp }
              }
            """,
            None,
            "claimDailyQuestReward",
        ),
    ],
)
def test_core_mutations_require_auth(mutation, variables, field_name):
    client = Client()
    payload = _post_graphql(client, mutation, variables=variables)

    assert "errors" in payload
    assert payload["data"][field_name] is None


def test_toggle_and_delete_flow_preserves_then_removes_data(user):
    client = Client()
    client.force_login(user)

    habit = Habit.objects.create(owner=user, name="Flow Quest")
    checkin = CheckIn.objects.create(habit=habit, date=timezone.localdate())

    toggle_mutation = """
      mutation($id: ID!, $isActive: Boolean!) {
        toggleHabitActive(id: $id, isActive: $isActive) {
          habit { id isActive }
        }
      }
    """
    toggle_payload = _post_graphql(client, toggle_mutation, {"id": str(habit.id), "isActive": False})
    assert "errors" not in toggle_payload, toggle_payload.get("errors")
    assert toggle_payload["data"]["toggleHabitActive"]["habit"]["isActive"] is False
    assert Habit.objects.filter(id=habit.id, owner=user).exists()
    assert CheckIn.objects.filter(id=checkin.id, habit=habit).exists()

    delete_mutation = """
      mutation($id: ID!) {
        deleteHabit(id: $id) {
          ok
          deletedId
        }
      }
    """
    delete_payload = _post_graphql(client, delete_mutation, {"id": str(habit.id)})
    assert "errors" not in delete_payload, delete_payload.get("errors")
    assert delete_payload["data"]["deleteHabit"]["ok"] is True
    assert delete_payload["data"]["deleteHabit"]["deletedId"] == str(habit.id)
    assert Habit.objects.filter(id=habit.id).count() == 0
    assert CheckIn.objects.filter(id=checkin.id).count() == 0
