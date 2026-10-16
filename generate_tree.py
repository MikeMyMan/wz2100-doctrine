#!/usr/bin/env python3
"""
DOCTRINE — a generated tech tree for Warzone 2100.

The vanilla tree is 390 hand-authored topics. That is precisely why it cannot be
rebalanced: moving one node revalues everything up- and downstream, by hand.

This tree is a FUNCTION of about twenty numbers. Retuning the whole progression
means editing the CONFIG block, not 390 JSON objects.

The ratchet:
    Combat UNLOCKS a topic. Power RESEARCHES it. Neither alone advances you.
    Each weapon family has four axes (Damage / Range / Reload / Accuracy) and four
    tiers. Fighting reveals one random eligible (axis, tier) at a time; a tier only
    becomes eligible once EVERY axis of the tier below it has been researched.
    So combat gives breadth, research gives depth, and running away with the game
    on either one alone is structurally impossible.

Every emitted entry uses only engine-supported classes, parameters and filters,
verified against src/research.cpp and src/wzapi.cpp (getUpgradesObject).
"""

import json, sys, math, os
from collections import defaultdict, OrderedDict

WZ = os.environ.get("WZ_ROOT", "/tmp/wz2100")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — the entire progression curve lives here
# ─────────────────────────────────────────────────────────────────────────────

CONFIG = {
    # Because the engine applies upgrades ADDITIVELY ON THE BASE VALUE (never
    # compounding), a constant `value` means a shrinking relative gain. We solve
    # for values that hold the RELATIVE gain constant per tier:
    #     value_n = 100 * g * (1+g)^(n-1)
    "field_gain":     0.12,   # crew skill: +12% relative per tier
    "field_tiers":    3,
    "doctrine_gain":  0.25,   # materiel: +25% relative per tier
    "doctrine_tiers": 4,
    "reach_gain":     0.08,   # range: geometric in effect, keep it tight
    "reach_tiers":    3,

    # Field knowledge required to unlock each field tier, per family.
    # STEEPLY diminishing: the Nth improvement to a component you have already
    # mastered costs far more than the 1st improvement to something you have
    # never fielded. This is the anti-flatline mechanic AND the anti-deathball
    # mechanic: when a line stops paying, a fresh line is the efficient move.
    "knowledge_base":    800,
    "knowledge_growth": 2.1,

    # Research cost of the topics themselves.
    "field_pts":     [200, 500, 1100],
    "field_pow":     [10, 25, 50],
    "signature_pts": 900,
    "signature_pow": 45,
    "ratchet_pts":   [900, 2400, 5200, 10000],
    "ratchet_pow":   [30, 85, 190, 360],
}


def escalating(gain, tiers):
    """Values that hold the relative gain constant under additive-on-base math."""
    return [max(1, round(100 * gain * (1 + gain) ** (n - 1))) for n in range(1, tiers + 1)]


def knowledge_curve(tiers):
    b, g = CONFIG["knowledge_base"], CONFIG["knowledge_growth"]
    return [int(round(b * g ** n)) for n in range(tiers)]


# ─────────────────────────────────────────────────────────────────────────────
# FAMILIES — the field-research grouping axis
# ─────────────────────────────────────────────────────────────────────────────
# `subclass` is the engine's weaponSubClass, used as filterValue with
# filterParameter "ImpactClass" (the vanilla pattern).

