#!/usr/bin/env python3
"""Validate the generated tree against what the engine will actually accept."""
import json, os, sys
from collections import defaultdict

WZ = os.environ.get("WZ_ROOT", "/tmp/wz2100")
D = json.load(open("/home/claude/wz-doctrine/out/research-doctrine.json"))
VAN = json.load(open(f"{WZ}/data/mp/stats/research.json"))
WEAPONS = json.load(open(f"{WZ}/data/mp/stats/weapons.json"))
BODIES = json.load(open(f"{WZ}/data/mp/stats/body.json"))
STRUCTS = json.load(open(f"{WZ}/data/mp/stats/structure.json"))

# Engine-supported (class -> parameters), read from src/wzapi.cpp getUpgradesObject()
SUPPORTED = {
    "Body": {"HitPoints", "HitPointPct", "Power", "Armour", "Thermal", "Resistance"},
    "Sensor": {"HitPoints", "HitPointPct", "Range"},
    "Propulsion": {"HitPoints", "HitPointPct", "HitPointPctOfBody"},
    "ECM": {"Range", "HitPoints", "HitPointPct"},
    "Repair": {"RepairPoints", "HitPoints", "HitPointPct"},
    "Construct": {"ConstructorPoints", "HitPoints", "HitPointPct"},
    "Brain": {"BaseCommandLimit", "CommandLimitByLevel", "RankThresholds", "HitPoints", "HitPointPct"},
    "Weapon": {"MaxRange", "ShortRange", "MinRange", "HitChance", "ShortHitChance", "FirePause",
               "ReloadTime", "Rounds", "Radius", "Damage", "MinimumDamage", "RadiusDamage",
               "RepeatDamage", "RepeatTime", "RepeatRadius", "HitPoints", "HitPointPct", "EmpRadius"},
    "Building": {"ResearchPoints", "ModuleResearchPoints", "RepairPoints", "PowerPoints",
                 "ModulePowerPoints", "ProductionPoints", "ModuleProductionPoints", "RearmPoints",
                 "Armour", "Resistance", "Thermal", "HitPoints", "Limit"},
}
# Fields present in the Stats object -> legal as filterParameter.
# register_common() puts these on EVERY component.
COMMON_FILTERS = {"Id", "Weight", "BuildPower", "BuildTime", "HitPoints", "HitPointPct"}
WEAPON_FILTERS = COMMON_FILTERS | {"ImpactClass", "Effect", "ImpactType", "MaxRange", "MinRange",
                                   "Damage", "RadiusDamage", "FirePause", "ReloadTime", "Rounds",
                                   "Radius", "MinimumDamage", "Penetrate", "HitChance", "Recoil",
                                   "FlightSpeed", "Rotate", "MaxElevation", "MinElevation",
                                   "ShootInAir", "ShootOnGround", "EmpRadius", "RepeatDamage",
                                   "RepeatRadius", "RepeatTime", "RepeatClass", "RepeatType",
                                   "ShortHitChance", "ShortRange", "FireOnMove", "NoFriendlyFire"}
BODY_FILTERS = COMMON_FILTERS | {"Power", "Armour", "Thermal", "Resistance", "Size",
                                 "WeaponSlots", "BodyClass"}

VALID_SUBCLASS = {w.get("weaponSubClass") for w in WEAPONS.values()}
VALID_WEAPON_IDS = set(WEAPONS)
VALID_BODY_SIZES = {b.get("size") for b in BODIES.values()}
VALID_STRUCT_IDS = set(STRUCTS)

errors, warns, notes = [], [], []

# ── 1. Prerequisites resolve ────────────────────────────────────────────────
known = set(D) | set(VAN)
external = defaultdict(list)
for tid, t in D.items():
    for r in t.get("requiredResearch", []):
        if r not in known:
            errors.append(f"{tid}: dangling prerequisite '{r}'")
        elif r not in D:
            external[r].append(tid)

# ── 2. Acyclic ──────────────────────────────────────────────────────────────
colour = {}
def visit(n, stack):
    if colour.get(n) == 2:
        return
    if colour.get(n) == 1:
        errors.append(f"CYCLE: {' -> '.join(stack + [n])}")
        return
    colour[n] = 1
    for r in D.get(n, {}).get("requiredResearch", []):
        if r in D:
            visit(r, stack + [n])
    colour[n] = 2
