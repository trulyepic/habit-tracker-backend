from datetime import timedelta

import pytest
from django.utils import timezone

from habits.models import CheckIn, Habit, PlayerProfile
from habits.services.weekly_bosses import (
    WEEKLY_BOSS_REWARD_XP,
    claim_weekly_boss_reward,
    get_weekly_boss_encounter,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="weekly_boss_user",
        password="pass12345",
        email="weekly@example.com",
    )


def _seed_weekly_progress(owner, *, active_habits=4, week_checkins=8):
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())

    habits = []
    for i in range(active_habits):
        habit = Habit.objects.create(owner=owner, name=f"wb-habit-{i}", is_active=True)
        habits.append(habit)

        # Long streak to satisfy streak-focused weekly mechanics.
        for d in range(9):
            CheckIn.objects.create(habit=habit, date=today - timedelta(days=d), minutes_spent=20)

    # Ensure we have enough check-ins during current week window.
    for idx in range(week_checkins):
        habit = habits[idx % len(habits)]
        day = monday + timedelta(days=(idx % 7))
        CheckIn.objects.get_or_create(habit=habit, date=day, defaults={"minutes_spent": 20})


def test_get_weekly_boss_encounter_returns_expected_shape(user):
    profile, _ = PlayerProfile.objects.get_or_create(user=user)
    profile.level = 8
    profile.save(update_fields=["level"])

    encounter = get_weekly_boss_encounter(user=user)

    assert encounter["total_count"] == 4
    assert len(encounter["quests"]) == 4
    assert encounter["boss"]["is_weekly"] is True
    assert encounter["reward_xp"] == WEEKLY_BOSS_REWARD_XP
    assert encounter["reward_claimed"] is False
    assert encounter["reward_claimed_at"] is None
    assert encounter["reward_awarded_xp"] == 0


def test_claim_weekly_boss_reward_awards_once_when_complete(user):
    profile, _ = PlayerProfile.objects.get_or_create(user=user)
    profile.level = 15
    profile.total_xp = 0
    profile.save(update_fields=["level", "total_xp"])
    _seed_weekly_progress(user, active_habits=4, week_checkins=10)

    first = claim_weekly_boss_reward(user=user)
    profile.refresh_from_db()

    assert first["claimed"] is True
    assert first["claim_reason"] == "claimed"
    assert first["awarded_xp"] >= WEEKLY_BOSS_REWARD_XP
    assert first["encounter"]["reward_claimed"] is True
    assert first["encounter"]["reward_awarded_xp"] == WEEKLY_BOSS_REWARD_XP
    assert profile.total_xp == first["awarded_xp"]
    assert "raid_initiate" in (profile.achievements_unlocked or {})

    second = claim_weekly_boss_reward(user=user)
    profile.refresh_from_db()

    assert second["claimed"] is False
    assert second["claim_reason"] == "already_claimed"
    assert second["awarded_xp"] == 0
    assert profile.total_xp == first["awarded_xp"]
