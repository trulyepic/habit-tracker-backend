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


def _seed_weekly_progress(owner, *, active_habits=4, week_checkins=10):
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())

    seeded = []
    for i in range(active_habits):
        habit = Habit.objects.create(owner=owner, name=f"wb-strong-{i}", is_active=True)
        seeded.append(habit)
        for d in range(9):
            CheckIn.objects.create(habit=habit, date=today - timedelta(days=d), minutes_spent=25)

    for idx in range(week_checkins):
        habit = seeded[idx % len(seeded)]
        day = monday + timedelta(days=(idx % 7))
        CheckIn.objects.get_or_create(habit=habit, date=day, defaults={"minutes_spent": 25})


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
          rewardClaimedAt
          rewardAwardedXp
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
    assert chain["rewardClaimedAt"] is None
    assert chain["rewardAwardedXp"] == 0

    claim_mutation = """
      mutation {
        claimDailyQuestReward {
          claimed
          claimReason
          awardedXp
          chain {
            rewardClaimed
            rewardClaimable
            rewardXp
            rewardClaimedAt
            rewardAwardedXp
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
    assert first_data["claimReason"] == "claimed"
    assert first_data["awardedXp"] == DAILY_QUEST_REWARD_XP
    assert first_data["chain"]["rewardClaimed"] is True
    assert first_data["chain"]["rewardClaimable"] is False
    assert first_data["chain"]["rewardClaimedAt"] is not None
    assert first_data["chain"]["rewardAwardedXp"] == DAILY_QUEST_REWARD_XP
    assert first_data["profile"]["totalXp"] == DAILY_QUEST_REWARD_XP

    second_claim = _post_graphql(client, claim_mutation)
    assert "errors" not in second_claim, second_claim.get("errors")
    second_data = second_claim["data"]["claimDailyQuestReward"]
    assert second_data["claimed"] is False
    assert second_data["claimReason"] == "already_claimed"
    assert second_data["awardedXp"] == 0
    assert second_data["chain"]["rewardClaimed"] is True
    assert second_data["chain"]["rewardAwardedXp"] == DAILY_QUEST_REWARD_XP
    assert second_data["profile"]["totalXp"] == DAILY_QUEST_REWARD_XP


def test_weekly_boss_encounter_and_claim_reward_once_via_graphql(user):
    profile, _ = PlayerProfile.objects.get_or_create(user=user)
    profile.level = 15
    profile.total_xp = 0
    profile.save(update_fields=["level", "total_xp"])
    _seed_weekly_progress(user)

    client = Client()
    client.force_login(user)

    encounter_query = """
      query {
        weeklyBossEncounter {
          weekKey
          boss { key name rarity difficulty isWeekly }
          completedCount
          totalCount
          isComplete
          rewardXp
          rewardClaimed
          rewardClaimable
          rewardClaimedAt
        }
      }
    """
    encounter_payload = _post_graphql(client, encounter_query)
    assert "errors" not in encounter_payload, encounter_payload.get("errors")

    encounter = encounter_payload["data"]["weeklyBossEncounter"]
    assert encounter["boss"]["isWeekly"] is True
    assert encounter["isComplete"] is True
    assert encounter["rewardClaimed"] is False
    assert encounter["rewardClaimable"] is True

    claim_mutation = """
      mutation {
        claimWeeklyBossReward {
          claimed
          claimReason
          awardedXp
          encounter {
            rewardClaimed
            rewardClaimable
            rewardClaimedAt
            rewardAwardedXp
          }
          profile {
            totalXp
          }
        }
      }
    """
    first_claim = _post_graphql(client, claim_mutation)
    assert "errors" not in first_claim, first_claim.get("errors")
    first = first_claim["data"]["claimWeeklyBossReward"]
    assert first["claimed"] is True
    assert first["claimReason"] == "claimed"
    assert first["awardedXp"] > 0
    assert first["encounter"]["rewardClaimed"] is True
    assert first["encounter"]["rewardClaimable"] is False
    assert first["encounter"]["rewardClaimedAt"] is not None
    assert first["profile"]["totalXp"] > 0

    second_claim = _post_graphql(client, claim_mutation)
    assert "errors" not in second_claim, second_claim.get("errors")
    second = second_claim["data"]["claimWeeklyBossReward"]
    assert second["claimed"] is False
    assert second["claimReason"] == "already_claimed"


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
