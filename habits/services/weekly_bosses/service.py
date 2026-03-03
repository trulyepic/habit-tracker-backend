from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from habits.models import CheckIn, Habit, PlayerProfile
from habits.services import habit_stats
from habits.services.achievements import build_context, evaluate_new_unlocks, total_bonus_xp_for_keys
from habits.services.bosses import resolve_weekly_boss
from habits.services.game_balance import MAX_FREEZE_CHARGES
from habits.services.gamification import level_from_xp
from habits.services.streaks import maybe_grant_level_freezes
from habits.services.weekly_bosses.catalog import WEEKLY_BOSS_REWARD_XP, WEEKLY_OBJECTIVE_POOL
from habits.services.weekly_bosses.types import WeeklyBossContext, WeeklyBossObjectiveDef


def _week_bounds(d=None) -> tuple:
    date = d or timezone.localdate()
    start = date - timedelta(days=date.weekday())  # Monday
    end = start + timedelta(days=6)
    return start, end


def _week_key(d=None) -> str:
    date = d or timezone.localdate()
    iso_year, iso_week, _ = date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _week_seed(d=None) -> int:
    date = d or timezone.localdate()
    iso_year, iso_week, _ = date.isocalendar()
    return iso_year * 100 + iso_week


def _pick_weekly_defs(*, seed: int, count: int = 4) -> list[WeeklyBossObjectiveDef]:
    size = len(WEEKLY_OBJECTIVE_POOL)
    picks: list[WeeklyBossObjectiveDef] = []
    used: set[int] = set()

    cursor = abs(seed) % size
    while len(picks) < min(count, size):
        if cursor not in used:
            picks.append(WEEKLY_OBJECTIVE_POOL[cursor])
            used.add(cursor)
        cursor = (cursor + 1) % size

    return picks


def _context_for_user(*, user, level: int, start_date, end_date) -> WeeklyBossContext:
    habits = list(Habit.objects.filter(owner=user).only("id", "is_active"))
    active_habits = [h for h in habits if h.is_active]
    active_ids = [h.id for h in active_habits]

    weekly_checkin_events = 0
    weekly_active_habits_touched = 0
    if active_ids:
        week_checkins = CheckIn.objects.filter(
            habit_id__in=active_ids,
            used_freeze=False,
            date__range=(start_date, end_date),
        )
        weekly_checkin_events = week_checkins.count()
        weekly_active_habits_touched = week_checkins.values("habit_id").distinct().count()

    max_streak = 0
    active_with_streak_5 = 0
    today = timezone.localdate()
    for habit in active_habits:
        dates = list(habit.checkins.filter(used_freeze=False).values_list("date", flat=True))
        date_set = set(dates)
        streak = 0
        cursor = today
        while cursor in date_set:
            streak += 1
            cursor -= timedelta(days=1)
        max_streak = max(max_streak, streak)
        if streak >= 5:
            active_with_streak_5 += 1

    return WeeklyBossContext(
        active_count=len(active_habits),
        weekly_checkin_events=int(weekly_checkin_events),
        weekly_active_habits_touched=int(weekly_active_habits_touched),
        max_streak=max_streak,
        active_with_streak_5=active_with_streak_5,
        level=int(level or 1),
    )


def get_weekly_boss_encounter(*, user, profile: PlayerProfile | None = None, at_date=None) -> dict:
    profile = profile or PlayerProfile.objects.get_or_create(user=user)[0]
    week_key = _week_key(at_date)
    week_start, week_end = _week_bounds(at_date)

    claims = dict(profile.weekly_boss_claims or {})
    claimed_record = claims.get(week_key)
    reward_claimed = claimed_record is not None

    reward_claimed_at = None
    reward_awarded_xp = 0
    if reward_claimed:
        if isinstance(claimed_record, dict):
            raw_claimed_at = claimed_record.get("claimed_at")
            reward_claimed_at = parse_datetime(raw_claimed_at) if isinstance(raw_claimed_at, str) else None
            reward_awarded_xp = int(claimed_record.get("awarded_xp") or WEEKLY_BOSS_REWARD_XP)
        else:
            reward_awarded_xp = WEEKLY_BOSS_REWARD_XP

    ctx = _context_for_user(
        user=user,
        level=profile.level,
        start_date=week_start,
        end_date=week_end,
    )
    defs = _pick_weekly_defs(seed=_week_seed(at_date), count=4)
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

    return {
        "week_key": week_key,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "boss": resolve_weekly_boss(seed=_week_seed(at_date)),
        "quests": quests,
        "completed_count": completed_count,
        "total_count": total_count,
        "completion_pct": int(completion_pct),
        "is_complete": is_complete,
        "reward_xp": WEEKLY_BOSS_REWARD_XP,
        "reward_claimed": reward_claimed,
        "reward_claimable": bool(is_complete and not reward_claimed),
        "reward_claimed_at": reward_claimed_at,
        "reward_awarded_xp": reward_awarded_xp,
    }


