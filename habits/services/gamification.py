from dataclasses import dataclass

from django.db.models import Sum
from django.utils import timezone
from typing import Optional

from django.db import transaction

from habits.models import CheckIn, PlayerProfile, Habit
from habits.services import habit_stats
from habits.services.achievements import (
    build_context,
    evaluate_new_unlocks,
    total_bonus_xp_for_keys,
)
from habits.services.game_balance import (
    CHECKIN_BASE_XP,
    CHECKIN_MINUTES_BONUS_CAP,
    CHECKIN_MINUTES_BONUS_PER,
    CHECKIN_STREAK_BONUS_CAP,
    CHECKIN_STREAK_BONUS_PER_DAY,
)
from habits.services.streaks import maybe_grant_level_freezes, maybe_start_recovery_quest


@dataclass(frozen=True)
class XPAwardBreakdown:
    base: int
    streak_bonus: int
    minutes_bonus: int

    @property
    def total(self):
        return self.base + self.streak_bonus + self.minutes_bonus


def award_achievement_bonus_xp(*, profile, checkin, newly_unlocked_keys) -> int:
    """
    Adds bonus XP for newly unlocked achievements.
    - profile.total_xp increases (affects level)
    - checkin.xp_awarded increases (so the check-in reward reflects it)
    Returns the total bonus XP added.
    """
    total_bonus = total_bonus_xp_for_keys(newly_unlocked_keys)

    if total_bonus > 0:
        profile.total_xp += total_bonus

        # Attribute the bonus to the triggering check-in for audit/UX.
        checkin.xp_awarded += total_bonus
        checkin.save(update_fields=["xp_awarded"])
    return total_bonus


def level_from_xp(total_xp: int) -> int:
    """
    Level curve: XP needed to advance = 100 * current_level
    Total XP thresholds:
        level 1 starts at 0
        level 2 starts at 100
        level 3 starts at 300
        level 4 starts at 600
    """
    level = 1
    remaining = total_xp
    while True:
        cost = 100 * level
        if remaining < cost:
            return level
        remaining -= cost
        level += 1


def compute_xp_award(
        *,
        current_streak: int,
        minutes_spent: Optional[int],
) -> XPAwardBreakdown:
    base = CHECKIN_BASE_XP
    streak_bonus = min(
        CHECKIN_STREAK_BONUS_PER_DAY * max(current_streak, 0),
        CHECKIN_STREAK_BONUS_CAP,
    )

    if minutes_spent is None:
        minutes_bonus = 0
    else:
        # +1 XP per configured minute bucket, capped by configured limit.
        minutes_bonus = min(minutes_spent // CHECKIN_MINUTES_BONUS_PER, CHECKIN_MINUTES_BONUS_CAP)

    return XPAwardBreakdown(base=base, streak_bonus=streak_bonus, minutes_bonus=minutes_bonus)


@transaction.atomic
def apply_checkin_reward(
    *,
    user,
    checkin: CheckIn,
    current_streak: int,
    total_checkins_for_user: int,
) -> PlayerProfile:
    profile, _ = PlayerProfile.objects.select_for_update().get_or_create(user=user)

    breakdown = compute_xp_award(
        current_streak=current_streak,
        minutes_spent=checkin.minutes_spent,
    )

    # Persist awarded XP for audit/history (base + streak + minutes)
    checkin.xp_awarded = breakdown.total
    checkin.save(update_fields=["xp_awarded"])

    # Apply XP + minutes to profile
    profile.total_xp += breakdown.total
    if checkin.minutes_spent:
        profile.total_minutes_logged += checkin.minutes_spent

    now_iso = timezone.now().isoformat()
    unlocked, newly_unlocked = evaluate_new_unlocks(
        unlocked=profile.achievements_unlocked or {},
        context=build_context(
            total_checkins=total_checkins_for_user,
            streak_days=current_streak,
            total_minutes_logged=profile.total_minutes_logged,
        ),
        now_iso=now_iso,
    )

    # Award rarity-based bonus XP for newly unlocked achievements
    award_achievement_bonus_xp(
        profile=profile,
        checkin=checkin,
        newly_unlocked_keys=newly_unlocked,
    )

    # IMPORTANT: compute level after all XP is applied (including achievement bonuses)
    profile.level = level_from_xp(profile.total_xp)

    profile.achievements_unlocked = unlocked
    update_fields = [
        "total_xp",
        "level",
        "total_minutes_logged",
        "achievements_unlocked",
        "updated_at",
    ]
    if maybe_grant_level_freezes(profile=profile):
        update_fields.extend(["streak_freeze_charges", "freeze_milestones_claimed"])
    maybe_start_recovery_quest(user=user, profile=profile)
    if "recovery_quest_started_on" not in update_fields:
        update_fields.append("recovery_quest_started_on")
    profile.save(update_fields=update_fields)

    return profile


@transaction.atomic
def reconcile_profile_from_history(*, user) -> PlayerProfile:
    """
    Backfill achievements_unlocked based on existing data (server source of truth).
    Only ADDS missing achievements; does not remove anything.
    """
    profile, _ = PlayerProfile.objects.select_for_update().get_or_create(user=user)

    before_unlocked = profile.achievements_unlocked or {}
    before_minutes = profile.total_minutes_logged

    # Recompute minutes from all checkins (for correctness)
    agg = CheckIn.objects.filter(habit__owner=user).aggregate(total_minutes=Sum("minutes_spent"))
    profile.total_minutes_logged = int(agg["total_minutes"] or 0)

    total_checkins_for_user = CheckIn.objects.filter(habit__owner=user).count()

    max_streak = 0
    for h in Habit.objects.filter(owner=user).only("id"):
        s = habit_stats.current_streak(h)
        if s > max_streak:
            max_streak = s

    now_iso = timezone.now().isoformat()
    unlocked, _ = evaluate_new_unlocks(
        unlocked=before_unlocked,
        context=build_context(
            total_checkins=total_checkins_for_user,
            streak_days=max_streak,
            total_minutes_logged=profile.total_minutes_logged,
        ),
        now_iso=now_iso,
    )

    did_change = (unlocked != before_unlocked) or (profile.total_minutes_logged != before_minutes)
    if did_change:
        profile.achievements_unlocked = unlocked
        profile.save(update_fields=["total_minutes_logged", "achievements_unlocked", "updated_at"])

    return profile










