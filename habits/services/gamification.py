from dataclasses import dataclass

from django.db.models import Sum
from django.utils import timezone
from typing import Optional

from django.db import transaction

from habits.models import CheckIn, PlayerProfile, Habit
from habits.services import habit_stats
from habits.services.habit_stats import total_checkins


@dataclass(frozen=True)
class XPAwardBreakdown:
    base: int
    streak_bonus: int
    minutes_bonus: int

    @property
    def total(self):
        return self.base + self.streak_bonus + self.minutes_bonus


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
    base = 10
    streak_bonus = min(2 * max(current_streak, 0), 20)

    if minutes_spent is None:
        minutes_bonus = 0
    else:
        #  +1 XP per 10 minutes, cap at +30
        minutes_bonus = min(minutes_spent // 10, 30)

    return XPAwardBreakdown(base=base, streak_bonus=streak_bonus, minutes_bonus=minutes_bonus)


@transaction.atomic
def apply_checkin_reward( *, user, checkin: CheckIn, current_streak: int, total_checkins_for_user: int ) -> PlayerProfile:
    profile, _ = PlayerProfile.objects.select_for_update().get_or_create(user=user)

    breakdown = compute_xp_award(
        current_streak=current_streak,
        minutes_spent=checkin.minutes_spent,
    )

    # persist awarded XP for audit/history
    checkin.xp_awarded = breakdown.total
    checkin.save(update_fields=["xp_awarded"])

    profile.total_xp += breakdown.total
    if checkin.minutes_spent:
        profile.total_minutes_logged += checkin.minutes_spent
    profile.level = level_from_xp(profile.total_xp)

    unlocked = profile.achievements_unlocked or {}
    now_iso = timezone.now().isoformat()

    # Phase 1 achievements
    if "first_step" not in unlocked and total_checkins_for_user >= 1:
        unlocked["first_step"] = now_iso
    if "on_fire" not in unlocked and current_streak >= 7:
        unlocked["on_fire"] = now_iso
    if "ten_hours" not in unlocked and profile.total_minutes_logged >= 600:
        unlocked["ten_hours"] = now_iso

    profile.achievements_unlocked = unlocked

    profile.save(update_fields=[
        "total_xp",
        "level",
        "total_minutes_logged",
        "achievements_unlocked",
        "updated_at"
    ])

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

    unlocked = dict(before_unlocked)
    now_iso = timezone.now().isoformat()

    if "first_step" not in unlocked and total_checkins_for_user >= 1:
        unlocked["first_step"] = now_iso

    if "on_fire" not in unlocked and max_streak >= 7:
        unlocked["on_fire"] = now_iso

    if "ten_hours" not in unlocked and profile.total_minutes_logged >= 600:
        unlocked["ten_hours"] = now_iso

    did_change = (unlocked != before_unlocked) or (profile.total_minutes_logged != before_minutes)
    if did_change:
        profile.achievements_unlocked = unlocked
        profile.save(update_fields=["total_minutes_logged", "achievements_unlocked", "updated_at"])

    return profile













