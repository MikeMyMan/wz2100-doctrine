#!/usr/bin/env python3
"""
DOCTRINE — build doctrine.wz for Warzone 2100 4.5.5 (Windows install).

Reads vanilla stats straight out of the installed mp.wz (a plain ZIP; read-only),
applies the generated DOCTRINE data from out/, and produces + installs the mod.

Run:  py -X utf8 build_mod.py
Output:
  build/doctrine.wz            the mod
  build/REBALANCE-SUMMARY.md   every stat change vs vanilla, reviewable
  installed to  %USERPROFILE%\\Documents\\Warzone 2100 Project\\Warzone 2100\\mods\\4.5.5\\autoload\\

Corrections vs IMPLEMENTATION.md (verified against the 4.5.5 source):
  * delete set is surplus MINUS doctrine — 10 surplus IDs are also doctrine
    replacement topics and must survive
  * 6 vanilla prereqs point at deleted ladder tops -> re-pointed to tier-4
    doctrine topics (dangling requiredResearch is a FATAL assert in research.cpp)
  * calculationMode lives in a "_config_" dict, not at document root
  * scripts ship under multiplay/script/mods/ (the real mod hook), not rules/

DOCTRINE v2 (artifact drops) tree restructure:
  * researchAvailable() auto-reveals any topic whose NON-EMPTY prereq list is
    fully researched; only empty-prereq topics wait for enableResearch(). So
    every script-gated topic ships with requiredResearch stripped:
      - 176 axis topics (revealed one at a time by intel-crate pickups)
      - 45 signature topics (v1: stay hidden forever)
  * the 33 R-Cred-<fam>-Tier2..4 certificates are removed — the tier gate is
    enforced by the script's currentTier() and they gated nothing else
  * the 4 R-Cred-Breadth topics stay: the script enables them at N families
    tier-2+, and the infrastructure branch cascades natively behind them
"""
import copy
import json
import os
import re
import shutil
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

# NOTE: IMPLEMENTATION.md §3.3 says Documents\, but these builds actually use
# %APPDATA%\Roaming (verified: the game created mods\<version>\ there on run).
MODS_ROOT = (Path(os.environ["APPDATA"]) / "Warzone 2100 Project"
             / "Warzone 2100" / "mods")

# Target selection: `py build_mod.py [4.7.0|4.5.5]`, default 4.7.0.
# out dirs are generated per target by generate_tree.py/rebalance.py run
# against that version's mp.wz (they are version-aware).
# Where each game version is installed. Override per machine without editing this
# file: set WZ_MP_WZ_455 / WZ_MP_WZ_470 to the full path of that version's mp.wz.
# (The defaults are the standard Windows install locations.)
def _mp_wz(env_key, default):
    return Path(os.environ.get(env_key, default))


TARGETS = {
    "4.5.5": {
        "mp_wz": _mp_wz("WZ_MP_WZ_455", r"C:\Program Files\Warzone 2100-4.5.5\data\mp.wz"),
        "out": HERE / "out",
        "build": HERE / "build",
        "install": MODS_ROOT / "4.5.5" / "autoload",
    },
    "4.7.0": {
        "mp_wz": _mp_wz("WZ_MP_WZ_470", r"C:\Program Files\Warzone 2100\data\mp.wz"),
        "out": HERE / "out-4.7.0",
        "build": HERE / "build-4.7.0",
        "install": MODS_ROOT / "4.7.0" / "autoload",
    },
}
ARGV = [a for a in sys.argv[1:] if a != "--telemetry"]
TELEMETRY = "--telemetry" in sys.argv
# --force-diff=N pins the AI difficulty for headless measurement only
FORCE_DIFF = 0
for _a in sys.argv[1:]:
    if _a.startswith("--force-diff="):
        FORCE_DIFF = int(_a.split("=", 1)[1])
ARGV = [a for a in ARGV if not a.startswith("--force-diff=")]
TARGET = ARGV[0] if ARGV else "4.7.0"
if TARGET not in TARGETS:
    print(f"unknown target {TARGET}; use one of {list(TARGETS)}")
    sys.exit(1)
MP_WZ = TARGETS[TARGET]["mp_wz"]
OUT = TARGETS[TARGET]["out"]
BUILD = TARGETS[TARGET]["build"]
INSTALL_DIR = TARGETS[TARGET]["install"]

# Superweapon / bomb prerequisites that reference deleted vanilla ladder tops.
# Re-pointed to the tier-4 doctrine topic of the same family+axis intent.
REPOINT = {
    "R-Wpn-Rail-ROF03":          "R-Wpn-Rail-Reload04",
    "R-Wpn-Cannon-Damage05":     "R-Wpn-Cannon-Damage04",
    "R-Wpn-Missile-ROF03":       "R-Wpn-Missile-Reload04",
    "R-Wpn-RocketSlow-Accuracy02": "R-Wpn-Rocket-Accuracy04",
    "R-Wpn-Rocket-Damage08":     "R-Wpn-Rocket-Damage04",
    "R-Wpn-Flamer-Damage05":     "R-Wpn-Flamer-Damage04",
    # Deleting the double-dipping R-Wpn-Mortar-Acc01 orphaned the whole
    # counter-battery / sensor / heavy-artillery branch, which hung off it via
    # R-Sys-CBSensor-Turret01. Re-point at the basic mortar unlock: same intent
    # ("you need mortars before counter-battery") and no new gating, since
    # R-Wpn-Mortar01Lt is already reachable on the normal mortar line.
    "R-Wpn-Mortar-Acc01":        "R-Wpn-Mortar01Lt",
}

# Projectile-speed pass, by weaponSubClass. (mult, cap) or (None, absolute).
# Bullets should feel near-hitscan; rail is the fastest ballistic in the game;
# rockets/missiles keep visible travel; arcs (mortar/howitzer/bomb/flame) and
# beams stay untouched — artillery must remain dodgeable.
FLIGHT_SPEED = {
    "MACHINE GUN": ("abs", 3600),
    "A-A GUN":     ("abs",  3200),
    "CANNON":      ("mult", 1.5, 3000),
    "GAUSS":       ("abs",  3200),
    "ROCKET":      ("mult", 1.2, None),
    "MISSILE":     ("mult", 1.2, None),
}

# Appended to Nexus's buildDefinitions.js. Runs inside each AI script instance,
# where `me` is that AI's player number and `difficulty` its real setting.
DIFFICULTY_GRADIENT_JS = """

// ---- DOCTRINE difficulty gradient -----------------------------------------
// Power throughput decides how fast the AI replaces losses, which is exactly
// what a scavenger flood tests. Values are percentages for setPowerModifier.
// Note Medium sits ABOVE parity at 120%: an AI plays its economy far less
// efficiently than a human does, so matching a player's income leaves it
// behind. Parity of power is not parity of outcome.
const DOCTRINE_POWER_BY_DIFF = { 1: 100, 2: 150, 3: 200, 4: 300 };

// Vanilla caps every player at 5 tank factories. Raising the allowance in
// build.js does nothing on its own -- the limit has to move too.
const DOCTRINE_FACTORY_LIMIT = { 3: 6, 4: 10 };

// Power alone plateaus: Nexus only runs two factories, so past roughly 200% it
// banks power it cannot spend and the army stops growing (measured: 340% gave
// no larger a force than 160%). What a higher difficulty actually needs is
// better units, not more of the same. So the top two difficulties also recover
// intel faster -- a free topic off their OWN available list on a timer, which
// is the same DOCTRINE crate ladder everyone climbs, just turned faster.
// enumResearch() only ever returns topics already unlocked for this player, so
// this cannot skip the ladder, and completing it here still flows through
// DOCTRINE's eventResearched bookkeeping.
const DOCTRINE_INTEL_EVERY = { 3: 150000, 4: 75000 };   // ms per free topic

// FORCED_DIFF is 0 in every real build. The headless skirmish harness ignores
// per-player difficulty (verified: every AI reports 2 whatever the config says),
// so measuring the gradient means pinning it at build time.
const DOCTRINE_FORCED_DIFF = %FORCE%;

function doctrineApplyDifficulty() {
	if (typeof difficulty === "undefined" && !DOCTRINE_FORCED_DIFF) { return; }
	const d = DOCTRINE_FORCED_DIFF || difficulty;
	const pct = DOCTRINE_POWER_BY_DIFF[d];
	if (pct === undefined) { return; }
	setPowerModifier(pct, me);

	const facLimit = DOCTRINE_FACTORY_LIMIT[d];
	if (facLimit !== undefined)
	{
		setStructureLimits("A0LightFactory", facLimit, me);
	}
	if (DOCTRINE_DIFF_DEBUG) {
		debug("DOCTRINE-DIFF p" + me + " difficulty=" + d + " power=" + pct + "%");
	}
}
const DOCTRINE_DIFF_DEBUG = %DEBUG%;
function doctrineFreeIntel() {
	const d = DOCTRINE_FORCED_DIFF || difficulty;
	const every = DOCTRINE_INTEL_EVERY[d];
	if (every === undefined) { return; }
	// ONLY the DOCTRINE weapon-upgrade ladder. enumResearch() returns every
	// available topic, which on the first cut meant this handed out defences,
	// walls and factories -- the AI was fielding hardcrete long before it should
	// have had the technology. Axis topics are "R-Wpn-<family>-<axis>0<tier>".
	const list = enumResearch().filter(function (r) {
		return /^R-Wpn-.+-(Damage|Range|Reload|Accuracy)0[1-9]$/.test(r.id);
	});
	if (list.length > 0) {
		const pick = list[gameTime % list.length];
		hackNetOff();
		completeResearch(pick.name !== undefined ? pick.name : pick.id, me);
		hackNetOn();
		if (DOCTRINE_DIFF_DEBUG) { debug("DOCTRINE-INTEL p" + me + " " + pick.id); }
	}
	queue("doctrineFreeIntel", every);
}

queue("doctrineApplyDifficulty", 100);
queue("doctrineFreeIntel", 60000);
"""

# Scavenger mortars fire far less accurately than the player's. (longHit, shortHit)
# against the vanilla 50/40 they inherit from Mortar1Mk1.
# 22/18 was still reported as "100% precise" in play. The reason is splash:
# radius 160 with 40 splash damage means even a missed shell lands real damage
# next to the target, which reads as a hit. So the scav copy both misses more
# and hurts less when it misses.
SCAV_MORTAR_ID  = "BabaMortarPit"
# 12/10 was too far: the pit costs 350 build points and missed 88% of the
# time, so it was not worth building at all. 22/18 keeps it well short of
# the player's 50/40 mortar -- still no precise artillery battery -- while
# making the emplacement worth its price.
SCAV_MORTAR_HIT = (22, 18)
SCAV_MORTAR_SPLASH = 20   # vanilla Mortar1Mk1: 40

# Nexus factory/lab allowance by derrick count, as (vanilla-snippet, replacement).
# Vanilla: <=8 -> 2, <=12 -> 3, <=16 -> 4, else 5.
# Raise the ALLOWANCE, not the thresholds: a 3-6 derrick holding is the normal
# case, and under vanilla that band gets 2. Shifting thresholds instead would
# have left that band on 2-3, which is barely a change.
# These replace the four `amount = N;` assignments IN ORDER (derrick bands
# <=8, <=12, <=16, more). Applied positionally, never by search-and-replace --
# chained text replacement rewrites values it has already written.
FACTORY_ALLOWANCE = [4, 5, 5, 5]

# Insane is meant to out-produce, not just out-spend. Vanilla caps every
# player at 5 tank factories (rules/setup/structurelimits.js), so the
# structure limit itself has to be raised for these to be reachable -- that
# happens in DIFFICULTY_GRADIENT_JS, which runs inside the AI and can see
# its own difficulty.
CRLF = chr(13) + chr(10)
TAB_JS = chr(9)
Q = chr(34)
INSANE_FACTORIES = 10
HARD_FACTORIES = 6


