# DOCTRINE — implementation handoff

> **PARTLY STALE — written 2026-08-16.** Sections 1-2 (the core mechanic and the exact
> kill-accounting algorithm), 6 (verified engine API) and 7 (traps) are still accurate and
> worth reading. Everything about the build, packaging and file manifest predates the AI
> patch system, the release pipeline and all work after mid-August.
>
> For current build architecture see **`ARCHITECTURE.md`**; for where to change values see
> **`TUNING.md`**; to get started see **`HANDOVER.md`**.

**Read this first. It is written for an implementing AI or developer with no prior context.**

Target: **Warzone 2100 4.5.5**, Windows, skirmish vs AI.
Everything below was verified against the `4.5.5` git tag, not master. Line numbers are 4.5.5.

---

## 1. The core mechanic, in one page

**Kills stack into knowledge. Knowledge unlocks a research topic. Research pays for it.**

That is the whole loop. There is no unit retrieval, no driving a commander home, no salvage
recovery. Those were explored and are **deferred** (§10) — do not implement them.

```
  You kill an enemy unit
        │
        ▼
  Weight it by how good it was, relative to YOUR OWN army
  (far beneath you  →  worth nothing)
        │
        ▼
  Add the weighted points to the WEAPON FAMILY you killed it with
  (Cannon / Rocket / MG / Missile / …)
        │
        ▼
  Family knowledge crosses a threshold
        │
        ▼
  ONE random locked topic in that family becomes visible   ← enableResearch()
  (Warhead / Fire Control / Loading Drill / Gunnery, at the current tier)
        │
        ▼
  Player pays research time + power in a lab, as normal
        │
        ▼
  When ALL FOUR axes of a tier are RESEARCHED, the next tier becomes unlockable
```

Two rules give the system its shape:

1. **Combat unlocks, power researches.** Neither alone advances you. Killing things without
   spending power gets you a pile of visible-but-unresearched topics. Spending power without
   fighting gets you nothing to spend it on.
2. **Breadth before depth.** You cannot rush one axis. Tier *T+1* of *any* axis stays locked
   until all four axes of tier *T* are researched. Which axis surfaces next is random.

Anti-farming falls out of the weighting: grinding a scavenger base yields literally zero once
your own army is decent.

---

## 2. Exact kill accounting — the algorithm

This section is normative. Implement exactly this.

### 2.1 Constants

```js
const KILL_BASE   = 100;    // knowledge points for one parity kill (weight 1.0)
const STALENESS   = 4000;   // ms — max age of a "last hit" record for it to count
const P75_REFRESH = 30000;  // ms — how often the reference cost is recomputed
const TIERS       = 4;
const AXES        = ["Damage", "Range", "Reload", "Accuracy"];
const KNOWLEDGE   = [800, 1680, 3528, 7409];   // to unlock ONE topic at tier 1..4
```

### 2.2 Step 1 — attribute the kill

`eventDestroyed(obj)` **does not say who killed it**. There is no API that does. So:

```
on eventAttacked(victim, attacker):
    if attacker.player == me and attacker is a DROID:
        lastHit[victim.id] = { weapons: attacker.weapons[].id, time: gameTime }

on eventDestroyed(obj):
    rec = lastHit[obj.id];  delete lastHit[obj.id]
    if rec is missing                     -> ignore
    if gameTime - rec.time > STALENESS    -> ignore   (it wandered off and died later)
    if obj.type != DROID                  -> ignore   (structures give no knowledge)
    if obj.player == me                   -> ignore   (your own losses give nothing)
    if obj.player == scavengerPlayer      -> allowed, but the weighting will usually zero it
    -> credit(obj, rec)
```

**This is last-hitter attribution and it is approximate.** Splash, artillery and simultaneous
fire will misattribute some kills. That is acceptable: it only changes *which of your own
weapon families* gets credit, never whether you get credit.

### 2.3 Step 2 — compute the reference

The weighting is relative to **your own army**, so it self-scales over a match.

```
reference = 75th-percentile `cost` of your own living combat droids
            (droidType == DROID_WEAPON or DROID_CYBORG)
```

Recompute at most every `P75_REFRESH` ms; cache between.

**Why p75 and not something else:**
- **Not the mean** — a player could field a screen of cheap junk to drag the bar down and
  inflate the value of everything they kill.
