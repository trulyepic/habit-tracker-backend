from habits.services.bosses.types import BossBuffDef, BossDef


# Central boss registry.
# Keep all daily/weekly bosses here and control rollout with `active` / `archived`.
DAILY_BOSS_CATALOG: tuple[BossDef, ...] = (
    BossDef(
        key="daily_combo_sentinel",
        name="Combo Sentinel",
        subtitle="Rapid check-ins break its defense matrix.",
        icon="swords",
        tint="from-fuchsia-500 to-violet-500",
        rarity="common",
        difficulty="rookie",
        mechanics=(
            "Complete quick multi-check-in objectives to shatter combo shields.",
            "Finishing any mechanic deals direct HP damage.",
        ),
        buffs=(
            BossBuffDef(
                key="combo_armor",
                name="Combo Armor",
                description="Starts with bonus HP until your first check-in lands.",
            ),
        ),
    ),
    BossDef(
        key="daily_streak_warden",
        name="Streak Warden",
        subtitle="Protect your chain and crush attrition.",
        icon="shield",
        tint="from-sky-500 to-cyan-500",
        rarity="rare",
        difficulty="rookie",
        mechanics=(
            "Streak-focused mechanics reward steady daily consistency.",
            "Each completed streak mechanic removes a chunk of Boss HP.",
        ),
        buffs=(
            BossBuffDef(
                key="attrition_aura",
                name="Attrition Aura",
                description="Reduces progress pace until one streak objective is cleared.",
            ),
        ),
    ),
    BossDef(
        key="daily_order_titan",
        name="Order Titan",
        subtitle="Clear active quests to collapse its command core.",
        icon="target",
        tint="from-amber-500 to-orange-500",
        rarity="rare",
        difficulty="veteran",
        mechanics=(
            "Clean-sweep mechanics encourage full active-quest participation.",
            "Completing all objectives exposes the reward chest.",
        ),
        buffs=(
            BossBuffDef(
                key="command_core",
                name="Command Core",
                description="Last objective grants a larger final HP break.",
            ),
        ),
    ),
    BossDef(
        key="daily_ember_hydra",
        name="Ember Hydra",
        subtitle="Many heads, one weakness: repeated disciplined actions.",
        icon="flame",
        tint="from-rose-500 to-red-500",
        rarity="epic",
        difficulty="veteran",
        mechanics=(
            "Multi-objective completion in one session greatly accelerates progress.",
            "Keep streaks alive to prevent the hydra from regaining momentum.",
        ),
        buffs=(
            BossBuffDef(
                key="ember_regen",
                name="Ember Regeneration",
                description="Displays high remaining HP until at least two mechanics are broken.",
            ),
        ),
    ),
    # Archived example retained for future seasonal return.
    BossDef(
        key="daily_rust_tyrant_s1",
        name="Rust Tyrant",
        subtitle="A relic from an older season.",
        icon="sparkles",
        tint="from-slate-600 to-slate-500",
        rarity="legacy",
        difficulty="veteran",
        mechanics=("Archived seasonal boss. Not currently in rotation.",),
        buffs=(),
        active=False,
        archived=True,
    ),
)


WEEKLY_BOSS_CATALOG: tuple[BossDef, ...] = (
    BossDef(
        key="weekly_void_marshall",
        name="Void Marshall",
        subtitle="A disciplined commander that punishes weak routines.",
        icon="crown",
        tint="from-indigo-600 to-blue-700",
        rarity="epic",
        difficulty="challenging",
        mechanics=(
            "Weekly objectives require broader consistency than daily fights.",
            "Breaking each mechanic lowers its fortress barrier.",
        ),
        buffs=(
            BossBuffDef(
                key="fortress_barrier",
                name="Fortress Barrier",
                description="Weekly HP drops only after objective milestones are met.",
            ),
            BossBuffDef(
                key="pressure_field",
                name="Pressure Field",
                description="Encourages maintaining multiple active streak lines.",
            ),
        ),
    ),
    BossDef(
        key="weekly_astral_overseer",
        name="Astral Overseer",
        subtitle="Tracks every lapse across the week.",
        icon="sparkles",
        tint="from-fuchsia-600 to-purple-700",
        rarity="legendary",
        difficulty="challenging",
        mechanics=(
            "Sustained weekly check-ins unlock accelerated completion.",
            "Roster-wide participation weakens its astral shell.",
        ),
        buffs=(
            BossBuffDef(
                key="astral_shell",
                name="Astral Shell",
                description="Higher objective targets than daily encounters.",
            ),
            BossBuffDef(
                key="orbit_lock",
                name="Orbit Lock",
                description="Rewards touching multiple quests during the same week.",
            ),
        ),
    ),
    BossDef(
        key="weekly_iron_behemoth",
        name="Iron Behemoth",
        subtitle="Built to test long-form momentum and resilience.",
        icon="shield",
        tint="from-emerald-700 to-teal-700",
        rarity="legendary",
        difficulty="hard",
        mechanics=(
            "Streak-heavy weekly mechanics challenge consistent execution.",
            "Conquer all mechanics to open a premium weekly chest.",
        ),
        buffs=(
            BossBuffDef(
                key="behemoth_plating",
                name="Behemoth Plating",
                description="Demands stronger streak thresholds for full completion.",
            ),
            BossBuffDef(
                key="overclock_drive",
                name="Overclock Drive",
                description="Final mechanic is tuned for advanced users but still attainable.",
            ),
        ),
    ),
)


def get_active_daily_bosses() -> list[BossDef]:
    return [boss for boss in DAILY_BOSS_CATALOG if boss.active and not boss.archived]


def get_active_weekly_bosses() -> list[BossDef]:
    return [boss for boss in WEEKLY_BOSS_CATALOG if boss.active and not boss.archived]


def get_archived_daily_bosses() -> list[BossDef]:
    return [boss for boss in DAILY_BOSS_CATALOG if boss.archived]


def get_archived_weekly_bosses() -> list[BossDef]:
    return [boss for boss in WEEKLY_BOSS_CATALOG if boss.archived]
