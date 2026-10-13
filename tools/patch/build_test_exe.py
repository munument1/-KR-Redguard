"""Build a LOCAL experimental RG.EXE with a fifth LE object and UTF-8 hooks.

Only the known Steam Software executable is accepted. Never writes a source
file or an installation directory. Original LE object numbers are preserved.
Reference: Open Watcom bld/watcom/h/exeflat.h (LE header/map/fixup structures).
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/encoding'))
from game_text_x86 import (assemble, BASE, PACK_OFFSET, DRAW, MEASURE, HOOK_BYTES,
                           STYLES_OFFSET, SCRATCH_OFFSET, NATIVE_FONT_OFFSET)
from unicode_font import unpack

ORIGINAL_SHA = '43450fb0fa82091fe4e4e9ad73e16fc35586c1091a25f11cec07d18078255097'
PAGE = 4096


class LE:
    def __init__(self, blob):
        self.blob = blob
        self.header = struct.unpack_from('<I', blob, 60)[0]
        if blob[self.header:self.header + 4] != b'LE\0\0' or self.u32(0x28) != PAGE:
            raise ValueError('unsupported LE format')
        self.pages = self.u32(0x14)
        self.objects = [struct.unpack_from('<6I', blob, self.header + self.u32(0x40) + i * 24)
                        for i in range(self.u32(0x44))]
        self.fixpages = struct.unpack_from('<' + str(self.pages + 1) + 'I', blob, self.header + self.u32(0x68))

    def u32(self, offset):
        return struct.unpack_from('<I', self.blob, self.header + offset)[0]

    def physical(self, logical):
        pos = self.header + self.u32(0x48) + logical * 4
        if self.blob[pos + 3] != 0:
            raise ValueError('unsupported LE page flag')
        return int.from_bytes(self.blob[pos:pos + 3], 'big')

    def file_offset(self, address):
        for size, base, flags, first, count, _ in self.objects:
            if base <= address < base + min(size, count * PAGE):
                logical = first - 1 + (address - base) // PAGE
                return self.u32(0x80) + (self.physical(logical) - 1) * PAGE + (address - base) % PAGE
        raise ValueError(f'address not backed by a page: {address:#x}')

    def records(self, page):
        pos = self.header + self.u32(0x6c)
        return self.blob[pos + self.fixpages[page]:pos + self.fixpages[page + 1]]

    def fixups(self, page):
        data = self.records(page)
        pos = 0
        while pos < len(data):
            typ, flags, disp, obj = struct.unpack_from('<BBhB', data, pos)
            pos += 5
            if typ not in (2, 7, 8) or flags not in (0, 16) or not 1 <= obj <= len(self.objects):
                raise ValueError('unsupported fixup')
            offset = 0
            if typ != 2:
                width = 4 if flags & 16 else 2
                offset = int.from_bytes(data[pos:pos + width], 'little')
                pos += width
            yield typ, disp, obj, offset
        if pos != len(data):
            raise ValueError('invalid fixup boundary')


def fixrecord(typ, displacement, obj, offset):
    return struct.pack('<BBhBI', typ, 16, displacement, obj, offset)


def rebuild(raw, payload, added_fixups, hooks):
    le = LE(raw)
    if len(le.objects) != 4 or le.u32(0x40) != 196:
        raise ValueError('unexpected original object table')
    if any(le.u32(o) for o in (0x4c, 0x54, 0x60, 0x64, 0x74, 0x7c, 0x88, 0x98, 0x9c)):
        raise ValueError('unsupported optional LE table')
    count = (len(payload) + PAGE - 1) // PAGE
    newpages = le.pages + count
    # Keep objects 1..4 and each existing logical/physical page unchanged.
    objects = raw[le.header + le.u32(0x40):le.header + le.u32(0x48)]
    objects += struct.pack('<6I', len(payload), BASE, 0x2047, le.pages + 1, count, 0)
    pagemap = raw[le.header + le.u32(0x48):le.header + le.u32(0x48) + le.pages * 4]
    pagemap += b''.join(i.to_bytes(3, 'big') + b'\0' for i in range(le.pages + 1, newpages + 1))
    # Resource/resident name/entry tables contain no object renumbering.
    misc_start = le.u32(0x48) + le.pages * 4
    misc = raw[le.header + misc_start:le.header + le.u32(0x68)]
    records = [bytearray(le.records(i)) for i in range(le.pages)] + [bytearray() for _ in range(count)]
    data_start = le.u32(0x80)
    data_end = data_start + (le.pages - 1) * PAGE + le.u32(0x2c)
    data = bytearray(raw[data_start:data_end])
    data.extend(b'\0' * (le.pages * PAGE - len(data)))
    changes = []
    for address, offset in hooks:
        expected = HOOK_BYTES[address]
        original = raw[le.file_offset(address):le.file_offset(address) + len(expected)]
        if original != expected:
            raise ValueError('hook instruction mismatch')
        obj = le.objects[0]
        logical = obj[3] - 1 + (address - obj[1]) // PAGE
        displacement = (address - obj[1]) % PAGE + 1
        if any(d < displacement - 1 + len(expected) and d + (2 if t == 2 else 4) > displacement - 1
               for t, d, _, _ in le.fixups(logical)):
            raise ValueError('hook overlaps original relocation')
        at = le.file_offset(address) - data_start
        data[at:at + len(expected)] = b'\xe9' + struct.pack('<i', BASE + offset - address - 5) + b'\x90' * (len(expected) - 5)
        records[logical].extend(fixrecord(8, displacement, 5, offset))
        changes.append({'address': hex(address), 'before': original.hex(), 'target_offset': offset})
    for source, typ, obj, offset in added_fixups:
        page, disp = divmod(source, PAGE)
        records[le.pages + page].extend(fixrecord(typ, disp, obj, offset))
        # A fixup spanning two pages appears in both page lists.
        if disp + 4 > PAGE:
            records[le.pages + page + 1].extend(fixrecord(typ, disp - PAGE, obj, offset))
    fix_offsets, fixdata = [], bytearray()
    for record in records:
        fix_offsets.append(len(fixdata))
        fixdata.extend(record)
    fix_offsets.append(len(fixdata))
    fixpages = struct.pack('<' + str(newpages + 1) + 'I', *fix_offsets)
    # Preserve the import-name terminator (and any original loader tail).
    old_tail = le.u32(0x6c) + le.fixpages[-1]
    loader_tail = raw[le.header + old_tail:le.header + le.u32(0x40) + le.u32(0x38)]
    offsets = {}
    offsets[0x40] = 196
    offsets[0x48] = 196 + len(objects)
    newmisc = offsets[0x48] + len(pagemap)
    for o in (0x50, 0x58, 0x5c):
        offsets[o] = newmisc + le.u32(o) - misc_start
    offsets[0x68] = newmisc + len(misc)
    offsets[0x6c] = offsets[0x68] + len(fixpages)
    for o in (0x70, 0x78):
        offsets[o] = offsets[0x6c] + len(fixdata) + le.u32(o) - old_tail
    loader = objects + pagemap + misc + fixpages + fixdata + loader_tail
    result = bytearray(raw[:le.header + 196]) + loader
    newdata = (len(result) + 511) // 512 * 512
    result.extend(b'\0' * (newdata - len(result)))
    result.extend(data)
    result.extend(payload)
    # XVER is a DOS extender version trailer; preserve it at EOF.
    result.extend(raw[data_end:])
    offsets.update({0x14: newpages, 0x2c: len(payload) % PAGE or PAGE,
                    0x30: len(fixpages) + len(fixdata) + len(loader_tail),
                    0x38: len(loader), 0x44: 5, 0x80: newdata})
    for o, value in offsets.items():
        struct.pack_into('<I', result, le.header + o, value)
    validate(raw, bytes(result), hooks, added_fixups, payload)
    return bytes(result), changes


def validate(original, patched, hooks, fixes, payload):
    before, after = LE(original), LE(patched)
    if after.objects[:4] != before.objects or after.objects[4][1] != BASE:
        raise ValueError('original object definitions changed')
    allowed = {before.file_offset(a) + i for a, _ in hooks for i in range(len(HOOK_BYTES[a]))}
    changed = 0
    for page in range(before.pages):
        length = before.u32(0x2c) if before.physical(page) == before.pages else PAGE
        a = before.u32(0x80) + (before.physical(page) - 1) * PAGE
        b = after.u32(0x80) + (after.physical(page) - 1) * PAGE
        for i, (x, y) in enumerate(zip(original[a:a + length], patched[b:b + length])):
            if x != y:
                changed += 1
                if a + i not in allowed:
                    raise ValueError('unexpected original page modification')
        old = list(before.fixups(page))
        new = list(after.fixups(page))
        if new[:len(old)] != old:
            raise ValueError('original relocation changed')
    if not changed:
        raise ValueError('hooks were not installed')
    start = after.file_offset(BASE)
    if patched[start:start + len(payload)] != payload:
        raise ValueError('embedded payload mismatch')
    for page in range(after.pages):
        list(after.fixups(page))
    if after.header + after.u32(0x40) + after.u32(0x38) > after.u32(0x80):
        raise ValueError('loader overlaps page data')


def build(exe, pack, output):
    raw = exe.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA:
        raise ValueError('unsupported RG.EXE version')
    if output.resolve().is_relative_to(exe.parent.resolve()):
        raise ValueError('output must be outside the game installation')
    font = pack.read_bytes()
    glyphs = unpack(font)
    styles = (pack.parent / 'font_styles.bin').read_bytes()
    if (styles[:4] != b'KCL1' or len(styles) < 32 or
            struct.unpack_from('<I', styles, 8)[0] != 320 or
            len(styles) != 32 + struct.unpack_from('<I', styles, 4)[0] * 320 or
            not 1 <= struct.unpack_from('<I', styles, 4)[0] <= 32 or
            any(styles[12:32]) or STYLES_OFFSET + len(styles) > PACK_OFFSET):
        raise ValueError('invalid native color styles')
    for at in range(32, len(styles), 320):
        w, h, sample = struct.unpack_from('<HHI', styles, at + 32)
        if not 0 < w <= 256 or not 0 < h <= 256 or sample >= w * h or styles[at + 48] != 0:
            raise ValueError('invalid native font style sample or transparency')
    if PACK_OFFSET + len(font) > SCRATCH_OFFSET:
        raise ValueError('font overlaps color scratch buffer')
    height = max(g.top + g.height for g in glyphs if g.enabled) - min(g.top for g in glyphs if g.enabled) + 2
    code, exports, fixes, source = assemble(height)
    if len(code) > STYLES_OFFSET:
        raise ValueError('code overlaps native font styles')
    payload = (code.ljust(STYLES_OFFSET, b'\0') + styles).ljust(PACK_OFFSET, b'\0') + font
    payload = payload.ljust(NATIVE_FONT_OFFSET + 0x1000, b'\0')
    hooks = [(DRAW, exports['draw']), (MEASURE, exports['measure']),
             (0x186AD, exports['general_draw']), (0x188E4, exports['clipped_draw']),
             (0x19023, exports['general_measure']), (0x190D1, exports['token_measure']),
             (0x1835C, exports['cursor_draw'])]
    patched, changes = rebuild(raw, payload, fixes, hooks)
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'RG.EXE'
    if target.exists():
        raise ValueError('refusing to overwrite an existing test EXE; choose a new output directory')
    target.write_bytes(patched)
    (output / 'text_adapter.asm').write_text(source, encoding='ascii')
    report = {'status': 'EXPERIMENTAL; DOS/game execution not verified', 'revision': 4,
              'source_sha256': ORIGINAL_SHA, 'output_sha256': hashlib.sha256(patched).hexdigest(),
              'output_size': len(patched), 'embedded_font_sha256': hashlib.sha256(font).hexdigest(),
              'glyph_count': len(glyphs), 'cached_line_height': height, 'adapter_bytes': len(code),
              'native_color_styles': struct.unpack_from('<I', styles, 4)[0],
              'font_styles_sha256': hashlib.sha256(styles).hexdigest(),
              'exports': exports, 'runtime_fixups': fixes, 'hooks': changes,
              'limitations': ['Software RG.EXE only; no Glide support',
                  'one embedded REDSEL-derived font for strings containing non-ASCII bytes',
                  'original subtitle/movie line splitting remains; UI hardcoded strings and movies 1-4 untranslated',
                  'DOS startup, shadow/scaling/clipping and in-game font appearance need play testing'],
              'game_verified': False}
    (output / 'build_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if hashlib.sha256(exe.read_bytes()).hexdigest() != ORIGINAL_SHA:
        raise ValueError('source changed during build')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--font-pack', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.exe, args.font_pack, args.output), indent=2))
