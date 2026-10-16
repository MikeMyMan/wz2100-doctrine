# Continue DOCTRINE on another machine

Everything needed to rebuild, test and publish is in this archive. Nothing here depends on
the machine it was packed on except two game-install paths, both overridable (below).

## 1. What you need installed

| | why |
|---|---|
| **Python 3.10+** | the build (`py -X utf8 build_mod.py`) |
| **Warzone 2100 4.7.x and/or 4.5.x** | the build reads each version's `mp.wz` |
| **Node.js** *(optional)* | syntax-gates every shipped script before packaging |

## 2. Unpack

```
wz-doctrine_2/    the mod source  -- put anywhere, e.g. C:\Users\<you>\Downloads\
uuscav2/          scavenger source -- keep it BESIDE wz-doctrine_2, same parent folder
tests/            headless test configs
harness/          the parallel playtest runner
dist/             the built 1.0.0 release
```

`uuscav2/` must sit next to `wz-doctrine_2/` — the scavenger repack script uses that relative
layout.

## 3. Point it at your game installs

The build defaults to the standard Windows locations. If yours differ, set these instead of
editing any file:

```powershell
$env:WZ_MP_WZ_470 = "D:\Games\Warzone 2100\data\mp.wz"
$env:WZ_MP_WZ_455 = "D:\Games\Warzone 2100-4.5.5\data\mp.wz"
```

Defaults if unset:
- 4.7.0 → `C:\Program Files\Warzone 2100\data\mp.wz`
- 4.5.5 → `C:\Program Files\Warzone 2100-4.5.5\data\mp.wz`

Node is found on `PATH`; override with `NODE_EXE` if it is somewhere unusual.

## 4. Build

```powershell
py -X utf8 build_mod.py 4.7.0      # builds AND installs to %APPDATA%\...\mods\4.7.0\autoload\
py -X utf8 build_mod.py 4.5.5
py -X utf8 build_mod.py 4.7.0 --telemetry   # debug build: enables debug() output
```

`build_mod.py` never writes into a game installation — game folders are read-only, everything
installs to `%APPDATA%\Warzone 2100 Project\Warzone 2100\mods\<version>\autoload\`.

To rebuild the scavenger archive after editing `uuscav2/multiplay/script/scavengers/ultimateScavengers.js`:

```powershell
py -X utf8 harness\repack_uuscav2.py
```

To rebuild the release (`dist/`, with checksums, refusing any build containing telemetry or a
debug probe):

```powershell
py -X utf8 package_release.py
```

## 5. Test

Copy `tests\*.json` into `%APPDATA%\Warzone 2100 Project\Warzone 2100\tests\`, then:

```powershell
powershell -ExecutionPolicy Bypass -File harness\run_battery.ps1
py -X utf8 harness\analyse.py
```

`run_battery.ps1` runs several headless games in parallel, each in its own throwaway config
directory. Edit the `$runs` list at the top to choose configs and the `$wall` value for the
wall-clock limit in seconds.

### Harness rules — learned the hard way, do not skip

1. **Always use `--configdir=<scratch>`.** A headless run with `--nosound` against your real
   profile writes `sound=0` into your config on exit. It silently killed game audio once and
   took a while to trace.
2. **`--skirmish=` needs the `.json` extension.** Without it the game silently falls back to a
   default 10-player all-Nexus match and every result is meaningless.
3. **The `ai` field must be a path relative to `multiplay/skirmish/`:** `nexus.js`,
   `Cobra.js` (capital C), `semperfi.js`, `nb_generic.js`, `nb_hover.js`, `nb_turtle.js`,
   `bonecrusher/bonecrusher.js`. Bare names or full paths make the engine read *garbage* for
   the script name — it logs `utf8::is_valid` and `unable to open file` asserts plus
   `Failed to load AI`. Those asserts are **not** benign noise. Two rounds of conclusions were
   once drawn from games in which no AI had loaded.
4. **`player_0` is the autogame host** and never receives an AI script. Real AIs are 1–3.
5. **Check before trusting any result:** no `Failed to load AI`, the expected map loaded, and a
   `DOCTRINE-AI` identity line for every expected player.
6. **Map matters.** `4c-rush` ("Sk-Rush") has 29 features, all oil — *zero buildings*. Anything
   involving houses must be tested on **`Thales`** (206 buildings). Note the challenge `map`
   field takes the display name (`Thales`), not the folder name (`7c-Thales`).
7. `debug()` output lands in the **stderr** file, not stdout.
8. `numKills` is not a property on structure objects — a probe reading it returns 0 everywhere.
9. Kill runs by PID (`Stop-Process -Id`). `taskkill /IM` kills every instance, and `timeout`
   cannot kill the binary at all.

## 6. Where things live

| path | |
|---|---|
| `build_mod.py` | the whole build: stat rebalance, research tree, AI patches, packaging |
| `doctrine.js` | the runtime script — crates, drops, house scavengers, tier gates |
| `uuscav2/.../ultimateScavengers.js` | scavenger AI |
| `out/`, `out-4.7.0/` | **build inputs** — pre-computed research tree + vanilla stats, do not delete |
| `HANDOVER.md` | project state, backlog, risk register — **read this first** |
| `ARCHITECTURE.md` | how the build pipeline, AI patching and runtime fit together |
| `TUNING.md` | every balance knob and which file it lives in |
| `PLAYTEST.md` | 32 rounds of measured reasoning behind every balance decision |
| `DOCTRINE.md`, `COMBAT.md` | design specification |
| `IMPLEMENTATION.md` | implementation notes |

`build/` and `build-4.7.0/` are regenerated staging directories and are not in this archive
(except `build/REBALANCE-SUMMARY.md`, which the README links).

## 7. State as of 2026-09-05

Version **1.0.0**, built and verified for both game versions. `dist/` holds the release.

**Open items, in the order I would take them:**

1. **The scavenger licensing question — blocks publishing the scavenger component.**
   `uuscav2` shares only ~1.4% of its content with the game's own `ultimateScavengers.js`, so
   it is genuine third-party work with unknown author and licence; DOCTRINE's version is ~64%
   derived from it. Four ways forward in `dist/README-DIST.md`. The mod as packaged plays
   correctly on stock scavenger settings.
2. **Add `COPYING`** (GPL-2.0 full text) to the distribution.
3. **Cobra's anti-air is unconfirmed.** It lists AA turrets natively and needs no patch, but
   its own detection never tripped in testing because no test game produced real aircraft.
4. **Cannon (`ALL ROUNDER`) is mediocre on both counter tables** with no matchup it clearly
   wins. The natural niche is HARD structures. Flagged, never actioned.
5. **The squad-tactics idea** — smaller raid squads targeting oil, consolidation for base
   assaults, a home QRF. Investigated long ago; no plan written, no code.
6. **Weapon-upgrade inflation**, diagnosed and deliberately left alone: ladders truncated
   10→4 rungs at +223% (~4x cheaper than vanilla), and `doctrineFreeIntel()` grants Hard/Insane
   AI roughly 34/68 free weapon upgrades per 86-minute game. The smallest effective lever is
   the free-grant timer, because it is AI-only.

**Two traps worth remembering:**

- Anti-air turrets are subclass `A-A GUN` / `A-A MISSILE` and can **only** engage aircraft, so
  AA production must stay gated on a live air threat.
- The AI codebases do not share helpers. Nexus and SemperFi have `random()`; BoneCrusher has
  only `Math.random()`. Calling the wrong one throws ~7,000 `ReferenceError`s per game and the
  game keeps running, so it is easy to miss.
