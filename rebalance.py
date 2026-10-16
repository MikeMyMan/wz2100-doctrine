#!/usr/bin/env python3
"""
DOCTRINE — combat rebalance.

Emits modified copies of the vanilla stat files. Every change is a diff against
the shipped data, so nothing is lost and everything is reviewable.

Four goals, in order of leverage:
  1. Make counters PRONOUNCED — AT genuinely crushes tanks, AP crushes cyborgs,
     artillery genuinely sieges, and the generalist is genuinely mediocre.
  2. Make armour MATTER — the flat 33% minimumDamage floor currently guarantees
     every wrong-tool weapon lands a third of its damage regardless of armour.
  3. Stop salvo overkill — twin AT missiles currently launch 200ms apart while
     the first round needs 1330ms to arrive.
  4. Raise the air FLOOR without raising its ceiling — VTOLs are not weak, they
     are swingy. Make sorties survive to deliver, don't make the alpha bigger.
"""

import json, os, copy
from collections import defaultdict

WZ = os.environ.get("WZ_ROOT", "/tmp/wz2100")
SRC = f"{WZ}/data/mp/stats"
OUT = "/home/claude/wz-doctrine/out/stats"
os.makedirs(OUT, exist_ok=True)

WEAPON_TIME = 100          # stats.cpp:45 — JSON time values are ×100 to get ms
GAME_TICKS_PER_SEC = 1000  # gtime.h:37

changes = defaultdict(list)


def log(f, msg):
    changes[f].append(msg)


# ═════════════════════════════════════════════════════════════════════════════
# 1. WEAPON vs PROPULSION — make counters pronounced
# ═════════════════════════════════════════════════════════════════════════════
# The core failure: ALL ROUNDER (cannons, rails, Needle, Gauss, Particle Gun) sits
# at 105/115/120/125 vs Tracked/Half-track/Hover/Wheeled — i.e. ABOVE NEUTRAL
# against every ground propulsion except cyborgs. Meanwhile ANTI TANK gets only
# 120 vs Tracked. The specialist beats the generalist by 15%. That is not a
# counter, and it is exactly the complaint on the forums since 2014:
#   "Since cannons are also an all rounder weapon, they [are] effective against
#    structures, units and borgs, making a mix and match pointless."  — Amzo2000
#
# Fix: pull the generalist to neutral-or-below everywhere, and push each
# specialist hard into its own matchup.

WEAPON_MODIFIER = {
    #                    Half-Tracked  Hover  Legged  Lift  Propellor  Tracked  Wheeled
    "ALL ROUNDER":     {"Half-Tracked": 100, "Hover": 105, "Legged":  55, "Lift": 45,
                        "Propellor":  95, "Tracked":  90, "Wheeled": 110},
    "ANTI PERSONNEL":  {"Half-Tracked":  45, "Hover": 100, "Legged": 175, "Lift": 55,
                        "Propellor":  45, "Tracked":  35, "Wheeled":  95},
    "ANTI TANK":       {"Half-Tracked": 150, "Hover": 100, "Legged":  25, "Lift": 70,
                        "Propellor": 130, "Tracked": 175, "Wheeled": 145},
    "ARTILLERY ROUND": {"Half-Tracked":  70, "Hover": 110, "Legged": 140, "Lift": 20,
                        "Propellor":  65, "Tracked":  30, "Wheeled":  95},
    "BUNKER BUSTER":   {"Half-Tracked":  35, "Hover":  20, "Legged":  25, "Lift": 25,
                        "Propellor":  45, "Tracked":  45, "Wheeled":  30},
    "FLAMER":          {"Half-Tracked": 105, "Hover": 135, "Legged": 155, "Lift": 20,
                        "Propellor":  90, "Tracked":  70, "Wheeled": 120},
}

# ═════════════════════════════════════════════════════════════════════════════
# 2. WEAPON vs STRUCTURE — give artillery the siege role it is named for
# ═════════════════════════════════════════════════════════════════════════════
# Currently ARTILLERY ROUND is 100 vs HARD — and 96 of 165 structures are HARD.
# So artillery is exactly neutral against the thing it exists to destroy, and
# WORSE than neutral (20) against bunkers. Meanwhile ALL ROUNDER is also 100 vs
# HARD, so a cannon is as good a siege weapon as a howitzer.

