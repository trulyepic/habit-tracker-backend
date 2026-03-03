from habits.services.bosses.catalog import get_active_daily_bosses, get_active_weekly_bosses
from habits.services.bosses.types import BossDef


def _pick_rotating_boss(*, pool: list[BossDef], seed: int) -> BossDef:
    if not pool:
        raise ValueError("No active bosses configured for this rotation")
    return pool[abs(int(seed)) % len(pool)]


def _serialize_boss(*, boss: BossDef, is_weekly: bool) -> dict:
    return {
        "key": boss.key,
        "name": boss.name,
        "subtitle": boss.subtitle,
        "icon": boss.icon,
        "tint": boss.tint,
        "rarity": boss.rarity,
        "difficulty": boss.difficulty,
        "mechanics": list(boss.mechanics),
        "buffs": [
            {
                "key": buff.key,
                "name": buff.name,
                "description": buff.description,
            }
            for buff in boss.buffs
        ],
        "is_weekly": bool(is_weekly),
    }


def resolve_daily_boss(*, seed: int) -> dict:
    boss = _pick_rotating_boss(pool=get_active_daily_bosses(), seed=seed)
    return _serialize_boss(boss=boss, is_weekly=False)


def resolve_weekly_boss(*, seed: int) -> dict:
    boss = _pick_rotating_boss(pool=get_active_weekly_bosses(), seed=seed)
    return _serialize_boss(boss=boss, is_weekly=True)
