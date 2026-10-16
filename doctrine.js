/*
 * DOCTRINE v3 — battlefield-salvaged research unlocks.
 * Target: Warzone 2100 4.5.5 / 4.7.0, skirmish vs AI.
 * Ships at: multiplay/script/mods/doctrine.js, included from
 * multiplay/script/mods/init.js (the engine's mod hook, loaded LAST by
 * rules/includes.js).
 *
 * THE MECHANIC
 *   Killing a worthwhile enemy unit can drop an intel crate at the wreck. Drive
 *   any unit over it and ONE research topic from the VICTIM'S weapon family is
 *   unlocked for whoever picked it up — you salvage THEIR tech. The engine
 *   removes the crate on pickup, so grabbing an enemy's crate denies it to them.
 *   Destroyed scenery can yield intel too, and wrecks sometimes leave oil drums.
 *
 * EVERY PLAYER PLAYS BY THESE RULES (AI compatible)
 *   State is tracked per player, drops roll for whoever made the kill, and the
 *   collector is whoever physically reaches the crate. Two engine facts shape
 *   how the AI is handled (both verified in the 4.7.0 source):
 *
 *   1. move.cpp checkLocalFeatures() ignores non-human players entirely unless
 *      the droid carries a DORDER_RECOVER order. So AI-owned crates get a
 *      recover order issued to a nearby unit, re-issued by the sweep timer, and
 *      a decay safety net so AI progress can never stall on pathing.
 *   2. The shipped AI scripts (Nexus, Cobra) research from hardcoded topic
 *      lists, so merely enabling a topic for them would do nothing. AI pickups
 *      therefore complete the topic directly and are charged its power cost.
 *
 * ENGINE NOTE (why the tree ships with EMPTY prerequisites on axis topics):
 * researchAvailable() auto-reveals any topic whose non-empty prereq list is
 * fully researched. Only topics with NO prerequisites wait for enableResearch().
 * All gating therefore lives in this script.
 */

// ───────────────────────────────────────────────────────────────── constants ──
const TIERS = 4;
const AXES  = ["Damage", "Range", "Reload", "Accuracy"];

// Drop tuning.
//   scavengers:  chance = DROP_BASE * SCAV_FLOOR * killerVet   (flat ~3.6%)
//   everyone else: chance = DROP_BASE_VET * rankFactor * weight * killerVet
//
// A factory-fresh unit has nothing to teach: intel comes from crews that had
// actually learned something before they died. So for non-scavenger victims the
// drop scales with the DEAD unit's EXPERIENCE — which the engine accrues from
// damage dealt as well as from kills, so the curve is continuous rather than
// stepped. A unit that never fired drops nothing; a lightly-blooded one already
// has a small chance; every hit it landed and especially every kill it scored
// raises it, up to EXP_FULL.
//
//   experience  0    -> 0.0%     (never fought)
//               0.5  -> 0.2%
//               2    -> 1.3%     (~one kill)
//               7    -> 6.6%
//              11+   -> 12.0%    (capped)
//
// droid.experience is exposed already divided by EXP_SCALE (65536) in
// quickjs_backend.cpp, so it is the same "kills-equivalent" number the rank
// thresholds use — EXP_FULL 11 matches the old rank-4 cap, keeping overall
// rates calibrated while making the curve smooth.
const DROP_BASE     = 0.20;   // scavenger path only (see SCAV_FLOOR)
const DROP_BASE_VET = 0.12;   // parity kill (weight 1.0) vs a fully-blooded victim
const EXP_FULL      = 11;     // victim experience at which the scaling maxes out
// Shape of the experience curve. 1.0 is linear; above 1.0 bends it DOWN at the
// low end while leaving the EXP_FULL cap untouched, so barely-blooded units drop
// noticeably less without changing what a veteran is worth.
//   exp   linear -> curved
//   0.5    0.5%  -> 0.2%
//   2      2.2%  -> 1.3%
//   7      7.6%  -> 6.6%
//   11+   12.0%  -> 12.0%  (unchanged)
const EXP_CURVE     = 1.3;
const DROP_CAP      = 0.90;
const VET_BONUS     = 0.60;   // up to +60% for a veteran KILLER (was +50%)
const VET_CAP       = 24;     // killer kills at which that bonus maxes out
const PITY_RATE     = 0.03;   // pity gained per miss, scaled by kill weight

// Scavengers get a FLAT drop weight, not max(killWeight, floor). Playtest found
// scav relics far too common, and the reason was that early on the cost-weight
// beat the floor: a 35-cost scav against a p75 of 55 scores 0.39, i.e. ~7.9%,
// not the intended 5%. Pinning it flat makes the rate predictable at any stage
// and stops early scav-clearing from being the best source of intel.
//   0.20 * 0.18 = 3.6% flat  (5.8% for a veteran killer)
// Scav misses still do NOT feed the pity pool, otherwise farming a scav base
// would pump the drop rate for real fights.
const SCAV_FLOOR  = 0.14;

// Destroyed scenery (houses, ruins, wrecks) occasionally hides usable tech.
// Deliberately rare: a bonus, not a farming route.
const HOUSE_CHANCE = 0.015;   // 1.5% per destroyed damageable feature

/* Scavengers living in the ruins. Flattening a house turns its occupants out:
   they were always meant to, and never did -- nothing in the mod spawned them.
   Only real buildings count (BUILDING / SKYSCRAPER); trees, wrecks, boulders
   and vehicles are scenery and produce nobody. Needs a scavenger player in
   the game, so it is silent when scavengers are switched off. */
const HOUSE_SCAV_CHANCE = 0.40;   // 40% of flattened houses are occupied
const HOUSE_SCAV_MIN = 1;
const HOUSE_SCAV_MAX = 5;

// Wrecks sometimes leave fuel behind. The engine grants the power on pickup.
const DRUM_CHANCE  = 0.05;    // 5% per destroyed enemy unit or building

const STALENESS   = 4000;     // ms — max age of a last-hit record
const P75_REFRESH = 30000;    // ms — reference recompute interval
const CRATE_TTL   = 300000;   // ms — intel decays after 5 minutes in the field
const SWEEP_EVERY = 20000;    // ms — expiry + AI recover-order cadence

/* Build-time switch, flipped to true by `build_mod.py --telemetry`. Off in every
   shipped build; on it dumps a per-player census each sweep so headless runs can
   be measured rather than guessed at. */
const TELEMETRY = false;

// weaponSubClass -> family key. Must match generate_tree.py FAMILIES.
const SUBCLASS_TO_FAMILY = {
	"MACHINE GUN": "MG",      "CANNON":    "Cannon",   "ROCKET":  "Rocket",
	"MISSILE":     "Missile", "FLAME":     "Flamer",   "MORTARS": "Mortar",
	"HOWITZERS":   "Howitzer","ENERGY":    "Laser",    "GAUSS":   "Rail",
	"A-A GUN":     "AA",      "EMP":       "EMP"
};