STRUCTURE_MODIFIER = {
    "ALL ROUNDER":     {"BUNKER":  60, "HARD":  75, "MEDIUM":  95, "SOFT": 125},
    "ANTI PERSONNEL":  {"BUNKER":  30, "HARD":  25, "MEDIUM":  55, "SOFT": 160},
    "ANTI TANK":       {"BUNKER":  55, "HARD":  30, "MEDIUM":  60, "SOFT":  80},
    "ARTILLERY ROUND": {"BUNKER":  45, "HARD": 130, "MEDIUM": 165, "SOFT": 200},
    "BUNKER BUSTER":   {"BUNKER": 450, "HARD": 320, "MEDIUM": 130, "SOFT": 100},
    "FLAMER":          {"BUNKER": 320, "HARD":  15, "MEDIUM":  65, "SOFT": 155},
}

# ═════════════════════════════════════════════════════════════════════════════
# 3. minimumDamage — the highest-leverage single number in the game
# ═════════════════════════════════════════════════════════════════════════════
#   combat.cpp:650  final = MAX(modified - armour, modified * minimumDamage/100)
#
# All 119 designable MP weapons ship at 33. crab_ found what that means in 2013:
#   "machineguns are ignoring armor actually (do 33% dmg) ... After some point
#    (after first or second armor upgrade) all machineguns just doing minimum 33%
#    damage. That damage does not depend on armor. So Machinegun ignore armor."
# Per's reply: "In 3.2, you can mod the amount percentage of armour ignored, so
# you can experiment with that." Nobody in MP ever has.
#
# The floor does NOT flatten the modifier table — it flattens ARMOUR. Once
# armour >= 0.67 x modified damage, damage becomes armour-independent. So a low
# floor makes armour research bite; a high floor makes a weapon a penetrator.
# Setting it PER ROLE is what makes counters feel like counters.

MIN_DAMAGE_BY_EFFECT = {
    "ANTI PERSONNEL":  20,   # must be blunted by armour — but not to literal zero
    "ALL ROUNDER":     25,   # generalist: armour hurts it
    "ARTILLERY ROUND": 35,   # big shells care less about plate
    "FLAMER":          30,   # thermal channel
    "ANTI TANK":       45,   # a penetrator. reliably defeats armour
    "BUNKER BUSTER":   55,   # shaped charge
}

# ═════════════════════════════════════════════════════════════════════════════
# 4. SALVO TIMING — stop the second missile flying at a corpse
# ═════════════════════════════════════════════════════════════════════════════
# The engine does NOT treat a salvo as atomic. Each round is an independent
# combFire() decision, and `ammo` persists across target changes — it only
# refills once reloadTime has elapsed (combat.cpp:120-135). So an unspent round
# carries to the next target with ZERO waste. The anti-overkill behaviour is
# already in the architecture; it is suppressed purely because firePause is set
# to 1-2 (100-200ms) while the missile needs ~750-1350ms to arrive.
#
# Fix: set intra-salvo firePause >= flight time at a realistic engagement range,
# and trim reloadTime so sustained DPS against a target that SURVIVES is
# unchanged. Net effect: same damage into tough targets, no waste into dying ones.

SALVO_FIX = {
    # id                 firePause  reloadTime   rationale
    "Missile-A-T":       (14,  86),   # Scourge: 1327ms flight @ max range -> 1400ms
    "Rocket-HvyA-T":     ( 8, 172),   # Tank Killer: 0.75s flight
    "Rocket-LtA-T":      ( 7, 153),   # Lancer:      0.68s flight
}
# The cyborg AT weapons (Cyb-Hvywpn-A-T, Cyb-Wpn-Atmiss, Cyb-Hvywpn-TK,
# CyborgRocket) look like salvo weapons but are NOT: they have no `numRounds` and
# no `reloadTime`, so firePause (80-180 => 8-18 SECONDS) is their entire firing
# cycle. Rewriting firePause on those would turn an 8s cycle into 1.2s — a
# ~7x DPS buff by accident. Guarded below: SALVO_FIX only applies where
# numRounds > 1. Keep that guard if you extend this table.
# Deliberately NOT touched: Rocket-MRL (8 rounds), Rocket-Sunburst (6),
# Missile-HvySAM (4), Missile-LtSAM (2). These are saturation/AA weapons whose
# job IS to blanket a volume — spacing their rounds would break them.

