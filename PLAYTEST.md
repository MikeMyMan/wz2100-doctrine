# DOCTRINE v3 — playtest guide

## Which game install to use

DOCTRINE is now built for **both** of your installs — each gets its own build from
its own game data:

| install | mod location | build command |
|---|---|---|
| **4.7.0** (`C:\Program Files\Warzone 2100`) — recommended | `mods\4.7.0\autoload\doctrine.wz` | `py -X utf8 build_mod.py 4.7.0` |
| 4.5.5 (`C:\Program Files\Warzone 2100-4.5.5`) | `mods\4.5.5\autoload\doctrine.wz` | `py -X utf8 build_mod.py 4.5.5` |

## How to see that the mod is loaded

1. **Main menu:** the version string in the bottom corner lists loaded mods —
   with DOCTRINE active it shows `Mods: doctrine` (plus `uuscav2` on 4.7.0).
2. **In a skirmish:** the console prints **"DOCTRINE active — kill, salvage,
   research."** right at the start.
3. **Anytime in-game:** type `doctrine` in chat — if the mod is running you get
   the status dump; if nothing happens, it isn't loaded.
4. Your logs also show it: `%APPDATA%\Warzone 2100 Project\Warzone 2100\logs\`
   contains `Included new script file multiplay/script/mods/doctrine.js` when
   run with `--debug=script`. (Your 16:05 run today loaded no mods — the 4.7.0
   autoload folder was still empty at that point.)

## Your other mods (4.7.0)

- **Scavengers rebuilt as technicals.** Vanilla scav civilian vehicles were
  absurdly durable — a School Bus had **200 HP, the same as a Python** and 3× a
  Viper — while hitting softer than your own guns (BusCannon 28 vs Cannon1Mk1 35).
  They tanked early weapons on hit points, not armour. Now:
  - **Civilian shells lose 30% HP, armour drops harder:** bus 200→140, fire
    engine 200→140, van 160→112, camper 130→91, jeep 120→84, buggy 100→70,
    trike 80→56 — and their armour is cut where it matters (bus 4→2 kinetic,
    van 6→2, camper 6→2). Working plant takes −20%: tractor 150→120, cranes
    140→112, armoured truck 190→152. A bus still soaks more raw damage than a
    Viper (65 HP), but its paper-thin armour means your weapons land far closer
    to full damage now.
  - **Their guns hit much harder:** BusCannon and BaBaCannon 28→**46** damage,
    BabaRocket 20→**34**, scav MGs +40%, scav rocket VTOL 46→60.
  - **But they aim badly:** accuracy cut ~25–30% across the board (BusCannon
    60/50 → 45/32).
  - **And the heavy guns must stop to fire:** cannons and rockets now have
    `fireOnMove: 0`, so a charging technical has to halt before it can shoot —
    which is your opening to kite it.
  - **Genuinely armoured units keep their armour:** ScavNEXUStrack stays
    225 HP / 14 armour, the armoured truck only trims 190→140.
  - *Engine limit worth knowing:* Warzone has **no partial "accuracy while
    moving" stat** — `combat.cpp` only offers the hard `fireOnMove` gate. So
    "inaccurate on the move" is expressed as stop-to-fire on the heavy weapons
    plus the flat accuracy cut, which is as close as the data model allows.
  - Untouched on purpose: the scav rocket **pits** (already high DPS defensive
    emplacements) and `MG3Mk1`/`Flame1Mk1`/`Mortar1Mk1` — those are *your* own
    weapons that scav towers merely borrow, so changing them would nerf you.
- **NEXUS Tank held back.** The scav capture unit (`ScavNEXUStrack` +
  `ScavNEXUSlink`) takes your units and buildings outright, has 225 HP and 14
  kinetic armour — 3.5× a Viper body — yet cost the scavs only 29 power, and the
  stock script could field it from minute one with no counter available. It is
  now gated to **20 minutes** of game time; before that the same factory slot
  builds an ordinary scav tank. Tune `NEXUS_TANK_AFTER` at the top of
  `uuscav2\multiplay\script\scavengers\ultimateScavengers.js`, then repack.
- **uuscav2** — *not* part of the base game. The base game does ship an
  "Ultimate Scavengers" lobby option, but your download is a modified variant of
  that scavenger AI plus a rule that grants scavengers every tech any player
  researches. It's installed as `mods\4.7.0\autoload\uuscav2.wz` (scav AI script
  only — pick "Ultimate Scavengers" in the lobby's scavenger setting to use it).
  Its research-sharing rule collided with DOCTRINE (both mods ship
  `multiplay/script/mods/init.js`), so that part now lives inside doctrine.js —
  `SCAV_RESEARCH_PARITY` at the top, set `false` to turn it off.
- **wz2100mp_LRF_Parity** — a full stat/model conversion, packaged to
  `mods\4.7.0\global\wz2100mp_LRF_Parity.wz`. It replaces the same stat files as
  DOCTRINE, so they can never run together. Play it (without DOCTRINE) via:
  `"C:\Program Files\Warzone 2100\bin\warzone2100.exe" --mod=wz2100mp_LRF_Parity.wz`
  after temporarily moving doctrine.wz out of `autoload\`.
- **Warzone Reforged FX** — shader-only (Vulkan) graphics overhaul pinned to
  4.7.0; no stats or scripts, stacks cleanly with DOCTRINE. Needs the Vulkan
  backend (Options → Video → Graphics Backend).

**The mechanic changed**: research is no longer unlocked by an invisible knowledge
counter. Killing a worthwhile enemy unit has a chance to drop an **intel crate** at
the wreck. Drive any unit over it and one research topic from the **victim's**
weapon family appears in your labs — you salvage *their* tech. If an enemy unit
reaches the crate first the intel is destroyed, and a crate left in the field
**decays after 5 minutes**.

The mod is **built and installed**. Launch the game normally, start a skirmish.

```
Installed at:  %APPDATA%\Warzone 2100 Project\Warzone 2100\mods\4.7.0\autoload\doctrine.wz
Logs:          %APPDATA%\Warzone 2100 Project\Warzone 2100\logs\
Rebuild:       py -X utf8 build_mod.py 4.7.0  (in this folder; also reinstalls)
Uninstall:     delete the doctrine.wz from the autoload folder
```

## How the loop works now

1. **Kill** an enemy combat unit. **Only crews that had learned something leave
   anything behind** — a unit that never fought has nothing to teach, however
   expensive it was. Chance now scales *continuously* with the dead unit's
   **experience**, which the engine accrues from damage dealt as well as from
   kills. So even a lightly-blooded unit carries a small chance, and every hit it
   landed — especially every kill it scored — raises it:

   | victim experience | roughly | drop chance | with a Hero killer |
   |---|---|---:|---:|
   | 0 | never fought | **0%** | **0%** |
   | 0.5 | a few hits landed | 0.2% | 0.3% |
   | 1 | — | 0.5% | 0.8% |
   | 2 | ~one kill | 1.3% | 2.1% |
   | 4 | — | 3.4% | 5.5% |
   | 7 | — | 6.7% | 10.7% |
   | 11+ | veteran crew | 12% | 19.2% |
   | scavenger (any) | — | 3.6% flat | 5.8% |

   Those figures are for a parity-cost target; the kill-weight below still
   multiplies them (up to 2.5× for something well above your own army).
   Previously *every* kill rolled a flat 20% regardless of rank — losing a
   screen of green units handed the enemy a stream of free intel. Now it hands
   them nothing.

   The full formula: `12% × (victim experience ÷ 11, capped)^1.3 × kill-weight × killer veterancy`.
   The `^1.3` bends the low end down so barely-blooded units drop noticeably less,
   while a veteran crew is worth exactly what it was:
   - *kill-weight* compares the victim's cost to the 75th percentile of your own
     army — killing above your weight rolls up to 2.5×.
   - *veterancy of the killing unit* adds up to **+60%** (was +50%) — veterans
     read the wreckage better.
   - Every miss feeds a **pity pool** that boosts later rolls, so real combat
     always pays out eventually. Killing a unit with zero experience feeds
     nothing at all — treated exactly like a target far beneath your army.
   - **Scavengers** never drop to zero: they sit far below any real army, so the
     curve would zero them out, but they still carry usable hardware. A scav kill
     roll a **flat** `SCAV_FLOOR` → **3.6%** (5.8% for a veteran), and
     the crate holds that scav weapon's family — kill scav MG buggies for MG
     intel, flamer scavs for Flamer intel, and so on. Scav misses deliberately do
     **not** feed the pity pool, so farming a scav base can't pump your rate for
     real fights. The floor only bites once your army outclasses the scavs —
     early on the cost-weight is already above it, so this governs late-game
     scav relics rather than the opening.
2. **Salvage** — a crate appears at the wreck (console announces the position).
   Any of your units driving over it collects it.
3. **Research** — the revealed topic (Warhead / Fire Control / Loading Drill /
   Gunnery at the family's current tier) is paid for in a lab as normal.
4. **Tier gate** — a family only drops tier-2 intel once all four tier-1 axes are
   *researched*, and so on through tier 4.
5. **Breadth** — getting 2 / 3 / 4 / 5 different families to tier 2 unlocks the
   Combined Arms Doctrine certificates, which open the infrastructure branch
   (research/power/factory upgrades, alloys, auto-repair, extra labs).

### New in v3

- **Crates are visible and vanish when taken.** Vanilla ships the artifact
  feature with `startVisible: 0`, so a dropped crate could go unnoticed — it is
  now visible where it lands. The engine also does *not* remove a generic
  artifact on pickup in skirmish (verified in-game: the crate sat there after
  being collected), so the script removes it itself. Take a crate and it is
  gone from the map — including an enemy's crate, which denies it outright and
  gives the research to **you**.
- **Scenery intel.** Destroying neutral houses, ruins and wrecks has a **1.5%**
  chance to reveal a crate. It has no victim to inherit a family from, so it
  picks a family you can still learn in — always at your current tier.
- **Oil barrels from wrecks.** Destroyed enemy units and buildings leave an oil
  drum **5%** of the time. The engine grants the power on pickup. These bonus
  drums deliberately bypass the map's drum-respawn timer, so they cannot
  inflate the map economy over a long game.
- **Research is slower and dearer.** Labs run at **40% of vanilla speed**
  (facility 14 → 6 points, module 12 → 5), and every topic you research
  normally costs **+50% power**. **Captured research is exempt** — the 222
  crate-unlocked topics keep their original cost, so salvaging hardware is a
  genuine discount over grinding it out in a lab.

### The early game is punchy now

Playtesting found openings barely registered, and the cause was arithmetic rather
than feel: the free starting machinegun (`MG1Mk1`) dealt **10 damage** while the
starting body (Viper) has **10 kinetic armour**. Armour is subtracted per hit, so
raw damage was **exactly zero** — the weapon could only ever land its 28%
minimum-damage floor, and a Viper needed **22.2 s** to kill another Viper. Since
both sides open with Viper + MG, that one interaction defined every early game.

It was the *only* floor-bound weapon in the game (Flamer raw 18, Rocket-Pod 12,
Cannon 25 all penetrate), so the fix is narrow rather than global inflation. The
MG line is re-spaced, damage only — cycle times, ranges and accuracy untouched:

| weapon | damage | DPS | TTK vs a Viper |
|---|---:|---:|---|
| Machinegun (light) | 10 → **15** | 2.9 → 5.2 | 22.2 s → **12.4 s** |
| Twin Machinegun | 16 → **20** | 5.2 → 8.7 | 12.4 s → 7.5 s |
| Heavy Machinegun | 26 → **28** | 11.9 → 13.6 | 5.4 s → 4.8 s |
| Assault Gun | 19 → **22** | 11.8 → 16.0 | 5.5 s → 4.1 s |
| Twin Assault Gun | 28 → **30** | 23.5 → 26.9 | 2.8 s → 2.4 s |

The `-Pillbox` emplacement versions move with their turrets. The free starting
weapon still sits clearly below the researched Mini-Rocket Pod (8.3 s), so the
first research step keeps its value.

**The late game is undisturbed.** Machineguns are ANTI PERSONNEL, held at 35 vs
Tracked by the counter matrix, so a fully-upgraded Heavy MG against a Python
moves only 61.8 s → 49.5 s — still deliberately hopeless against armour. The lift
lands on early duels and anti-infantry work and is suppressed everywhere else.

### Standard-issue machinegun

Vanilla's `setupComponents()` is an empty stub — nothing is buildable at match
start, and you must research `R-Wpn-MG1Mk1` before you own any weapon at all.
Now, the moment a player has a research facility, the basic machinegun is
standard-issue. It applies to every player including the AI, and covers both a
lab finished during play and one pre-placed by "start with bases" (which fires no
build event, so it is granted at kickoff too).

Note this only bites in **no-bases** games: with bases enabled, `R-Wpn-MG1Mk1` is
already researched at t=0 for everyone, verified in-game.

### Post-playtest trim (machineguns overshot)

The first punchy-early pass went too far: machineguns were shredding scavenger
units and even their buildings. Three compounding causes, all corrected:

- **MG damage pulled back** ~10%: light 16 → **15**, twin 22 → **20**, heavy
  32 → **28**, assault 24 → **22**, twin assault 34 → **30** (with matching
  `-Pillbox` versions). The opening Viper duel goes 10.4 s → **12.4 s**, still
  well ahead of vanilla's 17.9 s.
- **Scavenger durability restored in two steps.** The earlier pass cut armour
  harder than HP (bus 4 → 2, van 6 → 2), and because armour is *subtracted* per
  hit that let MG land ~87% of its damage on them. Armour first went back to
  bus **3** / van **4**; a second playtest showed the big shells still melting,
  so the **larger** vehicles now keep 85–90% of their hitpoints and the bus gets
  its vanilla armour **4** back:

  | scav body | vanilla HP | now | heavy MG TTK |
  |---|---:|---:|---:|
  | School Bus | 200 | **170** (armour 4) | 6.3 s → **9.5 s** |
  | Fire Engine | 200 | **170** (armour 4) | **9.5 s** |
  | Ice Van | 160 | **136** | **7.6 s** |
  | Camper | 130 | **110** | **6.1 s** |
  | Armoured Truck | 190 | **171** | **11.5 s** |
  | Tractor | 150 | **135** | **7.5 s** |

  The small technicals — jeep, buggy, trike — deliberately stay at −30% HP and
  low armour, so they remain proper glass cannons (buggy still 3.6 s).

- **Scavenger heavy weapons unshackled.** An audit of every scav weapon found
  their *heavy* guns had punishing vanilla cycles, and the stop-to-fire rule
  compounded it — they were barely shooting at all:

  | weapon | vanilla | now |
  |---|---:|---:|
  | `BabaFlame` (flamer) | 2.1 dps — **12 s** between bursts | **13.6 dps** (2.5 s) |
  | `BaBaCannon` / `BusCannon` | 9.3 dps (3.0 s) | **19.2 dps** (2.4 s) |
  | `BabaRocket` (6-rocket salvo) | 12.0 dps (10 s reload) | **29.1 dps** (7 s) |
  | `BabaPitRocketAT` (rocket pit) | 8.3 dps (12 s) | **12.5 dps** (8 s) |

  Accuracy also lifted across the scav arsenal (`longHit` 30 → 36–45), which was
  the single biggest reason they felt harmless — they were missing 70% of shots.
  A trap worth recording: `BabaPitRocketAT` fires a 2-rocket salvo, so
  `reloadTime` is its cycle and `firePause` is the *gap between the two rockets*.
  Changing `firePause` there would have spread its salvo 8 s apart.

- **Scavengers hit back harder.** Infantry are 29 HP fodder, so damage is where
  they earn their keep: `BaBaMG` 14 → **17** (42.5 dps). Helicopters lifted too —
  `MG1-VTOL-SCAVS` 22 → **26**, `Rocket-VTOL-Pod-SCAVS` 60 → **68** (136 dps).
  *Worth knowing:* for VTOL weapons `numRounds` is a **magazine** (100 rockets
  per rearm), not a salvo, so the real cadence is `firePause` and a damage change
  moves DPS one-for-one — these are potent.
- **Anti-personnel no longer demolishes buildings.** Vanilla gives it **160%**
  against SOFT structures, which with a buffed MG chewed through a scav power
  generator in ~12 s. Now **110%** vs SOFT and **45%** vs MEDIUM: power generator
  11.8 s → **20.1 s**, factory 34.3 s → **49.2 s**. Buildings are a job for
  cannons, artillery and bunker busters.

### Scavenger relics are now a flat rate

Drops from scavengers were far too common, and the documented "5%" was wrong.
The scav path took `max(killWeight, SCAV_FLOOR)`, and early on the cost-weight
*beats* the floor — a 35-cost scav against a p75 of 55 scores 0.39, i.e. **7.9%**.
Scav kills now use a **flat** weight, giving **3.6%** (5.8% with a veteran killer)
at every stage of the game, so clearing scavs early is no longer the best source
of intel.

### Playtest results — where scavengers now sit

Measured with a scripted combat harness (units spawned, 25 s engagement, survivors
and average health recorded):

| engagement | outcome |
|---|---|
| 3 Viper-MG vs **6 infantry** | player wins, down to **73%** health |
| 3 Viper-MG vs **5 buggy-MG** | **scavengers win** — player wiped, 3 buggies left at 89% |
| 3 Viper-MG vs **3 bus-cannon** | close — player 2/3 at 71%, one bus survives |
| 3 Viper-MG vs **4 van-flamer** | player wins but **loses a unit** (flamers used to deal zero) |

The crossover sits around **1.5–2 scavengers per player unit**, which is the
intended shape: a scav wave is genuinely dangerous, a handful is not.

*A caution on reading these numbers:* scav units are nearly free — a buggy costs
**6** power and infantry **2**, against **90** for a player Viper MG. Equal-count
tests are therefore meaningless (the player should win 3v3), and at 5:1 the
scavengers win no matter what the stats say, simply because 15 units focus-firing
3 always wins. Only the middle band tells you anything.

### The AI can fortify now

The AI was being overrun by scavengers because **it could not build defences at
all**. 57 of the 72 defence-unlocking research topics are crate-gated, and
Nexus's own `STANDARD_BASIC_DEFENSES` list opens with `PillBox1` and
`GuardTower6` — `PillBox1` needs `R-Wpn-MG-Damage01`, `GuardTower6` needs the
mini-pod line. Its entire early repertoire sat behind crates it had not earned,
so with nothing to build it simply absorbed the hits.

A command centre now entitles an **AI player** to the basic MG emplacements:

- **`PillBox1`** — "Heavy Machinegun Bunker" (700 HP), and the first thing Nexus
  reaches for in its defence list. This is the "HMG tower" in practice;
  `GuardTower3` exists in the data but no research grants it in any file, vanilla
  included, so it is not usable.
- **`GuardTower1`** — "Heavy Machinegun Guard Tower" (450 HP), for picketing
  oil derricks.

**AI only, deliberately.** Both are *Heavy* MG structures, so handing them to the
human free would undercut the earned-research premise — you still unlock defences
through crates like everything else. The AI gets the crutch because it cannot
cope without one. Verified with bases off: human `false`, all three AI `true`.

> **Where the "free HMG bunker" actually comes from.** If you see the Heavy
> Machinegun Bunker and Guard Tower buildable without research, that is the
> **"start with bases"** lobby setting, not this mod. Tested directly: with the
> mod's grants disabled entirely and bases ON, both are still available to every
> player; with bases OFF they are available to nobody. Starting with a base hands
> out a starting tech package — the same reason `R-Wpn-MG1Mk1` is already
> researched at t=0 in base games. Play with bases off if you want the full
> crate-earned progression.

**What I could not verify:** whether Nexus then actually *builds* them and
fortifies. My headless harness has stopped attaching the Nexus AI (it loads no AI
script at all), so its behaviour is unobservable here. That `PillBox1` is
literally the first entry in its own defence list is a strong indication, but it
is an inference from reading its source, not a measurement.

### Research facilities: earn your labs

You now start with **two** research facilities. Every completed research upgrade
(`Synaptic Link Data Analysis`, `Dedicated Synaptic Link`, and so on) earns you
another, up to a hard cap of **5**. Verified in-game: the cap starts at 2, rises
one per upgrade, and stops at 5. AI players are governed by the same rule.

*Implementation note:* the cap is set from `doctrine.js` via `setStructureLimits()`
rather than through research data. The only topic in any research file that used
`Building.Limit` was `R-Struc-Limit-Labs`, and neither the docs nor the data
established what base its `value: 40` applied to (the facility has no `limit`
field) nor whether `applyLimitSet()` would override it. Its `Limit` result has
been removed; the topic still earns a lab because the script counts it. Tune
`LAB_LIMIT_START` / `LAB_LIMIT_MAX` at the top of `doctrine.js`.

### Captured research is quicker to integrate

The crate-unlocked upgrades now research **20% faster** (tiers 720 / 1920 / 4160 /
8000 points, down from 900 / 2400 / 5200 / 10000). They were already the scarce,
earned half of the loop — you had to win the fight and physically recover the
crate — so the lab step should not also be the slow half, especially with labs
running at 40% speed.

### Machinegun balance: verified, no change needed

Checked against every other family on *full unit cost* (body + propulsion +
weapon), not weapon cost alone — the weapon is a small slice of a unit, so
per-weapon figures badly flatter cheap guns.

| tier | weapon | unit | vs cyborg | vs wheeled | vs tracked |
|---|---|---:|---:|---:|---:|
| early | Twin MG | 105 | 11.2 | 10.4 | 2.0 |
| mid | Heavy MG | 221 | 23.4 | 16.4 | 3.3 |
| late | Twin Assault Gun | 335 | 45.7 | 31.3 | 6.7 |

MG is the **strongest** family against cyborgs — its speciality — and the
**weakest of all** against armour (a Rocket-Pod does 6.3 vs tracked where the
light MG does 1.7). The counter-play holds too: MG effectiveness roughly halves
against half-tracks and collapses against tracks, so an MG rush is answered by
switching propulsion. That is the intended shape, and it is what makes the
punchy opening safe to keep.

### Two outliers trimmed

The comparison did expose two weapons dominating their cost bracket:

- **Flashlight laser** (`Laser3BEAMMk1`) is classed ANTI PERSONNEL and was beating
  MG in MG's own speciality — 64.4 dps vs cyborgs at unit cost 321, against the
  *late-game* Twin Assault Gun's 45.7 at 335. It was also inverted inside its own
  ladder, out-damaging the dearer Pulse Laser meant to succeed it. Damage
  **100 → 75**: now 46.9, just above the top MG (as later tech should be) and back
  below Pulse Laser's 54.9.
- **Scourge** (`Missile-A-T`) was the audit's outstanding residual — 4.4× Tank
  Killer per power, one-salvoing a fully-upgraded Python. Damage **360 → 200**,
  bringing it to **2.4×** Tank Killer: still clearly the best anti-tank weapon,
  no longer trivialising armour. (Damage was the only safe lever — with
  `numRounds` above 1 the engine uses `reloadTime` as the cycle, so cutting the
  salvo to one round would have switched it to `firePause` and made it *faster*.)

### Balance audit: weapons now keep pace with armour

A numeric audit found weapons falling off a cliff late game. DOCTRINE had replaced
vanilla's 9-step damage ladders with a 4-tier ratchet totalling **+144%**, but left
defence research untouched at vanilla's **+270% armour / +270% HP**. Armour is
*subtracted per hit*, so falling behind is not linear — damage collapses onto the
minimum-damage floor. Measured fully upgraded against a Python:

| weapon | vanilla | before fix | now |
|---|---:|---:|---:|
| Light Cannon | 38.7 s | 113.4 s | **62.0 s** |
| Light Cannon *vs its best target* | — | 43.1 s | **22.4 s** |
| Heavy Cannon | — | 22.1 s | **15.4 s** |
| Lancer (AT) | 16.9 s | 16.0 s | **12.8 s** |
| Pulse Laser | 23.7 s | 12.6 s | **11.4 s** |

Fixes applied:

- **Damage scaling restored to vanilla parity.** The four tiers are now
  `[34, 46, 61, 82]` = **+223%** total (was `[25,31,39,49]` = +144%), derived by
  solving the generator's own constant-relative-gain formula for vanilla's +225%.
  Reload (−46%) was already at parity; Accuracy (+46%) and Range (+31%, a
  DOCTRINE-only axis) are unchanged.
- **Three upgrade bugs fixed.** Vanilla's `R-Wpn-Energy-Damage01-03` had survived
  the merge and stacked on DOCTRINE's Laser ladder, silently giving lasers
  **+219% damage against everyone else's +144%**; `R-Wpn-Mortar-Acc01-03` likewise
  gave mortars **+76% accuracy vs +46%**. Both deleted. VTOL bombs, which are not
  one of the 11 families and so received *no* ladder at all, were raised from +75%
  to **+180%**. Every family now reads a uniform +223% damage / +46% accuracy.
- **Anti-tank reined in, generalists lifted.** The `minimumDamage` floor — which
  *is* the late-game damage number once armour exceeds raw damage — was restored
  for ALL ROUNDER (25→**33**) and ANTI PERSONNEL (20→**28**), and pulled back for
  ANTI TANK (45→**38**). ANTI TANK vs Tracked went 175→**150**, Half-Tracked
  150→**135**, Wheeled 145→**130**. Counters still point the right way: ANTI TANK
  is best vs Tracked, ANTI PERSONNEL vs Legged, and ALL ROUNDER is best nowhere.

Deleting the mortar accuracy topics orphaned the whole counter-battery / sensor /
heavy-artillery branch (it hung off `R-Sys-CBSensor-Turret01`); that prerequisite
now points at the basic mortar unlock instead — same intent, no new gating.

**Known residual:** unifying every family at +223% over-rewards the weapons vanilla
deliberately gave *short* ladders because their base damage was already huge.
Scourge (`Missile-A-T`) now kills a fully-upgraded Python in **1.3 s** versus
vanilla's 3.8 s — it one-salvos, as it does in vanilla, but harder. Rockets sit at
a healthy ~1.3× vanilla. Fixing this properly means per-family ladders, which
breaks DOCTRINE's "every family has the same four tiers" premise — a design call
rather than a bug, so it is left for you to decide.

### Veterancy matters more

Ranks now arrive on **0 / 2 / 4 / 7 / 11 / 16 / 22 / 30 / 40** kills — Hero at 40,
down from 64 (and from vanilla's unreachable 512).

Worth knowing *why* it was done that way: the per-rank bonuses themselves —
**+5% accuracy, −6% damage taken and +5% speed per level** — are
`#define` compile-time constants in `src/droid.h` (`EXP_ACCURACY_BONUS`,
`EXP_REDUCE_DAMAGE`, `EXP_SPEED_BONUS`). **A data mod cannot change them**;
only a recompiled engine could. So the one available lever for making veterancy
count for more is reaching the ranks sooner, which is what this curve does — a
unit now holds a higher level (and therefore more accumulated bonus) at any
given point in its career. At Hero that is +40% accuracy, −48% damage taken and
+40% speed. It also feeds the drop model above: veteran enemies are now the
targets worth hunting.

