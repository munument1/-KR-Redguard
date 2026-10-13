"""Exercise the actual Unicode layout machine code with >256 glyphs."""
import importlib.util
from pathlib import Path
import struct
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools/encoding' / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


font = load('rg_unicode_font', 'unicode_font.py')
runtime = load('rg_unicode_layout', 'unicode_layout_x86.py')
try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_MEM_READ
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EDX, UC_X86_REG_ESP, UC_X86_REG_EIP,
        UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)
    AVAILABLE = importlib.util.find_spec('keystone') is not None
except ImportError:
    AVAILABLE = False


class FontTests(unittest.TestCase):
    def test_more_than_256_distinct_bitmap_records(self):
        glyphs = [font.Glyph(cp, 1, 1, 0, 0, cp % 31, bytes([cp % 256]))
                  for cp in range(0xAC00, 0xAC00 + 3000)]
        blob = font.pack(glyphs)
        self.assertEqual(font.unpack(blob), glyphs)
        self.assertEqual(font.RECORD.size, 24)

    def test_corrupt_fonts_rejected(self):
        glyph = font.Glyph(0xAC00, 1, 1, 0, 0, 20, b'\x01')
        for bad in [b'', font.pack([glyph])[:-1], b'BAD!' + font.pack([glyph])[4:]]:
            with self.assertRaises(ValueError):
                font.unpack(bad)
        with self.assertRaises(ValueError):
            font.pack([glyph, glyph])
        with self.assertRaises(ValueError):
            font.pack([font.Glyph(0xD800, 1, 1, 0, 0, 1, b'\x01')])


