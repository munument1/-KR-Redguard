"""LE table growth and hook placement without proprietary game assets."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/patch'))
import build_test_exe as builder


def fixture():
    header, pages = 0x80, 163
    objects = [(0xA0000, 0x10000, 0x2045, 1, 160, 0)]
    objects += [(4096, base, 0x2043, 161 + i, 1, 0)
                for i, base in enumerate([0x120000, 0x370000, 0x4C0000])]
    objtab = b''.join(struct.pack('<6I', *obj) for obj in objects)
    pagemap = b''.join(i.to_bytes(3, 'big') + b'\0' for i in range(1, pages + 1))
    mapoff, miscoff = 196 + len(objtab), 196 + len(objtab) + len(pagemap)
    fixpageoff = miscoff + 3
    fixrecoff = fixpageoff + 4 * (pages + 1)
    # Include an original cross-object relocation in a separate code page.
    record = builder.fixrecord(7, 8, 2, 32)
    fixpages = struct.pack('<' + str(pages + 1) + 'I', 0, *([len(record)] * pages))
    loader = objtab + pagemap + b'\0' * 3 + fixpages + record + b'\0'
    dataoff = (header + 196 + len(loader) + 511) // 512 * 512
    raw = bytearray(dataoff + pages * 4096)
    raw[:2] = b'MZ'
    struct.pack_into('<I', raw, 60, header)
    raw[header:header + 4] = b'LE\0\0'
    values = {0x14: pages, 0x28: 4096, 0x2c: 4096, 0x30: len(fixpages) + len(record) + 1,
              0x38: len(loader), 0x40: 196, 0x44: 4, 0x48: mapoff,
              0x50: miscoff, 0x58: miscoff, 0x5c: miscoff + 1,
              0x68: fixpageoff, 0x6c: fixrecoff, 0x70: fixrecoff + len(record),
              0x78: fixrecoff + len(record), 0x80: dataoff}
    for off, value in values.items():
        struct.pack_into('<I', raw, header + off, value)
    raw[header + 196:header + 196 + len(loader)] = loader
    for address, prologue in [(builder.DRAW, '56575589e5'), (builder.MEASURE, '5351525657')]:
        at = dataoff + address - 0x10000
        raw[at:at + 5] = bytes.fromhex(prologue)
    raw.extend(b'XVER' + b'\0' * 24)
    return bytes(raw)


class RebuildTests(unittest.TestCase):
    def test_tables_pages_trailer_and_cross_page_fixups(self):
        raw = fixture()
        payload = b'\x90' * 9000
        hooks = [(builder.DRAW, 10), (builder.MEASURE, 20)]
        fixes = [(4094, 7, 5, 8192)]
        result, _ = builder.rebuild(raw, payload, fixes, hooks)
        before, after = builder.LE(raw), builder.LE(result)
        self.assertEqual(after.pages, before.pages + 3)
        self.assertEqual(after.objects[:4], before.objects)
        self.assertEqual(after.objects[4][0], len(payload))
        self.assertEqual(after.u32(0x2c), 808)
        self.assertTrue(result.endswith(b'XVER' + b'\0' * 24))
        self.assertEqual(list(after.fixups(0)), list(before.fixups(0)))
        self.assertEqual(list(after.fixups(before.pages)), [(7, 4094, 5, 8192)])
        self.assertEqual(list(after.fixups(before.pages + 1)), [(7, -2, 5, 8192)])
        self.assertEqual(result[after.file_offset(builder.BASE):after.file_offset(builder.BASE) + 9000], payload)
        for address, offset in hooks:
            at = after.file_offset(address)
            self.assertEqual(result[at], 0xE9)
            self.assertEqual(address + 5 + struct.unpack_from('<i', result, at + 1)[0], builder.BASE + offset)

    def test_changed_hook_and_unexpected_original_page_edits_rejected(self):
        raw = fixture()
        hooks = [(builder.DRAW, 10), (builder.MEASURE, 20)]
        broken = bytearray(raw)
        broken[builder.LE(raw).file_offset(builder.DRAW)] ^= 1
        with self.assertRaisesRegex(ValueError, 'instruction mismatch'):
            builder.rebuild(bytes(broken), b'\x90' * 9000, [], hooks)
        result, _ = builder.rebuild(raw, b'\x90' * 9000, [], hooks)
        broken = bytearray(result)
        broken[builder.LE(result).file_offset(0x11000)] ^= 1
        with self.assertRaisesRegex(ValueError, 'unexpected original page'):
            builder.validate(raw, bytes(broken), hooks, [], b'\x90' * 9000)


if __name__ == '__main__':
    unittest.main()
