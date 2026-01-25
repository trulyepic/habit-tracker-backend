from __future__ import annotations
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

class Habit(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='habits',
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='unique_habit_name_per_user')
        ]

    if TYPE_CHECKING:
        # Django dynamically injects this via related_name="checkins"
        checkins = None

    def __str__(self) -> str:
        return self.name
    

class CheckIn(models.Model):
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE,
                              related_name="checkins")
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["habit", "date"], name="unique_checkin_per_habit_per_day")
        ]
        ordering = ["-date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.habit.name} @ {self.date}"
