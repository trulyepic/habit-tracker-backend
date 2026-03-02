# Habit Tracker Backend Context

## Purpose
- Django + GraphQL API for habit/quest tracking with gamification.
- Primary frontend consumer: `habit-tracker-web`.

## Stack
- Python 3.12
- Django
- Graphene GraphQL
- SQLite for local dev
- PostgreSQL on Railway for deployed env

## Runtime and Env Notes
- `DATABASE_URL` is used for Postgres environments (Railway).
- Local default remains SQLite when Postgres env is not set.
- Required Python deps include:
  - `dj-database-url`
  - `python-dotenv`

## Core Domain
- `Habit`: user-owned quest/habit (`is_active`, `name`, `description`).
- `CheckIn`: daily check-in per habit (unique by `habit + date`).
- `PlayerProfile`: XP/level/time, achievements, daily quest claims, streak safety state.

## Key Features Implemented
- Habit CRUD and active toggle.
- Daily check-in with XP reward, no duplicate XP on same-day duplicate check-in.
- Achievement unlock tracking and progression sync.
- Daily Quest Chain:
  - deterministic daily objective rotation
  - reward claim once per day
  - claim metadata exposed:
    - `reward_claimed`
    - `reward_claimable`
    - `reward_claimed_at`
    - `reward_awarded_xp`
  - explicit mutation reason:
    - `claimed`
    - `already_claimed`
    - `incomplete`
- Streak safety + recovery quest claim flow.
- Recent activity feed includes both:
  - `checkin`
  - `habit_created`

## Important Behavior Contracts
- Deactivate (`toggle_habit_active`) must NOT delete habit or check-ins.
- Delete (`delete_habit`) is destructive and removes habit plus related check-ins.
- Daily reward claims must be idempotent (no double-award).

## Main Files
- Schema/mutations/queries:
  - `habits/schema.py`
- Daily quests:
  - `habits/services/daily_quests/service.py`
  - `habits/services/daily_quests/catalog.py`
- Streak safety/recovery:
  - `habits/services/streaks.py`
- Models:
  - `habits/models.py`

## Tests and CI
- Run local tests:
  - `pytest -q`
- Django checks:
  - `python manage.py check`
- GitHub Actions workflow:
  - `.github/workflows/backend-tests.yml`
  - job name used for required status checks: `Backend Tests / test`

## Deployment/Workflow Notes
- Backend repo is connected to Railway for deployment updates from Git pushes.
- Recommended repo protection:
  - require PR before merge
  - require `Backend Tests / test` status check on `main`

## Working Rules (Project-Specific)
- Keep backend as source of truth for progression/claims.
- Add/extend tests whenever GraphQL contract changes.
- Prefer explicit mutation result states (`reason` fields) over implicit client inference.