// Feature stattypes that are NOT destructible scenery. NOTE: feature.stattype
// is a NUMBER, not a string, so these must be compared against the engine
// constants — a string-keyed lookup silently never matches.
function isSpecialFeature(f) {
	return f.stattype === ARTIFACT || f.stattype === OIL_DRUM
		|| f.stattype === OIL_RESOURCE;
}

// Breadth credentials: Combined Arms Doctrine N opens infrastructure tech once
// the player holds tier 2+ (= tier 1 fully researched) in N different families.
const BREADTH_LEVELS = [2, 3, 4, 5];

// Scavenger research parity (from the uuscav2 mod, folded in here because two
// mods cannot both ship multiplay/script/mods/init.js): every research any
// player completes is granted to the scavengers. Set false to disable.
const SCAV_RESEARCH_PARITY = true;

// ── Research facility limits ─────────────────────────────────────────────────
// Start with TWO labs; every completed research upgrade earns another, up to five.
// Driven from the script with setStructureLimits() rather than from research
// data: R-Struc-Limit-Labs was the only topic anywhere using Building.Limit, and
// neither the docs nor the data establish what base its percentage applies to
// (A0ResearchFacility has no `limit` key) nor whether applyLimitSet() would
// override it. setStructureLimits() is documented, takes a player argument, and
// is what vanilla itself uses — so this works for the AI too.
//
// Ordering is favourable: vanilla's eventGameInit runs setupStructureLimit() AND
// applyLimitSet() before ours, because we capture and call the previous handler
// first — so our value is written last.
const LAB_LIMIT_START = 2;
const LAB_LIMIT_MAX   = 5;
const LAB_STRUCTURE   = "A0ResearchFacility";

// ── Standard-issue weapon ────────────────────────────────────────────────────
// Vanilla's setupComponents() is an empty stub, so NOTHING is buildable at match
// start — you must research R-Wpn-MG1Mk1 (60 pts) before you have any weapon at
// all. That is survivable in vanilla, but DOCTRINE runs labs at 40% speed, and
// the shipped Nexus AI only consults its priority research lists 10% of the time
// on Medium (nexus_includes/research.js doResearch) — the rest of the time it
// picks at RANDOM from everything available. One random pick of a 1200-point
// topic then blocks its single lab for a very long time, which is why the AI
// fielded attack units late or not at all.
//
// So the moment a player's research facility comes online, the basic machinegun
// is standard-issue. Cheap, thematic, and it makes early aggression reliable for
// the AI without depending on its research ordering.
const STARTER_WEAPON = "MG1Mk1";
/* ...and the 60-point topic that actually unlocks it. It has no
   prerequisites, which in DOCTRINE means "hidden until enabled", so it has
   to be switched on explicitly or nobody could ever research it. */
const STARTER_TOPIC = "R-Wpn-MG1Mk1";

// ── Standard-issue defences ──────────────────────────────────────────────────
// The AI was being overrun by scavengers because it could not fortify at all.
// 57 of the 72 defence-unlocking topics are crate-gated, and Nexus's own
// STANDARD_BASIC_DEFENSES list (nexus_standards/buildDefinitions.js) opens with
// PillBox1 and GuardTower6 — PillBox1 needs R-Wpn-MG-Damage01, GuardTower6 needs
// the mini-pod line, so its entire early repertoire was locked behind crates it
// had not earned yet. With nothing to build it just took the hits.
//
// The AI's one free emplacement: the Heavy Machinegun Guard Tower, granted at
// the command centre and hard-capped below. A no-defences experiment measured
// slightly better army numbers, but in real play an AI with zero emplacements
// reads as broken and folds to the first raid that catches its army out of
// position — so the tower is back, and the cap is what prevents the old
// carpet-of-bunkers failure. The production-side fixes (factory allowance,
// crate flow) are what actually made the AI field an army.
/* Deliberately EMPTY. GuardTower1 used to be switched on here for free once a
   player had an HQ, because R-Defense-Tower01 requires R-Wpn-MG1Mk1 and MG1Mk1
   was hidden -- so without the crutch nobody could ever research the tower.
   Round 24 made MG1Mk1 researchable for everyone at kickoff, so that path is
   open now and the crutch became a leak: the Heavy Machinegun Guard Tower
   turned buildable four minutes in whether or not you had researched it.
   Everyone earns it through R-Defense-Tower01 now, same as the gun itself. */
const STARTER_DEFENCES = [];
// ...but not immediately. Granted at t=0 the AI pours its opening power into
// towers instead of factories and units (measured: def=6-7, atk=0-2, dead by
// ~500s; with no towers at all the same AI reached 8 attackers). Delaying the
// grant gives the opening to the army and the towers arrive as a second layer.
const AI_TOWER_DELAY = 240000;   // ms before the AI may place them

// It still needs a leash for later, though. Once basic MG defences DO unlock,
// Nexus builds them without limit and in clusters — the behaviour that started
// this. These are capped whether or not they were ever granted: enough to
// picket the base plus one per derrick it holds, and no more. Heavier defences
// further up the tree are expensive enough to limit themselves.
const AI_CAPPED_DEFENCES = ["GuardTower1", "PillBox1"];
const AI_TOWER_BASE  = 4;    // main base picket
const AI_TOWER_MAX   = 10;   // absolute ceiling regardless of derrick count

/* NOTE: the AI difficulty gradient does NOT live here. It cannot: in the rules
   script context playerData[p].difficulty reports a flat 2 (MEDIUM) for every
   AI player regardless of the lobby or challenge setting — verified by dumping
   it for all ten slots across Easy/Hard/Insane configs. The gradient is applied
   from inside the AI's own script instance instead, where the `difficulty`
   global is that AI's real setting; see DIFFICULTY_GRADIENT_JS in build_mod.py,
   which is appended to the Nexus file DOCTRINE already overrides. */

// Rank curve, in kills. Vanilla is 0/4/8/16/32/64/128/256/512 — Hero is
// effectively unreachable. The per-rank bonuses themselves are compile-time
// constants in droid.h (EXP_ACCURACY_BONUS 5%, EXP_REDUCE_DAMAGE 6%,
// EXP_SPEED_BONUS 5%, all per level) and CANNOT be changed by a data mod, so
// the only way to make veterancy count for more is to reach the ranks sooner.
// This curve is compressed again over the previous one (Hero at 40, not 64),
// which also feeds the drop model above — veterans are worth killing.
// Assign the WHOLE array at once (doc/js-globals.md).
const RANK_THRESHOLDS = [0, 2, 4, 7, 11, 16, 22, 30, 40];

// ───────────────────────────────────────────────────────────────────── state ──
// All per-player maps are keyed by player number.
var unlocked   = {};   // p -> { topicId: true }  revealed for that player
var researched = {};   // p -> { topicId: true }  completed by that player
var pity       = {};   // p -> accumulated miss weight
var refCache   = {};   // p -> { value, at }
var lastHit    = {};   // "TYPE:id" -> { t, exp, killer }
var crates     = {};   // featureId -> { fam, owner, born, x, y, ordered }
var drums      = {};   // featureId -> true   (drums WE spawned)
var dumpedOnce = false;
var resDumped  = {};
var stats      = { drops: 0, recovered: 0, denied: 0, decayed: 0, drums: 0, houses: 0,
                   houseScavs: 0 };