FAMILIES = OrderedDict([
    ("MG",       dict(subclass="MACHINE GUN", label="Machinegun",  icon="IMAGE_RES_WEAPONTECH", at=False)),
    ("Cannon",   dict(subclass="CANNON",      label="Cannon",      icon="IMAGE_RES_WEAPONTECH", at=True)),
    ("Rocket",   dict(subclass="ROCKET",      label="Rocket",      icon="IMAGE_RES_WEAPONTECH", at=True)),
    ("Missile",  dict(subclass="MISSILE",     label="Missile",     icon="IMAGE_RES_WEAPONTECH", at=True)),
    ("Flamer",   dict(subclass="FLAME",       label="Flamer",      icon="IMAGE_RES_WEAPONTECH", at=False)),
    ("Mortar",   dict(subclass="MORTARS",     label="Mortar",      icon="IMAGE_RES_WEAPONTECH", at=False)),
    ("Howitzer", dict(subclass="HOWITZERS",   label="Howitzer",    icon="IMAGE_RES_WEAPONTECH", at=False)),
    ("Laser",    dict(subclass="ENERGY",      label="Energy",      icon="IMAGE_RES_WEAPONTECH", at=True)),
    ("Rail",     dict(subclass="GAUSS",       label="Rail",        icon="IMAGE_RES_WEAPONTECH", at=True)),
    ("AA",       dict(subclass="A-A GUN",     label="AA Gun",      icon="IMAGE_RES_WEAPONTECH", at=False)),
    ("EMP",      dict(subclass="EMP",         label="EMP",         icon="IMAGE_RES_WEAPONTECH", at=False)),
])

# ─────────────────────────────────────────────────────────────────────────────
# THE RATCHET
# ─────────────────────────────────────────────────────────────────────────────
# Each weapon family improves along FOUR axes. Combat reveals ONE (axis, tier) at
# a time, chosen at random from those currently eligible. A tier only becomes
# eligible once EVERY axis of the previous tier has been RESEARCHED — not merely
# unlocked.
#
#   fight ──▶ Range I unlocked ──▶ (pay for it, or don't)
#   fight ──▶ Damage I unlocked ──▶ ...
#   ... all four tier-I topics RESEARCHED ──▶ tier II becomes eligible
#
# Two things fall out of this, and they are the point:
#   · Combat alone cannot run away with the game. Advancing a tier REQUIRES
#     spending power on research, so the ratchet is its own snowball brake —
#     it replaces the crew/materiel gate that did that job before.
#   · You cannot rush one axis. Progress is breadth-first by construction, so
#     every weapon ends up improving along all four dimensions rather than
#     becoming a damage number with a gun attached.
# The randomness means no two games hand you the same weapon in the same order.

AXES = OrderedDict([
    ("Damage",   dict(label="Warhead",   gain=0.25, params=["Damage", "RadiusDamage"],
                      blurb="Charge and fragmentation.")),
    ("Range",    dict(label="Fire Control", gain=0.07, params=["MaxRange", "ShortRange"],
                      blurb="Engagement geometry. Vanilla touches this in zero topics.")),
    ("Reload",   dict(label="Loading Drill", gain=0.10, params=["FirePause", "ReloadTime"],
                      negate=True, blurb="Time between shots.")),
    ("Accuracy", dict(label="Gunnery",   gain=0.10, params=["HitChance", "ShortHitChance"],
                      blurb="Fall of shot.")),
])
WEAPON_TIERS = 4

BODY_SIZES = [("LIGHT", "Light"), ("MEDIUM", "Medium"), ("HEAVY", "Heavy")]

# NOTE — a trap worth recording. `filterParameter: "Size"` looks legal but is NOT.
# wzapi.cpp:4392 does `body["Size"] = psStats->size` on a raw BODY_SIZE enum, so it
# serialises as an INTEGER (0..3), while ImpactClass/Effect go through
# getWeaponSubClass()/getWeaponEffect() and serialise as strings. Comparing against
# "LIGHT" would never match — and research.cpp `continue`s on a non-match with no
# warning, so the topic would silently do nothing. We enumerate body Ids instead:
# explicit, and immune to enum reordering.


# ─────────────────────────────────────────────────────────────────────────────
# Load the real component inventory
# ─────────────────────────────────────────────────────────────────────────────