### Weapons: the MG ladder and elevated defences

- **The Heavy MG now actually hits like one.** In vanilla it was barely an
  upgrade: the light MG does 10 damage on a 5-tick cycle (**20 dps**) while the
  heavy did 17 on a slower 7-tick cycle — just **24.3 dps** for a far later and
  dearer weapon, and barely ahead of the Twin MG's 23.3. The extra per-shot
  punch was being eaten by the slower rate of fire. Retuned by damage only
  (cycle times and ranges untouched):

  | weapon | before | after |
  |---|---:|---:|
  | Machinegun (light) | 10 dmg / 20.0 dps | *unchanged* |
  | Twin Machinegun | 14 dmg / 23.3 dps | **16 dmg / 26.7 dps** |
  | **Heavy Machinegun** | 17 dmg / 24.3 dps | **26 dmg / 37.1 dps** |
  | Assault Gun | 19 dmg / 47.5 dps | *unchanged* |

  The matching `-Pillbox` emplacement versions move with their turrets so the
  defensive line does not fall behind. Side effect worth knowing: the scavenger
  bunker also mounts the heavy MG, so it gets the same buff.

- **Elevated defences out-range ground-level ones.** Towers and wall
  towers/hardpoints (height 2) now reach **+15%** further than pillboxes,
  bunkers and emplacements (height 1) — e.g. a Light Cannon reaches 960 on a
  PillBox but **1104** on a Wall Tower. 57 elevated structures were re-pointed;
  the 50 ground-level ones are untouched.

  *How, and why it is safe:* range lives on the **weapon**, not the structure,
  and 31 of the 58 weapons mounted on defences are shared across both heights
  (`Cannon1Mk1` sits on the height-1 PillBox4 *and* the height-2 WallTower02),
  so the range could not simply be edited. Each elevated structure instead gets
  its own `-Elev` weapon variant — the same pattern the game already uses for
  its `-Pillbox` and `-VTOL` versions. Verified in the engine source that
  structures resolve weapons **by ID**, and that **no** vanilla research
  upgrades a weapon by Id (every weapon upgrade filters on ImpactClass), so the
  variants inherit all research automatically, DOCTRINE's ratchet included.
  Confirmed in-game: 0 unresolved weapons, 0 load errors.

  Scavenger gun/flame towers are height 2 and get the bonus too — consistent
  with the rule, but flip `ELEVATED_RANGE_MULT` in `build_mod.py` if you would
  rather they did not.

