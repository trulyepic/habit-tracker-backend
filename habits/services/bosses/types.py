from dataclasses import dataclass


@dataclass(frozen=True)
class BossBuffDef:
    key: str
    name: str
    description: str


@dataclass(frozen=True)
class BossDef:
    key: str
    name: str
    subtitle: str
    icon: str
    tint: str
    rarity: str
    difficulty: str
    mechanics: tuple[str, ...]
    buffs: tuple[BossBuffDef, ...]
    active: bool = True
    archived: bool = False
