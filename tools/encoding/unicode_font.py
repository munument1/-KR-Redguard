"""Sparse Unicode bitmap font sidecar for the experimental x86 text runtime.

KGF1 header: magic, count, stride=24, records offset=24, bitmaps offset, size.
Record: scalar:u32, bitmap offset:u32, width/height:u16, left/top:i16,
advance/enabled:u16, bitmap length:u32. Offsets are relative to the pack base.
This is a NEW format, not an extended vanilla FNT. No game loader is installed.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

HEADER = struct.Struct('<4s5I')
RECORD = struct.Struct('<IIHHhhHHI')


@dataclass(frozen=True)
class Glyph:
    scalar: int
    width: int
    height: int
    left: int
    top: int
    advance: int
    pixels: bytes
    enabled: int = 1


def pack(glyphs: list[Glyph]) -> bytes:
    ordered = sorted(glyphs, key=lambda glyph: glyph.scalar)
    if not ordered or len(ordered) > 65535:
        raise ValueError('expected 1..65535 sparse glyphs')
    if len({glyph.scalar for glyph in ordered}) != len(ordered):
        raise ValueError('duplicate Unicode scalar')
    bitmap_start = HEADER.size + len(ordered) * RECORD.size
    rows, pixels = bytearray(), bytearray()
    for glyph in ordered:
        if not 0 <= glyph.scalar <= 0x10FFFF or 0xD800 <= glyph.scalar <= 0xDFFF:
            raise ValueError('invalid Unicode scalar')
        if not 0 <= glyph.width <= 256 or not 0 <= glyph.height <= 256:
            raise ValueError('bitmap dimension out of range')
        if not 0 <= glyph.advance <= 65535 or glyph.enabled not in (0, 1):
            raise ValueError('invalid glyph advance or enabled flag')
        if not -32768 <= glyph.left <= 32767 or not -32768 <= glyph.top <= 32767:
            raise ValueError('invalid glyph origin')
        if len(glyph.pixels) != glyph.width * glyph.height:
            raise ValueError('bitmap length mismatch')
        rows.extend(RECORD.pack(glyph.scalar, bitmap_start + len(pixels), glyph.width,
                                glyph.height, glyph.left, glyph.top, glyph.advance,
                                glyph.enabled, len(glyph.pixels)))
        pixels.extend(glyph.pixels)
    total = bitmap_start + len(pixels)
    return HEADER.pack(b'KGF1', len(ordered), RECORD.size, HEADER.size, bitmap_start, total) + rows + pixels


def unpack(blob: bytes) -> list[Glyph]:
    if len(blob) < HEADER.size:
        raise ValueError('truncated font header')
    magic, count, stride, records, bitmaps, size = HEADER.unpack_from(blob)
    if (magic != b'KGF1' or not 1 <= count <= 65535 or stride != RECORD.size or
            records != HEADER.size or bitmaps != records + count * stride or size != len(blob) or bitmaps > size):
        raise ValueError('invalid font header')
    glyphs, previous, cursor = [], -1, bitmaps
    for idx in range(count):
        cp, offset, width, height, left, top, advance, enabled, length = RECORD.unpack_from(blob, records + idx * stride)
        if cp <= previous or offset != cursor or length != width * height or offset + length > size:
            raise ValueError('invalid glyph order or bitmap range')
        glyphs.append(Glyph(cp, width, height, left, top, advance, blob[offset:offset + length], enabled))
        previous, cursor = cp, offset + length
    if cursor != size or pack(glyphs) != blob:
        raise ValueError('noncanonical font pack')
    return glyphs
