"""Native palette family inheritance and outlined mask geometry."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/encoding'))
from font_colors import style_lut, outlined_pack, menu_colors, menu_lut
from unicode_font import Glyph, pack, unpack


def font(border, body):
    pixels = bytes([border] * 5 + [border, body, body, body, border] * 3 + [border] * 5)
    return {'glyphs': [{'codepoint': 65, 'width': 5, 'height': 5, 'pixels': pixels}],
            'palette': bytes(range(256)) * 3}


class ColorTests(unittest.TestCase):
    def test_identical_native_shapes_preserve_exact_face_and_border_indices(self):
        lut = style_lut(font(195, 81), font(67, 133))
        self.assertEqual((lut[0], lut[195], lut[81]), (0, 67, 133))

    def test_monochrome_returns_logical_ink_without_baking_a_speaker_color(self):
        lut = style_lut(font(195, 81), font(1, 1))
        self.assertEqual(lut[0], 0)
        self.assertEqual(lut[195], 0)
        self.assertTrue(all(lut[i] == 1 for i in range(1, 256) if i != 195))

    def test_outline_preserves_advance_and_original_latin_bitmap(self):
        latin = Glyph(65, 2, 2, 0, 0, 3, b'\0\x51\xc3\0')
        korean = Glyph(0xac00, 2, 2, 1, 3, 4, bytes([195]) * 4)
        result = unpack(outlined_pack(pack([latin, korean])))
        self.assertEqual(result[0], latin)
        g = result[1]
        self.assertEqual((g.width, g.height, g.left, g.top, g.advance), (4, 4, 0, 2, 4))
        self.assertEqual(g.pixels[0], 195)
        self.assertNotEqual(g.pixels[5], 195)

    def test_menu_override_preserves_normal_palette_and_uses_nontransparent_dark_ink(self):
        ref, target = font(195, 81), font(67, 133)
        # Synthetic 6-bit palette: make index 10 exactly the target dark RGB.
        target['palette'] = bytearray([63] * 768)
        target['palette'][30:33] = bytes([3, 1, 0])
        ref['palette'] = target['palette']
        baseline = style_lut(ref, target)
        menu = menu_lut(ref, target, 'FONTNORM.FNT')
        self.assertEqual(menu[195], 10)
        self.assertEqual(menu[81], baseline[81])
        self.assertEqual(style_lut(ref, target), baseline)
        selected = menu_colors(target, 'FONTSEL.FNT')
        self.assertEqual(selected[0], 10)
        self.assertEqual(selected[1], 67)
        self.assertEqual(menu_colors(font(1, 1), 'REDONE.FNT'), bytes(16))

    def test_menu_uses_shared_palette_for_identical_font_aliases(self):
        reference, first, alias = font(195, 81), font(195, 81), font(195, 81)
        alias['palette'] = bytes(768)
        self.assertEqual(menu_lut(reference, first, 'LONORMAL.FNT'),
                         menu_lut(reference, alias, 'LOWFONT.FNT'))
