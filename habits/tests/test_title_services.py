from habits.services.titles import resolve_title_state


def test_resolve_title_state_defaults_to_rookie_when_no_achievements():
    state = resolve_title_state(level=1, achievements_unlocked={})

    assert state["current_title"]["key"] == "rookie"
    assert state["next_title"]["key"] == "pathfinder"
    assert state["is_max_title"] is False


def test_resolve_title_state_advances_with_level_and_achievements():
    state = resolve_title_state(
        level=12,
        achievements_unlocked={
            "first_step": "2026-03-01T10:00:00+00:00",
            "on_fire": "2026-03-01T10:00:00+00:00",
            "ten_hours": "2026-03-01T10:00:00+00:00",
            "iron_will": "2026-03-01T10:00:00+00:00",
        },
    )

    assert state["current_title"]["key"] == "iron_vanguard"
    assert state["next_title"]["key"] == "centurion_prime"
    assert "centurion" in state["next_title_missing_achievements"]


def test_resolve_title_state_reports_max_title_when_track_completed():
    state = resolve_title_state(
        level=30,
        achievements_unlocked={
            "first_step": "2026-03-01T10:00:00+00:00",
            "on_fire": "2026-03-01T10:00:00+00:00",
            "ten_hours": "2026-03-01T10:00:00+00:00",
            "iron_will": "2026-03-01T10:00:00+00:00",
            "centurion": "2026-03-01T10:00:00+00:00",
            "raid_initiate": "2026-03-01T10:00:00+00:00",
            "behemoth_bane": "2026-03-01T10:00:00+00:00",
            "voidbreaker": "2026-03-01T10:00:00+00:00",
        },
    )

    assert state["current_title"]["key"] == "legend_of_routine"
    assert state["next_title"] is None
    assert state["is_max_title"] is True