### The AI plays by the same rules

Every player has their own progress, drop rolls, pity pool and tier gates.
Two engine facts had to be worked around, both verified in the 4.7.0 source:

- `move.cpp checkLocalFeatures()` **ignores non-human players entirely** unless
  the droid is carrying a `DORDER_RECOVER` order — so AI-owned crates get a
  recover order issued to their nearest eligible unit, re-issued every 20s
  (their scripts retask constantly), plus a decay safety net that grants the
  crate if it expires uncollected, so AI progress can never stall on pathing.
  **You can still steal an AI's crate** by reaching it first — that is the real
  denial play, and it must be done before the crate decays.
- The shipped AI scripts research from hardcoded topic lists, so merely
  *enabling* a topic for them would do nothing forever. AI pickups therefore
  complete the topic outright — wrapped in `hackNetOff()`, without which it
  silently fails — and the AI is **charged the power cost**, so it pays too.
  AIs skip the research *time*, which offsets them never seeking crates out.

Weapon *unlocks* (new guns, defenses, superweapons) hang off the axis topics with
normal prerequisites and appear automatically as you research salvaged intel.

## AI behaviour and scavenger scaling — measured

Everything below came out of headless 4-AI runs on Sk-Rush against ultimate
scavengers (Nexus on Hard, no human). Headless runs about 50x realtime, so a
20-minute game takes ~20 seconds of wall clock. To reproduce:

```bash
warzone2100.exe --headless --nosound --autogame --skirmish=ai-vs-scav
```

The config lives at `tests/ai-vs-scav.json` in the Warzone config directory.
Building with `py -X utf8 build_mod.py 4.7.0 --telemetry` turns on a per-sweep
census (attack units, trucks, factories, defences, oil, live scavengers) printed
to stdout. Telemetry is OFF in every normal build.

### The AI was not over-building defences by choice — it was starved

First measurement, with the AI granted a starter emplacement:

| game time | AI defences | AI attack units | scavengers |
|---|---|---|---|
| 180 s | 4 | 0 | 9 |
| 420 s | 5 | 0-2 | 138 |
| 580 s | 5 | 0 | 223 |

It built four defences before its first tank and died with the concrete still
standing. The same map with the scavenger mod removed: the AI reached 9-13
tanks, held 4-6 derricks each, and all three were alive at 19 minutes.

So the AI is fine. Two real problems sat underneath.

### 1. Scavenger production had no ceiling

`uuscav2` allowed 16 scavenger factories and 8 VTOL factories, each building
whenever idle on a 1-second timer. That compounds to 240 units by 8 minutes.
Capping units alone just displaced it — the freed trucks poured into the build
loop's fallback branch and put up 270 mortar pits and cannon towers instead. So
both are capped now:

| | stock | now |
|---|---|---|
| scavenger factories | 16 | 4 |
| VTOL factories | 8 | 3 |
| emplacements | unlimited | 24 |
| fielded combat units | unlimited | 12 + 3/min, max 60 |
| measured units @ 8 min | 240 | ~65 |
| measured structures @ 12 min | 270 | ~85 |

The ramp is deliberately shallow at the start and flat late: the opening rush is
undiminished, the exponential is gone.

### 2. The AI gets no defences at all now

Granting the AI a starter emplacement measured strictly *worse* than granting it
nothing, on identical scavenger settings:

| | tower granted | no defences |
|---|---|---|
| AI army at 380 s | 0-1 | **9 and 6** |
| AIs with a real army | 0 of 3 | **2 of 3** |

Given the same power, the AI defends better with tanks than with towers. It now
earns defences through crates exactly like you do. Two leashes remain for when
it does unlock them:

* `GuardTower1` and `PillBox1` are capped at 4 + one per derrick, ceiling 10 —
  so no more clusters, and it stops.
* Nexus's own `STANDARD_BASIC_DEFENSES` list ships with one literal changed,
  `PillBox1` -> `GuardTower1`, so its opening emplacement is the Heavy
  Machinegun Guard Tower rather than the bunker. The file is otherwise a
  byte-identical copy of your game version's own, taken from that version's
  `mp.wz` so it cannot drift.

### Also fixed: the starter weapon was gated behind a research lab

`MG1Mk1` used to require a research facility. An AI that built factories before
a lab therefore had no weapon to mount and turned out nothing but trucks — two
factories standing at 180 s with zero combat units. It is now granted to
everyone at kickoff, which is what vanilla does. The earned-research premise
lives in the crate ladder above it, not in withholding the opening weapon.

### Still open

Scavengers still eventually grind the AIs down in these runs. That is four AIs
at Hard fighting each other *and* the scavengers with no human present, so it is
not necessarily wrong — but if you want them less lethal, the levers are
`SCAV_MAX_FACTORIES` and `scavUnitCeiling()` at the top of
`uuscav2/multiplay/script/scavengers/ultimateScavengers.js`.

## AI difficulty — it was inert, now it works

**The finding that mattered:** AI difficulty was doing essentially nothing. DOCTRINE
could not even read it — in the rules-script context `playerData[p].difficulty`
returns a flat `2` (MEDIUM) for every AI player no matter what the lobby or
challenge file says. Verified by dumping all ten slots across Easy, Hard and
Insane configs; every one reported `2`. Nexus's own script, meanwhile, only
varies its research targeting by difficulty. So the setting was close to
cosmetic.

The gradient now lives inside the AI's own script instance, where the
`difficulty` global IS that AI's real setting. It is appended to the Nexus file
DOCTRINE already overrides (`buildDefinitions.js`), so each AI configures itself.
Two levers:

| difficulty | power | free intel |
|---|---|---|
| Easy | 80% | — |
| Medium | 120% | — |
| Hard | 180% | one topic / 150 s |
| Insane | 250% | one topic / 75 s |

Medium deliberately sits *above* parity. An AI plays its economy far less
efficiently than a human does, so giving it a player's income still leaves it
behind — parity of power is not parity of outcome.

*Power* scales how fast the AI replaces losses. It plateaus, though: Nexus runs
only two factories, so past roughly 200% it banks power it cannot spend — 340%
produced no larger a force than 160%. That is why the top two difficulties also
get *intel*: a free topic pulled off their own `enumResearch()` list, which only
ever contains topics already unlocked for that player. It cannot skip the crate
ladder, only climb it faster, and it still flows through DOCTRINE's normal
`eventResearched` bookkeeping.

### What is verified, and what is not

Verified: the difficulty each AI sees, the power modifier being applied, the
intel grants firing, and zero script errors.

**Not** verified: that this produces the intended Easy/Medium-lose,
Hard-struggles, Insane-wins spread. Two things defeated measurement.

* With every AI allied on one team the skirmish ends on its own win condition —
  scavengers are not a team — so "how long the AI survived" is really "when the
  game stopped". That metric is invalid and should be ignored.
* Run-to-run variance swamps the effect at two samples per setting. Easy alone
  ranged 680-800 s and peaked at 13 units in one run and 9 in another. Army size
  across difficulties came out 13 / 7 / 11 / 12 — not an ordering, just noise.

So treat the table above as a starting point calibrated by mechanism, not by
outcome. If Insane still loses to scavengers in real play, raise its intel rate
first (it converts to unit quality) and only then its power, since power alone
hits the two-factory ceiling. Both live at the top of `DIFFICULTY_GRADIENT_JS`
in `build_mod.py`.

### Measuring it yourself

The harness ignores per-player difficulty, so builds take a pin for testing:

```bash
py -X utf8 build_mod.py 4.7.0 --telemetry --force-diff=4
```

`--force-diff` is 0 in every normal build, and `--telemetry` also turns on the
`DOCTRINE-DIFF` / `DOCTRINE-INTEL` debug lines. A fair comparison needs several
runs per setting and should compare army size and derricks held at a fixed time,
never survival time.

## Crate economy — three defects found from a real game log

Investigating "the AI builds walls too early" and "it never techs up" turned up
three separate bugs, all now fixed.

**1. Free intel was handing out the whole tech tree.** The Hard/Insane intel
bonus picked a random topic from `enumResearch()`, which returns *every*
available topic — not DOCTRINE's ladder. It was granting `R-Defense-Tower01`,
`R-Struc-Factory-Cyborg` and the hardcrete-wall branch, which is exactly why the
AI had walls long before it should have had the technology. It is now filtered to
`R-Wpn-<family>-<Damage|Range|Reload|Accuracy>0<tier>` — the weapon ladder only.

**2. Scavenger kills were burning the drop budget.** The crate goes to the
killer, and in a scav-heavy game the scavengers get most of the kills. Measured:
of 8 crates in one game, **5 were scavenger-owned**. Those are dead weight twice
over — scavengers never execute `DORDER_RECOVER` because their own script
retasks every unit each second, and `SCAV_RESEARCH_PARITY` already hands them
every topic anyone else completes. A scavenger kill now produces no crate at all,
so drops only occur where they can actually be used.

**3. Crates were keyed on an unstable id.** `spawnCrate` keyed its record on the
id returned by `addFeature`, but the expiry sweep matches ids from
`enumFeature`. When those disagreed the record was silently deleted after five
seconds and the crate became permanently uncollectable — sitting on the map,
never expiring, never counted. It is now re-resolved through `enumFeature` by
position before being tracked.

There was also a **telemetry** defect worth recording because it cost a whole
debugging pass: `stats.recovered` only incremented for human pickups, so the AI
looked like it never collected anything when it was collecting fine. It now
counts every recovery.

### Verified working end to end

After the fixes, one measured game: 3 crates dropped, 3 recovered, and the
research landed on the right players — p2 gained two weapon upgrades, p3 one.
Before the fixes it was 8 dropped, 0 usable, and **zero** weapon upgrades
completed by anyone all game (`res=3(0doc)`, flat from the first tick to the
last).

### Still a tuning question, not a bug

Three crates a game is a thin diet — that is roughly three weapon upgrades over
twenty minutes. That number falls straight out of the scavenger drop rate, which
is deliberately low (`SCAV_FLOOR` in `doctrine.js`, ~3.6% per scavenger kill)
because it was tuned down on purpose. Now that scavenger-owned drops no longer
exist, the same rate yields noticeably fewer usable crates than it used to, so it
may be worth raising. It is left as set rather than changed unilaterally.

## Scavenger mortar accuracy

`A0BaBaMortarPit` fired `Mortar1Mk1` — the *same* weapon as the player's own
mortar emplacement — so its accuracy could not be lowered without nerfing the
player's mortar too. The scavengers now get their own copy, `BabaMortarPit`,
identical apart from accuracy and flagged `designable: 0` so it never shows up in
the design screen:

| | longHit | shortHit |
|---|---|---|
| player `Mortar1Mk1` | 50 | 40 (unchanged) |
| scavenger `BabaMortarPit` | **22** | **18** |

## Why the AI had untech'd walls, and why it never attacked

Both symptoms had concrete causes in vanilla code DOCTRINE had never overridden.

### "Start with Bases" was handing out every early defence for free

`rules/setup/base.js` calls `completeResearchOnTime(timeBaseTech, player)` where
`timeBaseTech = 3*60`. That function walks a **hardcoded table** in
`camTechEnabler.js` and calls `completeResearch()` directly — it never consults
availability, so DOCTRINE's gating was bypassed completely. Everything with a
time at or under 180 was granted to every player, AI included:

| at | topic | grants |
|---|---|---|
| 48 s | `R-Defense-Tower01` | Guard Tower |
| 108 s | `R-Defense-TankTrap01` | tank traps |
| 129 s | `R-Defense-HardcreteWall` | **walls** |
| 177 s | `R-Defense-Pillbox01` / `05`, `HardcreteGate` | **bunkers, gates** |

Every `R-Defense-*` entry (83 of them) is now stripped from that table. The base
package still grants the economy, propulsion and weapon tech that makes a
starting base playable — no defensive structure comes free to anyone any more.

**Caveat:** the headless harness ignores the `bases` setting entirely
(`baseType` reports 0 no matter what the config says), so this fix cannot be
verified here. It is verified only as a data change: 83 entries removed, 0
`R-Defense-*` remaining in the shipped file. It needs a real game with bases on.

### The AI was production-capped at two factories

`nexus_includes/build.js`, `buildMaxsBasedOnDerricks()`, allows only **two**
factories until a player holds more than 8 oil derricks. Across every measured
run the AI held 3-6 derricks — so it sat on two factories all game while banking
2000-3000 power it had no way to spend. That, not power and not personality, was
the ceiling on how fast it could field an army.

The allowance is now 4/5/5/5 instead of 2/3/4/5. Measured immediately after:
the AI reached **4 factories and 8 attackers**, against 2 factories and 0-3
attackers before.

### A red herring worth recording

Nexus has a `vtol1` personality with `attackers: 0` that looks like it would
explain a turtling AI, and the game log does print "going air." about a quarter
of the time. It is **not** the cause: `vtol1` declares `"type": "air"` while
`chooseVtolPersonality()` searches for type `"vtol"`, which matches nothing, so
it always falls through to the land personality. The branch is unreachable in
vanilla. Do not "fix" it.

## Round 3: aggression, research economy, mortar splash

**Scav mortar "still 100% precise".** The shipped accuracy really was 22/18 —
the deception was splash: radius 160 with 40 splash damage means a missed shell
still lands real damage next to the target, which reads as a hit. The scav-only
mortar is now 12/10 accuracy AND 20 splash (the player's mortar keeps 50/40/40).

**Heavy MG projectile speed.** All MGs were at flightSpeed 3000 (2x vanilla).
The whole MG line is now a flat 3600 — effectively hitscan at combat ranges.

**Research costs +60%.** `RESEARCH_POWER_MULT` 1.5 -> 2.4 for everything except
crate topics. The AI would simply stop researching at those prices (its
budgeting predates them), so AIs get 37.5% back on completion — an effective
1.5x for the AI, full 2.4x for you.

**"Attacks once then gives up" — found and fixed.** Nexus's `doAllOutAttack()`
refuses to attack with fewer than 10 units in its attacker group. Its army under
DOCTRINE peaks around 8-16 and is constantly whittled by scavengers, so it
crossed 10 once, attacked, took losses, and never attacked again. The threshold
is now 5.

**"Not building as much as it can" — a vanilla production bug.** In all three
Nexus production loops (ground/cyborg/VTOL) the per-factory guard
`if (busy || low power) return;` sits INSIDE the factory loop and aborts the
whole pass at the first busy factory — factories 2..N only ever produced when
factory 1 happened to be idle. The busy check is now `continue`; the power
check stays a global `return`.

**Guard towers are back, delayed.** The tower grant returned (you wanted the AI
to have them) but now arrives at the 4-minute mark: granted at t=0 the AI
measurably pours its opening into towers instead of factories and units
(def=6-7, atk=0-2, dead by ~500s). Delayed, the opening goes to the army and
towers arrive as the second layer. The 4+derricks cap still applies.

**Insane "building base defenses" is engine behaviour, not tech leakage.** With
"Start with Bases", vanilla `shouldRemoveBaseStructure()` deliberately lets an
INSANE AI keep the pre-placed base's walls and defences (everyone else has them
removed). It did not build those; it inherited them. Left alone — it is part of
what makes Insane insane.