function unlockedOf(p)   { if (!unlocked[p])   { unlocked[p]   = {}; } return unlocked[p]; }
function researchedOf(p) { if (!researched[p]) { researched[p] = {}; } return researched[p]; }

function isHuman(p) { return p === selectedPlayer; }

// ─────────────────────────────────────────────────────────────────── helpers ──

function topicId(fam, axis, tier) {
	return "R-Wpn-" + fam + "-" + axis + "0" + tier;
}

/* Weapon -> family lookup, built once from the stats themselves.
   IMPORTANT: Stats.Weapon is keyed by the weapon's DISPLAY NAME ("*BaBa MG*"),
   not by its id ("BaBaMG"), so Stats.Weapon[droid.weapons[i].id] is always
   undefined — which silently killed every drop in v2. Index by both. */
var WPN_FAMILY = {};
(function buildWeaponFamilyMap() {
	if (typeof Stats === "undefined" || !Stats.Weapon) { return; }
	for (var key in Stats.Weapon) {
		var s = Stats.Weapon[key];
		if (!s) { continue; }
		var fam = SUBCLASS_TO_FAMILY[s.ImpactClass];
		if (!fam) { continue; }
		WPN_FAMILY[key] = fam;
		if (s.Id) { WPN_FAMILY[s.Id] = fam; }
	}
})();

/* Families represented by a droid's turrets. Used on the VICTIM: the crate
   carries tech from the family the dead unit was fielding. */
function weaponFamilies(droid) {
	var out = [];
	if (!droid.weapons) { return out; }
	for (var i = 0; i < droid.weapons.length; i++) {
		var w = droid.weapons[i];
		var fam = WPN_FAMILY[w.id];
		if (!fam) { fam = WPN_FAMILY[w.name]; }
		if (fam && out.indexOf(fam) === -1) { out.push(fam); }
	}
	return out;
}

/* Reference = 75th-percentile cost of that player's living combat droids.
   NOT the mean (a screen of cheap junk would drag the bar down) and NOT the
   attacker's own cost (that rewards sniping with the cheapest unit). p75 can
   only be lowered by actually giving up your good units. */
function myReference(p) {
	var c = refCache[p];
	if (c && gameTime - c.at < P75_REFRESH) { return c.value; }
	var mine = enumDroid(p).filter(function (d) {
		return d.droidType === DROID_WEAPON || d.droidType === DROID_CYBORG;
	});
	if (mine.length === 0) { return (c && c.value > 0) ? c.value : 1; }
	var costs = mine.map(function (d) { return d.cost; }).sort(function (a, b) { return a - b; });
	var idx = Math.floor(costs.length * 0.75);
	if (idx > costs.length - 1) { idx = costs.length - 1; }
	refCache[p] = { value: costs[idx], at: gameTime };
	return costs[idx];
}

/*  r  <  0.40  -> 0            nothing to learn from something far beneath you
   0.40..1.00   -> ramp 0 -> 1
   1.00..2.50   -> weight == r
    r >= 2.50   -> 2.50 cap                                                    */
function killWeight(targetCost, ref) {
	if (ref <= 0) { return 0; }
	var r = targetCost / ref;
	if (r < 0.40) { return 0; }
	if (r < 1.00) { return (r - 0.40) / 0.60; }
	if (r < 2.50) { return r; }
	return 2.50;
}

function allAxesResearched(p, fam, tier) {
	var done = researchedOf(p);
	for (var i = 0; i < AXES.length; i++) {
		if (!done[topicId(fam, AXES[i], tier)]) { return false; }
	}
	return true;
}

/* Lowest tier not yet fully researched. Because it is the LOWEST, every tier
   below it is complete by construction — the tier gate is inherent. */
function currentTier(p, fam) {
	for (var t = 1; t <= TIERS; t++) {
		if (!allAxesResearched(p, fam, t)) { return t; }
	}
	return TIERS + 1;
}

/* The topic a crate yields for THIS player right now, or null. Chosen at pickup
   time, not drop time, so one crate suits whoever actually reaches it. */
function nextTopic(p, fam) {
	var t = currentTier(p, fam);
	if (t > TIERS) { return null; }
	var open = unlockedOf(p), done = researchedOf(p), cand = [];
	for (var i = 0; i < AXES.length; i++) {
		var id = topicId(fam, AXES[i], t);
		if (!open[id] && !done[id]) { cand.push(id); }
	}
	if (cand.length === 0) { return null; }
	return cand[syncRandom(cand.length)];   // syncRandom, NEVER Math.random
}

/* A family this player could still learn something in — used for scenery intel,
   which has no victim to inherit a family from. Naturally lands at the player's
   own level because nextTopic() tracks their current tier. */
function offerableFamily(p) {
	var cand = [], seen = {};
	for (var sub in SUBCLASS_TO_FAMILY) {
		var fam = SUBCLASS_TO_FAMILY[sub];
		if (seen[fam]) { continue; }
		seen[fam] = true;
		if (nextTopic(p, fam) !== null) { cand.push(fam); }
	}
	if (cand.length === 0) { return null; }
	return cand[syncRandom(cand.length)];
}

// ───────────────────────────────────────────────────────── crates and drops ──

/* Point a nearby unit at the crate. move.cpp checkLocalFeatures() skips
   non-human players entirely UNLESS the droid is on a DORDER_RECOVER order, so
   without this an AI could never collect anything. VTOLs and transporters
   cannot pick up at all, so they are filtered out. */
function orderRecover(p, feature) {
	var units = enumDroid(p).filter(function (d) {
		return !d.isVTOL && d.droidType !== DROID_TRANSPORTER
			&& d.droidType !== DROID_SUPERTRANSPORTER;
	});
	var best = null, bestD = 99999999;
	for (var i = 0; i < units.length; i++) {
		var dx = units[i].x - feature.x, dy = units[i].y - feature.y;
		var d2 = dx * dx + dy * dy;
		if (d2 < bestD) { bestD = d2; best = units[i]; }
	}
	if (best === null) { return false; }
	orderDroidObj(best, DORDER_RECOVER, feature);
	return true;
}

/* A wreck often sits on an occupied tile, where addFeature() logs
   "Building feature on tile already occupied" and returns null. Try the spot
   itself, then its immediate neighbours, so drops land quietly instead of
   being lost and spamming the log. */
const PLACE_OFFSETS = [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1],
                       [1, 1], [-1, -1], [1, -1], [-1, 1]];

