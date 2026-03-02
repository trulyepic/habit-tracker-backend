from dataclasses import dataclass


@dataclass(frozen=True)
class TitleDef:
    """Backend title definition used for progression and API responses."""

    key: str
    name: str
    emoji: str
    flavor: str
    min_level: int
    required_achievements: tuple[str, ...]
