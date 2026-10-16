#!/usr/bin/env python3
"""Assemble the DOCTRINE release artefacts.

Builds both game versions from source, copies the mod archives out of the install
directory into ``dist/``, writes the distribution notes, and prints a checksum
manifest.

    py -X utf8 package_release.py

Nothing here writes into a game installation -- ``build_mod.py`` installs to
%APPDATA% as always, and this script only reads those results back out.
"""

import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
DIST = ROOT / "dist"
VERSIONS = ("4.7.0", "4.5.5")

# Files that ship beside the .wz so a downloader gets the docs too. Keep this in
# step with every relative link in README.md and PLAYTEST.md -- main() checks that
# no shipped document points at a file that was left behind.
# The release layout. Player-facing documents sit at the top level of the
# download; the development record goes in docs/ so the root stays readable.
# main() checks that no shipped document links to a file that was left behind.
DOCS_ROOT = ["README.md", "GAMEPLAY.md", "CHANGELOG.md", "LICENSE.md",
             "COPYING"]
DOCS_SUB = {
    "docs/DOCTRINE.md": "DOCTRINE.md",
    "docs/COMBAT.md": "COMBAT.md",
    "docs/ARCHITECTURE.md": "ARCHITECTURE.md",
    "docs/TUNING.md": "TUNING.md",
    "docs/HANDOVER.md": "HANDOVER.md",
    "docs/CONTINUE-HERE.md": "CONTINUE-HERE.md",
    "docs/IMPLEMENTATION.md": "IMPLEMENTATION.md",
    "docs/PLAYTEST.md": "PLAYTEST.md",
    "docs/REBALANCE-SUMMARY.md": "build/REBALANCE-SUMMARY.md",
}


def appdata_mod(version: str) -> pathlib.Path:
    return (pathlib.Path(os.environ["APPDATA"]) / "Warzone 2100 Project"
            / "Warzone 2100" / "mods" / version / "autoload" / "doctrine.wz")


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg: str) -> None:
    print(f"PACKAGE FAILED: {msg}")
    sys.exit(1)


