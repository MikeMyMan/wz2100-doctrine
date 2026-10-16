# DOCTRINE — a tech tree where research is earned in the field

*A design specification for Warzone 2100. Every mechanism cited has been verified against
`Warzone2100/warzone2100` master — source file and line given where it matters.*

---

## 0. The one-line thesis

> Vanilla research changes **scale**. It never changes **shape**.
> DOCTRINE makes research a **consequence of how you fought**, not a queue you click.

The vanilla tree is 390 topics, of which **204 (52%) unlock no object at all** and consume
**63% of all research time**. Upgrades are additive on the base value, so nine steps of "+25%"
is +225%, not 1.25⁹ — the ninth step delivers a third of the first step's effect for twelve
times the price. Nothing ever retires (1 of 390 topics uses `replacedComponents`). And no
research entry touches the rock-paper-scissors tables, so matchup ratios at minute 60 are
byte-identical to minute 5.

Both sides' numbers inflate. The relationships never move. Symmetric inflation carries no
information — which is, mathematically, what "meaningless" means.

---

## 1. The loop

```
       ┌─────────────────────────────────────────────────────────────┐
       │                                                             │
       ▼                                                             │
   COMBAT ──▶ commander accumulates ──▶ DEBRIEF at Relay Center ──▶ FIELD KNOWLEDGE
                 (engine already                (drive home)          (per component)
                  does this)                                              │
                                                                          ▼
                                                              enableResearch() on
                                                              FIELD topics (crew skill)
                                                                          │
                                                          ┌───────────────┴───────────────┐
                                                          ▼                               ▼
                                                  DEPTH GATE                       BREADTH GATE
                                              (mastery in one family)        (competence in N families)
                                                          │                               │
                                                          ▼                               ▼
                                                DOCTRINE topics                  INFRASTRUCTURE
                                             (materiel: damage, range,       (research rate, power,
                                              penetration, new weapons)       production, limits)
                                                          │                               │
                                                          └───────────────┬───────────────┘
                                                                          ▼
                                                                    better army ──▶ back to COMBAT
```

> **SUPERSEDED — see `COMBAT.md` §5.** The crew/materiel split below was replaced by the
> unlock ratchet: combat unlocks one random axis-tier, research pays for it, and a tier only
> opens once every axis below it is *researched*. The ratchet is a simpler and stronger
> throttle. The rest of this document (banking loop, black box, breadth gates, spine, entry
> path) is unchanged and still applies.

**The original rule (retained for rationale):**

| | **FIELD** (crew) | **DOCTRINE** (materiel) |
|---|---|---|
| Earned with | combat | power |
| Represents | what the crew learned | what the engineers built |
| Improves | `HitChance`, `ShortHitChance`, `FirePause`, `ReloadTime`, body `Power` | `Damage`, `RadiusDamage`, `MaxRange`, `MinimumDamage`, `Armour`, new components |
| Magnitude | +12% relative per tier, 3 tiers | +25% relative per tier, 4 tiers |
| Can it snowball? | No — capped to crew-skill magnitudes | Yes, but it's gated behind field credentials |

This is the Wargame rule: *"Veterancy affects the human only. It won't make a tank shoot a
bigger sabot."* It gives the tree a **narrative** — and narrative is the thing "meaningless"
was missing:

> *Field reports from Medium Cannon crews indicate consistent over-penetration at range.
> Ballistics division can now develop APFSDS rounds.*

The field data literally justifies the engineering. That's the synergy.

---

## 2. What the engine already does for you

Three mechanisms exist and are either idle or wired to something trivial.

### 2.1 The Command Turret is already a knowledge accumulator

`src/projectile.cpp:371–378`:

```cpp
droidIncreaseExperience(psDroid, experienceInc);      // the shooter
cmdDroidUpdateExperience(psDroid, experienceInc);     // AND its commander
```

Not a split — a **duplicate**. The commander accrues the *sum* of every hit landed by every
unit in its group. It then pays back out: `getDroidEffectiveLevel()` returns
`MAX(own level, commander level)`, so the commander broadcasts its rank down to every attached
unit, and `autoRewardRankFromAttach` grants +1 level just for being linked. Group size is
`BaseCommandLimit + level × CommandLimitByLevel` = **6 + 2×level** — 6 at Rookie, 22 at Hero.

So the loop already compounds: bigger group → more accumulated experience → higher rank →
bigger group, *and every unit inherits the rank*.

**What all of that currently buys:** −6% damage taken, +5% accuracy, +5% speed per level.
A Hero commander — the combat record of 22 tanks across a whole game — cashes out as roughly
a 40% accuracy bump. **Two of 390 research topics touch this component.** It is the most
structurally sophisticated and least developed thing in the game.