def load_inventory():
    research = json.load(open(f"{WZ}/data/mp/stats/research.json"))
    weapons = json.load(open(f"{WZ}/data/mp/stats/weapons.json"))
    bodies = json.load(open(f"{WZ}/data/mp/stats/body.json"))
    granted = set()
    for v in research.values():
        for c in v.get("resultComponents", []):
            granted.add(c)
    by_family = defaultdict(list)
    sub2fam = {f["subclass"]: k for k, f in FAMILIES.items()}
    for wid, w in weapons.items():
        if wid not in granted:
            continue
        fam = sub2fam.get(w.get("weaponSubClass"))
        if fam:
            by_family[fam].append((wid, w.get("name", wid)))
    bodies_by_size = defaultdict(list)
    for bid, b in bodies.items():
        if bid in granted and not bid.startswith(("Cyborg", "Transporter", "SuperTransport")):
            bodies_by_size[b.get("size")].append((bid, b.get("name", bid)))
    return research, weapons, by_family, bodies_by_size


def signature_candidates(by_family):
    """Core designable turrets — the ones a player actually puts on a chassis.
    VTOL and cyborg variants ride on the family topics instead."""
    out = {}
    for fam, items in by_family.items():
        picks = [(i, n) for i, n in sorted(items)
                 if "VTOL" not in i and not i.startswith("Cyb")
                 and not n.startswith("*") and "AA " not in n]
        out[fam] = picks
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Emitters
# ─────────────────────────────────────────────────────────────────────────────

TOPICS = OrderedDict()
META = {}  # id -> extra info for the browser / spec


def emit(tid, name, pts, power, req, results=None, icon="IMAGE_RES_WEAPONTECH",
         kind="doctrine", note="", knowledge=None, unlocks=None, subgroup=None,
         result_components=None, result_structures=None):
    t = {
        "id": tid,
        "name": name,
        "iconID": icon,
        "researchPoints": int(pts),
        "researchPower": int(power),
    }
    if req:
        t["requiredResearch"] = list(req)
    if results:
        t["results"] = results
    if result_components:
        t["resultComponents"] = list(result_components)
    if result_structures:
        t["resultStructures"] = list(result_structures)
    if subgroup:
        t["subgroupIconID"] = subgroup
    TOPICS[tid] = t
    META[tid] = dict(kind=kind, note=note, knowledge=knowledge, unlocks=unlocks or [])
    return tid


def wres(params, subclass, value, negate=False, by_id=None):
    """Weapon upgrade results. by_id targets ONE weapon via filterParameter 'Id'
    (proven legal by vanilla R-Comp-CommandTurret02)."""
    out = []
    for p in params:
        r = {"class": "Weapon", "parameter": p, "value": -value if negate else value}
        if by_id:
            r["filterParameter"] = "Id"
            r["filterValue"] = by_id
        else:
            r["filterParameter"] = "ImpactClass"
            r["filterValue"] = subclass
        out.append(r)
    return out


# ── 1. THE SPINE: Command & Doctrine ────────────────────────────────────────
# This is the critical path. Everything in the field tier depends on it, so it
# must be early, cheap and obvious. Vanilla gives the Command Turret TWO topics
# out of 390. Here it gets eight, and it is the backbone of the game.