for tid in D:
    visit(tid, [])

# ── 3. Results are engine-legal ─────────────────────────────────────────────
for tid, t in D.items():
    for i, r in enumerate(t.get("results", [])):
        cls, par = r.get("class"), r.get("parameter")
        if cls not in SUPPORTED:
            errors.append(f"{tid}.results[{i}]: unknown class '{cls}'")
            continue
        if par not in SUPPORTED[cls]:
            errors.append(f"{tid}.results[{i}]: '{par}' is not upgradeable on {cls}")
        fp, fv = r.get("filterParameter"), r.get("filterValue")
        if fp is None:
            if fv is not None:
                errors.append(f"{tid}.results[{i}]: filterValue without filterParameter")
            continue
        if fv is None:
            errors.append(f"{tid}.results[{i}]: filterParameter without filterValue")
        legal = {"Weapon": WEAPON_FILTERS, "Body": BODY_FILTERS}.get(cls, COMMON_FILTERS)
        if fp not in legal:
            errors.append(f"{tid}.results[{i}]: '{fp}' not a Stats field on {cls}")
        # filterValue must actually match something
        if cls == "Weapon" and fp == "ImpactClass" and fv not in VALID_SUBCLASS:
            errors.append(f"{tid}: no weapon has subclass '{fv}'")
        if cls == "Weapon" and fp == "Id" and fv not in VALID_WEAPON_IDS:
            errors.append(f"{tid}: no weapon with Id '{fv}'")
        if cls == "Body" and fp == "Size" and fv not in VALID_BODY_SIZES:
            errors.append(f"{tid}: no body with Size '{fv}'")
        if cls == "Building" and fp == "Id" and fv not in VALID_STRUCT_IDS:
            errors.append(f"{tid}: no structure with Id '{fv}'")

# ── 4. Required schema fields ───────────────────────────────────────────────
for tid, t in D.items():
    for k in ("id", "name", "researchPoints", "iconID"):
        if k not in t:
            errors.append(f"{tid}: missing required field '{k}'")
    if t.get("id") != tid:
        errors.append(f"{tid}: id field mismatch ({t.get('id')})")
    if t.get("researchPower", 0) > 450:
        warns.append(f"{tid}: researchPower {t['researchPower']} exceeds the 450 "
                     f"ceiling every vanilla topic respects")
    for c in t.get("resultComponents", []):
        if c not in VALID_WEAPON_IDS and c != "CommandBrain01":
            notes.append(f"{tid}: resultComponent '{c}' not a weapon (check it exists)")
    for s in t.get("resultStructures", []):
        if s not in VALID_STRUCT_IDS:
            errors.append(f"{tid}: resultStructure '{s}' does not exist")

# ── 5. Reachability from the roots ──────────────────────────────────────────
roots = {t["id"] for t in D.values() if not t.get("requiredResearch")}
reach, frontier = set(roots), list(roots)
depends = defaultdict(list)
for tid, t in D.items():
    for r in t.get("requiredResearch", []):
        depends[r].append(tid)
# treat external (vanilla) prereqs as satisfiable
satisfied = set(external) | set(VAN)
changed = True
while changed:
    changed = False
    for tid, t in D.items():
        if tid in reach:
            continue
        if all(r in reach or r in satisfied for r in t.get("requiredResearch", [])):
            reach.add(tid); changed = True
unreachable = set(D) - reach

# ── report ──────────────────────────────────────────────────────────────────
print(f"topics: {len(D)}")
print(f"roots (no prerequisite): {len(roots)}  {sorted(roots)[:6]}")
print(f"external prerequisites (must exist in the vanilla tree you merge into): {len(external)}")
for r, users in sorted(external.items()):
    ok = "OK — present in vanilla" if r in VAN else "MISSING FROM VANILLA"
    print(f"    {r:34s} <- {len(users):3d} topics   [{ok}]")
print(f"unreachable topics: {len(unreachable)} {sorted(unreachable)[:5]}")
print()
print(f"ERRORS: {len(errors)}")
for e in errors[:40]:
    print("   ✗", e)
print(f"WARNINGS: {len(warns)}")
for w in warns[:20]:
    print("   !", w)
print(f"NOTES: {len(notes)}")
for n in notes[:10]:
    print("   ·", n)
sys.exit(1 if errors else 0)