- **Not the attacker's own cost** (which is what the engine's own `qualityFactor` uses) — that
  rewards sniping with the cheapest possible unit.
- p75 can only be lowered by actually giving up your good units. That is not an exploit, it is
  a sacrifice.

If you have no combat droids alive, reuse the last cached value; if there has never been one,
use `1` (everything counts) — this only happens in the first seconds of a match.

### 2.4 Step 3 — the weight curve

```
r = victim.cost / reference

r <  0.40           ->  weight = 0                      nothing to learn
0.40 <= r < 1.00    ->  weight = (r - 0.40) / 0.60      ramps 0 -> 1
1.00 <= r < 2.50    ->  weight = r                      (slope is exactly 1 in this band)
r >= 2.50           ->  weight = 2.50                   cap
```

`victim.cost` is exposed to JS and returns `calcDroidPower()` — the summed component build
cost (`src/quickjs_backend.cpp:1003`). A Dragon/Gauss/Tracks costs **602**; a scavenger trike
costs **38**. That ratio *is* the tech gap; no separate "tech level" concept is needed.

**What this produces** (reference = your p75):

| target killed | cost | you're in Vipers (62) | Pythons (285) | Vengeance (480) |
|---|---:|---:|---:|---:|
| Scavenger trike | 38 | 0.35 | **0** | **0** |
| Viper MG half-track | 62 | 1.00 | **0** | **0** |
| Cobra Light Cannon | 155 | 2.50 | 0.24 | **0** |
| Cobra Lancer | 230 | 2.50 | 0.68 | 0.13 |
| Python Medium Cannon | 285 | 2.50 | 1.00 | 0.32 |
| Tiger Heavy Cannon | 409 | 2.50 | 1.44 | 0.75 |
| Vengeance Scourge | 480 | 2.50 | 1.68 | 1.00 |
| Dragon Gauss | 602 | 2.50 | 2.11 | 1.25 |

### 2.5 Step 4 — assign to weapon families

```
gain = KILL_BASE * weight
if gain <= 0: stop

fams = distinct weapon families among the killer's turrets
       (map weapon id -> weaponSubClass -> family; see families.json)
if fams is empty: stop            (e.g. a truck ran something over)

each family in fams receives  gain / fams.length
```

A twin-turret unit with two different weapon types splits its learning. A single-turret unit
puts it all in one family. **This is why army composition is a research decision.**

### 2.6 Step 5 — offer an unlock (the ratchet)

Run after every credit.

```
for each family F with knowledge K[F]:

    T = the lowest tier where NOT all four axes are RESEARCHED
        (if all four axes of all four tiers are researched, family is done — skip)

    # tier gate: you may only work on tier T if tier T-1 is FULLY RESEARCHED
    if T > 1 and not all four axes of tier T-1 are researched:  skip

    if K[F] < KNOWLEDGE[T-1]:  skip

    candidates = axes at tier T whose topic is not yet UNLOCKED
    if candidates is empty:  skip          (all four already offered, go research them)

    pick = candidates[ syncRandom(candidates.length) ]
    enableResearch("R-Wpn-<F>-<pick><TT>", me)
    mark it unlocked
    K[F] -= KNOWLEDGE[T-1]                 # the knowledge is SPENT, not just a threshold
```

**Two details that matter:**

- **Knowledge is spent, not merely compared.** If it were a threshold, crossing it once would
  reveal all four axes at once and the breadth-first rule would do nothing.
- **`syncRandom(limit)`, never `Math.random()`.** `syncRandom` is the engine's deterministic
  synchronised RNG (`src/wzapi.cpp:288`). Using `Math.random()` will desync multiplayer and
  break save/reload determinism.

### 2.7 Step 6 — flip the tier credential

```
on eventResearched(research, structure, player):
    if player != me: return
    mark research.id as RESEARCHED
    for each family F, for each tier T in 2..4:
        if all four axes of tier T-1 are researched and R-Cred-<F>-Tier<T> not yet enabled:
            enableResearch("R-Cred-<F>-Tier" + T, me)
```

`R-Cred-<F>-Tier<T>` is a synthetic 10-point / 1-power marker topic that exists purely so the
cross-axis sync rule can be expressed as an ordinary `requiredResearch` entry. The player
researches it in ~1 second; it is a certificate, not a project. **This is the only bridge the
script needs between its own bookkeeping and the native research system** — every other
prerequisite in the tree is normal `requiredResearch`.

