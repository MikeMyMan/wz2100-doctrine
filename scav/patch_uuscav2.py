#!/usr/bin/env python3
"""Apply DOCTRINE's scavenger changes to your own copy of uuscav2.wz.

    py -X utf8 patch_uuscav2.py [path\\to\\uuscav2.wz]

With no argument it looks for uuscav2.wz in your Warzone 2100 4.7.0 autoload
folder. The original is backed up as ``uuscav2.wz.original`` beside it, then the
archive is rewritten in place, so the game picks the patched version up with no
load-order guesswork.

Why a patch and not a ready-made file
-------------------------------------
"Ultimate Ultimate Scavengers 2" is somebody else's mod and its licence and
author are not established, so DOCTRINE does not redistribute it. This script
carries DOCTRINE's own additions (368 lines) plus 10 lines of the original,
quoted only so it can verify it is patching what it thinks it is -- 3% of the
file. You supply the mod; this supplies the changes.

What it changes
---------------
Staged escalation by phase, production ceilings, picketing their own derricks
factories and generators, infantry squads of three, four grades of suicide bomb
truck, a 25% cap on the air arm, range-banded multi-turret vehicles, the NEXUS
capture tank held back to 20 minutes, and two crash guards in stock pathing
code. GAMEPLAY.md section 7 describes what that means in play.

It is safe to re-run: an already-patched archive is detected and left alone, and
nothing is written unless every one of the 23 changes verifies first.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import zipfile

SCRIPT = "multiplay/script/scavengers/ultimateScavengers.js"
HERE = pathlib.Path(__file__).resolve().parent
PATCH = HERE / "scav_patch.json"
MARKER = "SCAV_PICKETS"        # a DOCTRINE constant; absent from the original


def fail(msg: str) -> None:
    print(f"\nFAILED: {msg}")
    sys.exit(1)


def default_target() -> pathlib.Path:
    cands = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        cands.append(pathlib.Path(appdata) / "Warzone 2100 Project" / "Warzone 2100")
    home = os.environ.get("HOME") or os.path.expanduser("~")
    cands.append(pathlib.Path(home) / ".local" / "share" / "warzone2100")
    cands.append(pathlib.Path(home) / "Library" / "Application Support" / "Warzone 2100")
    for base in cands:
        p = base / "mods" / "4.7.0" / "autoload" / "uuscav2.wz"
        if p.exists():
            return p
    fail("could not find uuscav2.wz in an autoload folder.\n"
         "        Install the scavenger mod first, or pass its path:\n"
         "          py -X utf8 patch_uuscav2.py D:\\path\\to\\uuscav2.wz")


def main() -> None:
    target = (pathlib.Path(sys.argv[1]).expanduser() if len(sys.argv) > 1
              else default_target())
    if not target.exists():
        fail(f"no such file: {target}")
    if not PATCH.exists():
        fail(f"patch data missing: {PATCH.name} must sit beside this script")

    data = json.loads(PATCH.read_text(encoding="utf-8"))
    hunks, baseline = data["hunks"], data["baseline_lines"]

    with zipfile.ZipFile(target) as z:
        names = z.namelist()
        if SCRIPT not in names:
            fail(f"{target.name} does not contain {SCRIPT}.\n"
                 "        Is this really uuscav2.wz?")
        contents = {n: z.read(n) for n in names}

    raw = contents[SCRIPT].decode("utf-8")
    crlf = "\r\n" in raw
    lines = raw.replace("\r\n", "\n").split("\n")

    if MARKER in raw:
        print(f"{target.name} is already DOCTRINE-patched — nothing to do.")
        print("To re-apply from scratch, restore uuscav2.wz.original over it first.")
        return

    if len(lines) != baseline:
        fail(f"your copy has {len(lines)} lines; this patch was built against "
             f"{baseline}.\n"
             "        It is a different release of the scavenger mod, so the patch\n"
             "        cannot be applied safely. Nothing has been changed.")

    # Verify every hunk BEFORE touching anything, so a mismatch cannot leave a
    # half-patched archive behind.
    for i, h in enumerate(hunks, start=1):
        at, remove = h["at"], h["remove"]
        if lines[at:at + len(remove)] != remove:
            fail(f"change {i} of {len(hunks)} does not match at line {at + 1}.\n"
                 f"        expected: {(remove[0][:60] if remove else '(insertion)')!r}\n"
                 f"        found:    {(lines[at][:60] if at < len(lines) else '(end of file)')!r}\n"
                 "        Your uuscav2.wz differs from the one DOCTRINE was built\n"
                 "        against. Nothing has been changed.")

    # Splice from the end so earlier indices stay valid.
    out = list(lines)
    for h in sorted(hunks, key=lambda x: x["at"], reverse=True):
        out[h["at"]:h["at"] + len(h["remove"])] = h["insert"]
    text = "\n".join(out)
    print(f"all {len(hunks)} changes verified and applied "
          f"({len(lines)} -> {len(out)} lines)")

    # Syntax-gate before writing: a broken scavenger script disables the whole
    # faction, and the game reports it only as a runtime exception mid-match.
    node = shutil.which("node") or os.environ.get("NODE_EXE")
    if node and pathlib.Path(node).exists():
        tmp = HERE / "_syntax_check.js"
        tmp.write_text(text, encoding="utf-8")
        r = subprocess.run([str(node), "--check", str(tmp)],
                           capture_output=True, text=True)
        tmp.unlink(missing_ok=True)
        if r.returncode:
            fail("the patched script does not parse, so it was NOT written:\n"
                 + r.stderr[:600])
        print("syntax OK")
    else:
        print("note: node not found, skipping the syntax check")

    backup = target.with_suffix(target.suffix + ".original")
    if backup.exists():
        print(f"backup already present, keeping it: {backup.name}")
    else:
        shutil.copy2(target, backup)
        print(f"backed up  {backup.name}")

    contents[SCRIPT] = (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for n, payload in contents.items():
            z.writestr(n, payload)

    print(f"patched    {target}")
    print("\nStart a skirmish with scavengers set to Ultimate.")
    print("To undo, rename uuscav2.wz.original back over uuscav2.wz.")


if __name__ == "__main__":
    main()
