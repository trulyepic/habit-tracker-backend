from habits.services.daily_quests.types import DailyQuestDef, DailyQuestProgress


def _clamp_min_one(n: int) -> int:
    return max(1, int(round(n)))


DAILY_QUEST_REWARD_XP = 60

# Pool for deterministic daily rotation. Same date => same 3 objectives.
DAILY_QUEST_POOL: tuple[DailyQuestDef, ...] = (
    DailyQuestDef(
        key="first_strike",
        title="First Strike",
        description="Complete your first quest check-in today.",
        icon="target",
        evaluate=lambda c: DailyQuestProgress(
            current=c.checked_in_today_count,
            target=1,
            complete=c.checked_in_today_count >= 1,
        ),
    ),
    DailyQuestDef(
        key="combo_session",
        title="Combo Session",
        description="Complete multiple quest check-ins today.",
        icon="swords",
        evaluate=lambda c: (
            lambda target: DailyQuestProgress(
                current=c.checked_in_today_count,
                target=target,
                complete=c.checked_in_today_count >= target,
            )
        )(_clamp_min_one(3 if c.level >= 10 else 2)),
    ),
    DailyQuestDef(
        key="streak_guard",
        title="Streak Guard",
        description="Maintain at least one strong streak.",
        icon="shield",
        evaluate=lambda c: (
            lambda target: DailyQuestProgress(
                current=c.max_streak,
                target=target,
                complete=c.max_streak >= target,
            )
        )(_clamp_min_one(7 if c.level >= 12 else 4)),
    ),
    DailyQuestDef(
        key="active_squad",
        title="Active Squad",
        description="Keep a stable set of active quests.",
        icon="sparkles",
        evaluate=lambda c: (
            lambda target: DailyQuestProgress(
                current=c.active_count,
                target=target,
                complete=c.active_count >= target,
            )
        )(_clamp_min_one(4 if c.level >= 10 else 3)),
    ),
    DailyQuestDef(
        key="streak_unit",
        title="Streak Unit",
        description="Have multiple quests with 3+ streak days.",
        icon="flame",
        evaluate=lambda c: (
            lambda target: DailyQuestProgress(
                current=c.active_with_streak_3,
                target=target,
                complete=c.active_with_streak_3 >= target,
            )
        )(_clamp_min_one(2 if c.level >= 10 else 1)),
    ),
    DailyQuestDef(
        key="clean_sweep",
        title="Clean Sweep",
        description="Check in all active quests today.",
        icon="target",
        evaluate=lambda c: (
            lambda target: DailyQuestProgress(
                current=c.checked_in_today_count,
                target=target,
                complete=c.active_count > 0 and c.checked_in_today_count >= target,
            )
        )(_clamp_min_one(c.active_count)),
    ),
)
