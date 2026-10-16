#!/usr/bin/env python3
"""Repack uuscav2.wz from source and install it to %APPDATA%.

    py -X utf8 harness/repack_uuscav2.py

Run this after editing
``uuscav2/multiplay/script/scavengers/ultimateScavengers.js``. Expects the
``uuscav2`` folder to sit beside ``wz-doctrine_2``.

Only 4.7.0 gets the scavenger archive -- 4.5.5 runs DOCTRINE without it.
"""

import os
import pathlib
import subprocess
import sys
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent.parent / "uuscav2"          # harness/ -> wz-doctrine_2/ -> ..
DST = (pathlib.Path(os.environ["APPDATA"]) / "Warzone 2100 Project" / "Warzone 2100"
       / "mods" / "4.7.0" / "autoload" / "uuscav2.wz")

FILES = ["multiplay/script/mods/init.js",
         "multiplay/script/scavengers/ultimateScavengers.js"]


def main() -> None:
    if not SRC.is_dir():
        sys.exit(f"uuscav2 source not found at {SRC}\n"
                 "Keep the uuscav2 folder beside wz-doctrine_2.")
    missing = [f for f in FILES if not (SRC / f).exists()]
    if missing:
        sys.exit(f"missing source files: {missing}")

    # Syntax-gate before shipping: a broken scavenger script disables the whole
    # faction silently, and the game logs it only as a runtime exception.
    import shutil
    node = shutil.which("node") or os.environ.get("NODE_EXE")
    if node:
        for f in FILES:
            r = subprocess.run([node, "--check", str(SRC / f)],
                               capture_output=True, text=True)
            if r.returncode:
                sys.exit(f"syntax error in {f}:\n{r.stderr[:500]}")
        print("syntax OK")
    else:
        print("note: node not found, skipping the syntax check")

    DST.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(SRC / f, f)
    print(f"installed: {DST}  ({DST.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
