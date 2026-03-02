from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from habits.models import CheckIn, Habit, PlayerProfile
from habits.services.game_balance import (
    FREEZE_LEVEL_MILESTONE_INTERVAL,
    MAX_FREEZE_CHARGES,
    RECOVERY_QUEST_REWARD_XP,
    RECOVERY_QUEST_TARGET_DAYS,
    RECOVERY_QUEST_WINDOW_DAYS,
)


def _level_from_xp(total_xp: int) -> int:
    level = 1
    remaining = total_xp
    while True:
        cost = 100 * level
        if remaining < cost:
            return level
        remaining -= cost
        level += 1


def _distinct_active_checkin_days_since(*, user, start_date):
    return set(
        CheckIn.objects.filter(
            habit__owner=user,
            date__gte=start_date,
            used_freeze=False,
        ).values_list("date", flat=True)
    )


def maybe_grant_level_freezes(*, profile: PlayerProfile) -> bool:
    """
    Grants one freeze for each newly reached 5-level milestone.
    Returns True if charges changed.
    """
    milestone_count = int(profile.level or 0) // FREEZE_LEVEL_MILESTONE_INTERVAL
    newly_reached = max(milestone_count - int(profile.freeze_milestones_claimed or 0), 0)
    if newly_reached <= 0:
        return False

    next_charges = min(MAX_FREEZE_CHARGES, int(profile.streak_freeze_charges or 0) + newly_reached)
    profile.streak_freeze_charges = next_charges
    profile.freeze_milestones_claimed = milestone_count
    return True


def maybe_start_recovery_quest(*, user, profile: PlayerProfile) -> bool:
    """
    Starts a two-day comeback quest after a recent missed-day streak break.
    We detect a break when a habit has a check-in on D-2 and missed D-1.
    """
    today = timezone.localdate()

    if profile.recovery_quest_started_on and profile.recovery_quest_claimed_on is None:
        # Active quest already exists.
        return False

    if profile.recovery_quest_started_on and profile.recovery_quest_claimed_on:
        # Keep old quest until a new break event is detected.
        pass

    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    candidate_habits = Habit.objects.filter(owner=user, is_active=True).only("id")
    for habit in candidate_habits:
        has_two_days_ago = CheckIn.objects.filter(habit=habit, date=two_days_ago).exists()
        has_yesterday = CheckIn.objects.filter(habit=habit, date=yesterday).exists()
        if has_two_days_ago and not has_yesterday:
            profile.recovery_quest_started_on = today
            profile.recovery_quest_claimed_on = None
            return True
    return False


def recovery_quest_status(*, user, profile: PlayerProfile) -> dict:
    today = timezone.localdate()

    # Expire stale unfinished quests.
    if profile.recovery_quest_started_on and profile.recovery_quest_claimed_on is None:
        if (today - profile.recovery_quest_started_on).days > RECOVERY_QUEST_WINDOW_DAYS:
            profile.recovery_quest_started_on = None

    started = profile.recovery_quest_started_on
    if not started:
        return {
            "active": False,
            "start_date": None,
            "progress_days": 0,
            "target_days": RECOVERY_QUEST_TARGET_DAYS,
            "complete": False,
            "claimed": False,
            "reward_xp": RECOVERY_QUEST_REWARD_XP,
            "claimable": False,
        }

    progress_days = len(_distinct_active_checkin_days_since(user=user, start_date=started))
    complete = progress_days >= RECOVERY_QUEST_TARGET_DAYS
    claimed = profile.recovery_quest_claimed_on is not None
    return {
        "active": True,
        "start_date": started.isoformat(),
        "progress_days": int(progress_days),
        "target_days": RECOVERY_QUEST_TARGET_DAYS,
        "complete": bool(complete),
        "claimed": bool(claimed),
        "reward_xp": RECOVERY_QUEST_REWARD_XP,
        "claimable": bool(complete and not claimed),
    }


@transaction.atomic
def consume_streak_freeze(*, user, habit_id) -> dict:
    profile, _ = PlayerProfile.objects.select_for_update().get_or_create(user=user)
    habit = Habit.objects.get(pk=habit_id, owner=user)
    today = timezone.localdate()

    if profile.streak_freeze_charges <= 0:
        return {"consumed": False, "reason": "no_charges", "profile": profile, "habit": habit}

    yesterday = today - timedelta(days=1)
    has_yesterday = CheckIn.objects.filter(habit=habit, date=yesterday).exists()
    if not has_yesterday:
        return {"consumed": False, "reason": "not_at_risk", "profile": profile, "habit": habit}

    checkin, created = CheckIn.objects.get_or_create(
        habit=habit,
        date=today,
        defaults={"xp_awarded": 0, "used_freeze": True},
    )

    if not created:
        if checkin.used_freeze:
            return {"consumed": False, "reason": "already_protected", "profile": profile, "habit": habit}
        return {"consumed": False, "reason": "already_checked_in", "profile": profile, "habit": habit}

    profile.streak_freeze_charges = max(profile.streak_freeze_charges - 1, 0)
    profile.save(update_fields=["streak_freeze_charges", "updated_at"])
    return {"consumed": True, "reason": None, "profile": profile, "habit": habit}


@transaction.atomic
def claim_recovery_quest_reward(*, user) -> dict:
    profile, _ = PlayerProfile.objects.select_for_update().get_or_create(user=user)
    maybe_start_recovery_quest(user=user, profile=profile)
    status = recovery_quest_status(user=user, profile=profile)

    if not status["claimable"]:
        return {"claimed": False, "awarded_xp": 0, "profile": profile, "recovery_quest": status}

    profile.total_xp += RECOVERY_QUEST_REWARD_XP
    profile.level = _level_from_xp(profile.total_xp)
    profile.recovery_quest_claimed_on = timezone.localdate()
    profile.streak_freeze_charges = min(MAX_FREEZE_CHARGES, int(profile.streak_freeze_charges or 0) + 1)
    maybe_grant_level_freezes(profile=profile)
    profile.save(
        update_fields=[
            "total_xp",
            "level",
            "recovery_quest_claimed_on",
            "streak_freeze_charges",
            "freeze_milestones_claimed",
            "updated_at",
        ]
    )

    return {
        "claimed": True,
        "awarded_xp": RECOVERY_QUEST_REWARD_XP,
        "profile": profile,
        "recovery_quest": recovery_quest_status(user=user, profile=profile),
    }