DOCTRINE gives it eight topics and makes it the backbone.

### 2.2 Artifacts are a working `enableResearch()` pipeline, campaign-gated

`libcampaign_includes/artifact.js` binds a tech to a structure label; the structure dies, a
crate spawns on its rubble, `eventPickup` fires. Critically it calls **`enableResearch()`, not
`completeResearch()`** — the artifact makes a topic *appear*, and you still pay time and power.

Artifacts are **keys, not gifts**. DOCTRINE uses the same pattern for field knowledge.

### 2.3 Recycle is already "retire a veteran, bank the benefit"

`src/droid.cpp:509` — send a unit to a factory: it is consumed, you get partial power back,
and its experience goes into a **priority queue sorted by rank**, consumed highest-first. The
next units off any production line come out at that rank. Chassis-, weapon- and
propulsion-agnostic. `eventObjectRecycled()` is an exposed JS hook.

The sacrifice verb already exists and players already know the gesture. DOCTRINE points it at
a different building.

---

## 3. Knowledge model

### 3.1 Accrual — you don't track anything

Do **not** poll damage events. The engine already sums the group's combat output into
`commander.experience`, which is exposed to JS (`quickjs_backend.cpp:1544`). Read it.

```js
const gained = cmdr.experience - banked[cmdr.id];
```

That single line replaces an entire per-hit tracking system, is free of desync risk, and is
exactly what the player means by "the brain accumulated the points."

### 3.2 Distribution — composition is a research decision

At debrief, `gained` is distributed across **the components actually present in the group**,
proportionally to how many units carry each.

```
group: 6 × [Medium Cannon / Python / Tracks]
       4 × [Lancer / Cobra / Half-tracks]
gained: 5,000

  Cannon2A-TMk1  → 3,000        Body11ABT (Python)  → 3,000
  Rocket-LtA-T   → 2,000        Body5REC  (Cobra)   → 2,000
```

Component knowledge rolls up into **family** knowledge (Cannon, Rocket, …) for the family
topics, and stays per-component for the signature topics.

**This is why homogeneous death-balls self-correct.** Because field tiers have steeply
diminishing knowledge requirements (§5.2), a group that pours everything into one component
hits that component's wall and starts wasting knowledge, while a mixed group spreads across
components that are each early on their curve and extracts more total value. The curve does
the balancing; no separate anti-deathball rule is needed.

### 3.3 Learning from defeat

**Knowledge must not come from kills alone.** If it did, losing produces no research, which
makes you lose harder — a death spiral that punishes the player already behind. That is the
worst failure mode a progression system can have, and against a hard AI it would be miserable.

The engine already helps: `droidIncreaseExperience` is called on *hits landed*, not kills, so a
squad that gets mauled while shooting back still banks. On top of that, DOCTRINE adds a
**survivability channel**: at debrief, each chassis present also banks knowledge proportional to
damage absorbed (read from `health` deltas on `eventAttacked`).

A unit that dies having absorbed enormous fire should teach you the most. Applique armour came
from tanks that burned; MRAPs came from IED casualties. Real militaries learn more from their
defeats than their victories — and a system that models that is both better design and closer
to the thing you were reaching for.

---

## 4. The commander banking loop

### 4.1 Debrief

The Command Relay Center has `userLimits: [0,1,1]` — **you can only ever build one**. There is
exactly one place on the map to debrief. On a large map that is a real logistical decision
every single time.

1. Commander accrues in the field. This knowledge is **unbanked and at risk**.
2. Drive it within range of the Relay Center → **Debrief**. Yield 100%.
3. Knowledge distributes (§3.2). Thresholds crossed call `enableResearch()`.
4. `commander.experience` is *not* reset — only the banked watermark moves. The commander keeps
   its rank and combat bonuses. You are extracting a copy of the record, not spending it.

### 4.2 The black box

Commander dies with unbanked knowledge → drop a **Data Core** feature at the wreck
(`addFeature`, the artifact pattern). Any unit recovering it returns **50%** of the unbanked
amount (85% with `R-Sys-DataCore`).

This turns the worst moment in the system into a *play response* instead of a flat loss. It is
a rescue mission you did not plan, generated by the game, at a location that matters. It is
also the single strongest argument for the whole design: **losing is interesting.**

### 4.3 Recycle-to-lab (the sacrifice route)

Units not in a command group are not wasted. Recycle a unit **at a Research Facility** instead
of a Factory: it is consumed and banks its own experience directly, at a lower rate (~40%) than
commander debrief.

