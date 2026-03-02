import graphene
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from graphene_django import DjangoObjectType

from .models import Habit, CheckIn, PlayerProfile
from habits.services import habit_stats
from .services.gamification import apply_checkin_reward, reconcile_profile_from_history
from habits.services.daily_quests import claim_daily_quest_reward, get_daily_quest_chain
from habits.services.titles import resolve_title_state


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
        fields = ("id", "habit", "date", "created_at", "minutes_spent", "xp_awarded")


class DailyQuestObjectiveType(graphene.ObjectType):
    key = graphene.String(required=True)
    title = graphene.String(required=True)
    description = graphene.String(required=True)
    icon = graphene.String(required=True)
    current = graphene.Int(required=True)
    target = graphene.Int(required=True)
    complete = graphene.Boolean(required=True)


class DailyQuestChainType(graphene.ObjectType):
    date_key = graphene.String(required=True)
    quests = graphene.List(DailyQuestObjectiveType, required=True)
    completed_count = graphene.Int(required=True)
    total_count = graphene.Int(required=True)
    completion_pct = graphene.Int(required=True)
    is_complete = graphene.Boolean(required=True)
    reward_xp = graphene.Int(required=True)
    reward_claimed = graphene.Boolean(required=True)
    reward_claimable = graphene.Boolean(required=True)


class PlayerProfileType(DjangoObjectType):
    current_title = graphene.Field(lambda: TitleType)
    next_title = graphene.Field(lambda: TitleType)
    next_title_progress_pct = graphene.Int()
    next_title_missing_levels = graphene.Int()
    next_title_missing_achievements = graphene.List(graphene.String)
    is_max_title = graphene.Boolean()
    unlocked_titles = graphene.List(lambda: TitleType)

    class Meta:
        model = PlayerProfile
        fields = ("total_xp", "level", "total_minutes_logged", "achievements_unlocked")

    @staticmethod
    def _title_state_for_profile(profile):
        # Graphene passes the Django model instance as resolver root.
        return resolve_title_state(
            level=int(profile.level or 1),
            achievements_unlocked=profile.achievements_unlocked or {},
        )

    def resolve_current_title(self, info):
        return PlayerProfileType._title_state_for_profile(self)["current_title"]

    def resolve_next_title(self, info):
        return PlayerProfileType._title_state_for_profile(self)["next_title"]

    def resolve_next_title_progress_pct(self, info):
        return PlayerProfileType._title_state_for_profile(self)["next_title_progress_pct"]

    def resolve_next_title_missing_levels(self, info):
        return PlayerProfileType._title_state_for_profile(self)["next_title_missing_levels"]

    def resolve_next_title_missing_achievements(self, info):
        return PlayerProfileType._title_state_for_profile(self)["next_title_missing_achievements"]

    def resolve_is_max_title(self, info):
        return PlayerProfileType._title_state_for_profile(self)["is_max_title"]

    def resolve_unlocked_titles(self, info):
        return PlayerProfileType._title_state_for_profile(self)["unlocked_titles"]


class TitleType(graphene.ObjectType):
    key = graphene.String(required=True)
    name = graphene.String(required=True)
    emoji = graphene.String(required=True)
    flavor = graphene.String(required=True)
    min_level = graphene.Int(required=True)
    required_achievements = graphene.List(graphene.String, required=True)


class UserType(DjangoObjectType):
    player_profile = graphene.Field(PlayerProfileType)

    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email")

    def resolve_player_profile(self, info):
        user = info.context.user
        if user.is_anonymous:
            return None
        profile = reconcile_profile_from_history(user=user)
        return profile


class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    habits = graphene.List(HabitType, active_only=graphene.Boolean(required=False))
    habit = graphene.Field(HabitType, id=graphene.ID(required=True))
    daily_quest_chain = graphene.Field(DailyQuestChainType)

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

    def resolve_daily_quest_chain(self, info):
        user = info.context.user
        if user.is_anonymous:
            return None
        return get_daily_quest_chain(user=user)
    


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
        minutes_spent = graphene.Int(required=False)

    checkin = graphene.Field(CheckInType)
    created = graphene.Boolean(required=True)
    habit = graphene.Field(HabitType)
    profile = graphene.Field(PlayerProfileType)

    @classmethod
    def mutate(cls, root, info, habit_id, date=None, minutes_spent=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("Authentication required")

        habit = Habit.objects.get(pk=habit_id, owner=user)
        checkin_date = date or timezone.localdate()

        checkin, created = CheckIn.objects.get_or_create(
            habit=habit,
            date=checkin_date,
            defaults={"minutes_spent": minutes_spent}
        )

        # If it already existed, do NOT double-award XP or overwrite minutes
        if not created:
            profile, _ = PlayerProfile.objects.get_or_create(user=user)
            return cls(checkin=checkin, created=False, habit=habit, profile=profile)

        # Newly created: award XP + minutes + achievements
        # ensure minutes is set for the created checkin (defaults handled, but keep safe)
        if minutes_spent is not None and checkin.minutes_spent != minutes_spent:
            checkin.minutes_spent = minutes_spent
            checkin.save(update_fields=["minutes_spent"])

        # streak uses existing habit_stats logic (prefetch not required here)
        streak = habit_stats.current_streak(habit)

        # total checkins for users (for first_step achievement)
        total_for_user = CheckIn.objects.filter(habit__owner=user).count()

        profile = apply_checkin_reward(
            user=user,
            checkin=checkin,
            current_streak=streak,
            total_checkins_for_user=total_for_user
        )

        return cls(checkin=checkin, created=True, habit=habit, profile=profile)


        

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


class ClaimDailyQuestReward(graphene.Mutation):
    claimed = graphene.Boolean(required=True)
    awarded_xp = graphene.Int(required=True)
    chain = graphene.Field(DailyQuestChainType)
    profile = graphene.Field(PlayerProfileType)

    @classmethod
    def mutate(cls, root, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("Authentication required")

        result = claim_daily_quest_reward(user=user)
        return cls(
            claimed=result["claimed"],
            awarded_xp=result["awarded_xp"],
            chain=result["chain"],
            profile=result["profile"],
        )


class Mutation(graphene.ObjectType):
    create_habit = CreateHabit.Field()
    toggle_habit_active = ToggleHabitActive.Field()
    check_in_today = CheckInToday.Field()
    delete_habit = DeleteHabit.Field()
    claim_daily_quest_reward = ClaimDailyQuestReward.Field()