def emit_spine():
    S = "IMAGE_RES_COMPUTERTECH"
    emit("R-Struc-CommandRelay", "Command Relay Post", 900, 25,
         ["R-Sys-Sensor-Tower01"], icon=S, kind="spine",
         result_structures=["A0ComDroidControl"],
         note="One per player. The only place a commander can be debriefed.")

    emit("R-Comp-CommandTurret01", "Command Turret", 600, 18,
         ["R-Struc-CommandRelay"], icon=S, kind="spine",
         result_components=["CommandBrain01", "CommandTurret1"],
         note="The accumulator. Engine already credits every hit landed by any "
              "group member to the commander (projectile.cpp:378).")

    emit("R-Sys-Debrief01", "Field Debriefing Protocol", 1200, 40,
         ["R-Comp-CommandTurret01"], icon=S, kind="spine",
         note="ENABLES BANKING. Until this is researched a commander accumulates "
              "experience but cannot convert it to field knowledge.")

    emit("R-Comp-CommandTurret02", "Command Turret Upgrade", 2500, 90,
         ["R-Sys-Debrief01", "R-Sys-Sensor-Upgrade02"], icon=S, kind="spine",
         results=[
             {"class": "Brain", "parameter": "BaseCommandLimit", "value": 20},
             {"class": "Brain", "parameter": "CommandLimitByLevel", "value": 50},
             {"class": "Brain", "filterParameter": "Id", "filterValue": "CommandBrain01",
              "parameter": "RankThresholds", "value": -10},
             {"class": "Brain", "filterParameter": "Id", "filterValue": "CommandBrain01",
              "parameter": "HitPoints", "value": 20},
         ],
         note="Vanilla topic, kept verbatim. Bigger groups = wider knowledge capture.")

    emit("R-Sys-Debrief02", "Structured After-Action Review", 4000, 140,
         ["R-Comp-CommandTurret02"], icon=S, kind="spine",
         note="Banking yield +40%. Same combat record, more knowledge extracted.")

    emit("R-Sys-DataCore", "Hardened Data Core", 6000, 200,
         ["R-Sys-Debrief02"], icon=S, kind="spine",
         note="Black box recovery rises 50% -> 85%. Losing a commander stops "
              "being a catastrophe and becomes a rescue.")

    emit("R-Comp-CommandTurret03", "Distributed Command", 9000, 300,
         ["R-Sys-DataCore"], icon=S, kind="spine",
         results=[
             {"class": "Brain", "parameter": "BaseCommandLimit", "value": 30},
             {"class": "Brain", "filterParameter": "Id", "filterValue": "CommandBrain01",
              "parameter": "RankThresholds", "value": -15},
             {"class": "Brain", "filterParameter": "Id", "filterValue": "CommandBrain01",
              "parameter": "HitPoints", "value": 30},
         ],
         note="Commanders learn 15% faster again and survive the drive home.")

    emit("R-Sys-Telemetry", "Combat Telemetry Uplink", 16000, 450,
         ["R-Comp-CommandTurret03", "R-Sys-Sensor-UpLink"], icon=S, kind="spine",
         note="REMOTE DEBRIEF at 60% yield. The drive home still pays better — "
              "this removes the obligation, not the choice.")


# ── 2. THE WEAPON RATCHET ──────────────────────────────────────────────────
# Native prerequisites express two of the three rules:
#   Axis(T) requires Axis(T-1)                 — you must research a tier to pass it
#   Axis(T) requires R-Cred-<fam>-Tier<T>      — the cross-axis sync gate
# The credential is a synthetic marker the script enables once every axis of tier
# T-1 is RESEARCHED. Everything downstream is ordinary requiredResearch, so the
# research UI, tooltips and prerequisite display all work with zero special-casing.
# The script's ONLY jobs are: enable a random eligible topic when knowledge is
# banked, and flip the credential when a tier completes.