Two routes, honestly different:

| | Commander debrief | Recycle to lab |
|---|---|---|
| Yield | 100% | ~40% |
| Volume | whole group at once | one unit |
| Risk | the drive home | none |
| Cost | none (commander survives) | the unit is destroyed |

### 4.4 Remote debrief

`R-Sys-Telemetry` (late, expensive) allows banking without driving home, at **60% yield**.
This removes the *obligation*, not the *choice* — driving home still pays better. Late game
should relax a constraint it made you feel for an hour, not delete it.

---

## 5. The curves

### 5.1 Escalating values, because the engine adds on the base

`src/research.cpp` computes `statsOriginalValue × value / 100` and **adds**. A constant `value`
therefore means a *shrinking* relative gain — this is the whole reason vanilla feels like a
treadmill. DOCTRINE solves for values that hold the relative gain constant:

```
value_n = 100 · g · (1+g)^(n-1)
```

| Ladder | g | Values | Total |
|---|---|---|---|
| Field (crew) | 0.12 | **12, 13, 15** | +40% |
| Doctrine (materiel) | 0.25 | **25, 31, 39, 49** | +144% |
| Reach (range) | 0.08 | **8, 9, 9** | +26% |

Every tier feels the same size as the one before it. That alone kills the "countless meaningless
increments" complaint.

*(Also set `"calculationMode": "improved"` in the research file — it exists in `research.cpp`,
significantly reduces accumulated `ceil()` rounding error, and only the campaign mods currently
use it. MP still runs legacy `Compat`.)*

### 5.2 Steeply diminishing knowledge, cheap entry for new lines

Knowledge required for field tier *n* in a family: `1000 × 2.1ⁿ` → **1,000 / 2,100 / 4,410**.

This is the mechanism that answers the original complaint. Under vanilla, your ninth cannon
upgrade is +8% for twelve times the price — a dead end you walk down anyway because there is
nothing else. Under DOCTRINE, your third cannon tier is expensive **and your first rocket tier
is cheap**. At exactly the moment cannons flatten out, the efficient move becomes *learning
something you have never fielded*.

> The late game stops being "+8% damage, step nine" and becomes
> **"I've taken cannons as far as they go — time to learn rockets."**
> The treadmill becomes an exploration gradient.

### 5.3 Worked example — Medium Cannon, start vs endgame

| | base | vanilla endgame | DOCTRINE endgame |
|---|---|---|---|
| Damage | 60 | 195 (+225%) | 146 (+144%) |
| Range | 1024 | **1024 (unchanged)** | **1290 (+26%)** |
| Accuracy (long) | 55 | **55 (unchanged)** | **85** |
| Fire pause | 40 | 24 (−40%) | 16 (−60%) |
| **Effective DPS** | 1.0× | **8.1×** | **9.5×** |

Comparable total power. Distributed across **four qualitatively different axes** instead of one,
two of which vanilla never touches at all. Range in particular relocates the fight rather than
scaling it — you feel +26% range the instant you use it, every time.

---

## 6. The gates

### 6.1 Depth — specialists get better guns

Expressed **natively** in `requiredResearch`, no script needed, because field topics are real
research topics:

```
R-Doct-Cannon-Lethality02  requires  R-Doct-Cannon-Lethality01
                                     R-Field-Cannon-Gunnery02      ← the gate
```

You cannot develop better cannon ammunition until cannon crews have logged the hours.

### 6.2 Breadth — generalists get a better war machine

`requiredResearch` is a pure AND-list, so *"field tier 2 in any four families"* cannot be
expressed natively. Solution: **synthetic credential topics** the script enables.

```json
{"id": "R-Cred-Breadth04", "name": "Combined Arms Doctrine 4",
 "researchPoints": 10, "researchPower": 1}
```

Zero cost — it is a certificate, not a project. Everything downstream then uses ordinary
prerequisites. **This is the only bridge the script needs between its own accounting and the
native research system.**

Breadth gates the infrastructure: research rate, power, production, armour, auto-repair, and
the research-facility `Limit` (yes, `Building.Limit` is upgradeable and vanilla never uses it).

The two gate types pull in opposite directions on purpose. **Depth makes your guns better;
breadth makes your war machine better.** That is a genuine strategic axis, and it is exactly
the branching decision the vanilla tree has zero of.

### 6.3 Signature topics — and why the tree can be huge but feel small

Signature topics apply to **one weapon by `Id`** and are unlocked only by mastering that
specific component.

Because `enableResearch()` reveals topics and un-enabled topics are **invisible**, you can ship
46 signature topics and a player will only ever see the four or five they earned.

