import os


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


# Check-in XP economy
CHECKIN_BASE_XP = _int_env("CHECKIN_BASE_XP", 10)
CHECKIN_STREAK_BONUS_PER_DAY = _int_env("CHECKIN_STREAK_BONUS_PER_DAY", 2)
CHECKIN_STREAK_BONUS_CAP = _int_env("CHECKIN_STREAK_BONUS_CAP", 20)
CHECKIN_MINUTES_BONUS_PER = max(_int_env("CHECKIN_MINUTES_BONUS_PER", 10), 1)  # +1 XP per N minutes
CHECKIN_MINUTES_BONUS_CAP = _int_env("CHECKIN_MINUTES_BONUS_CAP", 30)
CHECKIN_MINUTES_MIN = max(_int_env("CHECKIN_MINUTES_MIN", 1), 1)
CHECKIN_MINUTES_MAX = max(_int_env("CHECKIN_MINUTES_MAX", 720), CHECKIN_MINUTES_MIN)

# Daily quests
DAILY_QUEST_REWARD_XP = _int_env("DAILY_QUEST_REWARD_XP", 60)
WEEKLY_BOSS_REWARD_XP = _int_env("WEEKLY_BOSS_REWARD_XP", 180)

# Streak safety / recovery loop
MAX_FREEZE_CHARGES = _int_env("MAX_FREEZE_CHARGES", 3)
FREEZE_LEVEL_MILESTONE_INTERVAL = max(_int_env("FREEZE_LEVEL_MILESTONE_INTERVAL", 5), 1)
RECOVERY_QUEST_REWARD_XP = _int_env("RECOVERY_QUEST_REWARD_XP", 40)
RECOVERY_QUEST_TARGET_DAYS = max(_int_env("RECOVERY_QUEST_TARGET_DAYS", 2), 1)
RECOVERY_QUEST_WINDOW_DAYS = max(_int_env("RECOVERY_QUEST_WINDOW_DAYS", 5), 1)
