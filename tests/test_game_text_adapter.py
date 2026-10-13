"""Exercise relocated adapter code, original ABI and bounded UTF-8 reads."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/encoding'))
import game_text_x86 as adapter
from unicode_font import Glyph, pack, unpack

try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
        UC_X86_REG_ESP, UC_X86_REG_EIP)
    AVAILABLE = importlib.util.find_spec('keystone') is not None
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, 'requires local keystone/unicorn')
class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.exports, cls.fixes, _ = adapter.assemble(8)
        cls.font = pack([Glyph(cp, 3, 4, 1, 2, 5, bytes([17]) * 12)
                         for cp in [32, 63, 65, 0xAC00, 0xB098, 0xFFFD]])

    def run_adapter(self, text, draw=False, flags=0, rebase=False, entry=None,
                    mono=False, foreground=17, lut=None, native_backend=False,
                    menu_options=None, glyph_pixels=None):
        # Code, data and injected object move independently, as LE fixups allow.
        old_base = 0x110000 if rebase else 0x10000
        data_base = 0x220000 if rebase else 0x120000
        new_base = 0x1500000 if rebase else adapter.BASE
        code = bytearray(self.code)
        for source, typ, obj, offset in self.fixes:
            target = {1: old_base, 2: data_base, 5: new_base}[obj] + offset
            value = target if typ == 7 else target - (new_base + source) - 4
            struct.pack_into('<I', code, source, value & 0xFFFFFFFF)
        m = Uc(UC_ARCH_X86, UC_MODE_32)
        m.mem_map(old_base, 0x100000)
        m.mem_map(new_base, 0xb0000)
        m.mem_map(data_base, 0x10000)
        native_call = data_base + 0x22483b
        m.mem_map(native_call & ~4095, 4096)
        m.mem_map(0x3000000, 0x1000)
        m.mem_map(0x3100000, 0x10000)
        m.mem_map(0x3200000, 0x1000)
        m.mem_write(new_base, bytes(code))
        font = self.font
        if glyph_pixels is not None:
            font = pack([Glyph(g.scalar, g.width, g.height, g.left, g.top, g.advance, glyph_pixels, g.enabled)
                         for g in unpack(font)])
        m.mem_write(new_base + adapter.PACK_OFFSET, font)
        style = b'\0' * 32 + struct.pack('<HHIII', 3, 4, 0, 17, int(mono)) + (lut or bytes(range(256))) + (menu_options or b'\0' * 16)
        m.mem_write(new_base + adapter.STYLES_OFFSET,
                    struct.pack('<4s7I', b'KCL1', 1, 320, 0, 0, 0, 0, 0) + style)
        native = data_base + 0x1000
        m.mem_write(data_base + 0x3e00, struct.pack('<I', native))
        m.mem_write(data_base + 0x3e04, bytes([foreground]))
        for off, value in [(0x42, 65), (0x44, 1), (0x250, 3), (0x450, 4)]:
            m.mem_write(native + off, struct.pack('<H', value))
        m.mem_write(native + 0xa50, struct.pack('<I', data_base + 0x6000))
        m.mem_write(data_base + 0x6000, bytes([17]) * 12)
        # Fake only the original routines after the preserved entry prologues.
        m.mem_write(old_base + 0x66e9d, bytes.fromhex('89ec5d5f5ec3'))
        m.mem_write(old_base + 0x6718a, bytes.fromhex('55b87b0000005d5f5e5a595bc3'))
        textptr = 0x3001000 - len(text) - 1
        m.mem_write(textptr, text + b'\0')
        sp = 0x310f000
        m.mem_write(sp, struct.pack('<I', 0x3200000))
        if native_backend:
            flags |= 0x100
        regs = {UC_X86_REG_EAX: 100 if draw else textptr, UC_X86_REG_EDX: 40,
                UC_X86_REG_EBX: flags, UC_X86_REG_ECX: textptr if draw else 0x1234,
                UC_X86_REG_ESI: 0x5678, UC_X86_REG_EDI: 0x9abc, UC_X86_REG_EBP: 0xdef0}
        for reg, value in regs.items():
            m.reg_write(reg, value)
        m.reg_write(UC_X86_REG_ESP, sp)
        calls = []
        self.last_rendered_inks = []

        def blit(cpu, address, size, user):
            esp = cpu.reg_read(UC_X86_REG_ESP)
            ret, w, h, mode, pixels = struct.unpack('<5I', cpu.mem_read(esp, 20))
            calls.append((cpu.reg_read(UC_X86_REG_EAX), cpu.reg_read(UC_X86_REG_EDX),
                          cpu.reg_read(UC_X86_REG_EBX), cpu.reg_read(UC_X86_REG_ECX)))
            self.assertEqual((w, h, mode), (3, 4, 1))
            self.last_rendered_inks.append(bytes(cpu.mem_read(pixels, 12)))
            # Original blitter is allowed to destroy scratch registers.
            for reg in [UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX]:
                cpu.reg_write(reg, 0xBAD)
            cpu.reg_write(UC_X86_REG_ESP, esp + 20)
            cpu.reg_write(UC_X86_REG_EIP, ret)
        at = old_base + adapter.BLIT - 0x10000
        m.hook_add(UC_HOOK_CODE, blit, begin=at, end=at)
        def native_blit(cpu, address, size, user):
            current = struct.unpack('<I', cpu.mem_read(data_base + 0x3e00, 4))[0]
            self.assertEqual(current, new_base + adapter.NATIVE_FONT_OFFSET)
            width = struct.unpack('<H', cpu.mem_read(current + 0x250, 2))[0]
            height = struct.unpack('<H', cpu.mem_read(current + 0x450, 2))[0]
            pixels = struct.unpack('<I', cpu.mem_read(current + 0xa50, 4))[0]
            inks = bytes(cpu.mem_read(pixels, width * height))
            self.last_rendered_inks.append(bytes(foreground if v == 1 else v for v in inks))
            calls.append((cpu.reg_read(UC_X86_REG_EAX), cpu.reg_read(UC_X86_REG_EBX), width, height))
            esp = cpu.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack('<I', cpu.mem_read(esp, 4))[0]
            cpu.reg_write(UC_X86_REG_ESP, esp + 4)
            cpu.reg_write(UC_X86_REG_EIP, ret)
        m.hook_add(UC_HOOK_CODE, native_blit, begin=native_call, end=native_call)
        m.emu_start(new_base + self.exports[entry or ('draw' if draw else 'measure')], 0x3200000, count=1000000)
        self.assertEqual(m.reg_read(UC_X86_REG_EIP), 0x3200000)
        self.assertEqual(m.reg_read(UC_X86_REG_ESP), sp + 4)
        self.assertEqual(struct.unpack('<I', m.mem_read(data_base + 0x3e00, 4))[0], native)
        for reg, value in regs.items():
            if reg != UC_X86_REG_EAX or draw:
                self.assertEqual(m.reg_read(reg), value)
        return m.reg_read(UC_X86_REG_EAX), calls

    def test_width_after_independent_object_relocation(self):
        for rebased in (False, True):
            self.assertEqual(self.run_adapter('가A나'.encode(), rebase=rebased)[0], 15)

    def test_draw_calls_once_per_scalar_and_ret16_contract(self):
        _, calls = self.run_adapter('가A나'.encode(), draw=True, rebase=True)
        self.assertEqual(calls, [(101, 42, 3, 4), (106, 42, 3, 4), (111, 42, 3, 4)])

    def test_original_ascii_paths_are_retained(self):
        self.assertEqual(self.run_adapter(b'AAA')[0], 123)
        self.assertEqual(self.run_adapter(b'AAA', draw=True)[1], [])

    def test_multiline_width_and_draw(self):
        self.assertEqual(self.run_adapter('가A\r\n나'.encode())[0], 10)
        self.assertEqual(self.run_adapter('가A\r\n나'.encode(), draw=True)[1],
                         [(101, 42, 3, 4), (106, 42, 3, 4), (101, 50, 3, 4)])

    def test_center_right_and_scaled_arguments(self):
        text = '가A나'.encode()
        self.assertEqual(self.run_adapter(text, draw=True, flags=1)[1][0], (94, 42, 3, 4))
        self.assertEqual(self.run_adapter(text, draw=True, flags=2)[1][0], (86, 42, 3, 4))
        self.assertEqual(self.run_adapter(text, draw=True, flags=5)[1][0], (87, 44, 6, 8))

    def test_missing_and_truncated_sequence_at_page_end(self):
        for data, expected in [('없'.encode(), 5), (b'\xea\xb0', 10), (b'\xf0\x9f\x92\xa9', 5)]:
            self.assertEqual(self.run_adapter(data)[0], expected)
            self.assertEqual(len(self.run_adapter(data, draw=True)[1]), expected // 5)

    def test_word_width_counts_scalars_and_stops_before_next_word(self):
        self.assertEqual(self.run_adapter('  가A나 나'.encode(), rebase=True, entry='token_measure')[0], 15)
        self.assertEqual(self.run_adapter('\n가'.encode(), entry='token_measure')[0], 0)

    def test_native_palette_lut_applies_to_mixed_ascii_and_korean(self):
        lut = bytearray(range(256))
        lut[17] = 146
        self.run_adapter('가A나'.encode(), draw=True, rebase=True, lut=bytes(lut))
        self.assertEqual(self.last_rendered_inks, [bytes([146]) * 12] * 3)

    def test_monochrome_uses_live_foreground_and_restores_native_font(self):
        for color in (0, 51, 81, 146, 160, 182):
            self.run_adapter('가A'.encode(), draw=True, rebase=True, mono=True,
                             foreground=color, native_backend=True)
            self.assertEqual(self.last_rendered_inks, [bytes([color]) * 12] * 2)

    def test_menu_dark_outline_and_selected_fill_do_not_change_dialogue(self):
        pixels = bytes([195, 81, 112, 116, 119, 0] * 2)
        options = bytes([111, 229, 113, 230, 121, 1]) + bytes(10)
        self.run_adapter('가A'.encode(), draw=True, rebase=True, menu_options=options, glyph_pixels=pixels)
        self.assertEqual(self.last_rendered_inks, [bytes([111, 229, 113, 230, 121, 0] * 2)] * 2)
        self.run_adapter('가A'.encode(), draw=True, rebase=True, menu_options=options,
                         glyph_pixels=pixels, native_backend=True)
        self.assertEqual(self.last_rendered_inks, [pixels] * 2)


if __name__ == '__main__':
    unittest.main()
