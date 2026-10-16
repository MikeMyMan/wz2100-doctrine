# DOCTRINE — handover

Everything needed to take this project over. Written 2026-09-05 at version **1.0.0**.

**Start here, then read `CONTINUE-HERE.md`.** That one is operational — install, build, test.
This one is the map: what exists, what state it is in, what is left, and what to be careful of.

---

## 1. What this is

A total conversion for Warzone 2100 that replaces the research queue with a salvage loop:
kills drop intel crates you must physically drive over to collect. Roughly three weeks of
work, 32 documented playtest rounds, shipped as one ~150 KB `.wz` per game version.

**Status: audited and ready to publish.** Both game versions build clean *and have both now been played* — the 4.5.5 engine was
finally exercised in the 2026-10-16 pre-release audit, having previously been built but never run. All seven bundled AIs run
the mod's research engine, and `dist/` holds a verified 1.0.0 release. It has not been
published yet — two items block that (§4), neither of them a code defect.

## 2. The documents

| file | what it answers | trust |
|---|---|---|
| **`CONTINUE-HERE.md`** | How do I build, test and resume work? | current |
| **`ARCHITECTURE.md`** | How is it built? Why is it built that way? | current |
| **`TUNING.md`** | Where do I change a number? | current |
| **`README.md`** | *(player-facing)* what is this mod and how do I install it? | current |
| **`CHANGELOG.md`** | What is in 1.0.0, and what is known-broken? | current |
| **`PLAYTEST.md`** | Why is this value what it is? | current, 120 KB |
| **`DOCTRINE.md`** | What was the design intent? | Aug 15, design-stable |
| **`COMBAT.md`** | The combat rebalance and unlock ratchet | Aug 15, design-stable |
| **`IMPLEMENTATION.md`** | Kill accounting, engine API, traps | **Aug 16 — partly stale** |
| **`LICENSE.md`** | Licensing and third-party material | current |
| **`dist/README-DIST.md`** | What ships, what does not, and why | current |

`IMPLEMENTATION.md` is accurate on the kill-accounting algorithm, the verified engine API and
the two hard traps, but predates the AI patch system, the release pipeline and everything
after mid-August. It carries a banner saying so. `ARCHITECTURE.md` supersedes it where they
overlap.

**`PLAYTEST.md` is the most valuable document here.** It is a chronological record of 32
rounds, each with the measurement that motivated a change and the result afterwards —
including the times a fix was wrong and had to be corrected. If you are wondering why a number
is what it is, search it there before changing it.

## 3. How the work has been done

Worth continuing, because it caught real bugs repeatedly:

1. **Measure before changing.** Nearly every balance decision in `PLAYTEST.md` starts with a
   number pulled from a real game or the shipped stats, not an impression.
2. **Verify from the shipped archive**, never the source tree. Several bugs existed only in
   what was packaged — a patch that silently failed to apply, a probe left in.
3. **Read completed output, not mid-run samples.** Sampling a running game produced several
   wrong conclusions early on.
4. **Check the harness before believing a result.** Two rounds of conclusions were once drawn
   from games where no AI had actually loaded. `harness/analyse.py` now flags this explicitly.
5. **Force a gate open to test the branch behind it.** A feature gated on enemy aircraft is
   otherwise untestable — that technique found a ~7,000-exceptions-per-game bug hours before
   it would have shipped.

## 4. Blocking publication

1. **The scavenger licensing question.** DOCTRINE's scavenger behaviour derives from the
   third-party mod *Ultimate Ultimate Scavengers 2*, which shares only ~1.4% of its content
   with the game's own `ultimateScavengers.js` — so it is genuine third-party work, not a
   tweak of a GPL game file, and DOCTRINE's version is ~64% derived from it. Its author and
   licence are unknown. Four ways forward are in `dist/README-DIST.md`. **The mod as packaged
   plays correctly without it** on the game's stock scavenger settings; only the DOCTRINE
   scavenger escalation is absent.
2. **`COPYING` is missing.** GPL-2.0 requires the full licence text alongside the
   distribution. One download: <https://www.gnu.org/licenses/gpl-2.0.txt>

## 5. Backlog, in the order I would take it

> The 2026-10-16 audit closed four items (4.5.5 never played, an unbounded `lastHit` map, an over-claimed `minVersionSupported`, and an unguarded debug call) and confirmed save/reload persistence against a real savegame. See the CHANGELOG's pre-release audit section. Nothing below is a blocker.

| # | item | size | notes |
|---|---|---|---|
| 1 | Confirm Cobra's anti-air | small | It lists AA turrets natively and needs no patch, but its own detection never tripped in testing because no test game produced real aircraft. Force the gate as in round 32. |
| 2 | Cannon (`ALL ROUNDER`) balance | medium | Mediocre on both counter tables with no matchup it clearly wins. Natural niche: HARD structures — it is the direct-fire answer to walls and hardpoints. Diagnosed, never actioned. |
| 3 | AI free-upgrade rate | small | `doctrineFreeIntel()` gives Hard/Insane AI ~34/68 free weapon upgrades per long game. Biggest single lever on AI strength; AI-only, so it does not touch the player curve. A lifetime cap plus a slower timer is the smallest effective change. |
| 4 | Squad tactics | large | Smaller raid squads targeting oil, consolidation for base assaults, a home QRF. Investigated long ago; no plan written, no code. |
| 5 | Turtle robustness | medium | Fragile when it starts beside a strong enemy. Now at `defensiveness: 90` (was 100, which built only defences and VTOLs, never a tank). |
| 6 | `JSValueToInt32` asserts | small | A handful in long NullBot games, only in the final minutes as the scavenger faction dies. Non-fatal, no stack printed, cause unidentified. |

## 6. Risk register

| risk | why it matters | mitigation in place |
|---|---|---|
| **A game update breaks an AI patch** | Every AI patch is a string match against an upstream file. A reworded line breaks it. | The build `fail()`s loudly on a missing anchor rather than shipping an unpatched AI. Re-run both builds after any game update. |
| **Shipping a telemetry or probe build** | Happened twice in development. | `package_release.py` refuses to package either, and syntax-checks every script. |
| **Trusting a broken playtest** | Cost two rounds of wrong conclusions. | `harness/analyse.py` reports `aiLoadFail` prominently; `CONTINUE-HERE.md` §5 lists the nine rules. |
| **Testing on the wrong map** | `4c-rush` has zero buildings, which hid two dead features for weeks. | Documented in three places. Use `Thales` for anything involving scenery. |
| **Calling a helper an AI does not have** | ~7,000 exceptions per game, and the game keeps running. | Documented in `ARCHITECTURE.md` §2.3. Check which helpers exist in the file you patch. |
| **Save compatibility** | Saves made with DOCTRINE need DOCTRINE to load. | Stated in `README.md`. Crates, collected topics and pity state all survive save/reload. |

## 7. If you change one thing, know this

- **Armour is subtracted after the weapon-effect modifier.** A low-damage weapon sits on its
  damage floor, so a modest damage change can swing effectiveness several-fold. Recompute from
  the shipped stats; do not estimate.
- **Empty `requiredResearch` means hidden, not free.** That is how crate-gating works.
- **`apply_elevation` must remain the last stat pass.**
- **Never edit anything inside a game installation.** Everything installs to `%APPDATA%`.
