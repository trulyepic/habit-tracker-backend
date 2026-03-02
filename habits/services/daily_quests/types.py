from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DailyQuestContext:
    active_count: int
    checked_in_today_count: int
    max_streak: int
    active_with_streak_3: int
    level: int


@dataclass(frozen=True)
class DailyQuestProgress:
    current: int
    target: int
    complete: bool


@dataclass(frozen=True)
class DailyQuestDef:
    key: str
    title: str
    description: str
    icon: str
    evaluate: Callable[[DailyQuestContext], DailyQuestProgress]