function placeFeature(kind, x, y) {
	for (var i = 0; i < PLACE_OFFSETS.length; i++) {
		var fx = x + PLACE_OFFSETS[i][0], fy = y + PLACE_OFFSETS[i][1];
		if (fx < 1 || fy < 1 || fx >= mapWidth - 1 || fy >= mapHeight - 1) { continue; }
		// Pre-check the tile: addFeature() logs an engine error on every blocked
		// attempt, so probing first keeps the log clean rather than relying on
		// its null return. getObject() catches units/structures/features sitting
		// on the tile; water and cliffs are excluded by terrain type.
		if (getObject(fx, fy) !== null) { continue; }
		// TER_* are documented as terrainType() return values but are not
		// guaranteed to be registered globals, and an undefined reference here
		// would throw and kill every drop — so probe defensively.
		if (typeof TER_WATER !== "undefined" && terrainType(fx, fy) === TER_WATER) { continue; }
		if (typeof TER_CLIFFFACE !== "undefined" && terrainType(fx, fy) === TER_CLIFFFACE) { continue; }
		var f = addFeature(kind, fx, fy);
		if (f !== null) { return f; }
	}
	return null;
}

/* Find the live engine-side feature for a just-placed crate. Matches on tile
   position rather than identity, because position is the one thing that is
   stable across the addFeature -> enumFeature boundary. */
function resolveFeature(placed) {
	var list = enumFeature(ALL_PLAYERS);
	for (var i = 0; i < list.length; i++) {
		var f = list[i];
		if (f.stattype !== ARTIFACT) { continue; }
		if (Math.abs(f.x - placed.x) < 1 && Math.abs(f.y - placed.y) < 1) { return f; }
	}
	return null;
}

function spawnCrate(fam, owner, x, y) {
	// addFeature is MULTIPLAY_UNSAFE — fine here: DOCTRINE targets skirmish vs AI.
	var crate = placeFeature("Crate", x, y);
	if (crate === null) { return false; }
	// Re-resolve the feature through enumFeature and key on THAT id. The object
	// addFeature hands back does not reliably carry the same id the engine then
	// reports, and the expiry sweep matches against enumFeature — so keying on
	// the returned object silently orphaned most crates after five seconds.
	// Measured before this fix: 4 crates dropped, 1 still tracked, 0 ever
	// recoverable, and research completely stalled for every AI.
	crate = resolveFeature(crate);
	if (crate === null) { return false; }
	crates[crate.id] = { fam: fam, owner: owner, born: gameTime,
		x: crate.x, y: crate.y, ordered: false };
	stats.drops++;
	if (!isHuman(owner)) {
		crates[crate.id].ordered = orderRecover(owner, crate);
	} else {
		console("DOCTRINE: " + fam + " intel dropped at (" + Math.floor(crate.x)
			+ ", " + Math.floor(crate.y) + ") — recover it before the enemy does!");
	}
	return true;
}

/* Hand a topic to a player.
   Human: revealed in the labs and paid for as normal — that is the whole game.
   AI: the shipped AI scripts only research their own hardcoded lists, so an
   enabled topic would sit there forever. Complete it outright instead, and
   charge the power so they pay for it too. */
function grantTopic(p, topic, fam, how) {
	if (isHuman(p)) {
		enableResearch(topic, p);
		unlockedOf(p)[topic] = true;
		console("DOCTRINE: intel " + how + " — " + topic + " is now available for research.");
		return;
	}
	var r = getResearch(topic, p);
	var cost = (r && r.power) ? r.power : 0;
	var have = playerPower(p);
	setPower(have > cost ? have - cost : 0, p);
	// enableResearch FIRST: completeResearch() does nothing for a topic that was
	// never made "possible" for that player, and every axis topic ships with
	// empty prerequisites precisely so it stays impossible until granted.
	// hackNetOff() around the completion applies it directly instead of sending
	// it as a sync message (the same guard uuscav2 uses for its scav parity).
	enableResearch(topic, p);
	hackNetOff();
	completeResearch(topic, p);
	hackNetOn();
	unlockedOf(p)[topic] = true;
	researchedOf(p)[topic] = true;
}

function collectCrate(feature, p, how) {
	var rec = crates[feature.id];
	if (rec === undefined) { return; }
	delete crates[feature.id];
	var topic = nextTopic(p, rec.fam);
	if (topic === null) {
		if (isHuman(p)) {
			console("DOCTRINE: recovered " + rec.fam + " intel, but there is nothing "
				+ "new to learn in that branch yet.");
		}
		clearFeature(feature);
		return;
	}
	// Count every recovery, not just the player's. Counting only human pickups
	// made the AI look like it never collected anything, which sent an entire
	// debugging pass down the wrong path.
	stats.recovered++;
	if (!isHuman(p) && isHuman(rec.owner)) { stats.denied++; }
	grantTopic(p, topic, rec.fam, how);
	clearFeature(feature);
	if (!isHuman(p) && isHuman(rec.owner)) {
		console("DOCTRINE: the enemy recovered our " + rec.fam + " intel!");
	}
}

/* The engine fires eventPickup and grants the pickup, but does NOT remove a
   GENERIC ARTEFACT feature in skirmish — verified in-game, the crate sat there
   after being collected. Clear it ourselves so intel disappears the moment it
   is captured, and so nothing can be walked over twice. */
function clearFeature(feature) {
	if (feature) { removeObject(feature, false); }
}

function tryDrop(victim, rec) {
	var p = rec.killer;
	// A scavenger kill produces nothing. Scavengers get most of the kills in a
	// scav-heavy game, and a crate owned by them is dead weight twice over: they
	// never execute DORDER_RECOVER (their own script retasks every unit each
	// second), and SCAV_RESEARCH_PARITY already hands them every topic anyone
	// else completes. Measured before this: of 8 crates in one game, 5 were
	// scavenger-owned and silently discarded, and no AI completed a single
	// weapon upgrade all game.
	if (typeof scavengerPlayer !== "undefined" && p === scavengerPlayer) { return; }
	var isScav = (typeof scavengerPlayer !== "undefined"
		&& victim.player === scavengerPlayer);
	// Scavenger INFANTRY are the pair-built chaff now -- dozens of them die
	// every minute, and each one rolling on the crate table made bodies,
	// not battles, the source of intel. People carry nothing worth salvaging.
	if (isScav && victim.type === DROID && victim.droidType === DROID_PERSON) { return; }

	var w = killWeight(victim.cost, myReference(p));
	var base;
	if (isScav) {
		w = SCAV_FLOOR;              // flat, never the cost-weight — see SCAV_FLOOR
		base = DROP_BASE * w;
	} else {
		// A crew that never fought learned nothing worth salvaging — no drop,
		// and no pity either, exactly like a target far beneath your own army.
		// Everything above zero scales continuously with what it had learned.
		var vexp = victim.experience || 0;
		if (vexp <= 0) { return; }
		base = DROP_BASE_VET * Math.pow(Math.min(vexp / EXP_FULL, 1), EXP_CURVE) * w;
	}
	if (w <= 0 || base <= 0) { return; }

	var fams = weaponFamilies(victim);
	if (fams.length === 0) { return; }   // trucks / sensors / NEXUS carry no tech

	var vet = 1 + VET_BONUS * Math.min((rec.exp || 0) / VET_CAP, 1);
	var have = isScav ? 0 : (pity[p] || 0);
	var chance = Math.min(base * vet + have, DROP_CAP);

	if (syncRandom(1000) >= Math.floor(chance * 1000)) {
		if (!isScav) { pity[p] = have + PITY_RATE * w; }
		return;
	}
	var fam = fams[syncRandom(fams.length)];
	if (spawnCrate(fam, p, victim.x, victim.y)) {
		if (!isScav) { pity[p] = 0; }
	} else if (!isScav) {
		pity[p] = have + PITY_RATE * w;
	}
}

