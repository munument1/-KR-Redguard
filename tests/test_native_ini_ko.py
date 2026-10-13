"""INI translation must preserve timing, actions, numeric placeholders and tags."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/patch'))
import native_ini_ko as native


class NativeIniTests(unittest.TestCase):
    def menu(self):
        lines = ['[page0]', 'text[0] = SAVE', 'action[0] = 1', 'text[1] = 1234567',
                 '[page3]', 'movie_name[0] = INTRO.SMK']
        lines.extend(f'movie0_text[{i}] = 0,255,255,255,{100+i},{200+i},sample,{i}'
                     for i in range(72))
        lines.append('movie1_text[0] = 0,255,255,255,1,2,keep unchanged')
        return ('\r\n'.join(lines) + '\r\n').encode('ascii')

    def test_ui_and_intro_preserve_other_values_and_all_timing_fields(self):
        raw = self.menu()
        translated, counts = native.translate_menu(raw)
        self.assertEqual(counts, {'ui': 1, 'intro': 72})
        a, b = raw.decode().splitlines(), translated.decode('utf-8').splitlines()
        self.assertEqual(len(a), len(b))
        self.assertFalse(translated.startswith(b'\xef\xbb\xbf'))
        for old, new in zip(a, b):
            if old.startswith('movie0_text['):
                self.assertEqual(old.split(',', 6)[:6], new.split(',', 6)[:6])
                self.assertTrue(any('\uac00' <= c <= '\ud7a3' for c in new))
            elif old.startswith('text[0]'):
                self.assertEqual(new, 'text[0] = 저장')
            else:
                self.assertEqual(old, new)

    def test_missing_or_duplicate_intro_rejected(self):
        with self.assertRaises(ValueError):
            native.translate_menu(self.menu().replace(b'movie0_text[71]', b'movie0_text[70]'))
        with self.assertRaises(ValueError):
            native.translate_menu(self.menu().replace(b'movie0_text[71]', b'movie1_text[71]'))

    def test_key_display_names_do_not_change_bindings(self):
        raw = b'[input]\r\ninventory_key = 23\r\n[defined]\r\nkey[128] = left mouse\r\n'
        result, count = native.translate_keys(raw)
        self.assertEqual(count, 1)
        self.assertEqual(result.decode(), '[input]\r\ninventory_key = 23\r\n[defined]\r\nkey[128] = 마우스 왼쪽\r\n')
