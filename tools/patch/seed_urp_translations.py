"""Prepare translation sources with the original URP dialogue + movie typo fixes.

The resulting JSON files contain game/patch text: keep them LOCAL in output/.
Do not upload either output as part of the public translation tool repository.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.patch.build_urp_coyle import extract_patch_files
from tools.rtx.rtx_tool import Rtx


def parse_rtx_changes(text: str, archive: Rtx) -> dict[str, str]:
    """URP row indices are file/disk order, the reverse of the RNAV index."""
    disk = sorted(archive.entries, key=lambda entry: entry.offset)
    changes = {}
    for record in text.splitlines():
        if not record.strip():
            continue
        cols = record.split("\t", 2)
        if len(cols) != 3:
            raise ValueError(f"bad upstream RTX change line: {record!r}")
        ix, tag, value = cols
        if not ix.isascii() or not ix.isdecimal():
            raise ValueError("upstream RTX index must be decimal")
        index = int(ix)
        if index >= len(disk) or disk[index].id != tag:
            raise ValueError(f"upstream RTX index/tag mismatch: {index} {tag}")
        if tag in changes:
            raise ValueError(f"duplicate RTX translation correction tag: {tag}")
        changes[tag] = value
    return changes


def parse_ini_changes(text: str) -> list[dict]:
    current_file = None
    section = None
    changed = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if line[0] != " ":
            current_file = stripped
        elif stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        else:
            if "=" not in stripped:
                raise ValueError(f"bad INI change {line!r}")
            key, value = stripped.split("=", 1)
            changed.append({"file": current_file, "section": section, "key": key.strip(), "corrected_english": value.strip(), "translation": None})
    return changed


def seed(urp: Path, original_rtx: Path, output: Path, movies_output: Path) -> dict:
    if any(p.resolve() == original_rtx.resolve() for p in (output, movies_output)):
        raise ValueError("translation output cannot replace source RTX")
    with zipfile.ZipFile(urp) as archive:
        files = extract_patch_files(archive)
    game_rtx = Rtx(original_rtx.read_bytes())
    changes = parse_rtx_changes(files["RTX Changes.txt"].decode("cp437"), game_rtx)
    source = game_rtx.manifest("cp437")
    source["patch"] = {"name": "Unofficial Redguard Patch", "changes": len(changes), "zip_sha256": hashlib.sha256(urp.read_bytes()).hexdigest()}
    for record in source["entries"]:
        if record["tag"] in changes:
            record["vanilla_original"] = record["original"]
            record["original"] = changes[record["tag"]]
            record["corrected_by_urp"] = True
    ini = {
        "format": "redguard-urp-ini-translation-source-v1",
        "source_patch_zip_sha256": source["patch"]["zip_sha256"],
        "entries": parse_ini_changes(files["INI Changes.txt"].decode("cp437")),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    movies_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
    movies_output.write_text(json.dumps(ini, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"source": str(output), "corrected_rtx": len(changes), "movie_source": str(movies_output), "ini_changes": len(ini["entries"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urp", type=Path, required=True)
    parser.add_argument("--rtx", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("output/ENGLISH.urp-source.json"))
    parser.add_argument("--movies-output", type=Path, default=Path("output/MENU.urp-source.json"))
    args = parser.parse_args()
    print(json.dumps(seed(args.urp, args.rtx, args.output, args.movies_output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
