"""Redguard texture localization preparation, without modifying game assets.

This tool inventories proprietary assets locally, delegates read-only extraction
to rgpre, and builds thumbnail contact sheets for visual translation review.
No original assets or converted images belong in the public repository.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess


ASSET_FIELDS = ("path", "kind", "size", "candidate_for_text", "notes")
TEXBANK = re.compile(r"^TEXBSI\.\d+$", re.IGNORECASE)
SOFTWARE_TEXTURE = re.compile(r"^TEXTURE\.\d+$", re.IGNORECASE)
IMAGE_EXTENSIONS = {".png", ".bmp", ".gif", ".jpg", ".jpeg", ".pcx", ".tga"}
MODEL_EXTENSIONS = {".3d", ".3dc", ".rob", ".wld"}


def classify(filename: str) -> tuple[str, str, str] | None:
    """Return (asset class, candidate label, explanation)."""
    name = filename.upper()
    suffix = Path(filename).suffix.lower()
    if TEXBANK.fullmatch(name):
        return "texbsi", "review", "3D texture bank; inspect extracted frames for lettering"
    if SOFTWARE_TEXTURE.fullmatch(name):
        return "texture_software", "review", "Steam software renderer texture; converter compatibility not yet established"
    if suffix == ".gxa":
        return "gxa", "review", "bitmap/animation archive; inspect UI or titles"
    if suffix in {".lbm", ".pcx", ".anm"}:
        return suffix[1:], "review", "screen bitmap/animation; extract with rgpre"
    if suffix == ".col":
        return "palette", "reference", "palette for texture export; not text content"
    if suffix == ".fnt":
        return "font", "separate", "glyph/font work uses tools/fnt"
    if suffix in IMAGE_EXTENSIONS:
        return "image", "review", "standalone image; inspect visual contents"
    if suffix in MODEL_EXTENSIONS:
        return "model", "reference", "3D model/scene; inspect surfaces via rgpre"
    return None


def inventory(root: Path) -> list[dict]:
    if not root.is_dir():
        raise ValueError(f"Asset directory not found: {root}")
    records = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part.lower() in {".git", "output", "__pycache__"} for part in path.relative_to(root).parts[:-1]):
            continue
        result = classify(path.name)
        if result is None:
            continue
        kind, candidate, notes = result
        records.append({
            "path": path.relative_to(root).as_posix(),
            "kind": kind,
            "size": path.stat().st_size,
            "candidate_for_text": candidate,
            "notes": notes,
        })
    return sorted(records, key=lambda row: (row["kind"], row["path"].casefold()))


def write_inventory(root: Path, destination: Path) -> list[dict]:
    rows = inventory(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ASSET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def extract(root: Path, output: Path, rgpre: str, palette: Path | None, limit: int | None, only: str | None = None) -> dict:
    """Export supported formats; never rewrite the source assets."""
    rows = [row for row in inventory(root) if row["kind"] in {"texbsi", "gxa", "pcx", "lbm", "anm"}]
    if only:
        pattern = re.compile(only, re.IGNORECASE)
        rows = [row for row in rows if pattern.search(row["path"])]
    if limit is not None:
        rows = rows[:limit]
    executable = shutil.which(rgpre)
    if executable is None:
        raise ValueError(f"rgpre executable not found: {rgpre}")
    if palette is not None and not palette.is_file():
        raise ValueError(f"Palette not found: {palette}")
    if output.resolve() == root.resolve() or root.resolve() in output.resolve().parents:
        raise ValueError("Extraction output must be outside the asset source directory")
    results = []
    for item in rows:
        source = root / item["path"]
        stem = item["path"].replace("/", "__")
        is_image = item["kind"] in {"pcx", "lbm"}
        dest = output / (stem + ".png" if is_image else stem)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not is_image:
            dest.mkdir(parents=True, exist_ok=True)
        args = [executable, "convert", item["kind"], str(source), "-o", str(dest)]
        if palette is not None and item["kind"] == "texbsi":
            args.extend(["--palette", str(palette)])
        try:
            done = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
            status = "ok" if done.returncode == 0 else "failed"
            message = (done.stderr or done.stdout)[-1200:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            status, message = "failed", str(exc)
        results.append({"source": item["path"], "output": dest.name, "status": status, "message": message})
    output.mkdir(parents=True, exist_ok=True)
    (output / "export_report.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"total": len(results), "success": sum(r["status"] == "ok" for r in results)}


def sheets(source: Path, dest: Path, per_sheet: int = 72, columns: int = 6) -> int:
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError as exc:
        raise ValueError("Install Pillow first: python -m pip install pillow") from exc
    if not source.is_dir():
        raise ValueError(f"Export directory not found: {source}")
    candidates = sorted((p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in {".png", ".gif", ".jpg", ".bmp"}), key=lambda p: str(p).casefold())
    dest.mkdir(parents=True, exist_ok=True)
    tile_w, tile_h, image_w, image_h = 190, 180, 174, 145
    index = []
    for start in range(0, len(candidates), per_sheet):
        batch = candidates[start:start + per_sheet]
        page = start // per_sheet + 1
        canvas = Image.new("RGB", (columns * tile_w, ((len(batch) + columns - 1) // columns) * tile_h), "#eaeaea")
        draw = ImageDraw.Draw(canvas)
        for pos, path in enumerate(batch):
            number = start + pos + 1
            x, y = (pos % columns) * tile_w, (pos // columns) * tile_h
            try:
                with Image.open(path) as original:
                    frame = original.convert("RGBA")
                    frame.thumbnail((image_w, image_h))
                    background = Image.new("RGBA", (image_w, image_h), "#777777")
                    background.alpha_composite(frame, ((image_w-frame.width)//2, (image_h-frame.height)//2))
                    canvas.paste(background.convert("RGB"), (x+8, y+4))
                state = "ok"
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                state = f"error: {str(exc)[:80]}"
                draw.rectangle((x+8, y+4, x+182, y+149), outline="#cc0000", width=2)
            draw.text((x+8, y+152), f"{number:04d} {path.name[:17]}", fill="#111111")
            index.append({"number": number, "sheet": page, "source": path.relative_to(source).as_posix(), "status": state, "translation_needed": "", "comment": ""})
        canvas.save(dest / f"texture_sheet_{page:03d}.png")
    with (dest / "texture_review.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("number", "sheet", "source", "status", "translation_needed", "comment"))
        writer.writeheader()
        writer.writerows(index)
    return len(candidates)


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="action", required=True)
    scan = sub.add_parser("scan", help="Inventory graphic candidates in a directory")
    scan.add_argument("root", type=Path)
    scan.add_argument("--csv", type=Path, default=Path("output/texture_inventory.csv"))
    export = sub.add_parser("extract", help="Export candidates using externally installed rgpre")
    export.add_argument("root", type=Path)
    export.add_argument("--output", type=Path, default=Path("output/texture_exports"))
    export.add_argument("--rgpre", default="rgpre")
    export.add_argument("--palette", type=Path)
    export.add_argument("--limit", type=int)
    export.add_argument("--only", help="optional regex to select source filenames (e.g. gui|MENU|MAP)")
    review = sub.add_parser("sheets", help="Build visual review contact sheets from exported images")
    review.add_argument("root", type=Path)
    review.add_argument("--output", type=Path, default=Path("output/texture_review"))
    review.add_argument("--per-sheet", type=int, default=72)
    args = cli.parse_args()
    try:
        if args.action == "scan":
            rows = write_inventory(args.root, args.csv)
            print(f"Scanned {len(rows)} graphic candidates -> {args.csv}")
        elif args.action == "extract":
            if args.limit is not None and args.limit < 0:
                raise ValueError("--limit cannot be negative")
            print(json.dumps(extract(args.root, args.output, args.rgpre, args.palette, args.limit, args.only)))
        else:
            if args.per_sheet <= 0:
                raise ValueError("--per-sheet must be positive")
            print(f"Indexed {sheets(args.root, args.output, args.per_sheet)} preview images -> {args.output}")
    except ValueError as exc:
        cli.error(str(exc))


if __name__ == "__main__":
    main()