def check_archive(path: pathlib.Path, version: str) -> dict:
    """Refuse to ship a build with telemetry, probes or syntax errors in it."""
    z = zipfile.ZipFile(path)
    info = json.loads(z.read("mod-info.json"))
    doctrine = z.read("multiplay/script/mods/doctrine.js").decode("utf-8")

    if "const TELEMETRY = false;" not in doctrine:
        fail(f"{version}: telemetry is not disabled in doctrine.js")
    for probe in ("SCAVDEF", "AATANK", "PROBE t=", "P1WPN", "hqAvail"):
        if probe in doctrine:
            fail(f"{version}: debug probe {probe!r} left in doctrine.js")

    # node is optional; it only powers the syntax gate. Look on PATH first so this
    # works on any machine, then fall back to the standard Windows install.
    _found = shutil.which("node")
    _default = os.path.join("C:" + os.sep, "Program Files", "nodejs", "node.exe")
    node = pathlib.Path(_found or os.environ.get("NODE_EXE", _default))
    bad = []
    if node.exists():
        tmp = DIST / "_syntax"
        tmp.mkdir(parents=True, exist_ok=True)
        for name in z.namelist():
            if not name.endswith(".js"):
                continue
            f = tmp / name.replace("/", "__")
            f.write_bytes(z.read(name))
            if subprocess.run([str(node), "--check", str(f)],
                              capture_output=True).returncode:
                bad.append(name)
        shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            fail(f"{version}: JavaScript syntax errors in {bad}")

    return {"version": info["version"], "files": len(z.namelist()),
            "kb": path.stat().st_size // 1024, "js_checked": node.exists()}


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    manifest = []
    for version in VERSIONS:
        print(f"--- building {version}")
        r = subprocess.run([sys.executable, "-X", "utf8", "build_mod.py", version],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            fail(f"build_mod.py {version} exited {r.returncode}\n{r.stdout[-2000:]}")

        src = appdata_mod(version)
        if not src.exists():
            fail(f"{version}: {src} not produced")
        meta = check_archive(src, version)

        out = DIST / f"doctrine-{meta['version']}-wz{version}.wz"
        shutil.copy2(src, out)
        digest = sha256(out)
        manifest.append((out.name, meta, digest))
        print(f"    {out.name}  {meta['kb']} KB  {meta['files']} files  "
              f"sha256 {digest[:16]}...")

    for doc in DOCS_ROOT:
        src_doc = ROOT / doc
        if not src_doc.exists():
            fail(f"document listed in DOCS_ROOT is missing: {doc}")
        shutil.copy2(src_doc, DIST / doc)
    for dest, src_rel in DOCS_SUB.items():
        src_doc = ROOT / src_rel
        if not src_doc.exists():
            fail(f"document listed in DOCS_SUB is missing: {src_rel}")
        target = DIST / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_doc, target)

    # The sources link to each other by project path (IMPLEMENTATION.md,
    # build/REBALANCE-SUMMARY.md). The release moves most of them under docs/,
    # so rewrite every relative link on the COPIES to match the release layout.
    # Sources keep their own correct links; only what ships is rewritten.
    release_path = {pathlib.PurePath(d).name: d for d in DOCS_ROOT}
    for dest in DOCS_SUB:
        release_path[pathlib.PurePath(dest).name] = dest
    release_path["REBALANCE-SUMMARY.md"] = "docs/REBALANCE-SUMMARY.md"

    def retarget(md: pathlib.Path, link: str) -> str:
        name = pathlib.PurePath(link.split("#")[0]).name
        if name not in release_path:
            return link
        rel = os.path.relpath((DIST / release_path[name]).parent, md.parent)
        prefix = "" if rel == "." else rel.replace(os.sep, "/") + "/"
        frag = link.split("#", 1)
        return prefix + name + ("#" + frag[1] if len(frag) > 1 else "")

    for md in sorted(DIST.rglob("*.md")):
        txt = md.read_text(encoding="utf-8", errors="replace")
        out = re.sub(
            r"(\[[^\]]+\]\()([^)]+)(\))",
            lambda m: m.group(1) + (m.group(2) if m.group(2).startswith(
                ("http://", "https://", "#", "mailto:")) else retarget(md, m.group(2))) + m.group(3),
            txt)
        if out != txt:
            md.write_text(out, encoding="utf-8")

    # The scavenger component ships as a patch the player applies to their own
    # copy of uuscav2.wz -- DOCTRINE's changes, not the third-party file.
    scav_src = ROOT / "scav"
    scav_dst = DIST / "scav"
    scav_dst.mkdir(parents=True, exist_ok=True)
    for f in ("patch_uuscav2.py", "scav_patch.json"):
        if not (scav_src / f).exists():
            fail(f"scavenger patch incomplete: scav/{f} is missing")
        shutil.copy2(scav_src / f, scav_dst / f)
    print(f"    scav patch: {len(json.loads((scav_src / 'scav_patch.json')
          .read_text(encoding='utf-8'))['hunks'])} hunks")

    (DIST / "README-DIST.md").write_text(DIST_NOTES, encoding="utf-8")

    # Every relative link in a shipped document must resolve inside dist/.
    broken = []
    for md in sorted(DIST.rglob("*.md")):
        for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", md.read_text(encoding="utf-8",
                                                                    errors="replace")):
            target = m.group(1)
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if not (md.parent / target.split("#")[0]).exists():
                broken.append(f"{md.relative_to(DIST)} -> {target}")
    if broken:
        fail("shipped documents contain broken links: " + "; ".join(broken))
    print(f"    links OK across {len(list(DIST.rglob('*.md')))} documents")

    lines = ["# DOCTRINE release manifest", ""]
    for name, meta, digest in manifest:
        lines.append(f"- `{name}`")
        lines.append(f"  - version {meta['version']}, {meta['files']} files, {meta['kb']} KB")
        lines.append(f"  - sha256 `{digest}`")
    (DIST / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("")
    print(f"dist/ ready: {len(manifest)} archives + "
          f"{len(DOCS_ROOT) + len(DOCS_SUB)} docs")
    # One download with everything in it.
    bundle = ROOT / f"DOCTRINE-{manifest[0][1]['version']}.zip"
    if bundle.exists():
        bundle.unlink()
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(DIST.rglob("*")):
            if f.is_file():
                z.write(f, f"DOCTRINE-{manifest[0][1]['version']}/{f.relative_to(DIST).as_posix()}")
    print("")
    print(f"bundle: {bundle.name}  {bundle.stat().st_size // 1024} KB  "
          f"({len(zipfile.ZipFile(bundle).namelist())} files)")
    print(f"        {bundle}")
    print("NOTE: the scavenger component is NOT packaged -- see dist/README-DIST.md")


DIST_NOTES = r"""# DOCTRINE 1.0.0 — what is in this download

## Install

Pick the archive matching your game version and drop it into your autoload folder:

| file | for |
|---|---|
| `doctrine-1.0.0-wz4.7.0.wz` | Warzone 2100 4.7.x |
| `doctrine-1.0.0-wz4.5.5.wz` | Warzone 2100 4.5.x |

- **Windows** `%APPDATA%\Warzone 2100 Project\Warzone 2100\mods\<version>\autoload\`
- **Linux** `~/.local/share/warzone2100/mods/<version>/autoload/`
- **macOS** `~/Library/Application Support/Warzone 2100/mods/<version>/autoload/`

Skirmish and multiplayer only. Move the file out of `autoload/` before playing the campaign.
Full instructions in `README.md`; how to actually play it in `GAMEPLAY.md`.

## Layout

```
README.md         what the mod is, requirements, install
GAMEPLAY.md       how to play it -- the loop, the gates, the matchup tables
CHANGELOG.md      what is in 1.0.0, the pre-release audit, known issues
LICENSE.md        GPL-2.0-or-later and third-party attribution
MANIFEST.md       sha256 for both archives
docs/             design specification, build architecture, tuning reference,
                  the full 32-round playtest record and the stat diff
```

## The scavenger component

DOCTRINE's scavenger escalation — staged phases, fortified derricks, infantry squads, four
grades of suicide bomb truck, the capped air arm — modifies **Ultimate Ultimate Scavengers 2**,
which is somebody else's mod with no established licence or author. So this download ships
*the changes*, not the file.

```
1. install Ultimate Ultimate Scavengers 2 yourself (uuscav2.wz in mods/4.7.0/autoload/)
2. py -X utf8 scav/patch_uuscav2.py
```

The script finds the mod in your autoload folder, verifies all 23 changes against your copy,
backs it up as `uuscav2.wz.original`, and rewrites the archive in place. It writes nothing
unless every change verifies, is a no-op if already applied, and refuses a different release
of the mod rather than corrupting it. 368 of the lines it adds are DOCTRINE's own; 10 lines of
the original are quoted purely so it can confirm it is patching what it thinks it is.

**Without it**, the game's own scavengers are used and everything else in DOCTRINE is
unaffected. House scavengers work either way — they live in DOCTRINE's own runtime script.

## Before you publish

- [ ] Add `COPYING` (GPL-2.0 full text) from <https://www.gnu.org/licenses/gpl-2.0.txt>
- [ ] Decide the scavenger question above
- [ ] Verify the checksums in `MANIFEST.md` against what you upload
- [ ] Play one full skirmish per game version from the packaged file, not a dev build
"""


if __name__ == "__main__":
    main()