def emit_ratchet(by_family):
    kcur = knowledge_curve(WEAPON_TIERS)
    roman = ["I", "II", "III", "IV", "V"]
    for fam, f in FAMILIES.items():
        if not by_family.get(fam):
            continue
        for T in range(1, WEAPON_TIERS + 1):
            if T > 1:
                emit(f"R-Cred-{fam}-Tier{T}", f"{f['label']} Doctrine Review {roman[T-1]}",
                     10, 1, [], icon="IMAGE_RES_COMPUTERTECH", kind="credential",
                     note=f"SYNTHETIC MARKER. Script enables this once ALL FOUR "
                          f"{f['label']} tier-{T-1} topics are RESEARCHED. Until then no "
                          f"tier-{T} topic can be unlocked by combat, however much you fight.")
        for axis, a in AXES.items():
            vals = escalating(a["gain"], WEAPON_TIERS)
            for T in range(1, WEAPON_TIERS + 1):
                tid = f"R-Wpn-{fam}-{axis}{T:02d}"
                req = ["R-Sys-Debrief01"] if T == 1 else \
                      [f"R-Wpn-{fam}-{axis}{T-1:02d}", f"R-Cred-{fam}-Tier{T}"]
                emit(tid, f"{f['label']} {a['label']} {roman[T-1]}",
                     CONFIG["ratchet_pts"][T-1], CONFIG["ratchet_pow"][T-1], req,
                     results=wres(a["params"], f["subclass"], vals[T-1],
                                  negate=a.get("negate", False)),
                     kind="ratchet", knowledge=kcur[T-1],
                     note=f"{a['blurb']} Battlefield-unlocked at {kcur[T-1]:,} "
                          f"{f['label']} knowledge — but only once tier {T-1 or 1} is "
                          f"fully researched. One of four axes; which one surfaces "
                          f"next is random.")


# ── 3. SIGNATURE TOPICS: mastery of ONE specific weapon ─────────────────────
# These exist in the data but stay INVISIBLE until earned. enableResearch() only
# reveals what you have actually mastered, so the research UI stays small even
# though the tree is large. That is the opposite of vanilla, where all 390 topics
# are visible from minute one.

def emit_signature(sigs):
    kreq = int(CONFIG["knowledge_base"] * CONFIG["knowledge_growth"] ** WEAPON_TIERS)
    for fam, items in sigs.items():
        f = FAMILIES[fam]
        for wid, wname in items:
            tid = f"R-Sig-{wid}"
            emit(tid, f"{wname}: Veteran Crews",
                 CONFIG["signature_pts"], CONFIG["signature_pow"],
                 [f"R-Wpn-{fam}-Accuracy02"],
                 results=(wres(["HitChance", "ShortHitChance"], f["subclass"], 15, by_id=wid)
                          + wres(["FirePause", "ReloadTime"], f["subclass"], 20,
                                 negate=True, by_id=wid)),
                 kind="signature", knowledge=kreq,
                 note=f"Applies to {wname} ONLY. Earned by mastering this single "
                      f"component, not the family. Invisible until earned.")


# ── WEAPON SUCCESSION: the actual gun lineage ───────────────────────────────
# Vanilla already encodes this and it is the best part of the existing tree:
#     Machinegun -> Twin MG -> Heavy MG -> Assault Gun -> Twin Assault Gun
# and it is ALREADY gated on upgrade tiers — Twin MG needs MG-Damage02, Assault
# Gun needs MG3Mk1 + MG-ROF02. Under DOCTRINE those prerequisites now mean
# "you must have FOUGHT with machineguns", because that is what unlocks a tier.
# You do not get the Heavy Machinegun from a lab. You get it because your MG
# crews reported what they needed.
#
# Two problems to solve when merging with vanilla:
#   1. ID COLLISION. Vanilla's upgrade topics are R-Wpn-<fam>-Damage01..09/10 and
#      R-Wpn-<fam>-ROF01..06. This generator emits R-Wpn-<fam>-Damage01..04 and
#      R-Wpn-<fam>-Reload01..04. Damage01-04 collide (good — the succession
#      prerequisites re-point at the ratchet for free); Damage05-09 and every ROF
#      topic do NOT, so they would survive as orphans and let the player
#      double-dip on the old ladder.
#   2. TIER RESCALING. A prerequisite on Damage05-of-9 has to become a
#      prerequisite on the equivalent point of a 4-tier ladder.
# emit_succession() rewrites the prerequisites; SURPLUS records what the merged
# research.json must DELETE.

VANILLA_AXIS = {"Damage": "Damage", "ROF": "Reload", "Accuracy": "Accuracy"}
SURPLUS = []          # vanilla topic ids that must be removed on merge
CROSSLINKS = []       # (from_family, to_topic) cross-family dependencies, for the browser


