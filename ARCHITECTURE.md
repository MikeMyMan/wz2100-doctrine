# DOCTRINE — architecture

How the mod is actually put together, as of version 1.0.0. Read this before changing
anything; `CONTINUE-HERE.md` covers how to run the build, this covers what the build *is*.

`IMPLEMENTATION.md` predates this document by three weeks and describes the kill-accounting
algorithm and the engine API accurately, but **not** the AI patch system, the release
pipeline, or anything added after mid-August. Where the two disagree, this file is current.

---

## 1. The shape of the thing

DOCTRINE is one `.wz` archive — a plain zip the game auto-loads. It contains three kinds of
thing, and they work in completely different ways:

| kind | files | mechanism |
|---|---|---|
| **stat overrides** | `stats/*.json` | the game merges them over its own tables at load |
| **a rules script** | `multiplay/script/mods/doctrine.js` | runs every game, owns the crate loop |
| **patched AI scripts** | `multiplay/skirmish/**` | *replace* the game's bundled AI files |

The third is the one that surprises people. There is no hook system for skirmish AIs: to
change how Nexus builds tanks you must ship a whole modified copy of `nexus_includes/production.js`
that shadows the game's own. `build_mod.py` therefore reads each AI file out of the game's
`mp.wz` at build time, applies textual patches, and ships the result. **Every AI patch is a
string transformation against a specific upstream file**, which is why the build asserts
loudly when an anchor string is not found — a game update that rewords a line breaks the patch,
and failing the build is far better than silently shipping an unpatched AI.

---

## 2. Build pipeline (`build_mod.py`)

One script, ~3,100 lines, run as `py -X utf8 build_mod.py <4.7.0|4.5.5> [--telemetry]`.

```
   game's mp.wz  ─────┐
                      ├──▶  build_research()   ──▶ merged research tree (601 topics)
   out*/research-      │
   doctrine.json ─────┘
                                    │
   game's stats/*.json ──▶ apply_* passes ──▶ rebalanced stats
                                    │
   game's AI scripts   ──▶ text patches   ──▶ patched AI scripts
                                    │
   doctrine.js         ──▶ TELEMETRY flag  ──▶ runtime script
                                    │
                                    ▼
                     staging/  ──zip──▶  doctrine.wz
                                    │
                                    ▼
              %APPDATA%\...\mods\<version>\autoload\doctrine.wz
```

**It never writes into a game installation.** Game folders are read-only by project rule;
everything installs to `%APPDATA%`. The only reads from the install are `mp.wz` and its
siblings.

### 2.1 The stat passes

Applied in `main()` in this order. **Order matters** in two places, both marked in the source:

```python
weapons = apply_scav_technicals(...)   # scav bodies + improvised guns
bodies  = apply_cyborg_tuning(...)     # cheap, quick, fragile
bodies  = apply_bomb_truck_body(...)   # ScavBomberBody clone
weapons = apply_mg_ladder(...)         # the MG damage line
weapons = apply_weapon_tuning(...)     # per-weapon outliers, incl. scav defences
weapons = apply_bomb_truck_gun(...)    # BaBaMG-Pointblank clone
weapons = apply_flight_speed(...)      # near-hitscan bullets
weapons, structures = apply_elevation(...)   # LAST -- see below
```

- `apply_elevation` runs **last** so the `-Elev` variants it clones inherit every earlier
  weapon change. Move it earlier and elevated defences silently keep pre-tuning damage.
- The clone passes (`apply_bomb_truck_gun`, `apply_bomb_truck_body`, the scav mortar) create
  *new* component ids by deep-copying an existing entry and overriding fields. This is the
  pattern to reuse when you want to change something for one user without changing it for
  everyone who shares that component.

### 2.2 The research tree

`build_research()` merges the vanilla tree with `out*/research-doctrine.json`, deletes the
surplus upgrade ladder, and strips prerequisites from script-gated topics so they are hidden
until `doctrine.js` reveals them.

Two rules that cost real debugging:

1. **Empty `requiredResearch` means hidden, not free.** A topic with no prerequisites is
   invisible until `enableResearch()` names it. That is how crate-gating works.
2. **Weapon *unlocks* must never sit behind crate-only topics.** 37 of them did once, which
   froze every player on the starting machinegun for a whole match. `main()` removes axis
   topics from every prerequisite list and re-anchors the orphans onto their own family's
   unlock chain at matching depth. Read the long comment there before touching prerequisites.

`RESEARCH_OVERRIDE` is the small dict for retuning individual topics (currently the VTOL line).

### 2.3 The AI patch system

Every AI gets the same research engine plus its own targeted fixes.

