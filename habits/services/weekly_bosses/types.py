from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class WeeklyBossContext:
    active_count: int
    weekly_checkin_events: int
    weekly_active_habits_touched: int
    max_streak: int
    active_with_streak_5: int
    level: int


@dataclass(frozen=True)
class WeeklyBossProgress:
    current: int
    target: int
    complete: bool


@dataclass(frozen=True)
class WeeklyBossObjectiveDef:
    key: str
    title: str
    description: str
    icon: str
    evaluate: Callable[[WeeklyBossContext], WeeklyBossProgress]
