import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from habits.models import CheckIn, Habit, PlayerProfile
from habits.services.daily_quests import DAILY_QUEST_REWARD_XP

pytestmark = pytest.mark.django_db


@pytest.fixture()
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="dq_graphql_user",
        password="pass12345",
        email="dq_graphql@example.com",
    )


def _post_graphql(client: Client, query: str, variables=None):
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    response = client.post("/graphql/", data=payload, content_type="application/json")
    assert response.status_code == 200
    return json.loads(response.content)


def _create_strong_habit(owner, name: str, streak_days: int = 7):
    habit = Habit.objects.create(owner=owner, name=name, is_active=True)
    today = timezone.localdate()
    for offset in range(streak_days):
        CheckIn.objects.create(habit=habit, date=today - timedelta(days=offset), minutes_spent=20)
    return habit


def test_daily_quest_chain_and_claim_reward_once_via_graphql(user):
    profile, _ = PlayerProfile.objects.get_or_create(user=user)
    profile.level = 12
    profile.total_xp = 0
    profile.save(update_fields=["level", "total_xp"])

    # Strong data setup satisfies all objective variants in the catalog.
    for i in range(4):
        _create_strong_habit(user, f"dq-strong-{i}", streak_days=7)

    client = Client()
    client.force_login(user)

    chain_query = """
      query {
        dailyQuestChain {
          dateKey
          completedCount
          totalCount
          isComplete
          rewardXp
          rewardClaimed
          rewardClaimable
        }
      }
    """
    chain_payload = _post_graphql(client, chain_query)
    assert "errors" not in chain_payload, chain_payload.get("errors")

    chain = chain_payload["data"]["dailyQuestChain"]
    assert chain["isComplete"] is True
    assert chain["rewardClaimed"] is False
    assert chain["rewardClaimable"] is True
    assert chain["rewardXp"] == DAILY_QUEST_REWARD_XP

    claim_mutation = """
      mutation {
        claimDailyQuestReward {
          claimed
          awardedXp
          chain {
            rewardClaimed
            rewardClaimable
            rewardXp
          }
          profile {
            totalXp
            level
          }
        }
      }
    """
    first_claim = _post_graphql(client, claim_mutation)
    assert "errors" not in first_claim, first_claim.get("errors")
    first_data = first_claim["data"]["claimDailyQuestReward"]
    assert first_data["claimed"] is True
    assert first_data["awardedXp"] == DAILY_QUEST_REWARD_XP
    assert first_data["chain"]["rewardClaimed"] is True
    assert first_data["chain"]["rewardClaimable"] is False
    assert first_data["profile"]["totalXp"] == DAILY_QUEST_REWARD_XP

    second_claim = _post_graphql(client, claim_mutation)
    assert "errors" not in second_claim, second_claim.get("errors")
    second_data = second_claim["data"]["claimDailyQuestReward"]
    assert second_data["claimed"] is False
    assert second_data["awardedXp"] == 0
    assert second_data["profile"]["totalXp"] == DAILY_QUEST_REWARD_XP


def test_me_query_resolves_player_profile_title_fields_without_errors(user):
    profile, _ = PlayerProfile.objects.get_or_create(user=user)
    profile.level = 3
    profile.achievements_unlocked = {"first_step": timezone.now().isoformat()}
    profile.save(update_fields=["level", "achievements_unlocked"])

    client = Client()
    client.force_login(user)

    me_query = """
      query {
        me {
          id
          username
          playerProfile {
            level
            achievementsUnlocked
            currentTitle { key name emoji flavor minLevel requiredAchievements }
            nextTitle { key name emoji flavor minLevel requiredAchievements }
            nextTitleProgressPct
            nextTitleMissingLevels
            nextTitleMissingAchievements
            isMaxTitle
            unlockedTitles { key name }
          }
        }
      }
    """
    payload = _post_graphql(client, me_query)
    assert "errors" not in payload, payload.get("errors")

    profile_data = payload["data"]["me"]["playerProfile"]
    assert profile_data["currentTitle"] is not None
    assert profile_data["nextTitleProgressPct"] is not None
    assert isinstance(profile_data["unlockedTitles"], list)
