# DOCTRINE — how to play it

If you know Warzone 2100, the first three minutes will feel completely normal. Build trucks,
take oil, put up a lab, research the opening machinegun. The change arrives with your first
kill.

---

## 1. The loop

Research is no longer a shopping list. It is salvage.

```
   you kill something  ──▶  it may drop an INTEL CRATE  ──▶  you drive over the crate
            ▲                                                          │
            │                                                          ▼
   new hardware changes      ◀──  the topic it carried  ◀──  that topic unlocks in your lab
   how you fight next
```

**Be precise about what this changes.** You still unlock *weapons* in the lab, the normal
way — 56 of the 57 weapon-unlock topics are ordinary researchable topics, so machineguns,
cannons, rockets and the rest are bought with research points as always.

What you can no longer buy are the **improvements**. Every weapon family's Damage, Range,
Reload and Accuracy upgrades — 206 topics, four axes across four tiers — are hidden from the
lab entirely and arrive *only* in intel crates. Of the 601 topics in the tree, 303 are
normally researchable and 298 are gated this way.

So the lab still answers "what can I build?" Only the field answers "how good is it?"

## 2. Intel crates

**What drops one.** Killing an enemy unit. Not every kill — the chance is driven by the
victim's **veterancy**, and a green unit gives you nothing whatsoever:

| victim's experience | chance of a crate |
|---|---|
| 0 (fresh from the factory) | **0% — never** |
| 2 | 1.3% |
| 4 | 3.2% |
| 8 | 7.9% |
| 11 or more (fully blooded) | **12%** |

Those figures are for a victim of roughly your own unit cost. Two things then modify them:

- **Relative worth.** Something far beneath your current hardware teaches you nothing either,
  and scales the chance down. Crushing scouts with a late-game army is not research.
- **Your killer's own veterancy**, worth up to +60% once that unit has 24 kills.

A hidden pity counter rises on every miss so a bad run cannot stall you, and the whole thing
is capped at 90%. Your own losses drop nothing, and neither does shooting your own buildings.

Your own losses drop nothing. Nor does shooting up your own buildings.

**What it contains.** An **upgrade for the weapon the victim was actually carrying** — read
off its equipped turrets, not guessed. Kill a Lancer unit and you get rocket/anti-tank
improvements; kill a machinegun Viper and you get machinegun improvements. Eleven families
can appear: MG, Cannon, Rocket, Missile, Flamer, Mortar, Howitzer, Laser, Rail, AA, EMP. A
unit carrying two different turret types can yield either.

The crate always contains one of the four axes — **Damage, Range, Reload or Accuracy** — at
your current tier in that family. Which one is decided **when you pick it up**, not when it
drops, so it is always something you still need rather than a duplicate.

This is the strategic core of the mod: **the enemy's arsenal decides which of your weapons
can improve.** Fight nothing but cyborgs and your anti-tank line never gets better. If you
want rocket upgrades, you have to go and kill veteran rocket units.

**Getting it.** Drive any unit over it. Crates are **visible to everyone** and sit on the
field for **five minutes** before decaying. This is the single most important consequence of
the whole design: *the technology is lying on contested ground.* An enemy who reaches your
crate first takes the research instead of you, and you will be told when it happens.

**If you are losing badly**, a hidden pity counter raises your drop chance until something
lands, so a bad run does not become a death spiral.

## 3. Depth and breadth

Each weapon family has **four tiers**, and each tier has **four upgrade axes** — Damage,
Range, Reload, Accuracy.

- **Depth:** crates in a family give you tier 1. Research all four axes of tier 1 and the
  next crate in that family starts offering tier 2. A family you commit to gets deep.
- **Breadth:** reaching tier 2 in **two** different families earns *Combined Arms Doctrine 2*.
  Three families earns Doctrine 3, and so on to five. These credentials are what open the
  **economic and structural** tree — power, factories, modules, defences.

So a one-trick army stalls. You can have the best rockets on the map and still be unable to
build a power upgrade, because you never learned anything else.

## 4. Research is slower, and upgrades are fewer and bigger

Labs run at **40% of vanilla speed**, and bought topics cost substantially more power.
Captured topics — the ones crates give you — are both faster and cheaper. Salvage is the
efficient path; buying is the fallback.

Damage ladders are **four rungs instead of ten**, totalling **+223%** against vanilla's +250%.
You reach about 90% of vanilla's ceiling for roughly a quarter of the research. Each step is
a real jump rather than a rounding error.

You start with **two research labs** and earn one more per research upgrade, to a maximum of
five.

## 5. The matchups — the most important tables in the mod

Vanilla never touched these, so a Lancer at minute 60 beat a tank by exactly the same ratio
as at minute 5. DOCTRINE moves them, which means **picking the right weapon matters more than
having the bigger number.**

### Against units (% damage dealt)

