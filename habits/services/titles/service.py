from habits.services.titles.catalog import TITLE_TRACK
from habits.services.titles.types import TitleDef


def _as_payload(title: TitleDef) -> dict:
    return {
        "key": title.key,
        "name": title.name,
        "emoji": title.emoji,
        "flavor": title.flavor,
        "min_level": title.min_level,
        "required_achievements": list(title.required_achievements),
    }


def _has_requirements(title: TitleDef, *, level: int, unlocked_keys: set[str]) -> bool:
    if level < title.min_level:
        return False
    return all(k in unlocked_keys for k in title.required_achievements)


def resolve_title_state(*, level: int, achievements_unlocked: dict | None) -> dict:
    """Resolve title progression from profile level and unlocked achievements."""

    unlocked_map = achievements_unlocked or {}
    unlocked_keys = set(unlocked_map.keys())

    unlocked_titles = [
        title for title in TITLE_TRACK if _has_requirements(title, level=level, unlocked_keys=unlocked_keys)
    ]

    current = unlocked_titles[-1] if unlocked_titles else TITLE_TRACK[0]
    current_index = TITLE_TRACK.index(current)
    next_title = TITLE_TRACK[current_index + 1] if current_index + 1 < len(TITLE_TRACK) else None

    if next_title is None:
        return {
            "current_title": _as_payload(current),
            "next_title": None,
            "next_title_progress_pct": 100,
            "next_title_missing_levels": 0,
            "next_title_missing_achievements": [],
            "is_max_title": True,
            "unlocked_titles": [_as_payload(t) for t in unlocked_titles],
        }

    next_missing_achievements = [
        k for k in next_title.required_achievements if k not in unlocked_keys
    ]
    next_missing_levels = max(next_title.min_level - level, 0)

    level_progress = min(level / next_title.min_level, 1) if next_title.min_level > 0 else 1
    achievement_progress = (
        (len(next_title.required_achievements) - len(next_missing_achievements))
        / len(next_title.required_achievements)
        if next_title.required_achievements
        else 1
    )

    next_title_progress_pct = round((level_progress * 0.6 + achievement_progress * 0.4) * 100)

    return {
        "current_title": _as_payload(current),
        "next_title": _as_payload(next_title),
        "next_title_progress_pct": int(next_title_progress_pct),
        "next_title_missing_levels": int(next_missing_levels),
        "next_title_missing_achievements": list(next_missing_achievements),
        "is_max_title": False,
        "unlocked_titles": [_as_payload(t) for t in unlocked_titles],
    }
