from habits.services.achievements.types import AchievementDef, DEFAULT_RARITY_BONUS_XP

# Global rarity defaults. Individual achievements can override with bonus_xp_override.
RARITY_BONUS_XP = DEFAULT_RARITY_BONUS_XP

# Single source of truth for backend unlock rules.
# Add new achievements here and frontend can mirror key + copy + rarity.
ACHIEVEMENTS: dict[str, AchievementDef] = {
    "first_step": AchievementDef(
        rarity="common",
        rule=lambda c: c.total_checkins >= 1,
        bonus_xp_override=None,
        description="Complete your first check-in.",
    ),
    "on_fire": AchievementDef(
        rarity="rare",
        rule=lambda c: c.streak_days >= 7,
        bonus_xp_override=None,
        description="Reach a 7-day streak on any habit.",
    ),
    "ten_hours": AchievementDef(
        rarity="rare",
        rule=lambda c: c.total_minutes_logged >= 600,
        bonus_xp_override=None,
        description="Log 10 hours total time invested.",
    ),
    "twenty_five_hours": AchievementDef(
        rarity="epic",
        rule=lambda c: c.total_minutes_logged >= 1500,
        bonus_xp_override=None,
        description="Log 25 total hours across all habits.",
    ),
    "hundred_hours": AchievementDef(
        rarity="legendary",
        rule=lambda c: c.total_minutes_logged >= 6000,
        bonus_xp_override=None,
        description="Log 100 total hours across all habits.",
    ),
    "iron_will": AchievementDef(
        rarity="epic",
        rule=lambda c: c.streak_days >= 30,
        bonus_xp_override=None,
        description="Reach a 30-day streak on any habit.",
    ),
    "centurion": AchievementDef(
        rarity="legendary",
        rule=lambda c: c.total_checkins >= 100,
        bonus_xp_override=None,
        description="Complete 100 total check-ins across all habits.",
    ),
    "raid_initiate": AchievementDef(
        rarity="rare",
        rule=lambda c: c.weekly_boss_wins >= 1,
        bonus_xp_override=None,
        description="Claim your first Weekly Boss reward.",
    ),
    "behemoth_bane": AchievementDef(
        rarity="epic",
        rule=lambda c: c.weekly_hard_boss_wins >= 1,
        bonus_xp_override=None,
        description="Defeat a hard Weekly Boss.",
    ),
    "voidbreaker": AchievementDef(
        rarity="legendary",
        rule=lambda c: c.weekly_legendary_boss_wins >= 2,
        bonus_xp_override=None,
        description="Defeat two legendary Weekly Bosses.",
    ),
}
