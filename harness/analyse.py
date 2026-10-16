#!/usr/bin/env python3
"""Summarise the headless games left in %TEMP%\\wzbattery by run_battery.ps1.

    py -X utf8 harness/analyse.py [name ...]

With no arguments it reports on every run it finds. For each game it prints the
length, script errors, AI load failures, the DOCTRINE identity lines, the final
census, the scoreboard and any scavenger-defence telemetry.

Read this before trusting any playtest result: a game where `aiLoadFail` is
non-zero, or where no `DOCTRINE-AI` line appears for a player, did not run the
matchup you thought it did.
"""

import collections
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(os.environ["TEMP"]) / "wzbattery"


def text(name: str) -> str:
    out = ""
    for ext in (".out.txt", ".err.txt"):          # debug() lands in .err
        p = ROOT / (name + ext)
        if p.exists():
            out += p.read_text(encoding="utf-8", errors="replace")
    return out


def main() -> None:
    if not ROOT.exists():
        print(f"no results directory: {ROOT}")
        return
    names = sys.argv[1:] or sorted({p.name.split(".")[0] for p in ROOT.glob("*.txt")})

    for name in names:
        t = text(name)
        if not t:
            print(f"\n##### {name}: NO LOG")
            continue

        ts = [int(x) for x in re.findall(r"CENSUS t=(\d+)s", t)]
        errs = re.findall(r".*(uncaught|is not defined|TypeError|ReferenceError).*", t, re.I)
        aifail = len(re.findall(r"Failed to load AI", t))
        cannot = collections.Counter(re.findall(r"Cannot build ([^\n]*?) for player", t))
        asserts = collections.Counter(
            m.strip()[:80] for m in re.findall(r"Assert in Warzone: [^(]*\(([^\n]*)", t))
        ais = sorted(set(re.findall(r"DOCTRINE-AI p\d+ ai=\w+ pers=\S+ family=\w+", t)))

        print(f"\n##### {name}: len={max(ts) if ts else 0}s ended={'Game ended' in t} "
              f"scriptErr={len(errs)} aiLoadFail={aifail} "
              f"cannotBuild={sum(cannot.values())} asserts={sum(asserts.values())}")
        if aifail:
            print("   !! AI SCRIPTS FAILED TO LOAD -- results are meaningless, "
                  "check the `ai` field in the test config")
        for a in ais:
            print("   ", a)
        for e in errs[:4]:
            print("   SCRIPT-ERR:", e.strip()[:150])
        for k, v in cannot.most_common(4):
            print(f"   cannot-build x{v}: {k}")
        for k, v in asserts.most_common(3):
            print(f"   assert x{v}: {k}")

        census = [l for l in t.splitlines() if "CENSUS t=" in l]
        if census:
            for seg in census[-1].split(" | ")[:9]:
                print("   ", seg.strip()[:140])

        seen = set()
        for l in re.findall(r"^ *\d \| .*$", t, re.M)[-8:]:
            if l not in seen:
                seen.add(l)
                print("   SB", l.strip()[:110])

        sd = re.findall(r"SCAVDEF t=(\d+)s \[([^\]]*)\]", t)
        if sd:
            peak = collections.Counter()
            for _, body in sd:
                for item in body.split(" | "):
                    m = re.match(r"(.*)x(\d+)$", item.strip())
                    if m:
                        peak[m.group(1)] = max(peak[m.group(1)], int(m.group(2)))
            alive = [int(a) for a, b in sd if b.strip()]
            print(f"   scav defences alive until {max(alive) if alive else 0}s; "
                  f"peak {dict(peak)}")


if __name__ == "__main__":
    main()