## Towers in the wrong base — Nexus never defended its own

Report: the AI builds turrets, but in *other* bases, not its own. Reading every
defence path in Nexus explains it exactly: **vanilla Nexus has no code path
that builds basic defences inside its own base.** Its three defence builders
are forward emplacements at remote derricks (`protectCloseDerrick`, whose own
comment reads "start being nasty"), sensor towers at derricks, and mortar pits
near sensors. The own-base carpet seen in early games came from the free wall
tech, which is now stripped — leaving only the forward towers.

Fix: a new `baseTowerDefense()` step, tried FIRST in `buildDefenses()`: up to 4
Guard Towers around the AI's own base position, before any sensor or derrick
work. Combined with the 4-minute grant delay the measured sequence is now
army first (3-6 attackers by ~260s), base towers second (def 1-4 from 260s on),
both coexisting — and the forward towers at contested oil still happen, which
matches "main base first, oil fields second".

## Nexus was refusing FREE research

"It feels like the AI might not be researching" — it wasn't. Measured: 3 topics
available at t=20s, the same 3 still available and **none completed** at t=900s.
Research count frozen at 4 for a twenty-minute game.

The cause is a two-part trap:

* `doResearch()` skips a lab whenever `getRealPower(me) < LOW_POWER` (140).
* Raising the factory allowance made the AI spend power down to 20-100
  continuously, so that gate is now almost always closed.
* And the early topics it would pick — `R-Sys-Engineering01`,
  `R-Sys-Sensor-Turret01`, `R-Wpn-MG1Mk1` — carry **no power cost at all**. It
  was refusing to start free research because it was short of power it did not
  need to spend.

Research now has its own floor of 30. Topics that do cost power are still paid
for normally by the engine. Measured immediately after, same settings:

| | before | after |
|---|---|---|
| topics completed by 740s | 4 (frozen from ~100s) | **12 and climbing** |
| peak army | 0-4 | **11** |

### Income

| difficulty | power |
|---|---|
| Easy | 100% |
| Medium | 150% |
| Hard | 200% |
| Insane | 300% |

### Caveat on the "3 available topics" number

That figure comes from the headless harness, which forces **no bases**, so the
AI only receives the 1-second `cleanTech` package. In a real game with bases on
the start package opens 61 reachable topics. The frozen-research bug was real
either way — it just looks more dramatic in the harness.

## Making Insane actually insane

Two changes, because raising one alone does nothing:

* **Factory allowance.** `buildMaxsBasedOnDerricks()` hands ONE shared number to
  labs, factories, repair bays, cyborg and VTOL factories -- so raising it
  wholesale would also give Insane nine repair bays. Factories now get their own
  `doctrineFactoryAllowance()`: **Insane 10, Hard 6**, ignoring the derrick curve
  entirely so a high-difficulty AI reaches its ceiling in the opening minutes
  rather than waiting on oil it may never hold. Labs, repair bays and VTOL pads
  keep the shared derrick amount.
* **Structure limit.** Vanilla caps every player at 5 tank factories
  (`rules/setup/structurelimits.js`), so the allowance alone would have done
  nothing past 5. The limit is raised per difficulty from inside the AI's own
  script instance (Hard 6, Insane 10), where `difficulty` is readable.

Measured, Insane against ultimate scavengers:

| | before | after |
|---|---|---|
| factories | 2 | **6** |
| peak army | 8-11 | **15** |
| scavenger count | rising unchecked | pushed *down* (63 -> 57) |

**It does not reach 10 factories** -- it plateaus around 6 because power binds
first: even at 300% income it only holds ~3 derricks on this map. The allowance
is a ceiling, not a mandate. If Insane should go further the next lever is oil,
not factories -- either more aggressive derrick expansion or another income
step.

Note the version difference caught by the build guard: 4.7.0 names the shared
allowance `AMOUNT`, 4.5.5 names it `amount`. The patch matches either.

## Round 4: the research wall, abandoned towers, group attacks

**Why research "stops" — measured, not guessed.** Simulating the shipped tree:
61 of 602 topics are reachable from the base package alone; adding every crate
axis topic reaches 319. The remaining 200 REACHABLE topics — the entire late
infrastructure, cyborg and command branch — hang solely behind the Combined
Arms (Breadth) credentials. Breadth-2 required all FOUR tier-1 axes researched
in TWO families: each axis needs its own crate, so that was 8 specific crates
plus research. At the real crate rate it never happened, and once the base
topics ran out, research went silent. A family now counts once ANY tier-1 axis
in it is researched — fielded experience with N branches, not mastery of them.
Verified: the available list grows again (3 -> 8 within one AI game, Power
Module / Cyborg Factory / Command Relay cascading in). The 83 `R-Sig-*` topics
that stay locked are v1 leftovers, hidden by design.

**Scav artifact drops reduced.** `SCAV_FLOOR` 0.18 -> 0.14: a scavenger kill now
rolls ~2.8% instead of ~3.6%.

**Abandoned defence foundations — a vanilla gap.** `finishStructs()`, the pass
that sends trucks back to unfinished buildings, explicitly SKIPPED DEFENSE and
WALL structures. A truck chased off a half-built tower never returned, and the
build loop then started a fresh one elsewhere. The exclusion is removed;
defences and walls now resume like everything else.

**Group attacks and varied routes.** `doAllOutAttack()` used to order each
attacker at the target individually the moment the count passed the threshold —
a trickle that dies piecemeal. Two stateless additions:

* *Regroup*: if more than a third of the group is over 9 tiles from the group
  centroid, stragglers are pulled to the centroid first and the attack waits
  until the group is actually together.
* *Lanes*: the approach alternates between direct and two flanking waypoints on
  a two-minute cycle, so successive waves take different routes instead of
  funnelling down one lane. (True per-unit path control is not exposed to
  scripts — waypoints are the available lever.)

Code-verified on both game versions (4.5.5 declares `var len` where 4.7.0 has
`const LEN`; the build detects which). Behaviour needs a real game to judge.

**The fast AT tower — my bug, confirmed.** The Scavenger AT-Rocket Pit
(`A0BaBaRocketPitAT`) was firing 2x50 rockets every 8s. An earlier "nerf" set
its reloadTime to 80 believing that was a slowdown — vanilla is 120, so it was
actually a 50% BUFF. Now 140: slightly slower than vanilla.

## Starting base: no more free research facility

The standard "Start with Bases" setting pre-placed a Research Facility for
every player. The lab is the engine of the whole DOCTRINE loop, so handing it
over pre-built skipped the first real decision of the game. The pre-placed lab
is now removed for every player and difficulty in the standard-base setting.
Advanced Bases keeps everything; No Bases never had one. (4.7.0 and 4.5.5
structure this vanilla file completely differently -- the build patches both
shapes.) Cannot be verified in the headless harness, which forces No Bases; the
next real game with bases on is the check.

## The tech tree WAS broken — weapon unlocks sat behind crates

Investigating "the AI never uses mini-rocket array or half-tracks" found the
same root cause as "research stops at some point", and it is the biggest defect
found so far.

The brief was that artifacts unlock **upgrades**. What shipped had it backwards
for 53 prerequisites across 37 topics: DOCTRINE repurposed the vanilla upgrade
topic IDs into crate-only axis topics, but the vanilla *weapon-unlock* topics
still listed those same IDs as their prerequisite. The result:

| to build | first needed |
|---|---|
| Light Cannon (`R-Wpn-Cannon1Mk1`) | an **MG crate** (`R-Wpn-MG-Damage01`) |
| Mini-Rocket Array (`R-Wpn-Rocket02-MRL`) | a **rocket crate** |
| Lancer (`R-Wpn-Rocket01-LtAT`) | **two** rocket crates |
| Super weapons | a **tier-4** crate of that family |

At the measured rate of about three crates a game, that froze every player and
every AI on the starting machinegun for the whole match. It also explains the
half-track question exactly: half-tracks themselves only need Engineering, but
**every half-track template in Nexus's list pairs the propulsion with a
crate-locked weapon**, so no half-track design was ever buildable.