### 2.8 Worked example

You are fielding Python / Medium Cannon / Tracks (p75 reference = 285). You kill a
Tiger / Heavy Cannon (cost 409) with a Medium Cannon tank.

```
r      = 409 / 285             = 1.44
weight = r                      = 1.44        (in the 1.00–2.50 band)
gain   = 100 * 1.44             = 144
fams   = ["Cannon"]                            (one turret)
K["Cannon"] += 144
```

Suppose that brings `K["Cannon"]` to 1,750 and Cannon tier 1 is fully researched but tier 2 is
not started. `T = 2`, `KNOWLEDGE[1] = 1680`, so:

```
1750 >= 1680                    -> unlock fires
candidates = [Damage, Range, Reload, Accuracy]  (none unlocked at tier 2 yet)
pick       = syncRandom(4) -> 2 -> "Reload"
enableResearch("R-Wpn-Cannon-Reload02")
K["Cannon"] = 1750 - 1680 = 70
```

"Cannon Loading Drill II" now appears in the lab. The player pays 2,400 points / 85 power.
The other three tier-2 cannon topics stay invisible until more cannon kills pay for them.

---

## 3. Environment

### 3.1 Source

```
https://github.com/Warzone2100/warzone2100
git clone https://github.com/Warzone2100/warzone2100.git
git checkout 4.5.5          # tag; commit 96ce8bf7
```

**Do not develop against `master`.** The stat files differ in ways that will hard-crash a 4.5.5
install — see §7.1.

Data lives in `data/mp/stats/*.json` and `data/base/`. The engine files you need to read (never
modify — this is a data + script mod, no C++ changes) are:

| file | why |
|---|---|
| `src/research.cpp` | how `results` / `filterParameter` are applied |
| `src/combat.cpp` | damage formula, `minimumDamage` floor (line 536) |
| `src/projectile.cpp` | experience & `qualityFactor` (lines 288–298) |
| `src/wzapi.cpp` | the JS API surface, `getUpgradesObject()` |
| `src/quickjs_backend.cpp` | what fields JS objects expose |
| `src/stats.cpp` | stat loading, `WEAPON_TIME` (line 45), weapon-effect names |
| `doc/js-events.md` | the event list |

### 3.2 Local install

```
C:\Program Files\Warzone 2100-4.5.5\
├── bin\                     the executable
├── data\
│   ├── base.wz              (122 MB — base assets; a ZIP)
│   ├── mp.wz                ( 10 MB — MP stats; a ZIP, this is what we override)
│   ├── sequences.wz
│   └── mods\
│       ├── campaign\
│       └── multiplayer\
└── doc\
```

`.wz` files are **plain ZIP archives**. `mp.wz` contains `stats/*.json` — the files this mod
replaces. You can inspect it with any unzip tool. **Do not edit files inside Program Files**;
mods are loaded from the user config directory instead.

### 3.3 Where the mod goes

The user config directory on Windows for a *release-tagged* build is:

```
%USERPROFILE%\Documents\Warzone 2100 Project\Warzone 2100\
```

(`src/version.cpp:87` — tagged builds use the unsuffixed name `Warzone 2100`.)

Mod folders are **versioned by tag** (`src/version.cpp:139`, `src/main.cpp:1985`):

```
...\Warzone 2100\mods\4.5.5\autoload\     loaded automatically, every game
...\Warzone 2100\mods\4.5.5\global\       loaded with --mod=doctrine.wz
...\Warzone 2100\mods\4.5.5\multiplay\    loaded with --mod_mp=doctrine.wz
```

**Use `mods\4.5.5\autoload\` during development** — drop the `.wz` in and it loads on next
launch, no command line needed. Ship via `global` or `multiplay` later.

Verify the exact path exists before writing; if `mods\4.5.5\` is absent, launch the game once
to make the game create it.

### 3.4 Packaging

A mod is a ZIP renamed `.wz`, with the same internal layout as `mp.wz`:

```
doctrine.wz
├── mod-info.json                  (optional metadata)
├── stats/
│   ├── research.json              full replacement
│   ├── weapons.json               full replacement
│   ├── weaponmodifier.json        full replacement
│   ├── structuremodifier.json     full replacement
│   └── propulsion.json            full replacement
└── multiplay/
    └── script/
        └── rules/
            └── doctrine.js        the ratchet logic
