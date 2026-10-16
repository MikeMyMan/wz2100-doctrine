# DOCTRINE

**A Warzone 2100 total conversion where research is earned in the field, not queued in a lab.**

Kills drop intel crates carrying **weapon upgrades** — for the weapon the victim was
carrying, with a chance driven by how veteran it was. Drive over the crate and the upgrade
unlocks. Leave it and it decays; let an enemy reach it first and they take it instead. How
good your weapons get depends on what you chose to fight and whether you held the ground
long enough to collect the salvage.

---

## Why

Vanilla Warzone 2100's tech tree is 390 topics, of which **204 unlock nothing at all** while
consuming 63% of total research time. Upgrades are additive, so nine steps of "+25%" is
+225%, not compounding — the ninth step delivers a third of the first step's effect for
twelve times the price. Almost nothing is ever retired, and no research entry touches the
rock-paper-scissors damage tables, so the matchup ratios at minute 60 are byte-identical to
minute 5.

Both sides' numbers inflate. The relationships never move. Symmetric inflation carries no
information.

DOCTRINE replaces the queue with a loop:

```
COMBAT ──▶ crew gains experience ──▶ kill drops intel ──▶ you collect it ──▶ topic unlocks
   ▲                                                                              │
   └──────────────────────── new hardware changes how you fight ◀─────────────────┘
```

## What changes

**Weapon upgrades are salvage.** You still unlock weapons in the lab the normal way. What you
cannot buy are the **improvements** — every family's Damage, Range, Reload and Accuracy
upgrades (206 topics) are hidden from the lab and arrive only in intel crates.

A crate carries an upgrade for **the weapon the victim was actually carrying**, read off its
equipped turrets. Kill veteran rocket units and your rockets improve; kill nothing but
cyborgs and your anti-tank line never does. Drop chance is driven by the victim's veterancy —
**zero from a freshly built unit**, up to 12% from a fully blooded one — scaled by how
significant the target was relative to your own army. Crates are visible to everyone and sit
on the map for five minutes, so contested ground is where the upgrades are.

**Ladders are short and steep.** Damage ladders run four rungs instead of ten, reaching
roughly 90% of vanilla's ceiling for about a quarter of the research cost. Fewer, larger,
more decisive steps.

**The counter tables move.** Machineguns shred infantry and bounce off tracks; anti-tank is
the mirror; artillery sieges buildings but cannot hit a moving tank; flamers are devastating
against bunkers and useless against hardcrete. These are real matchups you are meant to
exploit, not a flat +X% on both sides.

**Cyborgs are a swarm.** Cheap, quick to build, fast on the map — and fragile. They melt to
machineguns and mortars and shrug off anti-tank fire. They cannot flatten a base: their
weapons do 45–60% to buildings, so they stay an anti-unit force.

**Scavengers are a faction, not scenery.** With the optional scavenger component they build
bunkers and towers around their derricks, field infantry squads of three, run suicide bomb
trucks in four grades, put helicopters up late, and research alongside everyone else.
Flatten an occupied house and its residents come out shooting — that part works regardless.

> **The scavenger component is a patch, not a download.** It changes *Ultimate Ultimate
> Scavengers 2*, which is somebody else's mod, so DOCTRINE ships the changes rather than the
> file. Install that mod yourself, then run `scav/patch_uuscav2.py` — it verifies all 23
> changes against your copy, backs it up, and rewrites it in place. Skip it and you get the
> game's own scavengers with everything else in DOCTRINE unchanged.

**Every AI plays by these rules.** Nexus, SemperFi, Cobra, BoneCrusher, NullBot, Hover and
Turtle all run the DOCTRINE research engine, pick a weapon family that matches their own
declared personality, and collect crates on the field the same way you do.

## Requirements

- **Warzone 2100 4.5.x or 4.7.x** (built and tested against 4.5.5 and 4.7.0)
- Skirmish / multiplayer only — **do not** load it for the campaign

## Install

1. Download the `.wz` for your game version.
2. Drop it in your autoload folder:
   - **Windows** `%APPDATA%\Warzone 2100 Project\Warzone 2100\mods\<version>\autoload\`
   - **Linux** `~/.local/share/warzone2100/mods/<version>/autoload/`
   - **macOS** `~/Library/Application Support/Warzone 2100/mods/<version>/autoload/`

   Replace `<version>` with `4.5.5` or `4.7.0` to match your build.
3. Start a skirmish. The mod is active when a research lab offers far fewer topics than usual
   and kills start dropping crates.

**New to it? Read [GAMEPLAY.md](GAMEPLAY.md).** It covers the crate loop, the depth and breadth
gates, and the two matchup tables — which matter far more here than in vanilla, because picking
the wrong weapon now fails outright rather than merely underperforming.

Anything in `autoload/` loads automatically and applies to every skirmish. Remove the file to
play vanilla again. Two total conversions cannot be stacked — if you run another balance mod,
take it out first.

## Playing it

The first minutes are ordinary: build trucks, take oil, research the opening machinegun. The
change arrives with your first kill.

- **Collect your crates.** They are on the map for anyone to take. Ignoring them is refusing
  your own research.
- **Veterans are worth more dead than green ones.** Killing a decorated enemy unit is the
  richest source of tech in the game.
- **Losses teach nobody.** Your own destroyed units drop nothing, and neither does farming
  your own buildings.
- **Breadth opens infrastructure.** Reaching tier 2 in several different weapon families
  unlocks the Combined Arms credentials, which open the economic and structural tree.
- **You start with two labs**, and earn one more per research upgrade, to a maximum of five.

Type `doctrine` in the in-game chat for a status readout, or `doctrine ai` to see what the AI
players have salvaged.

## Compatibility and scope

- Skirmish and multiplayer. **Not** the campaign — move the file out of `autoload/` first.
- Replaces `stats/` (weapons, bodies, research, structures, damage tables) and patches the
  bundled skirmish AIs. Any other mod touching those files will conflict.
- Save games made with DOCTRINE loaded need DOCTRINE to load them. Crates on the field,
  collected topics and pity state all survive a save/reload.

## Credits and licence

DOCTRINE is by Martin Steinke, licensed **GPL-2.0-or-later**, the same licence as Warzone
2100 itself. It contains modified copies of Warzone 2100's own skirmish AI scripts and stat
files, which are GPL-2.0-or-later and copyright their respective authors.

See [CHANGELOG.md](CHANGELOG.md) for release history, and [PLAYTEST.md](PLAYTEST.md) for the
measured reasoning behind individual balance decisions.

### For players

- [GAMEPLAY.md](GAMEPLAY.md) — how to play it: the loop, the gates, the matchup tables
- [CHANGELOG.md](CHANGELOG.md) — what is in this release, and what is known-broken

### For developers

- [HANDOVER.md](HANDOVER.md) — start here: project state, backlog, risks
- [ARCHITECTURE.md](ARCHITECTURE.md) — how the build and runtime work
- [TUNING.md](TUNING.md) — where to change any balance value
- [CONTINUE-HERE.md](CONTINUE-HERE.md) — build, test and release commands

### Design and record

- [DOCTRINE.md](DOCTRINE.md) — the design specification: the loop, the gates, the curves
- [COMBAT.md](COMBAT.md) — the combat rebalance and the unlock ratchet
- [IMPLEMENTATION.md](IMPLEMENTATION.md) — kill accounting and the engine API
- [PLAYTEST.md](PLAYTEST.md) — 32 rounds of measured reasoning behind every balance decision
- [REBALANCE-SUMMARY.md](build/REBALANCE-SUMMARY.md) — full stat diff against vanilla