def emit_succession(research, weapons, by_family):
    import math, re
    sub2fam = {f["subclass"]: k for k, f in FAMILIES.items()}

    def wfam(wid):
        return sub2fam.get(weapons.get(wid, {}).get("weaponSubClass"))

    # how many tiers does each vanilla upgrade ladder have?
    vmax = defaultdict(int)
    stem = re.compile(r"^R-Wpn-([A-Za-z]+?)(Slow)?-(Damage|ROF|Accuracy)(\d+)$")
    for k in research:
        m = stem.match(k)
        if m:
            vmax[(m.group(1), m.group(3))] = max(vmax[(m.group(1), m.group(3))], int(m.group(4)))

    def remap(dep):
        """Rewrite a vanilla upgrade prerequisite onto the 4-tier ratchet."""
        m = stem.match(dep)
        if not m:
            return dep
        vfam, _slow, vaxis, n = m.group(1), m.group(2), m.group(3), int(m.group(4))
        fam = vfam if vfam in FAMILIES else {"Energy": "Laser", "Rail": "Rail",
                                             "Flamer": "Flamer"}.get(vfam)
        if fam not in FAMILIES:
            return dep
        top = vmax[(vfam, vaxis)] or 1
        tier = min(WEAPON_TIERS, max(1, math.ceil(n / top * WEAPON_TIERS)))
        return f"R-Wpn-{fam}-{VANILLA_AXIS[vaxis]}{tier:02d}"

    # record vanilla ladder topics the merge must drop
    for k in research:
        m = stem.match(k)
        if not m:
            continue
        vfam, vaxis, n = m.group(1), m.group(3), int(m.group(4))
        fam = vfam if vfam in FAMILIES else {"Energy": "Laser"}.get(vfam)
        # everything on the old ladder goes: the tiers we replace by ID, and the
        # surplus tiers that would otherwise survive as a parallel ladder
        if fam in FAMILIES and not (VANILLA_AXIS[vaxis] == "Damage" and n <= WEAPON_TIERS):
            SURPLUS.append(k)

    for tid, v in sorted(research.items(), key=lambda x: x[1]["researchPoints"]):
        guns = [w for w in v.get("resultComponents", []) if w in weapons]
        if not guns:
            continue
        core = [w for w in guns if "VTOL" not in w and not w.startswith("Cyb")]
        fam = next((wfam(w) for w in (core or guns) if wfam(w)), None)
        if not fam or not by_family.get(fam):
            continue
        req = [remap(d) for d in v.get("requiredResearch", [])]
        seen, dedup = set(), []
        for r in req:
            if r not in seen:
                seen.add(r); dedup.append(r)
        # note any prerequisite that comes from a DIFFERENT weapon family
        for r in dedup:
            m2 = re.match(r"^R-Wpn-([A-Za-z]+)-", r)
            src = m2.group(1) if m2 else None
            if src in FAMILIES and src != fam:
                CROSSLINKS.append((src, tid))
        emit(tid, v["name"], v["researchPoints"], v.get("researchPower", 0), dedup,
             icon=v.get("iconID", "IMAGE_RES_WEAPONTECH"), kind="weapon",
             result_components=guns,
             note=f"Unlocks {', '.join(core or guns)}. Prerequisites remapped onto the "
                  f"ratchet — this gun is earned by fighting with {FAMILIES[fam]['label']}s, "
                  f"not bought from a lab.")
        META[tid]["family"] = fam
        META[tid]["guns"] = core or guns


# ── 6. PENETRATION: make the RPS layer sharpen over time ────────────────────
# MinimumDamage is the floor that stops a wrong-matchup weapon doing less than
# 33% of its damage (combat.cpp:650). Vanilla never touches it, so rock-paper-
# scissors ratios are byte-identical at minute 5 and minute 60.

