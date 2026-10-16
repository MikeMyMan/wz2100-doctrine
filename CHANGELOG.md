# Changelog

All notable changes to DOCTRINE. Dates are the build date; version numbers follow
[semantic versioning](https://semver.org/).

## 1.0.0 — 2026-09-04

First public release.

### The core loop

- Kills drop **intel crates** carrying a **weapon upgrade** — one of Damage, Range, Reload or
  Accuracy at the player's current tier, for the family the victim was actually carrying
  (read off its equipped turrets). Weapon *unlocks* stay normally researchable; it is the 206
  upgrade topics that are hidden from the lab and crate-only.
- Drop chance is driven by the victim's veterancy: **zero** from a freshly built unit, rising
  to 12% at full veterancy for a parity-cost target, scaled by relative worth, plus up to
  +60% for a veteran killer and a pity counter on misses, capped at 90%.
- Crates are visible to all players, decay after five minutes, and can be taken by whoever
  reaches them first.
- Of 601 topics, 303 are normally researchable and 298 are gated — 206 weapon upgrade axes
  plus the breadth credentials and signature topics. **Depth** gates advance a
  family tier by tier; **breadth** credentials (Combined Arms Doctrine 2–5) open the
  economic and structural tree once several families reach tier 2.
- Research labs start at two and increase by one per research upgrade, to a maximum of five.
- Destroyed units and buildings can leave **oil drums** (5%); flattened scenery can yield
  intel at your own tech level (1.5%).

### Combat rebalance

- Damage ladders shortened from ten rungs to four, reaching ~90% of vanilla's ceiling for
  roughly a quarter of the research cost.
- Weapon-vs-propulsion and weapon-vs-structure tables retuned so matchups matter: machineguns
  shred infantry and bounce off tracks, anti-tank is the mirror, artillery sieges buildings
  but cannot track a moving tank, flamers gut bunkers and do nothing to hardcrete.
- Machineguns deliberately removed from demolition duty so they cannot chew through
  generators.
- Cyborgs made cheap, quick and **fragile** — a genuine swarm that melts to machineguns and
  mortars, shrugs off anti-tank fire, and cannot demolish a base.
- Elevated defensive structures get +15% weapon range over their ground-level equivalents.
- Projectile flight speeds raised so machinegun and cannon fire reads as near-hitscan.

### Scavengers

- Promoted from scenery to a faction: staged escalation through four phases of bodies and
  weapons, research parity with the other players, and a production ceiling that keeps early
  pressure without the late exponential.
- Fortify their own derricks, factories and generators with bunkers, gun towers, mortar pits
  and rocket pits — four emplacements per site.
- Infantry built in squads of three, continuously, as a share of their unit ceiling.
- **Suicide bomb trucks** in four grades (Truck, Bus, Tanker, Rig) that detonate with the
  power-generator explosion. Their gun reaches only 40, well inside their own blast radius,
  so they must close to kill.
- Helicopters capped at 25% of the unit ceiling so the late game stays a ground war.
- Multi-turret vehicles draw all their weapons from one range band, so every barrel reaches.
- Flattening an occupied house turns out 1–5 armed scavengers.

### AI

- All seven bundled AIs — Nexus, SemperFi, Cobra, BoneCrusher, NullBot, Hover, Turtle — run
  the DOCTRINE research engine, choose a weapon family matching their own declared
  personality, and collect intel crates in the field.
- **Anti-air tanks.** Nexus previously referenced no anti-air turret in any of its 21 files
  and SemperFi none in any of its 9; both built AA structures at home while their field armies
  could not shoot back at aircraft. Nexus, SemperFi and BoneCrusher now build them —
  measured, with the gate forced open for the test: Nexus 16/12/31 per player, SemperFi
  10/16/7, BoneCrusher 1/2/4. Cobra and the NullBot family list AA turrets in their own tank
  weapon tables and need no patch. Production is gated on a live air threat, because anti-air
  turrets are subclass `A-A GUN`/`A-A MISSILE` and can only engage aircraft.
- SemperFi's production and defence lists widened, and unit production spread across the best
  three available weapons — its lists are priority lists, so it previously fielded exactly one
  weapon at a time.
- NullBot, Hover and Turtle now count scavengers as an enemy. Stock NullBot enumerates
  players as `i < maxPlayers`, so the scavenger faction did not exist for it; with every other
  player allied it saw no enemy, built trucks forever and was overrun.

### Notable fixes

- Destroyed **features never fired `eventDestroyed`'s attribution path**, because the engine
  emits `eventAttacked` only for droids and structures. Houses therefore produced neither
  intel nor scavengers in any game. Scenery is now handled before the last-hitter gate.
- Anti-air turrets are air-only (`A-A GUN` / `A-A MISSILE` subclass), so AA production is
  gated on a live air threat rather than built speculatively.
- Cyborg weapons paired with the body that can actually mount them; an invalid pairing made
  `buildDroid` fail outright and produced flamer-only cyborgs.
- Scavenger pathing guarded against an unroutable truck, which threw and aborted the whole
  scavenger tick.

### Pre-release audit (2026-10-16)

A full audit before first publication. Findings, all addressed:

- **The 4.5.5 build had never actually been played.** Every playtest in development ran
  on 4.7.0; the 4.5.5 archive was built and verified by inspection only. It has now been
  run on the 4.5.5 engine across four games up to 93 minutes — all five AI types load and
  announce, intel crates drop and are recovered, 0 script errors, 0 asserts, 0 failed
  builds.
- **`lastHit` grew without bound.** A last-hitter record is written for every object that
  is *attacked* and was only ever deleted when that object was *destroyed*, so anything
  shot at and merely damaged left a permanent entry. The engine serialises script globals
  into savegames, so it inflated both memory and save size over a long game. The existing
  20-second sweep now prunes records older than `STALENESS`, which can never be used
  again.
- **`minVersionSupported` claimed 4.5.0** but the mod has only ever been built against and
  played on 4.5.5 and 4.7.0. Corrected to `4.5.5` rather than inviting untested
  installations.
- **Census telemetry would throw with scavengers switched off** — `enumDroid(undefined)`.
  Debug-build only, now guarded.

Verified clean and needing no change: no `Math.random` in the mod's own sync-relevant
paths (the one occurrence in Nexus is stock code); cheat commands correctly gated behind
cheat mode and the local player; all `debug()` calls unreachable in a production build;
no TODO/FIXME markers; player indexing bounded by `maxPlayers` throughout; and every
factual claim in the README checked against the shipped data.

Save/reload persistence, previously asserted, is now **evidence-backed**: a real savegame
contains `crates`, `drums`, `pity`, `researched`, `unlocked` and `stats` under
`globals_0` in `scriptstate.json`.

### Known issues

- Turtle remains fragile on maps where it starts beside a strong enemy; it is defensive by
  design and slow to field an army.
- Cobra's native anti-air production has not been observed firing. It lists AA turrets and
  needs no patch, but its own air detection never tripped in testing because no test game
  produced real aircraft — scavenger helicopters arrive at 15 minutes and the scavengers were
  dead before then in every long run.
- Occasional non-fatal `JSValueToInt32` engine asserts in long NullBot games, in the final
  minutes when the scavenger faction is nearly gone. Play is unaffected.
- `STARTER_DEFENCES` ships as an empty list with a documented no-op helper — dead code
  left from an earlier design, harmless but not yet removed.
- Whether the engine enforces `mod-info.json`'s `"type": "alternateMP"` to keep the mod
  out of the campaign has **not** been verified. Anything in `autoload/` applies to every
  game, so the instruction to move the file out before playing the campaign stands as the
  conservative answer.
- The `ALL ROUNDER` (cannon) effect is mediocre on both counter tables with no matchup it
  clearly wins — a known open balance question.
