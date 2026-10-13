"""Read and visualize original Redguard FNT bitmap fonts (no dependencies)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import zlib


class FntError(ValueError):
    pass


def read_font(raw: bytes) -> dict:
    pos = 0
    chunks: dict[bytes, bytes] = {}
    order = []
    end_marker = False
    while pos + 4 <= len(raw):
        tag = raw[pos:pos + 4]
        if tag == b"END ":
            pos += 4
            end_marker = True
            break
        if pos + 8 > len(raw):
            raise FntError("truncated chunk header")
        length = struct.unpack_from(">I", raw, pos + 4)[0]
        if length > len(raw) - (pos + 8):
            raise FntError("chunk beyond file")
        if tag in chunks or tag not in (b"FNHD", b"BPAL", b"FPAL", b"FBMP", b"RDAT"):
            raise FntError("duplicate/unsupported chunk")
        chunks[tag] = raw[pos + 8:pos + 8 + length]
        order.append(tag.decode("ascii"))
        pos += 8 + length
    if not end_marker or any(raw[pos:]):
        raise FntError("missing END marker or invalid trailing bytes")
    if b"FNHD" not in chunks or b"FBMP" not in chunks:
        raise FntError("missing FNHD or FBMP")
    if (b"BPAL" in chunks) == (b"FPAL" in chunks):
        raise FntError("expected exactly one palette")
    hd = chunks[b"FNHD"]
    pal = chunks.get(b"BPAL", chunks.get(b"FPAL"))
    if len(hd) != 56 or len(pal) != 768:
        raise FntError("FNHD must be 56 bytes and palette 768")
    start, count = struct.unpack_from("<HH", hd, 46)
    line_height = struct.unpack_from("<H", hd, 44)[0]
    if (struct.unpack_from("<H", hd, 34)[0] == 1) != (b"RDAT" in chunks):
        raise FntError("RDAT flag mismatch")
    glyphs = []
    blob = chunks[b"FBMP"]
    at = 0
    for i in range(count):
        if at + 10 > len(blob):
            raise FntError(f"glyph {i}: truncated record")
        enabled, left, top, width, height = struct.unpack_from("<HhhHH", blob, at)
        at += 10
        length = width * height
        if length > len(blob) - at:
            raise FntError(f"glyph {i}: truncated bitmap")
        glyphs.append({
            "index": i, "codepoint": start + i, "enabled": enabled,
            "offset_left": left, "offset_top": top, "width": width,
            "height": height, "pixels": blob[at:at + length],
        })
        at += length
    if at != len(blob):
        raise FntError("FBMP contains trailing bytes")
    return {
        "glyphs": glyphs, "start": start, "count": count,
        "line_height": line_height, "palette": pal, "chunks": order,
        "palette_tag": "BPAL" if b"BPAL" in chunks else "FPAL",
        "trailing_padding": len(raw) - pos,
        "source": raw, "raw_chunks": chunks,
    }


def make_png(font: dict, cols: int = 16) -> bytes:
    glyphs = font["glyphs"]
    max_w = max((x["width"] for x in glyphs), default=1)
    max_h = max((x["height"] for x in glyphs), default=1)
    cw, ch = max_w + 2, max_h + 2
    rows = max(1, (len(glyphs) + cols - 1) // cols)
    w, h = cw * cols, ch * rows
    if w * h > 30_000_000:
        raise FntError("atlas too large")
    pixels = bytearray(w * h * 4)
    pal = font["palette"]
    for index, item in enumerate(glyphs):
        x0, y0 = (index % cols) * cw + 1, (index // cols) * ch + 1
        for y in range(item["height"]):
            for x in range(item["width"]):
                color = item["pixels"][y * item["width"] + x]
                if color == 0:
                    continue
                target = ((y0 + y) * w + x0 + x) * 4
                source = color * 3
                pixels[target:target + 4] = bytes([min(pal[source] * 4, 255), min(pal[source + 1] * 4, 255), min(pal[source + 2] * 4, 255), 255])
    scan = b"".join(b"\x00" + pixels[y * w * 4:(y + 1) * w * 4] for y in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(scan)) + chunk(b"IEND", b"")


def metadata(font: dict) -> dict:
    return {
        "format": "redguard-fnt-metadata-v1",
        "character_start": font["start"],
        "character_count": font["count"],
        "line_height": font["line_height"],
        "palette_tag": font["palette_tag"],
        "chunks": font["chunks"],
        "trailing_padding": font["trailing_padding"],
        "byte_character_range": font["start"] + font["count"] - 1 <= 255,
        "glyphs": [{k: v for k, v in item.items() if k != "pixels"} for item in font["glyphs"]],
    }


def replace_glyph(font: dict, codepoint: int, glyph: dict) -> bytes:
    """Serialize a safe replacement of ONE existing byte-indexed glyph slot."""
    index = codepoint - font["start"]
    if not (0 <= index < font["count"] and codepoint <= 255):
        raise FntError("replacement must target an existing 0..255 character slot")
    width, height = glyph.get("width"), glyph.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or not (1 <= width <= 128 and 1 <= height <= 128):
        raise FntError("glyph dimensions must be 1..128")
    raw_pixels = glyph.get("pixels")
    if not isinstance(raw_pixels, list) or len(raw_pixels) != width * height:
        raise FntError("invalid glyph pixel array length")
    if any(not isinstance(i, int) or not (0 <= i <= 255) for i in raw_pixels):
        raise FntError("palette indices must be 0..255")
    left = glyph.get("offset_left", 0)
    top = glyph.get("offset_top", 0)
    if any(not isinstance(n, int) or n < -32768 or n > 32767 for n in (left, top)):
        raise FntError("glyph offsets must fit i16")
    out_fbmp = bytearray()
    for i, old in enumerate(font["glyphs"]):
        if i == index:
            out_fbmp.extend(struct.pack("<HhhHH", 1, left, top, width, height))
            out_fbmp.extend(raw_pixels)
        else:
            out_fbmp.extend(struct.pack("<HhhHH", old["enabled"], old["offset_left"], old["offset_top"], old["width"], old["height"]))
            out_fbmp.extend(old["pixels"])
    raw_chunks = dict(font["raw_chunks"])
    raw_chunks[b"FBMP"] = bytes(out_fbmp)
    output = bytearray()
    for tag in font["chunks"]:
        chunk = raw_chunks[tag.encode("ascii")]
        output.extend(tag.encode("ascii") + struct.pack(">I", len(chunk)) + chunk)
    output.extend(b"END " + b"\x00" * font["trailing_padding"])
    finished = bytes(output)
    verify = read_font(finished)
    if verify["count"] != font["count"] or verify["palette"] != font["palette"]:
        raise FntError("reassembled font failed invariant checks")
    for i, old in enumerate(font["glyphs"]):
        if i != index and old != verify["glyphs"][i]:
            raise FntError(f"unexpected change to glyph {i}")
    return finished


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--atlas", type=Path, help="output transparent PNG atlas")
    parser.add_argument("--json", type=Path, help="output glyph/metric JSON")
    parser.add_argument("--replace-code", type=int, help="ASCII/byte slot to replace (0..255)")
    parser.add_argument("--glyph-json", type=Path, help="single bitmap glyph payload JSON")
    parser.add_argument("--write-fnt", type=Path, help="new .FNT output for replacement")
    args = parser.parse_args()
    font = read_font(args.source.read_bytes())
    replace_options = [args.replace_code is not None, args.glyph_json is not None, args.write_fnt is not None]
    if any(replace_options) and not all(replace_options):
        parser.error("--replace-code, --glyph-json, --write-fnt must be given together")
    if all(replace_options):
        if args.source.resolve() == args.write_fnt.resolve():
            parser.error("cannot overwrite the original font")
        glyph = json.loads(args.glyph_json.read_text(encoding="utf-8"))
        font_bytes = replace_glyph(font, args.replace_code, glyph)
        args.write_fnt.parent.mkdir(parents=True, exist_ok=True)
        args.write_fnt.write_bytes(font_bytes)
        font = read_font(font_bytes)
        print(f"replaced glyph slot {args.replace_code}, wrote {args.write_fnt}")
    print(f"{args.source.name}: glyphs={font['count']} start={font['start']} line_height={font['line_height']} palette={font['palette_tag']}")
    if args.atlas:
        args.atlas.parent.mkdir(parents=True, exist_ok=True)
        args.atlas.write_bytes(make_png(font))
        print(f"atlas: {args.atlas}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(metadata(font), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"metadata: {args.json}")


if __name__ == "__main__":
    main()