def emit_penetration(by_family):
    for fam, f in FAMILIES.items():
        if not f["at"] or not by_family.get(fam):
            continue
        prev = None
        for n, v in enumerate([20, 25]):
            tid = f"R-Wpn-{fam}-Penet{n+1:02d}"
            gate = f"R-Wpn-{fam}-Damage{min(n+3, WEAPON_TIERS):02d}"
            req = [gate] if prev is None else [prev, gate]
            emit(tid, f"{f['label']} Armour-Piercing {['I','II'][n]}",
                 6000 + 8000 * n, 200 + 200 * n, req,
                 results=wres(["MinimumDamage"], f["subclass"], v),
                 kind="penetration",
                 note="Raises the guaranteed-damage floor for this family only. "
                      "Your chosen line becomes matchup-independent; everything "
                      "else stays matchup-dependent. Progress as SPECIALISATION.")
            prev = tid


# ── 7. BREADTH CREDENTIALS + INFRASTRUCTURE ────────────────────────────────
# requiredResearch is a pure AND-list, so "field tier 2 in any four families"
# cannot be expressed natively. Solution: synthetic marker topics that the
# script enables. Everything downstream then uses ordinary prerequisites.
# This is the ONLY bridge the script needs.

def emit_breadth():
    S = "IMAGE_RES_COMPUTERTECH"
    for n in (2, 3, 4, 5):
        emit(f"R-Cred-Breadth{n:02d}", f"Combined Arms Doctrine {n}", 10, 1, [],
             icon=S, kind="credential",
             note=f"SYNTHETIC MARKER. Script calls enableResearch() when the player "
                  f"holds field tier 2+ in {n} DIFFERENT families. Zero cost — it is "
                  f"a certificate, not a project.")

    # Specialists get better guns (depth gates above).
    # Generalists get a better war machine (breadth gates here).
    infra = [
        ("R-Struc-Research-Upgrade01", "Synaptic Link Data Analysis", 2, 2400, 75,
         [{"class": "Building", "parameter": "ResearchPoints", "value": 30}]),
        ("R-Struc-Power-Upgrade01", "Gas Turbine Generator", 2, 3000, 90,
         [{"class": "Building", "parameter": "PowerPoints", "value": 25}]),
        ("R-Struc-Factory-Upgrade01", "Automated Manufacturing", 3, 3600, 110,
         [{"class": "Building", "parameter": "ProductionPoints", "value": 30}]),
        ("R-Struc-Research-Upgrade02", "Dedicated Synaptic Link", 3, 6000, 190,
         [{"class": "Building", "parameter": "ResearchPoints", "value": 30}]),
        ("R-Vehicle-Metals01", "Composite Alloys", 3, 4800, 150,
         [{"class": "Body", "filterParameter": "BodyClass", "filterValue": "Droids",
           "parameter": "Armour", "value": 30},
          {"class": "Body", "filterParameter": "BodyClass", "filterValue": "Droids",
           "parameter": "HitPointPct", "value": 30}]),
        ("R-Sys-Autorepair-General", "Auto-Repair", 4, 9000, 300, None),
        ("R-Struc-Research-Upgrade03", "Neural Synapse Research Brain", 4, 12000, 380,
         [{"class": "Building", "parameter": "ResearchPoints", "value": 30},
          {"class": "Building", "parameter": "ModuleResearchPoints", "value": 30}]),
        ("R-Struc-Limit-Labs", "Distributed Research Network", 5, 14000, 420,
         [{"class": "Building", "filterParameter": "Id", "filterValue": "A0ResearchFacility",
           "parameter": "Limit", "value": 40}]),
    ]
    for tid, name, breadth, pts, pw, results in infra:
        emit(tid, name, pts, pw, [f"R-Cred-Breadth{breadth:02d}"],
             results=results, icon="IMAGE_RES_COMPUTERTECH", kind="infrastructure",
             note=f"BREADTH GATE {breadth}: requires field experience in {breadth} "
                  f"different weapon families. Generalists get the war machine.")


