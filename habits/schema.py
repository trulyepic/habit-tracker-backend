import graphene
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from graphene_django import DjangoObjectType

from .models import Habit, CheckIn, PlayerProfile
from habits.services import habit_stats
from .services.gamification import apply_checkin_reward, reconcile_profile_from_history
from habits.services.daily_quests import claim_daily_quest_reward, get_daily_quest_chain
from habits.services.weekly_bosses import claim_weekly_boss_reward, get_weekly_boss_encounter
from habits.services.titles import resolve_title_state
from habits.services.streaks import (
    claim_recovery_quest_reward,
    consume_streak_freeze,
    maybe_start_recovery_quest,
    recovery_quest_status,
)


class HabitType(DjangoObjectType):
    total_checkins = graphene.Int()
    checked_in_today = graphene.Boolean()
    last_7_days_count = graphene.Int()
    current_streak = graphene.Int()
    best_streak = graphene.Int()
    used_freeze_today = graphene.Boolean()

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

    def resolve_used_freeze_today(self, info):
        return habit_stats.used_freeze_today(self)


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


class BossBuffType(graphene.ObjectType):
    key = graphene.String(required=True)
    name = graphene.String(required=True)
    description = graphene.String(required=True)


class BossType(graphene.ObjectType):
    key = graphene.String(required=True)
    name = graphene.String(required=True)
    subtitle = graphene.String(required=True)
    icon = graphene.String(required=True)
    tint = graphene.String(required=True)
    rarity = graphene.String(required=True)
    difficulty = graphene.String(required=True)
    mechanics = graphene.List(graphene.String, required=True)
    buffs = graphene.List(BossBuffType, required=True)
    is_weekly = graphene.Boolean(required=True)


class DailyQuestChainType(graphene.ObjectType):
    date_key = graphene.String(required=True)
    boss = graphene.Field(BossType, required=True)
    quests = graphene.List(DailyQuestObjectiveType, required=True)
    completed_count = graphene.Int(required=True)
    total_count = graphene.Int(required=True)
    completion_pct = graphene.Int(required=True)
    is_complete = graphene.Boolean(required=True)
    reward_xp = graphene.Int(required=True)
    reward_claimed = graphene.Boolean(required=True)
    reward_claimable = graphene.Boolean(required=True)
    reward_claimed_at = graphene.DateTime()
    reward_awarded_xp = graphene.Int(required=True)


class WeeklyBossEncounterType(graphene.ObjectType):
    week_key = graphene.String(required=True)
    week_start = graphene.String(required=True)
    week_end = graphene.String(required=True)
    boss = graphene.Field(BossType, required=True)
    quests = graphene.List(DailyQuestObjectiveType, required=True)
    completed_count = graphene.Int(required=True)
    total_count = graphene.Int(required=True)
    completion_pct = graphene.Int(required=True)
    is_complete = graphene.Boolean(required=True)
    reward_xp = graphene.Int(required=True)
    reward_claimed = graphene.Boolean(required=True)
    reward_claimable = graphene.Boolean(required=True)
    reward_claimed_at = graphene.DateTime()
    reward_awarded_xp = graphene.Int(required=True)


class PlayerProfileType(DjangoObjectType):
    current_title = graphene.Field(lambda: TitleType)
    next_title = graphene.Field(lambda: TitleType)
    next_title_progress_pct = graphene.Int()
    next_title_missing_levels = graphene.Int()
    next_title_missing_achievements = graphene.List(graphene.String)
    is_max_title = graphene.Boolean()
    unlocked_titles = graphene.List(lambda: TitleType)
    streak_freeze_charges = graphene.Int()
    recovery_quest = graphene.Field(lambda: RecoveryQuestType)

    class Meta:
        model = PlayerProfile
        fields = (
            "total_xp",
            "level",
            "total_minutes_logged",
            "achievements_unlocked",
            "streak_freeze_charges",
        )

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

    def resolve_recovery_quest(self, info):
        user = info.context.user
        return recovery_quest_status(user=user, profile=self)


class TitleType(graphene.ObjectType):
    key = graphene.String(required=True)
    name = graphene.String(required=True)
    emoji = graphene.String(required=True)
    flavor = graphene.String(required=True)
    min_level = graphene.Int(required=True)
    required_achievements = graphene.List(graphene.String, required=True)


class RecoveryQuestType(graphene.ObjectType):
    active = graphene.Boolean(required=True)
    start_date = graphene.String()
    progress_days = graphene.Int(required=True)
    target_days = graphene.Int(required=True)
    complete = graphene.Boolean(required=True)
    claimed = graphene.Boolean(required=True)
    reward_xp = graphene.Int(required=True)
    claimable = graphene.Boolean(required=True)


class ActivityEventType(graphene.ObjectType):
    id = graphene.ID(required=True)
    action = graphene.String(required=True)
    habit_name = graphene.String(required=True)
    date = graphene.Date(required=True)
    created_at = graphene.DateTime(required=True)
    minutes_spent = graphene.Int()
    xp_awarded = graphene.Int(required=True)
    used_freeze = graphene.Boolean(required=True)


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
        if maybe_start_recovery_quest(user=user, profile=profile):
            profile.save(update_fields=["recovery_quest_started_on", "updated_at"])
        return profile