> Vanilla's problem is 390 topics all visible from minute one.
> Here ~330 topics exist in the data and perhaps 40 are visible at any moment.

That inverts the "I can't remember the tech tree" complaint that has been open since 2013 —
there is nothing to memorise, because the tree shows you only what you earned.

---

## 7. The technologies that lead to this — the entry path

This is the critical path. Everything in the field tier depends on it, so it must be **early,
cheap, and the obvious first thing you do**.

```
R-Sys-Sensor-Tower01            (vanilla, start-adjacent)
        │
        ▼
R-Struc-CommandRelay            900 pts / 25 pw    → Command Relay Center (limit 1)
        │
        ▼
R-Comp-CommandTurret01          600 pts / 18 pw    → Command Turret + CommandBrain01
        │
        ▼
R-Sys-Debrief01                1200 pts / 40 pw    ★ ENABLES BANKING
        │                                            Until this, commanders accumulate
        │                                            but cannot convert.
        ▼
R-Comp-CommandTurret02         2500 pts / 90 pw    +group size, RankThresholds −10%
        │
        ▼
R-Sys-Debrief02                4000 pts /140 pw    banking yield +40%
        │
        ▼
R-Sys-DataCore                 6000 pts /200 pw    black box recovery 50% → 85%
        │
        ▼
R-Comp-CommandTurret03         9000 pts /300 pw    RankThresholds −15% again, +HP
        │
        ▼
R-Sys-Telemetry               16000 pts /450 pw    remote debrief at 60% yield
```

**Note `RankThresholds` with a negative value.** Vanilla already ships this exactly once
(`R-Comp-CommandTurret02`, `value: -10`) — research that improves *learning itself*. DOCTRINE
makes it a line. Your army getting **better at getting better** is a compounding upgrade that
isn't a damage multiplier.

### 7.1 Bootstrapping

The game opens conventionally. Base research (MG, Light Cannon, trucks, factories, the early
weapon unlocks) is available from the start exactly as now. The field system layers in from
roughly minute five, when your first commander has something to report.

There is no bootstrap deadlock and the mechanic is teachable in one game.

### 7.2 The XP curve must be fixed first

Vanilla rank thresholds are **0 / 4 / 8 / 16 / 32 / 64 / 128 / 256 / 512 kills**. Cyp, a core
dev:

> *"noone pays attention to unit experience since it's useless… in the time it takes to get
> much experience, it would have been much faster to just win the game. Don't think I ever
> reached hero rank."*

If Hero is unreachable, a veterancy-driven system has nothing to trigger on. The devs already
knew — their own commander cheat (`rules/events/chat.js:13`) rewrites the curve to
`[0, 2, 4, 8, 16, 24, 32, 48, 64]`, roughly half. **Adopt something close to that as the
baseline.** It is settable at runtime, per player.

---

## 8. Topic inventory

Generated by `generate_tree.py`. Validated: acyclic, zero dangling prerequisites, every
`class`/`parameter` pair checked against `getUpgradesObject()`, every `filterValue` checked to
match a real component.

| Kind | Topics | Research points | Notes |
|---|---:|---:|---|
| Field (crew skill) | 75 | 45,000 | 11 families × 2 axes × 3 tiers, + 3 chassis classes |
| Signature (per weapon) | 46 | 41,400 | invisible until earned |
| Doctrine (materiel) | 44 | 264,000 | 11 families × 4 tiers |
| Reach (range) | 33 | 209,000 | **an axis vanilla never touches** |
| Penetration | 10 | 100,000 | **makes RPS sharpen over time** |
| Spine (Command) | 8 | 40,200 | vanilla gives this 2 |
| Infrastructure | 8 | 54,800 | breadth-gated |
| Credentials | 4 | 40 | synthetic markers |
| **Total** | **228** | **754,440** | |

Plus the carried-over vanilla weapon/body/propulsion/structure unlock chains (~150 topics),
giving ~380 total — comparable to vanilla's 390, with a completely different composition, and
a far smaller *visible* tree at any moment.

Vanilla for comparison: 390 topics / 3,590,910 points, of which 63% buys nothing.

---

## 9. Script wiring

Everything below is an existing, documented API.

