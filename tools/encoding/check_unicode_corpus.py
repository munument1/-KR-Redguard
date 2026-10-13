"""Build an experimental Unicode font and run all translations through x86 layout.

Reads drafts and original FNT only. Writes only --output. The chosen TTF is a
development font, not an approved final in-game typeface. Does not patch RG.EXE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

from unicode_font import Glyph, pack, unpack
from unicode_layout_x86 import assemble, ROOT  # Adds local emulator dependency path.


def check(drafts: Path, legacy_path: Path, ttf_path: Path, output: Path) -> dict:
    from PIL import Image, ImageDraw, ImageFont
    from fontTools.ttLib import TTFont
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EDX, UC_X86_REG_ESP, UC_X86_REG_EIP

    rows, source_hashes = [], {}
    for path in sorted(drafts.glob('rtx_*_ko.jsonl')):
        raw = path.read_bytes()
        source_hashes[path.name] = hashlib.sha256(raw).hexdigest()
        rows.extend(json.loads(line) for line in raw.decode('utf-8').splitlines())
    if not rows or len({row['tag'] for row in rows}) != len(rows):
        raise ValueError('missing drafts or duplicate tags')
    if any(not isinstance(row.get('translation'), str) or not row['translation'] for row in rows):
        raise ValueError('missing translation')
    font_loader = runpy.run_path(str(ROOT / 'tools/fnt/fnt_tool.py'))['read_font']
    legacy = font_loader(legacy_path.read_bytes())
    bang = next(glyph for glyph in legacy['glyphs'] if glyph['codepoint'] == 33)
    glyphs = {}
    for glyph in legacy['glyphs']:
        cp = ord(bytes([glyph['codepoint']]).decode('cp437'))
        advance = (glyph['width'] + 1 + (bang['width'] if cp == 32 else 0)) if glyph['enabled'] else 0
        glyphs[cp] = Glyph(cp, glyph['width'], glyph['height'], glyph['offset_left'], glyph['offset_top'], advance,
                           glyph['pixels'], int(bool(glyph['enabled'])))
    needed = {ord(char) for row in rows for char in row['translation']} | {0xFFFD}
    # The installed Noto KR may not contain U+FFFD. Use the explicit legacy
    # question-mark bitmap for malformed UTF-8 instead of accepting a tofu.
    question = glyphs[63]
    glyphs[0xFFFD] = Glyph(0xFFFD, question.width, question.height, question.left,
                           question.top, question.advance, question.pixels, question.enabled)
    controls = {cp for cp in needed if cp < 32} - {9, 10, 13}
    if controls:
        raise ValueError(f'unhandled controls: {sorted(controls)}')
    missing = needed - glyphs.keys() - {9, 10, 13}
    with TTFont(ttf_path) as source_font:
        unavailable = missing - source_font.getBestCmap().keys()
    if unavailable:
        raise ValueError(f'prototype TTF lacks codepoints: {sorted(unavailable)}')
    face = ImageFont.truetype(str(ttf_path), 20)
    for cp in sorted(missing):
        char = chr(cp)
        box = face.getbbox(char)
        width, height = box[2] - box[0], box[3] - box[1]
        image = Image.new('L', (width, height), 0)
        ImageDraw.Draw(image).text((-box[0], -box[1]), char, font=face, fill=255)
        pixels = bytes(195 if alpha >= 128 else 0 for alpha in image.tobytes())
        glyphs[cp] = Glyph(cp, width, height, box[0], 3, round(face.getlength(char)) + 1, pixels)
    blob = pack(list(glyphs.values()))
    unpack(blob)
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(0x1000, 0x1000)
    code = assemble()
    machine.mem_write(0x1000, code)
    machine.mem_map(0x30000, 0x10000)
    machine.mem_map(0x50000, 0x10000)
    machine.mem_map(0x70000, 0x10000)
    machine.mem_map(0x100000, (len(blob) + 4095) // 4096 * 4096)
    machine.mem_write(0x100000, blob)
    results = []
    for row in rows:
        text = row['translation']
        data = text.encode('utf-8')
        if len(data) > 0x10000:
            raise ValueError('translation too large for corpus test buffer')
        pointer = 0x40000 - len(data)
        machine.mem_write(pointer, data)
        capacity, output_ptr, stack = 256, 0x5F000, 0x7FF00
        machine.mem_write(stack, struct.pack('<7I', 0x1FFF, pointer, len(data), 0x100000, 500, output_ptr, capacity))
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.emu_start(0x1000, 0x1FFF, count=2000000)
        if machine.reg_read(UC_X86_REG_EIP) != 0x1FFF:
            raise ValueError('layout failed to finish within instruction budget')
        count, status = machine.reg_read(UC_X86_REG_EAX), machine.reg_read(UC_X86_REG_EDX)
        if status or count > capacity:
            raise ValueError(f"{row['tag']}: layout status {status}")
        spans = [struct.unpack('<4I', machine.mem_read(output_ptr + line * 16, 16)) for line in range(count)]
        pieces = []
        previous_end = 0
        for start, end, width, flags in spans:
            if not 0 <= previous_end <= start <= end <= len(data):
                raise ValueError('nonmonotonic or invalid byte spans')
            piece = data[start:end].decode('utf-8', errors='strict')
            pieces.append(piece)
            expected = sum(4 * glyphs[32].advance if char == '\t' else
                           (glyphs[ord(char)].advance if glyphs[ord(char)].enabled else 0) for char in piece)
            if expected != width or width > 500:
                raise ValueError('width differs from bitmap metrics or exceeds limit')
            previous_end = end
        if ''.join(char for piece in pieces for char in piece if not char.isspace()) != ''.join(char for char in text if not char.isspace()):
            raise ValueError(f"{row['tag']}: non-whitespace characters lost or duplicated")
        results.append({'index': row['index'], 'tag': row['tag'], 'line_count': count,
                        'spans': [dict(start=start, end=end, width=width, flags=flags) for start, end, width, flags in spans]})
    for name, digest in source_hashes.items():
        if hashlib.sha256((drafts / name).read_bytes()).hexdigest() != digest:
            raise ValueError('translation draft changed during test')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'redsel_unicode_prototype.kgf').write_bytes(blob)
    (output / 'palette.json').write_text(json.dumps(list(legacy['palette'])), encoding='utf-8')
    report = {'status': 'prototype x86 emulation only; no game hook or framebuffer test',
              'entries_checked': len(rows), 'glyph_count': len(glyphs), 'font_pack_bytes': len(blob),
              'font_pack_sha256': hashlib.sha256(blob).hexdigest(), 'development_ttf': ttf_path.name,
              'wrap_width': 500, 'source_draft_sha256': source_hashes,
              'maximum_lines': max(result['line_count'] for result in results),
              'known_limitations': ['codepoint wrapping, not Unicode grapheme segmentation or punctuation kinsoku',
                                    'new layout accepts width equal to limit; original game uses strict less-than for tokens',
                                    '500px wrapping does not establish subtitle block fits the 480px screen'],
              'results': results}
    (output / 'corpus_layout_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {key: report[key] for key in ['status', 'entries_checked', 'glyph_count', 'font_pack_bytes', 'maximum_lines']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-font', type=Path, required=True)
    parser.add_argument('--development-font', type=Path, required=True)
    parser.add_argument('--drafts', type=Path, default=ROOT / 'output/text_translation/drafts')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/engine_utf8/unicode_layout')
    args = parser.parse_args()
    print(json.dumps(check(args.drafts, args.legacy_font, args.development_font, args.output), ensure_ascii=True))