# ═════════════════════════════════════════════════════════════════════════════
# 5. AIR — raise the floor, not the ceiling
# ═════════════════════════════════════════════════════════════════════════════
# The community verdict is NOT "VTOLs are weak" — it is "VTOLs are binary".
# Zepherian benchmarked it himself and retracted his own OP complaint:
#   "AA research is indeed in time with vtol ... The thing is it is a very binary
#    situation ... There is no mid ground ... AA as an afterthought will not work."
# crab_: "In current balance we cannot make VTOLs stronger because it will make
#         VTOLs overpowered in certain cases."
#
# So a straight damage buff is the WRONG move — it widens the swing that people
# already hate. Instead:
#   (a) VTOLs survive to deliver: V-Tol hitpointPctOfBody 100 -> 150. It is
#       currently identical to Wheels, while Tracks get 300.
#   (b) Fix the payload asymmetry: missile VTOLs get 2 shots per sortie while
#       VTOL Assault Gun gets 36. Raise attack runs on the starved ones only.
# Both raise the expected value of a sortie without raising its alpha strike.

VTOL_PROP_HP = 150          # was 100

VTOL_ATTACK_RUNS = {
    "Rocket-VTOL-LtA-T":   3,   # VTOL Lancer         was 1  (2 -> 6 shots)
    "Rocket-VTOL-HvyA-T":  2,   # VTOL Tank Killer    was 1  (2 -> 4 shots)
    "Missile-VTOL-AT":     2,   # VTOL Scourge        was 1  (2 -> 4 shots)
    "Rocket-VTOL-BB":      2,   # VTOL Bunker Buster  was 1  (2 -> 4 shots)
}

# AA cannot be separated from ground AT via the modifier table — "ANTI AIRCRAFT"
# and "ALL ROUNDER" are ALIASES for the same enum (stats.cpp:1669), and every
# dedicated AA weapon is tagged ANTI TANK. So AA tuning has to be per-weapon.
# Lowering ANTI TANK vs Lift (80 -> 70) helps VTOLs against BOTH dedicated AA and
# incidental ground fire; we hand the difference back to dedicated AA only, so
# AA remains the answer and stray ground fire does not.
AA_DAMAGE_SCALE = {
    "QuadMg1AAGun":   1.15,   # Hurricane
    "QuadRotAAGun":   1.15,   # Whirlwind
    "AAGun2Mk1":      1.20,   # Cyclone
    "AAGun2Mk1Quad":  1.20,   # Tornado
    "Rocket-Sunburst": 1.15,
    "Missile-LtSAM":  1.10,   # Avenger
    "Missile-HvySAM": 1.10,   # Vindicator
    "AAGunLaser":     1.10,   # Stormbringer
}