# ── 8. CHASSIS HANDLING: crew skill for bodies ─────────────────────────────

def emit_chassis(bodies_by_size):
    vals = escalating(0.10, 3)
    kcur = knowledge_curve(3)
    roman = ["I", "II", "III"]
    for size, label in BODY_SIZES:
        ids = bodies_by_size.get(size, [])
        if not ids:
            continue
        prev = None
        for n in range(3):
            tid = f"R-Field-Chassis{size.title()}-Handling{n+1:02d}"
            req = ["R-Sys-Debrief01"] if prev is None else [prev]
            emit(tid, f"{label} Chassis Handling {roman[n]}",
                 CONFIG["ratchet_pts"][n], CONFIG["ratchet_pow"][n], req,
                 results=[{"class": "Body", "filterParameter": "Id", "filterValue": bid,
                           "parameter": "Power", "value": vals[n]} for bid, _ in ids],
                 icon="IMAGE_RES_VEHICLETECH", kind="chassis", knowledge=kcur[n],
                 note=f"Driver skill on {label.lower()} chassis "
                      f"({', '.join(n2 for _, n2 in ids)}). Engine output, i.e. speed. "
                      f"Unlocked at {kcur[n]:,} chassis knowledge.")
            prev = tid


# ─────────────────────────────────────────────────────────────────────────────
def main():
    research, weapons, by_family, bodies_by_size = load_inventory()
    sigs = signature_candidates(by_family)

    emit_spine()
    emit_ratchet(by_family)
    emit_succession(research, weapons, by_family)
    emit_chassis(bodies_by_size)
    emit_signature(sigs)
    emit_penetration(by_family)
    emit_breadth()

    os.makedirs("/home/claude/wz-doctrine/out", exist_ok=True)
    with open("/home/claude/wz-doctrine/out/research-doctrine.json", "w") as fh:
        json.dump(TOPICS, fh, indent=1, sort_keys=True)
    with open("/home/claude/wz-doctrine/out/surplus.json", "w") as fh:
        json.dump(sorted(set(SURPLUS)), fh, indent=1)
    with open("/home/claude/wz-doctrine/out/meta.json", "w") as fh:
        json.dump({"topics": TOPICS, "meta": META,
                   "crosslinks": CROSSLINKS, "surplus": sorted(set(SURPLUS)),
                   "config": CONFIG,
                   "families": {k: dict(v) for k, v in FAMILIES.items()},
                   "inventory": {k: v for k, v in by_family.items()},
                   "signatures": {k: v for k, v in sigs.items()}}, fh, indent=1)

    # ── report ──
    kinds = defaultdict(int)
    pts = defaultdict(int)
    for tid, t in TOPICS.items():
        kinds[META[tid]["kind"]] += 1
        pts[META[tid]["kind"]] += t["researchPoints"]
    print(f"{'KIND':16s} {'TOPICS':>7s} {'POINTS':>12s}")
    for k in sorted(kinds, key=lambda x: -kinds[x]):
        print(f"{k:16s} {kinds[k]:7d} {pts[k]:12,d}")
    print(f"{'TOTAL':16s} {len(TOPICS):7d} {sum(pts.values()):12,d}")
    print()
    print("RATCHET — four axes, four tiers, breadth-first:")
    for axis, a in AXES.items():
        v = escalating(a["gain"], WEAPON_TIERS)
        tot = 1.0
        for x in v: tot *= 1 + a["gain"]
        print(f"   {axis:9s} values {str(v):22s} total {(tot-1)*100:5.0f}% relative")
    print("Knowledge to unlock each tier:", knowledge_curve(WEAPON_TIERS))
    print("Research cost per tier:", CONFIG["ratchet_pts"])


if __name__ == "__main__":
    main()