class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    habits = graphene.List(HabitType, active_only=graphene.Boolean(required=False))
    habit = graphene.Field(HabitType, id=graphene.ID(required=True))
    daily_quest_chain = graphene.Field(DailyQuestChainType)
    weekly_boss_encounter = graphene.Field(WeeklyBossEncounterType)
    recent_activity = graphene.List(ActivityEventType, limit=graphene.Int(required=False))

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

    def resolve_weekly_boss_encounter(self, info):
        user = info.context.user
        if user.is_anonymous:
            return None
        return get_weekly_boss_encounter(user=user)

    def resolve_recent_activity(self, info, limit=20):
        user = info.context.user
        if user.is_anonymous:
            return []

        safe_limit = max(1, min(int(limit or 20), 100))
        checkins = (
            CheckIn.objects.filter(habit__owner=user)
            .select_related("habit")
            .order_by("-date", "-created_at")[:safe_limit]
        )
        created_habits = Habit.objects.filter(owner=user).only("id", "name", "created_at").order_by("-created_at")[:safe_limit]

        events = []
        for c in checkins:
            events.append(
                {
                    "id": c.id,
                    "action": "checkin",
                    "habit_name": c.habit.name,
                    "date": c.date,
                    "created_at": c.created_at,
                    "minutes_spent": c.minutes_spent,
                    "xp_awarded": c.xp_awarded,
                    "used_freeze": c.used_freeze,
                }
            )

        for h in created_habits:
            events.append(
                {
                    "id": f"habit-{h.id}",
                    "action": "habit_created",
                    "habit_name": h.name,
                    "date": h.created_at.date(),
                    "created_at": h.created_at,
                    "minutes_spent": None,
                    "xp_awarded": 0,
                    "used_freeze": False,
                }
            )

        events.sort(key=lambda e: (e["created_at"], str(e["id"])), reverse=True)
        return [
            {
                "id": c["id"],
                "action": c["action"],
                "habit_name": c["habit_name"],
                "date": c["date"],
                "created_at": c["created_at"],
                "minutes_spent": c["minutes_spent"],
                "xp_awarded": c["xp_awarded"],
                "used_freeze": c["used_freeze"],
            }
            for c in events[:safe_limit]
        ]
    


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

        # If today was protected by freeze, "upgrade" it to a real check-in and award XP.
        if not created and checkin.used_freeze:
            checkin.used_freeze = False
            if minutes_spent is not None:
                checkin.minutes_spent = minutes_spent
                checkin.save(update_fields=["used_freeze", "minutes_spent"])
            else:
                checkin.save(update_fields=["used_freeze"])

            streak = habit_stats.current_streak(habit)
            total_for_user = CheckIn.objects.filter(habit__owner=user, used_freeze=False).count()
            profile = apply_checkin_reward(
                user=user,
                checkin=checkin,
                current_streak=streak,
                total_checkins_for_user=total_for_user,
            )
            return cls(checkin=checkin, created=True, habit=habit, profile=profile)

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
        total_for_user = CheckIn.objects.filter(habit__owner=user, used_freeze=False).count()

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
    claim_reason = graphene.String(required=True)
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
            claim_reason=result["claim_reason"],
            awarded_xp=result["awarded_xp"],
            chain=result["chain"],
            profile=result["profile"],
        )


class ClaimWeeklyBossReward(graphene.Mutation):
    claimed = graphene.Boolean(required=True)
    claim_reason = graphene.String(required=True)
    awarded_xp = graphene.Int(required=True)
    encounter = graphene.Field(WeeklyBossEncounterType)
    profile = graphene.Field(PlayerProfileType)

    @classmethod
    def mutate(cls, root, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("Authentication required")

        result = claim_weekly_boss_reward(user=user)
        return cls(
            claimed=result["claimed"],
            claim_reason=result["claim_reason"],
            awarded_xp=result["awarded_xp"],
            encounter=result["encounter"],
            profile=result["profile"],
        )


class ConsumeStreakFreeze(graphene.Mutation):
    consumed = graphene.Boolean(required=True)
    reason = graphene.String()
    habit = graphene.Field(HabitType)
    profile = graphene.Field(PlayerProfileType)

    class Arguments:
        habit_id = graphene.ID(required=True)

    @classmethod
    def mutate(cls, root, info, habit_id):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("Authentication required")

        result = consume_streak_freeze(user=user, habit_id=habit_id)
        return cls(
            consumed=result["consumed"],
            reason=result["reason"],
            habit=result["habit"],
            profile=result["profile"],
        )


class ClaimRecoveryQuestReward(graphene.Mutation):
    claimed = graphene.Boolean(required=True)
    awarded_xp = graphene.Int(required=True)
    profile = graphene.Field(PlayerProfileType)
    recovery_quest = graphene.Field(RecoveryQuestType)

    @classmethod
    def mutate(cls, root, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception("Authentication required")

        result = claim_recovery_quest_reward(user=user)
        return cls(
            claimed=result["claimed"],
            awarded_xp=result["awarded_xp"],
            profile=result["profile"],
            recovery_quest=result["recovery_quest"],
        )


class Mutation(graphene.ObjectType):
    create_habit = CreateHabit.Field()
    toggle_habit_active = ToggleHabitActive.Field()
    check_in_today = CheckInToday.Field()
    delete_habit = DeleteHabit.Field()
    claim_daily_quest_reward = ClaimDailyQuestReward.Field()
    claim_weekly_boss_reward = ClaimWeeklyBossReward.Field()
    consume_streak_freeze = ConsumeStreakFreeze.Field()
    claim_recovery_quest_reward = ClaimRecoveryQuestReward.Field()