# ═════════════════════════════════════════════════════════════════════════════
def main():
    # ── modifier tables ──────────────────────────────────────────────────────
    for name, table in (("weaponmodifier", WEAPON_MODIFIER),
                        ("structuremodifier", STRUCTURE_MODIFIER)):
        old = json.load(open(f"{SRC}/{name}.json"))
        # VERSION SAFETY: emit only keys the target build actually knows about.
        # stats.cpp loadWeaponModifiers() does `debug(LOG_FATAL, "Invalid Propulsion
        # type - %s"); return false;` on an unknown key — so shipping "Propellor"
        # (naval, added after 4.5.x) to a 4.5.5 install is a HARD FAILURE, not a
        # warning. Intersecting with the source file makes this version-agnostic.
        known = set()
        for row in old.values():
            known |= set(row)
        out = {}
        for eff, row in table.items():
            if eff not in old:
                log(name, f"SKIP effect '{eff}' — not present in this build")
                continue
            out[eff] = {}
            for key, new in row.items():
                if key not in known:
                    log(name, f"SKIP {eff} vs {key} — key absent in this build")
                    continue
                out[eff][key] = new
                o = old.get(eff, {}).get(key)
                if o is not None and o != new:
                    log(name, f"{eff:16s} vs {key:13s} {o:4d} -> {new:4d}")
        json.dump(out, open(f"{OUT}/{name}.json", "w"), indent="\t")

    # ── weapons ──────────────────────────────────────────────────────────────
    weapons = json.load(open(f"{SRC}/weapons.json"))
    new = copy.deepcopy(weapons)

    for wid, w in new.items():
        eff = w.get("weaponEffect")

        # minimumDamage by role
        if eff in MIN_DAMAGE_BY_EFFECT:
            o = w.get("minimumDamage", 33)
            n = MIN_DAMAGE_BY_EFFECT[eff]
            if o != n:
                w["minimumDamage"] = n

        # salvo spacing — ONLY for true multi-round weapons (see note above)
        if wid in SALVO_FIX and w.get("numRounds", 1) > 1:
            fp, rl = SALVO_FIX[wid]
            ofp, orl = w.get("firePause"), w.get("reloadTime")
            flight_ms = int(1000 * w["longRange"] / w["flightSpeed"])
            w["firePause"], w["reloadTime"] = fp, rl
            log("weapons",
                f"{wid:20s} SALVO firePause {ofp}->{fp} ({ofp*WEAPON_TIME}ms->{fp*WEAPON_TIME}ms; "
                f"flight {flight_ms}ms), reload {orl}->{rl}")

        # air payload
        if wid in VTOL_ATTACK_RUNS:
            o = w.get("vtolAttackRuns", 1)
            w["vtolAttackRuns"] = VTOL_ATTACK_RUNS[wid]
            rounds = w.get("numRounds", 1)
            log("weapons", f"{wid:20s} AIR attackRuns {o}->{w['vtolAttackRuns']} "
                           f"({o*rounds}->{w['vtolAttackRuns']*rounds} shots/sortie)")

        # AA compensation
        if wid in AA_DAMAGE_SCALE:
            o = w["damage"]
            w["damage"] = int(round(o * AA_DAMAGE_SCALE[wid]))
            log("weapons", f"{wid:20s} AA damage {o}->{w['damage']}")

    md = defaultdict(int)
    for wid, w in new.items():
        if w.get("minimumDamage") != weapons[wid].get("minimumDamage", 33):
            md[(w.get("weaponEffect"), w["minimumDamage"])] += 1
    for (eff, v), n in sorted(md.items()):
        log("weapons", f"minimumDamage 33 -> {v:2d} on {n:3d} {eff} weapons")

    json.dump(new, open(f"{OUT}/weapons.json", "w"), indent="\t", sort_keys=True)

    # ── propulsion ───────────────────────────────────────────────────────────
    prop = json.load(open(f"{SRC}/propulsion.json"))
    for pid in ("V-Tol", "Helicopter"):
        if pid in prop:
            o = prop[pid].get("hitpointPctOfBody")
            prop[pid]["hitpointPctOfBody"] = VTOL_PROP_HP
            log("propulsion", f"{pid:12s} hitpointPctOfBody {o} -> {VTOL_PROP_HP} "
                             f"(was identical to Wheels; Tracks get 300)")
    json.dump(prop, open(f"{OUT}/propulsion.json", "w"), indent="\t", sort_keys=True)

    # ── report ───────────────────────────────────────────────────────────────
    for f in ("weaponmodifier", "structuremodifier", "weapons", "propulsion"):
        print(f"\n── {f}.json ──  {len(changes[f])} changes")
        for c in changes[f]:
            print("   ", c)

    # ── the money table: does AT actually punish tanks now? ──────────────────
    print("\n\n═══ COUNTER SHARPNESS: specialist vs generalist, same target ═══")
    old_wm = json.load(open(f"{SRC}/weaponmodifier.json"))
    for target in ("Tracked", "Legged", "Lift", "Wheeled"):
        print(f"\n  vs {target}")
        for eff in ("ANTI TANK", "ANTI PERSONNEL", "ARTILLERY ROUND", "ALL ROUNDER"):
            o = old_wm[eff][target]
            n = WEAPON_MODIFIER[eff][target]
            ov = o / old_wm["ALL ROUNDER"][target]
            nv = n / WEAPON_MODIFIER["ALL ROUNDER"][target]
            print(f"    {eff:16s} {o:4d} -> {n:4d}   "
                  f"ratio vs generalist {ov:5.2f}x -> {nv:5.2f}x")


if __name__ == "__main__":
    main()