def _weekly_claim_counters(claims_map: dict) -> tuple[int, int, int]:
    wins = 0
    hard_wins = 0
    legendary_wins = 0
    for _, value in (claims_map or {}).items():
        wins += 1
        if isinstance(value, dict):
            if str(value.get("difficulty", "")).lower() == "hard":
                hard_wins += 1
            if str(value.get("rarity", "")).lower() == "legendary":
                legendary_wins += 1
    return wins, hard_wins, legendary_wins


def _max_streak_for_user(*, user) -> int:
    max_streak = 0
    for habit in Habit.objects.filter(owner=user).only("id"):
        streak = habit_stats.current_streak(habit)
        if streak > max_streak:
            max_streak = streak
    return max_streak


@transaction.atomic
def claim_weekly_boss_reward(*, user) -> dict:
    profile, _ = PlayerProfile.objects.select_for_update().get_or_create(user=user)
    encounter = get_weekly_boss_encounter(user=user, profile=profile)

    if encounter["reward_claimed"]:
        return {
            "claimed": False,
            "claim_reason": "already_claimed",
            "awarded_xp": 0,
            "profile": profile,
            "encounter": encounter,
        }

    if not encounter["is_complete"]:
        return {
            "claimed": False,
            "claim_reason": "incomplete",
            "awarded_xp": 0,
            "profile": profile,
            "encounter": encounter,
        }

    claims = dict(profile.weekly_boss_claims or {})
    boss = encounter["boss"]
    claims[encounter["week_key"]] = {
        "claimed_at": timezone.now().isoformat(),
        "awarded_xp": WEEKLY_BOSS_REWARD_XP,
        "boss_key": boss.get("key"),
        "rarity": boss.get("rarity"),
        "difficulty": boss.get("difficulty"),
    }

    profile.total_xp += WEEKLY_BOSS_REWARD_XP
    total_checkins = CheckIn.objects.filter(habit__owner=user, used_freeze=False).count()
    max_streak = _max_streak_for_user(user=user)
    weekly_wins, hard_wins, legendary_wins = _weekly_claim_counters(claims)
    now_iso = timezone.now().isoformat()
    unlocked, newly_unlocked = evaluate_new_unlocks(
        unlocked=profile.achievements_unlocked or {},
        context=build_context(
            total_checkins=total_checkins,
            streak_days=max_streak,
            total_minutes_logged=profile.total_minutes_logged,
            weekly_boss_wins=weekly_wins,
            weekly_hard_boss_wins=hard_wins,
            weekly_legendary_boss_wins=legendary_wins,
        ),
        now_iso=now_iso,
    )
    bonus_xp = total_bonus_xp_for_keys(newly_unlocked)
    profile.total_xp += bonus_xp
    profile.level = level_from_xp(profile.total_xp)
    profile.streak_freeze_charges = min(MAX_FREEZE_CHARGES, int(profile.streak_freeze_charges or 0) + 1)
    maybe_grant_level_freezes(profile=profile)
    profile.weekly_boss_claims = claims
    profile.achievements_unlocked = unlocked
    profile.save(
        update_fields=[
            "total_xp",
            "level",
            "weekly_boss_claims",
            "achievements_unlocked",
            "streak_freeze_charges",
            "freeze_milestones_claimed",
            "updated_at",
        ]
    )

    updated = get_weekly_boss_encounter(user=user, profile=profile)
    return {
        "claimed": True,
        "claim_reason": "claimed",
        "awarded_xp": WEEKLY_BOSS_REWARD_XP + bonus_xp,
        "profile": profile,
        "encounter": updated,
    }