DOCTRINE_ENGINE_JS = '// DOCTRINE research policy -- see build_mod.py\r\nconst RESEARCH_MIN_POWER = 30;\r\n\r\n// A lab upgrade is only worth taking when research has actually become slow.\r\n// Putting the ladder first unconditionally made the AI beeline for it and\r\n// field nothing but the starting machinegun while it did.\r\nconst DOCTRINE_SLOW_SECONDS = 360;      // 6 minutes average per topic\r\nconst DOCTRINE_WEAPONS_BEFORE_LAB = 1;  // earn one real weapon first\r\n// how far the lab ladder may run ahead of the weapon count (0 = strict alternation)\r\nconst DOCTRINE_LAB_LEAD = 0;\r\n\r\n/* The two topics every AI takes before it thinks about anything else.\r\n\r\n   R-Wpn-MG1Mk1 is first because it is the opening weapon and it is no longer\r\n   handed out free -- 60 points, ten seconds at the base lab rate, and until\r\n   it lands the factories can only turn out trucks. It also carries\r\n   CyborgChaingun and MG1-VTOL, so it opens MG cyborgs and MG VTOLs too.\r\n\r\n   The Heavy Machinegun Guard Tower follows: the AI\'s only early emplacement,\r\n   600 points, and its prerequisite is the topic directly above it. */\r\nconst DOCTRINE_DEFENCE_FIRST = ["R-Wpn-MG1Mk1", "R-Defense-Tower01"];\r\n\r\n// Cheap openers: Twin MG, Light Cannon, Flamer. One of these comes before\r\n// any thought of lab infrastructure.\r\nconst DOCTRINE_EARLY_WEAPONS = [\r\n\t"R-Wpn-MG2Mk1", "R-Wpn-Cannon1Mk1", "R-Wpn-Flamer01Mk1", "R-Wpn-MG3Mk1",\r\n];\r\n// components that prove a real weapon beyond the starting MG is in hand\r\nconst DOCTRINE_WEAPON_MARKERS = ["MG2Mk1", "Cannon1Mk1", "Flame1Mk1", "MG3Mk1"];\r\n\r\n// Two very different things were living in one list. The cheap enablers\r\n// below are fine to take as soon as research has gone slow...\r\nconst DOCTRINE_LAB_INFRA = [\r\n\t"R-Struc-CommandRelay", "R-Struc-Research-Module",\r\n\t"R-Struc-Factory-Module", "R-Struc-Power-Upgrade01",\r\n];\r\n\r\n// ...but the Synaptic Link chain is the expensive, self-compounding one.\r\n// Counting the relay and the module as `lab steps` gave the AI enough\r\n// budget to take Synaptic Link Data Analysis immediately after the module,\r\n// which is exactly the behaviour being complained about. It gets its own\r\n// list, its own counter, and it sits BELOW the support topics.\r\nconst DOCTRINE_LAB_UPGRADES = [\r\n\t"R-Struc-Research-Upgrade01", "R-Struc-Research-Upgrade02",\r\n\t"R-Struc-Research-Upgrade03", "R-Struc-Research-Upgrade04",\r\n];\r\n\r\n// Tank traps, repair and walls come before any Synaptic upgrade. All are\r\n// cheap (300-2400 points) and all of them matter more early than a faster\r\n// lab does.\r\n// The chassis to CARRY the weapons: engines, propulsion, bodies, armour.\r\n// Without this list the AI researched guns it could only mount on wheeled\r\n// Vipers. Ordered cheap-to-dear so it interleaves naturally as rungs finish.\r\nconst DOCTRINE_VEHICLE_TECH = [\r\n\t"R-Vehicle-Engine01", "R-Vehicle-Prop-Halftracks", "R-Vehicle-Body05",\r\n\t"R-Vehicle-Metals01", "R-Vehicle-Body04", "R-Vehicle-Metals02",\r\n\t"R-Vehicle-Prop-Tracks", "R-Vehicle-Engine02", "R-Vehicle-Body11",\r\n\t"R-Vehicle-Body08", "R-Vehicle-Metals03", "R-Vehicle-Engine03",\r\n];\r\n\r\n// Base air defence, researched proactively from minute 12 -- scavenger air\r\n// arrives at 15:00 and Nexus\'s own AA logic is purely reactive (it only\r\n// places AA after already being hit from the air).\r\nconst DOCTRINE_AA_AFTER = 720000;\r\nconst DOCTRINE_AA = [\r\n\t"R-Wpn-AAGun03", "R-Defense-AASite-QuadMg1",\r\n\t"R-Wpn-Sunburst", "R-Defense-Sunburst", "R-Wpn-AAGun04",\r\n];\r\n\r\n// Emplacement variety. Every topic here is 600-1100 points and hangs off\r\n// research the AI does anyway (Hardcrete, MG3, Light Cannon, MiniPod).\r\n// Unlocking them feeds three vanilla behaviours that were sitting dead:\r\n// buildGates() fortifies base gateways with wall-tower HARDPOINTS,\r\n// derrickDefense() rings derricks with mortar pits, and the basic-defence\r\n// pool for pickets grows beyond the lone Guard Tower.\r\nconst DOCTRINE_DEF_TECH = [\r\n\t"R-Defense-Pillbox01", "R-Defense-WallTower02", "R-Defense-WallTower01",\r\n\t"R-Defense-MortarPit", "R-Defense-Tower06", "R-Defense-RotMG",\r\n];\r\n\r\n// One working AA line is enough while the sky is empty. Research past it\r\n// only escalates if an enemy actually fields air.\r\n// AA structures, inlined rather than read from STANDARD_ANTI_AIR_DEFENSES --\r\n// that list is a Nexus-only global and this engine also runs inside Cobra,\r\n// BoneCrusher, NullBot and SemperFi.\r\nconst DOCTRINE_AA_STRUCTS = [\r\n\t"AASite-QuadMg1", "AASite-QuadBof", "AASite-QuadRotMg",\r\n\t"P0-AASite-SAM1", "P0-AASite-SAM2", "P0-AASite-Laser",\r\n\t"P0-AASite-Sunburst", "AASite-QuadBof02",\r\n];\r\n\r\nfunction doctrineHasAA()\r\n{\r\n\tfor (let i = 0; i < DOCTRINE_AA_STRUCTS.length; ++i)\r\n\t{\r\n\t\tif (isStructureAvailable(DOCTRINE_AA_STRUCTS[i])) { return true; }\r\n\t}\r\n\treturn false;\r\n}\r\n\r\nfunction doctrineEnemyAir()\r\n{\r\n\tlet n = 0;\r\n\tfor (let pl = 0; pl < maxPlayers; ++pl)\r\n\t{\r\n\t\tif (pl === me || allianceExistsBetween(me, pl)) { continue; }\r\n\t\tconst ds = enumDroid(pl);\r\n\t\tfor (let i = 0; i < ds.length; ++i)\r\n\t\t{\r\n\t\t\tif (isVTOL(ds[i])) { ++n; }\r\n\t\t}\r\n\t}\r\n\tif (typeof scavengerPlayer !== "undefined" && scavengerPlayer >= 0)\r\n\t{\r\n\t\tconst sc = enumDroid(scavengerPlayer);\r\n\t\tfor (let i = 0; i < sc.length; ++i)\r\n\t\t{\r\n\t\t\tif (isVTOL(sc[i])) { ++n; }\r\n\t\t}\r\n\t}\r\n\treturn n;\r\n}\r\n\r\n/* Topics that unlock a whole UNIT CLASS rather than a stat.\r\n\r\n   R-Struc-Factory-Cyborg scored 18.3 under this model -- dead last behind\r\n   every early topic -- because it matches no list and is not R-Vehicle-,\r\n   R-Defense- or R-Wpn-, so it fell into the catch-all weight and was then\r\n   punished for its cost. The AI therefore almost never built cyborgs at\r\n   all, and any cyborg balancing would have been invisible to it. One topic\r\n   that unlocks the factory, the body AND the legs is worth more than a\r\n   single stat upgrade, so it is weighted accordingly. */\r\nconst DOCTRINE_UNIT_ENABLERS = ["R-Struc-Factory-Cyborg"];\r\n\r\nconst DOCTRINE_SUPPORT_FIRST = [\r\n\t"R-Defense-TankTrap01", "R-Sys-MobileRepairTurret01",\r\n\t"R-Defense-HardcreteWall", "R-Defense-WallUpgrade01",\r\n\t"R-Struc-RepairFacility",\r\n];\r\n\r\n\r\n// Each AI favours one weapon family for the whole game, derived from its\r\n// player slot so it stays sync-safe -- two Nexus players no longer converge\r\n// on identical armies.\r\n/* A weapon family is a whole LINE, not a handful of base unlocks.\r\n\r\n   Matching only the four or five unlock topics missed every damage,\r\n   accuracy and rate-of-fire upgrade that belongs to the same weapon --\r\n   which is most of what a family actually costs. Cobra states its\r\n   preference as `R-Wpn-Cannon-Damage02`, an upgrade, so exact-id matching\r\n   could not read it at all. Prefixes catch the line end to end. */\r\nconst DOCTRINE_FAMILY_PREFIXES = [\r\n\t["R-Wpn-Cannon"],\r\n\t["R-Wpn-Flam"],                          // Flamer01Mk1 and Flame2\r\n\t["R-Wpn-Rocket", "R-Wpn-Missile"],       // missiles are the rocket end-game\r\n\t["R-Wpn-MG"],\r\n\t["R-Wpn-Mortar", "R-Wpn-Howitzer"],      // one indirect-fire family\r\n];\r\n\r\n// Which family a topic belongs to, or -1.\r\nfunction doctrineFamilyOf(id)\r\n{\r\n\tfor (let f = 0; f < DOCTRINE_FAMILY_PREFIXES.length; ++f)\r\n\t{\r\n\t\tconst pre = DOCTRINE_FAMILY_PREFIXES[f];\r\n\t\tfor (let k = 0; k < pre.length; ++k)\r\n\t\t{\r\n\t\t\tif (id.indexOf(pre[k]) === 0) { return f; }\r\n\t\t}\r\n\t}\r\n\treturn -1;\r\n}\r\n\r\nconst DOCTRINE_FAMILY_NAMES = ["cannon", "flamer", "rocket", "mg", "mortar"];\r\n\r\n/* Which weapon family this AI favours.\r\n\r\n   Was: the player slot. That meant Cobra AC (cannons), NullBot FR (flamers)\r\n   and Hover R (rockets) all researched the same line whenever they shared a\r\n   slot -- the engine silently overrode every personality\'s weapon identity.\r\n\r\n   Now the AI\'s OWN declaration is read first. Cobra and the three NullBot\r\n   AIs both expose weapons[].res lists; Nexus exposes earlyResearch;\r\n   BoneCrusher exposes research_path. Matches are position-weighted, so a\r\n   primary weapon outranks a later fallback. Only an AI that declares\r\n   nothing at all (SemperFi) falls through to its build-time default, and\r\n   only then to the slot number. */\r\nfunction doctrineFamilyHints()\r\n{\r\n\tconst hints = [];\r\n\r\n\t// `ordered` lists state a preference: first entry is the primary weapon,\r\n\t// so it must outrank the fallbacks below it. A `flat` list is a whole-game\r\n\t// plan with no ranking (BoneCrusher), where sheer volume is the signal.\r\n\tconst push = function (arr, cap, ordered) {\r\n\t\tif (arr === undefined || arr === null) { return; }\r\n\t\tconst n = Math.min(arr.length, cap);\r\n\t\tfor (let i = 0; i < n; ++i)\r\n\t\t{\r\n\t\t\tlet id = null;\r\n\t\t\tif (typeof arr[i] === "string") { id = arr[i]; }\r\n\t\t\telse if (arr[i] !== null && arr[i] !== undefined\r\n\t\t\t\t&& typeof arr[i].res === "string") { id = arr[i].res; }\r\n\t\t\tif (id === null) { continue; }\r\n\t\t\thints.push({ id: id, w: ordered ? (n - i) : 1 });\r\n\t\t}\r\n\t};\r\n\r\n\t// Cobra: `personality` is a KEY into subPersonalities\r\n\ttry\r\n\t{\r\n\t\tif (typeof subPersonalities !== "undefined" && typeof personality === "string"\r\n\t\t\t&& subPersonalities[personality] !== undefined)\r\n\t\t{\r\n\t\t\tconst sp = subPersonalities[personality];\r\n\t\t\tif (sp.primaryWeapon !== undefined) { push(sp.primaryWeapon.weapons, 8, true); }\r\n\t\t\tpush(sp.res, 8, true);\r\n\t\t\tif (sp.secondaryWeapon !== undefined) { push(sp.secondaryWeapon.weapons, 4, false); }\r\n\t\t}\r\n\t}\r\n\tcatch (e) { }\r\n\r\n\t// NullBot / Hover / Turtle: `personality` is the OBJECT itself\r\n\ttry\r\n\t{\r\n\t\tif (typeof personality === "object" && personality !== null\r\n\t\t\t&& personality.weaponPaths !== undefined && personality.weaponPaths.length > 0)\r\n\t\t{\r\n\t\t\tpush(personality.weaponPaths[0].weapons, 8, true);\r\n\t\t\tpush(personality.earlyResearch, 8, true);\r\n\t\t\tif (personality.weaponPaths.length > 1)\r\n\t\t\t{\r\n\t\t\t\tpush(personality.weaponPaths[1].weapons, 4, false);\r\n\t\t\t}\r\n\t\t}\r\n\t}\r\n\tcatch (e) { }\r\n\r\n\t// Nexus: `branch` names the active entry in nexusBranch\r\n\ttry\r\n\t{\r\n\t\tif (typeof nexusBranch !== "undefined" && typeof branch === "string"\r\n\t\t\t&& nexusBranch[branch] !== undefined)\r\n\t\t{\r\n\t\t\tpush(nexusBranch[branch].earlyResearch, 10, true);\r\n\t\t}\r\n\t}\r\n\tcatch (e) { }\r\n\r\n\t// BoneCrusher: one flat whole-game plan drawn from a weighted bag. These\r\n\t// plans are genuinely mixed -- its "cannon" path holds 7 machinegun\r\n\t// topics to 6 cannon -- so read emphasis by volume, unranked.\r\n\ttry\r\n\t{\r\n\t\tif (typeof research_path !== "undefined") { push(research_path, 200, false); }\r\n\t}\r\n\tcatch (e) { }\r\n\r\n\treturn hints;\r\n}\r\n\r\nfunction doctrinePickFamily()\r\n{\r\n\tconst hints = doctrineFamilyHints();\r\n\tconst score = [];\r\n\tfor (let f = 0; f < DOCTRINE_FAMILY_PREFIXES.length; ++f) { score.push(0); }\r\n\r\n\tfor (let i = 0; i < hints.length; ++i)\r\n\t{\r\n\t\tconst f = doctrineFamilyOf(hints[i].id);\r\n\t\tif (f >= 0) { score[f] += hints[i].w; }\r\n\t}\r\n\r\n\tlet bestIdx = -1;\r\n\tlet bestScore = 0;\r\n\tfor (let f = 0; f < score.length; ++f)\r\n\t{\r\n\t\tif (score[f] > bestScore) { bestScore = score[f]; bestIdx = f; }\r\n\t}\r\n\r\n\tif (bestIdx < 0 && typeof DOCTRINE_AI_DEFAULT_FAMILY !== "undefined"\r\n\t\t&& DOCTRINE_AI_DEFAULT_FAMILY >= 0)\r\n\t{\r\n\t\tbestIdx = DOCTRINE_AI_DEFAULT_FAMILY;\r\n\t}\r\n\tif (bestIdx < 0) { bestIdx = me % DOCTRINE_FAMILY_PREFIXES.length; }\r\n\treturn bestIdx;\r\n}\r\n\r\n// Resolved lazily and cached. Personalities are assigned in\r\n// eventStartLevel(), long after this file is parsed, so a load-time const\r\n// would always read `undefined` and fall through to the slot number.\r\nvar DOCTRINE_FAMILY_IDX = -1;\r\nfunction doctrineFamily()\r\n{\r\n\tif (DOCTRINE_FAMILY_IDX < 0) { DOCTRINE_FAMILY_IDX = doctrinePickFamily(); }\r\n\treturn DOCTRINE_FAMILY_IDX;\r\n}\r\n\r\n// Whatever this AI calls its current personality, for reporting.\r\nfunction doctrinePersonalityName()\r\n{\r\n\ttry { if (typeof personality === "string") { return personality; } } catch (e) { }\r\n\ttry\r\n\t{\r\n\t\tif (typeof personality === "object" && personality !== null\r\n\t\t\t&& personality.chatalias !== undefined) { return personality.chatalias; }\r\n\t}\r\n\tcatch (e) { }\r\n\ttry { if (typeof branch === "string") { return branch; } } catch (e) { }\r\n\ttry\r\n\t{\r\n\t\tif (typeof policy !== "undefined" && policy["build"] !== undefined)\r\n\t\t{\r\n\t\t\treturn "build:" + policy["build"];\r\n\t\t}\r\n\t}\r\n\tcatch (e) { }\r\n\treturn "fixed";\r\n}\r\n\r\n\r\n// Live lab throughput in research points per second, including the module\r\n// and every upgrade already taken.\r\nfunction doctrineLabRate()\r\n{\r\n\tconst b = (typeof Upgrades !== "undefined" && Upgrades[me]) ? Upgrades[me].Building : undefined;\r\n\tif (b !== undefined)\r\n\t{\r\n\t\tconst direct = b["A0ResearchFacility"];\r\n\t\tif (direct !== undefined && direct.researchPoints > 0) { return direct.researchPoints; }\r\n\t\tfor (const k in b)\r\n\t\t{\r\n\t\t\tif (b[k] !== undefined && b[k].researchPoints > 0) { return b[k].researchPoints; }\r\n\t\t}\r\n\t}\r\n\treturn 6;   // DOCTRINE ships A0ResearchFacility at 6 points/sec\r\n}\r\n\r\n// Typical seconds to finish what is currently on offer. MEDIAN, not mean:\r\n// topic costs run from 1 point to 56,600, so an average is dragged around by\r\n// whichever extreme is visible. The median tracks what the AI actually picks.\r\nfunction doctrineTypicalResearchSeconds()\r\n{\r\n\tconst list = enumResearch();\r\n\tconst costs = [];\r\n\tfor (let i = 0; i < list.length; ++i)\r\n\t{\r\n\t\tif (list[i].points > 0) { costs.push(list[i].points); }\r\n\t}\r\n\tif (costs.length === 0) { return 0; }\r\n\tcosts.sort(function (a, b) { return a - b; });\r\n\treturn costs[Math.floor(costs.length / 2)] / doctrineLabRate();\r\n}\r\n\r\n// How many Synaptic Link upgrades are already done. Deliberately NOT\r\n// counting the relay/module/factory-module enablers.\r\nfunction doctrineLabStepsDone()\r\n{\r\n\tlet n = 0;\r\n\tfor (let i = 0; i < DOCTRINE_LAB_UPGRADES.length; ++i)\r\n\t{\r\n\t\tconst r = getResearch(DOCTRINE_LAB_UPGRADES[i], me);\r\n\t\tif (r !== null && r.done) { ++n; }\r\n\t}\r\n\treturn n;\r\n}\r\n\r\nfunction doctrineWeaponsInHand()\r\n{\r\n\tlet n = 0;\r\n\tfor (let i = 0; i < DOCTRINE_WEAPON_MARKERS.length; ++i)\r\n\t{\r\n\t\tif (componentAvailable(DOCTRINE_WEAPON_MARKERS[i])) { ++n; }\r\n\t}\r\n\treturn n;\r\n}\r\n\r\n// Lab work needs THREE things: a real weapon in hand, research that has\r\n// actually gone slow, and no unspent lead over the weapon tree. That last\r\n// rule is what stops the AI chaining the whole ladder back to back -- it may\r\n// never hold more lab rungs than weapons, so each rung is paid for with a\r\n// weapon before the next is considered.\r\nfunction doctrineWantsLab()\r\n{\r\n\tconst weapons = doctrineWeaponsInHand();\r\n\tif (weapons < DOCTRINE_WEAPONS_BEFORE_LAB) { return false; }\r\n\tif (doctrineLabStepsDone() >= weapons + DOCTRINE_LAB_LEAD) { return false; }\r\n\treturn doctrineTypicalResearchSeconds() > DOCTRINE_SLOW_SECONDS;\r\n}\r\n\r\n\r\n/* ---- Scoring model -------------------------------------------------\r\n   The old design was a fixed cascade: eight ordered lists, first match\r\n   wins. Two things were wrong with it. Anything not in a list was\r\n   invisible, and -- worse -- the lists themselves hold expensive topics,\r\n   so a 4,800-point engine upgrade outranked a 300-point tank trap purely\r\n   because its list came earlier. The \'quick wins\' step meant to fix that\r\n   sat SEVENTH, behind five lists, so it almost never got a say.\r\n\r\n   Every available topic is now scored on what it is and how long it takes,\r\n   and the best score wins. The AI has options rather than a running order,\r\n   and research time is a first-class term instead of an afterthought.\r\n   --------------------------------------------------------------------- */\r\nconst DOCTRINE_HALFLIFE = 150;   // seconds; topics at this length score half\r\n\r\n// what a topic is worth before time is considered\r\nconst DOCTRINE_W_DEFENCE  = 95;\r\nconst DOCTRINE_W_WEAPON   = 90;\r\nconst DOCTRINE_W_VEHICLE  = 90;\r\nconst DOCTRINE_W_SUPPORT  = 85;\r\nconst DOCTRINE_W_AA_WANT  = 130;  // no AA yet, or enemy air in the sky\r\nconst DOCTRINE_W_AA_HAVE  = 5;    // one line is enough while nothing flies\r\nconst DOCTRINE_W_INFRA    = 70;\r\nconst DOCTRINE_W_UPG_WANT = 75;   // research has genuinely gone slow\r\nconst DOCTRINE_W_UPG_IDLE = 4;    // otherwise: near-worthless\r\nconst DOCTRINE_W_ENABLER  = 100;  // unlocks a whole unit class\r\n/* A weapon UPGRADE rung is worth much less than a weapon UNLOCK.\r\n\r\n   Round 18b switched family matching from a list of base unlocks to whole-\r\n   line prefixes. That was right for READING which family an AI prefers, but\r\n   it was also wired into the scoring, so the x1.4 favoured-family bonus\r\n   started landing on every Damage/Range/Reload/Accuracy rung as well.\r\n   Measured result: an MG rung scored 70.0 while the Heavy MG unlock scored\r\n   54.0, the Flamer 54.0 and the Cannon 30.0 -- so Nexus took Twin MG and\r\n   then ground MG rungs forever, never opening a second weapon line.\r\n\r\n   Upgrades keep the family bonus but start from a much lower base, so a\r\n   new weapon always outranks another increment of the one already held. */\r\nconst DOCTRINE_W_WPN_UPGRADE = 55;\r\nconst DOCTRINE_UPGRADE_AXIS = /^R-Wpn-.+-(Damage|Range|Reload|Accuracy|ROF|Acc)[0-9]+$/;\r\n\r\nconst DOCTRINE_W_OTHER    = 55;\r\nconst DOCTRINE_FAMILY_MULT = 1.4; // this AI\'s favoured weapon family\r\n\r\nfunction doctrineInList(id, list)\r\n{\r\n\tfor (let i = 0; i < list.length; ++i)\r\n\t{\r\n\t\tif (list[i] === id) { return true; }\r\n\t}\r\n\treturn false;\r\n}\r\n\r\nfunction doctrineWeight(id, wantLab, wantAA)\r\n{\r\n\tif (doctrineInList(id, DOCTRINE_LAB_UPGRADES))\r\n\t{\r\n\t\treturn wantLab ? DOCTRINE_W_UPG_WANT : DOCTRINE_W_UPG_IDLE;\r\n\t}\r\n\tif (doctrineInList(id, DOCTRINE_AA))\r\n\t{\r\n\t\treturn wantAA ? DOCTRINE_W_AA_WANT : DOCTRINE_W_AA_HAVE;\r\n\t}\r\n\tif (doctrineInList(id, DOCTRINE_LAB_INFRA)) { return DOCTRINE_W_INFRA; }\r\n\tif (doctrineInList(id, DOCTRINE_SUPPORT_FIRST)) { return DOCTRINE_W_SUPPORT; }\r\n\tif (doctrineInList(id, DOCTRINE_UNIT_ENABLERS)) { return DOCTRINE_W_ENABLER; }\r\n\tif (doctrineInList(id, DOCTRINE_DEF_TECH)) { return DOCTRINE_W_DEFENCE; }\r\n\tif (id.indexOf("R-Vehicle-") === 0) { return DOCTRINE_W_VEHICLE; }\r\n\tif (id.indexOf("R-Defense-") === 0) { return DOCTRINE_W_DEFENCE; }\r\n\tif (id.indexOf("R-Wpn-") === 0)\r\n\t{\r\n\t\tlet w = DOCTRINE_UPGRADE_AXIS.test(id)\r\n\t\t\t? DOCTRINE_W_WPN_UPGRADE : DOCTRINE_W_WEAPON;\r\n\t\tif (doctrineFamilyOf(id) === doctrineFamily()) { w *= DOCTRINE_FAMILY_MULT; }\r\n\t\treturn w;\r\n\t}\r\n\treturn DOCTRINE_W_OTHER;\r\n}\r\n\r\n/* Available topics, ranked by score, best first.\r\n\r\n   This used to return only the single best topic, and that was the hole the\r\n   old behaviour leaked back through: with several labs, lab 1 started the\r\n   best topic, lab 2 recomputed the SAME topic, pursueResearch refused it\r\n   (already underway), and the lab fell through to the AI\'s own hardcoded\r\n   list -- where SemperFi keeps R-Struc-Research-Upgrade09 and BoneCrusher\r\n   opens research_lasttech with it, so pursueResearch marched the whole\r\n   Synaptic ladder rung by rung. A ranked list lets every lab take the next\r\n   best thing instead of failing over. */\r\nfunction doctrineRankedTopics()\r\n{\r\n\tconst list = enumResearch();\r\n\tconst rate = doctrineLabRate();\r\n\tconst wantLab = doctrineWantsLab();\r\n\tconst wantAA = (gameTime > DOCTRINE_AA_AFTER)\r\n\t\t&& (!doctrineHasAA() || doctrineEnemyAir() > 0);\r\n\tconst ranked = [];\r\n\r\n\tfor (let i = 0; i < list.length; ++i)\r\n\t{\r\n\t\tconst topic = list[i];\r\n\t\tif (!(topic.points > 0)) { continue; }\r\n\t\tconst secs = topic.points / rate;\r\n\t\tconst score = doctrineWeight(topic.name, wantLab, wantAA)\r\n\t\t\t* (DOCTRINE_HALFLIFE / (secs + DOCTRINE_HALFLIFE));\r\n\t\tranked.push({ name: topic.name, score: score });\r\n\t}\r\n\tranked.sort(function (x, y) { return y.score - x.score; });\r\n\treturn ranked;\r\n}\r\n\r\nfunction doctrineBestTopic()\r\n{\r\n\tconst ranked = doctrineRankedTopics();\r\n\treturn ranked.length > 0 ? ranked[0] : null;\r\n}\r\n\r\n/* One call for every AI to use. Returns true when it started research on\r\n   the given lab. Callers try this FIRST and only fall back to their own\r\n   hard-coded lists if it returns false -- those lists reference topics that\r\n   DOCTRINE deleted or moved behind crates, so on their own they stall. */\r\nvar doctrineReported = false;\r\n\r\n/* One line per AI, once per game. Fires from the hook entry rather than\r\n   from the lab loop, so it reports even when every lab is busy -- the\r\n   question it answers is "did this AI load and reach its research code",\r\n   not "did it start a topic this tick". */\r\nfunction doctrineAnnounce()\r\n{\r\n\tif (!DOCTRINE_AI_REPORT || doctrineReported) { return; }\r\n\tdoctrineReported = true;\r\n\ttry\r\n\t{\r\n\t\tdebug("DOCTRINE-AI p" + me + " ai=" + DOCTRINE_AI_NAME\r\n\t\t\t+ " pers=" + doctrinePersonalityName()\r\n\t\t\t+ " family=" + DOCTRINE_FAMILY_NAMES[doctrineFamily()]\r\n\t\t\t+ " hints=" + doctrineFamilyHints().length);\r\n\t}\r\n\tcatch (e) { }\r\n}\r\n\r\nfunction doctrineResearchPick(lab)\r\n{\r\n\t// typeof-guard, not defined(): Cobra and BoneCrusher have no defined()\r\n\t// helper in scope, and a ReferenceError here would be swallowed by the\r\n\t// hooks\' try/catch -- the engine would just silently stop working.\r\n\tif (typeof lab === "undefined" || lab === null) { return false; }\r\n\r\n\tfor (let i = 0; i < DOCTRINE_DEFENCE_FIRST.length; ++i)\r\n\t{\r\n\t\tif (pursueResearch(lab, DOCTRINE_DEFENCE_FIRST[i])) { return true; }\r\n\t}\r\n\r\n\t// Walk the ranking until something sticks: with N labs, lab k simply\r\n\t// takes the k-th best topic instead of failing on a duplicate.\r\n\tconst ranked = doctrineRankedTopics();\r\n\tfor (let i = 0; i < ranked.length && i < 12; ++i)\r\n\t{\r\n\t\tif (pursueResearch(lab, ranked[i].name)) { return true; }\r\n\t}\r\n\treturn false;\r\n}\r\n\r\n\r\n/* Is anything hostile in the air right now? Anti-air turrets are subclass\r\n   "A-A GUN"/"A-A MISSILE" and can only engage VTOLs, so an AA tank built\r\n   against an empty sky is a wasted factory slot -- every AI that builds one\r\n   asks this first. Counts scavenger helicopters as well as player VTOLs. */\r\nfunction doctrineAirThreat()\r\n{\r\n\ttry { return doctrineEnemyAir() > 0; } catch (e) { return false; }\r\n}\r\n'

CRLF = chr(13) + chr(10)

def doctrine_ai_header(name, default_family):
    """Per-AI constants prepended to that AI's copy of the shared engine.

    default_family is only consulted when the AI declares no weapon
    preference the engine can read (SemperFi); -1 means "use the slot".
    """
    return (
        "// DOCTRINE per-AI identity" + CRLF
        + 'const DOCTRINE_AI_NAME = "' + name + '";' + CRLF
        + "const DOCTRINE_AI_DEFAULT_FAMILY = " + str(default_family) + ";" + CRLF
        + "const DOCTRINE_AI_REPORT = " + ("true" if TELEMETRY else "false") + ";" + CRLF
        + CRLF)


CONFIG_DICT_KEY = "_config_"   # research.cpp RESEARCH_JSON_CONFIG_DICT_KEY

# ── Research pacing ──────────────────────────────────────────────────────────
# Slow the whole research game down: labs work at 40% of vanilla speed (-60%),
# and every topic the player must BUY costs 50% more power. Topics salvaged from
# the battlefield ("captured research" — the axis + signature topics that only
# an intel crate can reveal) are exempt: recovering the hardware is the discount.
RESEARCH_SPEED_KEEP = 0.40    # A0ResearchFacility / A0ResearchModule1
RESEARCH_POWER_MULT = 2.40    # non-captured topics only (1.5 raised by +60%)
# The human pays the full 2.4x; an AI pays an effective 1.5x via a completion
# rebate in doctrine.js. Nexus's budgeting predates these prices and it simply
# stops researching when topics cost this much, which defeats the point of
# slowing the PLAYER down.
# (the rebate constant itself lives in doctrine.js, next to the handler)

# ── Weapon damage scaling ────────────────────────────────────────────────────
# THE headline balance bug. generate_tree.py derives the four damage tiers from
# AXES["Damage"]["gain"] = 0.25 via value_n = 100*g*(1+g)^(n-1) -> [25,31,39,49],
# i.e. +144% total. But DEFENCE research was left at vanilla's +270% armour and
# +270% hitpoints. Armour is SUBTRACTED per hit, so falling behind is not linear
# — it is a cliff, and damage collapses onto the minimumDamage floor. Measured
# fully-upgraded vs a Python: Light Cannon 38.7s TTK in vanilla -> 113.4s here,
# Heavy MG 64.8s -> 114.5s, while anti-tank was untouched. The late game was
# becoming "anti-tank or nothing".
#
# Vanilla cannon/rocket totalled +225%. Solving 100*((1+g)^4 - 1) = 222 gives
# g ~= 0.34, so the tier series becomes [34, 46, 61, 82]. Set explicitly here
# rather than re-deriving in generate_tree.py, so both targets get it without a
# generator re-run. Reload (-46%) is already at vanilla parity, Accuracy (+46%)
# and Range (+31%, a DOCTRINE-only axis) are left alone.
DAMAGE_TIER_VALUES = [34, 46, 61, 82]

# Crate-unlocked upgrades research 20% faster than the generator's [900, 2400,
# 5200, 10000]. They are already the scarce, earned half of the loop — you had to
# win a fight and physically recover the crate — so the lab step should not also
# be the slow half, especially with labs at 40% speed.
CAPTURED_TIME_MULT = 0.80

# VTOL bombs are not one of the 11 DOCTRINE families, so they receive no ladder
# at all — only vanilla's R-Wpn-Bomb-Damage01-03 (+25% each, +75% total, and no
# reload/range/accuracy whatsoever). Against +270% armour that is hopeless.
# Raise those three to ~+180% total rather than introduce a 12th family (which
# would also need a crate-family mapping in doctrine.js).
BOMB_TIER_VALUES = [45, 60, 75]

# Vanilla topics that survive the merge and stack ON TOP of the DOCTRINE ladder
# because they filter the same ImpactClass. Left in place they hand two families
# a large silent bonus: lasers reached +219% damage against everyone else's
# +144%, and mortars +76% accuracy against everyone else's +46%.
DOUBLE_DIP = [
    "R-Wpn-Energy-Damage01", "R-Wpn-Energy-Damage02", "R-Wpn-Energy-Damage03",
    "R-Wpn-Mortar-Acc01", "R-Wpn-Mortar-Acc02", "R-Wpn-Mortar-Acc03",
]

# ── Counter tuning: rein in anti-tank, lift the generalists ──────────────────
# The minimumDamage floor is what a weapon falls back to once armour exceeds its
# damage, so at full upgrades it IS the late-game damage number. The rebalance
# had cut it for the generalist and anti-personnel roles while raising it for
# anti-tank, which is most of why cannons needed 43s to kill even their best
# target while Scourge one-salvoed a Python.
MIN_DAMAGE_BY_EFFECT = {
    "ALL ROUNDER":    33,   # was 25 (vanilla 33) — the generalist can hurt armour again
    "ANTI PERSONNEL": 28,   # was 20 (vanilla 32) — still poor vs armour, no longer nil
    "ANTI TANK":      38,   # was 45 (vanilla 33) — still the best, less absolute
}

# Playtest: machineguns were flattening scavenger buildings. Anti-personnel is
# for infantry, not demolition — vanilla's 160% vs SOFT let a buffed MG chew
# through power generators in ~12s. Pull SOFT and MEDIUM down so structures are
# a job for cannons, artillery and bunker busters.
STRUCTURE_MODIFIER_OVERRIDE = {
    "ANTI PERSONNEL": {"SOFT": 110, "MEDIUM": 45},
}

# Counters stay clearly pronounced (150 vs ALL ROUNDER's 90) without making
# every non-AT weapon pointless against armour.
WEAPON_MODIFIER_OVERRIDE = {
    "ANTI TANK": {"Tracked": 150, "Half-Tracked": 135, "Wheeled": 130},
    # Cyborgs are "Legged". They are now cheap and quick to field, so the
    # counters that are supposed to answer them have to be unambiguous:
    # machineguns and artillery, exactly as asked.
    "ANTI PERSONNEL":  {"Legged": 190},
    "ARTILLERY ROUND": {"Legged": 165},
}

# ── The machinegun ladder ────────────────────────────────────────────────────
# Playtesting found the opening barely registers, and the cause is arithmetic:
# MG1Mk1 deals 10 damage while Body1REC (Viper, the starting body) has 10 kinetic
# armour. Armour is SUBTRACTED per hit, so raw damage is exactly ZERO and the
# starting weapon can only ever land its 28% minimum-damage floor — a Viper took
# 22.2s to kill another Viper. Both sides open with Viper + MG, so that single
# interaction defined the whole early game.
#
# MG1Mk1 is the only floor-bound weapon in the game (Flamer raw 18, Rocket-Pod
# 12, Cannon 25 all penetrate), so the fix is narrow rather than global
# inflation. Damage only — cycle times, ranges and accuracy untouched. Verified
# DPS stays strictly ordered: 6.3 -> 10.4 -> 16.4 -> 18.3 -> 31.3.
#
#   MG1Mk1 light     10 -> 16   TTK vs Viper 22.2s -> 10.4s
#   MG2Mk1 twin      16 -> 22                12.4s ->  6.2s
#   MG3Mk1 heavy     26 -> 32                 5.4s ->  4.0s
#   MG4 assault      19 -> 24                 5.5s ->  3.6s
#   MG5 twin assault 28 -> 34                 2.8s ->  2.1s
#
# The late game is undisturbed: machineguns are ANTI PERSONNEL, held at 35 vs
# Tracked by the counter matrix, so fully upgraded MG3Mk1 vs a Python moves only
# 61.8s -> 49.5s — still deliberately hopeless against armour. The lift lands on
# early duels and anti-infantry work and is suppressed everywhere else.
#
# The -Pillbox emplacement versions move with their turrets. -VTOL variants are
# left alone; they carry their own separate tuning (MG3-VTOL is already 27).
MG_LINE = {
    "MG1Mk1":            {"damage": 15},
    "MG1-Pillbox":       {"damage": 15},
    "MG2Mk1":            {"damage": 20},
    "MG2-Pillbox":       {"damage": 20},
    "MG3Mk1":            {"damage": 28},
    "MG3-Pillbox":       {"damage": 28},
    "MG4ROTARYMk1":      {"damage": 22},
    "MG4ROTARY-Pillbox": {"damage": 22},
    "MG5TWINROTARY":     {"damage": 30},
}

