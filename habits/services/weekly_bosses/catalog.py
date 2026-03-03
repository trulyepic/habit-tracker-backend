from habits.services.game_balance import WEEKLY_BOSS_REWARD_XP
from habits.services.weekly_bosses.types import WeeklyBossObjectiveDef, WeeklyBossProgress


def _clamp_min_one(n: int) -> int:
    return max(1, int(round(n)))


WEEKLY_OBJECTIVE_POOL: tuple[WeeklyBossObjectiveDef, ...] = (
    WeeklyBossObjectiveDef(
        key="weekly_vanguard",
        title="Vanguard Tempo",
        description="Log consistent check-ins across the week.",
        icon="target",
        evaluate=lambda c: (
            lambda target: WeeklyBossProgress(
                current=c.weekly_checkin_events,
                target=target,
                complete=c.weekly_checkin_events >= target,
            )
        )(_clamp_min_one(8 if c.level >= 12 else 6)),
    ),
    WeeklyBossObjectiveDef(
        key="weekly_roster_control",
        title="Roster Control",
        description="Touch multiple active quests this week.",
        icon="sparkles",
        evaluate=lambda c: (
            lambda target: WeeklyBossProgress(
                current=c.weekly_active_habits_touched,
                target=target,
                complete=c.weekly_active_habits_touched >= target,
            )
        )(_clamp_min_one(3 if c.level >= 10 else 2)),
    ),
    WeeklyBossObjectiveDef(
        key="weekly_streak_forge",
        title="Streak Forge",
        description="Maintain one elite streak line.",
        icon="shield",
        evaluate=lambda c: (
            lambda target: WeeklyBossProgress(
                current=c.max_streak,
                target=target,
                complete=c.max_streak >= target,
            )
        )(_clamp_min_one(9 if c.level >= 15 else 6)),
    ),
    WeeklyBossObjectiveDef(
        key="weekly_elite_squad",
        title="Elite Squad",
        description="Keep multiple quests at 5+ streak days.",
        icon="flame",
        evaluate=lambda c: (
            lambda target: WeeklyBossProgress(
                current=c.active_with_streak_5,
                target=target,
                complete=c.active_with_streak_5 >= target,
            )
        )(_clamp_min_one(2 if c.level >= 12 else 1)),
    ),
    WeeklyBossObjectiveDef(
        key="weekly_active_roster",
        title="Active Roster",
        description="Sustain a broad active quest lineup.",
        icon="swords",
        evaluate=lambda c: (
            lambda target: WeeklyBossProgress(
                current=c.active_count,
                target=target,
                complete=c.active_count >= target,
            )
        )(_clamp_min_one(4 if c.level >= 10 else 3)),
    ),
)


__all__ = ["WEEKLY_BOSS_REWARD_XP", "WEEKLY_OBJECTIVE_POOL"]