function tryDrum(obj, killer) {
	// Same rule as the crates: scavenger infantry leave no oil drums either.
	if (typeof scavengerPlayer !== "undefined" && obj.player === scavengerPlayer
			&& obj.type === DROID && obj.droidType === DROID_PERSON) { return; }
	if (syncRandom(1000) >= Math.floor(DRUM_CHANCE * 1000)) { return; }
	var d = placeFeature("OilDrum", obj.x, obj.y);
	if (d === null) { return; }
	drums[d.id] = { owner: killer, born: gameTime, ordered: false };
	stats.drums++;
	if (!isHuman(killer)) { drums[d.id].ordered = orderRecover(killer, d); }
}

/* Who flattened this house? Features carry no attacker, so credit the
   closest unit that could plausibly have shot it -- scavengers excluded,
   they salvage nothing. Returns null when nobody is nearby. */
const HOUSE_CREDIT_RANGE = 8;
function featureKiller(obj) {
	var best = null, bestD = HOUSE_CREDIT_RANGE + 1;
	var near = enumRange(obj.x, obj.y, HOUSE_CREDIT_RANGE, ALL_PLAYERS, false);
	for (var i = 0; i < near.length; i++) {
		var o = near[i];
		if (o.type !== DROID) { continue; }
		if (typeof scavengerPlayer !== "undefined" && o.player === scavengerPlayer) { continue; }
		var dx = o.x - obj.x, dy = o.y - obj.y;
		var d = Math.sqrt(dx * dx + dy * dy);
		if (d < bestD) { bestD = d; best = o.player; }
	}
	return best;
}

function isHouseFeature(f) {
	return (typeof BUILDING !== "undefined" && f.stattype === BUILDING)
		|| (typeof SKYSCRAPER !== "undefined" && f.stattype === SKYSCRAPER);
}

function tryHouseScavs(obj) {
	if (typeof scavengerPlayer === "undefined" || scavengerPlayer < 0) { return; }
	if (!isHouseFeature(obj)) { return; }
	if (syncRandom(1000) >= Math.floor(HOUSE_SCAV_CHANCE * 1000)) { return; }
	var n = HOUSE_SCAV_MIN + syncRandom(HOUSE_SCAV_MAX - HOUSE_SCAV_MIN + 1);
	var made = 0;
	for (var i = 0; i < n; i++) {
		try {
			if (addDroid(scavengerPlayer, obj.x, obj.y, "Scavenger",
					"B1BaBaPerson01", "BaBaLegs", "", "", "BaBaMG")) { made++; }
		} catch (e) { break; }
	}
	if (made > 0) { stats.houseScavs += made; }
}

function tryHouseIntel(obj, killer) {
	if (syncRandom(1000) >= Math.floor(HOUSE_CHANCE * 1000)) { return; }
	var fam = offerableFamily(killer);
	if (fam === null) { return; }
	if (spawnCrate(fam, killer, obj.x, obj.y)) { stats.houses++; }
}

/* One lab to start, +1 per completed research upgrade, hard-capped at five. */
function labLimitFor(p) {
	var done = researchedOf(p), n = 0;
	for (var k in done) {
		if (k.indexOf("R-Struc-Research-Upgrade") === 0 || k === "R-Struc-Limit-Labs") { n++; }
	}
	var lim = LAB_LIMIT_START + n;
	return lim > LAB_LIMIT_MAX ? LAB_LIMIT_MAX : lim;
}

function applyLabLimit(p) {
	setStructureLimits(LAB_STRUCTURE, labLimitFor(p), p);
}

/* Cap the AI's starter emplacements: a base picket plus one per derrick. Without
   this Nexus builds them without limit and in clusters. Recomputed by the sweep
   so the allowance grows as it expands, and never applied to a human. */


function applyTowerLimit(p) {
	if (isHuman(p)) { return; }
	var derricks = enumStruct(p).filter(function (s) {
		return s.stattype === RESOURCE_EXTRACTOR;
	}).length;
	var lim = AI_TOWER_BASE + derricks;
	if (lim > AI_TOWER_MAX) { lim = AI_TOWER_MAX; }
	for (var i = 0; i < AI_CAPPED_DEFENCES.length; i++) {
		setStructureLimits(AI_CAPPED_DEFENCES[i], lim, p);
	}
}

/* Combined Arms Doctrine N: opens once N families are at tier 2+. The
   credential is a 10-point certificate; the infrastructure topics behind it use
   ordinary prerequisites and cascade natively once it is researched. */
/* One researched tier-1 axis is enough to call a family "fielded" for the
   Combined Arms (Breadth) credentials. The old bar -- all FOUR axes at tier 1,
   each needing its own crate -- made Breadth-2 cost 8 specific crates, which at
   the measured crate rate never happened; 200 topics (the entire late
   infrastructure and cyborg branch) sat behind it, and research appeared to
   simply stop mid-game. */
function anyAxisResearched(p, fam, tier) {
	var done = researchedOf(p);
	for (var i = 0; i < AXES.length; i++) {
		if (done[topicId(fam, AXES[i], tier)]) { return true; }
	}
	return false;
}

function checkBreadth(p) {
	var families = 0, seen = {};
	for (var sub in SUBCLASS_TO_FAMILY) {
		var fam = SUBCLASS_TO_FAMILY[sub];
		if (seen[fam]) { continue; }
		seen[fam] = true;
		if (anyAxisResearched(p, fam, 1)) { families++; }
	}
	var open = unlockedOf(p);
	for (var i = 0; i < BREADTH_LEVELS.length; i++) {
		var n = BREADTH_LEVELS[i];
		var cid = "R-Cred-Breadth0" + n;
		if (families < n || open[cid]) { continue; }
		open[cid] = true;
		if (isHuman(p)) {
			enableResearch(cid, p);
			console("DOCTRINE: Combined Arms Doctrine " + n + " — field experience in "
				+ n + " weapon branches. New infrastructure options open.");
		} else {
			completeResearch(cid, p);
			researchedOf(p)[cid] = true;
		}
	}
}

/* Per-player census for headless balance runs: who has an army, who has trucks,
   who is holding oil, and how much concrete is going up. Only ever called when
   the build-time TELEMETRY switch is on. */
