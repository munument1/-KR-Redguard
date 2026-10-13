"""Build a LOCAL Redguard Mod Manager add-on from your legally obtained URP ZIP.

No upstream Unofficial Redguard Patch data is committed to our repository.
The output is intended for the owner's private use; do not redistribute it
without upstream permission. Original installed game files stay untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile


ORIGINAL = "  if after_iszara = 0 and CyrusFriend = 0 and HayleStory = 1"
REPLACEMENT = "  if CyrusFriend = 0 and HayleStory = 1"
MAP_NAME = "ISLAND"
LINE = 1520
UPSTREAM_FILES = ("About.txt", "INI Changes.txt", "Map Changes.txt", "RTX Changes.txt")
LOCAL_MOD_NAME = "Unofficial Redguard Patch + Coyle Fix (Local)"


def parse_changes(text: str) -> dict[str, list[tuple[int, str]]]:
    """Validate mod-manager change format, keeping per-map source line numbers."""
    changes: dict[str, list[tuple[int, str]]] = {}
    current = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line[0] != " ":
            current = line.strip()
            if current in changes:
                raise ValueError(f"duplicate map section: {current}")
            changes[current] = []
            continue
        if current is None:
            raise ValueError("map change before a map header")
        found = re.fullmatch(r"\s*(\d+)\t(.*)", line)
        if not found:
            raise ValueError(f"unsupported map change: {line!r}")
        changes[current].append((int(found[1]), found[2]))
    return changes


def inject_coyle(source: bytes) -> bytes:
    text = source.decode("cp437")
    changes = parse_changes(text)
    if MAP_NAME not in changes:
        raise ValueError("source URP has no ISLAND map section")
    if any(pos == LINE for pos, _ in changes[MAP_NAME]):
        raise ValueError("source URP already edits the Coyle line; inspect manually")

    # Mod Manager resolves line numbers against the ORIGINAL decompiled RGM
    # and treats a 'null' line followed by new text as a replacement.
    changes[MAP_NAME].extend([(LINE, "null"), (LINE, REPLACEMENT)])
    if sum(1 for p, _ in changes[MAP_NAME] if p == LINE) != 2:
        raise ValueError("Coyle replacement not uniquely mapped")
    output = []
    for map_name, entries in changes.items():
        output.append(map_name)
        for pos, value in entries:
            output.append(f"  {pos}\t{value}")
        output.append("")
    rebuilt = ("\n".join(output) + "\n").encode("cp437")
    reparsed = parse_changes(rebuilt.decode("cp437"))
    assert reparsed[MAP_NAME][-2:] == [(LINE, "null"), (LINE, REPLACEMENT)]
    return rebuilt


def check_game_script(game: Path, jar: Path, inspector: Path) -> None:
    if not jar.is_file() or not inspector.is_file():
        raise ValueError("Redguard Mod Manager.jar and RgmInspector.java are required")
    command = ["java", "-cp", str(jar), str(inspector), str(game), "menuAddItem(\"?hay\"", "ISLAND"]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    hits = [s for s in completed.stdout.splitlines() if s.startswith(f"ISLAND\t{LINE}\t")]
    if hits != [f"ISLAND\t{LINE}\t{ORIGINAL}"]:
        raise ValueError(f"game map differs: expected guard at ISLAND:{LINE}, got {hits!r}")
    if 'ISLAND\t1522\t    menuAddItem("?hay", var35, 7)' not in completed.stdout:
        raise ValueError("Coyle HAYLE dialogue entry not found in expected location")


def extract_patch_files(archive: zipfile.ZipFile) -> dict[str, bytes]:
    all_files: dict[str, bytes] = {}
    for part in archive.infolist():
        if part.is_dir():
            continue
        if part.file_size > 2000000:
            raise ValueError("unexpected large ZIP member")
        basename = Path(part.filename.replace("\\", "/")).name
        if basename not in UPSTREAM_FILES or basename in all_files:
            raise ValueError(f"unexpected/duplicate URP file {part.filename!r}")
        all_files[basename] = archive.read(part)
    if set(all_files) != set(UPSTREAM_FILES):
        raise ValueError(f"source ZIP missing required files: {set(UPSTREAM_FILES) - set(all_files)}")
    return all_files


def build(source: Path, output: Path, game: Path, jar: Path, inspector: Path) -> dict:
    if source.resolve() == output.resolve():
        raise ValueError("source and output paths must differ")
    check_game_script(game, jar, inspector)
    with zipfile.ZipFile(source, "r") as archive:
        files = extract_patch_files(archive)

    modified = dict(files)
    modified["Map Changes.txt"] = inject_coyle(files["Map Changes.txt"])
    # Preserve original typos, script and RTX corrections verbatim in private
    # builds. The game backup becomes the source for Mod Manager's application.
    about = files["About.txt"].decode("cp437").splitlines()
    original_version = about[0] if about else "unknown"
    modified["About.txt"] = (
        f"1.03 + Coyle-local-1\n"
        f"Dillonn241 (original URP); local Coyle correction\n"
        f"Original Unofficial Redguard Patch 1.03, plus a fix for Coyle's HAYLE topic after rescuing Iszara.\n"
        f"Private local combination. Original About.txt reported version {original_version}.\n"
    ).encode("cp437")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as destination:
        for name in UPSTREAM_FILES:
            destination.writestr(f"{LOCAL_MOD_NAME}/{name}", modified[name])
    with zipfile.ZipFile(output) as verify:
        produced = extract_patch_files(verify)
        if produced != modified:
            raise ValueError("ZIP roundtrip failed")

    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    return {
        "source_patch": source.name,
        "source_sha256": source_hash,
        "original_about_version": original_version,
        "output": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "upstream_files_retained": ["INI Changes.txt", "RTX Changes.txt"],
        "coyle_condition": {"map": MAP_NAME, "original_line": LINE, "before": ORIGINAL.strip(), "after": REPLACEMENT.strip()},
        "redistribution": "personal use only; request author's permission to redistribute a merged mod",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True, help="original user-downloaded URP ZIP")
    ap.add_argument("--game", type=Path, required=True, help="unmodified Redguard game directory")
    ap.add_argument("--jar", type=Path, default=Path("Redguard Mod Manager.jar"))
    ap.add_argument("--output", type=Path, default=Path("output/Unofficial Redguard Patch + Coyle Fix (Local).zip"))
    args = ap.parse_args()
    try:
        result = build(args.source, args.output, args.game, args.jar.resolve(), Path(__file__).resolve().parents[1] / "script" / "RgmInspector.java")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        ap.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
