from datetime import timedelta
from django.utils import timezone
from habits.models import Habit
from django.db.models import Count, Exists, OuterRef, Q, Subquery

from habits.models import CheckIn, Habit


def with_habit_stats(qs):
    """
    Adds efficient annotations used by derived GraphQL fields.

    - total_checkins_anno
    - last_7_days_count_anno
    -checked_in_today_anno
    """
    today = timezone.localdate()
    start = today - timedelta(days=6)

    today_checkin_exists = CheckIn.objects.filter(habit_id=OuterRef("pk"), date=today)

    return qs.annotate(
        total_checkins_anno=Count("checkins", distinct=True),
        last_7_days_count_anno=Count(
            "checkins",
            filter=Q(checkins__date__range=(start, today)),
            distinct=True,
        ),
        checked_in_today_anno=Exists(today_checkin_exists),
    )

def _prefetched_checkin_dates_or_none(habit):
    """
    If `checkins` were prefetched, Django stores them in _prefetched_objects_cache
    We can use that to avoid DB queries.
    """

    cache = getattr(habit, "_prefetched_objects_cache", None) or {}
    if "checkins" not in cache:
        return None
    
    # cache["checkins"] is a list of CheckIn objects
    # We only need dates (unique)
    dates = {ci.date for ci in cache["checkins"]}
    return dates


def total_checkins(habit: Habit) -> int:
    val = getattr(habit, "total_checkins_anno", None)
    if val is not None:
        return int(val)
    return habit.checkins.count()


def checked_in_today(habit: Habit) -> bool:
    val = getattr(habit, "checked_in_today_anno", None)
    if val is not None:
        return bool(val)
    today = timezone.localdate()
    return habit.checkins.filter(date=today).exists()


def last_7_days_count(habit: Habit) -> int:
    val = getattr(habit, "last_7_days_count_anno", None)
    if val is not None:
        return int(val)
    today = timezone.localdate()
    start = today - timedelta(days=6)
    return habit.checkins.filter(date__range=(start, today)).count()


def current_streak(habit: Habit) -> int:
    # Keep streak logic as-is for now (harder to annotate cleanly).
    today = timezone.localdate()

    prefetched_dates = _prefetched_checkin_dates_or_none(habit)
    if prefetched_dates is not None:
        streak = 0
        day =today
        while day in prefetched_dates:
            streak +=1
            day -= timedelta(days=1)
        return streak

    # Fallback: DB-based
    dates = list(
        habit.checkins.filter(date__lte=today)
        .values_list("date", flat=True)
        .distinct()
        .order_by("-date")
    )
    if not dates or dates[0] != today:
        return 0
    
    streak = 1
    expected = today - timedelta(days=1)
    for d in dates[1:]:
        if d == expected:
            streak +=1
            expected -= timedelta(days=1)
        elif d < expected:
            break
    return streak


def best_streak(habit: Habit) -> int:
    """
    Docstring for best_streak 
    Max consecutive-day streak across all checkins.
    Uses prefetched checkins if available; otherwise queries once.
    
    :param habit:
    :return:
    :rtype: int
    """
    prefetched_dates = _prefetched_checkin_dates_or_none(habit)
    if prefetched_dates is not None:
        dates = sorted(prefetched_dates)
    else:
        dates = list(
            habit.checkins.values_list("date", flat=True)
            .distinct()
            .order_by("date")
        )
    if not dates:
        return 0
    
    best = 1
    cur = 1
    for prev, nxt in zip(dates, dates[1:]):
        if nxt == prev + timedelta(days=1):
            cur +=1
            if cur > best:
                best = cur
        else:
            cur = 1
    return best