from habits.services.achievements import (
    ACHIEVEMENTS,
    build_context,
    evaluate_new_unlocks,
    total_bonus_xp_for_keys,
)


def test_evaluate_new_unlocks_unlocks_all_eligible_achievements():
    unlocked, newly_unlocked = evaluate_new_unlocks(
        unlocked={},
        context=build_context(
            total_checkins=100,
            streak_days=30,
            total_minutes_logged=600,
        ),
        now_iso="2026-03-01T10:00:00+00:00",
    )

    assert set(newly_unlocked) == {"first_step", "on_fire", "ten_hours", "iron_will", "centurion"}
    for key in newly_unlocked:
        assert unlocked[key] == "2026-03-01T10:00:00+00:00"


def test_evaluate_new_unlocks_skips_already_unlocked_achievements():
    unlocked, newly_unlocked = evaluate_new_unlocks(
        unlocked={"first_step": "2026-02-01T10:00:00+00:00"},
        context=build_context(
            total_checkins=100,
            streak_days=10,
            total_minutes_logged=600,
        ),
        now_iso="2026-03-01T10:00:00+00:00",
    )

    assert unlocked["first_step"] == "2026-02-01T10:00:00+00:00"
    assert "first_step" not in newly_unlocked
    assert set(newly_unlocked) == {"on_fire", "ten_hours", "centurion"}


def test_evaluate_new_unlocks_unlocks_iron_will_at_30_day_streak():
    unlocked, newly_unlocked = evaluate_new_unlocks(
        unlocked={},
        context=build_context(
            total_checkins=20,
            streak_days=30,
            total_minutes_logged=120,
        ),
        now_iso="2026-03-01T10:00:00+00:00",
    )

    assert "iron_will" in newly_unlocked
    assert unlocked["iron_will"] == "2026-03-01T10:00:00+00:00"


def test_evaluate_new_unlocks_unlocks_centurion_at_100_total_checkins():
    unlocked, newly_unlocked = evaluate_new_unlocks(
        unlocked={},
        context=build_context(
            total_checkins=100,
            streak_days=3,
            total_minutes_logged=120,
        ),
        now_iso="2026-03-01T10:00:00+00:00",
    )

    assert "centurion" in newly_unlocked
    assert unlocked["centurion"] == "2026-03-01T10:00:00+00:00"


def test_total_bonus_xp_for_keys_uses_catalog_definitions():
    expected = (
        ACHIEVEMENTS["first_step"].bonus_xp
        + ACHIEVEMENTS["on_fire"].bonus_xp
    )
    actual = total_bonus_xp_for_keys(["first_step", "on_fire", "unknown_key"])
    assert actual == expected