Fix: axis topics are removed from every prerequisite list; where that empties a
list the topic is re-anchored onto its own family's weapon chain at matching
depth (tier 1 -> that family's first weapon, tier 4 -> its fourth), preserving
ordering. Crates now gate the four upgrade axes only, as designed.

| | before | after |
|---|---|---|
| reachable with **no** crates | 61 / 602 | **98 / 602** |
| + Breadth credentials | 519* | 306** |
| axis topics used as a prerequisite | 53 | **0** |
| dependency cycles / dangling | — | 0 / 0 |

*the old 519 was theoretical: it assumed every crate topic already granted.
**the new figure needs no crates at all, so it is the number actually attainable.

Verified in game: by t=300s an AI's available-research list contains
`R-Wpn-Cannon1Mk1` and `R-Wpn-MG3Mk1` — both previously unreachable. One
circular prerequisite (RailGun02 <-> RailGun03) created by re-anchoring is
detected and broken by the build.

## Scavenger escalation ladder

| phase | from | behaviour |
|---|---|---|
| hold | 0:00 | economy only; **no offensive orders at all** |
| — | 2:00 | hold lifted; still economy-only production |
| light | 3:30 | infantry, MG buggies / trikes / jeeps |
| medium | 6:00 | adds cannons and basic rockets, heavier bodies |
| heavy | 10:00 | AT rockets, flamers, 3x-cannon heavy tanks |
| air | 10:00 | VTOL factories and helicopters (was 6:00, or instant at T2) |

Measured: scavenger units stay at 7-12 through the first 200s instead of
ramping immediately. During the hold, factories put out trucks (capped at 10)
so the oil push continues, which is what makes them dangerous later rather than
sooner.

## Round 6: lab-gated weapons, AI research character, scav pickets

**Advanced weapons now require lab upgrades.** The lab ladder had to be fixed
first: `R-Struc-Research-Upgrade01/02/03` were themselves behind Breadth
credentials, which need crates -- gating weapons on them would have re-created
the crate dependency round 5 removed. The ladder is re-anchored into one
researchable spine:

    Research Module -> Upgrade01 -> Upgrade02 -> Upgrade03 -> 04..09

19 expensive component unlocks then gate on it by cost: 3k+ needs the Module,
7k+ Upgrade01, 15k+ Upgrade02, 30k+ Upgrade03.

| weapon | cost | now requires |
|---|---:|---|
| Lancer | 3,600 | Research Module |
| Assault Gun (MG4) | 6,000 | Research Module |
| Flamer Mk2 | 7,200 | Upgrade01 |
| Rail Gun | 14,400 | Upgrade07 (already deeper) |

Side effect worth noting: fixing the lab spine also unblocked everything that
hung off it. Reachable **without a single crate** went 98 -> **222** of 602.

**The AI now has research character.** Two additions ahead of Nexus's stock
lists in `doResearch()`:

* `DOCTRINE_LAB_PRIORITY` is tried first every time -- command relay, research
  module, the upgrade ladder, factory module. It never prioritised lab
  infrastructure before, which is why expensive topics took ~80 minutes.
* Each AI picks a favoured weapon family from its player slot
  (`me % families`) -- cannon, flamer, rocket, MG or mortar -- and researches
  from it 55% of the time. Two Nexus players on one map no longer converge on
  identical armies.

**Scavengers picket their own oil.** Stock uuscav2 only ever emplaced next to
*enemy* derricks (`protectCloseDerrick`); its own wells and outposts stood bare
all game. Trucks now picket owned derricks and factories from the first minute,
up to 2 emplacements within 5 tiles of each site, still under the global cap of
24. The type climbs with the escalation phase:

| phase | picket types |
|---|---|
| hold / light | Gun Tower (75 build points -- nearly free) |
| medium | + Cannon Tower |
| heavy | + Mortar Pit, Bunker, Rocket Pit, AT Rocket Pit, Flame Tower |

**"The AI can't recover oil drums and artifacts" -- partly.** Measured: 4
artifacts dropped and 4 recovered, 6 drums spawned and 0 left on the map, so the
pickups *were* happening. But `aiRecovering` was **0 at every single sample** --
the AI was never actually driving to them; artifacts were arriving via the
decay safety net and drums by proximity. `checkLocalFeatures()` in move.cpp only
lets a non-human player pick a feature up while that droid holds a
DORDER_RECOVER order, and the AI scripts retask units every second, so the one
order issued at drop time was gone almost immediately. Drums now get the same
per-sweep re-issue crates already had, so AI units genuinely fetch them.

## Round 7: the AI stops beelining for lab upgrades

Round 6 put `DOCTRINE_LAB_PRIORITY` first *unconditionally*, and the AI duly
beelined the ladder while fielding nothing but the starting machinegun. The
policy is now adaptive and follows the brief directly:

1. **A real weapon first.** `DOCTRINE_EARLY_WEAPONS` (Twin MG, Light Cannon,
   Flamer, Heavy MG) outranks lab work until at least one is actually in hand
   (checked with `componentAvailable`, not by topic count).
2. **Then more weapons at that level** -- the favoured-family list keeps running.
3. **The lab ladder only once research is genuinely slow.**
   `doctrineAvgResearchSeconds()` averages the `points` of everything currently
   on offer and divides by live lab throughput (`Upgrades[me].Building`, which
   already includes the module and any upgrades taken). Above
   `DOCTRINE_SLOW_SECONDS` (360 = 6 minutes) the ladder moves to the front.
4. **A fallback** keeps a lab from idling: if no weapon is reachable, the ladder
   runs anyway rather than leaving the lab empty.

Measured opening for one Hard AI, exactly the intended shape:

| time | topic |
|---|---|
| 1:09 | MG1 |
| **4:31** | **Twin MG** |
| **6:08** | **Flamer** |
| **7:51** | **Heavy MG** |
| **8:09** | **Light Cannon** |
| 8:37 | Command Relay -- first step toward the ladder |
| 11:59 | Research Module |

Four weapons before any lab work, and the module arrives when the tree has
actually slowed. 32 topics completed in the run, zero script errors.

## Round 8: lab upgrades stop chaining, scav infantry from t=0

**Why it chained.** The 6-minute rule was measured with a *mean* over every
available topic, and topic costs run from 1 point to 56,600. At the base lab
rate of 6 points/sec the typical topic already takes **6.7 minutes** -- so the
gate was open from the first check and never closed, and the AI walked the whole
ladder. Two changes:

* **Median, not mean** (`doctrineTypicalResearchSeconds`). Robust to both the
  1-point trivia and the 56,600-point monsters, and it tracks what the AI will
  actually pick next. Each lab rung raises throughput, which pushes the median
  time back under the threshold and closes the gate by itself.
* **Alternation rule.** The AI may never hold more lab rungs than weapons
  (`DOCTRINE_LAB_LEAD = 0`), so every rung has to be paid for with a weapon
  first. The idle-lab fallback honours the same rule -- without that it quietly
  chained the ladder on its own, which is the bug in miniature.

Measured, same Hard AI: **2 lab rungs out of 25 topics**, and nothing chained --
Command Relay 8:38, Research Module 12:02, and between and after them Twin MG,
Flamer, Heavy MG, Light Cannon, half-tracks, power module, mortar.

**Scavenger infantry from the first minute.** Foot troops are no longer a
phase-1 privilege -- the infantry branch now sits above the phase-0 truck line,
so scavengers field people immediately and only the *wheeled* arsenal stays
phase-gated. Anything that is not infantry in phase 0 still becomes a truck,
which funds the expansion rather than idling the factory. Measured: scav units
climb 1 -> 16 over the first 2:40 (previously flat), structures 20 -> 34 in the
same window.

## Round 9: guard tower first, scavenger air at 15 minutes

**Heavy MG Guard Tower is now the AI's first research after MG1.**
`R-Defense-Tower01` (grants `GuardTower1`, needs `R-Wpn-MG1Mk1`, only 600
points) sits at the very head of the decision chain -- ahead of the early
weapons AND ahead of any lab work. Measured: researched at 5:12 and the first
tower is standing by 4:20, reaching 5 emplacements by 9:40.

One honest limit: it cannot be *instant* after MG1Mk1 completes at 1:09, because
both labs are already mid-topic and research cannot be preempted. The tower goes
in as soon as a lab frees. Priority is what was asked for and priority is what it
now has.

**Scavenger air moved to 15 minutes.** `SCAV_T_AIR` 600e3 -> 900e3. VTOL
factories and helicopters both gate on it, so nothing airborne appears before
15:00. The heavy ground phase stays at 10:00.

## Round 10: Synaptic Link demoted below the support topics

The round-8 alternation rule looked right but counted the wrong things. Its
"lab steps done" tally included `R-Struc-CommandRelay` and
`R-Struc-Research-Module` -- cheap enablers, not upgrades -- so after those two
the AI already had budget for **Synaptic Link Data Analysis**
(`R-Struc-Research-Upgrade01`) and took it immediately after the module.

The one list is now two, and a support tier sits between them:

| list | contents | when |
|---|---|---|
| `DOCTRINE_LAB_INFRA` | Command Relay, Research Module, Factory Module, Power Upgrade | as soon as research is slow |
| `DOCTRINE_SUPPORT_FIRST` | **Tank Traps, Mobile Repair, Hardcrete, Improved Hardcrete, Repair Facility** | before any Synaptic upgrade |
| `DOCTRINE_LAB_UPGRADES` | Synaptic Link Data Analysis and the rest of the chain | last, and only when slow |

`doctrineLabStepsDone()` now counts **only** the Synaptic chain, so the
alternation rule measures what it was always meant to. The idle-lab fallback
was also restricted to the enablers -- it could otherwise reach the Synaptic
chain by itself, which is the same bug through a different door.

Measured opening, one Hard AI:

| time | topic |
|---|---|
| 4:49 | Guard Tower |
| **5:18** | **Tank Traps** |
| 6:08 | Flamer |
| **6:35** | **Mobile Repair Turret** |
| **6:59** | **Hardcrete** |
| 7:51 / 8:34 | Heavy MG, Light Cannon |
| 10:56 | **Improved Hardcrete** |
| 12:51 | Research Module |
| **21:04** | **Synaptic Link Data Analysis** (1 of 27 topics) |

## Round 11: chassis research, and proactive base AA

**Why the AI stayed on basic weapons -- two causes, one visible symptom.**

* *Structural*: `R-Vehicle-Metals01` required `R-Cred-Breadth03` -- a crate
  credential -- and Tracks, Body08 and Body11 all chain through Metals02 ->
  Metals01. The whole heavier-vehicle line was crate-locked (the round-5
  disease again). Metals01 now anchors on Engine01; reachable-without-crates
  went 222 -> **263**, with Tracks, Body08/11 and Thermal Armor all open.
* *Behavioural*: nothing in the research chain ever asked for vehicle tech, so
  even reachable rungs lost to the weapon bias every time. A new
  `DOCTRINE_VEHICLE_TECH` list (engines, half-tracks/tracks, bodies, metals,
  ordered cheap-to-dear) runs 50% of the time before the favoured family and
  always as a catch-up after it.

The advanced-weapons complaint is the same fault seen from the factory: Nexus
builds from templates that need body+propulsion+weapon ALL available, and with
tracks/heavy bodies unreachable it could only ever field wheeled Vipers no
matter what guns it knew. With the chassis line open the better templates pass
`componentAvailable` and enter the pool on their own.

Measured (8-minute headless run): Engine01 at 7:48, Half-tracks at 12:04,
interleaved with weapons, walls and infrastructure -- 27 topics, no lab-chaining.

**Base air defence.** Nexus's own AA logic is purely reactive -- it only places
AA after already being bombed (`buildAANearLoc` from eventAttacked). Two
changes:

* `DOCTRINE_AA` research from minute 12 (before scavenger air at 15:00):
  Hurricane AA -> its site, then Sunburst -> its site. The Hurricane line needs
  only Heavy MG + Research Module, both already in the AI's normal opening.
* `baseAADefense()` in the build chain: two AA sites go up around the base as
  soon as any AA structure is researched -- no longer waiting to be bombed
  first.

## Round 12: defence variety, derrick pickets, and walls

**Defence tech is now researched deliberately.** `DOCTRINE_DEF_TECH` sits right
after the support tier: Bunker, Cannon Hardpoint, MG Hardpoint, Mortar Pit,
Mini-Rocket Tower, Rotary Pillbox -- every topic 600-1100 points and hanging
off research the AI does anyway. Unlocking them wakes three vanilla behaviours
that were sitting dead for lack of tech:

* `buildGates()` fortifies map gateways inside its base with wall-tower
  **hardpoints** -- this is the walls answer;
* `derrickDefense()` rings derricks with mortar pits once sensors are up;
* the basic-defence pool for pickets grows beyond the lone Guard Tower.

**Own derricks get a picket.** All three vanilla derrick paths either needed
tech the AI rarely had or applied to ENEMY oil only (`protectCloseDerrick`).
New `derrickTowerDefense()`: one basic emplacement per owned derrick (skipped
under threat), placed by the oil-builder trucks, budgeted by the existing
4+derricks tower cap. Chain order: base towers -> base AA -> derrick pickets ->
sensors -> mortar pits.

**On walls, honestly:** Nexus fortifies gateways with hardpoints and rebuilds
Hardcrete Walls it once owned (`rebuildQueue`), and both now fire because the
tech arrives. It has NO placement logic for free-form curtain walls, and
inventing one would be a large, risky addition -- not done.

**Reactive AA stays.** The proactive two-site step is on top of, not instead
of, the vanilla bombed-then-build response.

Measured: Pillbox research at 17:09, mortar tech at 16:18, wall upgrades and
vehicle engines interleaved, def=5 while holding 3 derricks -- 28 topics, zero
errors.

## Round 13: AA restraint, quick-wins research, cumulative scav tiers

**AA stops after one working line.** The AA research step now runs only while
no AA site is available yet -- or when an enemy actually fields air
(`doctrineEnemyAir()` counts hostile VTOLs, scavengers included). One Hurricane
line while the sky is empty; Sunburst and the rest only under real air threat.

**Quick wins before long hauls.** New step in the chain: any available topic
that would finish inside **2 minutes** at current lab speed is taken first,
cheapest first (`doctrineQuickTopic()`), before anything long-running gets a
lab. Long topics only start when nothing quick remains -- and every lab
upgrade taken widens what counts as "quick", so the net effect compounds.
Measured: from 8:00 on, a stream of cheap topics (Gate, Wall Upgrade, MG
Accuracy, Engine02, MiniPod, Command Relay, MG Range) with no monster topic
hogging a lab; 27 topics, no Synaptic chaining, zero errors.

**Scavenger tiers now accumulate.** The phase lists REPLACED each other, so a
heavy-phase scav force abruptly stopped fielding trikes and MG infantry. The
body and weapon pools are now the union of every unlocked tier with the newest
tier entered twice -- emphasis on the high end, everything still in the mix.

Caveat: AA completion and the scav late-game mix both sit past what a headless
run can reach; ordering is verified, the feel needs a real game.

## Round 14: fixed cascade replaced with a scoring model

**Why it kept picking long topics -- my bug.** The decision chain was eight
ordered lists, first match wins, and the "quick wins" step added last round sat
**seventh**. Five list steps outranked it, and those lists hold expensive
topics: `DOCTRINE_VEHICLE_TECH` contains Metals02 (3,600) and Engine03 (4,800),
`DOCTRINE_LAB_INFRA` the Research Module. So a 4,800-point engine upgrade beat a
300-point tank trap purely because its list came earlier. I described that step
last round as running "before any long-running topic gets a lab" -- it did not.

**Answering the design question: options, not a fixed tree.** The cascade is
gone. Every available topic is now scored:

    score = weight(what it is) x HALFLIFE / (seconds + HALFLIFE)

with `DOCTRINE_HALFLIFE = 150`, so a topic taking 150s scores half what an
instant one would, and a 10-minute topic about a fifth. Weights:

| kind | weight |
|---|---|
| AA, when none exists or enemy air is up | 130 |
| defences and defence tech | 95 |
| weapons (x1.4 for this AI's favoured family) | 90 |
| vehicle tech (engines, tracks, bodies, armour) | 90 |
| support (traps, repair, walls) | 85 |
| lab infrastructure | 70 |
| Synaptic upgrades, when research has gone slow | 75 |
| **Synaptic upgrades otherwise** | **4** |
| **AA once one line exists and nothing flies** | **5** |
| anything else | 55 |

Two consequences worth naming. Nothing is invisible any more -- topics that
were in no list at all can now be picked on merit. And the AA/Synaptic
restraints become weights rather than gates, so they degrade gracefully instead
of switching hard on and off.

The only hard-coded priority left is the Heavy MG Guard Tower, which still runs
before scoring.

Measured against the previous build, same map and difficulty:

| | old cascade | scoring |
|---|---|---|
| median topic cost | 900 | **660** |
| mean | 1,011 | **801** |
| dearest topic taken | 2,400 | **1,800** |
| topics under 1,200 points | 23/27 | **24/26** |

No Synaptic upgrade was taken at all in the scoring run (its 2,400 never
outscored the cheap field), and the AI filled out Pillbox 01/04/05, Hardcrete
Gate and Wall Tower instead -- the defence variety that had been theoretically
unlocked since round 12 but never chosen.

**Tuning from here** is now editing weights rather than reordering a list. If
the AI feels too defensive, drop `DOCTRINE_W_DEFENCE`; if it should tolerate
long research, raise `DOCTRINE_HALFLIFE`.

## Round 15: chassis ordering, and the AI builds walls

**The Chassis Handling bug -- real, and DOCTRINE's own.** `generate_tree.py`
gave all three tier-1 lines the same prerequisite (`R-Sys-Debrief01`), so Light,
Medium and Heavy Chassis Handling appeared in the lab simultaneously -- and
Heavy was researchable long before any heavy body existed. Each line now hangs
off the first body of its own size class:

| line | now requires |
|---|---|
| Light Chassis Handling I | `R-Vehicle-Body01` (Viper) |
| Medium Chassis Handling I | `R-Vehicle-Body05` (Cobra) |
| Heavy Chassis Handling I | `R-Vehicle-Body11` (Python) |

Tiers II and III already chained off tier I correctly.

**The wider audit.** A sweep for tiered topics not requiring their predecessor
flags 211 -- but almost all are legitimate. Vanilla's body numbering interleaves
size classes on purpose (Body11 is a HEAVY that genuinely follows the MEDIUM
Body05), `R-Cred-Breadth*` are script-granted, and the crate axis topics carry
no prerequisites by design. The Chassis family was the one true defect.

**Walls.** Scripted line-building turns out to be impossible: `orderDroidBuild`
takes a single tile, and no shipped AI ever *issues* `DORDER_LINEBUILD` -- they
only test for it as an order state. So walls go up one segment at a time:
`baseWallDefense()` puts up to **two hardcrete segments beside each base
emplacement**, capped at 14 total, skipping tiles that are occupied or unsafe.
That is the classic tower-behind-wall shape rather than a curtain wall, and it
is what the API actually supports.

Measured: first wall at 9:20 (immediately after Hardcrete research), peaking at
6 alongside 5 emplacements before scavengers ground them down. Build order is
now base towers -> base AA -> derrick pickets -> walls -> sensors -> mortar pits.

## Round 16: full prerequisite audit -- the late game was dead-ended

An audit of **all 119 component unlocks** (every body, weapon, propulsion) plus
**all 90 structure unlocks** found 11 components unreachable without crates --
and every one traced to a SINGLE prerequisite edge:

    R-Struc-Factory-Upgrade01  requires  R-Cred-Breadth03

Breadth credentials are script-granted only once N weapon families have a tier-1
axis researched -- i.e. N crates. That one edge gated:

    Factory-Upgrade01 -> VTOL Factory -> VTOL Propulsion
        -> all five VTOL bombs
        -> Engine07 -> Engine08 -> Engine09
        -> Body10, Body13, Body14  (the top heavy chassis)
        -> Transporter, Super Transporter

So the entire air branch and the top of the body and engine ladders sat behind
crate luck -- the same disease as the weapon unlocks (round 5) and the vehicle
metals (round 11), one layer deeper. Three infrastructure topics are re-anchored
on the buildings they actually follow from:

| topic | was | now |
|---|---|---|
| `R-Struc-Factory-Upgrade01` | Breadth03 | Factory Module |
| `R-Struc-Power-Upgrade01` | Breadth02 | Power Module |
| `R-Sys-Autorepair-General` | Breadth04 | Research Upgrade02 |

`R-Struc-Limit-Labs` keeps its Breadth gate deliberately -- DOCTRINE strips its
Limit result and caps labs from script, so it blocks nothing.

### Result

| | before | after |
|---|---|---|
| component unlocks reachable | 108/119 | **119/119** |
| structure unlocks reachable | 90/90 | 90/90 |
| topics reachable without crates | 263 | **311** |
| cycles / dangling | 0 / 0 | 0 / 0 |

Per class, everything now completes: 6/6 heavy bodies, 6/6 light, 5/5 medium,
1/1 super heavy, all six propulsions including Lift, and every weapon
subclass -- 16/16 cannon, 15/15 rocket, 11/11 machinegun, 11/11 energy, 8/8
missile, 7/7 gauss, 5/5 bombs, and the rest.

**Honest note on the ladders themselves:** Metals, Armor-Heat, Engine and the
Cyborg equivalents were already correctly chained (each rung requires the one
below). Vanilla's body numbering interleaves size classes on purpose, so
Body11 legitimately follows Body05 -- that is not a defect. The Chassis Handling
family (round 15) and this Breadth edge were the two genuine ordering faults.

## Round 17: the other four AIs share the research engine

Nexus had the DOCTRINE scoring engine; the other four AIs did not. They steer
research from hard-coded topic lists written against the **vanilla** tree, and
DOCTRINE moved a great deal of that tree. Measuring each AI's list against what
actually ships:

| AI | topics referenced | deleted by DOCTRINE | behind crates | dead |
|---|---|---|---|---|
| BoneCrusher | 497 | 110 | 103 | **43%** |
| NullBot | 203 | 0 | 23 | 11% |
| SemperFi | 62 | 0 | 7 | 11% |
| Cobra | 92 | 1 | 0 | 1% |

Nothing crashed, which is why this went unnoticed: `pursueResearch()` on a
missing or unreachable topic simply returns `false`. The AI works down its list,
fails most of it, and researches far less than it should. BoneCrusher was
steering by a list that is nearly half dead.

### What changed

The engine was lifted out of the Nexus-only header into one shared source
(`DOCTRINE_ENGINE_JS`), so tuning a weight now tunes **all five AIs at once**.
Two portability fixes were needed:

- `doctrineHasAA()` read Nexus's `STANDARD_ANTI_AIR_DEFENSES`, which does not
  exist in the other scripts. The AA structure list is now inlined.
- A single entry point, `doctrineResearchPick(lab)`: guard-tower topics first,
  then the best-scoring topic. Returns `true` when it starts research.

Each AI's research entry point tries the engine first and falls back to its own
list only if the engine declines:

| AI | entry point | mode |
|---|---|---|
| NullBot | `doResearch(lab)` | given one lab, returns `true` on success |
| BoneCrusher | `doResearch()` | finds and drives every idle lab itself |
| SemperFi | `lookForResearch()` | same |
| Cobra | `cobraDoResearch()` / `research()` | same |

The two game versions differ in brace style (`function f()
{` vs
`function f() {`) and in names -- Cobra's entry is `cobraDoResearch` in 4.7.0 and
plain `research` in 4.5.5 -- so entries are matched by regex on the function head
and the hook is inserted after the opening brace. The hook uses **only engine
globals** (`RESEARCH_LAB`, `BUILT`, `structureIdle`) rather than any AI's private
structure table, wrapped in `try/catch`, so it is scope-safe everywhere. An
earlier version used Cobra's `RES_LAB` and would have thrown -- `node --check`
cannot catch an undefined global, only a real game can.

### Verification

| check | result |
|---|---|
| JS syntax, all files, both versions | 26/26 pass |
| engine present in all five AI research files | 5/5, both versions |
| hook inside the entry function, after the engine | 4/4, both versions |
| Nexus regression (headless, scav-Medium) | 17 topics, **0 errors** -- unchanged shape |
| debug output in shipped build | none (all behind `TELEMETRY`/`DOCTRINE_DIFF_DEBUG`, both `false`) |

**What is not verified.** The headless harness only ever loads Nexus -- a
Cobra-configured game silently falls back to it -- so the other four AIs are
confirmed by data, syntax and hook placement only. Their *behaviour* needs a real
skirmish. Pick BoneCrusher or Cobra in a normal game and watch whether research
keeps moving past the early tiers; that is the one thing the harness cannot tell
us.

## Round 18: every AI tested, and research now follows the personality

### First: every headless result before this round was invalid

`--skirmish=<name>` needs the **`.json` extension**. Without it the game logs
one line and then silently starts a *different* game:

    error [loadMapChallengeAndPlayerSettings] Missing specified file: tests/scav-Medium

...followed by a default 10-player, all-Nexus, all-Medium match on 4c-rush. It
runs, produces plausible output and exits 0. Every headless run in this project
had been hitting that fallback, which is where three "known limitations" came
from. None of them were real:

| believed | actually |
|---|---|
| the harness only ever loads Nexus | the config was never read |
| it ignores per-player difficulty | difficulty applies fine (`difficulty: 3` for Hard) |
| it ignores the `bases` setting | bases apply fine (17 topics granted at t=0) |

The `ai` field also needs the script path **relative to `multiplay/skirmish/`** --
the same value as that AI's own `.json` `js` field. Other forms fail in three
different ways, two of them silent:

| value | result |
|---|---|
| `bonecrusher/bonecrusher.js` | **works** |
| `multiplay/skirmish/bonecrusher/bonecrusher.js` | resolves to `multiplay/skirmish/.` -- load error |
| `bonecrusher` | load error |
| `bonecrusher.json` | **no AI loaded at all, and no error line** |

Slot `player_0` is the autogame host and never gets an AI script, so a
four-player config tests three AI instances.

### Every AI verified in a real game

One telemetry line per AI per game, emitted from the research hook entry (not
the lab loop, so it fires even when every lab is busy):

| AI | personalities seen | family chosen | topics | errors |
|---|---|---|---|---|
| Nexus | `generic1` ×3 | mg | 74 | 0 |
| NullBot | `fc`, `mr`, `mc` | cannon, rocket, cannon | 76 | 0 |
| Hover AI | `r` ×3 | rocket | 85 | 0 |
| Turtle AI | `mr`, `mc`, `mc` | rocket, cannon, cannon | 65 | 0 |
| Cobra | `AC`, `AB`, `AC` | cannon, rocket, cannon | 122 | 0 |
| BoneCrusher | `build:standart` | mg, mortar, mortar | -- | 0 |
| SemperFi | `fixed` (has none) | rocket | 65 | 0 |

All seven load, reach their research code, and research. Cobra is the strongest
performer at 122 topics.

### Research now follows the personality

The engine used to pick its favoured weapon family from `me % 5` -- the **player
slot**. Cobra AC (cannons), NullBot FR (flamers) and Hover R (rockets) all
researched the same line if they shared a slot: the engine was silently
overriding every personality's weapon identity.

It now reads what each AI actually declares, and only falls back to the slot
when an AI declares nothing:

| AI | what the engine reads |
|---|---|
| Cobra | `subPersonalities[personality].primaryWeapon.weapons[].res`, then `.res` |
| NullBot / Hover / Turtle | `personality.weaponPaths[0].weapons[].res`, then `.earlyResearch` |
| Nexus | `nexusBranch[branch].earlyResearch` |
| BoneCrusher | `research_path` |
| SemperFi | nothing -- build-time default (rockets, per its own description) |

Two design points that mattered:

- **Families are whole weapon LINES, matched by prefix.** Matching only the four
  or five base unlocks missed every damage/accuracy/ROF upgrade -- most of what a
  family costs. Cobra states its preference as `R-Wpn-Cannon-Damage02`, an
  *upgrade*, so exact-id matching could not read Cobra at all.
- **Ordered lists rank by position; flat lists count by volume.** A personality's
  weapon list is a preference (first = primary), but BoneCrusher's `research_path`
  is a whole-game plan with no ranking.

Verified offline against every AI's real personality data by running the shipped
engine in Node -- 24 cases, 0 errors:

| AI | personality | family |
|---|---|---|
| Nexus | generic1, vtol1 | mg |
| NullBot | MR, FR | rocket |
| NullBot | MC, FC | cannon |
| Hover AI | R | rocket |
| Turtle AI | MR / MC | rocket / cannon |
| Cobra | AC / AR / AB / AM / AA | cannon / flamer / rocket / mg / mortar |
| SemperFi | (none) | rocket |

Cobra gets a clean five-way spread, one family per personality -- exactly the
variety its author intended. Live games matched every offline prediction.

**Honest note on BoneCrusher.** It has no personalities, and its research paths
are genuinely mixed rather than themed: the path *named* `research_cannon` holds
7 machinegun topics to 6 cannon, and `research_fire2` is cannon-heavy despite the
name. The engine reads the emphasis of whichever path was drawn, so BoneCrusher's
family varies per game and will not always match the path's name. That is a fact
about the vanilla data, not a mapping fault.

**Known, deliberately unfixed.** Nexus's `vtol1` personality is unreachable in
vanilla: it declares `"type": "air"` but `chooseVtolPersonality()` searches for
`"vtol"`, gets nothing, and falls back to land. On a large map Nexus decides to
"go air" 45% of the time and silently plays land anyway. Left alone -- `vtol1`
declares `attackers: 0`, so enabling it would field an AI that builds no ground
attack force at all, and that needs its own testing round before it is switched
on.

## Round 19: why weapons max out, the counter tables, and cyborgs

### Why BoneCrusher's weapons were maxed out

Not crates -- or rather, crates only open the door. Three causes, largest first:

**1. Every upgrade ladder was truncated from 10 rungs to 4, at nearly full value.**
`R-Wpn-<fam>-Damage01..04` grant **+34/+46/+61/+82 = +223%**; vanilla's ten rungs
grant +250%. So a family reaches ~90% of vanilla's ceiling for **14,800 research
points instead of 58,600** -- about 4x cheaper. Rungs 05-10 exist only as inert
stubs (1 point, no results) so AI `pursueResearch` lookups resolve. This applies
to the human player as much as the AI.

**2. Hard/Insane AI get free weapon upgrades on a timer.** `doctrineFreeIntel()`
completes a random available `R-Wpn-*-(Damage|Range|Reload|Accuracy)0[1-9]` topic
every **150 s on Hard, 75 s on Insane** -- no research time, no power. In an
86-minute game that is **~34 free rungs on Hard, ~68 on Insane**, when a whole
family only *has* 16 upgrade topics. Across the tree, 179 such topics worth
678,800 research points. **AI-only -- the player never gets this.**

**3. The scoring engine concentrates on one family** (`DOCTRINE_FAMILY_MULT 1.4`
plus a 150 s half-life favours cheap topics, which is exactly what damage rungs are).

Left unchanged this round by choice. When it needs fixing, cause 2 is the smallest
effective lever: it is AI-only, so a lifetime cap and a slower timer leave the
player's own curve untouched.

### Reference: what each weapon is strong and weak against

**vs units** (`weaponmodifier.json`, % damage by propulsion):

| effect | Wheeled | Half-Track | Tracked | Hover | Legged | VTOL |
|---|---|---|---|---|---|---|
| ANTI PERSONNEL (MG) | 95 | 45 | **35** | 100 | **190** | 55 |
| ANTI TANK (rockets, missiles) | 130 | 135 | **150** | 100 | **25** | 70 |
| ARTILLERY (mortar, howitzer) | 95 | 70 | **30** | 110 | **165** | 20 |
| FLAMER | 120 | 105 | 70 | 135 | 155 | 20 |
| ALL ROUNDER (cannon) | 110 | 100 | 90 | 105 | 55 | 45 |
| BUNKER BUSTER | 30 | 35 | 45 | 20 | 25 | 25 |

**vs buildings** (`structuremodifier.json`, % damage by structure class):

| effect | SOFT | MEDIUM | HARD | BUNKER |
|---|---|---|---|---|
| ANTI PERSONNEL (MG) | 110 | 45 | 25 | 30 |
| ALL ROUNDER (cannon) | 125 | 95 | 75 | 60 |
| ANTI TANK | 80 | 60 | 30 | 55 |
| ARTILLERY | **200** | **165** | **130** | 45 |
| FLAMER | 155 | 65 | 15 | **320** |
| BUNKER BUSTER | 100 | 130 | **320** | **450** |

| class | holds |
|---|---|
| SOFT (5) | scav power gen and walls, cooling tower |
| MEDIUM (49) | derricks, power gens, labs, factories, cyborg factory, guard towers, mortar pits |
| HARD (96) | HQ, hardcrete walls, gates, tank traps, wall-tower hardpoints, AA sites |
| BUNKER (15) | every pillbox, plasmite bunker, missile silo |

Artillery is the siege arm (buffed against everything but bunkers). Pillboxes are
the artillery-proof answer, and bunker busters (450%) or flamers (320%) are the
answer to *them*. Machineguns were deliberately taken off demolition duty in an
earlier round. **Cannon is the open question**: it lost ground on both tables
(100 -> 75 vs HARD, 100 -> 90 vs Tracked) and is now mediocre at everything with
no matchup it wins. HARD is its natural niche if it needs one.

### Cyborgs: cheaper, quicker, and genuinely fragile

The measurement that mattered, and it corrected an earlier claim of mine that
cyborgs were already the cheap option. Counting the **complete unit** -- the
weapon is the dominant cost, which body-only tuning would have missed:

| complete unit | power | build points | effective HP |
|---|---|---|---|
| MG cyborg (before) | 75 | **305** | 300 |
| MG Viper | 90 | 250 | 130 |
| **MG cyborg (after)** | **41** | **170** | **162** |

`CyborgChaingun` alone cost 40 power / 160 points where `MG1Mk1` costs 10 / 50,
and did *less* damage (12 vs 15). So cyborgs were 22% **slower** to build than a
tank and twice as durable -- the opposite of a swarm unit.

| change | from | to |
|---|---|---|
| `CyborgLightBody` power / points / HP / armour | 25 / 95 / 200 / 12 | 16 / 65 / 120 / 7 |
| `CyborgHeavyBody` power / points / HP / armour | 50 / 205 / 300 / 15 | 34 / 140 / 190 / 10 |
| `CyborgLegs` power / points / HP-share | 10 / 50 / 50% | 7 / 35 / 35% |
| `CyborgChaingun` power / points / damage | 40 / 160 / 12 | 18 / 70 / 15 |
| other cyborg weapons | -- | ~0.55x power, ~0.5x points |
| `R-Struc-Factory-Cyborg` | 1800 pts / 134 | 1000 / 75 |
| ANTI PERSONNEL vs Legged | 175 | 190 |
| ARTILLERY vs Legged | 140 | 165 |

Measured on the shipped build: **46% the power, 68% the build time**, and against
machineguns an effective 85 HP versus a Viper's 137 -- so a cyborg dies to MG fire
in ~62% of the time a Viper does, while shrugging off anti-tank at 25%. Dropping
armour 12 -> 7 matters as much as the HP cut: `MG1Mk1` deals 15, so against 12
armour it was nearly pinned to its minimum-damage floor.

Cyborg weapons are ANTI PERSONNEL and ANTI TANK, which do only 45% and 60% to
MEDIUM buildings -- so a cyborg swarm harasses units but cannot flatten a base.

### The blocker this would have hit

`R-Struc-Factory-Cyborg` scored **18.3** under the research engine -- dead last
behind every early topic, because it matches no priority list and is not
`R-Vehicle-`/`R-Defense-`/`R-Wpn-`, so it fell into the catch-all weight and was
then punished for its cost. The AI almost never built cyborgs at all, and the
entire rebalance above would have been **invisible to all seven AIs**.

Fixed with a `DOCTRINE_UNIT_ENABLERS` list at weight 100 -- one topic that unlocks
the factory, the body and the legs is worth more than a single stat upgrade. With
the cost cut it now scores 47.3, placing it 3rd-4th: early and reliable, without
displacing the opening guard tower or tank traps.

### Measured: every AI now fields cyborgs

One headless game per AI on the shipped build, with a `cyb=` counter added to the
telemetry census (peak cyborgs held by a single player):

| AI | cyborg factory researched | peak cyborgs | peak combat units |
|---|---|---|---|
| BoneCrusher | yes | **104** | -- |
| Cobra | yes, 3/3 instances | **40** | -- |
| Nexus | yes, 3/3 @ 697s | **36** | -- |
| NullBot | yes, 12x | **38** | 53 |
| SemperFi | yes, 3/3 @ 254s | **8** | 18 |
| Turtle AI | yes, 3/3 @ 197-246s | 0 | **0** |
| Hover AI | yes, 3/3 @ 272s | not observed | -- |

Zero script errors in every run.

**Turtle's 0 is not a fault** -- it built *no combat units at all* (`atk=0` at
1040s). That is `defensiveness: 100` doing exactly what it says: towers, not units.

**Hover is the one gap.** It researches the factory reliably and shares NullBot's
production code and templates, so it should behave like NullBot, but every Hover
game either ended before ~270s (free-for-all) or produced no units at all
(all-allied, where the only enemy is scavengers). Unverified rather than working
or broken -- worth a glance in a real game.

**BoneCrusher at 104 cyborgs is the swarm risk landing.** Its nominal `maxCyborgs
= 30` clearly does not bound the standing army. Nexus stopped at 36 against its
cap of 35, so that cap does work. If 100-cyborg BoneCrusher armies are too much in
play, the dial is `CYBORG_TUNING` build points, not damage.

**Correction (round 21):** I previously wrote that `Cannot build "Scavenger Gun
Tower" for player 7` was pre-existing noise unrelated to DOCTRINE. That was
**wrong**. `A0BaBaGunTower` appears only in *our* `SCAV_PICKETS` list -- the stock
scavenger script never names it -- and it is not in the scavengers'
enabled-structure list in `rules/setup/scavengers.js`. So every picket attempt
failed, ~660 times in an 86-minute game. Fixed in round 21 by using `bbaatow`,
which stock uses, is enabled, and mounts the only ShootAir scavenger ground gun.

Two harness notes for next time: `timeout` cannot kill the headless binary (it
ignores SIGTERM, and even `-k` did not land), so runs must be capped with an
explicit `taskkill //F //IM warzone2100.exe` after a `sleep`. And an all-allied
config keeps a game alive far longer, but the NullBot-family AIs then build no
army at all, so production has to be measured in free-for-all.

### Also fixed: 660 engine asserts per game

`R-Struc-Research-Upgrade03` carried a result vanilla does not have --
`{"class": "Building", "parameter": "ModuleResearchPoints"}` with no filter, so the
engine applied it to every building and asserted on each one lacking that
parameter. One 86-minute game logged 660 of them. The build now strips any
`Building` result whose parameter no vanilla topic sets, so this class of stray
cannot come back silently.

## Round 23: the non-Nexus AIs stop chaining research upgrades

### Why SemperFi (and BoneCrusher, Cobra) still over-researched upgrades

Nexus behaved because its hook REPLACED its research chain inline. The other
AIs' hooks ran BEFORE their own code -- and the engine leaked labs back to it:

- `doctrineResearchPick` computed exactly ONE best topic. With several labs,
  lab 1 started it, lab 2 recomputed the SAME topic, `pursueResearch` refused
  the duplicate, and lab 2 fell through to the AI's own hardcoded lists.
- Those lists steer straight at the ladder: SemperFi's `POWER_AND_RESEARCH_TECH`
  holds `R-Struc-Research-Upgrade09`, and BoneCrusher's `research_lasttech`
  opens with it. `pursueResearch` toward rung 9 walks the whole Synaptic chain
  one rung at a time -- the exact behaviour being complained about, again.
- A landmine found on the way: the engine's `defined(lab)` guard used a helper
  that Cobra and BoneCrusher never define. Any future call path without the
  hooks' try/catch would have died on a ReferenceError. Replaced with a typeof
  check.

### The fix (shared, all five AIs)

1. `doctrineRankedTopics()` -- the scorer now returns the full ranking, and
   `doctrineResearchPick` walks it until something sticks, so with N labs, lab
   k simply takes the k-th best topic.
2. The self-labs hooks (SemperFi, BoneCrusher, Cobra) now RETURN once the
   engine has taken every idle lab -- the AI's own list only runs if the engine
   genuinely could not start anything.
3. Nexus's inline chain now calls the same `doctrineResearchPick`, so its
   multiple labs stop duplicating each other's picks too.

### Measured (SemperFi, allied, 13 min)

| | before (structure) | after |
|---|---|---|
| research driver | own FUNDAMENTALS list on leaked labs | engine on every lab |
| Research-Upgrade topics | chains toward Upgrade09 | **1**, engine-gated, no chain |
| topic mix | MG + upgrades | walls, cyborg factory, MiniPod, mortar, MRL, metals, bodies (37 topics) |
| labs working in parallel | duplicated picks | distinct topics, near-simultaneous completions |

Zero script errors. BoneCrusher's full run later reached 20 minutes and
confirmed the same shape: 42 topics, only 2 engine-gated Research-Upgrades
(Upgrade01 at 643 s, no chain), a diverse mix of cyborg factory, MG line,
mortars, walls and modules. Cobra carries the identical shared fix but its
runs stayed short -- code-verified plus engine-shaped early picks; watch it
in a real game.

### Scavenger infantry: pairs, and no more loot pinatas

- **Built in pairs**: when the infantry roll fires, the factory is flagged and
  its next idle tick builds the twin before anything else is considered.
- **No drops**: scavenger INFANTRY now yield neither intel crates nor oil
  drums (`DROID_PERSON` excluded in both `tryDrop` and `tryDrum`). They are
  pair-built chaff -- dozens die every minute, and each one rolling on the
  crate table made bodies, not battles, the source of intel. Vehicles and
  structures drop exactly as before.

## Round 24: the opening machinegun is earned, not issued

`R-Wpn-MG1Mk1` is a 60-point topic -- about ten seconds at the base lab rate --
but DOCTRINE was handing the weapon out free at kickoff via
`makeComponentAvailable`, so the topic granted something you already had.

Now the weapon comes out of the lab like everything else:

- `grantStarterWeapon()` calls `enableResearch(STARTER_TOPIC, p)` instead of
  `makeComponentAvailable`. The enable is **required**: the topic has no
  prerequisites, which in DOCTRINE means "hidden until enabled", so removing
  the free grant without it would have made the machinegun unobtainable.
- `DOCTRINE_DEFENCE_FIRST` is now `["R-Wpn-MG1Mk1", "R-Defense-Tower01"]`, so
  every one of the five AIs pursues it before anything else.
- Researching it also grants `CyborgChaingun` and `MG1-VTOL`, so it now opens
  MG cyborgs and MG VTOLs in the same breath rather than just the tank turret.

### The regression risk, measured

An older comment recorded that gating this weapon once left an AI with **zero
combat units at t=180s** and overrun by 580s. That was worth re-checking, in the
worst case: `bases: 1` (CAMP_CLEAN), where no lab is pre-placed and the base-tech
table does not grant the topic (`cleanTech = 1`, MG1Mk1 sits at threshold 5).

| | before (free grant) | after (researched) |
|---|---|---|
| MG1Mk1 available | t=0, free | **researched at t=67s**, first topic |
| attackers @ t=60/120/180 | 0 / 0 / 0 | 0 / 0 / 0 |
| attackers @ t=240 | 3 | 3 |
| trucks, factories @ 180 | 6, 2 | 6, 2 |

**Identical.** The early gap was never the weapon -- it is the AI's own
truck-first build order. Gating the machinegun behind its research costs nothing.

Note `bases` in a challenge/test JSON is 1=none, 2=bases, 3=advanced. A first
attempt with `bases: 0` silently behaved like a based game and granted the topic
at t=0, which would have made the test meaningless.

## Round 25: the AIs were starting the MG and then overwriting it

Round 24 put `R-Wpn-MG1Mk1` first in `DOCTRINE_DEFENCE_FIRST`, and Nexus obeyed
(t=67s). SemperFi did not -- it researched sensors and engineering instead, with
the 10-second Machinegun sitting available and untouched.

A probe on the forced-pursue loop showed the engine was working perfectly:

    DOCTRINE-FIRST SemperFi t=80  R-Wpn-MG1Mk1 -> true
    DOCTRINE-FIRST SemperFi t=81  R-Wpn-MG1Mk1 -> true
    DOCTRINE-FIRST SemperFi t=83  R-Wpn-MG1Mk1 -> true
    ...12 attempts in all, t=80s through t=284s, never once finished

The timestamps interleave with the AI's own completions -- attempts at t=272 and
t=281 sit in the very ticks where Sensor-Turret01 and Engineering01 finished on
those same labs, which is the overwrite caught in the act.

`pursueResearch` returned **true** every time -- the lab genuinely started the
topic -- and it never completed, because something replaced it seconds later.

**The bug was mine, from round 23.** The self-labs hook decided whether to yield
to the AI's own research pass by RE-QUERYING `structureIdle()` after calling
`doctrineResearchPick`. That flag does not flip synchronously after
`pursueResearch`, so the labs still looked idle, the hook did not return, and the
AI's own list ran and overwrote what the engine had just started. Nexus was
immune because its inline hook uses the returned `found` flag instead.

**Fix:** count what the engine actually took and yield on that, never on a
re-query:

    let _dTook = 0;
    for (...) { if (doctrineResearchPick(_dLabs[_i])) { ++_dTook; } }
    if (_dLabs.length > 0 && _dTook === _dLabs.length) { return; }

### Measured, CAMP_CLEAN (no pre-placed lab)

| AI | before | after |
|---|---|---|
| SemperFi | sensors/engineering; MG started 6x, never finished | **MG1Mk1 first, t=91s** |
| Cobra | -- | **MG1Mk1 first, t=93s** |
| BoneCrusher | -- | **MG1Mk1 first, t=92s** |
| Nexus | already correct | t=67s |

Zero script errors. This also closes the round-23 leak properly: the AIs' own
lists can no longer overwrite ANY engine pick, not just the machinegun.

## Round 26: bomb trucks that actually close, banded turrets, an infantry horde

### The bomb truck never detonated on anything

It carried `BaBaMG`, which reaches **960**, while the blast it is carrying has a
radius of **256**. So it parked at machinegun range, shot, and died far outside
its own kill zone. It now carries `BaBaMG-Pointblank` -- a generated variant at
**224 range**, deliberately shorter than the blast radius, so if it is shooting
at you it is already inside the explosion.

### Multi-turret vehicles use all their guns

A three-turret vehicle engages at ONE distance, so a 2304-range mortar beside a
384-range flamer meant two of three barrels were decoration. There is no
scripting call to force an engagement range, so instead all three turrets are
drawn from the same **range band**:

| band | range | weapons |
|---|---|---|
| short | 384 | `BabaFlame` |
| medium | 960 | MGs, both cannons, all three rocket types |
| long | 2304 | `Mortar1Mk1` |

### Infantry: first, always, and in numbers -- after one bad miss

First attempt used an absolute floor of `8 + 6/min` capped at **70**. The total
scav unit ceiling is **60**, so the floor could never be satisfied and the ground
factories built infantry and nothing else. Measured over a 55-minute game:
**zero tanks, zero bomb trucks, ever.**

Replaced with a **share** of the ceiling (60%), plus a 30% chance each tick that
a vehicle is built anyway even while below the share. Ceiling raised 60 -> 70 so
"more infantry" does not mean "fewer of everything else".

| | broken build | fixed build |
|---|---|---|
| Tank | NONE all game | first at **240s** |
| Bomb Truck | NONE all game | first at **640s** |
| Heavy Tank | NONE all game | first at **800s** |
| Napalm Helicopter | present | first at **1140s** |
| scav units @ 1200s | 73 | **94** |

### Also: the guard tower stopped being free

`grantStarterDefences()` was switching on `GuardTower1` for everyone four minutes
in, so the Heavy Machinegun Guard Tower became buildable without researching
`R-Defense-Tower01`. That crutch existed because MG1Mk1 used to be unresearchable
-- round 24 fixed that, so the crutch was pure leak and is now removed.
`STARTER_DEFENCES` is empty and there are **zero** `enableStructure` calls left.

### Answered: no, the Mini-Rocket Pod does not fire eight

`Rocket-Pod` has no `numRounds` (so: one rocket) despite the eight tubes on the
model. `Rocket-MRL`, the Mini-Rocket *Array*, is the one with `numRounds: 8`.
Both match vanilla exactly -- not a DOCTRINE change, and the Array is correct.

## Round 27–28: bomb trucks at point-blank, SemperFi's narrow lists, scav squads

- **Bomb truck gun 224 → 40 range** (`BaBaMG-Pointblank`). At 224 it still stood off
  and plinked; at 40 it has to be practically touching its target, well inside the 256
  blast it carries.
- **SemperFi built twin MGs / MG1 only, flamer cyborgs only, MG towers only** — because
  its production and defence lists are *priority lists* and cannon, heavy MG, mortar,
  pillboxes, bunkers and cannon hardpoints were simply absent from them. Lists widened:
  tank weapons 6 → 10, artillery 3 → 4 (mortar), standard defences 6 → 12, artillery
  defences 5 → 6.
- **Scavengers went airborne late** because `enumDroid(me, DROID_WEAPON)` counts VTOLs
  and tanks in one pool and the cheaper VTOL factories won the race for it. Air capped
  at 25% of the unit ceiling. Infantry now come **three** per build; the infantry floor
  is a share of the ceiling (60%) rather than a hard count (a hard count of 70 against
  a ceiling of 60 had produced zero vehicles for 55 minutes).

## Round 29: one weapon at a time, and the cyborg that was never built

- **Widening SemperFi's lists could never have fixed the monoculture.** `buildDroid`
  takes the *first available* entry of a component list, so a priority list yields one
  weapon at a time — every tank a twin MG before, every tank a light cannon after.
  `doctrinePickWeapon()` now draws at random from the best three available. Measured at
  2240s: `Cannon1Mk1×23 MG1Mk1×17 Rocket-MRL×12 MG2Mk1×10 MG3Mk1×6 Rocket-LtA-T×4
  Mortar1Mk1×3`.
- **100% flamer cyborgs was my own bug from round 28**: I had put the light cyborg
  weapons (`CyborgRocket/Cannon/RotMG/Chaingun`) into `CYBORG_ROCKETS`, which
  `buildCyborg` mounts on `CyborgHeavyBody` — an invalid pairing, and the heavy body
  needs `R-Cyborg-Metals04` anyway — so that branch failed outright and every cyborg came
  from the flamer branch (`CyborgFlamer01×100`). Light weapons now have their own list on
  the light body. After: `Flamer×40 Cannon×18 Chaingun×11 Rocket×1`.
- **Scav bunkers shipped**: from phase 2, listed twice in later phases, 4 defences per
  site (was 2), generators picketed too, emplacement ceiling 24 → 44, and the counter
  fixed — it only tallied mortar pits and cannon towers, so bunkers, gun towers, rocket
  pits and flame towers were invisible to the cap.

## Round 30: the scavenger MG tower with the man on top

You reported the new scav MG turret barely scratching anything. It was my regression from
round 21: the picket switched from `A0BaBaGunTower` (which scavengers are not allowed to
build — 660 asserts per game) to `bbaatow`, which is worse in every way:

| | old tower | `bbaatow` as shipped | now |
|---|---|---|---|
| gun damage | 24 (BuggyMG) | **18** (`bbaawep`) | **32** |
| fire rate (firePause) | 5 | **7** — slowest scav MG | **6** |
| tower HP | 400 | **250** | **400** |
| build points | 75 | **200** | **90** |

Armour is subtracted *after* the weapon-effect modifier, so 18 damage was pinned to the
minimum-damage floor: 7.1 of it got through a Viper, about 2 a shot against tracks. Some
of its 80% accuracy was traded back for penetration (70/85).

Sweep of every scav weapon and defence found three more not worth their build cost:

| weapon | problem | change |
|---|---|---|
| AT-Rocket Pit (500 pts, dearest scav defence) | 2 rockets then 140-tick reload; shortHit 30 < longHit 60 | reload 80, shortHit 60 |
| Rocket Pit (400 pts) | 16 damage a shot | 30 |
| BabaFlame | slower (25) than the standard Flame1Mk1 (20) it should beat | 18 |
| BabaMortarPit | **deliberate** DOCTRINE nerf to 12% hit, but a 350-pt pit missing 88% is not worth building | 22/18 (player's mortar stays 50/40) |

Effective damage from the shipped stats (wheeled / tracked / cyborg): MG tower
81→238 / 20→37 / 311→628; Rocket Pit 81→218 / 68→225; AT-Rocket Pit 45→77 / 49→84.
Still weak against tracked armour by design. The scav cannons were left alone —
`ALL ROUNDER` being mediocre is the open balance question. Scav *vehicles* in the last
phase still carry the full-accuracy `Mortar1Mk1` while the pit is nerfed — flagged, not
changed.

*The round-30 in-game "verification" was invalid — see round 31.*

## Round 31: bug sweep — the harness was lying, and the NullBot family was blind

**Your game had no sound.** Not the mod: its archive holds only `stats/`, `multiplay/`
and `mod-info.json`. Every headless test run used `--nosound` against your real profile
and the game persisted `sound=0` into `config` on exit (config written 0.09 s after the
last run's log). Restored (one byte, backup `config.bak-presound`). All test runs now use
`--configdir=<scratch>`.

**Six test configs could never load their AI.** `"ai": "nexus"` / `"Cobra"` / full
`multiplay/skirmish/…` paths make the engine read garbage for the script name (the
`utf8::is_valid` + `unable to open file` asserts I had dismissed as noise). Consequence:
the round-30 scav A/B compared two games in which **no AI existed** — the "scavengers
wiped four Easy AIs" result meant nothing. Working forms: `nexus.js`, `Cobra.js`,
`semperfi.js`, `nb_generic.js`, `nb_hover.js`, `nb_turtle.js`,
`bonecrusher/bonecrusher.js`.

**`buildCyborg` idled the factory** whenever the picked branch had no mountable weapon
(heavy body before any heavy weapon; flamer branch before flamers). Each branch now falls
through unless `doctrinePickWeapon` returns an available component.

**NullBot, Hover and Turtle were wiped by the scavengers in 20 minutes, every game, with
0 tanks and 0 defences.** Root cause: stock NullBot enumerates living players as
`i < maxPlayers`, so the scavenger player does not exist for it. With every real player
allied, `scopeRatings().land === 0` → `produceTank()` returns false → `spendMoney()`
builds trucks forever. (It had an HQ from t=20 s — my first theory, `iCanDesign()`, was
wrong; the probe disproved it.) Fix shipped in `nb_includes/misc.js` (a hostile scavenger
player joins `enumLivingPlayers()`) **and** `nb_includes/adapt.js` (its IIFE-private
per-player stat tables get a scavenger entry — without that, ~1,700
`cannot read property 'collapse'` exceptions per game; caught by the test batch before it
reached you). After: NullBot `atk=135 def=127`, Hover `atk=138 def=136`, scavengers
beaten, 0 script errors over 3 hours each. Turtle additionally ships at
`defensiveness: 90` (was 100, which builds only defences and VTOLs, never a tank). Verified: three allied Turtles now beat the scavengers (`atk=130-142 def=70-116`, scavs gone at 12,440 s, 0 errors) where before all three died by 500 s. Two Turtles beside a Nexus *enemy* still fall at 24 min on Sk-Rush — but so nearly did that Nexus (2 attackers left against 90 scavengers); that is the map and the scavengers, not a script fault.

**Scav script threw** `cannot read property 'x' of undefined` at
`ultimateScavengers.js:488` — stock code: `ff.next()` returns undefined for a truck the
flow field cannot route; sibling at :480 where `pickStructLocation` can return null. Both
guarded; a 6,180 s run is clean.

**Crates**: `drops=0` in every allied-vs-scavenger game is by design (scavenger kills roll
only `SCAV_FLOOR`, scav weapons carry no tech, fresh victims have no experience). In
NullBot-vs-Nexus: `drops=7 recovered=7`.

**Known, non-fatal**: `JSValueToInt32 Failed` engine asserts (3 in an 11,880 s NullBot game, 9 in a 13,200 s Turtle game) — none in any unpatched game, and only in the final minutes when the scavenger faction is down to its last structures, so NullBot is passing an engine call something derived from an emptied scavenger target set. The engine substitutes 0 and play continues; no stack is printed, so the exact call is not yet identified.

Battery (isolated config dirs, five games in parallel, all seven AIs): 0 script errors,
0 AI load failures, 0 failed builds in every game after the fixes above.

## Round 32: anti-air, the VTOL wall, houses that were never wired up

Four items from a 2h43m game on 7c-Thales.

**No AI built an anti-air TANK.** Checked every AA-capable component in `weapons.json`
against all five AI codebases. **Nexus** referenced no anti-air turret anywhere in its 21
files; **SemperFi** none in its 9 -- both build AA *structures* at home while their field
armies cannot shoot back at aircraft at all. BoneCrusher's only two mentions were a code
comment and a wall hardpoint. Cobra and the NullBot family already list AA turrets in their
tank weapon tables and could always field them. Nexus (7 templates), SemperFi (`TANK_AA`) and
BoneCrusher now build them, all gated on a new shared `doctrineAirThreat()` -- AA turrets are
subclass `A-A GUN` / `A-A MISSILE` and can only engage aircraft, so one built against an empty
sky is a wasted factory slot. The helper counts scavenger helicopters, which SemperFi's own
`enemyHasVtol` flag would never have seen.

**VTOLs were unreachable.** The prerequisite closure of `R-Struc-VTOLPad` was 16 topics and
40,900 research points -- 114 minutes of a single base-rate lab. The three VTOL topics are
halved and the factory no longer requires `R-Vehicle-Engine03` (4,800 points plus its own
chain); Hover and Factory-Upgrade01 still gate it. Now **28,300 points, ~79 minutes** -- a
mid-game commitment instead of a wall.

**Houses never spawned anyone -- and never produced intel either.** The scavenger spawn was
genuinely never implemented, but the deeper bug is that the whole feature branch of
`eventDestroyed` was dead code: the engine fires `eventAttacked` for droids and structures
only, so a destroyed FEATURE has no last-hitter record and every one of them returned at the
`rec === undefined` gate. Measured across every playtest in this document, `scenery intel`
was **0 in all of them**. Scenery is now handled before that gate, credited to the closest
non-scavenger unit within 8 tiles.

*This was invisible for a second reason:* the headless test map (`4c-rush` / "Sk-Rush") has
**29 features, all oil resources, and zero buildings**. 7c-Thales has **206**. Every house
test before this ran on a map with no houses.

Verified on Thales: houses 206 -> 118, **107 house scavengers spawned**, `sceneryIntel=1`,
0 script errors.

**Bomb trucks come in four grades.** One variant in a 136 HP ice van died on the run-in now
that its gun reaches only 40. `ScavBomberBody` is a dedicated 340 HP / armour 8 shell built by
the mod for this one job, so buffing it does not also buff every technical sharing the van
(the ice van stays at 136). Grades by phase: Bomb Truck, Bomb Bus, Bomb Tanker, Bomb Rig --
all detonate.

**Verified with the gate forced open** (nothing ever actually flew in a normal test --
scavenger helicopters arrive at 15 minutes and the scavengers were dead before then in
every long run, so the gate correctly stayed shut and the build path was never exercised):
Nexus 16/12/31 AA tanks per player, SemperFi 10/16/7, BoneCrusher 1/2/4, 0 errors.

That test caught a shipping bug: my BoneCrusher branch called `random(3)`, but BoneCrusher
is a separate codebase that uses `Math.random()` -- it calls `random()` zero times and
`Math.random()` nine times, where Nexus and SemperFi are the reverse. Left in, every
BoneCrusher game would have thrown ~7,000 `ReferenceError`s. Fixed and re-verified clean.

Cobra lists AA turrets natively and needs no patch, but its own detection never tripped,
so its AA production remains unobserved rather than confirmed.

### Release

Version bumped to **1.0.0**. `package_release.py` builds both game versions, refuses to
package a build with telemetry or a debug probe left in it, syntax-checks every shipped
script, and writes `dist/` with checksums. README, CHANGELOG and LICENCE added.

**The scavenger component is deliberately not packaged.** `uuscav2` shares only ~1.4% of its
content with the game's own `ultimateScavengers.js` -- it is a genuine third-party mod whose
licence and author are unknown, and DOCTRINE's version is ~64% derived from it. Options are in
`dist/README-DIST.md`.

## Debug commands (type in the in-game chat)

| command | effect |
|---|---|
| `doctrine ai` | show what each AI player has salvaged and their tier per family |
| `doctrine` | dump per-family tier progress, crates on the field, pity %, drop/recover/denied/decayed counters |
| `doctrine crate Cannon` | spawn a real test crate next to your first unit — tests the full pickup path (**cheat mode**: Shift+Backspace) |
| `doctrine unlock MG` | skip the crate, reveal that family's next topic directly (**cheat mode**) |

Families: `MG, Cannon, Rocket, Missile, Flamer, Mortar, Howitzer, Laser, Rail, AA, EMP`.

## What to verify in play

Already machine-verified in a headless 4.7.0 match: mod loads with zero uncaught
errors; the **full drop path** works end-to-end (armed unit → weapon family
resolved → crate spawned → picked up → `R-Wpn-MG-Range01` revealed); every
research topic renders a proper thumbnail (0 model-less, same as vanilla); tree
integrity holds (495 reachable, 46 signature topics hidden by design, no dangling
prerequisites); and no NEXUS Tank is built inside the 20-minute gate.

| # | Test | Expected |
|---|---|---|
| 1 | Open research early | Only starter topics visible — no Warhead/Gunnery topics until you salvage intel |
| 2 | Kill scavengers with your starting units | Occasional crate drops carrying that scav's weapon family |
| 3 | Reach Pythons, kill a scavenger | Drops become rare (~3%) but never zero |
| 3b | Play past 20 minutes vs Ultimate Scavengers | NEXUS Tanks start appearing — not before |
| 3c | Fight a scav bus/jeep with starting MGs | Dies far quicker than before, but its cannon hurts when it connects |
| 3d | Kite a scav cannon/rocket technical | It must **stop** to fire — keep moving and it can't shoot back |
| 3d2 | Kill freshly-built enemy units | **No** crates at all — they were green |
| 3d3 | Kill a decorated enemy veteran | Much better odds; watch for the drop message |
| 3e | Drive over a crate | It **disappears** immediately and the topic appears in your labs |
| 3f | Grab a crate an enemy dropped | You get the research, they lose it |
| 3g | Shell some neutral houses | Occasional (1.5%) intel crate at your own tech level |
| 3h | Destroy enemy units/buildings | Occasional (5%) oil drum to collect |
| 3k | Build a Heavy MG tank next to a light MG one | Clearly harder hitting now (37 vs 20 dps) |
| 3l | Compare a wall tower and a pillbox with the same gun | The tower engages noticeably sooner (+15% range) |
| 3n | Build labs | Only 1 at first; each research upgrade earns another, max 5 |
| 3m | Fight armoured units late game with cannons | Should hurt now, not bounce (62s vs Python, 22s vs its proper target) |
| 3i | Time a lab topic | Noticeably slower than vanilla; captured topics cost less power than bought ones |
| 3j | Type `doctrine ai` after ~20 min | AI players show salvaged topics and tier progress |
| 4 | Collect a crate | Console: "intel recovered", topic appears in lab |
| 5 | Let a crate sit 5 minutes | "intel decayed" — it vanishes |
| 6 | Let an enemy unit drive over your crate | "the enemy recovered our intel!" *(engine may not fire pickup for AI units — if you never see this, tell me and I'll switch denial to proximity-based)* |
| 7 | Research all four tier-1 topics of one family | Next crates for that family contain tier-2 topics |
| 8 | Get two families to tier 2 | Combined Arms Doctrine 2 appears; researching it opens first infrastructure topics |
| 9 | Save, quit, reload | Crates on the field, pity, revealed topics all survive |
| 10 | Feel: MG/cannon fire | Near-hitscan bullets (flightSpeed ×2 / ×1.5); Lancer vs tracks hits much harder; mortar vs hardpoints sieges properly |

## Notes

- Your `wz2100mp_long_range_fighting_v1_0.wz` was removed from `autoload\` (two
  total-conversion mods can't stack; copies remain in `mods\4.5.5\global\` and
  `mods\downloads\`).
- Don't play the **campaign** with doctrine.wz in `autoload\` — move it out first.
- AI opponents research their own trees and don't participate in salvage (v1 scope).
- Full stat diff vs vanilla: [build/REBALANCE-SUMMARY.md](build/REBALANCE-SUMMARY.md).