| your weapon | Wheels | Half-track | **Tracks** | Hover | **Cyborgs** | VTOL |
|---|---|---|---|---|---|---|
| **Machinegun** | 95 | 45 | **35** | 100 | **190** | 55 |
| **Anti-tank** (Lancer, TK, missiles) | 130 | 135 | **150** | 100 | **25** | 70 |
| **Artillery** (mortar, howitzer) | 95 | 70 | **30** | 110 | **165** | 20 |
| **Flamer** | 120 | 105 | 70 | 135 | **155** | 20 |
| **Cannon** | 110 | 100 | 90 | 105 | 55 | 45 |

Read the two extremes: **machineguns shred cyborgs and bounce off tracks. Anti-tank is the
exact mirror.** Artillery hits infantry hard but cannot meaningfully hurt a moving tank.
Cannon is the generalist that is never the best answer to anything.

### Against buildings (% damage dealt)

| your weapon | Soft | Medium *(derricks, factories, labs)* | Hard *(walls, hardpoints, HQ)* | Bunkers *(pillboxes)* |
|---|---|---|---|---|
| **Machinegun** | 110 | 45 | 25 | 30 |
| **Cannon** | 125 | 95 | 75 | 60 |
| **Anti-tank** | 80 | 60 | 30 | 55 |
| **Artillery** | **200** | **165** | **130** | 45 |
| **Flamer** | 155 | 65 | 15 | **320** |
| **Bunker buster** | 100 | 130 | **320** | **450** |

- **Artillery is the siege arm.** Mortars and howitzers are the general answer to bases,
  derricks and hardpoints.
- **Pillboxes are the artillery-proof answer** at 45%. The counter to *them* is a bunker
  buster (450%) or a flamer (320%).
- **Flamers are all-or-nothing** — devastating against bunkers, useless against hardcrete.
- **Machineguns cannot demolish.** They were deliberately taken off that job, so you cannot
  chew through a generator with massed MG.

### One thing worth understanding

Armour is subtracted **after** the modifier above. A low-damage weapon firing into the wrong
matchup lands on its minimum-damage floor and does almost nothing — a few points a shot. This
is why a wrong-weapon attack does not merely underperform, it fails outright.

## 6. Cyborgs

Cheap, quick to build, faster across the map — and genuinely fragile. They melt to
machineguns and mortars and shrug off anti-tank fire. Their weapons do only 45–60% to
buildings, so a cyborg swarm cannot flatten a base; it is an anti-unit force that takes
ground and kills crews.

If someone is pushing cyborgs at you, the answer is machineguns, and you already have them.

## 7. Scavengers are a faction now

**This section needs the optional scavenger component.** It patches *Ultimate Ultimate
Scavengers 2* — install that mod, then run `scav/patch_uuscav2.py` from this download. House
scavengers (the last item below) work without it; everything else in this section does not.

With it, expect a real third party rather than scenery:

- They **fortify their own territory** — bunkers, gun towers, mortar pits and rocket pits
  around their derricks, factories and generators, four emplacements per site.
- They field **infantry in squads of three**, continuously.
- **Suicide bomb trucks** in four grades — Truck, Bus, Tanker, Rig. Their gun reaches almost
  nothing, so they must drive right up to you, and then they detonate. Kill them at distance.
- **Helicopters** from about fifteen minutes, capped so the late game stays a ground war.
- They **research alongside everyone else**, so they do not stay a minute-one threat.
- **Flatten an occupied house and 1–5 armed scavengers come out of the rubble.** Roughly 40%
  of buildings are occupied. Demolishing a town is not free.

## 8. Other things on the map

- **Destroyed scenery** occasionally (1.5%) yields an intel crate at your own tech level.
- **Destroyed units and buildings** occasionally (5%) leave an **oil drum** to collect.
- Scavenger kills can still drop intel, at a flat low rate — but scavenger *infantry* drop
  nothing, or the sheer volume of bodies would become the main source of research.

## 9. Practical advice

1. **Collect your crates.** They are lying in the open for anyone. Ignoring one is declining
   your own research.
2. **Hunt veterans.** A decorated enemy unit is worth more to you dead than three fresh ones.
3. **Do not tunnel into one family.** You need breadth to unlock your economy.
4. **Scout what your opponent fields before committing a factory.** Tracks, cyborgs and
   hardpoints each want a different answer, and the wrong answer does almost nothing now.
5. **Expect the early game to feel thin.** Two labs, slow research, few options. It opens up
   the moment you start winning fights.

## 10. Chat commands

Type these into the in-game chat:

| command | |
|---|---|
| `doctrine` | your progress, crates on the field, counters |
| `doctrine ai` | what each AI player has salvaged |
| `doctrine crate <Family>` | spawn a crate beside you — **needs cheat mode** |
| `doctrine unlock <Family>` | reveal that family's next topic — **needs cheat mode** |

Cheat mode is Shift+Backspace.

## 11. What to expect from the AI

All seven bundled AIs — Nexus, SemperFi, Cobra, BoneCrusher, NullBot, Hover and Turtle — play
by these rules. They run the same research engine, they each commit to a weapon family that
matches their own personality, and **they collect crates on the field exactly as you do**. A
crate you leave in no-man's-land is one an AI may well come and take.

They will also build anti-air once something of yours is flying, so VTOLs are not a free win.
