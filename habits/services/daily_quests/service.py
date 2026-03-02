from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from habits.models import Habit, PlayerProfile
from habits.services.daily_quests.catalog import DAILY_QUEST_POOL, DAILY_QUEST_REWARD_XP
from habits.services.daily_quests.types import DailyQuestContext, DailyQuestDef
from habits.services.gamification import level_from_xp
from habits.services.game_balance import MAX_FREEZE_CHARGES
from habits.services.streaks import maybe_grant_level_freezes


def _date_key(d=None) -> str:
    return (d or timezone.localdate()).isoformat()


def _seed_for_date(d=None) -> int:
    dt = d or timezone.localdate()
    return dt.year * 10000 + dt.month * 100 + dt.day


def _pick_daily_defs(*, seed: int, count: int = 3) -> list[DailyQuestDef]:
    size = len(DAILY_QUEST_POOL)
    picks: list[DailyQuestDef] = []
    used: set[int] = set()

    cursor = abs(seed) % size
    while len(picks) < min(count, size):
        if cursor not in used:
            picks.append(DAILY_QUEST_POOL[cursor])
            used.add(cursor)
        cursor = (cursor + 2) % size

    return picks


def _context_for_user(*, user, level: int) -> DailyQuestContext:
    habits = list(Habit.objects.filter(owner=user).only("is_active"))
    active_habits = [h for h in habits if h.is_active]

    checked_in_today_count = 0
    max_streak = 0
    active_with_streak_3 = 0

    for habit in active_habits:
        dates = list(habit.checkins.filter(used_freeze=False).values_list("date", flat=True))
        today = timezone.localdate()
        date_set = set(dates)

        if today in date_set:
            checked_in_today_count += 1

        streak = 0
        cursor = today
        while cursor in date_set:
            streak += 1
            cursor = cursor - timedelta(days=1)

        if streak > max_streak:
            max_streak = streak
        if streak >= 3:
            active_with_streak_3 += 1

    return DailyQuestContext(
        active_count=len(active_habits),
        checked_in_today_count=checked_in_today_count,
        max_streak=max_streak,
        active_with_streak_3=active_with_streak_3,
        level=int(level or 1),
    )


def get_daily_quest_chain(*, user, profile: PlayerProfile | None = None, at_date=None) -> dict:
    profile = profile or PlayerProfile.objects.get_or_create(user=user)[0]

    today_key = _date_key(at_date)
    claims = dict(profile.daily_quest_claims or {})
    claimed_record = claims.get(today_key)

    ctx = _context_for_user(user=user, level=profile.level)
    defs = _pick_daily_defs(seed=_seed_for_date(at_date), count=3)

    quests = []
    for definition in defs:
        progress = definition.evaluate(ctx)
        quests.append(
            {
                "key": definition.key,
                "title": definition.title,
                "description": definition.description,
                "icon": definition.icon,
                "current": int(progress.current),
                "target": int(progress.target),
                "complete": bool(progress.complete),
            }
        )

    completed_count = len([q for q in quests if q["complete"]])
    total_count = len(quests)
    completion_pct = round((completed_count / total_count) * 100) if total_count else 0
    is_complete = completed_count == total_count
    reward_claimed = claimed_record is not None

    return {
        "date_key": today_key,
        "quests": quests,
        "completed_count": completed_count,
        "total_count": total_count,
        "completion_pct": int(completion_pct),
        "is_complete": is_complete,
        "reward_xp": DAILY_QUEST_REWARD_XP,
        "reward_claimed": reward_claimed,
        "reward_claimable": bool(is_complete and not reward_claimed),
    }


@transaction.atomic
def claim_daily_quest_reward(*, user) -> dict:
    profile, _ = PlayerProfile.objects.select_for_update().get_or_create(user=user)

    chain = get_daily_quest_chain(user=user, profile=profile)
    if chain["reward_claimed"]:
        return {
            "claimed": False,
            "awarded_xp": 0,
            "profile": profile,
            "chain": chain,
        }

    if not chain["is_complete"]:
        return {
            "claimed": False,
            "awarded_xp": 0,
            "profile": profile,
            "chain": chain,
        }

    claims = dict(profile.daily_quest_claims or {})
    claims[chain["date_key"]] = {
        "claimed_at": timezone.now().isoformat(),
        "awarded_xp": DAILY_QUEST_REWARD_XP,
    }

    profile.total_xp += DAILY_QUEST_REWARD_XP
    profile.level = level_from_xp(profile.total_xp)
    profile.streak_freeze_charges = min(MAX_FREEZE_CHARGES, int(profile.streak_freeze_charges or 0) + 1)
    maybe_grant_level_freezes(profile=profile)
    profile.daily_quest_claims = claims
    profile.save(
        update_fields=[
            "total_xp",
            "level",
            "daily_quest_claims",
            "streak_freeze_charges",
            "freeze_milestones_claimed",
            "updated_at",
        ]
    )

    updated_chain = get_daily_quest_chain(user=user, profile=profile)
    return {
        "claimed": True,
        "awarded_xp": DAILY_QUEST_REWARD_XP,
        "profile": profile,
        "chain": updated_chain,
    }
