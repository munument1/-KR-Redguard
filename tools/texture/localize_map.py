"""Make a reviewable Korean draft of the Redguard parchment map.

The inputs are local, user-owned extracted game artwork and the user-supplied
font. They are deliberately not distributed with this script.

Run from the project root::

    python tools/texture/localize_map.py

The original extraction and installed game are never modified. Repacking into
MAPMAP.GXA is not implemented here.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree


PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / "output/texture_exports/system__MAPMAP.GXA/MAPMAP_gxa/frame_000.png"
FONT = PROJECT / "솔뫼 김대건 Medium.ttf"
DEST = PROJECT / "output/texture_ko"


@dataclass(frozen=True)
class Label:
    key: str
    english: str
    korean: str
    # Polygon tightly encompassing only the existing English letters.
    polygon: tuple[tuple[int, int], ...]
    center: tuple[int, int]
    size: int
    angle: float = 0
    tracking: float = 0
    approved: bool = False


# Coordinates are measured on the original 640x480 MAPMAP GXA frame.
# Every name except Hunding Bay is provisional pending a terminology pass.
LABELS = (
    Label("ngasta", "Isle of N'Gasta", "은가스타 섬", ((45, 47), (145, 35), (148, 59), (48, 70)), (97, 52), 14, 9),
    Label("spine", "THE SPINE", "척추 열도", ((150, 209), (173, 225), (269, 127), (252, 112)), (216, 167), 21, 43, 1.5),
    Label("devils_den", "Devil's Den", "악마의 소굴", ((344, 95), (410, 94), (410, 113), (344, 114)), (378, 104), 11),
    Label("ogres_tooth", "Ogres Tooth Mts", "오거의 송곳니 산맥", ((214, 207), (313, 205), (316, 227), (212, 231)), (264, 218), 10),
    Label("hunding", "Hunding Bay", "훈딩 만", ((377, 272), (479, 272), (479, 298), (377, 298)), (429, 285), 20, 0, 2, True),
    Label("saintsport", "Saintsport", "세인츠포트", ((450, 386), (516, 386), (516, 408), (450, 408)), (486, 400), 11),
    Label("becean_upper", "B E C E A N", "베 시 언", ((2, 259), (188, 272), (186, 312), (2, 294)), (94, 285), 23, -7, 7),
    Label("becean_lower", "S E A", "해", ((10, 324), (101, 324), (104, 358), (10, 361)), (50, 340), 25, -5),
    Label("title", "STROS M'KAI", "스트로스 므카이", ((479, 320), (639, 320), (639, 356), (479, 356)), (558, 339), 23),
    Label("title_sub", "KINGDOM OF HAMMERFELL", "해머펠 왕국", ((481, 356), (639, 356), (639, 387), (481, 387)), (554, 371), 18),
)


def make_grid(original: Image.Image) -> Image.Image:
    canvas = original.convert("RGBA").copy()
    pen = ImageDraw.Draw(canvas, "RGBA")
    font = ImageFont.truetype("arial.ttf", 12)
    for x in range(0, canvas.width, 40):
        pen.line(((x, 0), (x, canvas.height)), fill=(0, 70, 240, 100), width=1)
        pen.text((x + 2, 2), str(x), font=font, fill=(0, 30, 180, 235))
    for y in range(0, canvas.height, 40):
        pen.line(((0, y), (canvas.width, y)), fill=(0, 70, 240, 100), width=1)
        pen.text((2, y + 2), str(y), font=font, fill=(0, 30, 180, 235))
    for entry in LABELS:
        pen.line((*entry.polygon, entry.polygon[0]), fill=(180, 30, 25, 220), width=1, joint="curve")
    return canvas


def make_erase_mask(original: np.ndarray) -> np.ndarray:
    # Text ink is much darker than parchment. Inpaint only colored ink inside
    # small hand-drawn text polygons, not entire rectangles of map geography.
    height, width = original.shape[:2]
    roi = np.zeros((height, width), dtype=np.uint8)
    for entry in LABELS:
        cv2.fillPoly(roi, [np.array(entry.polygon, dtype=np.int32)], color=255)
    ink = (original[:, :, 1] < 193) & (original[:, :, 0] < 245)
    ink_mask = np.where(ink, 255, 0).astype(np.uint8)
    ink_mask = cv2.dilate(ink_mask, np.ones((3, 3), dtype=np.uint8), iterations=1)
    return cv2.bitwise_and(ink_mask, roi)


def render_label(font_path: Path, label: Label, ink_color: tuple[int, int, int]) -> Image.Image:
    """Render and rotate sharp Korean ink with supersampled antialiasing."""
    scale = 4
    font = ImageFont.truetype(str(font_path), label.size * scale)
    tracking = label.tracking * scale
    glyphs = list(label.korean)
    advance = [ImageDraw.Draw(Image.new("L", (1, 1))).textlength(c, font=font) for c in glyphs]
    width = int(sum(advance) + max(len(glyphs) - 1, 0) * tracking + 24 * scale)
    height = label.size * scale * 3
    temp = Image.new("RGBA", (max(width, 1), height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(temp)
    x = 12 * scale
    for glyph, step in zip(glyphs, advance):
        draw.text((round(x), 4 * scale), glyph, font=font, fill=(*ink_color, 250), anchor="lt")
        x += step + tracking
    cropbox = temp.getbbox()
    if not cropbox:
        raise ValueError(f"No glyphs rendered for {label.key}: {label.korean}")
    cropped = temp.crop(cropbox)
    rotated = cropped.rotate(label.angle, resample=Image.Resampling.BICUBIC, expand=True)
    return rotated.resize(
        (max(1, round(rotated.width / scale)), max(1, round(rotated.height / scale))),
        Image.Resampling.LANCZOS,
    )


def build(original_image: Image.Image, font_path: Path) -> tuple[Image.Image, np.ndarray]:
    rgba = np.asarray(original_image.convert("RGBA"))
    rgb = rgba[:, :, :3].copy()
    mask = make_erase_mask(rgb)
    repaired = cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)
    working = Image.fromarray(np.dstack((repaired, rgba[:, :, 3])), "RGBA")
    for entry in LABELS:
        text = render_label(font_path, entry, (96, 76, 21))
        px = round(entry.center[0] - text.width / 2)
        py = round(entry.center[1] - text.height / 2)
        working.alpha_composite(text, (px, py))

    # Redguard is palette-based. Snap the touched RGB pixels back to one of the
    # original colors to prevent introducing novel ink shades during repainting.
    out = np.asarray(working.convert("RGBA")).copy()
    colors = np.unique(rgb.reshape(-1, 3), axis=0)
    changed = np.any(out[:, :, :3] != rgb, axis=2)
    if changed.any():
        _, idx = cKDTree(colors.astype(np.float32)).query(out[:, :, :3][changed], k=1)
        out[:, :, :3][changed] = colors[idx]
    out[:, :, 3] = rgba[:, :, 3]
    return Image.fromarray(out, "RGBA"), mask


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--font", type=Path, default=FONT)
    parser.add_argument("--output", type=Path, default=DEST)
    args = parser.parse_args()
    if not args.source.is_file() or not args.font.is_file():
        parser.error(f"Input unavailable: source={args.source!s} font={args.font!s}")
    original = Image.open(args.source).convert("RGBA")
    if original.size != (640, 480):
        parser.error(f"MAPMAP preview coordinates expect 640x480, got {original.size}")
    args.output.mkdir(parents=True, exist_ok=True)
    grid = make_grid(original)
    grid.save(args.output / "map_coordinate_grid.png")
    korean, mask = build(original, args.font)
    korean.save(args.output / "map_ko_draft.png")
    original.save(args.output / "map_original_reference.png")
    compare = Image.new("RGBA", (1280, 480))
    compare.paste(original, (0, 0))
    compare.paste(korean, (640, 0))
    compare.save(args.output / "map_before_after.png")
    Image.fromarray(mask).save(args.output / "map_erasure_mask.png")
    report = {
        "source": str(args.source),
        "font": args.font.name,
        "original_size": original.size,
        "labels": [asdict(entry) for entry in LABELS],
        "pixels_inpainted": int(np.count_nonzero(mask)),
        "status": "draft only; no GXA repack or game test",
    }
    (args.output / "map_labels.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved preview and map draft to {args.output}")
    print(f"Labels: {len(LABELS)}; painted ink pixels: {report['pixels_inpainted']}")


if __name__ == "__main__":
    main()