- **`DOCTRINE_ENGINE_JS`** is one large JS string injected into *each* AI's `research.js`.
  It carries the scoring model (`doctrineWeight`, `doctrineRankedTopics`), the family
  detection (`doctrineFamilyHints` reads each AI's own declared personality), and shared
  helpers like `doctrineAirThreat()`. Because it lands in every AI's script instance, any
  function defined here is callable from that AI's other files — that is how Nexus's
  `production.js` can call `doctrineAirThreat()`.
- **`SEMPERFI_LISTS`** widens SemperFi's priority lists by replacing whole array literals.
- Per-AI textual patches live inline in `main()`, each preceded by a comment explaining the
  measured behaviour that motivated it.

> **The AI codebases do not share a standard library.** Nexus and SemperFi have a `random(n)`
> helper; BoneCrusher has none and uses `Math.random()` throughout. Calling the wrong one
> throws `ReferenceError` on every tick — roughly 7,000 per game — and the game keeps running,
> so it will not announce itself. Check which helpers exist in the file you are patching.

### 2.4 Telemetry

`--telemetry` flips `const TELEMETRY = false;` to `true` in `doctrine.js`, enabling `debug()`
output. **Never ship a telemetry build.** `package_release.py` refuses to package one, and
also refuses any archive still containing a debug probe string.

---

## 3. Runtime (`doctrine.js`)

A rules-script mod loaded into the game's own rules instance. It wraps the existing event
handlers rather than replacing them — `__doctrinePrevDestroyed` and friends hold the previous
handler and are always called first, so the game's own logic and any other mod still run.

### 3.1 The crate loop

```
eventAttacked  ──▶ lastHit[obj] = { killer, exp, t }      (droids + structures ONLY)
eventDestroyed ──▶ tryDrop()  ──▶ spawnCrate()  ──▶ feature on the map
eventPickup    ──▶ collectCrate() ──▶ grantTopic() ──▶ enableResearch()
```

`tryDrop` decides the drop chance from the victim's **veterancy** and a **weight** comparing
its cost to the killer's own 75th-percentile unit cost (`myReference`) — you learn nothing
from something far beneath you. A pity counter stops long dry spells.

`nextTopic` picks what a crate yields at *pickup* time, not spawn time, so a crate is worth
whatever the collector still needs.

### 3.2 The trap that hid two features for months

**The engine fires `eventAttacked` for droids and structures only.** A destroyed *feature*
therefore has no last-hitter record. The original `eventDestroyed` checked `rec === undefined`
and returned before reaching its FEATURE branch, so scenery intel and house scavengers were
both dead code — `scenery intel` reads 0 in every playtest before round 32.

Features are now handled **before** that gate, and attributed by proximity (`featureKiller`,
closest non-scavenger droid within 8 tiles). If you reorganise `eventDestroyed`, keep the
feature branch first.

### 3.3 Other runtime responsibilities

- Research lab limits (`applyLabLimit`) — two labs, +1 per research upgrade, max five.
- Tier and breadth gates (`currentTier`, `BREADTH_LEVELS`).
- Scavenger research parity — every completed topic is granted to the scavengers. This lives
  here rather than in the scavenger mod because **two mods cannot both ship
  `multiplay/script/mods/init.js`**.
- The `doctrine` chat commands.

---

## 4. The scavenger component (`uuscav2`)

A **separate archive**, shipped only for 4.7.0, holding a heavily modified
`ultimateScavengers.js`. Repack it with `harness/repack_uuscav2.py` after editing.

It is not built by `build_mod.py` and is deliberately **not** in `dist/` — see
`dist/README-DIST.md` for the licensing question that blocks distributing it.

Its DOCTRINE changes are marked `DOCTRINE PATCH` in the source: staged escalation by phase,
production ceilings, picketing its own derricks, infantry squads, bomb-truck grades, the
helicopter share cap, and range-banded multi-turret vehicles.

---

## 5. Release (`package_release.py`)

Builds both versions, then **gates** before packaging: telemetry must be off, no debug probe
strings may remain, and every shipped `.js` must pass `node --check`. Writes `dist/` with the
archives, the docs, `README-DIST.md` and a checksum `MANIFEST.md`.

The gates exist because a telemetry build and a probe both shipped by accident during
development, and were caught only by reading the archive afterwards.

---

## 6. Testing

See `CONTINUE-HERE.md` §5 for the harness rules — they are not optional reading. The short
version: run headless games in an isolated `--configdir`, use exact `ai` script paths, and
verify each log actually loaded its AIs before believing any number in it.

Two facts about the test environment worth repeating here:

- `4c-rush` ("Sk-Rush") has **zero building features**. Anything involving houses must be
  tested on `Thales` (206 buildings).
- A feature gated on enemy aircraft cannot be exercised by a normal game — scavenger
  helicopters arrive at 15 minutes and the scavengers are usually dead first. Force the gate
  open in a throwaway build to test the branch, then ship the gated version. That technique
  found the BoneCrusher `random()` bug.
