from datetime import timedelta

import pytest
from django.utils import timezone

from habits.models import Habit, CheckIn, PlayerProfile
from habits.services.daily_quests import DAILY_QUEST_REWARD_XP, claim_daily_quest_reward, get_daily_quest_chain


pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="dq_user",
        password="pass12345",
        email="dq@example.com",
    )


def _create_strong_habit(owner, name: str, streak_days: int = 7):
    habit = Habit.objects.create(owner=owner, name=name, is_active=True)
    today = timezone.localdate()
    for offset in range(streak_days):
        CheckIn.objects.create(habit=habit, date=today - timedelta(days=offset), minutes_spent=20)
    return habit


def test_get_daily_quest_chain_returns_expected_shape(user):
    profile, _ = PlayerProfile.objects.get_or_create(user=user)
    profile.level = 5
    profile.save(update_fields=["level"])

    chain = get_daily_quest_chain(user=user)

    assert chain["total_count"] == 3
    assert len(chain["quests"]) == 3
    assert chain["reward_xp"] > 0
    assert chain["reward_claimed"] is False


def test_claim_daily_quest_reward_does_not_claim_when_incomplete(user):
    result = claim_daily_quest_reward(user=user)

    assert result["claimed"] is False
    assert result["awarded_xp"] == 0


def test_claim_daily_quest_reward_awards_once_when_complete(user):
    profile, _ = PlayerProfile.objects.get_or_create(user=user)
    profile.level = 12
    profile.total_xp = 0
    profile.save(update_fields=["level", "total_xp"])

    for i in range(4):
        _create_strong_habit(user, f"habit-{i}", streak_days=7)

    first = claim_daily_quest_reward(user=user)
    profile.refresh_from_db()

    assert first["claimed"] is True
    assert first["awarded_xp"] == DAILY_QUEST_REWARD_XP
    assert profile.total_xp == DAILY_QUEST_REWARD_XP

    second = claim_daily_quest_reward(user=user)
    profile.refresh_from_db()

    assert second["claimed"] is False
    assert second["awarded_xp"] == 0
    assert profile.total_xp == DAILY_QUEST_REWARD_XP
