# DOCTRINE — tuning reference

Where every knob lives. Change a value here, rebuild, playtest. Nothing in this file requires
understanding the whole build.

Rebuild after any change:

```powershell
py -X utf8 build_mod.py 4.7.0
py -X utf8 build_mod.py 4.5.5
```

---

## 1. The crate loop — `doctrine.js`, top of file

The feel of the whole mod. These are the first things to reach for.

| constant | now | what it does |
|---|---|---|
| `DROP_BASE_VET` | `0.12` | base drop chance for a parity kill on a fully-blooded victim |
| `EXP_FULL` | `11` | victim experience at which the veterancy scaling maxes out |
| `EXP_CURVE` | `1.3` | >1 punishes green victims harder |
| `DROP_CAP` | `0.90` | hard ceiling on any single drop roll |
| `VET_BONUS` / `VET_CAP` | `0.60` / `24` | how much the *killer's* own veterancy adds |
| `PITY_RATE` | `0.03` | accumulates on a failed roll so dry spells end |
| `SCAV_FLOOR` | `0.14` | flat chance for scavenger victims (never cost-weighted) |
| `CRATE_TTL` | `300000` | 5 min before a crate decays |
| `STALENESS` | `4000` | how long a last-hitter record stays valid |

**More tech, faster:** raise `DROP_BASE_VET`. **Less snowball:** lower `VET_BONUS`.
**Crates contested for longer:** raise `CRATE_TTL`.

## 2. Scenery and scavengers from houses — `doctrine.js`

| constant | now | |
|---|---|---|
| `HOUSE_CHANCE` | `0.015` | chance a flattened building yields an intel crate |
| `HOUSE_SCAV_CHANCE` | `0.40` | chance a flattened building is occupied |
| `HOUSE_SCAV_MIN` / `MAX` | `1` / `5` | how many scavengers come out |
| `HOUSE_CREDIT_RANGE` | `8` | tiles searched to credit the demolisher |
| `DRUM_CHANCE` | `0.05` | oil drum from a destroyed unit or building |

Only `BUILDING` and `SKYSCRAPER` features count — trees, wrecks and boulders produce nobody.
**Test these on `Thales`; `4c-rush` has no buildings at all.**

## 3. Research pacing — `doctrine.js` and `build_mod.py`

| where | constant | now | |
|---|---|---|---|
| doctrine.js | `LAB_LIMIT_START` / `MAX` | `2` / `5` | labs at start, and the ceiling |
| doctrine.js | `TIERS` / `AXES` | `4` / 4 axes | the shape of every family ladder |
| doctrine.js | `BREADTH_LEVELS` | `[2,3,4,5]` | families at tier 2+ needed per credential |
| build_mod.py | `RESEARCH_SPEED_KEEP` | `0.40` | lab speed vs vanilla — **the master pacing dial** |
| build_mod.py | `RESEARCH_POWER_MULT` | `2.40` | power cost of bought (not captured) topics |
| build_mod.py | `CAPTURED_TIME_MULT` | `0.80` | captured topics research faster |
| build_mod.py | `DAMAGE_TIER_VALUES` | `[34,46,61,82]` | the four damage rungs (+223% total) |
| build_mod.py | `RESEARCH_OVERRIDE` | VTOL line | per-topic cost and prerequisite overrides |

**Whole game too slow?** `RESEARCH_SPEED_KEEP` moves everything at once.

## 4. Combat balance — `build_mod.py`

| dict | line ≈ | what it controls |
|---|---|---|
| `WEAPON_MODIFIER_OVERRIDE` | 325 | weapon effect vs **propulsion** (the unit counter table) |
| `STRUCTURE_MODIFIER_OVERRIDE` | 319 | weapon effect vs **building class** (the siege table) |
| `MIN_DAMAGE_BY_EFFECT` | 309 | damage floor that lands regardless of armour |
| `MG_LINE` | 360 | the machinegun damage ladder |
| `WEAPON_TUNING` | 391 | per-weapon overrides — outliers, cyborg weapons, scav defences |
| `CYBORG_TUNING` | 475 | cyborg bodies: cheap, quick, fragile |
| `PROPULSION_OVERRIDE` | 499 | currently `CyborgLegs` |
| `STRUCTURE_TUNING` | 462 | structure HP / build cost (currently `bbaatow`) |
| `FLIGHT_SPEED` | 112 | projectile speed — how hitscan the guns feel |
| `ELEVATED_RANGE_MULT` | 519 | `1.15` — range bonus for tall defences |

