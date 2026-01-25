from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from habits.models import Habit, CheckIn
from habits.services import habit_stats

pytestmark = pytest.mark.django_db


@pytest.fixture()
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="u1",
        password="pass12345",
        email="u1@example.com",
    )


def _bulk_create_checkins(habit: Habit, dates):
    CheckIn.objects.bulk_create([CheckIn(habit=habit, date=d) for d in dates])


def test_with_habit_stats__annotates_total_checkins_checked_in_today_last_7_days_count(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="Gym")

    _bulk_create_checkins(
        habit,
        [
            today,
            today - timedelta(days=1),
            today - timedelta(days=10),
        ],
    )

    obj = habit_stats.with_habit_stats(Habit.objects.all()).get(pk=habit.pk)
    assert obj.total_checkins_anno == 3
    assert obj.checked_in_today_anno is True
    assert obj.last_7_days_count_anno == 2  # today + yesterday only


def test_total_checkins__uses_annotation_when_present(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="Read")
    _bulk_create_checkins(habit, [today, today - timedelta(days=2)])

    obj = habit_stats.with_habit_stats(Habit.objects.all()).get(pk=habit.pk)
    assert obj.total_checkins_anno == 2


def test_total_checkins__falls_back_to_db_when_annotation_missing(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="Meditate")
    _bulk_create_checkins(habit, [today])
    obj = Habit.objects.get(pk=habit.pk)

    assert habit_stats.total_checkins(obj) == 1


def test_checked_in_today__uses_annotation_when_present(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="Walk")
    _bulk_create_checkins(habit, [today])

    obj = habit_stats.with_habit_stats(Habit.objects.all()).get(pk=habit.pk)
    assert habit_stats.checked_in_today(obj) is True


def test_checked_in_today__falls_back_to_db_when_annotation_missing(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="Stretch")
    _bulk_create_checkins(habit, [today])

    obj = Habit.objects.get(pk=habit.pk)
    assert habit_stats.checked_in_today(obj) is True


def test_last_7_days_count__uses_annotation_when_present(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="Journal")
    _bulk_create_checkins(
        habit,
        [
            today,
            today - timedelta(days=3),
            today - timedelta(days=9),
        ],
    )

    obj = habit_stats.with_habit_stats(Habit.objects.all()).get(pk=habit.pk)
    assert habit_stats.last_7_days_count(obj) == 2


def test_last_7_days_count__falls_back_to_db_when_annotation_missing(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="DrinkWater")
    _bulk_create_checkins(habit, [today, today - timedelta(days=6)])

    obj = Habit.objects.get(pk=habit.pk)
    assert habit_stats.last_7_days_count(obj) == 2


def test_current_streak__prefetched__returns_zero_when_no_checkin_today_and_hits_no_db(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="NoToday")
    _bulk_create_checkins(habit, [today - timedelta(days=1), today - timedelta(days=2)])

    obj = Habit.objects.prefetch_related("checkins").get(pk=habit.pk)

    with CaptureQueriesContext(connection) as ctx:
        streak = habit_stats.current_streak(obj)

    assert streak == 0
    assert len(ctx) == 0


def test_current_streak__prefetched__counts_consecutive_days_and_hits_no_db(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="Streaky")
    _bulk_create_checkins(
        habit,
        [
            today,
            today - timedelta(days=1),
            today - timedelta(days=2),
            today - timedelta(days=5),  # break
        ],
    )

    obj = Habit.objects.prefetch_related("checkins").get(pk=habit.pk)

    with CaptureQueriesContext(connection) as ctx:
        streak = habit_stats.current_streak(obj)

    assert streak == 3
    assert len(ctx) == 0


def test_best_streak__prefetched__returns_max_run_and_hits_no_db(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="BestStreak")

    # Runs: (today..today-2) => 3
    # and (today-10..today-6) => 5  (best)
    dates = [
        today,
        today - timedelta(days=1),
        today - timedelta(days=2),
        today - timedelta(days=6),
        today - timedelta(days=7),
        today - timedelta(days=8),
        today - timedelta(days=9),
        today - timedelta(days=10),
    ]
    _bulk_create_checkins(habit, dates)

    obj = Habit.objects.prefetch_related("checkins").get(pk=habit.pk)

    with CaptureQueriesContext(connection) as ctx:
        best = habit_stats.best_streak(obj)

    assert best == 5
    assert len(ctx) == 0


def test_best_streak__non_prefetched__returns_max_run(user):
    today = timezone.localdate()
    habit = Habit.objects.create(owner=user, name="BestStreakDB")
    _bulk_create_checkins(habit, [today - timedelta(days=i) for i in range(4)])  # 4-day run

    obj = Habit.objects.get(pk=habit.pk)
    assert habit_stats.best_streak(obj) == 4
