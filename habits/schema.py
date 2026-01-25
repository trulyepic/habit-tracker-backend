import graphene
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from graphene_django import DjangoObjectType

from .models import Habit, CheckIn
from habits.services import habit_stats


class HabitType(DjangoObjectType):
    total_checkins = graphene.Int()
    checked_in_today = graphene.Boolean()
    last_7_days_count = graphene.Int()
    current_streak = graphene.Int()
    best_streak = graphene.Int()

    class Meta:
        model = Habit
        fields = ("id", "name", "description", "is_active", "created_at", "checkins")

    def resolve_total_checkins(self, info):
        return habit_stats.total_checkins(self)
    
    def resolve_checked_in_today(self, info):
        return habit_stats.checked_in_today(self)
    
    def resolve_last_7_days_count(self, info):
        return habit_stats.last_7_days_count(self)
    
    def resolve_current_streak(self, info):
        return habit_stats.current_streak(self)
    
    def resolve_best_streak(self, info):
        return habit_stats.best_streak(self)


class CheckInType(DjangoObjectType):
    class Meta:
        model = CheckIn
        fields = ("id", "habit", "date", "created_at")



class UserType(DjangoObjectType):
    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email")


class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    habits = graphene.List(HabitType, active_only=graphene.Boolean(required=False))
    habit = graphene.Field(HabitType, id=graphene.ID(required=True))

    def resolve_habits(self, info, active_only=None):
        user = info.context.user
        if user.is_anonymous:
            return Habit.objects.none()

        qs = Habit.objects.filter(owner=user).order_by("name")
        if active_only is True:
            qs = qs.filter(is_active=True)
        
        qs = habit_stats.with_habit_stats(qs).prefetch_related("checkins")
        return qs
    
    def resolve_habit(self, info, id):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("Authentication required")

        qs = habit_stats.with_habit_stats(
            Habit.objects.filter(owner=user)
        ).prefetch_related("checkins")
        return qs.get(pk=id)

    def resolve_me(self, info):
        user = info.context.user
        return None if user.is_anonymous else user
    


class CreateHabit(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        description = graphene.String(required=False)

    habit = graphene.Field(HabitType)

    def mutate(self, info, name, description=""):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("Authentication required")

        habit = Habit.objects.create(owner=user, name=name, description=description or "")
        return CreateHabit(habit=habit)
    

class ToggleHabitActive(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        is_active = graphene.Boolean(required=True)

    habit = graphene.Field(HabitType)

    def mutate(self, info, id, is_active):
        habit = Habit.objects.get(pk=id, owner=info.context.user)
        habit.is_active = is_active
        habit.save(update_fields=["is_active"])
        return ToggleHabitActive(habit=habit)
    

class CheckInToday(graphene.Mutation):
    class Arguments:
        habit_id = graphene.ID(required=True)
        date = graphene.Date(required=False)

    checkin = graphene.Field(CheckInType)
    created = graphene.Boolean(required=True)
    habit = graphene.Field(HabitType)

    @classmethod
    def mutate(cls, root, info, habit_id, date=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("Authentication required")
        habit = Habit.objects.get(pk=habit_id, owner=user)
        checkin_date = date or timezone.localdate()

        try:
            checkin = CheckIn.objects.create(habit=habit, date=checkin_date)
            return cls(checkin=checkin, created=True, habit=habit)
        except IntegrityError:
            checkin = CheckIn.objects.get(habit=habit, date=checkin_date)
            return cls(checkin=checkin, created=False, habit=habit)

        

class DeleteHabit(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    ok = graphene.Boolean(required=True)
    deleted_id = graphene.ID(required=True)

    def mutate(self, info, id):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("Authentication required")

        habit = Habit.objects.get(pk=id, owner=user)
        habit.delete()
        return DeleteHabit(ok=True, deleted_id=id)

    
class Mutation(graphene.ObjectType):
    create_habit = CreateHabit.Field()
    toggle_habit_active = ToggleHabitActive.Field()
    check_in_today = CheckInToday.Field()
    delete_habit = DeleteHabit.Field()