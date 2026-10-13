"""Build Korean glyph masks and style maps from the installed ORIGINAL fonts.

Styles identify a loaded font by its copied FNHD name and an A bitmap sample.
0 stays transparent. Native single-color glyphs use logical ink 1, interpreted
by the original general text renderer using the live foreground color.
No font, palette or game bitmap is included in this source module.
"""
from pathlib import Path
import collections
import json
import runpy
import struct

from unicode_font import Glyph, pack, unpack

ROOT = Path(__file__).resolve().parents[2]
HEADER_SIZE = 32
STYLE_STRIDE = 320


def native_style(font):
    glyph = next(g for g in font['glyphs'] if g['codepoint'] == 65)
    pixels, width, height = glyph['pixels'], glyph['width'], glyph['height']
    sample = next(i for i, v in enumerate(pixels) if v)
    edge, core = collections.Counter(), collections.Counter()
    for y in range(height):
        for x in range(width):
            value = pixels[y * width + x]
            if not value:
                continue
            boundary = any(not (0 <= x + dx < width and 0 <= y + dy < height) or
                           not pixels[(y + dy) * width + x + dx]
                           for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)])
            (edge if boundary else core)[value] += 1
    body = (core or edge).most_common(1)[0][0]
    border = edge.most_common(1)[0][0]
    mono = set(pixels) <= {0, 1}
    return glyph, sample, body, border, mono


def style_lut(reference, target):
    ref, _, _, _, _ = native_style(reference)
    glyph, _, body, border, mono = native_style(target)
    if mono:
        lut = bytearray([0] + [1] * 255)
        lut[195] = 0  # Original single-color families do not have an outline.
        return bytes(lut)
    inks = set(glyph['pixels']) - {0}
    luminance = lambda value: sum(w * c for w, c in zip((299, 587, 114), target['palette'][value * 3:value * 3 + 3]))
    lightest, darkest = max(inks, key=luminance), min(inks - {border} or inks, key=luminance)
    lut = bytearray([body] * 256)
    lut[0], lut[195], lut[81] = 0, border, body
    lut[112], lut[116], lut[119] = lightest, body, darkest
    # Identically shaped native families have an exact source-to-target map.
    if (ref['width'], ref['height']) == (glyph['width'], glyph['height']):
        pairs = collections.defaultdict(set)
        for old, new in zip(ref['pixels'], glyph['pixels']):
            pairs[old].add(new)
        if all(len(values) == 1 for values in pairs.values()) and pairs[0] == {0}:
            for old, values in pairs.items():
                lut[old] = next(iter(values))
    return bytes(lut)


def menu_colors(font, filename, palette=None):
    """Menu-only overrides; general/dialogue LUT remains byte-for-byte intact.

    Metadata at style+304: dark outline, selected body/highlight/mid/shade,
    enabled. RGB values are native 6-bit font palette components.
    """
    glyph, _, _, border, mono = native_style(font)
    if mono:
        return bytes(16)
    # Menu bitmaps are drawn into the shared framebuffer palette. LOWFONT and
    # LONORMAL have identical glyphs but different embedded palette chunks;
    # using those chunks would give the same runtime font two outline colors.
    palette = font['palette'] if palette is None else palette
    dark = min(range(1, 256), key=lambda i: sum((palette[i * 3 + j] - (3, 1, 0)[j]) ** 2 for j in range(3)))
    selected = filename.upper() in {'FONTSEL.FNT', 'FONTSELS.FNT', 'HISELECT.FNT', 'LOSELECT.FNT'}
    inks = collections.Counter(glyph['pixels'])
    inks.pop(0, None)
    brightness = lambda i: sum(w * c for w, c in zip((299, 587, 114), palette[i * 3:i * 3 + 3]))
    if selected:
        body = border
        highlight = max(inks, key=brightness)
        mid = next((v for v, _ in inks.most_common() if v != body and brightness(v) > brightness(body) * .75), body)
        shade = native_style(font)[2]
    else:
        body = highlight = mid = shade = 0
    return bytes([dark, body, highlight, mid, shade, 1]) + bytes(10)


