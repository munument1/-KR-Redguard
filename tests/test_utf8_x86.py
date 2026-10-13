"""Execute the actual prototype machine code, including unmapped boundary tests."""
import importlib.util
import json
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("utf8_x86", ROOT / "tools/encoding/utf8_x86.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EDX, UC_X86_REG_ESP,
        UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)
    AVAILABLE = importlib.util.find_spec("keystone") is not None
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, "requires local keystone-engine and unicorn")
class DecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.machine = Uc(UC_ARCH_X86, UC_MODE_32)
        cls.machine.mem_map(0x1000, 0x1000)
        cls.machine.mem_map(0x3000, 0x1000)
        cls.machine.mem_map(0x5000, 0x1000)
        cls.machine.mem_write(0x1000, runtime.assemble())

    def decode(self, data, remaining=None):
        # Place the input at the end of a mapped page. Any overread faults.
        pointer = 0x4000 - len(data)
        machine = self.machine
        if data:
            machine.mem_write(pointer, data)
        machine.mem_write(0x5FF0, struct.pack("<I", 0x1FFF))
        machine.reg_write(UC_X86_REG_ESP, 0x5FF0)
        machine.reg_write(UC_X86_REG_EAX, pointer)
        machine.reg_write(UC_X86_REG_EDX, len(data) if remaining is None else remaining)
        preserved = [UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]
        for index, register in enumerate(preserved):
            machine.reg_write(register, 0xA1230000 + index)
        machine.emu_start(0x1000, 0x1FFF, count=200)
        self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x5FF4)
        for index, register in enumerate(preserved):
            self.assertEqual(machine.reg_read(register), 0xA1230000 + index)
        return machine.reg_read(UC_X86_REG_EAX), machine.reg_read(UC_X86_REG_EDX)

    def test_unicode_boundaries(self):
        for cp in [0, 1, 0x7F, 0x80, 0x7FF, 0x800, 0xD7FF, 0xE000, 0xFFFF, 0x10000, 0x10FFFF]:
            with self.subTest(cp=cp):
                data = chr(cp).encode("utf-8")
                self.assertEqual(self.decode(data), (cp, len(data)))

    def test_every_modern_hangul_syllable(self):
        for cp in range(0xAC00, 0xD7A4):
            with self.subTest(cp=cp):
                self.assertEqual(self.decode(chr(cp).encode("utf-8")), (cp, 3))

    def test_all_single_bytes(self):
        for byte in range(256):
            self.assertEqual(self.decode(bytes([byte])), (byte, 1) if byte < 128 else (0xFFFD, 1))

    def test_bad_and_truncated_sequences(self):
        invalid = [b'\xc0\x80', b'\xc1\xbf', b'\xe0\x80\x80', b'\xf0\x80\x80\x80',
                   b'\xed\xa0\x80', b'\xed\xbf\xbf', b'\xf4\x90\x80\x80',
                   b'\xf5\x80\x80\x80', b'\xff', b'\xc2A', b'\xe1\x80A', b'\xf1\x80\x80A']
        for data in invalid:
            with self.subTest(data=data):
                self.assertEqual(self.decode(data), (0xFFFD, 1))
        for text in ['가', 'é', '\U0001F600']:
            data = text.encode('utf-8')
            for count in range(1, len(data)):
                self.assertEqual(self.decode(data[:count]), (0xFFFD, 1))
                self.assertEqual(self.decode(data, remaining=count), (0xFFFD, 1))
        self.assertEqual(self.decode(b''), (0xFFFD, 0))

    def test_current_translation_character_set(self):
        folder = ROOT / 'output/text_translation/drafts'
        paths = list(folder.glob('rtx_*_ko.jsonl'))
        if not paths:
            self.skipTest('local game translation data unavailable')
        chars = set()
        for path in paths:
            for line in path.read_text(encoding='utf-8').splitlines():
                chars.update(json.loads(line)['translation'])
        for char in chars:
            data = char.encode('utf-8')
            self.assertEqual(self.decode(data), (ord(char), len(data)))


if __name__ == '__main__':
    unittest.main()