| Need | Mechanism | Verified at |
|---|---|---|
| Read accumulated knowledge | `commander.experience` | `quickjs_backend.cpp:1544` |
| Rank-up notification | `eventDroidRankGained(droid, rankNum)` | `doc/js-events.md` |
| Reveal an earned topic | `enableResearch(id, player)` | `wzapi.cpp:2752` |
| Drop the black box | `addFeature(name, x, y)` | `wzapi.cpp:2011` |
| Recover the black box | `eventPickup(feature, droid)` | `qtscript.cpp:1861` |
| Sacrifice route | `eventObjectRecycled()` | `qtscript.cpp:1513` |
| Damage-absorbed channel | `eventAttacked(victim, attacker)` + `health` | `doc/js-events.md` |
| Per-component upgrades | `filterParameter: "Id"` in `research.json` | `research.cpp:951–966` |
| Runtime XP curve | `Upgrades[p].Brain[b].RankThresholds = [...]` | `rules/events/chat.js:13` |

**The only genuinely new code is the bookkeeping between "banked" and `enableResearch()`.**
Every other layer is a mechanism already in the engine, currently idle or wired to something
trivial.

### 9.1 Traps found while verifying

1. **`filterParameter: "Size"` on Body silently does nothing.** `wzapi.cpp:4392` assigns a raw
   `BODY_SIZE` enum, which serialises as an **integer**, while `ImpactClass` and `Effect` go
   through `getWeaponSubClass()` / `getWeaponEffect()` and serialise as strings. Comparing
   against `"LIGHT"` never matches — and `research.cpp` `continue`s on a non-match **with no
   warning**. Enumerate body `Id`s instead. *(The generator does this.)*
2. **The `Crate` feature has hardcoded engine behaviour.** Iluvalar hit this in 2011 building
   skirmish artifacts: *"that make it disappear half of the time with no research."* Use a
   different feature for the black box.
3. **`researchPower` is capped at 450 across all vanilla data** — a legacy of a removed
   hard-coded C++ limit. Verify nothing clamps values above it before relying on them.
4. **`addFeature` is marked `MUTLIPLAY_UNSAFE`.** Fine for skirmish-vs-AI; needs care if this
   ever goes to MP.

---

## 10. Risks, honestly

| Risk | Severity | Mitigation |
|---|---|---|
| **Death spiral** — losing yields no research | **High** | Knowledge from damage dealt *and absorbed* (§3.3). Non-negotiable; build this first. |
| **AI compatibility** — `Cobra.js` has 759 lines of hardcoded research IDs and will break | **High** | DOCTRINE *adds* topics and leaves vanilla IDs intact where possible. Cobra will still research its list; it just won't use the new system. Budget separate AI work, or start with NullBot, which historically coped best with tree changes. |
| **Legibility** — 30 components with hidden counters is the invisibility problem, worse | **High** | The readout is the feature, not polish. *"Medium Cannon: 47 engagements, 3 from Improved Recoil Dampening."* |
| **Commander mandatory** → one unit type dominates | Medium | Recycle-to-lab route (§4.3) keeps non-commander play viable at reduced rate. |
| **Punished for adapting** — locked into a weapon that stopped working | Medium | Knowledge rolls up by *family*, so Medium→Heavy Cannon is nearly free; only cross-family switches cost. Crew skill transferring within a family is also true to life. |
| **Snowball** — winning fights makes you better at fighting | Medium | Field magnitudes are capped at crew-skill scale (+40% total). Diminishing returns (§5.2) push winners sideways into fresh lines rather than deeper into a won one. |
| **Enum/filter silent no-ops** | Low | Covered by `validate.py`. Run it on every change. |

---

## 11. Build order

1. **Fix `RankThresholds`** to something reachable (§7.2). One line. Everything depends on it.
2. **Field knowledge accrual + debrief**, commander only, no research effects — just a readout
   proving the numbers accumulate and distribute sensibly.
3. **Wire `enableResearch()`** for one family (Cannon) end to end. Play it. This is the moment
   the design is either fun or it isn't — find out here, before generating 228 topics.
4. **Generate the full field + signature tier.**
5. **Doctrine + depth gates.**
6. **Breadth credentials + infrastructure.**
7. **Black box recovery.**
8. **Reach and penetration** — the axes vanilla never used. Save these; they're the payoff.

Step 3 is the real decision point. Everything before it is plumbing; everything after it is
scale.

---

## Files

| File | What it is |
|---|---|
| `generate_tree.py` | The tree as a function of ~20 numbers. Retune the progression by editing `CONFIG`, not 390 JSON objects. |
| `validate.py` | Checks the DAG, dangling prerequisites, and every class/parameter/filter pair against what the engine actually accepts. |
| `out/research-doctrine.json` | 228 generated topics, engine-schema valid. |
| `out/meta.json` | Topics + design metadata for the browser. |
| `techtree.html` | Interactive browser — because you cannot judge a tech tree from a list. |
