#!/usr/bin/env python3
"""
DOCTRINE — kill valuation.

"Higher tech units should help unlock faster if killed than lower tech units,
 and if they are really low they should do 0."

WHY THIS NEEDS A KILL LEDGER (a correction to DOCTRINE.md §3.1)
──────────────────────────────────────────────────────────────
§3.1 said: don't track anything, just read `commander.experience`. That was right
for an unweighted design and it is WRONG for this one, for two reasons:

 1. The engine has already flattened the information. By the time XP lands on the
    commander it is a scalar — there is no way to ask "what did that come from?"

 2. The engine has already applied its OWN weighting, and it is clamped in exactly
    the place we care about. `qualityFactor()` (projectile.cpp:301) scales XP by
    victim-vs-attacker cost and build points... then does:

        CLIP(powerRatio,  65536/2, 65536*2);
        CLIP(pointsRatio, 65536/2, 65536*2);

    A **0.5 floor**. Killing a scavenger trike with a Gauss tank still pays half.
    "Really low should do 0" is precisely what that clamp forbids, and it is C++,
    so a data mod cannot lift it.

So knowledge must be computed from a script-side ledger instead. `eventDestroyed`
does not name the killer, so the standard workaround applies: `eventAttacked`
maintains a last-hitter map, and the kill is credited on destroy.

Consequence worth stating plainly: `commander.experience` STOPS being the knowledge
source and goes back to being purely the rank mechanic (group size, combat bonuses,
which still matter a lot). The commander remains the accumulator and the courier —
unbanked knowledge rides with it and is lost/recovered on death exactly as designed.
Only the meter changes.

VALUE METRIC
────────────
`droid.cost` is exposed to JS (quickjs_backend.cpp:1514 -> calcDroidPower), and sums
the actual component build costs. No new plumbing, no guessing at "tech level":
a Dragon/Gauss/Tracks costs 602 and a scav trike costs 38, and that ratio IS the
tech gap.

THE REFERENCE
─────────────
Weight is RELATIVE to your own army, so it self-scales: the Viper that was a fair
fight at minute 5 is worth nothing at minute 40 without retuning anything.

Reference = the 75th percentile cost of your own active combat droids.
NOT the mean (fielding a screen of cheap junk would drag the bar down and inflate
everything you kill), and NOT the attacker's own cost (that rewards sniping with
the cheapest possible unit). p75 can only be lowered by actually giving up your
good units, which is not an exploit — it is a sacrifice.
"""

import json, os

CURVE = {
    "zero_below":  0.40,   # r < 0.40  -> 0. Nothing to learn from a target this far beneath you.
    "parity":      1.00,   # r = 1.00  -> 1.0
    "cap_at":      2.50,   # r >= 2.50 -> max
    "cap_weight":  2.50,
}


def weight(r):
    z, p, c, cw = (CURVE[k] for k in ("zero_below", "parity", "cap_at", "cap_weight"))
    if r < z:
        return 0.0
    if r < p:
        return (r - z) / (p - z)            # ramp 0 -> 1
    if r < c:
        return 1 + (cw - 1) * (r - p) / (c - p)   # ramp 1 -> cap
    return cw


def load_costs(wz):
    B = json.load(open(f"{wz}/data/mp/stats/body.json"))
    P = json.load(open(f"{wz}/data/mp/stats/propulsion.json"))
    W = json.load(open(f"{wz}/data/mp/stats/weapons.json"))

    def cost(b, p, w):
        # mirrors calcPower(): body + propulsion (a percentage of body) + turret
        bpow = B[b].get("buildPower", 0)
        return bpow + bpow * P[p].get("buildPower", 0) // 100 + W[w].get("buildPower", 0)

    return cost


REFERENCE_FLEET = [
    ("Scavenger trike",      "Body4ABT",  "wheeled01", "BaBaMG"),
    ("Viper MG wheels",      "Body1REC",  "wheeled01", "MG1Mk1"),
    ("Viper MG half-track",  "Body1REC",  "HalfTrack", "MG1Mk1"),
    ("Cobra Light Cannon",   "Body5REC",  "HalfTrack", "Cannon1Mk1"),
    ("Cobra Lancer",         "Body5REC",  "HalfTrack", "Rocket-LtA-T"),
    ("Python Medium Cannon", "Body11ABT", "tracked01", "Cannon2A-TMk1"),
    ("Python Tank Killer",   "Body11ABT", "tracked01", "Rocket-HvyA-T"),
    ("Tiger Heavy Cannon",   "Body9REC",  "tracked01", "Cannon375mmMk1"),
    ("Vengeance Scourge",    "Body10MBT", "tracked01", "Missile-A-T"),
    ("Dragon Gauss",         "Body14SUP", "tracked01", "RailGun3Mk1"),
]


def main():
    wz = os.environ.get("WZ_ROOT", "/tmp/wz2100")
    cost = load_costs(wz)
    fleet = [(n, cost(b, p, w)) for n, b, p, w in REFERENCE_FLEET]

    # three reference points across a game's arc
    refs = [("early — Viper MG", dict(fleet)["Viper MG half-track"]),
            ("mid — Python Med Cannon", dict(fleet)["Python Medium Cannon"]),
            ("late — Vengeance Scourge", dict(fleet)["Vengeance Scourge"])]

    print("Unit costs (calcDroidPower — what droid.cost returns):\n")
    for n, c in fleet:
        print(f"   {n:24s} {c:5d}")

    table = {}
    for label, ref in refs:
        print(f"\n\nReference p75 = {ref}  ({label})")
        print(f"   {'target':24s} {'cost':>5s} {'ratio':>6s} {'weight':>7s}")
        rows = []
        for n, c in fleet:
            r = c / ref
            w = weight(r)
            bar = "·" * int(round(w * 12))
            print(f"   {n:24s} {c:5d} {r:6.2f} {w:7.2f}  {bar}")
            rows.append({"name": n, "cost": c, "ratio": round(r, 3), "weight": round(w, 3)})
        table[label] = {"ref": ref, "rows": rows}

    curve = [{"r": round(x / 100, 2), "w": round(weight(x / 100), 4)} for x in range(0, 301, 4)]
    out = {"curve": CURVE, "samples": curve, "fleet": fleet, "table": table}
    os.makedirs("/home/claude/wz-doctrine/out", exist_ok=True)
    json.dump(out, open("/home/claude/wz-doctrine/out/killvalue.json", "w"), indent=1)
    print("\n\nwrote out/killvalue.json")


if __name__ == "__main__":
    main()