# ── Individual weapon outliers ───────────────────────────────────────────────
# Found by comparing every family on FULL UNIT COST (body + propulsion + weapon)
# against cyborg / wheeled / tracked targets.
#
# Laser3BEAMMk1 "Flashlight" is classed ANTI PERSONNEL and beat the machinegun in
# the machinegun's own speciality — 64.4 dps vs cyborgs at unit cost 321, against
# the LATE-game MG5TWINROTARY's 45.7 at cost 335. It was also an inversion inside
# the laser ladder: at 100 damage / 20 cycle it out-damaged the dearer Pulse Laser
# (54.9 at unit 385) that is meant to succeed it. 100 -> 75 puts it just above the
# top MG, as later tech should be, and back below Pulse Laser.
#
# Missile-A-T "Scourge" was the residual from the balance audit: 96.3 dps vs
# medium tracked at unit cost 485 = 19.9 per 100 power, against Tank Killer's 4.5
# — 4.4x per power, one-salvoing a fully-upgraded Python. 360 -> 200 targets
# roughly 2-2.5x Tank Killer instead.
#
# NOTE: damage is the only safe lever for Scourge. It has numRounds 2, and the
# engine uses reloadTime as the cycle only while numRounds > 1 — dropping rounds
# to 1 would switch the cycle to firePause (14) and make it dramatically FASTER.
WEAPON_TUNING = {
    "Laser3BEAMMk1": {"damage": 75},
    "Missile-A-T":   {"damage": 200},

    # ── Cyborg weapons: the real cost of a cyborg ───────────────────────────
    # A complete MG cyborg was 75 power / 305 build points against an MG Viper's
    # 90 / 250 -- only 17% cheaper and 22% SLOWER to build, while carrying a
    # weaker gun (12 damage vs MG1Mk1's 15). The weapon is what makes them
    # expensive: CyborgChaingun cost 40 power / 160 points where MG1Mk1 costs
    # 10 / 50. Tuning the body alone would have missed this entirely.
    #
    # Roughly halved so cyborgs become the cheap, quick swarm they are supposed
    # to be. CyborgChaingun also gets MG1Mk1's damage so the cyborg version of a
    # gun is no longer strictly worse than the tank version.
    "CyborgChaingun":        {"buildPower": 18,  "buildPoints": 70,  "damage": 15},
    "CyborgFlamer01":        {"buildPower": 30,  "buildPoints": 95},
    "CyborgCannon":          {"buildPower": 38,  "buildPoints": 120},
    "CyborgRotMG":           {"buildPower": 55,  "buildPoints": 150},
    "CyborgRocket":          {"buildPower": 80,  "buildPoints": 260},
    # heavy/late cyborg weapons, same ~0.55 power / ~0.5 points scaling so the
    # line stays internally consistent into the late game
    "Cyb-Wpn-Grenade":       {"buildPower": 44,  "buildPoints": 160},
    "Cyb-Wpn-Thermite":      {"buildPower": 55,  "buildPoints": 160},
    "Cyb-Wpn-Laser":         {"buildPower": 55,  "buildPoints": 300},
    "Cyb-Wpn-Rail1":         {"buildPower": 88,  "buildPoints": 400},
    "Cyb-Wpn-Atmiss":        {"buildPower": 128, "buildPoints": 500},
    "Cyb-Hvywpn-Mcannon":    {"buildPower": 41,  "buildPoints": 150},
    "Cyb-Hvywpn-Acannon":    {"buildPower": 69,  "buildPoints": 200},
    "Cyb-Hvywpn-HPV":        {"buildPower": 83,  "buildPoints": 225},
    "Cyb-Hvywpn-TK":         {"buildPower": 110, "buildPoints": 300},
    "Cyb-Hvywpn-A-T":        {"buildPower": 129, "buildPoints": 500},
    "Cyb-Hvywpn-PulseLsr":   {"buildPower": 83,  "buildPoints": 225},
    "Cyb-Hvywpn-RailGunner": {"buildPower": 132, "buildPoints": 375},

    # ── Scavenger defences that were not worth their build cost ────────────
    # `bbaawep` is the gun on the "man on a mount" MG tower (bbaatow), which
    # DOCTRINE started building in place of A0BaBaGunTower -- the scavengers are
    # not allowed to build that one, so every attempt failed. But bbaatow is a
    # downgrade in all three respects: 18 damage against BuggyMG's 24, the
    # SLOWEST fire rate of any scavenger machinegun (firePause 7 against 4-5),
    # and a 250hp tower instead of a 400hp one.
    #
    # 18 damage is the real problem. Armour is subtracted AFTER the weapon-effect
    # modifier, so a low-damage gun is disproportionately punished: against a
    # 10-armour Viper only 7.1 of its 18 got through, and against anything
    # tracked it sat on the minimum-damage floor doing about 2 a shot. At 32 it
    # penetrates properly. Some of its unusually high accuracy is traded back for
    # that punch, so it is a hard-hitting mount rather than a laser.
    "bbaawep":         {"damage": 32, "firePause": 6, "longHit": 70, "shortHit": 85},

    # The AT-Rocket Pit is the most expensive scavenger defence in the game at
    # 500 build points, and it was the WORST anti-tank they had: two rockets and
    # then a 140-tick reload, and shortHit 30 against longHit 60 -- less accurate
    # up close than at range, which is backwards for something that cannot move.
    "BabaPitRocketAT": {"reloadTime": 80, "shortHit": 60},

    # The plain Rocket Pit costs 400 build points to deal 16 damage a shot.
    "BabaPitRocket":   {"damage": 30},

    # The scavenger flamer fires SLOWER than the standard Flame1Mk1 (firePause 25
    # against 20) for only 6 more damage, so the "scavenger" version of the
    # weapon was strictly worse than the one it is supposed to be a scrappier
    # take on.
    "BabaFlame":       {"firePause": 18},
}

# ── Scavenger structures ─────────────────────────────────────────────────────
# structure.json has no per-entry override hook of its own; this adds one.
# bbaatow replaced A0BaBaGunTower (400hp, 75 build points). At 250hp and 200
# points it took nearly three times as long to build and died far faster, so the
# scavengers' standard picket was strictly worse than the one it stood in for.
STRUCTURE_TUNING = {
    "bbaatow": {"hitpoints": 400, "buildPoints": 90},
}

# ── Cyborg chassis: cheap, quick, and FRAGILE ────────────────────────────────
# Measured before this change, a complete MG cyborg had 300 effective hit points
# against an MG Viper's 130 -- more than twice as durable, which is why they
# never felt like the disposable swarm they are meant to be.
#
# Effective HP is body hitpoints x (1 + propulsion hitpointPctOfBody/100), so the
# legs matter as much as the body. Armour matters just as much again: MG1Mk1
# deals 15, so against 12 kinetic armour it was nearly pinned to its minimum
# damage floor. At 7 it penetrates properly and machineguns do their job.
CYBORG_TUNING = {
    "CyborgLightBody": {"buildPower": 16, "buildPoints": 65,
                        "hitpoints": 120, "armourKinetic": 7},
    "CyborgHeavyBody": {"buildPower": 34, "buildPoints": 140,
                        "hitpoints": 190, "armourKinetic": 10},
}

# ── The VTOL line: reachable this side of two hours ──────────────────────────
# Measured on the shipped tree, the prerequisite closure of R-Struc-VTOLPad was
# 16 topics and 40,900 research points -- 114 minutes of a single base-rate lab
# before the first airframe flies, which is why VTOLs never showed up in a normal
# game. The three VTOL topics are halved and the factory no longer demands
# R-Vehicle-Engine03 (4,800 points, and its own prereq chain); Hover and
# Factory-Upgrade01 still gate it, so it stays a mid-game commitment rather than
# an opening move.
RESEARCH_OVERRIDE = {
    "R-Struc-VTOLFactory": {"researchPoints": 3000,
                            "requiredResearch": ["R-Struc-Factory-Upgrade01",
                                                 "R-Vehicle-Prop-Hover"]},
    "R-Vehicle-Prop-VTOL": {"researchPoints": 3000},
    "R-Struc-VTOLPad":     {"researchPoints": 1800},
}

# propulsion.json has no per-entry override hook of its own; this adds one.
PROPULSION_OVERRIDE = {
    "CyborgLegs": {"buildPower": 7, "buildPoints": 35, "hitpointPctOfBody": 35},
}

# ── Elevation: high turrets see (and shoot) further ──────────────────────────
# Weapon range lives on the WEAPON, not the structure, and 31 of the 58 weapons
# mounted on defensive structures are shared across both tall and ground-level
# buildings (Cannon1Mk1 sits on the height-1 PillBox4 AND the height-2
# WallTower02), so the range cannot simply be edited in place. Instead each
# elevated defensive structure gets its own "-Elev" variant of its weapon with
# a longer reach — exactly the pattern the game already uses for its own
# "-Pillbox" and "-VTOL" variants.
#
# Safe because: structures resolve their weapons by ID (verified in the engine
# log via getCompFromID), and NO vanilla research upgrades a weapon by Id — every
# weapon upgrade filters on ImpactClass — so a variant inherits all research
# automatically, DOCTRINE's included.
#
# Only heights 1 and 2 carry weapons; every height-3 defensive structure is a
# sensor/CB/jammer tower with no gun, so two tiers is the whole picture.
ELEVATED_RANGE_MULT = 1.15    # height >= 2 defensive structures: +15% range

# ── Scavengers as technicals ─────────────────────────────────────────────────
# Vanilla scav civilian vehicles are absurdly durable: a School Bus has 200 HP —
# the same as a Python and 3x a Viper — while carrying only 4 armour. So they
# tank through early weapons on hit points alone, yet hit softer than the player
# equivalents (BusCannon 28 vs Cannon1Mk1 35). Rebuild them as technicals:
# fragile civilian shells, harder-hitting improvised guns, poor accuracy, and
# the heavy weapons must STOP to fire.
#
# NOTE ON "less accurate while driving": the engine has no partial
# moving-accuracy stat. combat.cpp only has the hard `fireOnMove` gate — a unit
# whose weapon has fireOnMove=0 cannot fire at all while moving (it defaults to
# true when the key is absent). So "inaccurate on the move" is expressed as
# stop-to-fire on the heavy guns plus a flat accuracy cut everywhere.
#
# Playtest pass 2: the big civilian shells were still melting to machineguns, so
# the LARGER vehicles keep 85-90% of their hitpoints (bus/fire engine/van/camper
# 0.85, tractor/armoured truck 0.90) while the small technicals — jeep, buggy,
# trike — stay at 0.70 and remain proper glass cannons. Bus and fire engine also
# get their vanilla armour 4 back; a bus is a big steel box even if it is not an
# armoured vehicle.
#
# body id -> (fraction of vanilla hitpoints to KEEP, armourKinetic, armourHeat)
# HP is expressed as a fraction so the intent stays readable: civilian shells
# keep 70% (-30%), working/armoured plant keeps 80% (-20%). Armour is set
# outright, since that is where "a bus is not an armoured vehicle" lives.
SCAV_BODY = {
    # civilian shells — sheet metal, not armour:  -30% HP
    "BusBody":                     (0.85, 4, 1),   # 200 -> 140, armour 4/1 -> 2/1
    "FireBody":                    (0.85, 4, 2),   # 200 -> 140
    "ScavIcevanBody":              (0.85, 4, 2),   # 160 -> 112
    "ScavCamperBody":              (0.85, 4, 2),   # 130 ->  91
    "B2JeepBody":                  (0.70, 3, 1),   # 120 ->  84
    "B2RKJeepBody":                (0.70, 3, 1),
    "B2JeepBody-Ultimate":         (0.70, 4, 2),   # 130 ->  91
    "B2RKJeepBody-Ultimate":       (0.70, 4, 2),
    "B3body-sml-buggy01":          (0.70, 2, 1),   # 100 ->  70
    "B3bodyRKbuggy01":             (0.70, 2, 1),
    "B3body-sml-buggy01-Ultimate": (0.70, 3, 2),   # 105 ->  73
    "B3bodyRKbuggy01-Ultimate":    (0.70, 3, 2),
    "B4body-sml-trike01":          (0.70, 1, 1),   #  80 ->  56
    "B4body-sml-trike01-Ultimate": (0.70, 2, 1),   #  95 ->  66
    # Infantry are the scavengers' pressure. At 29 HP they evaporated before
    # closing: a playtest of 6 infantry vs 3 Viper MGs left the player on 97%.
    "B1BaBaPerson01":              (1.20, 2, 1),   #  29 ->  35
    "B1BaBaPerson01-Ultimate":     (1.15, 3, 2),   #  50 ->  58
    # working plant / armoured scav hardware — steel frame:  -20% HP
    "B2tractor":                   (0.90, 4, 2),   # 150 -> 120
    "B2crane1":                    (0.80, 5, 3),   # 140 -> 112
    "B2crane2":                    (0.80, 5, 3),
    "ScavTruckBody":               (0.90, 8, 5),   # 190 -> 152
    # ScavNEXUStrack / ScavNEXUSbody / infantry / choppers deliberately untouched:
    # those ARE the armoured units, and the NEXUS tank is already time-gated.
}

# weapon id -> field overrides. Only weapons carried by scav VEHICLES.
# Deliberately excluded: BabaPitRocket / BabaPitRocketAT (scav rocket-pit
# emplacements, already high DPS) and MG3Mk1 / Flame1Mk1 / Mortar1Mk1 (player
# weapons that scav structures merely borrow — changing them would hit the
# player's own arsenal).
SCAV_WEAPON = {
    # Infantry carry the scavs' volume of fire — they are 29 HP fodder, so the
    # damage is where they earn their keep. Helicopter weapons lifted too; note
    # VTOL numRounds is a MAGAZINE (100 rockets per rearm), not a salvo, so the
    # real cadence is firePause and a damage change moves DPS one-for-one.
    # light guns: keep firing on the move, but spray
    "BaBaMG":                {"damage": 18, "shortHit": 50, "longHit": 36},
    "bTrikeMG":              {"damage": 20, "shortHit": 58, "longHit": 45},
    "BJeepMG":               {"damage": 22, "shortHit": 58, "longHit": 45},
    "BuggyMG":               {"damage": 24, "shortHit": 58, "longHit": 45},
    # Improvised heavy guns: hit hard, wildly inaccurate, must stop to shoot.
    # Their VANILLA cycles are punishing — cannon 3s, rocket salvo 10s reload,
    # flamer a ludicrous 12s — and stop-to-fire compounds it, so they were barely
    # shooting at all. Tighten the cycles to make scavengers genuinely dangerous
    # while keeping the inaccuracy and the halt-before-firing tell.
    "BaBaCannon":            {"damage": 46, "shortHit": 58, "longHit": 40,
                              "fireOnMove": 0, "firePause": 24},
    "BusCannon":             {"damage": 46, "shortHit": 58, "longHit": 42,
                              "fireOnMove": 0, "firePause": 24},
    "BabaRocket":            {"damage": 34, "radiusDamage": 24,
                              "shortHit": 45, "longHit": 42, "fireOnMove": 0,
                              "reloadTime": 70},
    # 12 SECONDS between bursts made scav flamers harmless. A flamer should be a
    # continuous threat you must not stand next to; 2.5s matches the player's own
    # Flame1Mk1 (2s) while staying the cruder weapon.
    "BabaFlame":             {"damage": 34, "shortHit": 82, "longHit": 40,
                              "firePause": 25},
    # Scav rocket pits: a 12s reload is no deterrent for an emplacement. NOTE the
    # salvo trap — numRounds is 2, so reloadTime is the cycle and firePause is the
    # SPACING BETWEEN the two rockets. Changing firePause here would have fired
    # them 8s apart instead of 0.3s. reloadTime is the correct lever.
    "BabaPitRocketAT":       {"reloadTime": 140},
    # scav air — VTOLs must fire while moving, so accuracy carries the nerf
    "MG1-VTOL-SCAVS":        {"damage": 26, "shortHit": 58, "longHit": 48},
    "Rocket-VTOL-Pod-SCAVS": {"damage": 68, "shortHit": 34, "longHit": 40},
}

# IMAGE_RES_VEHICLETECH does not exist in 4.5.5 (setIconID asserts on it);
# the 9 chassis-handling topics get the droid tech icon instead.
ICON_REMAP = {"IMAGE_RES_VEHICLETECH": "IMAGE_RES_DROIDTECH"}

FAMILIES = ["MG", "Cannon", "Rocket", "Missile", "Flamer", "Mortar",
            "Howitzer", "Laser", "Rail", "AA", "EMP"]
AXES = ["Damage", "Range", "Reload", "Accuracy"]

# ── Research thumbnails ──────────────────────────────────────────────────────
# The lab button renders the 3D model named by statID (a component) or imdName
# (a structure/effect .pie); iconID is only the small category badge, and a
# topic with neither model field falls back to a blank placeholder. The
# generator emits none of these, so every topic it REPLACED lost the vanilla
# model and every new topic never had one. Restore both.
DISPLAY_FIELDS = ("statID", "imdName", "msgName", "category",
                  "subgroupIconID", "techCode")

# Representative weapon per family — the same stat vanilla uses for that
# family's own upgrade ladder (verified present in 4.5.5 and 4.7.0 weapons.json).
FAMILY_STAT = {
    "MG": "MG1Mk1",              "Cannon":   "Cannon1Mk1",
    "Rocket": "Rocket-Pod",      "Missile":  "Missile-A-T",
    "Flamer": "Flame1Mk1",       "Mortar":   "Mortar1Mk1",
    "Howitzer": "Howitzer105Mk1","Laser":    "Laser2PULSEMk1",
    "Rail": "RailGun1Mk1",       "AA":       "QuadMg1AAGun",
    "EMP": "EMP-Cannon",
}
# Vanilla's subgroup badges. Vanilla has no Range ladder, so Range borrows the
# generic upgrade badge.
AXIS_SUBGROUP = {
    "Damage":   "IMAGE_RES_GRPDAM",
    "Reload":   "IMAGE_RES_GRPROF",
    "Accuracy": "IMAGE_RES_GRPACC",
    "Range":    "IMAGE_RES_GRPUPG",
}
AXIS_CATEGORY = {"Damage": "Damage", "Reload": "ROF",
                 "Accuracy": "Accuracy", "Range": "Range"}
# Breadth certificates are doctrine, not hardware — show the research facility.
BREADTH_IMD = "blresch4.PIE"

# The remaining DOCTRINE-only topics that match no family/axis pattern.
# statID = component model, imdName = structure/effect .pie (vanilla's own).
EXTRA_MODELS = {
    "R-Comp-CommandTurret03":  {"statID": "CommandBrain01"},
    "R-Struc-Limit-Labs":      {"imdName": "blresch4.PIE"},
    "R-Sys-DataCore":          {"imdName": "ICCCCONS.PIE"},
    "R-Sys-Debrief01":         {"imdName": "ICCCCONS.PIE"},
    "R-Sys-Debrief02":         {"imdName": "ICCCCONS.PIE"},
    "R-Sys-Telemetry":         {"imdName": "ICCCCONS.PIE"},
}
# Chassis-handling topics show the archetypal body of their weight class.
CHASSIS_BODY = {"ChassisLight": "Body1REC",      # Viper
                "ChassisMedium": "Body5REC",     # Cobra
                "ChassisHeavy": "Body11ABT"}     # Python

summary = defaultdict(list)    # file -> list of markdown lines


def fail(msg):
    print(f"BUILD FAILED: {msg}")
    sys.exit(1)


def load_vanilla(z, name):
    return json.loads(z.read(f"stats/{name}"))