function doctrineCensus() {
	if (TELEMETRY && !dumpedOnce) {
		dumpedOnce = true;
		var probe = ["PillBox1","GuardTower1","A0HardcreteMk1Wall","A0HardcreteMk1CWall",
		             "PillBox4","GuardTower6","Sys-SensoTower02","A0BaBaFactory"];
		var line0 = "AVAIL baseType=" + (typeof baseType !== "undefined" ? baseType : "?");
		for (var q = 1; q <= 2; q++) {
			line0 += " || p" + q + ":";
			for (var b = 0; b < probe.length; b++) {
				if (isStructureAvailable(probe[b], q)) { line0 += " " + probe[b]; }
			}
			var av = enumResearch(q);
			line0 += " [avail-research=" + av.length + "]";
		}
		debug(line0);
	}
	if (TELEMETRY && (gameTime < 30000 || gameTime > 300000) && !resDumped[Math.floor(gameTime/300000)]) {
		resDumped[Math.floor(gameTime/300000)] = true;
		var av = enumResearch(1), ids = [];
		for (var q = 0; q < av.length && q < 30; q++) { ids.push(av[q].name || av[q].id); }
		debug("AVAILRES t=" + Math.floor(gameTime/1000) + "s n=" + av.length + " :: " + ids.join(" "));
	}
	var line = "CENSUS t=" + Math.floor(gameTime / 1000) + "s";
	for (var p = 0; p < maxPlayers; p++) {
		var ds = enumDroid(p), att = 0, trk = 0, cyb = 0;
		for (var i = 0; i < ds.length; i++) {
			if (ds[i].droidType === DROID_CONSTRUCT) { trk++; }
			else if (ds[i].droidType === DROID_CYBORG) { att++; cyb++; }
			else if (ds[i].droidType === DROID_WEAPON) { att++; }
		}
		var ss = enumStruct(p), def = 0, oil = 0, fac = 0;
		for (var j = 0; j < ss.length; j++) {
			if (ss[j].stattype === DEFENSE) { def++; }
			else if (ss[j].stattype === RESOURCE_EXTRACTOR) { oil++; }
			else if (ss[j].stattype === FACTORY) { fac++; }
		}
		var nres = 0, ndoc = 0, done = researchedOf(p);
		for (var rk in done) {
			nres++;
			if (/^R-Wpn-.+-(Damage|Range|Reload|Accuracy)0[1-9]$/.test(rk)) { ndoc++; }
		}
		var walls = enumStruct(p).filter(function (w) {
			return w.stattype === WALL;
		}).length;
		line += " | p" + p + " atk=" + att + " cyb=" + cyb + " trk=" + trk + " fac=" + fac
		      + " def=" + def + " wall=" + walls + " oil=" + oil
		      + " res=" + nres + "(" + ndoc + "doc) pw=" + Math.round(playerPower(p));
	}
	var arts = enumFeature(ALL_PLAYERS).filter(function (f) { return f.stattype === ARTIFACT; }).length;
	var tracked = 0; for (var ck in crates) { tracked++; }
	var drumsOnMap = enumFeature(ALL_PLAYERS).filter(function (f) {
		return f.stattype === OIL_DRUM;
	}).length;
	var recovering = 0;
	for (var rp = 0; rp < maxPlayers; rp++) {
		if (isHuman(rp)) { continue; }
		var dl = enumDroid(rp);
		for (var di = 0; di < dl.length; di++) {
			if (dl[di].order === DORDER_RECOVER) { recovering++; }
		}
	}
	line += " || drumsMap=" + drumsOnMap + " aiRecovering=" + recovering
	      + " drumsSpawned=" + stats.drums;
	line += " || onmap=" + arts + " tracked=" + tracked + " drops=" + stats.drops + " recovered=" + stats.recovered
	      + " denied=" + stats.denied + " decayed=" + stats.decayed;
	// Telemetry only, but guard it anyway: with scavengers switched off
	// scavengerPlayer is undefined and enumDroid(undefined) throws, which
	// would break every census line in a debug build for no good reason.
	var hasScav = (typeof scavengerPlayer !== "undefined" && scavengerPlayer >= 0);
	var sc = hasScav ? enumDroid(scavengerPlayer) : [];
	var ss2 = hasScav ? enumStruct(scavengerPlayer) : [];
	line += " | scav=" + (sc === null ? 0 : sc.length)
		+ " scavkinds=[" + (function () {
			var seen = {}, out = [];
			if (sc !== null) { for (var q = 0; q < sc.length; q++) {
				if (!seen[sc[q].name]) { seen[sc[q].name] = true; out.push(sc[q].name); }
			} }
			return out.join(",");
		})() + "]"
	      + " scavstruct=" + (ss2 === null ? 0 : ss2.length);
	debug(line);
}

/* Expiry sweep. Also re-issues AI recover orders (the AI scripts retask their
   units constantly, so one order at drop time is not enough) and, when an
   AI-owned crate finally decays, grants it anyway so AI progress can never
   stall on pathing. A human gets no such safety net — collecting is the game.
   Grab an enemy crate before it decays and you deny it outright. */
function doctrineCrateSweep() {
	/* Prune the last-hitter map. An entry is written for every object that is
	   ATTACKED, and only ever deleted when that object is destroyed -- so
	   anything shot at and merely damaged left a permanent entry. The engine
	   serialises script globals into every savegame, so it grew the save as
	   well as memory over a long game. Records older than STALENESS can never
	   be used again (eventDestroyed rejects them), so they go here. */
	for (var hk in lastHit) {
		if (gameTime - lastHit[hk].t > STALENESS) { delete lastHit[hk]; }
	}
	var alive = {}, list = enumFeature(ALL_PLAYERS);
	for (var i = 0; i < list.length; i++) {
		if (list[i].stattype === ARTIFACT || list[i].stattype === OIL_DRUM) {
			alive[list[i].id] = list[i];
		}
	}
	for (var fid in crates) {
		var rec = crates[fid];
		var f = alive[fid];
		if (f === undefined) {
			// Taken or gone — but never untrack a crate the sweep merely missed
			// on the tick it spawned, or the artifact is orphaned on the map.
			if (gameTime - rec.born > 5000) { delete crates[fid]; }
			continue;
		}
		if (gameTime - rec.born > CRATE_TTL) {
			if (!isHuman(rec.owner)) {
				collectCrate(f, rec.owner, "recovered");          // AI safety net
			} else {
				delete crates[fid];
				stats.decayed++;
				console("DOCTRINE: " + rec.fam + " intel decayed in the field.");
			}
			removeObject(f, false);
			continue;
		}
		if (!isHuman(rec.owner)) { rec.ordered = orderRecover(rec.owner, f); }
	}
	// Drums need the same treatment crates get. checkLocalFeatures() in move.cpp
	// only lets a NON-human player pick a feature up while that droid is on a
	// DORDER_RECOVER order, and the AI scripts retask their units constantly --
	// so a single order at drop time is almost always overwritten within a
	// second and the drum then sits there forever. Measured: 9 drums spawned,
	// aiRecovering=0 at every sample.
	for (var did in drums) {
		var drec = drums[did];
		if (alive[did] === undefined) { delete drums[did]; continue; }
		if (drec && !isHuman(drec.owner)) {
			drec.ordered = orderRecover(drec.owner, alive[did]);
		}
	}
	if (TELEMETRY) { doctrineCensus(); }
	// re-cap AI emplacements as their derrick count changes
	for (var tp = 0; tp < maxPlayers; tp++) { applyTowerLimit(tp); grantStarterDefences(tp); }
}

