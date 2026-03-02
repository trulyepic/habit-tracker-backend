from datetime import timedelta

import pytest
from django.utils import timezone

from habits.models import CheckIn, Habit, PlayerProfile
from habits.services.streaks import claim_recovery_quest_reward, consume_streak_freeze, maybe_start_recovery_quest, recovery_quest_status

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="streak_user",
        password="pass12345",
        email="streak@example.com",
    )


def test_consume_streak_freeze_protects_habit(user):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    profile, _ = PlayerProfile.objects.get_or_create(user=user)
    profile.streak_freeze_charges = 2
    profile.save(update_fields=["streak_freeze_charges"])

    habit = Habit.objects.create(owner=user, name="Freeze Habit", is_active=True)
    CheckIn.objects.create(habit=habit, date=yesterday)

    result = consume_streak_freeze(user=user, habit_id=habit.id)
    profile.refresh_from_db()

    assert result["consumed"] is True
    assert profile.streak_freeze_charges == 1
    assert CheckIn.objects.filter(habit=habit, date=today, used_freeze=True).exists()


def test_recovery_quest_can_be_claimed_after_two_comeback_days(user):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    profile, _ = PlayerProfile.objects.get_or_create(user=user)
    profile.total_xp = 0
    profile.streak_freeze_charges = 0
    profile.save(update_fields=["total_xp", "streak_freeze_charges"])

    habit = Habit.objects.create(owner=user, name="Comeback Habit", is_active=True)
    CheckIn.objects.create(habit=habit, date=two_days_ago, xp_awarded=10)
    # Missed yesterday to trigger recovery quest.

    started = maybe_start_recovery_quest(user=user, profile=profile)
    assert started is True
    profile.save(update_fields=["recovery_quest_started_on", "updated_at"])

    # Two active comeback days.
    CheckIn.objects.create(habit=habit, date=today, xp_awarded=10)
    CheckIn.objects.create(habit=habit, date=today + timedelta(days=1), xp_awarded=10)

    status = recovery_quest_status(user=user, profile=profile)
    assert status["claimable"] is True

    result = claim_recovery_quest_reward(user=user)
    profile.refresh_from_db()

    assert result["claimed"] is True
    assert result["awarded_xp"] > 0
    assert profile.total_xp == result["awarded_xp"]
    assert profile.streak_freeze_charges == 1