def build_research(van, weapon_ids, known_stats):
    doc = json.load(open(OUT / "research-doctrine.json", encoding="utf-8"))
    surplus = set(json.load(open(OUT / "surplus.json", encoding="utf-8")))

    merged = dict(van)
    replaced = sum(1 for k in doc if k in van)
    merged.update(doc)

    delete = (surplus | set(DOUBLE_DIP)) - set(doc)
    kept = surplus & set(doc)
    for tid in delete:
        merged.pop(tid, None)

    repoints = 0
    for tid, topic in merged.items():
        req = topic.get("requiredResearch")
        if not req:
            continue
        new_req = [REPOINT.get(r, r) for r in req]
        if new_req != req:
            repoints += sum(1 for a, b in zip(req, new_req) if a != b)
            # a re-point can collide with an already-present prereq; dedupe
            seen, deduped = set(), []
            for r in new_req:
                if r not in seen:
                    seen.add(r)
                    deduped.append(r)
            topic["requiredResearch"] = deduped

    # ── restore research thumbnails ──────────────────────────────────────────
    inherited = derived = 0
    for tid, topic in merged.items():
        v = van.get(tid)
        if v:                                   # replaced a vanilla topic
            for f in DISPLAY_FIELDS:
                if f in v and f not in topic:
                    topic[f] = v[f]
                    inherited += 1

    for fam in FAMILIES:
        for axis in AXES:
            for tier in range(1, 5):
                topic = merged.get(f"R-Wpn-{fam}-{axis}0{tier}")
                if topic is None:
                    continue
                before = len(topic)
                topic.setdefault("statID", FAMILY_STAT[fam])
                topic.setdefault("subgroupIconID", AXIS_SUBGROUP[axis])
                topic.setdefault("category", f"{fam} {AXIS_CATEGORY[axis]}")
                derived += len(topic) - before

    # Penetration topics ride the same family model, generic upgrade badge
    for fam in FAMILIES:
        for tier in (1, 2):
            topic = merged.get(f"R-Wpn-{fam}-Penet0{tier}")
            if topic is None:
                continue
            before = len(topic)
            topic.setdefault("statID", FAMILY_STAT[fam])
            topic.setdefault("subgroupIconID", "IMAGE_RES_GRPUPG")
            topic.setdefault("category", f"{fam} Penetration")
            derived += len(topic) - before

    for chassis, body in CHASSIS_BODY.items():
        for tier in (1, 2, 3):
            topic = merged.get(f"R-Field-{chassis}-Handling0{tier}")
            if topic is None:
                continue
            before = len(topic)
            topic.setdefault("statID", body)
            topic.setdefault("subgroupIconID", "IMAGE_RES_GRPUPG")
            topic.setdefault("category", "Chassis Handling")
            derived += len(topic) - before

    for tid, fields in EXTRA_MODELS.items():
        topic = merged.get(tid)
        if topic is None:
            continue
        before = len(topic)
        for f, val in fields.items():
            topic.setdefault(f, val)
        derived += len(topic) - before

    for n in (2, 3, 4, 5):
        topic = merged.get(f"R-Cred-Breadth0{n}")
        if topic is not None:
            before = len(topic)
            topic.setdefault("imdName", BREADTH_IMD)
            topic.setdefault("subgroupIconID", "IMAGE_RES_GRPUPG")
            topic.setdefault("category", "Combined Arms")
            derived += len(topic) - before

    # signature topics are hidden in v1, but name their own weapon anyway
    for tid, topic in merged.items():
        if tid.startswith("R-Sig-") and "statID" not in topic:
            weapon = tid[len("R-Sig-"):]
            if weapon in weapon_ids:
                topic["statID"] = weapon
                derived += 1

    # every model reference must resolve, or the button renders blank again
    bad = sorted({t["statID"] for t in merged.values()
                  if t.get("statID") and t["statID"] not in known_stats})
    if bad:
        fail(f"topics reference non-existent statID: {bad[:10]}")
    summary["research.json"].append(
        f"- thumbnails restored: {inherited} display fields (statID/imdName/msgName/"
        f"category/subgroupIconID/techCode) inherited from the vanilla topics DOCTRINE "
        f"replaces, {derived} derived for new topics (family weapon model + axis badge).")

    # The shipped AI scripts research from hardcoded id lists that still name the
    # vanilla ROF / Damage05-09 ladders DOCTRINE deletes, which makes them log
    # "pursueResearch: No such research". Put the ids back as INERT stubs: no
    # results, no prerequisites, never enabled by anyone, so they can never be
    # researched or double-dip — they exist purely so the lookup resolves.
    stub_ids = sorted(delete)
    for tid in stub_ids:
        merged[tid] = {
            "id": tid,
            "name": van[tid].get("name", tid),
            "iconID": van[tid].get("iconID", "IMAGE_RES_WEAPONTECH"),
            "researchPoints": 1,
            "researchPower": 0,
            "statID": van[tid].get("statID"),
            "imdName": van[tid].get("imdName"),
        }
        merged[tid] = {k: v for k, v in merged[tid].items() if v is not None}
    print(f"AI compatibility: {len(stub_ids)} deleted vanilla ids re-added as inert "
          f"stubs so AI research lists resolve")
    summary["research.json"].append(
        f"- {len(stub_ids)} deleted vanilla upgrade ids kept as inert stubs (no "
        f"results, never enabled) so the shipped AI scripts stop logging "
        f"'No such research' for them.")

    icon_fixes = 0
    for topic in merged.values():
        new_icon = ICON_REMAP.get(topic.get("iconID"))
        if new_icon:
            topic["iconID"] = new_icon
            icon_fixes += 1
    if icon_fixes:
        summary["research.json"].append(
            f"  - {icon_fixes} topics: invalid `IMAGE_RES_VEHICLETECH` icon -> `IMAGE_RES_DROIDTECH`")

    dangling = [(tid, r) for tid, t in merged.items()
                for r in t.get("requiredResearch", []) if r not in merged]
    if dangling:
        fail(f"{len(dangling)} dangling requiredResearch after merge: {dangling[:10]}")

    # ── v2 restructure: script-gated topics get EMPTY prereqs ────────────────
    axis_ids = {f"R-Wpn-{f}-{a}0{t}" for f in FAMILIES for a in AXES
                for t in range(1, 5)}
    stripped = 0
    for tid, topic in merged.items():
        if (tid in axis_ids or tid.startswith("R-Sig-")) and topic.get("requiredResearch"):
            del topic["requiredResearch"]
            stripped += 1

    tier_creds = [t for t in merged
                  if t.startswith("R-Cred-") and "-Tier" in t]
    for tid in tier_creds:
        del merged[tid]
    still_needed = [(tid, r) for tid, t in merged.items()
                    for r in t.get("requiredResearch", []) if r in set(tier_creds)]
    if still_needed:
        fail(f"removed tier creds still referenced: {still_needed[:5]}")

    # reachability: base-game start + everything the script can enable must
    # reach the whole tree, except signature topics (hidden by design in v1)
    start = {"R-Sys-Sensor-Turret01", "R-Wpn-MG1Mk1", "R-Sys-Engineering01",
             "R-Sys-Spade1Mk1", "R-Vehicle-Body01", "R-Vehicle-Prop-Wheels"}
    script_enabled = axis_ids | {f"R-Cred-Breadth0{n}" for n in (2, 3, 4, 5)}
    reachable, changed = set(), True
    while changed:
        changed = False
        for tid, t in merged.items():
            if tid in reachable:
                continue
            req = t.get("requiredResearch", [])
            ok = (tid in start | script_enabled) if not req \
                else all(r in reachable for r in req)
            if ok:
                reachable.add(tid)
                changed = True
    dark = {t for t in merged if t not in reachable} - {CONFIG_DICT_KEY}
    sigs = {t for t in merged if t.startswith("R-Sig-")} | set(stub_ids)
    if dark != sigs:
        fail(f"unreachable topics beyond the hidden signatures: {sorted(dark - sigs)[:10]}"
             f" / sigs unexpectedly reachable: {sorted(sigs - dark)[:10]}")

    # Restore weapon damage scaling to vanilla parity (see DAMAGE_TIER_VALUES).
    dmg_fixed = 0
    for fam in FAMILIES:
        for tier in range(1, 5):
            t = merged.get(f"R-Wpn-{fam}-Damage0{tier}")
            if t is None:
                continue
            for r in t.get("results", []):
                if r.get("parameter") in ("Damage", "RadiusDamage"):
                    r["value"] = DAMAGE_TIER_VALUES[tier - 1]
                    dmg_fixed += 1
    bomb_fixed = 0
    for tier in range(1, 4):
        t = merged.get(f"R-Wpn-Bomb-Damage0{tier}")
        if t is None:
            continue
        for r in t.get("results", []):
            if r.get("parameter") in ("Damage", "RadiusDamage", "RepeatDamage"):
                r["value"] = BOMB_TIER_VALUES[tier - 1]
                bomb_fixed += 1
    print(f"damage scaling: {dmg_fixed} tier values set to {DAMAGE_TIER_VALUES} "
          f"(+{sum(DAMAGE_TIER_VALUES)}% total, was +144%), {bomb_fixed} bomb values "
          f"-> +{sum(BOMB_TIER_VALUES)}%")
    summary["research.json"].append(
        f"- weapon damage scaling restored to vanilla parity: tiers {DAMAGE_TIER_VALUES} "
        f"= +{sum(DAMAGE_TIER_VALUES)}% total (was [25,31,39,49] = +144%, against "
        f"unchanged +270% armour/HP research); VTOL bombs raised to "
        f"+{sum(BOMB_TIER_VALUES)}%; {len(DOUBLE_DIP)} double-dipping vanilla topics deleted.")

    # Crate-unlocked (captured) topics research faster — see CAPTURED_TIME_MULT.
    faster = 0
    for tid in sorted(axis_ids):
        t = merged.get(tid)
        if t is None:
            continue
        pts = t.get("researchPoints")
        if isinstance(pts, (int, float)) and pts > 0:
            t["researchPoints"] = int(round(pts * CAPTURED_TIME_MULT))
            faster += 1
    print(f"captured research: {faster} crate-unlocked topics researched "
          f"{100 - CAPTURED_TIME_MULT * 100:.0f}% faster")
    summary["research.json"].append(
        f"- crate-unlocked upgrades research {100 - CAPTURED_TIME_MULT * 100:.0f}% faster "
        f"(researchPoints x{CAPTURED_TIME_MULT}); they are the earned half of the loop, "
        f"so the lab step should not also be the slow half.")

    # Research pacing: every topic the player must BUY costs more power.
    # "Captured research" (the axis + signature topics that only an intel crate
    # can reveal) is exempt — salvaging the hardware IS the discount.
    captured = axis_ids | {t for t in merged if t.startswith("R-Sig-")}
    powered = 0
    for tid, t in merged.items():
        if tid in captured or CONFIG_DICT_KEY == tid:
            continue
        pw = t.get("researchPower")
        if isinstance(pw, (int, float)) and pw > 0:
            t["researchPower"] = int(round(pw * RESEARCH_POWER_MULT))
            powered += 1
    print(f"research pacing: researchPower x{RESEARCH_POWER_MULT} on {powered} bought "
          f"topics, {len(captured)} captured topics left at vanilla cost")
    summary["research.json"].append(
        f"- research pacing: +{RESEARCH_POWER_MULT * 100 - 100:.0f}% researchPower on "
        f"{powered} normally-researched topics; the {len(captured)} crate-unlocked "
        f"(captured) topics keep their original cost.")

    # Drop categories the engine would reject. research.cpp's
    # isResearchListValidConnectedDependencyGraph() requires exactly ONE member
    # of a category to not be a prerequisite of any other member (the tip of a
    # single chain). Our script-gated topics carry no prerequisites at all, so
    # each is its own source and the group always fails. The engine's only
    # response is to clear the category and log an error per group, so clear it
    # here instead and keep the log clean. Thumbnails are unaffected: those come
    # from statID / subgroupIconID, not category.
    cat_groups = defaultdict(list)
    for tid, t in merged.items():
        if t.get("category"):
            cat_groups[t["category"]].append(tid)
    dropped_cats = []
    for cat, members in sorted(cat_groups.items()):
        tips = 0
        for a in members:
            is_prereq = any(a in merged[b].get("requiredResearch", []) for b in members)
            if not is_prereq:
                tips += 1
        if tips != 1:
            dropped_cats.append(f"{cat} ({len(members)})")
            for m in members:
                merged[m].pop("category", None)
    print(f"categories: {len(cat_groups)} groups, {len(dropped_cats)} dropped as "
          f"engine-invalid (would each log an error)")
    if dropped_cats:
        summary["research.json"].append(
            f"- {len(dropped_cats)} research categories removed because the engine's "
            f"connected-dependency-graph check rejects them once the topics are "
            f"script-gated: {', '.join(dropped_cats[:6])}"
            + (" ..." if len(dropped_cats) > 6 else ""))

    # Research-facility caps are owned by doctrine.js via setStructureLimits(),
    # which is documented and deterministic. R-Struc-Limit-Labs is the ONLY topic
    # in any research.json using parameter "Limit", and it could not be
    # established from the docs or data what base value its "value: 40" applies
    # to (A0ResearchFacility has no `limit` key in structure.json) nor whether
    # applyLimitSet() would override it. Strip the result so it cannot fight the
    # script; the topic still grants a lab because labLimitFor() counts it.
    labs = merged.get("R-Struc-Limit-Labs")
    if labs is not None and labs.get("results"):
        dropped = [r for r in labs["results"] if r.get("parameter") == "Limit"]
        labs["results"] = [r for r in labs["results"] if r.get("parameter") != "Limit"]
        if not labs["results"]:
            del labs["results"]
        if dropped:
            print(f"lab limits: stripped {len(dropped)} Building.Limit result from "
                  f"R-Struc-Limit-Labs (the script owns the cap)")
            summary["research.json"].append(
                "- `R-Struc-Limit-Labs`: Building.Limit result removed — research-facility "
                "caps are set by doctrine.js via setStructureLimits() instead, which is "
                "documented and deterministic.")

    # every shipped topic should render a model, exactly like vanilla does
    # (checked here, after the tier certificates are gone)
    blank = sorted(tid for tid, t in merged.items()
                   if not t.get("statID") and not t.get("imdName")
                   and not t.get("resultStructures") and tid not in stub_ids)
    van_blank = sum(1 for t in van.values() if not t.get("statID")
                    and not t.get("imdName") and not t.get("resultStructures"))
    print(f"thumbnails: {inherited} fields inherited from vanilla, {derived} derived "
          f"for new topics, {len(blank)} model-less (vanilla leaves {van_blank})")
    if blank:
        fail(f"{len(blank)} topics would render a blank button: {blank[:10]}")

    merged[CONFIG_DICT_KEY] = {"calculationMode": "improved"}

    print(f"research.json: {len(van)} vanilla + {len(doc)} doctrine "
          f"({replaced} replace) - {len(delete)} deleted "
          f"({len(kept)} surplus IDs kept: doctrine replacements) "
          f"-> {len(merged) - 1} topics, {repoints} prereqs re-pointed, 0 dangling")
    print(f"v2 restructure: {stripped} script-gated topics stripped to empty prereqs, "
          f"{len(tier_creds)} tier credentials removed, "
          f"{len(reachable)} reachable + {len(sigs)} hidden signatures = full tree")
    summary["research.json"].append(
        f"- v2: {stripped} script-gated topics (axis + signature) ship with empty "
        f"prerequisites so only intel-crate pickups reveal them; {len(tier_creds)} "
        f"tier certificates removed (tier gate lives in doctrine.js); Breadth "
        f"credentials script-enabled at 2/3/4/5 families tier-2+.")
    summary["research.json"].append(
        f"- {len(van)} vanilla topics merged with {len(doc)} DOCTRINE topics "
        f"({replaced} replaced by ID), {len(delete)} vanilla ladder topics deleted, "
        f"{repoints} superweapon prerequisites re-pointed to tier-4 DOCTRINE topics, "
        f'`"_config_": {{"calculationMode": "improved"}}` set.')
    for old, new in sorted(REPOINT.items()):
        summary["research.json"].append(f"  - prereq `{old}` -> `{new}`")
    return merged


def apply_scav_technicals(weapons, bodies):
    """Fragile civilian shells, harder-hitting inaccurate improvised guns."""
    wn = bn = 0
    for wid, fields in SCAV_WEAPON.items():
        w = weapons.get(wid)
        if w is None:
            continue
        for field, val in fields.items():
            if w.get(field) != val:
                summary["weapons.json (scav technicals)"].append(
                    f"- `{wid}`.{field}: {w.get(field, '(default)')} -> {val}")
                w[field] = val
                wn += 1
    for bid, (hp_keep, kin, heat) in SCAV_BODY.items():
        b = bodies.get(bid)
        if b is None:
            continue
        old_hp = b.get("hitpoints", 0)
        hp = int(round(old_hp * hp_keep))
        summary["body.json (scav technicals)"].append(
            f"- `{bid}`: {old_hp} HP / {b.get('armourKinetic')} kin / "
            f"{b.get('armourHeat')} heat -> {hp} ({hp_keep * 100 - 100:+.0f}%) / "
            f"{kin} / {heat}")
        b["hitpoints"], b["armourKinetic"], b["armourHeat"] = hp, kin, heat
        bn += 1

    missing_w = sorted(set(SCAV_WEAPON) - set(weapons))
    missing_b = sorted(set(SCAV_BODY) - set(bodies))
    if missing_w or missing_b:
        print(f"  note: not present in this game version -> "
              f"weapons {missing_w}, bodies {missing_b}")
    print(f"scav technicals: {wn} weapon fields retuned across "
          f"{len(SCAV_WEAPON) - len(missing_w)} weapons, "
          f"{bn} bodies made fragile")
    return weapons, bodies


def apply_cyborg_tuning(bodies):
    """Cheap, quick and fragile cyborg chassis (see CYBORG_TUNING)."""
    n = 0
    for bid, fields in CYBORG_TUNING.items():
        b = bodies.get(bid)
        if b is None:
            fail(f"cyborg body {bid} missing from body.json")
        for f, val in fields.items():
            if f not in b:
                fail(f"{bid} has no field {f} -- vanilla layout changed")
            if b[f] != val:
                summary["body.json (cyborgs)"].append(
                    f"- `{bid}`.{f}: {b[f]} -> {val}")
                b[f] = val
                n += 1
    print(f"cyborg chassis: {n} values retuned (cheaper, quicker, far more fragile)")
    return bodies


def apply_counter_tuning(weapons, modifiers):
    """Restore the generalist/AP damage floor and pull anti-tank back a little."""
    n = 0
    for wid, w in sorted(weapons.items()):
        target = MIN_DAMAGE_BY_EFFECT.get(w.get("weaponEffect"))
        if target is None or w.get("minimumDamage") == target:
            continue
        summary["weapons.json (counter tuning)"].append(
            f"- `{wid}` ({w['weaponEffect']}).minimumDamage: {w.get('minimumDamage')} -> {target}")
        w["minimumDamage"] = target
        n += 1
    m = 0
    for effect, props in WEAPON_MODIFIER_OVERRIDE.items():
        row = modifiers.get(effect)
        if row is None:
            continue
        for prop, val in props.items():
            if prop in row and row[prop] != val:
                summary["weaponmodifier.json (counter tuning)"].append(
                    f"- `{effect}` vs {prop}: {row[prop]} -> {val}")
                row[prop] = val
                m += 1
    print(f"counter tuning: minimumDamage retuned on {n} weapons, "
          f"{m} weapon-vs-propulsion modifiers pulled back")
    return weapons, modifiers


def apply_weapon_tuning(weapons):
    n = 0
    for wid, fields in WEAPON_TUNING.items():
        w = weapons.get(wid)
        if w is None:
            continue
        for f, val in fields.items():
            if w.get(f) != val:
                summary["weapons.json (outliers)"].append(
                    f"- `{wid}`.{f}: {w.get(f)} -> {val}")
                w[f] = val
                n += 1
    print(f"outlier trims: {n} values retuned "
          f"(Flashlight 100 -> 75 damage, Scourge 360 -> 200)")
    return weapons


def apply_mg_ladder(weapons):
    n = 0
    for wid, fields in MG_LINE.items():
        w = weapons.get(wid)
        if w is None:
            continue
        for f, val in fields.items():
            if w.get(f) != val:
                summary["weapons.json (MG ladder)"].append(
                    f"- `{wid}`.{f}: {w.get(f)} -> {val}")
                w[f] = val
                n += 1
    print(f"MG ladder: {n} damage values retuned (light MG 10 -> 16, heavy 17 -> 32)")
    return weapons


# The scavenger bomb truck carried BaBaMG, which reaches 960 -- so it parked at
# machinegun range and shot, and the 256-radius blast it is carrying never
# touched anything. Its gun now reaches 40 -- point-blank, far inside its own
# 256 blast radius -- so it has to drive right up to whatever it kills.
BOMB_TRUCK_GUN = "BaBaMG-Pointblank"
BOMB_TRUCK_GUN_BASE = "BaBaMG"
# 224 still let it stand off and plink. At 40 it has to be practically
# touching its target -- well inside the 256 blast it is carrying.
BOMB_TRUCK_GUN_RANGE = 40
BOMB_TRUCK_GUN_SHORT = 32


# The bomb truck has to drive INTO its target to be worth anything, and it was
# doing that in a 136 HP ice van -- it died on the approach. This is a dedicated
# shell so buffing it does not also buff every scavenger technical that shares
# the van; the scavengers get tougher suicide trucks, not tougher raiders.
BOMB_TRUCK_BODY = "ScavBomberBody"
BOMB_TRUCK_BODY_BASE = "ScavIcevanBody"
BOMB_TRUCK_BODY_HP = 340
BOMB_TRUCK_BODY_KIN = 8
BOMB_TRUCK_BODY_HEAT = 4


def apply_bomb_truck_body(bodies):
    """A reinforced ice van that can survive the run-in."""
    base = bodies.get(BOMB_TRUCK_BODY_BASE)
    if base is None:
        fail(f"{BOMB_TRUCK_BODY_BASE} missing from body.json")
    v = copy.deepcopy(base)
    v["id"] = BOMB_TRUCK_BODY
    v["name"] = "*scavenger bomb truck*"
    v["hitpoints"] = BOMB_TRUCK_BODY_HP
    v["armourKinetic"] = BOMB_TRUCK_BODY_KIN
    v["armourHeat"] = BOMB_TRUCK_BODY_HEAT
    bodies[BOMB_TRUCK_BODY] = v
    summary["body.json (scav technicals)"].append(
        f"- `{BOMB_TRUCK_BODY}` (new, bomb-truck only): {base.get('hitpoints')} -> "
        f"{BOMB_TRUCK_BODY_HP} HP, armour {base.get('armourKinetic')}/"
        f"{base.get('armourHeat')} -> {BOMB_TRUCK_BODY_KIN}/{BOMB_TRUCK_BODY_HEAT}, "
        f"so the suicide truck survives long enough to reach what it is killing.")
    print(f"bomb truck: {BOMB_TRUCK_BODY} at {BOMB_TRUCK_BODY_HP} HP "
          f"(from {BOMB_TRUCK_BODY_BASE} {base.get('hitpoints')})")
    return bodies


def apply_bomb_truck_gun(weapons):
    """A point-blank BaBaMG variant, so the bomb truck has to close."""
    base = weapons.get(BOMB_TRUCK_GUN_BASE)
    if base is None:
        fail(f"{BOMB_TRUCK_GUN_BASE} missing from weapons.json")
    v = copy.deepcopy(base)
    v["id"] = BOMB_TRUCK_GUN
    v["name"] = "Scrap Gun"
    v["longRange"] = BOMB_TRUCK_GUN_RANGE
    v["shortRange"] = BOMB_TRUCK_GUN_SHORT
    weapons[BOMB_TRUCK_GUN] = v
    summary["weapons.json (outliers)"].append(
        f"- `{BOMB_TRUCK_GUN}`: {BOMB_TRUCK_GUN_BASE} at {BOMB_TRUCK_GUN_RANGE} range "
        f"(was {base.get('longRange')}) so the scavenger bomb truck closes to "
        f"inside its own 256 blast radius instead of parking at 960 and shooting.")
    print(f"bomb truck: {BOMB_TRUCK_GUN} at {BOMB_TRUCK_GUN_RANGE} range")
    return weapons


def apply_elevation(weapons, structures):
    """Give every elevated defensive structure a longer-ranged weapon variant."""
    made, retargeted = {}, 0
    for sid in sorted(structures):
        st = structures[sid]
        if st.get("type") != "DEFENSE" or not st.get("weapons"):
            continue
        if (st.get("height") or 1) < 2:
            continue
        new_list = []
        for wid in st["weapons"]:
            base = weapons.get(wid)
            if base is None:
                new_list.append(wid)
                continue
            vid = wid + "-Elev"
            if vid not in weapons:
                v = copy.deepcopy(base)
                v["id"] = vid
                for f in ("shortRange", "longRange"):
                    if isinstance(v.get(f), (int, float)):
                        v[f] = int(round(v[f] * ELEVATED_RANGE_MULT))
                weapons[vid] = v
                made[vid] = (wid, base.get("longRange"), v.get("longRange"))
            new_list.append(vid)
            retargeted += 1
        st["weapons"] = new_list
    for vid, (wid, old, new) in sorted(made.items()):
        summary["weapons.json (elevation)"].append(
            f"- `{vid}` (from `{wid}`): range {old} -> {new}")
    print(f"elevation: {len(made)} elevated weapon variants (+{ELEVATED_RANGE_MULT * 100 - 100:.0f}% range), "
          f"{retargeted} structure weapon slots re-pointed")
    return weapons, structures


def apply_flight_speed(weapons):
    changed = 0
    for wid, w in sorted(weapons.items()):
        rule = FLIGHT_SPEED.get(w.get("weaponSubClass"))
        fs = w.get("flightSpeed")
        if not rule or not isinstance(fs, (int, float)):
            continue
        if rule[0] == "mult":
            new = int(fs * rule[1])
            if rule[2]:
                new = min(new, rule[2])
        else:
            new = rule[1]
        if new != fs:
            w["flightSpeed"] = new
            summary["weapons.json (flightSpeed)"].append(
                f"- `{wid}` ({w.get('weaponSubClass')}): {fs} -> {new}")
            changed += 1
    print(f"weapons.json: flightSpeed raised on {changed} weapons "
          f"(MG x2, cannon x1.5, rocket/missile x1.2, rail/AA -> 3200)")
    return weapons


def diff_stats(fname, van, new):
    """Record every field difference vs vanilla into the summary."""
    lines = summary[fname]
    for key in sorted(set(van) | set(new)):
        a, b = van.get(key), new.get(key)
        if a == b:
            continue
        if a is None:
            lines.append(f"- `{key}`: added")
            continue
        if b is None:
            lines.append(f"- `{key}`: removed")
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            for f in sorted(set(a) | set(b)):
                if a.get(f) != b.get(f):
                    lines.append(f"- `{key}`.{f}: {a.get(f)!r} -> {b.get(f)!r}")
        else:
            lines.append(f"- `{key}`: {a!r} -> {b!r}")


def write_summary():
    parts = [f"# DOCTRINE — stat changes vs vanilla {TARGET} (generated by build_mod.py)\n"]
    purpose = {
        "research.json": "The research tree: the DOCTRINE ratchet replaces the vanilla upgrade ladders.",
        "weapons.json (flightSpeed)": "Projectile-speed pass: bullets near-hitscan, rail fastest, arcs untouched.",
        "weapons.json (scav technicals)": "Scav vehicle guns: hit harder, aim worse, heavy ones must stop to fire.",
        "body.json (scav technicals)": "Scav civilian vehicles lose their tank-grade hit points; real armour kept.",
        "body.json (cyborgs)": "Cyborg chassis: cheaper and quicker to build, and far more fragile.",
        "propulsion.json (cyborgs)": "Cyborg legs: cheaper, and carry less of the body's hit points.",
        "weapons.json": "minimumDamage by weapon role, salvo spacing, air payload (see COMBAT.md).",
        "weaponmodifier.json": "Weapon-vs-propulsion counters made pronounced (AT crushes tanks, AP crushes cyborgs).",
        "structuremodifier.json": "Weapon-vs-structure: artillery genuinely sieges.",
        "propulsion.json": "VTOL survivability floor.",
        "structure.json (research pacing)": "Research labs run at 40% of vanilla speed.",
        "features.json": "Dropped intel crates are visible where they land.",
        "weapons.json (MG ladder)": "Heavy MG now clearly out-damages the light MG.",
        "weapons.json (outliers)": "Individual weapons that dominated their cost bracket.",
        "weapons.json (elevation)": "Elevated defensive structures get longer-ranged weapon variants.",
        "weapons.json (counter tuning)": "Damage floor restored for generalist/AP roles, anti-tank pulled back.",
        "weaponmodifier.json (counter tuning)": "Anti-tank vs armour eased so other roles stay viable.",
        "structuremodifier.json (counter tuning)": "Anti-personnel no longer demolishes buildings.",
    }
    for fname in ["research.json", "body.json (scav technicals)",
                  "body.json (cyborgs)", "propulsion.json (cyborgs)",
                  "weapons.json (scav technicals)", "weapons.json (flightSpeed)",
                  "weapons.json (MG ladder)", "weapons.json (outliers)",
                  "weapons.json (elevation)",
                  "weapons.json (counter tuning)", "weaponmodifier.json (counter tuning)",
                  "structuremodifier.json (counter tuning)",
                  "weapons.json", "weaponmodifier.json", "structuremodifier.json",
                  "propulsion.json", "structure.json (research pacing)",
                  "features.json"]:
        lines = summary.get(fname)
        if not lines:
            continue
        parts.append(f"\n## {fname}\n\n{purpose.get(fname, '')}\n")
        parts.extend(lines)
        parts.append("")
    (BUILD / "REBALANCE-SUMMARY.md").write_text("\n".join(parts), encoding="utf-8")


