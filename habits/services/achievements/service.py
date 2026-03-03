from habits.services.achievements.catalog import ACHIEVEMENTS
from habits.services.achievements.types import AchievementContext


def build_context(
    *,
    total_checkins: int,
    streak_days: int,
    total_minutes_logged: int,
    weekly_boss_wins: int = 0,
    weekly_hard_boss_wins: int = 0,
    weekly_legendary_boss_wins: int = 0,
) -> AchievementContext:
    return AchievementContext(
        total_checkins=int(total_checkins),
        streak_days=int(streak_days),
        total_minutes_logged=int(total_minutes_logged),
        weekly_boss_wins=int(weekly_boss_wins),
        weekly_hard_boss_wins=int(weekly_hard_boss_wins),
        weekly_legendary_boss_wins=int(weekly_legendary_boss_wins),
    )


def evaluate_new_unlocks(
    *,
    unlocked: dict,
    context: AchievementContext,
    now_iso: str,
) -> tuple[dict, list[str]]:
    """Return updated unlocked map plus keys newly unlocked in this evaluation."""

    updated_unlocked = dict(unlocked or {})
    newly_unlocked: list[str] = []

    for key, definition in ACHIEVEMENTS.items():
        if key in updated_unlocked:
            continue
        if definition.rule(context):
            updated_unlocked[key] = now_iso
            newly_unlocked.append(key)

    return updated_unlocked, newly_unlocked


def total_bonus_xp_for_keys(keys: list[str]) -> int:
    """Sum bonus XP for achievement keys; unknown keys are ignored."""

    total = 0
    for key in keys:
        definition = ACHIEVEMENTS.get(key)
        if definition is None:
            continue
        total += definition.bonus_xp
    return total
