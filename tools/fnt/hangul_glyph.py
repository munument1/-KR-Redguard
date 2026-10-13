"""Rasterize one Hangul syllable to a Redguard palette-index glyph JSON.

Requires Pillow, installed separately (`python -m pip install pillow`).
Provide an open-licensed TTF/OTF file; this script never bundles font files.
"""

import argparse
import json
from pathlib import Path


def render(font_path: Path, text: str, size: int, color_index: int, top: int = 0) -> dict:
    from PIL import Image, ImageDraw, ImageFont

    if len(text) != 1 or not (0xAC00 <= ord(text) <= 0xD7A3):
        raise ValueError("choose one precomposed modern Hangul syllable")
    if not (4 <= size <= 96 and 1 <= color_index <= 255):
        raise ValueError("size must be 4..96, palette index 1..255")
    font = ImageFont.truetype(str(font_path), size=size)
    box = font.getbbox(text)
    if box is None:
        raise ValueError("font cannot provide this glyph")
    width, height = box[2] - box[0], box[3] - box[1]
    if width < 1 or height < 1:
        raise ValueError("glyph has empty bounds")
    image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(image).text((-box[0], -box[1]), text, fill=255, font=font)
    raw = [color_index if pixel >= 128 else 0 for pixel in image.tobytes()]
    if not any(raw):
        raise ValueError("font produced no visible pixels")
    return {
        "character": text, "width": width, "height": height,
        "offset_left": 0, "offset_top": top, "pixels": raw,
        "source_font_name": font_path.name, "size": size, "palette_index": color_index,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--font", type=Path, required=True)
    ap.add_argument("--text", required=True, help="one Hangul syllable")
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--palette-index", type=int, default=195)
    ap.add_argument("--offset-top", type=int, default=3)
    ap.add_argument("--output", type=Path, required=True)
    opts = ap.parse_args()
    data = render(opts.font, opts.text, opts.size, opts.palette_index, opts.offset_top)
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{opts.text} => {data['width']}x{data['height']} at {opts.output}")


if __name__ == "__main__":
    main()