def main():
    if not MP_WZ.exists():
        fail(f"{MP_WZ} not found")
    if BUILD.exists():
        shutil.rmtree(BUILD)
    staging = BUILD / "staging"
    (staging / "stats").mkdir(parents=True)
    (staging / "multiplay" / "script" / "mods").mkdir(parents=True)

    with zipfile.ZipFile(MP_WZ) as z:
        van_research = load_vanilla(z, "research.json")
        van_stats = {n: load_vanilla(z, n) for n in
                     ["weapons.json", "weaponmodifier.json",
                      "structuremodifier.json", "propulsion.json"]}
        van_bodies = load_vanilla(z, "body.json")
        van_structures = load_vanilla(z, "structure.json")
        with zipfile.ZipFile(MP_WZ.parent / "base.wz") as bz:
            van_features = json.loads(bz.read("stats/features.json"))
        # statID may name any component or structure — collect every legal id
        weapon_ids = set(van_stats["weapons.json"])
        known_stats = set(weapon_ids)
        for name in ["body.json", "brain.json", "construction.json", "ecm.json",
                     "propulsion.json", "repair.json", "sensor.json",
                     "structure.json"]:
            try:
                known_stats |= set(load_vanilla(z, name))
            except KeyError:
                pass

    # research.json — merged
    merged = build_research(van_research, weapon_ids, known_stats)
    # ---- Weapon UNLOCKS must not sit behind crate-only topics -------------
    # The design brief was that artifacts unlock UPGRADES. What actually
    # shipped had it backwards for 37 topics: the vanilla weapon-unlock topics
    # still list their old prerequisite, and DOCTRINE repurposed exactly those
    # IDs into crate-only axis topics. So:
    #     R-Wpn-Cannon1Mk1  (Light Cannon)      needs R-Wpn-MG-Damage01
    #     R-Wpn-Rocket02-MRL(Mini-Rocket Array) needs R-Wpn-Rocket-Damage01
    #     R-Wpn-Rocket01-LtAT (Lancer)          needs R-Wpn-Rocket-Damage02
    # At the measured crate rate (~3 a game) that freezes every player and AI
    # on the starting machinegun for the whole match, and is why the AI never
    # fields mini-rocket arrays or half-track designs -- every half-track
    # template in Nexus's list pairs the propulsion with a crate-locked weapon.
    #
    # Axis topics are therefore removed from every prerequisite list. Where that
    # empties a list, the topic is re-anchored onto the same family's own
    # unlock chain at matching depth (tier 1 -> that family's first weapon,
    # tier 4 -> its fourth), so progression keeps its shape and its ordering --
    # it is just researchable again. Crates still gate the four upgrade axes,
    # which is what they were always meant to gate.
    AXIS_RE = re.compile(r"^R-Wpn-(.+)-(Damage|Range|Reload|Accuracy)0([1-9])$")
    FALLBACK_ANCHOR = "R-Sys-Engineering01"

    # family -> its unlock topics (those granting components), ordered by cost
    fam_chain = {}
    for k, v in merged.items():
        if AXIS_RE.match(k) or not (v.get("resultComponents") or []):
            continue
        for rk, rv in merged.items():
            m = AXIS_RE.match(rk)
            if m and m.group(1) and k.startswith("R-Wpn-" + m.group(1)):
                fam_chain.setdefault(m.group(1), set()).add(k)
                break
    for fam in fam_chain:
        fam_chain[fam] = sorted(
            fam_chain[fam],
            key=lambda t: (merged[t].get("researchPoints") or 0, t))

    repointed, stripped = 0, 0
    for k, v in merged.items():
        req = v.get("requiredResearch") or []
        ax = [r for r in req if AXIS_RE.match(r)]
        if not ax:
            continue
        keep = [r for r in req if not AXIS_RE.match(r)]
        stripped += len(ax)
        if not keep:
            # deepest axis tier requested decides how far along the family
            # chain we re-anchor, so late topics stay late
            best = None
            for a in ax:
                m = AXIS_RE.match(a)
                fam, tier = m.group(1), int(m.group(3))
                chain = [c for c in fam_chain.get(fam, []) if c != k]
                if chain:
                    cand = chain[min(tier - 1, len(chain) - 1)]
                    if best is None or (merged[cand].get("researchPoints") or 0) > (
                            merged[best].get("researchPoints") or 0):
                        best = cand
            keep = [best] if best else [FALLBACK_ANCHOR]
            repointed += 1
        v["requiredResearch"] = keep
    # Re-anchoring can pair two topics of the same family that each end up
    # pointing at the other (RailGun02 <-> RailGun03 in practice). Break any
    # such cycle by dropping the back-edge to the cheaper topic.
    def _reaches(start, goal, seen=None):
        seen = seen or set()
        if start in seen:
            return False
        seen.add(start)
        for r in (merged.get(start, {}).get("requiredResearch") or []):
            if r == goal or _reaches(r, goal, seen):
                return True
        return False

    broken = 0
    for k, v in merged.items():
        req = v.get("requiredResearch") or []
        keep2 = [r for r in req if not (r in merged and _reaches(r, k))]
        if len(keep2) != len(req):
            broken += len(req) - len(keep2)
            v["requiredResearch"] = keep2 or [FALLBACK_ANCHOR]
    if broken:
        print(f"tech tree: broke {broken} circular prerequisite(s) from re-anchoring")

    # ---- Lab ladder first: make it researchable, then gate weapons on it ---
    # The lab upgrades were themselves behind Breadth credentials, which need
    # crates -- so gating weapons on them would have re-introduced exactly the
    # crate dependency the pass above just removed. Upgrade01-03 are re-anchored
    # onto the research module instead, giving one clean researchable spine:
    #     Research Module -> Upgrade01 -> Upgrade02 -> Upgrade03 -> 04..09
    LAB_SPINE = ["R-Struc-Research-Module", "R-Struc-Research-Upgrade01",
                 "R-Struc-Research-Upgrade02", "R-Struc-Research-Upgrade03"]
    for i in range(1, len(LAB_SPINE)):
        cur = merged.get(LAB_SPINE[i])
        if cur is None:
            fail(f"lab ladder: {LAB_SPINE[i]} missing")
        cur["requiredResearch"] = [LAB_SPINE[i - 1]]

    # Now gate expensive component unlocks behind that spine. Rule of thumb from
    # the brief: the dearer the topic, the deeper the lab requirement it needs.
    # Without this a 14,400-point weapon is technically available from minute one
    # and simply takes ~80 minutes to finish at base lab speed, which reads as
    # "the tree is stuck" rather than as a decision.
    LAB_BANDS = [(30000, "R-Struc-Research-Upgrade03"),
                 (15000, "R-Struc-Research-Upgrade02"),
                 (7000,  "R-Struc-Research-Upgrade01"),
                 (3000,  "R-Struc-Research-Module")]
    LAB_SET = set(LAB_SPINE)

    def _needs(topic, goal, seen=None):
        seen = seen or set()
        if topic in seen:
            return False
        seen.add(topic)
        for r in (merged.get(topic, {}).get("requiredResearch") or []):
            if r == goal or _needs(r, goal, seen):
                return True
        return False

    gated_counts = {}
    for k, v in merged.items():
        if k in LAB_SET or not (v.get("resultComponents") or []):
            continue
        pts = v.get("researchPoints") or 0
        for threshold, lab in LAB_BANDS:
            if pts >= threshold:
                req = v.get("requiredResearch") or []
                # skip if it already depends on this lab tier (or deeper)
                if lab not in req and not any(_needs(r, lab) or r == lab for r in req):
                    v["requiredResearch"] = req + [lab]
                    gated_counts[lab] = gated_counts.get(lab, 0) + 1
                break
    total_gated = sum(gated_counts.values())
    print(f"tech tree: {total_gated} expensive unlocks gated behind the lab ladder "
          + ", ".join(f"{k.split('-')[-1]}={v}" for k, v in sorted(gated_counts.items())))
    summary["research.json"].append(
        f"- **Advanced weapons now require lab upgrades.** The lab ladder itself is "
        f"re-anchored off the Research Module (it was behind crate-dependent Breadth "
        f"credentials), giving a researchable spine; {total_gated} expensive component "
        f"unlocks then gate on it by cost -- 3k+ needs the Module, 7k+ Upgrade01, "
        f"15k+ Upgrade02, 30k+ Upgrade03. Lancer, Assault Gun and the rail guns sit "
        f"behind real research infrastructure instead of an 80-minute wait.")

    # ---- Vehicle tech must not hang on Breadth credentials ----------------
    # R-Vehicle-Metals01 required R-Cred-Breadth03 (a crate credential), and
    # Tracks, Body08 and Body11 all chain through Metals02 -> Metals01 -- so the
    # entire heavier-vehicle line was crate-locked, which is why every army
    # stayed wheeled Vipers however far the weapons got. Same disease as the
    # round-5 weapon unlocks, same cure: each Metals/Armor rung with a Breadth
    # prerequisite is re-anchored onto the previous rung of its own ladder
    # (the first rung onto Engine01). Breadth keeps gating the rest of the
    # infrastructure tree as designed.
    veh_re = re.compile(r"^R-Vehicle-(Metals|Armor-Heat)0?(\d+)$")
    veh_fixed = 0
    for k, v in merged.items():
        m = veh_re.match(k)
        if not m:
            continue
        req = v.get("requiredResearch") or []
        if not any(r.startswith("R-Cred-Breadth") for r in req):
            continue
        fam_v, num = m.group(1), int(m.group(2))
        if num > 1:
            prev = f"R-Vehicle-{fam_v}0{num - 1}" if num - 1 < 10 else f"R-Vehicle-{fam_v}{num - 1}"
            anchor_t = prev if prev in merged else "R-Vehicle-Engine01"
        elif fam_v == "Armor-Heat":
            anchor_t = "R-Vehicle-Metals03" if "R-Vehicle-Metals03" in merged else "R-Vehicle-Engine01"
        else:
            anchor_t = "R-Vehicle-Engine01"
        v["requiredResearch"] = [r for r in req if not r.startswith("R-Cred-Breadth")] or [anchor_t]
        if anchor_t not in v["requiredResearch"] and not v["requiredResearch"]:
            v["requiredResearch"] = [anchor_t]
        veh_fixed += 1
    print(f"tech tree: {veh_fixed} vehicle Metals/Armor rungs freed from Breadth credentials")
    summary["research.json"].append(
        f"- **Vehicle tech freed from crates.** {veh_fixed} Metals/Thermal-Armor "
        f"rungs required Breadth credentials, locking Tracks, Body08 and Body11 "
        f"behind crate luck -- every army stayed wheeled Vipers. Each rung now "
        f"anchors on the previous rung of its own ladder.")

    # ---- Chassis Handling must follow the body it handles ------------------
    # generate_tree.py gave all three tier-1 Chassis Handling topics the same
    # prerequisite (R-Sys-Debrief01), so Light, Medium and Heavy appeared side
    # by side in the lab -- and Heavy Chassis Handling was researchable long
    # before any heavy body existed. Each line now hangs off the cheapest body
    # unlock of its own size class, which is the thing it actually handles.
    # (Tiers II and III already chain off tier I correctly.)
    CHASSIS_ANCHOR = {
        "R-Field-ChassisLight-Handling01":  "R-Vehicle-Body01",   # Viper
        "R-Field-ChassisMedium-Handling01": "R-Vehicle-Body05",   # Cobra
        "R-Field-ChassisHeavy-Handling01":  "R-Vehicle-Body11",   # Python
    }
    chassis_fixed = []
    for topic, body_topic in CHASSIS_ANCHOR.items():
        if topic not in merged:
            continue
        if body_topic not in merged:
            fail(f"chassis anchor {body_topic} missing from the tree")
        old_req = merged[topic].get("requiredResearch") or []
        merged[topic]["requiredResearch"] = [body_topic]
        chassis_fixed.append(f"{topic.split('-')[2]}: {old_req} -> [{body_topic}]")
    if chassis_fixed:
        print(f"tech tree: {len(chassis_fixed)} Chassis Handling lines anchored on "
              f"their own body class")
        summary["research.json"].append(
            "- **Chassis Handling now follows its body.** All three tier-1 lines "
            "shared one prerequisite, so Light/Medium/Heavy showed up together and "
            "Heavy was researchable before any heavy body existed. Each line now "
            "requires the first body of its own size class (Viper / Cobra / Python).")

    # ---- Late game must not dead-end on a crate credential -----------------
    # An audit of all 119 component unlocks found 11 unreachable without crates,
    # and every one traced to a SINGLE edge:
    #     R-Struc-Factory-Upgrade01  requires  R-Cred-Breadth03
    # Breadth credentials are script-granted only after N weapon families have a
    # tier-1 axis researched, i.e. N crates. That one edge gated:
    #     Factory-Upgrade01 -> VTOL Factory -> VTOL Propulsion
    #         -> all five VTOL bombs
    #         -> Engine07 -> Engine08 -> Engine09
    #         -> Body10, Body13, Body14 (the top heavy chassis)
    #         -> Transporter and Super Transporter
    # So the entire air branch and the top of the body/engine ladder sat behind
    # crate luck. Same disease as the weapon unlocks (round 5) and the vehicle
    # metals (round 11).
    #
    # These are re-anchored onto the infrastructure they actually follow from.
    # R-Struc-Limit-Labs deliberately keeps its Breadth gate: DOCTRINE strips its
    # Limit result anyway and caps labs from script, so it blocks nothing.
    BREADTH_REANCHOR = {
        "R-Struc-Factory-Upgrade01": "R-Struc-Factory-Module",
        "R-Struc-Power-Upgrade01":   "R-Struc-PowerModuleMk1",
        "R-Sys-Autorepair-General":  "R-Struc-Research-Upgrade02",
    }
    breadth_fixed = 0
    for topic, new_req in BREADTH_REANCHOR.items():
        if topic not in merged:
            continue
        if new_req not in merged:
            fail(f"breadth re-anchor target {new_req} missing from the tree")
        req = merged[topic].get("requiredResearch") or []
        kept = [r for r in req if not r.startswith("R-Cred-Breadth")]
        merged[topic]["requiredResearch"] = kept + [new_req] if kept else [new_req]
        breadth_fixed += 1
    if breadth_fixed:
        print(f"tech tree: {breadth_fixed} infrastructure topics freed from Breadth "
              f"credentials (unblocks VTOLs, top bodies, engines 07-09)")
        summary["research.json"].append(
            "- **The late game no longer dead-ends on crate luck.** "
            "`R-Struc-Factory-Upgrade01` required a Breadth credential, and that "
            "one edge made the VTOL factory, VTOL propulsion, all five bombs, "
            "engines 07-09, bodies 10/13/14 and both transporters unreachable "
            "without crates. Three infrastructure topics are re-anchored on the "
            "buildings they follow from; `R-Struc-Limit-Labs` keeps its Breadth "
            "gate since it grants nothing DOCTRINE uses.")

    # ---- Cyborgs arrive earlier -------------------------------------------
    # R-Struc-Factory-Cyborg unlocks BOTH the cyborg factory and the light
    # cyborg body + legs, and it hangs off R-Sys-Engineering01 alone, so it is
    # already available early -- it was just expensive enough that nobody took
    # it. Cyborgs are now the cheap fast swarm, so their one gate is cheap too.
    CYBORG_GATE = "R-Struc-Factory-Cyborg"
    if CYBORG_GATE in merged:
        gate = merged[CYBORG_GATE]
        old_pts, old_pwr = gate.get("researchPoints"), gate.get("researchPower")
        gate["researchPoints"], gate["researchPower"] = 1000, 75
        print(f"tech tree: {CYBORG_GATE} {old_pts} -> 1000 points "
              f"({old_pwr} -> 75 power)")
        summary["research.json"].append(
            f"- **Cyborgs arrive earlier.** `{CYBORG_GATE}` costs "
            f"{old_pts} -> 1000 points ({old_pwr} -> 75 power). It unlocks the "
            f"cyborg factory, the light body and the legs in one topic.")

    # ---- A stray result was spamming the log with engine asserts -----------
    # R-Struc-Research-Upgrade03 carried a SECOND result that vanilla does not
    # have: {"class": "Building", "parameter": "ModuleResearchPoints"} with no
    # filter, so the engine applied it to every building and asserted on each
    # one lacking that parameter. A single 86-minute game logged 660 of them:
    #   Parameter "ModuleResearchPoints" does not exist in Stats[Building][...]
    # Upgrades 01, 02 and 04 each carry only the correct ResearchPoints result.
    VANILLA_BUILDING_PARAMS = set()
    for t in van_research.values():
        for r in (t.get("results") or []):
            if r.get("class") == "Building" and r.get("parameter"):
                VANILLA_BUILDING_PARAMS.add(r["parameter"])
    stray = 0
    for tid, topic in merged.items():
        results = topic.get("results")
        if not results:
            continue
        kept = [r for r in results
                if not (r.get("class") == "Building"
                        and r.get("parameter") not in VANILLA_BUILDING_PARAMS)]
        if len(kept) != len(results):
            dropped = [r.get("parameter") for r in results if r not in kept]
            print(f"research: {tid} dropped stray Building result(s) {dropped}")
            summary["research.json"].append(
                f"- `{tid}`: removed a `Building` result for "
                f"`{', '.join(str(d) for d in dropped)}`, a parameter no vanilla "
                f"topic sets. Unfiltered, it made the engine assert once per "
                f"building that lacks it -- 660 log lines in one game.")
            topic["results"] = kept
            stray += len(results) - len(kept)
    if stray:
        print(f"research: {stray} stray Building result(s) removed")

    # Re-anchoring changes prerequisite edges, which can break a category's
    # connected-dependency-graph (the engine wants exactly one chain tip per
    # category). The same validation runs earlier in the build; re-run it here
    # over the new edges or the engine logs an error per broken group --
    # "Bomb Damage" was exactly that.
    cat_groups2 = defaultdict(list)
    for tid, t in merged.items():
        if t.get("category"):
            cat_groups2[t["category"]].append(tid)
    recheck = []
    for cat, members in sorted(cat_groups2.items()):
        tips = sum(1 for a in members
                   if not any(a in merged[b].get("requiredResearch", []) for b in members))
        if tips != 1:
            recheck.append(f"{cat} ({len(members)})")
            for m in members:
                merged[m].pop("category", None)
    if recheck:
        print(f"categories: {len(recheck)} further group(s) cleared after "
              f"re-anchoring: {', '.join(recheck)}")

    dangling = sorted({r for v in merged.values()
                       for r in (v.get("requiredResearch") or [])
                       if r not in merged})
    if dangling:
        fail(f"unlock re-point produced dangling prerequisites: {dangling[:8]}")
    print(f"tech tree: {stripped} crate-only prerequisites removed from unlock "
          f"topics, {repointed} re-anchored onto their family's own chain")
    summary["research.json"].append(
        f"- **Weapon unlocks no longer sit behind crates.** {stripped} crate-only "
        f"axis prerequisites were removed from unlock topics ({repointed} of them "
        f"re-anchored onto the same family's weapon chain at matching depth). "
        f"Light Cannon needed an MG crate, Mini-Rocket Array a rocket crate and "
        f"Lancer two -- at ~3 crates a game that froze everyone on the starting "
        f"machinegun. Crates now gate the four upgrade axes only, as designed.")

    n_ro = 0
    for rid, fields in RESEARCH_OVERRIDE.items():
        r = merged.get(rid)
        if r is None:
            fail(f"RESEARCH_OVERRIDE: {rid} missing from research.json")
        for f, val in fields.items():
            if r.get(f) != val:
                summary["research.json"].append(
                    f"- `{rid}`.{f}: {r.get(f)} -> {val}")
                r[f] = val
                n_ro += 1
    print(f"vtol line: {n_ro} values retuned "
          f"(factory/prop 6000 -> 3000, pad 3600 -> 1800, Engine03 gate dropped)")

    json.dump(merged, open(staging / "stats" / "research.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    # weapons.json — rebalanced + scav technicals + flight-speed pass
    # body.json — vanilla apart from the scav civilian shells
    weapons = json.load(open(OUT / "stats" / "weapons.json", encoding="utf-8"))
    bodies = copy.deepcopy(van_bodies)
    structures = copy.deepcopy(van_structures)
    weapons, bodies = apply_scav_technicals(weapons, bodies)
    bodies = apply_cyborg_tuning(bodies)
    bodies = apply_bomb_truck_body(bodies)
    weapons = apply_mg_ladder(weapons)
    weapons = apply_weapon_tuning(weapons)
    weapons = apply_bomb_truck_gun(weapons)
    weapons = apply_flight_speed(weapons)
    # elevation LAST, so the variants inherit every earlier weapon change
    weapons, structures = apply_elevation(weapons, structures)
    json.dump(weapons, open(staging / "stats" / "weapons.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    json.dump(bodies, open(staging / "stats" / "body.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    # summary section for the non-flightSpeed rebalance (flightSpeed has its own
    # section) — diff against vanilla with flightSpeed masked back to vanilla
    masked = {}
    for k, v in weapons.items():
        v = dict(v)
        if k in van_stats["weapons.json"] and "flightSpeed" in van_stats["weapons.json"][k]:
            v["flightSpeed"] = van_stats["weapons.json"][k]["flightSpeed"]
        masked[k] = v
    diff_stats("weapons.json", van_stats["weapons.json"], masked)

    # Scavenger mortar accuracy.
    # A0BaBaMortarPit fires Mortar1Mk1 -- the SAME weapon the player's own mortar
    # emplacement uses -- so its accuracy cannot be lowered directly without
    # nerfing the player's mortar too. Instead the scavengers get their own copy
    # of the weapon, identical apart from accuracy, and the pit is repointed at
    # it. Scavengers are meant to be a swarming, close-in threat, not a precise
    # artillery battery firing from off-screen.
    scav_mortar = copy.deepcopy(weapons["Mortar1Mk1"])
    scav_mortar["id"] = SCAV_MORTAR_ID
    scav_mortar["name"] = "*Scavenger Mortar*"
    scav_mortar["designable"] = 0          # never appears in the player's designer
    scav_mortar["longHit"] = SCAV_MORTAR_HIT[0]
    scav_mortar["shortHit"] = SCAV_MORTAR_HIT[1]
    scav_mortar["radiusDamage"] = SCAV_MORTAR_SPLASH
    weapons[SCAV_MORTAR_ID] = scav_mortar
    pit = structures.get("A0BaBaMortarPit")
    if pit is None or pit.get("weapons") != ["Mortar1Mk1"]:
        fail("A0BaBaMortarPit no longer carries Mortar1Mk1 -- re-check before "
             "repointing the scavenger mortar")
    pit["weapons"] = [SCAV_MORTAR_ID]
    print(f"scav mortar: accuracy {weapons['Mortar1Mk1']['longHit']}/"
          f"{weapons['Mortar1Mk1']['shortHit']} -> {SCAV_MORTAR_HIT[0]}/{SCAV_MORTAR_HIT[1]} "
          f"(own weapon, player's Mortar1Mk1 untouched)")
    summary["weapons.json"].append(
        f"- `{SCAV_MORTAR_ID}` (new, scavenger-only clone of Mortar1Mk1): "
        f"longHit {weapons['Mortar1Mk1']['longHit']} -> {SCAV_MORTAR_HIT[0]}, "
        f"shortHit {weapons['Mortar1Mk1']['shortHit']} -> {SCAV_MORTAR_HIT[1]}. "
        f"`A0BaBaMortarPit` repointed to it; the player's mortar is unchanged.")

    # structure.json — research buildings work slower
    slowed = []
    for sid in ("A0ResearchFacility", "A0ResearchModule1"):
        st = structures.get(sid)
        if st is None or "researchPoints" not in st:
            continue
        old = st["researchPoints"]
        st["researchPoints"] = max(1, int(round(old * RESEARCH_SPEED_KEEP)))
        slowed.append(f"{sid} {old}->{st['researchPoints']}")
        summary["structure.json (research pacing)"].append(
            f"- `{sid}`.researchPoints: {old} -> {st['researchPoints']} "
            f"({RESEARCH_SPEED_KEEP * 100 - 100:+.0f}%)")
    n_st = 0
    for sid, fields in STRUCTURE_TUNING.items():
        st = structures.get(sid)
        if st is None:
            fail(f"STRUCTURE_TUNING: {sid} missing from structure.json")
        for f, val in fields.items():
            if st.get(f) != val:
                summary["structure.json"].append(
                    f"- `{sid}`.{f}: {st.get(f)} -> {val}")
                st[f] = val
                n_st += 1
    print(f"scav structures: {n_st} values retuned "
          f"(bbaatow 250 -> 400 hp, 200 -> 90 build points)")

    json.dump(structures, open(staging / "stats" / "structure.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print(f"research pacing: lab speed {', '.join(slowed)}")

    # features.json — intel crates must be VISIBLE where they drop. Vanilla
    # ships Crate with startVisible 0 (campaign reveals artifacts by script),
    # which is why a dropped crate could go unnoticed.
    features = copy.deepcopy(van_features)
    if "Crate" in features:
        features["Crate"]["startVisible"] = 1
        summary["features.json"].append(
            "- `Crate`.startVisible: 0 -> 1 (dropped intel is visible on the map)")
    json.dump(features, open(staging / "stats" / "features.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    # remaining rebalanced stat files — copies from out/, weaponmodifier tuned
    for name in ["weaponmodifier.json", "structuremodifier.json", "propulsion.json"]:
        data = json.load(open(OUT / "stats" / name, encoding="utf-8"))
        if name == "structuremodifier.json":
            for effect, cols in STRUCTURE_MODIFIER_OVERRIDE.items():
                row = data.get(effect)
                if row is None:
                    continue
                for col, val in cols.items():
                    if col in row and row[col] != val:
                        summary["structuremodifier.json (counter tuning)"].append(
                            f"- `{effect}` vs {col}: {row[col]} -> {val}")
                        row[col] = val
        if name == "propulsion.json":
            for pid, fields in PROPULSION_OVERRIDE.items():
                row = data.get(pid)
                if row is None:
                    fail(f"propulsion {pid} missing from propulsion.json")
                for f, val in fields.items():
                    if f not in row:
                        fail(f"{pid} has no field {f} -- vanilla layout changed")
                    if row[f] != val:
                        summary["propulsion.json (cyborgs)"].append(
                            f"- `{pid}`.{f}: {row[f]} -> {val}")
                        row[f] = val
        if name == "weaponmodifier.json":
            weapons, data = apply_counter_tuning(weapons, data)
            json.dump(weapons, open(staging / "stats" / "weapons.json", "w",
                                    encoding="utf-8"), indent=1, ensure_ascii=False)
        json.dump(data, open(staging / "stats" / name, "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False)
        diff_stats(name, van_stats[name], data)

    # Nexus defence list: swap the Heavy Machinegun BUNKER for the Heavy
    # Machinegun GUARD TOWER as its opening emplacement. GuardTower1 is not
    # referenced anywhere in the shipped Nexus scripts, so granting it alone
    # would leave the AI building nothing at all. This is a verbatim copy of the
    # target version's own file with ONE string literal changed, taken from that
    # version's mp.wz so it can never drift out of sync.
    NEXUS_DEFS = "multiplay/skirmish/nexus_standards/buildDefinitions.js"
    with zipfile.ZipFile(MP_WZ) as z:
        nexus_src = z.read(NEXUS_DEFS).decode("utf-8")
    marker = "STANDARD_BASIC_DEFENSES"
    start = nexus_src.index(marker)
    end = nexus_src.index("];", start)
    block = nexus_src[start:end]
    if '"PillBox1"' not in block:
        fail("Nexus STANDARD_BASIC_DEFENSES no longer opens with PillBox1 — "
             "re-check the AI defence list before shipping an override")
    patched = nexus_src[:start] + block.replace('"PillBox1"', '"GuardTower1"', 1) + nexus_src[end:]

    # Difficulty gradient, applied from inside the AI's own script instance.
    # It cannot be done from doctrine.js: in the rules context
    # playerData[p].difficulty reports a flat 2 (MEDIUM) for every AI player no
    # matter what the lobby or challenge file says (verified by dumping it). The
    # `difficulty` global, however, IS that AI's real setting inside its own
    # script instance, and this file is included into it -- so the AI configures
    # itself. Intent: ultimate scavengers should roll an Easy or Medium AI,
    # press a Hard one, and lose to an Insane one.
    patched += (DIFFICULTY_GRADIENT_JS
                .replace("%DEBUG%", "true" if TELEMETRY else "false")
                .replace("%FORCE%", str(FORCE_DIFF)))
    nexus_dir = staging / "multiplay" / "skirmish" / "nexus_standards"
    nexus_dir.mkdir(parents=True, exist_ok=True)
    # newlines: the vanilla file is CRLF, and on Windows the default
    # translation would turn each into CRCRLF
    (nexus_dir / "buildDefinitions.js").write_text(patched, encoding="utf-8", newline="")
    print("nexus AI: STANDARD_BASIC_DEFENSES PillBox1 -> GuardTower1 "
          "(1 literal changed in an otherwise verbatim copy)")
    summary["research.json"].append(
        "- Nexus AI `buildDefinitions.js` overridden with a one-literal change: its "
        "opening emplacement is the Heavy Machinegun Guard Tower instead of the Bunker.")

    # Nexus production loop bug. In produceGroundUnits/produceCyborgs/
    # produceVtols the per-factory guard `if (busy || low power) return;` sits
    # INSIDE the factory loop -- it aborts the whole pass at the first busy
    # factory, so factories 2..N only ever produce when factory 1 happens to be
    # idle. With the factory allowance raised to 4 this mattered even more. The
    # power check stays a return (it is global); busy/unbuilt becomes continue.
    NEXUS_PROD = "multiplay/skirmish/nexus_includes/production.js"
    with zipfile.ZipFile(MP_WZ) as z:
        prod_src = z.read(NEXUS_PROD).decode("utf-8")
    prod_pat = re.compile(
        r"if \((\w+)\.status !== BUILT \|\| !structureIdle\(\1\) "
        r"\|\| getRealPower\(me\) < LOW_POWER\)\r?\n(\t+)\{\r?\n\t+return;\r?\n\t+\}")
    def _fix_prod(m):
        v, ind = m.group(1), m.group(2)
        nl = "\r\n"
        return (f"if (getRealPower(me) < LOW_POWER){nl}{ind}{{{nl}{ind}\treturn;{nl}{ind}}}{nl}{nl}"
                f"{ind}if ({v}.status !== BUILT || !structureIdle({v})){nl}{ind}{{{nl}{ind}\tcontinue;{nl}{ind}}}")
    prod_patched, nfix = prod_pat.subn(_fix_prod, prod_src)
    if nfix != 3:
        fail(f"Nexus production.js: expected 3 early-return factory guards, found {nfix}")
    prod_dir = staging / "multiplay" / "skirmish" / "nexus_includes"
    prod_dir.mkdir(parents=True, exist_ok=True)
    (prod_dir / "production.js").write_text(prod_patched, encoding="utf-8", newline="")
    print("nexus AI: production no longer stalls at the first busy factory (3 loops fixed)")
    summary["research.json"].append(
        "- Nexus `production.js`: the per-factory busy check aborted the whole "
        "production pass at the first busy factory; factories 2..N now produce "
        "independently (ground, cyborg and VTOL loops).")

    # Nexus attack threshold. doAllOutAttack() refuses to attack with fewer
    # than 10 units in the attacker group. Under DOCTRINE the AI's army peaks
    # around 8-16 and is constantly whittled by scavengers, so it crosses 10
    # once, attacks, takes losses, and then never attacks again -- the reported
    # "attacks once then gives up". 5 keeps a sanity floor but lets it keep
    # pressing with the army it can actually sustain.
    NEXUS_TACTICS = "multiplay/skirmish/nexus_includes/tactics.js"
    with zipfile.ZipFile(MP_WZ) as z:
        tac_src = z.read(NEXUS_TACTICS).decode("utf-8")
    if "const MIN_ATTACKERS = 10;" not in tac_src:
        fail("Nexus tactics.js MIN_ATTACKERS is no longer 10 -- re-check")
    tac_patched = tac_src.replace("const MIN_ATTACKERS = 10;",
                                  "const MIN_ATTACKERS = 5;", 1)
    tac_dir = staging / "multiplay" / "skirmish" / "nexus_includes"
    tac_dir.mkdir(parents=True, exist_ok=True)
    print("nexus AI: attack threshold MIN_ATTACKERS 10 -> 5")
    summary["research.json"].append(
        "- Nexus `tactics.js` `MIN_ATTACKERS`: 10 -> 5, so the AI keeps attacking "
        "with the army it can sustain instead of attacking once at peak strength "
        "and then never again.")

    # Nexus production throughput. buildMaxsBasedOnDerricks() allows only TWO
    # factories until a player holds more than 8 oil derricks. Measured across
    # every headless run, the AI held 3-6 derricks -- so it sat on two factories
    # for the whole game while banking 2000-3000 power it had no way to spend.
    # That, not power and not the personality, is the ceiling on how fast it can
    # field an army. The curve is shifted down so a normal 3-6 derrick holding
    # supports four factories instead of two. Only the four integers change; the
    # surrounding logic and the getStructureLimit() guard are untouched, so
    # DOCTRINE's own research-lab cap still applies to labs.
    NEXUS_BUILD = "multiplay/skirmish/nexus_includes/build.js"
    with zipfile.ZipFile(MP_WZ) as z:
        build_src = z.read(NEXUS_BUILD).decode("utf-8")
    fn_at = build_src.find("function buildMaxsBasedOnDerricks")
    if fn_at < 0:
        fail("Nexus build.js has no buildMaxsBasedOnDerricks -- re-check")
    fn_end = build_src.index("return amount;", fn_at)
    fn = build_src[fn_at:fn_end]
    spots = list(re.finditer(r"amount = (\d+);", fn))
    if len(spots) != len(FACTORY_ALLOWANCE):
        fail(f"Nexus buildMaxsBasedOnDerricks has {len(spots)} amount "
             f"assignments, expected {len(FACTORY_ALLOWANCE)}")
    new_fn, last = "", 0
    for spot, want in zip(spots, FACTORY_ALLOWANCE):
        new_fn += fn[last:spot.start()] + f"amount = {want};"
        last = spot.end()
    new_fn += fn[last:]
    build_patched = build_src[:fn_at] + new_fn + build_src[fn_end:]
    build_dir = staging / "multiplay" / "skirmish" / "nexus_includes"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "build.js").write_text(build_patched, encoding="utf-8", newline="")
    print("nexus AI: factory/lab allowance 2/3/4/5 -> 4/5/5/5 by derrick band")
    # Insane gets a factory allowance of its own, ignoring the derrick curve
    # entirely, so it reaches its production ceiling in the opening minutes
    # instead of waiting on oil it may never hold. Only the FACTORY line uses
    # it; labs, repair bays and VTOL pads stay on the shared derrick amount.
    # 4.7.0 names the shared allowance AMOUNT, 4.5.5 names it amount -- match
    # whichever this version uses rather than assuming.
    fac_re = re.compile(
        r"(currStructCount < getStructureLimit\(BASE_STRUCTURES\.factories, me\)"
        r" && currStructCount < )(AMOUNT|amount)( && "
        r"grabTrucksAndBuild\(BASE_STRUCTURES\.factories)")
    build_patched, nfac = fac_re.subn(
        lambda m: m.group(1) + "doctrineFactoryAllowance()" + m.group(3),
        build_patched, count=1)
    if nfac != 1:
        fail("Nexus build.js factory line in buildMaximums() not found -- re-check")

    fac_fn = ("function doctrineFactoryAllowance()" + CRLF
              + "{" + CRLF
              + TAB_JS + "// DOCTRINE_FORCED_DIFF is 0 in every real build; it lets the" + CRLF
              + TAB_JS + "// headless harness (which ignores per-player difficulty) test this." + CRLF
              + TAB_JS + "const d = (typeof DOCTRINE_FORCED_DIFF !== " + Q + "undefined" + Q
              + " && DOCTRINE_FORCED_DIFF) ? DOCTRINE_FORCED_DIFF : difficulty;" + CRLF
              + CRLF
              + TAB_JS + "if (d === INSANE) { return " + str(INSANE_FACTORIES) + "; }" + CRLF
              + TAB_JS + "if (d === HARD) { return " + str(HARD_FACTORIES) + "; }" + CRLF
              + CRLF
              + TAB_JS + "return buildMaxsBasedOnDerricks();" + CRLF
              + "}" + CRLF + CRLF)
    build_patched = build_patched.replace("function buildMaximums()", fac_fn + "function buildMaximums()", 1)
    print(f"nexus AI: factory allowance -- Insane {INSANE_FACTORIES}, Hard "
          f"{HARD_FACTORIES}, others by derrick curve")
    summary["research.json"].append(
        f"- Nexus `build.js`: factories get their own allowance -- Insane "
        f"{INSANE_FACTORIES}, Hard {HARD_FACTORIES}, ignoring the derrick curve, "
        f"so a high-difficulty AI reaches its production ceiling in the opening "
        f"minutes. Labs/repair/VTOL keep the shared derrick amount.")

    summary["research.json"].append(
        "- Nexus `build.js` `buildMaxsBasedOnDerricks()`: factory/lab allowance "
        "raised so a 3-6 derrick holding supports four factories rather than two. "
        "The AI was production-capped, not power-capped -- it banked 2000-3000 "
        "power it could not spend.")

    # Nexus builds NO defences inside its own base -- there is simply no code
    # path for it. Its three defence builders are: forward emplacements at
    # remote derricks (protectCloseDerrick -- "start being nasty"), sensor
    # towers at derricks, and mortar pits near sensors. So with the free wall
    # tech stripped, the only towers a player ever sees are the forward ones at
    # contested oil -- "builds turrets in the other bases, not his own". This
    # adds the missing path: up to 4 Guard Towers around its own base position,
    # tried FIRST in buildDefenses() so the base picket outranks everything
    # else, and before the vanilla early-return on sensor availability.
    NEXUS_BUILD2 = "multiplay/skirmish/nexus_includes/build.js"
    base_def_old = (
        "function buildDefenses()\r\n"
        "{\r\n"
        "\tif (!isStructureAvailable(BASE_STRUCTURES.sensors[0]))\r\n"
    )
    base_def_new = (
        "function baseTowerDefense()\r\n"
        "{\r\n"
        "\tif (!isStructureAvailable(\"GuardTower1\"))\r\n"
        "\t{\r\n"
        "\t\treturn false;\r\n"
        "\t}\r\n"
        "\r\n"
        "\tconst nearby = enumRange(BASE.x, BASE.y, 10, me, false).filter(function (o) {\r\n"
        "\t\treturn o.type === STRUCTURE && o.stattype === DEFENSE;\r\n"
        "\t});\r\n"
        "\r\n"
        "\tif (nearby.length >= 4)\r\n"
        "\t{\r\n"
        "\t\treturn false;\r\n"
        "\t}\r\n"
        "\r\n"
        "\treturn grabTrucksAndBuild(\"GuardTower1\", BASE, 10, 0);\r\n"
        "}\r\n"
        "\r\n"
        "function buildDefenses()\r\n"
        "{\r\n"
        "\tif (baseTowerDefense())\r\n"
        "\t{\r\n"
        "\t\treturn;\r\n"
        "\t}\r\n"
        "\r\n"
        "\tif (!isStructureAvailable(BASE_STRUCTURES.sensors[0]))\r\n"
    )
    # build.js is already patched above (factory allowance + production is a
    # different file); apply on the patched build source, not the vanilla one.
    if base_def_old not in build_patched:
        fail("Nexus build.js buildDefenses() head not found -- re-check")
    build_patched = build_patched.replace(base_def_old, base_def_new, 1)

    # Proactive base AA. Nexus only ever places AA reactively, after already
    # being hit from the air (buildAANearLoc via eventAttacked). Two sites go
    # up around the base once any AA structure is researched.
    aa_fn = ("function baseAADefense()\r\n"
             "{\r\n"
             "\tconst AA_STAT = bestStructureIn(STANDARD_ANTI_AIR_DEFENSES);\r\n"
             "\r\n"
             "\tif (!defined(AA_STAT))\r\n"
             "\t{\r\n"
             "\t\treturn false;\r\n"
             "\t}\r\n"
             "\r\n"
             "\tlet aaCount = 0;\r\n"
             "\tfor (let i = 0; i < STANDARD_ANTI_AIR_DEFENSES.length; ++i)\r\n"
             "\t{\r\n"
             "\t\taaCount += countStruct(STANDARD_ANTI_AIR_DEFENSES[i]);\r\n"
             "\t}\r\n"
             "\r\n"
             "\tif (aaCount >= 2)\r\n"
             "\t{\r\n"
             "\t\treturn false;\r\n"
             "\t}\r\n"
             "\r\n"
             "\treturn grabTrucksAndBuild(AA_STAT, BASE, 10, 0);\r\n"
             "}\r\n"
             "\r\n"
             "function buildDefenses()\r\n")
    if "function buildDefenses()\r\n" not in build_patched:
        fail("buildDefenses head vanished -- re-check")
    build_patched = build_patched.replace("function buildDefenses()\r\n", aa_fn, 1)
    aa_call_old = ("\tif (baseTowerDefense())\r\n"
                   "\t{\r\n"
                   "\t\treturn;\r\n"
                   "\t}\r\n")
    aa_call_new = (aa_call_old
                   + "\r\n"
                   "\tif (baseAADefense())\r\n"
                   "\t{\r\n"
                   "\t\treturn;\r\n"
                   "\t}\r\n")
    if aa_call_old not in build_patched:
        fail("baseTowerDefense call not found -- re-check")
    build_patched = build_patched.replace(aa_call_old, aa_call_new, 1)
    # Picket own derricks. All three vanilla derrick paths need something the
    # AI rarely had (sensors+mortar pits) or apply to ENEMY oil only
    # (protectCloseDerrick). One basic emplacement per owned derrick, budgeted
    # by the existing GuardTower1/PillBox1 structure limit of 4 + derricks.
    picket_fn = ("function derrickTowerDefense()\r\n"
                 "{\r\n"
                 "\tconst PICKET_STAT = bestStructureIn(STANDARD_BASIC_DEFENSES);\r\n"
                 "\r\n"
                 "\tif (!defined(PICKET_STAT))\r\n"
                 "\t{\r\n"
                 "\t\treturn false;\r\n"
                 "\t}\r\n"
                 "\r\n"
                 "\tconst derricks = enumStruct(me, BASE_STRUCTURES.derricks);\r\n"
                 "\r\n"
                 "\tfor (let i = 0, len = derricks.length; i < len; ++i)\r\n"
                 "\t{\r\n"
                 "\t\tconst d = derricks[i];\r\n"
                 "\r\n"
                 "\t\tif (threatInRange(d.x, d.y, ENEMIES, 3, false) || !safeDest(me, d.x, d.y))\r\n"
                 "\t\t{\r\n"
                 "\t\t\tcontinue;\r\n"
                 "\t\t}\r\n"
                 "\r\n"
                 "\t\tconst guarded = enumRange(d.x, d.y, 4, me, false).filter(function (o) {\r\n"
                 "\t\t\treturn o.type === STRUCTURE && o.stattype === DEFENSE;\r\n"
                 "\t\t});\r\n"
                 "\r\n"
                 "\t\tif (guarded.length >= 1)\r\n"
                 "\t\t{\r\n"
                 "\t\t\tcontinue;\r\n"
                 "\t\t}\r\n"
                 "\r\n"
                 "\t\tif (grabTrucksAndBuild(PICKET_STAT, {x: d.x, y: d.y, force: false}, 4, 0, groups.oilBuilders))\r\n"
                 "\t\t{\r\n"
                 "\t\t\treturn true;\r\n"
                 "\t\t}\r\n"
                 "\t}\r\n"
                 "\r\n"
                 "\treturn false;\r\n"
                 "}\r\n"
                 "\r\n"
                 "function baseAADefense()\r\n")
    if "function baseAADefense()\r\n" not in build_patched:
        fail("baseAADefense head vanished -- re-check")
    build_patched = build_patched.replace("function baseAADefense()\r\n", picket_fn, 1)
    picket_call_old = ("\tif (baseAADefense())\r\n"
                      "\t{\r\n"
                      "\t\treturn;\r\n"
                      "\t}\r\n")
    picket_call_new = (picket_call_old
                      + "\r\n"
                      "\tif (derrickTowerDefense())\r\n"
                      "\t{\r\n"
                      "\t\treturn;\r\n"
                      "\t}\r\n")
    if picket_call_old not in build_patched:
        fail("baseAADefense call not found -- re-check")
    build_patched = build_patched.replace(picket_call_old, picket_call_new, 1)
    # Walls. orderDroidBuild() takes a single tile and no AI ever issues
    # DORDER_LINEBUILD (they only test for it as an order state), so scripted
    # line-building is not available -- walls have to go up one segment at a
    # time. Each base emplacement gets up to two hardcrete segments beside it,
    # which is the classic tower-behind-wall shape and gives the trucks
    # something useful to spend idle time on. Capped so it cannot sprawl.
    wall_fn = ("const DOCTRINE_MAX_WALLS = 14;\r\n"
               "const DOCTRINE_WALLS_PER_DEFENCE = 2;\r\n"
               "\r\n"
               "function baseWallDefense()\r\n"
               "{\r\n"
               "\tconst WALL_STAT = \"A0HardcreteMk1Wall\";\r\n"
               "\r\n"
               "\tif (!isStructureAvailable(WALL_STAT))\r\n"
               "\t{\r\n"
               "\t\treturn false;\r\n"
               "\t}\r\n"
               "\r\n"
               "\tif (countStruct(WALL_STAT) >= DOCTRINE_MAX_WALLS)\r\n"
               "\t{\r\n"
               "\t\treturn false;\r\n"
               "\t}\r\n"
               "\r\n"
               "\tconst defences = enumRange(BASE.x, BASE.y, 12, me, false).filter(function (o) {\r\n"
               "\t\treturn o.type === STRUCTURE && o.stattype === DEFENSE;\r\n"
               "\t});\r\n"
               "\r\n"
               "\tconst STEPS = [[1, 0], [-1, 0], [0, 1], [0, -1]];\r\n"
               "\r\n"
               "\tfor (let i = 0, len = defences.length; i < len; ++i)\r\n"
               "\t{\r\n"
               "\t\tconst d = defences[i];\r\n"
               "\r\n"
               "\t\tif (!safeDest(me, d.x, d.y))\r\n"
               "\t\t{\r\n"
               "\t\t\tcontinue;\r\n"
               "\t\t}\r\n"
               "\r\n"
               "\t\tlet flanking = 0;\r\n"
               "\t\tfor (let k = 0; k < STEPS.length; ++k)\r\n"
               "\t\t{\r\n"
               "\t\t\tconst o = getObject(d.x + STEPS[k][0], d.y + STEPS[k][1]);\r\n"
               "\t\t\tif (o !== null && o.type === STRUCTURE && o.stattype === WALL)\r\n"
               "\t\t\t{\r\n"
               "\t\t\t\t++flanking;\r\n"
               "\t\t\t}\r\n"
               "\t\t}\r\n"
               "\r\n"
               "\t\tif (flanking >= DOCTRINE_WALLS_PER_DEFENCE)\r\n"
               "\t\t{\r\n"
               "\t\t\tcontinue;\r\n"
               "\t\t}\r\n"
               "\r\n"
               "\t\tfor (let k = 0; k < STEPS.length; ++k)\r\n"
               "\t\t{\r\n"
               "\t\t\tconst wx = d.x + STEPS[k][0];\r\n"
               "\t\t\tconst wy = d.y + STEPS[k][1];\r\n"
               "\r\n"
               "\t\t\tif (getObject(wx, wy) !== null || !safeDest(me, wx, wy))\r\n"
               "\t\t\t{\r\n"
               "\t\t\t\tcontinue;\r\n"
               "\t\t\t}\r\n"
               "\r\n"
               "\t\t\tif (grabTrucksAndBuild(WALL_STAT, {x: wx, y: wy, force: true}, 12, 4))\r\n"
               "\t\t\t{\r\n"
               "\t\t\t\treturn true;\r\n"
               "\t\t\t}\r\n"
               "\t\t}\r\n"
               "\t}\r\n"
               "\r\n"
               "\treturn false;\r\n"
               "}\r\n"
               "\r\n"
               "function derrickTowerDefense()\r\n")
    if "function derrickTowerDefense()\r\n" not in build_patched:
        fail("derrickTowerDefense head vanished -- re-check")
    build_patched = build_patched.replace("function derrickTowerDefense()\r\n", wall_fn, 1)
    wall_call_old = ("\tif (derrickTowerDefense())\r\n"
                     "\t{\r\n"
                     "\t\treturn;\r\n"
                     "\t}\r\n")
    wall_call_new = (wall_call_old
                     + "\r\n"
                     "\tif (baseWallDefense())\r\n"
                     "\t{\r\n"
                     "\t\treturn;\r\n"
                     "\t}\r\n")
    if wall_call_old not in build_patched:
        fail("derrickTowerDefense call not found -- re-check")
    build_patched = build_patched.replace(wall_call_old, wall_call_new, 1)
    print("nexus AI: hardcrete walls flank base emplacements (max 14)")
    summary["research.json"].append(
        "- Nexus now builds hardcrete WALLS: up to two segments flanking each "
        "base emplacement, capped at 14. Scripted line-building is impossible "
        "(orderDroidBuild takes one tile), so they go up segment by segment.")

    print("nexus AI: one emplacement per owned derrick (budgeted by the tower cap)")
    summary["research.json"].append(
        "- Nexus pickets its own oil: one basic emplacement per owned derrick, "
        "inside the existing 4+derricks tower budget. Vanilla only emplaced at "
        "ENEMY oil.")

    print("nexus AI: proactive base AA -- two sites once any AA tech is in")
    summary["research.json"].append(
        "- Nexus builds two AA sites around its base proactively once AA tech "
        "exists; vanilla only placed AA after already being bombed.")
    (build_dir / "build.js").write_text(build_patched, encoding="utf-8", newline="")
    print("nexus AI: baseTowerDefense() added -- up to 4 Guard Towers at its own base, tried first")
    summary["research.json"].append(
        "- Nexus `build.js`: new `baseTowerDefense()` step, tried first in "
        "`buildDefenses()` -- vanilla Nexus has NO code path that defends its own "
        "base, only forward emplacements at remote derricks. Up to 4 Guard "
        "Towers go up around its base position once the tower is available.")

    # Nexus was not researching at all -- production starves it.
    # doResearch() skips a lab whenever getRealPower(me) < LOW_POWER (140).
    # With the factory allowance raised the AI now spends power down to 40-100
    # continuously, so that gate is essentially always closed. Worse, the early
    # topics it would pick (R-Sys-Engineering01, R-Sys-Sensor-Turret01,
    # R-Wpn-MG1Mk1) carry NO power cost at all -- so it was refusing to start
    # free research because it was short of power it did not need to spend.
    # Measured: 3 topics available at t=20s, the same 3 still available and
    # none completed at t=900s.
    # Research gets its own much lower floor. Topics that DO cost power are
    # still paid for normally by the engine.
    NEXUS_RESEARCH = "multiplay/skirmish/nexus_includes/research.js"
    with zipfile.ZipFile(MP_WZ) as z:
        res_src = z.read(NEXUS_RESEARCH).decode("utf-8")
    # Put lab infrastructure and the favoured family ahead of the stock lists.
    chain_mark = (TAB_JS * 2 + "if ((difficulty === MEDIUM && random(100) < 10) "
                  "|| (difficulty >= HARD))")
    if chain_mark not in res_src:
        fail("Nexus research.js difficulty branch not found -- re-check")
    chain_new = (
        TAB_JS * 2 + "doctrineAnnounce();" + CRLF + CRLF
        + TAB_JS * 2 + "// DOCTRINE: the guard tower is the one hard-coded priority --" + CRLF
        + TAB_JS * 2 + "// it is the AI's only early defence and costs 600 points." + CRLF
        + TAB_JS * 2 + "// Guard tower first, then the ranked walk -- one lab takes the" + CRLF
        + TAB_JS * 2 + "// k-th best topic instead of duplicating its neighbour's pick." + CRLF
        + TAB_JS * 2 + "found = doctrineResearchPick(lab);" + CRLF + CRLF
        + TAB_JS * 2 + "if (!found && ((difficulty === MEDIUM && random(100) < 10) "
        "|| (difficulty >= HARD)))")
    res_src = res_src.replace(chain_mark, chain_new, 1)

    res_guard = "|| getRealPower(me) < LOW_POWER"
    if res_src.count(res_guard) != 1:
        fail(f"Nexus research.js: expected 1 LOW_POWER guard, found "
             f"{res_src.count(res_guard)}")
    res_patched = res_src.replace(res_guard, "|| getRealPower(me) < RESEARCH_MIN_POWER", 1)
    res_patched = doctrine_ai_header("Nexus", -1) + DOCTRINE_ENGINE_JS + res_patched
    res_dir = staging / "multiplay" / "skirmish" / "nexus_includes"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / "research.js").write_text(res_patched, encoding="utf-8", newline="")
    print("nexus AI: research power floor 140 -> 30 (it was refusing FREE research)")
    summary["research.json"].append(
        "- Nexus `research.js`: the lab loop skipped whenever power < 140, which "
        "with four factories running is almost always. The early topics cost no "
        "power at all, so it was refusing free research. Floor is now 30.")

    # Nexus never RESUMES an interrupted defence build. finishStructs() -- the
    # pass that sends trucks back to unfinished structures -- explicitly skips
    # DEFENSE and WALL stattypes. A truck chased off a half-built tower by
    # scavengers leaves it forever, and the build loop then starts a fresh one
    # elsewhere: "starts building defenses but stops and builds another without
    # finishing". The exclusion is removed; defences and walls resume like
    # everything else.
    fin_old = ("if (st.status === BUILT || st.stattype === DEFENSE || "
               "st.stattype === WALL)")
    fin_new = "if (st.status === BUILT)"
    if fin_old not in build_patched:
        fail("Nexus finishStructs() DEFENSE/WALL exclusion not found -- re-check")
    build_patched = build_patched.replace(fin_old, fin_new, 1)
    # build.js was already written by the base-tower block above; write again
    # with this change included
    (build_dir / "build.js").write_text(build_patched, encoding="utf-8", newline="")
    print("nexus AI: finishStructs() now resumes defences and walls")
    summary["research.json"].append(
        "- Nexus `build.js` `finishStructs()`: no longer skips DEFENSE/WALL, so "
        "interrupted defence constructions get finished instead of abandoned.")

    # Nexus attacks as a mob of individuals: doAllOutAttack() orders each
    # attacker at the target the moment the count passes the threshold, so they
    # arrive in a trickle and die piecemeal. Two additions, both stateless:
    #  * regroup -- if more than a third of the group is >9 tiles from the group
    #    centroid, stragglers are pulled to the centroid first and the attack
    #    waits until the group is actually together;
    #  * lanes -- the approach alternates between direct and two flanking
    #    waypoints on a two-minute cycle, so successive waves take different
    #    routes instead of funnelling down one lane.
    # 4.7.0 declares `const LEN`, 4.5.5 `var len` -- detect which identifier
    # this version uses and generate the inserted code with the same one.
    LENVAR = "LEN" if "(LEN < MIN_ATTACKERS)" in tac_patched else "len"
    tac_mark = ("\t\tif (" + LENVAR + " < MIN_ATTACKERS)\r\n\t\t{\r\n\t\t\treturn;\r\n\t\t}\r\n")
    if tac_mark not in tac_patched:
        fail("Nexus tactics.js MIN_ATTACKERS block not found -- re-check")
    regroup = (
        tac_mark + CRLF
        + "\t\t// DOCTRINE: gather before committing -- see build_mod.py" + "\r\n"
        + "\t\tlet cx = 0, cy = 0, eligible = 0;" + "\r\n"
        + "\t\tfor (let i = 0; i < " + LENVAR + "; ++i)" + "\r\n"
        + "\t\t{" + "\r\n"
        + "\t\t\tif (droids[i].order !== DORDER_RTR) { cx += droids[i].x; cy += droids[i].y; ++eligible; }" + "\r\n"
        + "\t\t}" + "\r\n"
        + "\t\tif (eligible === 0) { return; }" + "\r\n"
        + "\t\tcx = Math.floor(cx / eligible); cy = Math.floor(cy / eligible);" + "\r\n"
        + "\t\tlet far = 0;" + "\r\n"
        + "\t\tfor (let i = 0; i < " + LENVAR + "; ++i)" + "\r\n"
        + "\t\t{" + "\r\n"
        + "\t\t\tif (droids[i].order !== DORDER_RTR && distBetweenTwoPoints(cx, cy, droids[i].x, droids[i].y) > 9) { ++far; }" + "\r\n"
        + "\t\t}" + "\r\n"
        + "\t\tif (far * 3 > eligible)" + "\r\n"
        + "\t\t{" + "\r\n"
        + "\t\t\tfor (let i = 0; i < " + LENVAR + "; ++i)" + "\r\n"
        + "\t\t\t{" + "\r\n"
        + "\t\t\t\tconst d2 = droids[i];" + "\r\n"
        + "\t\t\t\tif (d2.order !== DORDER_RTR && distBetweenTwoPoints(cx, cy, d2.x, d2.y) > 9)" + "\r\n"
        + "\t\t\t\t{" + "\r\n"
        + "\t\t\t\t\torderDroidLoc(d2, DORDER_MOVE, cx, cy);" + "\r\n"
        + "\t\t\t\t}" + "\r\n"
        + "\t\t\t}" + "\r\n"
        + "\t\t\treturn;" + "\r\n"
        + "\t\t}" + "\r\n" + CRLF
        + "\t\t// DOCTRINE: alternate approach lanes on a two-minute cycle" + "\r\n"
        + "\t\tconst wave = Math.floor(gameTime / 120000) % 3;" + "\r\n"
        + "\t\tlet flankX = 0, flankY = 0;" + "\r\n"
        + "\t\tconst useFlank = (wave !== 0);" + "\r\n"
        + "\t\tif (useFlank)" + "\r\n"
        + "\t\t{" + "\r\n"
        + "\t\t\tconst fdx = target.x - cx, fdy = target.y - cy;" + "\r\n"
        + "\t\t\tconst fdl = Math.max(1, Math.floor(Math.sqrt(fdx * fdx + fdy * fdy)));" + "\r\n"
        + "\t\t\tconst sign = (wave === 1) ? 1 : -1;" + "\r\n"
        + "\t\t\tflankX = Math.floor((cx + target.x) / 2) + Math.floor((-fdy * 10 * sign) / fdl);" + "\r\n"
        + "\t\t\tflankY = Math.floor((cy + target.y) / 2) + Math.floor((fdx * 10 * sign) / fdl);" + "\r\n"
        + "\t\t\tflankX = Math.max(2, Math.min(mapWidth - 3, flankX));" + "\r\n"
        + "\t\t\tflankY = Math.max(2, Math.min(mapHeight - 3, flankY));" + "\r\n"
        + "\t\t}" + "\r\n"
    )
    tac_patched = tac_patched.replace(tac_mark, regroup, 1)
    atk_old = "\t\t\t\torderDroidObj(droid, DORDER_ATTACK, target);"
    atk_new = ("\t\t\t\tif (useFlank && distBetweenTwoPoints(droid.x, droid.y, target.x, target.y) > 18)" + "\r\n"
               + "\t\t\t\t{" + "\r\n"
               + "\t\t\t\t\torderDroidLoc(droid, DORDER_MOVE, flankX, flankY);" + "\r\n"
               + "\t\t\t\t}" + "\r\n"
               + "\t\t\t\telse" + "\r\n"
               + "\t\t\t\t{" + "\r\n"
               + "\t\t\t\t\torderDroidObj(droid, DORDER_ATTACK, target);" + "\r\n"
               + "\t\t\t\t}")
    if atk_old not in tac_patched:
        fail("Nexus tactics.js attack order line not found -- re-check")
    tac_patched = tac_patched.replace(atk_old, atk_new, 1)
    (tac_dir / "tactics.js").write_text(tac_patched, encoding="utf-8", newline="")
    print("nexus AI: attacks regroup before committing and alternate approach lanes")
    summary["research.json"].append(
        "- Nexus `tactics.js`: attackers regroup on their centroid before "
        "committing (no more piecemeal trickle) and alternate between a direct "
        "approach and two flanking lanes on a two-minute cycle.")

    # "Start with Bases" also pre-places a RESEARCH FACILITY. The lab is the
    # engine of the whole DOCTRINE loop, and handing it over pre-built skips the
    # first real decision of the game -- so the standard base now starts without
    # one, for every player and difficulty alike. Only CAMP_BASE is touched:
    # "Advanced Bases" (CAMP_WALLS) keeps everything, "No Bases" never had one.
    RULES_BASE = "multiplay/script/rules/setup/base.js"
    with zipfile.ZipFile(MP_WZ) as z:
        base_src = z.read(RULES_BASE).decode("utf-8")
    nl = "\r\n" if "\r\n" in base_src else "\n"
    tb = "\t"
    camp_norm_old = ("return stattype === WALL" + nl
                     + tb*3 + "|| stattype === DEFENSE" + nl
                     + tb*3 + "|| stattype === GATE" + nl
                     + tb*3 + "|| stattype === CYBORG_FACTORY" + nl
                     + tb*3 + "|| stattype === COMMAND_CONTROL;")
    camp_norm_new = ("return stattype === WALL" + nl
                     + tb*3 + "|| stattype === DEFENSE" + nl
                     + tb*3 + "|| stattype === GATE" + nl
                     + tb*3 + "|| stattype === CYBORG_FACTORY" + nl
                     + tb*3 + "|| stattype === RESEARCH_LAB" + nl
                     + tb*3 + "|| stattype === COMMAND_CONTROL;")
    camp_ins_old = ("return stattype === CYBORG_FACTORY" + nl
                    + tb*3 + "|| stattype === COMMAND_CONTROL;")
    camp_ins_new = ("return stattype === CYBORG_FACTORY" + nl
                    + tb*3 + "|| stattype === RESEARCH_LAB" + nl
                    + tb*3 + "|| stattype === COMMAND_CONTROL;")
    # 4.7.0 factors the removal test into shouldRemoveBaseStructure() with one
    # list per difficulty; 4.5.5 does it inline in setupBase() with a single
    # condition. Patch whichever shape this version has.
    inline_old = ("|| s.stattype === GATE || s.stattype === CYBORG_FACTORY "
                  "|| s.stattype === COMMAND_CONTROL)")
    inline_new = ("|| s.stattype === GATE || s.stattype === CYBORG_FACTORY "
                  "|| s.stattype === COMMAND_CONTROL "
                  "|| s.stattype === RESEARCH_LAB)")
    if camp_norm_old in base_src and camp_ins_old in base_src:
        base_patched = base_src.replace(camp_norm_old, camp_norm_new, 1)
        base_patched = base_patched.replace(camp_ins_old, camp_ins_new, 1)
    elif base_src.count(inline_old) == 1:
        base_patched = base_src.replace(inline_old, inline_new, 1)
    else:
        fail("rules/setup/base.js CAMP_BASE removal logic not found -- re-check")
    rules_dir = staging / "multiplay" / "script" / "rules" / "setup"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "base.js").write_text(base_patched, encoding="utf-8", newline="")
    print("start-with-bases: pre-placed research facility removed (all difficulties)")
    summary["research.json"].append(
        "- `rules/setup/base.js`: the standard starting base no longer includes a "
        "pre-placed Research Facility, for any player or difficulty. Building the "
        "first lab is the first decision of the game again. Advanced Bases is "
        "untouched.")

    # ---- SemperFi builds from three lists that are far too narrow ----------
    # Its production is a PRIORITY list: buildDroid walks it and takes the first
    # component that is available. Measured in play, that produced three
    # complaints, all from the same cause -- things simply are not in the lists.
    #
    #   TANK_WEAPON_LIST holds four rocket entries and then MG2Mk1/MG1Mk1. No
    #   cannon, no heavy machinegun, no mortar anywhere. Early on none of the
    #   rockets exist yet, so it falls all the way through to the twin MG and
    #   the starting MG and builds nothing else, however much it has researched.
    #
    #   CYBORG_ROCKETS holds only Cyb-Hvywpn-TK and Cyb-Hvywpn-A-T, both of
    #   which are late-game. buildCyborg picks flamer-or-rocket on a coin flip,
    #   the rocket branch finds nothing buildable, and every cyborg it fields
    #   for most of the game is a flamer.
    #
    #   standardDefenses holds six structures, all rocket or MG. Pillboxes,
    #   bunkers, cannon hardpoints and mortar pits are never built no matter
    #   what DOCTRINE unlocks, which is why its bases are all MG towers and
    #   mini-rocket pits.
    #
    # Each list is widened with what DOCTRINE actually makes reachable, keeping
    # SemperFi's rocket identity at the top of the order.
    SEMPERFI_LISTS = [
        ("multiplay/skirmish/semperfi_includes/production.js",
         'const TANK_WEAPON_LIST = [',
         ['\t"Missile-A-T", // Scourge',
          '\t"Rocket-HvyA-T", // Tank-killer',
          '\t"Rocket-LtA-T", // Lancer',
          '\t"Rocket-MRL", // MRL',
          '\t"Cannon2A-TMk1", // DOCTRINE: medium cannon',
          '\t"Cannon1Mk1", // DOCTRINE: light cannon',
          '\t"MG4ROTARYMk1", // DOCTRINE: assault gun',
          '\t"MG3Mk1", // DOCTRINE: heavy machinegun',
          '\t"MG2Mk1", // twin mg',
          '\t"MG1Mk1", // mg, initial weapon'],
         "tank weapons"),
        ("multiplay/skirmish/semperfi_includes/production.js",
         'const TANK_ARTILLERY = [',
         ['\t"Missile-MdArt", // Seraph',
          '\t"Rocket-MRL-Hvy", // HRA',
          '\t"Rocket-MRL", // MRL',
          '\t"Mortar1Mk1", // DOCTRINE: mortar, so artillery exists early too'],
         "tank artillery"),
        ("multiplay/skirmish/semperfi_includes/production.js",
         'const CYBORG_ROCKETS = [',
         ['\t"Cyb-Hvywpn-TK",',
          '\t"Cyb-Hvywpn-A-T",'],
         "cyborg heavy weapons"),
        ("multiplay/skirmish/semperfi_includes/build.js",
         'var standardDefenses = [',
         ['\t"WallTower-Atmiss",',
          '\t"WallTower-HvATrocket",',
          '\t"WallTower06",',
          '\t"WallTower02", // DOCTRINE: cannon hardpoint',
          '\t"WallTower01", // DOCTRINE: heavy MG hardpoint',
          '\t"Emplacement-MRL-pit",',
          '\t"Pillbox-RotMG", // DOCTRINE: assault-gun bunker',
          '\t"PillBox4", // DOCTRINE: cannon bunker',
          '\t"PillBox5", // DOCTRINE: flamer bunker',
          '\t"PillBox1", // DOCTRINE: heavy MG bunker',
          '\t"GuardTower6",',
          '\t"GuardTower1",'],
         "standard defences"),
        ("multiplay/skirmish/semperfi_includes/build.js",
         'var artilleryDefenses = [',
         ['\t"Emplacement-HvART-pit",',
          '\t"Emplacement-MdART-pit",',
          '\t"Emplacement-Rocket06-IDF",',
          '\t"Emplacement-MRLHvy-pit",',
          '\t"Emplacement-MRL-pit",',
          '\t"Emplacement-MortarPit01", // DOCTRINE: mortar pit'],
         "artillery defences"),
    ]
    sf_patched = {}
    for path, head, entries, label in SEMPERFI_LISTS:
        if path not in sf_patched:
            with zipfile.ZipFile(MP_WZ) as z:
                sf_patched[path] = z.read(path).decode("utf-8")
        src = sf_patched[path]
        # 4.7.0 declares these with const, 4.5.5 with var -- accept either.
        start = src.find(head)
        if start < 0 and head.startswith("var "):
            head = "const " + head[4:]
            start = src.find(head)
        if start < 0 and head.startswith("const "):
            head = "var " + head[6:]
            start = src.find(head)
        if start < 0:
            fail(f"SemperFi: list head not found: {head}")
        end = src.find("];", start)
        if end < 0:
            fail(f"SemperFi: unterminated list: {head}")
        body = CRLF.join(entries)
        sf_patched[path] = src[:start] + head + CRLF + body + CRLF + src[end:]
        print(f"semperfi: {label} widened to {len(entries)} entries")

    # ---- ...and stop it fielding ONE weapon at a time ----------------------
    # buildDroid() walks a component list and takes the first AVAILABLE entry,
    # so a priority list yields a monoculture: before the lists were widened it
    # was every tank a twin machinegun, and immediately afterwards it was every
    # tank a light cannon, because the cannon now sat above MG and below rockets
    # it had not researched yet. Widening the list alone could never fix that.
    #
    # SemperFi now picks at random from the best THREE available entries, so the
    # army is mixed while still climbing toward its rocket end-game.
    SF_PROD = "multiplay/skirmish/semperfi_includes/production.js"
    if SF_PROD not in sf_patched:
        with zipfile.ZipFile(MP_WZ) as z:
            sf_patched[SF_PROD] = z.read(SF_PROD).decode("utf-8")
    src = sf_patched[SF_PROD]

    helper = (
        "/* Pick one weapon at random from the best few this AI can actually" + CRLF
        + "   build. Passing the whole list to buildDroid() takes the first" + CRLF
        + "   available entry every single time, which makes every tank identical." + CRLF
        + "   Lists stay in priority order, so the top of `avail` is still the best" + CRLF
        + "   thing available -- this only spreads production across the top few. */" + CRLF
        + "function doctrinePickWeapon(list)" + CRLF
        + "{" + CRLF
        + TAB_JS + "if (!Array.isArray(list)) { return list; }" + CRLF
        + TAB_JS + "var avail = [];" + CRLF
        + TAB_JS + "for (var dpw = 0; dpw < list.length; ++dpw)" + CRLF
        + TAB_JS + "{" + CRLF
        + TAB_JS * 2 + "if (componentAvailable(list[dpw])) { avail.push(list[dpw]); }" + CRLF
        + TAB_JS + "}" + CRLF
        + TAB_JS + "if (avail.length === 0) { return list; }" + CRLF
        + TAB_JS + "var span = avail.length < 3 ? avail.length : 3;" + CRLF
        + TAB_JS + "return avail[random(span)];" + CRLF
        + "}" + CRLF + CRLF)

    head = "function buildAttacker(struct)"
    if head not in src:
        fail("SemperFi: buildAttacker not found")
    src = src.replace(head, helper + head, 1)

    # ---- Nexus and BoneCrusher had no anti-air TANK either -----------------
    # Checked every AA-capable component against all five AI codebases: Cobra and
    # the NullBot family list AA turrets in their tank weapon tables and can
    # already field them. Nexus references not one anti-air turret anywhere in its
    # 21 files, and BoneCrusher's only mentions are a comment and a wall hardpoint
    # -- neither can build a mobile AA unit at all. Both get one, gated on
    # doctrineAirThreat() so nothing is wasted while the sky is empty.
    NEXUS_TEMPLATES = "multiplay/skirmish/nexus_standards/templates.js"
    NEXUS_PROD = "multiplay/skirmish/nexus_includes/production.js"
    for _p in (NEXUS_TEMPLATES, NEXUS_PROD):
        if _p not in sf_patched:
            with zipfile.ZipFile(MP_WZ) as z:
                sf_patched[_p] = z.read(_p).decode("utf-8")

    nx_t = sf_patched[NEXUS_TEMPLATES]
    if "STANDARD_AA_TEMPLATES" not in nx_t:
        nx_aa = (CRLF
            + "// DOCTRINE: anti-air tanks. Nexus had no AA turret in any template," + CRLF
            + "// so its army could not shoot back at VTOLs at all. Ordered cheapest" + CRLF
            + "// first; getBestRandomTemplate walks from the END, so the heavy" + CRLF
            + "// missile carriers are preferred once they exist." + CRLF
            + "const STANDARD_AA_TEMPLATES = [" + CRLF
            + TAB_JS + '{ body: "Body1REC", prop: "wheeled01", weaps: ["QuadMg1AAGun",] },' + CRLF
            + TAB_JS + '{ body: "Body5REC", prop: "HalfTrack", weaps: ["QuadMg1AAGun",] },' + CRLF
            + TAB_JS + '{ body: "Body5REC", prop: "HalfTrack", weaps: ["AAGun2Mk1",] },' + CRLF
            + TAB_JS + '{ body: "Body5REC", prop: "tracked01", weaps: ["QuadRotAAGun",] },' + CRLF
            + TAB_JS + '{ body: "Body11ABT", prop: "tracked01", weaps: ["AAGun2Mk1Quad",] },' + CRLF
            + TAB_JS + '{ body: "Body11ABT", prop: "tracked01", weaps: ["Missile-LtSAM",] },' + CRLF
            + TAB_JS + '{ body: "Body9REC", prop: "tracked01", weaps: ["Missile-HvySAM",] },' + CRLF
            + "];" + CRLF)
        nx_t = nx_t + nx_aa
        sf_patched[NEXUS_TEMPLATES] = nx_t

    nx_p = sf_patched[NEXUS_PROD]
    nx_case = 'case "TRUCK": what = STANDARD_TRUCK_TEMPLATES; break;'
    if nx_case not in nx_p:
        fail("Nexus: template switch not found")
    nx_p = nx_p.replace(nx_case,
        'case "AA": what = STANDARD_AA_TEMPLATES; break;' + CRLF + TAB_JS * 2 + nx_case, 1)
    nx_need = "		else if (needTank())"
    if nx_need not in nx_p:
        fail("Nexus: needTank branch not found")
    nx_aa_branch = (
        TAB_JS * 2 + "else if (doctrineAirThreat() && !random(3)" + CRLF
        + TAB_JS * 3 + '&& defined(getBestRandomTemplate("AA", TEMPLATE_BEST_OFFSET)))' + CRLF
        + TAB_JS * 2 + "{" + CRLF
        + TAB_JS * 3 + "// DOCTRINE: something is flying and Nexus owns no mobile AA." + CRLF
        + TAB_JS * 3 + 'var nxAA = getBestRandomTemplate("AA", TEMPLATE_BEST_OFFSET);' + CRLF
        + TAB_JS * 3 + 'if (buildDroid(factory, "Nexus AA", nxAA.body, nxAA.prop, "", "", nxAA.weaps[0], "", ""))' + CRLF
        + TAB_JS * 3 + "{" + CRLF
        + TAB_JS * 4 + "success = true;" + CRLF
        + TAB_JS * 3 + "}" + CRLF
        + TAB_JS * 2 + "}" + CRLF
        + nx_need)
    nx_p = nx_p.replace(nx_need, nx_aa_branch, 1)
    sf_patched[NEXUS_PROD] = nx_p
    print("nexus: anti-air tanks added (7 templates, gated on enemy air)")

    # BoneCrusher: avail_guns is built from its own research->component table and
    # holds no AA turret, so "Army" units never carry one.
    BC_PROD = "multiplay/skirmish/bonecrusher/produce.js"
    if BC_PROD not in sf_patched:
        with zipfile.ZipFile(MP_WZ) as z:
            sf_patched[BC_PROD] = z.read(BC_PROD).decode("utf-8")
    bc = sf_patched[BC_PROD]
    bc_key = 'buildDroid(droid_factories[0], "Army", _body, _prop, "", "", _weapon, _second);'
    if bc_key not in bc:
        fail("BoneCrusher: Army buildDroid not found")
    bc_new = (
        "// DOCTRINE: an anti-air variant. avail_guns is built from BoneCrusher's" + CRLF
        + TAB_JS * 3 + "// own weapon table, which lists no AA turret at all." + CRLF
        + TAB_JS * 3 + "var bcAA = null;" + CRLF
        + TAB_JS * 3 + "// BoneCrusher has no random() helper -- it is a separate codebase" + CRLF
        + TAB_JS * 3 + "// and uses Math.random() throughout. Calling random() here threw" + CRLF
        + TAB_JS * 3 + "// ReferenceError roughly 7,000 times per game." + CRLF
        + TAB_JS * 3 + "if (doctrineAirThreat() && Math.random() < 0.33)" + CRLF
        + TAB_JS * 3 + "{" + CRLF
        + TAB_JS * 4 + 'var bcList = ["Missile-HvySAM", "Missile-LtSAM", "AAGunLaser",' + CRLF
        + TAB_JS * 5 + '"QuadRotAAGun", "AAGun2Mk1Quad", "AAGun2Mk1", "QuadMg1AAGun"];' + CRLF
        + TAB_JS * 4 + "for (var bcI = 0; bcI < bcList.length; ++bcI)" + CRLF
        + TAB_JS * 4 + "{" + CRLF
        + TAB_JS * 5 + "if (componentAvailable(bcList[bcI])) { bcAA = bcList[bcI]; break; }" + CRLF
        + TAB_JS * 4 + "}" + CRLF
        + TAB_JS * 3 + "}" + CRLF
        + TAB_JS * 3 + "if (bcAA !== null)" + CRLF
        + TAB_JS * 3 + "{" + CRLF
        + TAB_JS * 4 + 'buildDroid(droid_factories[0], "AA", _body, _prop, "", "", bcAA, bcAA);' + CRLF
        + TAB_JS * 3 + "}" + CRLF
        + TAB_JS * 3 + "else " + bc_key)
    bc = bc.replace(bc_key, bc_new, 1)
    sf_patched[BC_PROD] = bc
    print("bonecrusher: anti-air tanks added (gated on enemy air)")
    summary["research.json"].append(
        "- **Every AI can now field anti-air tanks.** Cobra and the NullBot family "
        "already listed AA turrets; Nexus referenced none in any of its 21 files and "
        "BoneCrusher's only mentions were a comment and a wall hardpoint. Both now "
        "build them, and all of them check `doctrineAirThreat()` first -- AA turrets "
        "are air-only, so one built against an empty sky is a wasted slot.")

    # ---- SemperFi never built a single anti-air TANK -----------------------
    # buildAttacker picks from TANK_WEAPON_LIST and TANK_ARTILLERY only, and
    # neither list holds one anti-air turret -- checked against every AA-capable
    # component in weapons.json. It does build AA structures (buildAntiAir /
    # SAM_SITES), so its base is covered while its army in the field is helpless
    # the moment anything flies. Reported from a 2h43m game on 7c-Thales.
    #
    # The branch only fires once the enemy actually has VTOLs, which SemperFi
    # already tracks in `enemyHasVtol` (set from its own events.js/tactics.js),
    # so nothing is wasted while the sky is empty.
    aa_list = (
        "const TANK_AA = [" + CRLF
        + TAB_JS + '"Missile-HvySAM", // vindicator' + CRLF
        + TAB_JS + '"Missile-LtSAM", // avenger' + CRLF
        + TAB_JS + '"AAGunLaser", // stormbringer' + CRLF
        + TAB_JS + '"QuadRotAAGun", // whirlwind' + CRLF
        + TAB_JS + '"AAGun2Mk1Quad", // flak cannon' + CRLF
        + TAB_JS + '"AAGun2Mk1", // hurricane' + CRLF
        + TAB_JS + '"QuadMg1AAGun", // cyclone -- R-Wpn-AAGun03, the reachable one' + CRLF
        + "];" + CRLF + CRLF)
    src = src.replace(head, aa_list + head, 1)

    aa_hook = (
        TAB_JS + "// DOCTRINE: mobile AA. Without this SemperFi fields no anti-air" + CRLF
        + TAB_JS + "// unit at all -- its two weapon lists contain none." + CRLF
        + TAB_JS + "// doctrineEnemyAir() counts SCAVENGER helicopters too; SemperFi's own" + CRLF
        + TAB_JS + "// enemyHasVtol only trips on a player VTOL it has actually seen." + CRLF
        + TAB_JS + 'if (doctrineAirThreat() && random(100) < 30)' + CRLF
        + TAB_JS + "{" + CRLF
        + TAB_JS * 2 + "var aaw = doctrinePickWeapon(TANK_AA);" + CRLF
        + TAB_JS * 2 + 'if (typeof aaw === "string")' + CRLF
        + TAB_JS * 2 + "{" + CRLF
        + TAB_JS * 3 + 'return buildDroid(struct, "AA Tank", TANK_BODY_LIST, prop, "", "", aaw);' + CRLF
        + TAB_JS * 2 + "}" + CRLF
        + TAB_JS + "}" + CRLF + CRLF)
    # placed after `prop` is finally decided (the hover block), before the
    # bunker-buster branch, so the AA tank inherits the same chassis choice.
    aa_at = src.find("if (enumGroup(attackGroup).length > MIN_ATTACK_GSIZE")
    if aa_at < 0:
        fail("SemperFi: buildAttacker bunker-buster branch not found for AA hook")
    line_start = src.rfind(CRLF, 0, aa_at)
    if line_start < 0:
        fail("SemperFi: could not anchor AA hook")
    src = src[:line_start + len(CRLF)] + aa_hook + src[line_start + len(CRLF):]
    print("semperfi: anti-air tanks built once the enemy fields VTOLs")
    summary["research.json"].append(
        "- **SemperFi builds anti-air tanks.** Neither of the two lists "
        "`buildAttacker` draws from held a single anti-air turret, so it never "
        "fielded a mobile AA unit -- only AA structures at home. It now builds "
        "them once it knows the enemy has VTOLs.")

    # ---- cyborgs: the weapon has to match the BODY -------------------------
    # Round 28 put CyborgRocket/Cannon/RotMG/Chaingun into CYBORG_ROCKETS, but
    # buildCyborg mounts that list on CyborgHeavyBody and those are all LIGHT
    # cyborg weapons -- an invalid pairing, and CyborgHeavyBody additionally
    # needs R-Cyborg-Metals04. So the branch failed outright and every cyborg
    # came from the flamer branch: measured CyborgFlamer01 x100 and nothing else
    # at t=2020s. Light weapons now get the light body, and the heavy branch is
    # only tried once the heavy body exists.
    cyb_light = (
        "const CYBORG_LIGHT = [" + CRLF
        + TAB_JS + '"CyborgRocket", // lancer cyborg' + CRLF
        + TAB_JS + '"CyborgCannon",' + CRLF
        + TAB_JS + '"CyborgRotMG",' + CRLF
        + TAB_JS + '"CyborgChaingun",' + CRLF
        + "];" + CRLF + CRLF)
    cyb_fn = (
        "function buildCyborg(struct)" + CRLF
        + "{" + CRLF
        + TAB_JS + "// Heavy weapons need CyborgHeavyBody; the light ones need" + CRLF
        + TAB_JS + "// CyborgLightBody. Mixing them makes buildDroid fail silently." + CRLF
        + TAB_JS + "// A branch only fires when it holds a weapon it can actually mount:" + CRLF
        + TAB_JS + "// doctrinePickWeapon hands back the whole list when nothing in it is" + CRLF
        + TAB_JS + "// available, and a failed buildDroid idles the factory for the tick." + CRLF
        + TAB_JS + 'if (componentAvailable("CyborgHeavyBody") && !random(2))' + CRLF
        + TAB_JS + "{" + CRLF
        + TAB_JS * 2 + "var hw = doctrinePickWeapon(CYBORG_ROCKETS);" + CRLF
        + TAB_JS * 2 + 'if (typeof hw === "string") { return buildDroid(struct, "Cyborg Heavy", "CyborgHeavyBody", "CyborgLegs", "", "", hw); }' + CRLF
        + TAB_JS + "}" + CRLF
        + TAB_JS + "if (!random(2))" + CRLF
        + TAB_JS + "{" + CRLF
        + TAB_JS * 2 + "var fw = doctrinePickWeapon(CYBORG_FLAMERS);" + CRLF
        + TAB_JS * 2 + 'if (typeof fw === "string") { return buildDroid(struct, "Cyborg Flamer", "CyborgLightBody", "CyborgLegs", "", "", fw); }' + CRLF
        + TAB_JS + "}" + CRLF
        + TAB_JS + 'return buildDroid(struct, "Cyborg Light", "CyborgLightBody", "CyborgLegs", "", "", doctrinePickWeapon(CYBORG_LIGHT));' + CRLF
        + "}" + CRLF + CRLF)
    cyb_start = src.find("function buildCyborg(struct)")
    cyb_end = src.find("function buildVTOL", cyb_start)
    if cyb_start < 0 or cyb_end < 0:
        fail("SemperFi: buildCyborg block not found")
    src = src[:cyb_start] + cyb_light + cyb_fn + src[cyb_end:]
    print("semperfi: cyborg weapons paired with the body that fits them")

    # Match on the EXPRESSION, not the declaration: 4.7.0 writes `const
    # weaponChoice` / `let secondary` where 4.5.5 writes `var` for both.
    TANK_EXPR = "(random(100) < WEAPON_CHANCE) ? TANK_WEAPON_LIST : TANK_ARTILLERY;"
    n_picks = src.count(TANK_EXPR)
    src = src.replace(TANK_EXPR, "doctrinePickWeapon(" + TANK_EXPR[:-1] + ");")
    for lst in ("CYBORG_FLAMERS", "CYBORG_ROCKETS"):
        old_call = '"", "", ' + lst + ");"
        if old_call in src:
            src = src.replace(old_call, '"", "", doctrinePickWeapon(' + lst + "));", 1)
            n_picks += 1
    # 2 = the two tank/artillery expressions. The cyborg calls are already
    # wrapped inside the replacement buildCyborg above, so they are not counted.
    if n_picks < 2:
        fail(f"SemperFi: only {n_picks} weapon pick sites rewritten")
    sf_patched[SF_PROD] = src
    print(f"semperfi: {n_picks} weapon choices spread over the best three available")
    summary["research.json"].append(
        "- **SemperFi no longer fields one weapon at a time.** `buildDroid` takes "
        "the FIRST available entry of a component list, so a priority list always "
        "produces a monoculture -- all twin machineguns before, all light cannons "
        "after the lists were widened. It now draws at random from the best three "
        "available, so the army is mixed while still climbing to its rockets.")

    # ---- NullBot / Hover / Turtle: scavengers are an ENEMY ------------------
    # Stock NullBot enumerates living players as `i < maxPlayers`, so the
    # scavenger player is never in its world at all. In DOCTRINE the scavengers
    # are a faction: measured on Sk-Rush with every real player allied, all
    # three NullBot variants saw "no enemy", produceTank() returned false on
    # scopeRatings().land === 0, spendMoney() built trucks forever, and every
    # one of them was overrun in 20 minutes with 0 tanks and 0 defences built.
    # Nexus, Cobra, BoneCrusher and SemperFi all fight scavengers already; this
    # brings the NullBot family in line. The only per-player indexing NullBot
    # does is playerData[sender] in chat and startPositions[me], so a scavenger
    # index is safe everywhere enumLivingPlayers() feeds.
    NB_MISC = "multiplay/skirmish/nb_includes/misc.js"
    with zipfile.ZipFile(MP_WZ) as z:
        nb_src = z.read(NB_MISC).decode("utf-8")
    nb_start = nb_src.find("function enumLivingPlayers()")
    if nb_start < 0:
        fail("NullBot: enumLivingPlayers not found in misc.js")
    nb_end = nb_src.find(chr(10) + "function ", nb_start + 10)
    if nb_end < 0:
        fail("NullBot: enumLivingPlayers end not found")
    nb_fn = (
        "function enumLivingPlayers()" + CRLF
        + "{" + CRLF
        + TAB_JS + "function uncached()" + CRLF
        + TAB_JS + "{" + CRLF
        + TAB_JS * 2 + "var ret = [];" + CRLF
        + TAB_JS * 2 + "// DOCTRINE: the scavengers are a faction, not scenery. Stock NullBot" + CRLF
        + TAB_JS * 2 + "// only ever looked at i < maxPlayers, so with every real player allied" + CRLF
        + TAB_JS * 2 + "// it saw no enemy, built trucks forever and was overrun." + CRLF
        + TAB_JS * 2 + "var candidates = [];" + CRLF
        + TAB_JS * 2 + "for (var c = 0; c < maxPlayers; ++c) { candidates.push(c); }" + CRLF
        + TAB_JS * 2 + 'if (typeof scavengerPlayer !== "undefined" && scavengerPlayer >= 0' + CRLF
        + TAB_JS * 3 + "&& scavengerPlayer !== me && !allianceExistsBetween(me, scavengerPlayer))" + CRLF
        + TAB_JS * 2 + "{" + CRLF
        + TAB_JS * 3 + "candidates.push(scavengerPlayer);" + CRLF
        + TAB_JS * 2 + "}" + CRLF
        + TAB_JS * 2 + "for (var k = 0; k < candidates.length; ++k)" + CRLF
        + TAB_JS * 2 + "{" + CRLF
        + TAB_JS * 3 + "var i = candidates[k];" + CRLF
        + TAB_JS * 3 + "if (countStructList(targets, i) > 0)" + CRLF
        + TAB_JS * 3 + "{" + CRLF
        + TAB_JS * 4 + "ret.push(i);" + CRLF
        + TAB_JS * 4 + "continue;" + CRLF
        + TAB_JS * 3 + "}" + CRLF
        + TAB_JS * 3 + "if (enumDroid(i).length > 0)" + CRLF
        + TAB_JS * 3 + "{" + CRLF
        + TAB_JS * 4 + "ret.push(i);" + CRLF
        + TAB_JS * 3 + "}" + CRLF
        + TAB_JS * 2 + "}" + CRLF
        + TAB_JS * 2 + "return ret;" + CRLF
        + TAB_JS + "}" + CRLF
        + CRLF
        + TAB_JS + "return cached(uncached, 30000);" + CRLF
        + "}" + CRLF)
    nb_src = nb_src[:nb_start] + nb_fn + nb_src[nb_end:]
    sf_patched[NB_MISC] = nb_src

    # adapt.js is an IIFE: its per-player stat tables (enemyStats / enemyStatsTemp)
    # are closure-private and sized to maxPlayers at load, so the scavenger index
    # above has no entry and every .collapse() on it threw -- measured ~1,700
    # "cannot read property 'collapse' of undefined" per game from spendMoney().
    # The entries have to be created inside adapt.js itself.
    NB_ADAPT = "multiplay/skirmish/nb_includes/adapt.js"
    with zipfile.ZipFile(MP_WZ) as z:
        ad_src = z.read(NB_ADAPT).decode("utf-8")
    ad_key = "enemyStatsTemp[i] = new EnemyStat();"
    ad_pos = ad_src.find(ad_key)
    if ad_pos < 0:
        fail("NullBot: adapt.js stat-table init loop not found")
    ad_close = ad_src.find("}", ad_pos)
    if ad_close < 0:
        fail("NullBot: adapt.js init loop close brace not found")
    ad_add = (CRLF
        + "// DOCTRINE: the scavenger player is an enemy too (misc.js enumLivingPlayers)," + CRLF
        + "// so it needs stat entries like every other player." + CRLF
        + 'if (typeof scavengerPlayer !== "undefined" && scavengerPlayer >= 0' + CRLF
        + TAB_JS + "&& enemyStats[scavengerPlayer] === undefined)" + CRLF
        + "{" + CRLF
        + TAB_JS + "enemyStats[scavengerPlayer] = new EnemyStat();" + CRLF
        + TAB_JS + "enemyStatsTemp[scavengerPlayer] = new EnemyStat();" + CRLF
        + "}" + CRLF)
    ad_src = ad_src[:ad_close + 1] + ad_add + ad_src[ad_close + 1:]
    sf_patched[NB_ADAPT] = ad_src

    # Turtle: defensiveness 100 switches on NullBot's "turtle-specific" branch in
    # chooseObjectType(), which builds ONLY defences and VTOLs -- never a tank.
    # Against vanilla scavengers that is survivable; against DOCTRINE's it is
    # not: measured on Sk-Rush, Turtle had one tower up at 380s and was wiped
    # by 500s, with 0 tanks, in every run. At 90 it stays overwhelmingly
    # defensive but the adapt vote may field a few tanks when it is outgunned.
    NB_TURTLE = "multiplay/skirmish/nb_turtle.js"
    with zipfile.ZipFile(MP_WZ) as z:
        tu_src = z.read(NB_TURTLE).decode("utf-8")
    n_tu = tu_src.count("defensiveness: 100")
    if n_tu == 0:
        fail("NullBot Turtle: defensiveness: 100 not found")
    tu_src = tu_src.replace("defensiveness: 100",
                            "defensiveness: 90 /* DOCTRINE: was 100, see build_mod.py */")
    sf_patched[NB_TURTLE] = tu_src
    print(f"nullbot: turtle defensiveness 100 -> 90 ({n_tu} personalities)")
    print("nullbot: adapt.js stat tables cover the scavenger player")
    print("nullbot: scavengers count as a living enemy (misc.js enumLivingPlayers)")
    summary["research.json"].append(
        "- **NullBot, Hover and Turtle now see scavengers as an enemy.** Stock "
        "NullBot enumerates players as `i < maxPlayers`, so the scavenger "
        "faction never existed for it: with no other enemy in reach it built "
        "nothing but trucks and was overrun. `enumLivingPlayers()` now includes "
        "a hostile scavenger player.")

    for path, text in sf_patched.items():
        out = staging / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="")
    summary["research.json"].append(
        "- **SemperFi actually uses what it researches.** Its production and "
        "defence lists are priority lists, and cannon, heavy MG, mortar, "
        "pillboxes, bunkers and cannon hardpoints were absent from all of them "
        "-- so it built twin MGs, flamer cyborgs and MG towers no matter what it "
        "had unlocked. Each list now carries the DOCTRINE-reachable options "
        "below SemperFi's own rocket preferences.")

    # ---- The other four AIs get the same research engine -------------------
    # Their research is driven by hard-coded topic lists, and DOCTRINE's tree
    # moved a great deal of it. Measured against the shipped tree:
    #     BoneCrusher  497 topics referenced, 110 DELETED, 103 crate-locked
    #     NullBot      203 referenced,          0 deleted,  23 crate-locked
    #     SemperFi      62 referenced,          0 deleted,   7 crate-locked
    #     Cobra         92 referenced,          1 deleted,   0 crate-locked
    # pursueResearch() on a missing or unreachable topic just returns false, so
    # nothing crashes -- the AI simply fails that pick and researches far less
    # than it should. BoneCrusher has 43% of its list dead.
    #
    # Each AI's research entry point now tries the DOCTRINE engine FIRST and
    # only falls back to its own list. Same engine text as Nexus uses, so tuning
    # a weight tunes every AI at once.
    #
    # The two game versions differ in brace style ("function f()\n{" vs
    # "function f() {") and in names (Cobra's entry is cobraDoResearch in 4.7.0
    # and plain research in 4.5.5), so entries are matched by regex on the
    # function head and the hook is inserted after its opening brace. Only
    # engine globals are used inside the hook -- RESEARCH_LAB rather than any
    # AI's private structure table -- so it is scope-safe everywhere.
    AI_HOOKS = [
        # (path, entry-point names, mode, label, fallback family index)
        # The fallback is only used when the AI exposes no weapon preference
        # the engine can read. SemperFi is the only one: it has no
        # personality system at all and is documented as rockets/missiles.
        ("multiplay/skirmish/nb_includes/research.js",       ["doResearch"],                  "lab_param",  "NullBot",     -1),
        ("multiplay/skirmish/bonecrusher/research.js",       ["doResearch"],                  "self_labs",  "BoneCrusher", -1),
        ("multiplay/skirmish/semperfi_includes/research.js", ["lookForResearch"],             "self_labs",  "SemperFi",     2),
        ("multiplay/skirmish/cobra_includes/research.js",    ["cobraDoResearch", "research"], "self_labs",  "Cobra",       -1),
    ]
    HOOK_LAB_PARAM = (
        "\r\n\tdoctrineAnnounce();"
        "\r\n\t// DOCTRINE: score-based pick first -- this AI's own lists reference"
        "\r\n\t// topics DOCTRINE deleted or moved behind crates."
        "\r\n\tif (doctrineResearchPick(lab))"
        "\r\n\t{"
        "\r\n\t\treturn true;"
        "\r\n\t}\r\n")
    HOOK_SELF_LABS = (
        "\r\n\tdoctrineAnnounce();"
        "\r\n\t// DOCTRINE: score-based pick first for every idle lab. Uses only"
        "\r\n\t// engine globals so it is safe in any AI's scope."
        "\r\n\ttry"
        "\r\n\t{"
        "\r\n\t\tconst _dLabs = enumStruct(me, RESEARCH_LAB).filter(function (e) {"
        "\r\n\t\t\treturn e.status === BUILT && structureIdle(e);"
        "\r\n\t\t});"
        "\r\n\t\tlet _dTook = 0;"
        "\r\n\t\tfor (let _i = 0; _i < _dLabs.length; ++_i)"
        "\r\n\t\t{"
        "\r\n\t\t\tif (doctrineResearchPick(_dLabs[_i])) { ++_dTook; }"
        "\r\n\t\t}"
        "\r\n\t\t// Yield only if the engine took EVERY idle lab, and decide that"
        "\r\n\t\t// from the take-count -- NOT by re-querying structureIdle(), which"
        "\r\n\t\t// does not flip synchronously after pursueResearch. Re-querying"
        "\r\n\t\t// left the labs still looking idle, so this AI's own pass ran and"
        "\r\n\t\t// OVERWROTE what the engine had just started. Measured: SemperFi"
        "\r\n\t\t// began R-Wpn-MG1Mk1 at t=80s six times over and never once"
        "\r\n\t\t// finished it, because its own list replaced it every tick."
        "\r\n\t\tif (_dLabs.length > 0 && _dTook === _dLabs.length) { return; }"
        "\r\n\t}"
        "\r\n\tcatch (e) { }\r\n")
    ai_done = []
    for path, fn_names, mode, label, fam in AI_HOOKS:
        with zipfile.ZipFile(MP_WZ) as z:
            try:
                src = z.read(path).decode("utf-8")
            except KeyError:
                continue
        hook = HOOK_LAB_PARAM if mode == "lab_param" else HOOK_SELF_LABS
        inserted = False
        for fn in fn_names:
            m = re.search(r"function\s+" + fn + r"\s*\([^)]*\)\s*\{", src)
            if not m:
                continue
            src = src[:m.end()] + hook + src[m.end():]
            inserted = True
            break
        if not inserted:
            fail(f"{label}: no research entry point matched {fn_names} in {path}")
        out = staging / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doctrine_ai_header(label, fam) + DOCTRINE_ENGINE_JS + src,
                       encoding="utf-8", newline="")
        ai_done.append(label)

    print(f"research engine ported to: {', '.join(ai_done)}")
    summary["research.json"].append(
        "- **The other four AIs share Nexus's research engine.** Cobra, "
        "BoneCrusher, NullBot and SemperFi steer by hard-coded topic lists that "
        "DOCTRINE's tree invalidated (BoneCrusher: 110 deleted + 103 crate-locked "
        "of 497 referenced). Each now tries the scoring engine first and falls "
        "back to its own list, so every AI benefits from the same tuning.")

    # "Start with Bases" was handing out every early defence for free.
    # rules/setup/base.js calls completeResearchOnTime(timeBaseTech=180), and
    # that function walks a HARDCODED table in camTechEnabler.js calling
    # completeResearch() directly -- it does not consult availability at all, so
    # DOCTRINE's gating was bypassed completely. Everything at <=180 was granted:
    # R-Defense-Tower01 (48), R-Defense-TankTrap01 (108), R-Defense-HardcreteWall
    # (129), R-Defense-Pillbox01/05 and HardcreteGate (177). That is precisely
    # the "AI has walls and bunkers it should not have the tech for" report.
    # Every R-Defense-* entry is removed from the table, so the base package
    # still grants the economy, propulsion and weapon tech that makes a starting
    # base playable, but no defensive structure comes free to anyone.
    TECH_ENABLER = "multiplay/script/functions/camTechEnabler.js"
    with zipfile.ZipFile(MP_WZ) as z:
        tech_src = z.read(TECH_ENABLER).decode("utf-8")
    m_start = tech_src.index("var allRes")
    m_end = tech_src.index("};", m_start)
    block = tech_src[m_start:m_end]
    kept, dropped = [], []
    for line in block.split(chr(10)):
        if re.match(r'\s*"R-Defense-[^"]*"\s*:', line):
            dropped.append(re.search(r'"([^"]+)"', line).group(1))
        else:
            kept.append(line)
    if not dropped:
        fail("camTechEnabler.js allRes has no R-Defense-* entries -- re-check "
             "before shipping an override")
    patched_tech = tech_src[:m_start] + chr(10).join(kept) + tech_src[m_end:]
    tech_dir = staging / "multiplay" / "script" / "functions"
    tech_dir.mkdir(parents=True, exist_ok=True)
    (tech_dir / "camTechEnabler.js").write_text(patched_tech, encoding="utf-8",
                                                newline="")
    print(f"start-with-bases: stripped {len(dropped)} free R-Defense-* topics "
          f"from the base tech package")
    summary["research.json"].append(
        f"- `camTechEnabler.js` allRes: removed {len(dropped)} `R-Defense-*` "
        f"entries so \"Start with Bases\" no longer grants free walls, gates, "
        f"bunkers or towers to anyone. Dropped: {', '.join(sorted(dropped))}.")

    # scripts
    doctrine_js = (HERE / "doctrine.js").read_text(encoding="utf-8")
    if TELEMETRY:
        # headless balance runs only; never in a build we hand over
        doctrine_js = doctrine_js.replace("const TELEMETRY = false;",
                                          "const TELEMETRY = true;", 1)
        print("!! TELEMETRY BUILD — per-sweep census enabled, do not ship")
    (staging / "multiplay" / "script" / "mods" / "doctrine.js").write_text(
        doctrine_js, encoding="utf-8", newline="\n")
    shutil.copy(HERE / "mod-init.js", staging / "multiplay" / "script" / "mods" / "init.js")

    # mod metadata
    json.dump({
        "name": "DOCTRINE",
        "author": "Martin Steinke",
        "type": "alternateMP",
        "version": "1.0.0",
        "description": "Research is earned in the field. Kills drop intel crates you must physically collect; short steep upgrade ladders; matchups that actually matter; scavengers as a real faction. Skirmish only.",
        "license": "GPL-2.0+",
        # Only ever built against 4.5.5 and 4.7.0 mp.wz and played on both.
        # 4.5.0-4.5.4 are untested, so they are not claimed.
        "minVersionSupported": "4.5.5",
        "maxVersionTested": TARGET,
    }, open(staging / "mod-info.json", "w", encoding="utf-8"), indent=1)

    write_summary()

    # package — ZIP renamed .wz, forward-slash member names
    wz_path = BUILD / "doctrine.wz"
    with zipfile.ZipFile(wz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(staging).as_posix())
    print(f"packaged: {wz_path} ({wz_path.stat().st_size // 1024} KB)")

    # install
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(wz_path, INSTALL_DIR / "doctrine.wz")
    print(f"installed: {INSTALL_DIR / 'doctrine.wz'}")


if __name__ == "__main__":
    main()