def menu_lut(reference, target, filename):
    lut = bytearray(style_lut(reference, target))
    options = menu_colors(target, filename, reference['palette'])
    if options[5]:
        lut[195] = options[0]
        if options[1]:
            for source, value in zip((81, 112, 116, 119), options[1:5]):
                lut[source] = value
    return bytes(lut)


def build_styles(font_dir):
    read = runpy.run_path(str(ROOT / 'tools/fnt/fnt_tool.py'))['read_font']
    reference = read((font_dir / 'REDSEL.FNT').read_bytes())
    files = [font_dir / 'REDSEL.FNT'] + sorted(p for p in font_dir.glob('*.FNT') if p.name != 'REDSEL.FNT')
    records, descriptions = [], []
    for path in files:
        font = read(path.read_bytes())
        glyph, sample, body, border, mono = native_style(font)
        name = font['raw_chunks'][b'FNHD'][:32]
        prefix = name + struct.pack('<HHIII', glyph['width'], glyph['height'], sample,
                                    glyph['pixels'][sample], int(mono))
        lut = style_lut(reference, font)
        options = menu_colors(font, path.name, reference['palette'])
        record = prefix + lut + options
        assert len(prefix) == 48 and len(record) == STYLE_STRIDE
        records.append(record)
        descriptions.append({'file': path.name, 'body_index': body, 'outline_index': border,
                             'monochrome_uses_live_foreground': mono, 'sample_offset': sample,
                             'sample_value': glyph['pixels'][sample], 'lut_hex': lut.hex(),
                             'menu_outline_index': options[0], 'menu_selected_body_index': options[1]})
    header = struct.pack('<4s7I', b'KCL1', len(records), STYLE_STRIDE, 0, 0, 0, 0, 0)
    return header + b''.join(records), descriptions


def outlined_pack(blob):
    from PIL import Image, ImageFilter
    result = []
    for glyph in unpack(blob):
        # Only synthetic single-ink glyphs are changed. Existing original Latin
        # and fallback bitmap gradients retain their native REDSEL indices.
        if set(glyph.pixels) - {0} != {195} or glyph.scalar < 256:
            result.append(glyph)
            continue
        width, height = glyph.width + 2, glyph.height + 2
        mask = Image.new('L', (width, height))
        mask.paste(Image.frombytes('L', (glyph.width, glyph.height), glyph.pixels).point(lambda x: 255 if x else 0), (1, 1))
        dilation = mask.filter(ImageFilter.MaxFilter(3))
        pixels = bytearray(width * height)
        for i, (inside, edge) in enumerate(zip(mask.tobytes(), dilation.tobytes())):
            y = i // width - 1
            shade = 112 if y < glyph.height * .15 else 81 if y < glyph.height * .5 else 116 if y < glyph.height * .85 else 119
            pixels[i] = shade if inside else 195 if edge else 0
        result.append(Glyph(glyph.scalar, width, height, glyph.left - 1, glyph.top - 1,
                            glyph.advance, bytes(pixels), glyph.enabled))
    return pack(result)


def build(font_dir, base_pack, output):
    output.mkdir(parents=True, exist_ok=False)
    styles, descriptions = build_styles(font_dir)
    (output / 'font_styles.bin').write_bytes(styles)
    (output / 'redsel_unicode_prototype.kgf').write_bytes(outlined_pack(base_pack.read_bytes()))
    (output / 'palette.json').write_bytes((base_pack.parent / 'palette.json').read_bytes())
    (output / 'font_styles.json').write_text(json.dumps(descriptions, indent=2), encoding='utf-8')
    return {'native_styles': len(descriptions), 'glyphs': len(unpack((output / 'redsel_unicode_prototype.kgf').read_bytes()))}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font-dir', type=Path, required=True)
    parser.add_argument('--base-pack', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.font_dir, args.base_pack, args.output)))