// ──────────────────────────────────────────────────────────────────── events ──
//
// All rules scripts share ONE global scope and this file loads LAST. The
// handlers below are ASSIGNED (not declared) so the captures above each one run
// first — a function declaration would hoist over the vanilla handler before
// the capture executes and recurse into itself.
//
// Captures are separate function-valued globals on purpose: the savegame
// serialiser skips function-typed globals, so they survive save/load and are
// re-captured when the scripts re-include. Do NOT move them into an object.
var __doctrinePrevAttacked   = (typeof eventAttacked   === "function") ? eventAttacked   : null;
var __doctrinePrevDestroyed  = (typeof eventDestroyed  === "function") ? eventDestroyed  : null;
var __doctrinePrevResearched = (typeof eventResearched === "function") ? eventResearched : null;
var __doctrinePrevGameInit   = (typeof eventGameInit   === "function") ? eventGameInit   : null;
var __doctrinePrevStartLevel = (typeof eventStartLevel === "function") ? eventStartLevel : null;
var __doctrinePrevChat       = (typeof eventChat       === "function") ? eventChat       : null;
var __doctrinePrevPickup     = (typeof eventPickup     === "function") ? eventPickup     : null;
var __doctrinePrevStructBuilt = (typeof eventStructureBuilt === "function") ? eventStructureBuilt : null;

/* eventDestroyed does not say who did the killing — no API does. We keep a
   last-hitter map recording when the object was last hit and how experienced
   the shooter was. Approximate under splash and simultaneous fire; that only
   skews the veterancy bonus, never whether the kill counts. Keys are prefixed
   by object type because droid and feature ids share a namespace. */
function hitKey(obj) { return obj.type + ":" + obj.id; }

eventAttacked = function (victim, attacker) {
	if (typeof __doctrinePrevAttacked === "function") { __doctrinePrevAttacked(victim, attacker); }
	if (!attacker || !victim) { return; }
	if (attacker.player === undefined || attacker.player < 0) { return; }
	lastHit[hitKey(victim)] = {
		t: gameTime,
		exp: (attacker.type === DROID) ? (attacker.experience || 0) : 0,
		killer: attacker.player
	};
};

eventDestroyed = function (obj) {
	if (typeof __doctrinePrevDestroyed === "function") { __doctrinePrevDestroyed(obj); }
	if (!obj) { return; }
	/* Scenery first: the engine fires eventAttacked for droids and structures
	   only, so a destroyed FEATURE never has a last-hitter record and every
	   feature died at the `rec === undefined` gate below. That is why no
	   house ever produced intel OR scavengers -- measured across every
	   playtest, `scenery intel` was 0 in all of them. Houses are handled
	   here, before the gate, and credited to whoever was standing over the
	   rubble. */
	if (obj.type === FEATURE) {
		tryHouseScavs(obj);
		if (!isSpecialFeature(obj)) {
			var fk = featureKiller(obj);
			if (fk !== null) { tryHouseIntel(obj, fk); }
		}
		delete lastHit[hitKey(obj)];
		return;
	}

	var key = hitKey(obj);
	var rec = lastHit[key];
	if (rec !== undefined) { delete lastHit[key]; }
	if (rec === undefined) { return; }
	if (gameTime - rec.t > STALENESS) { return; }   // wandered off and died later
	if (rec.killer === undefined) { return; }

	if (obj.type === DROID) {
		if (obj.player === rec.killer) { return; }  // own losses teach nobody
		tryDrop(obj, rec);
		tryDrum(obj, rec.killer);
	} else if (obj.type === STRUCTURE) {
		if (obj.player === rec.killer) { return; }  // no farming your own base
		tryDrum(obj, rec.killer);
	}
};

eventPickup = function (feature, droid) {
	// Our own bonus drum: the engine already granted the power. Skip the vanilla
	// handler, whose oil-drum respawn timer would otherwise treat every bonus
	// drum as a map drum and inflate the map's drum economy over a long game.
	if (feature && drums[feature.id] !== undefined) {
		delete drums[feature.id];
		clearFeature(feature);
		return;
	}
	if (typeof __doctrinePrevPickup === "function") { __doctrinePrevPickup(feature, droid); }
	if (!feature || !droid) { return; }
	if (crates[feature.id] === undefined) { return; }
	collectCrate(feature, droid.player, "recovered");
};

/* The opening machinegun is EARNED, not issued.

   It used to be handed out as a component at kickoff, which meant the 60-point
   R-Wpn-MG1Mk1 topic granted you something you already had. Now the topic is
   merely made researchable for everyone at kickoff and the weapon comes out of
   the lab like everything else -- ten seconds of research at the base rate, and
   it is the first thing every AI reaches for (see DOCTRINE_DEFENCE_FIRST).

   Note it also carries CyborgChaingun and MG1-VTOL, so researching it now opens
   MG cyborgs and MG VTOLs in the same breath rather than just the tank turret.

   The old comment warned this route once left an AI with zero combat units at
   t=180s because it built factories before a lab. That measurement was taken
   when the weapon waited on a research FACILITY with no ordering pressure; the
   engine now pursues this topic ahead of everything else, so the gap is the
   time to a first lab rather than an open-ended stall. */
function grantStarterWeapon(p) {
	enableResearch(STARTER_TOPIC, p);
	return true;
}

/* Kept as a no-op hook. Nothing is granted for free any more -- see
   STARTER_DEFENCES above -- but the sweep and the HQ event still call it, so it
   stays rather than being deleted at three call sites. */
function grantStarterDefences(p) {
	return false;
}

eventStructureBuilt = function (structure, droid) {
	if (typeof __doctrinePrevStructBuilt === "function") { __doctrinePrevStructBuilt(structure, droid); }
	if (!structure) { return; }
	if (structure.stattype === RESEARCH_LAB) {
		// A lab appearing is exactly when this becomes researchable in
		// practice; enabling again is harmless if it already was.
		enableResearch(STARTER_TOPIC, structure.player);
	} else if (structure.stattype === HQ && !isHuman(structure.player)) {
		grantStarterDefences(structure.player);   // no-op before AI_TOWER_DELAY
	}
};

