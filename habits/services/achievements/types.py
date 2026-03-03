from dataclasses import dataclass
from typing import Callable, Optional

DEFAULT_RARITY_BONUS_XP = {
    "common": 10,
    "rare": 25,
    "epic": 75,
    "legendary": 200,
}


@dataclass(frozen=True)
class AchievementContext:
    """Inputs used to evaluate achievement unlock rules."""

    total_checkins: int
    streak_days: int
    total_minutes_logged: int
    weekly_boss_wins: int = 0
    weekly_hard_boss_wins: int = 0
    weekly_legendary_boss_wins: int = 0


@dataclass(frozen=True)
class AchievementDef:
    """Catalog definition for one achievement."""

    rarity: str
    rule: Callable[[AchievementContext], bool]
    bonus_xp_override: Optional[int]
    description: str = ""

    @property
    def bonus_xp(self) -> int:
        if self.bonus_xp_override is not None:
            return int(self.bonus_xp_override)
        return int(DEFAULT_RARITY_BONUS_XP.get(self.rarity, 0))