@unittest.skipUnless(AVAILABLE, 'requires local unicorn and keystone-engine')
class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = runtime.assemble()

    def layout(self, text, width, capacity=128, advances=None, missing=None, disabled=None):
        data = text.encode('utf-8') if isinstance(text, str) else text
        chars = set(range(32, 127)) | {ord(c) for c in data.decode('utf-8', errors='replace')}
        # Deliberately allocate thousands of rows before the Korean glyphs.
        chars |= set(range(0x1000, 0x1000 + 3000))
        chars -= {ord(char) for char in (missing or '')}
        advances = advances or {}
        pack = font.pack([font.Glyph(cp, 1, 1, 0, 0, advances.get(chr(cp), 1), b'\x01',
                                    int(chr(cp) not in (disabled or ''))) for cp in chars])
        font.unpack(pack)  # The loader must validate before x86 code sees the table.
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(0x1000, 0x1000)
        machine.mem_write(0x1000, self.code)
        machine.mem_map(0x30000, 0x10000)
        pointer = 0x40000 - len(data)
        if data:
            machine.mem_write(pointer, data)
        machine.mem_map(0x50000, 0x10000)
        # End output at an unmapped page to catch capacity overruns.
        output = 0x60000 - capacity * 16
        if capacity:
            machine.mem_write(output, b'\xAA' * (capacity * 16))
        machine.mem_map(0x70000, 0x10000)
        machine.mem_map(0x100000, (len(pack) + 4095) // 4096 * 4096)
        machine.mem_write(0x100000, pack)
        stack = 0x7FF00
        machine.mem_write(stack, struct.pack('<7I', 0x1FFF, pointer, len(data), 0x100000, width, output, capacity))
        machine.reg_write(UC_X86_REG_ESP, stack)
        preserved = [UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]
        for idx, reg in enumerate(preserved):
            machine.reg_write(reg, 0xB1230000 + idx)
        machine.emu_start(0x1000, 0x1FFF, count=1000000)
        self.assertEqual(machine.reg_read(UC_X86_REG_EIP), 0x1FFF)
        self.assertEqual(machine.reg_read(UC_X86_REG_ESP), stack + 4)
        for idx, reg in enumerate(preserved):
            self.assertEqual(machine.reg_read(reg), 0xB1230000 + idx)
        count, status = machine.reg_read(UC_X86_REG_EAX), machine.reg_read(UC_X86_REG_EDX)
        self.assertLessEqual(count, capacity)
        rows = [struct.unpack('<4I', machine.mem_read(output + idx * 16, 16)) for idx in range(count)]
        for start, end, pixels, flags in rows:
            self.assertLessEqual(start, end)
            self.assertLessEqual(end, len(data))
            if status != 2 and not flags & 1:
                self.assertLessEqual(pixels, width)
        # Unused output slots must remain untouched.
        if capacity > count:
            self.assertEqual(bytes(machine.mem_read(output + count * 16, (capacity - count) * 16)), b'\xAA' * ((capacity - count) * 16))
        return data, rows, status

    def lines(self, result):
        data, rows, status = result
        self.assertEqual(status, 0)
        return [data[start:end].decode('utf-8') for start, end, _, _ in rows]

    def test_english_word_wrap_and_exact_width(self):
        self.assertEqual(self.lines(self.layout('one two three', 10)), ['one two', 'three'])
        self.assertEqual(self.lines(self.layout('12345', 5)), ['12345'])
        self.assertEqual(self.lines(self.layout('abcdefgh', 3)), ['abc', 'def', 'gh'])

    def test_korean_with_high_glyph_indices(self):
        self.assertEqual(self.lines(self.layout('가나다라마', 40, advances={c:20 for c in '가나다라마'})), ['가나', '다라', '마'])
        self.assertEqual(self.lines(self.layout('훈딩 만으로 가자', 5)), ['훈딩', '만으로', '가자'])

    def test_hard_breaks_empty_lines_and_crlf(self):
        self.assertEqual(self.lines(self.layout('가\r\n나\n\n다\r', 10)), ['가', '나', '', '다', ''])
        self.assertEqual(self.lines(self.layout('', 10)), [''])

    def test_four_byte_characters_and_tabs(self):
        self.assertEqual(self.lines(self.layout('가😀나다', 2)), ['가😀', '나다'])
        data, rows, status = self.layout('a\tb', 6)
        self.assertEqual(status, 0)
        self.assertEqual(rows, [(0, 3, 6, 0)])

    def test_capacity_invalid_width_and_oversized_glyph(self):
        self.assertEqual(self.layout('가나다', 1, capacity=0)[2], 1)
        self.assertEqual(self.layout('가나다', 1, capacity=1)[2], 1)
        self.assertEqual(self.layout('가', 0)[2], 2)
        _, rows, status = self.layout('가', 10, advances={'가':20})
        self.assertEqual(status, 0)
        self.assertEqual(rows, [(0, 3, 20, 1)])

    def test_missing_glyph_fallback_and_disabled_glyph(self):
        _, rows, status = self.layout('a☃b', 10, advances={'?':5}, missing='☃')
        self.assertEqual(status, 0)
        self.assertEqual(rows, [(0, 5, 7, 0)])
        _, rows, status = self.layout('가나다', 10, advances={'가':20}, disabled='가')
        self.assertEqual(status, 0)
        self.assertEqual(rows, [(0, 9, 2, 0)])

    def test_truncated_utf8_at_unmapped_boundary(self):
        data, rows, status = self.layout(b'\xe1\x80', 1)
        self.assertEqual(status, 0)
        self.assertEqual(rows, [(0, 1, 1, 0), (1, 2, 1, 0)])

    def test_random_mixed_text_conserves_characters_and_measured_width(self):
        generator = random.Random(20261013)
        alphabet = '가나다abc 😀\r\n\t'
        advances = {char: generator.randrange(1, 26) for char in alphabet}
        for sample in range(100):
            text = ''.join(generator.choice(alphabet) for _ in range(generator.randrange(0, 80)))
            with self.subTest(sample=sample):
                data, rows, status = self.layout(text, generator.randrange(1, 40), advances=advances)
                self.assertEqual(status, 0)
                pieces = [data[start:end].decode('utf-8') for start, end, _, _ in rows]
                self.assertEqual(''.join(char for piece in pieces for char in piece if not char.isspace()),
                                 ''.join(char for char in text if not char.isspace()))
                for piece, (_, _, pixels, _) in zip(pieces, rows):
                    expected = sum(4 * advances[' '] if char == '\t' else advances[char] for char in piece)
                    self.assertEqual(pixels, expected)

    def test_lookup_does_not_scan_11413_slots(self):
        from keystone import Ks, KS_ARCH_X86, KS_MODE_32
        count, first, base = 11413, 0x10000, 0x100000
        blob = font.pack([font.Glyph(first + idx, 0, 0, 0, 0, 20, b'') for idx in range(count)])
        encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(runtime.LOOKUP)
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(0x1000, 0x1000)
        machine.mem_write(0x1000, bytes(encoded))
        machine.mem_map(0x70000, 0x1000)
        machine.mem_map(base, (len(blob) + 4095) // 4096 * 4096)
        machine.mem_write(base, blob)
        visits = [0]

        def record_read(_machine, _access, address, size, _value, _user):
            relative = address - base - font.HEADER.size
            if 0 <= relative < count * font.RECORD.size and relative % font.RECORD.size == 0 and size == 4:
                visits[0] += 1

        machine.hook_add(UC_HOOK_MEM_READ, record_read)
        # Check every slot, as well as missing keys on both sides of the table.
        for scalar in range(first - 1, first + count + 1):
            visits[0] = 0
            machine.mem_write(0x70FF0, struct.pack('<I', 0x1FFF))
            machine.reg_write(UC_X86_REG_ESP, 0x70FF0)
            machine.reg_write(UC_X86_REG_EAX, scalar)
            machine.reg_write(UC_X86_REG_EDX, base)
            machine.emu_start(0x1000, 0x1FFF, count=1000)
            self.assertEqual(machine.reg_read(UC_X86_REG_EIP), 0x1FFF)
            expected = base + font.HEADER.size + (scalar - first) * font.RECORD.size if first <= scalar < first + count else 0
            self.assertEqual(machine.reg_read(UC_X86_REG_EAX), expected)
            self.assertLessEqual(visits[0], count.bit_length(), f'linear glyph scan for U+{scalar:04X}')


if __name__ == '__main__':
    unittest.main()