```

Stat JSON files are **whole-file replacements**, not patches. Build them by loading the 4.5.5
original, applying the generated changes, and writing the complete file.

```powershell
Compress-Archive -Path .\build\* -DestinationPath .\doctrine.zip -Force
Move-Item .\doctrine.zip "$env:USERPROFILE\Documents\Warzone 2100 Project\Warzone 2100\mods\4.5.5\autoload\doctrine.wz" -Force
```

### 3.5 Test loop

1. Build the `.wz`, drop it in `autoload`.
2. Launch, start a skirmish vs one AI on a small map.
3. Open the debug menu with **Ctrl+O** (needs `--debug` or cheat mode). Use the `jsdebug`
   cheat to inspect script state.
4. `console()` output from the script appears in the in-game console and in
   `...\Warzone 2100\logs\`.

Enable script debug output by running:

```
"C:\Program Files\Warzone 2100-4.5.5\bin\warzone2100.exe" --debug=script
```

**A stat file that fails to parse is fatal and the game will refuse to start.** Check the log
in `...\Warzone 2100\logs\` for `LOG_FATAL` lines if it won't launch.

---

## 4. File manifest

Generated by the scripts in this package. Run in this order:

```bash
export WZ_ROOT=/path/to/warzone2100     # at tag 4.5.5
python3 generate_tree.py                # -> out/research-doctrine.json, out/meta.json, out/surplus.json
python3 rebalance.py                    # -> out/stats/*.json
python3 killvalue.py                    # -> out/killvalue.json (reference tables; not shipped)
python3 validate.py                     # must print ERRORS: 0
```

| Action | File | Detail |
|---|---|---|
| **MERGE** | `stats/research.json` | Start from 4.5.5's 388 topics. Apply `out/research-doctrine.json` (351 topics) — same-ID entries **replace**, new IDs are **added**. |
| **DELETE** | `stats/research.json` | Remove every ID listed in `out/surplus.json` (**70 topics**). Non-optional — see §7.2. |
| **REPLACE** | `stats/weapons.json` | from `out/stats/weapons.json` — `minimumDamage` by role, salvo spacing, air payload, AA compensation |
| **REPLACE** | `stats/weaponmodifier.json` | from `out/stats/weaponmodifier.json` — 38 values |
| **REPLACE** | `stats/structuremodifier.json` | from `out/stats/structuremodifier.json` — 21 values |
| **REPLACE** | `stats/propulsion.json` | from `out/stats/propulsion.json` — VTOL survivability |
| **ADD** | `multiplay/script/rules/doctrine.js` | the ratchet logic (§2) |

### 4.1 Also set the calculation mode

In the merged `research.json`, at document root, set:

```json
"calculationMode": "improved"
```

`ResearchUpgradeCalculationMode::Improved` exists in 4.5.5 (`src/research.cpp:262`) and
significantly reduces accumulated per-step `ceil()` rounding error. MP still defaults to the
legacy `Compat` mode; only the campaign mods opt in. It costs nothing to switch.

### 4.2 Fix the rank curve

Vanilla rank thresholds are `0 / 4 / 8 / 16 / 32 / 64 / 128 / 256 / 512` **kills**. Hero is
effectively unreachable — a core dev said so on the forums, and the devs' own commander cheat
rewrites the curve to roughly half. Set at game start:

```js
Upgrades[me].Brain["CommandBrain01"].RankThresholds = [0, 2, 4, 8, 16, 24, 32, 48, 64];
```

Note the API quirk, documented in `doc/js-globals.md`: **you must assign the entire array at
once.** Setting individual indices silently does nothing.

---

## 5. Reference implementation

See **`doctrine.js`** in this package — a complete, commented implementation of §2 that can be
dropped into `multiplay/script/rules/`. It is written against the 4.5.5 API and uses only
verified calls.

---

## 6. Verified API surface (4.5.5)

Everything the mod depends on, confirmed present at tag `4.5.5`:

| Need | API / mechanism | Verified at |
|---|---|---|
| Reveal an earned topic | `enableResearch(id, player)` | `src/wzapi.cpp:2706` |
| Kill attribution (part 1) | `eventAttacked(victim, attacker)` | `doc/js-events.md:175` |
| Kill attribution (part 2) | `eventDestroyed(object)` | `doc/js-events.md:187` |
| Detect a completed topic | `eventResearched(research, structure, player)` | `doc/js-events.md:180` |
| Topic id from that event | `research.id` (and `research.name`) | `src/quickjs_backend.cpp:774–775` |
| Unit value | `droid.cost` → `calcDroidPower()` | `src/quickjs_backend.cpp:1003` |
| Killer's weapons | `droid.weapons[i].id` | `src/quickjs_backend.cpp:882–883` |
| Enumerate own army | `enumDroid(player, droidType)` | `src/wzapi.cpp:1083` |
| Unit type constants | `DROID_WEAPON`, `DROID_CYBORG`, `DROID` | `src/wzapi.cpp:4607, 4612, 4646` |
| Deterministic RNG | `syncRandom(limit)` | `src/wzapi.cpp:288` |
| Per-component upgrades | `filterParameter: "Id"` in research results | `src/research.cpp`; live example is vanilla `R-Comp-CommandTurret02` |
| Runtime rank curve | `Upgrades[p].Brain[b].RankThresholds = [...]` | `getUpgradesObject()` |
| Structure limits upgradeable | `Building.Limit` | `src/wzapi.cpp:4297` |
| Improved upgrade math | `"calculationMode": "improved"` | `src/research.cpp:262` |

Weapon parameters reachable from research (18 total; **vanilla 4.5.5 uses only 7**):
`MaxRange`, `ShortRange`, `MinRange`, `HitChance`, `ShortHitChance`, `FirePause`, `ReloadTime`,
`Rounds`, `Radius`, `Damage`, `MinimumDamage`, `RadiusDamage`, `RepeatDamage`, `RepeatTime`,
`RepeatRadius`, `HitPoints`, `HitPointPct`, `EmpRadius`.

---

## 7. Traps — read before writing code

### 7.1 `Propellor` in `weaponmodifier.json` is fatal on 4.5.5

The naval propulsion row exists only in `master`. `stats.cpp loadWeaponModifiers()` does:

```cpp
if (!getPropulsionType(list[i].toUtf8().c_str(), &type)) {
    debug(LOG_FATAL, "Invalid Propulsion type - %s", ...);
    return false;
}
```

**`LOG_FATAL` + `return false` — the game will not start.** `rebalance.py` now intersects
against the source file's keys, so it emits 6 rows × 6 propulsions for 4.5.5 and skips
`Propellor` automatically. If you hand-edit these files, do not add keys the build doesn't know.

### 7.2 Deleting the surplus ladder is not optional

Vanilla 4.5.5 upgrade ladders are `R-Wpn-<fam>-Damage01..09/10` and `R-Wpn-<fam>-ROF01..06`.
DOCTRINE emits `Damage01..04` and `Reload01..04`.

- `Damage01–04` **collide by ID** and cleanly replace vanilla — which is a gift, because every
  existing weapon-unlock prerequisite then re-points at the ratchet for free.
- `Damage05–09` and **every `ROF` topic do not collide.** Left in place they survive as a
  parallel upgrade ladder with no battlefield gating, and the player double-dips.

`out/surplus.json` lists the **70 topics** to delete. Verify after merging that no remaining
topic's `requiredResearch` references a deleted ID — `validate.py` checks this.

### 7.3 `filterParameter: "Size"` on a Body silently does nothing

`src/wzapi.cpp` assigns `body["Size"]` from a raw `BODY_SIZE` enum, so it serialises as an
**integer**, while `ImpactClass` and `Effect` go through `getWeaponSubClass()` /
`getWeaponEffect()` and serialise as **strings**. Comparing against `"LIGHT"` never matches —
and `research.cpp` skips a non-matching filter **with no warning**, so the topic quietly does
nothing. Enumerate body `Id`s instead. The generator already does.

### 7.4 The cyborg AT weapons are not salvo weapons

`Cyb-Hvywpn-A-T`, `Cyb-Wpn-Atmiss`, `Cyb-Hvywpn-TK`, `CyborgRocket` look like the twin-missile
weapons but have **no `numRounds` and no `reloadTime`** — `firePause` (80–180, i.e. **8–18
seconds**) is their entire firing cycle. Rewriting it turns an 8-second cycle into 1.2 seconds:
a ~7× DPS buff by accident. `rebalance.py` guards on `numRounds > 1`; keep that guard.

### 7.5 `qualityFactor` already exists and is clamped

`src/projectile.cpp:288–298` already scales experience by victim-vs-attacker cost — then
`CLIP(powerRatio, 65536/2, 65536*2)`. **A 0.5 floor**: killing a scavenger trike with a Gauss
tank still pays half. "Really low should be zero" is exactly what that clamp forbids, and it is
C++, so a data mod cannot lift it. This is *why* DOCTRINE keeps its own kill ledger rather than
reading `commander.experience`.

The engine's own experience system keeps running underneath and still drives **rank** (group
size, combat bonuses). That is fine and intended — it is a separate currency from knowledge.

### 7.6 Shipped AIs will not use this

`Cobra.js` and Nexus contain hardcoded research ID lists. They will keep researching their own
list and simply won't participate in the ratchet. They remain playable opponents. Do not spend
time "fixing" the AIs in v1 — verify they still start and build, and move on.

### 7.7 `addFeature` is `MULTIPLAY_UNSAFE`

Not used in v1 (that was the deferred black-box mechanic). If it comes back, note the flag.

---

## 8. Acceptance tests

Run each as a skirmish vs one AI. All are observable from `console()` output.

| # | Test | Expected |
|---|---|---|
| 1 | Game launches with the mod in `autoload` | No `LOG_FATAL` in logs; main menu reachable |
| 2 | Start a skirmish, check research list | Roughly 4–8 topics visible per family you have, **not** 350 |
| 3 | Kill a scavenger with an early Viper MG | Small but non-zero `Cannon`/`MG` knowledge logged |
| 4 | Reach Pythons, then kill a scavenger | **Zero** knowledge — weight is 0 |
| 5 | Accumulate 800 MG knowledge | Exactly **one** MG tier-1 topic appears, at random |
| 6 | Accumulate 1600 more without researching | A **second** tier-1 topic appears; never a tier-2 topic |
| 7 | Research all four MG tier-1 topics | `R-Cred-MG-Tier2` appears, then tier-2 topics become unlockable |
| 8 | Kill with a twin-turret unit carrying two families | Knowledge splits 50/50 between them |
| 9 | Save and reload mid-game | Knowledge totals and unlock state survive (see §9) |
| 10 | Fire a Scourge at a target that dies to round 1 | Second missile does **not** launch |
| 11 | Lancer vs a tracked Python | Noticeably higher damage than 4.5.5 (AT vs Tracked 120→175) |
| 12 | Mortar vs a hardpoint | Noticeably higher than 4.5.5 (ARTILLERY vs HARD 100→130) |

---

## 9. Persistence

Script state (`K`, `unlocked`, `researched`, `lastHit`) must survive save/load. Use the
`setGlobalVariable` / `getGlobalVariable` mechanism, or namespace the variables so the engine's
script serialiser picks them up. **Test #9 above is the check.** Note that `lastHit` can be
dropped on load without harm — worst case a couple of in-flight kills go uncredited.

---

## 10. Explicitly out of scope for v1

These were designed and are documented in `DOCTRINE.md` / `COMBAT.md`, but **do not implement
them now**:

- Commander debrief / driving knowledge home to the Command Relay Center
- Black-box recovery from a dead commander
- Recycle-to-lab as a knowledge route
- Tech drops from destroyed scavenger/rebel bases
- Signature topics (per-single-weapon mastery) — the data exists, leave them unenabled
- Breadth credentials + the infrastructure branch gated on them

v1 is: **kills → weighted knowledge → random unlock → pay to research → tier gate.** Ship that,
play it, then decide what earns its complexity.

---

## 11. Package contents

| File | What it is |
|---|---|
| `IMPLEMENTATION.md` | this document |
| `doctrine.js` | reference implementation of §2 |
| `generate_tree.py` | generates the 351-topic tree from ~20 numbers in a `CONFIG` block |
| `rebalance.py` | generates the modified stat files; version-aware |
| `killvalue.py` | the kill-weighting curve and reference tables |
| `validate.py` | DAG + engine-schema validation. **Run on every change.** |
| `out/research-doctrine.json` | the generated tree |
| `out/surplus.json` | the 70 vanilla topics to delete |
| `out/stats/*.json` | rebalanced stat files, generated against 4.5.5 |
| `DOCTRINE.md` | full design rationale (some sections superseded; see its header) |
| `COMBAT.md` | combat rebalance rationale + §5 the ratchet + §5a kill valuation |
| `techtree.html` | interactive browser for the generated tree |
