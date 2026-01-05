import graphene
from habits.schema import Query as HabitsQuery, Mutation as HabitsMutation


class Query(HabitsQuery, graphene.ObjectType):
    # placeholder for now
    ping = graphene.String(default_value="pong")


class Mutation(HabitsMutation, graphene.ObjectType):
    pass

schema = graphene.Schema(query=Query, mutation=Mutation)