Both modifier tables are documented with full before/after grids in `PLAYTEST.md`
("Finding 3" and "Finding 4"). Read those before changing a cell — the tables are the
rock-paper-scissors of the entire mod.

**Armour is subtracted *after* the effect modifier**, so low-damage weapons are punished
disproportionately and a small damage change can swing effectiveness several-fold. Always
recompute, never estimate.

## 5. Scavengers — `build_mod.py` and `uuscav2/…/ultimateScavengers.js`

| where | constant | |
|---|---|---|
| build_mod.py | `SCAV_BODY` | HP / armour multipliers per scav body |
| build_mod.py | `SCAV_WEAPON` | their improvised guns |
| build_mod.py | `SCAV_MORTAR_HIT` | `(22,18)` — deliberately worse than the player's mortar |
| build_mod.py | `BOMB_TRUCK_GUN_RANGE` | `40` — must stay under the 256 blast radius |
| build_mod.py | `BOMB_TRUCK_BODY_HP` | `340` — the dedicated bomber shell |
| scav script | `SCAV_T_*` | phase timings (hold / light / medium / heavy / air) |
| scav script | `SCAV_BODIES`, `SCAV_WEAPONS` | what they field per phase |
| scav script | `SCAV_BOMBERS` | the four bomb-truck grades |
| scav script | `SCAV_INFANTRY_SHARE` | `0.6` of the unit ceiling |
| scav script | `SCAV_AIR_SHARE` | `0.25` — caps helicopters |
| scav script | `SCAV_PICKET_PER_SITE` | `4` defences per derrick/factory/generator |
| scav script | `SCAV_MAX_EMPLACEMENTS` | `44` total |
| scav script | `scavUnitCeiling()` | `12 + 3/min`, capped at 70 |

Repack after editing the script: `py -X utf8 harness\repack_uuscav2.py`

## 6. AI behaviour — `build_mod.py`

| what | where |
|---|---|
| research scoring weights | `DOCTRINE_ENGINE_JS` → `DOCTRINE_W_*` constants |
| favoured-family multiplier | `DOCTRINE_FAMILY_MULT` (`1.4`) |
| topic cost half-life | `DOCTRINE_HALFLIFE` (`150` s) |
| what each AI researches first | `DOCTRINE_DEFENCE_FIRST` |
| SemperFi's build lists | `SEMPERFI_LISTS` |
| AA turret priority | `TANK_AA` (SemperFi), `STANDARD_AA_TEMPLATES` (Nexus), `bcList` (BoneCrusher) |
| AI factory allowance | `FACTORY_ALLOWANCE`, `HARD_FACTORIES`, `INSANE_FACTORIES` |
| AI free upgrades | `doctrineFreeIntel()` — **see the note below** |

> `doctrineFreeIntel()` grants Hard/Insane AI a free weapon upgrade every 150 s / 75 s — about
> 34 and 68 per 86-minute game, and it is **AI-only**. It is the single largest lever on AI
> weapon strength and the first thing to reach for if the AI feels overtuned. Diagnosed in
> PLAYTEST "Finding 1" and deliberately left alone.

## 7. Things that are not knobs

- **`apply_elevation` must stay last** in `main()`, or elevated defences keep pre-tuning stats.
- **Empty `requiredResearch` means hidden**, not free — that is the crate gate.
- **Weapon unlocks must never sit behind crate-only topics.** There is a whole re-anchoring
  pass in `main()` protecting this; it once froze every player on the starting machinegun.
- **AA turrets are air-only.** Any AA production must stay gated on a live air threat.
- **`Propellor` in `weaponmodifier.json` is fatal on 4.5.5** — see `IMPLEMENTATION.md` §7.1.