eventResearched = function (research, structure, player) {
	if (typeof __doctrinePrevResearched === "function") { __doctrinePrevResearched(research, structure, player); }

	// uuscav2: scavengers inherit every completed research, from any player.
	if (SCAV_RESEARCH_PARITY && typeof scavengerPlayer !== "undefined"
			&& scavengerPlayer >= 0 && player !== scavengerPlayer) {
		hackNetOff();
		completeResearch(research.id, scavengerPlayer);
		hackNetOn();
	}
	researchedOf(player)[research.id] = true;
	if (TELEMETRY && !isHuman(player)) {
		debug("RESDONE p" + player + " t=" + Math.floor(gameTime/1000) + "s " + research.id);
	}
	checkBreadth(player);
	applyLabLimit(player);   // each research upgrade earns another lab

	// Research prices carry a 2.4x multiplier to slow the HUMAN down. Nexus's
	// budgeting predates those prices and it simply stops researching, so an AI
	// gets 37.5% of the cost back on completion — an effective 1.5x. Crate
	// (axis) topics were never multiplied and get no rebate; neither does the
	// scavenger pseudo-player, which receives topics free via parity anyway.
	if (!isHuman(player)
			&& !(typeof scavengerPlayer !== "undefined" && player === scavengerPlayer)
			&& !/^R-Wpn-.+-(Damage|Range|Reload|Accuracy)0[1-9]$/.test(research.id)) {
		var rr = getResearch(research.id, player);
		if (rr && rr.power > 0) {
			setPower(playerPower(player) + Math.floor(rr.power * 0.375), player);
		}
	}
};

eventGameInit = function () {
	// Vanilla setup FIRST — it builds bases, applies limits, starts scavengers.
	if (typeof __doctrinePrevGameInit === "function") { __doctrinePrevGameInit(); }

	// Make veterancy reachable for everyone (it also feeds the drop chance).
	// Iterate like the vanilla "bettertogether" cheat — the literal key
	// "CommandBrain01" is not a valid index into Upgrades[..].Brain.
	for (var p = 0; p < maxPlayers; p++) {
		for (var b in Upgrades[p].Brain) {
			if (Upgrades[p].Brain[b].BaseCommandLimit > 0) {
				Upgrades[p].Brain[b].RankThresholds = RANK_THRESHOLDS;
			}
		}
	}
	// After vanilla's setupStructureLimit() + applyLimitSet(), so this wins.
	for (var lp = 0; lp < maxPlayers; lp++) {
		applyLabLimit(lp);
		grantStarterWeapon(lp);     // everyone opens with the standard-issue MG
		grantStarterDefences(lp);   // AI-only crutch; no-op when the list is empty
		applyTowerLimit(lp);        // and cap how many it may plant
	}

	setTimer("doctrineCrateSweep", SWEEP_EVERY);
};

eventStartLevel = function () {
	if (typeof __doctrinePrevStartLevel === "function") { __doctrinePrevStartLevel(); }
	console("DOCTRINE active — kill, salvage, research.");
};

// ─────────────────────────────────────────────────────────── debug interface ──
//
//   doctrine                 your progress, crates on the field, counters
//   doctrine ai              what each AI player has salvaged
//   doctrine crate <Fam>     spawn a real crate next to you   (cheat mode)
//   doctrine unlock <Fam>    reveal that family's next topic  (cheat mode)
// Cheat mode = Shift+Backspace; cheatmode comes from rules/events/cheat.js.

function doctrineDump() {
	var p = selectedPlayer;
	console("DOCTRINE — drop scales with victim experience, max at " + EXP_FULL);
	console("DOCTRINE — reference " + myReference(p) + ", pity "
		+ Math.floor((pity[p] || 0) * 100) + "%, crates on field "
		+ Object.keys(crates).length);
	console("  drops " + stats.drops + " / recovered " + stats.recovered
		+ " / denied by enemy " + stats.denied + " / decayed " + stats.decayed
		+ " | scenery intel " + stats.houses + " / oil drums " + stats.drums
		+ " | house scavengers " + stats.houseScavs);
	var seen = {};
	for (var sub in SUBCLASS_TO_FAMILY) {
		var fam = SUBCLASS_TO_FAMILY[sub];
		if (seen[fam]) { continue; }
		seen[fam] = true;
		var t = currentTier(p, fam);
		if (t > TIERS) { console("  " + fam + ": COMPLETE"); continue; }
		var open = unlockedOf(p), done = researchedOf(p), rev = 0, fin = 0;
		for (var i = 0; i < AXES.length; i++) {
			var id = topicId(fam, AXES[i], t);
			if (open[id]) { rev++; }
			if (done[id]) { fin++; }
		}
		console("  " + fam + ": tier " + t + " — " + rev + " revealed, " + fin + "/4 researched");
	}
}

function doctrineDumpAI() {
	for (var p = 0; p < maxPlayers; p++) {
		if (isHuman(p)) { continue; }
		var done = researchedOf(p), n = 0;
		for (var k in done) { if (k.indexOf("R-Wpn-") === 0) { n++; } }
		var line = "  player " + p + ": " + n + " salvaged topics —";
		var seen = {};
		for (var sub in SUBCLASS_TO_FAMILY) {
			var fam = SUBCLASS_TO_FAMILY[sub];
			if (seen[fam]) { continue; }
			seen[fam] = true;
			var t = currentTier(p, fam);
			if (t > 1) { line += " " + fam + "@T" + t; }
		}
		console(line);
	}
}

function doctrineFamFromArg(arg) {
	for (var sub in SUBCLASS_TO_FAMILY) {
		var fam = SUBCLASS_TO_FAMILY[sub];
		if (fam.toLowerCase() === String(arg || "").toLowerCase()) { return fam; }
	}
	return null;
}

eventChat = function (from, to, message) {
	if (typeof __doctrinePrevChat === "function") { __doctrinePrevChat(from, to, message); }
	if (from !== selectedPlayer) { return; }
	if (message === "doctrine") { doctrineDump(); return; }
	if (message === "doctrine ai") { doctrineDumpAI(); return; }

	var parts = message.split(" ");
	if (parts[0] !== "doctrine" || parts.length < 3) { return; }
	if (typeof cheatmode === "undefined" || !cheatmode) {
		console("DOCTRINE: '" + parts[1] + "' needs cheat mode (Shift+Backspace).");
		return;
	}
	var fam = doctrineFamFromArg(parts[2]);
	if (fam === null) {
		console("DOCTRINE: unknown family. Try: MG, Cannon, Rocket, Missile, Flamer, "
			+ "Mortar, Howitzer, Laser, Rail, AA, EMP");
		return;
	}
	if (parts[1] === "unlock") {
		var topic = nextTopic(selectedPlayer, fam);
		if (topic === null) { console("DOCTRINE: nothing offerable in " + fam + "."); return; }
		grantTopic(selectedPlayer, topic, fam, "recovered");
	} else if (parts[1] === "crate") {
		var mine = enumDroid(selectedPlayer);
		if (mine.length === 0) { console("DOCTRINE: no unit to drop next to."); return; }
		spawnCrate(fam, selectedPlayer, mine[0].x + 1, mine[0].y);
	}
};
