from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/patch'))
import urp_korean as urp


class KoreanUrpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name)
        names = ['ISLAND', 'VILE', 'GERRICKS', 'TEMPLE', 'TAVERN', 'BELLTOWR', 'HIDEINT', 'NECRISLE', 'HARBTOWR']
        self.sources = {'maps/' + n + '.RGM': ('original ' + n).encode() for n in names}
        self.sources['MENU.INI'] = '한국어 기본 메뉴'.encode()
        self.cfg = {'map_originals': {n: urp.sha(b) for n, b in self.sources.items() if n != 'MENU.INI'},
                    'menu_base_sha256': urp.sha(self.sources['MENU.INI'])}
        self.targets = {n: b + b' URP' for n, b in self.sources.items()}
        for n, b in self.sources.items():
            p = self.game / n
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b)
        (self.game / 'ENGLISH.RTX').write_bytes('이미 검수된 한국어 대사'.encode())

    def test_apply_repeat_restore_preserves_korean_archive(self):
        original_rtx = (self.game / 'ENGLISH.RTX').read_bytes()
        self.assertEqual(urp.install(self.game, self.targets, self.cfg)['changed'], 10)
        self.assertEqual(urp.install(self.game, self.targets, self.cfg)['changed'], 0)
        self.assertEqual(urp.restore(self.game, self.cfg)['restored'], 10)
        self.assertEqual(urp.restore(self.game, self.cfg)['restored'], 0)
        for name, data in self.sources.items():
            self.assertEqual((self.game / name).read_bytes(), data)
        self.assertEqual((self.game / 'ENGLISH.RTX').read_bytes(), original_rtx)

    def test_other_mod_blocks_entire_install(self):
        (self.game / 'MENU.INI').write_bytes(b'other mod')
        with self.assertRaises(ValueError):
            urp.install(self.game, self.targets, self.cfg)
        self.assertFalse(list(self.game.rglob('*.urp-ko.bak')))
        self.assertEqual((self.game / 'maps/ISLAND.RGM').read_bytes(), self.sources['maps/ISLAND.RGM'])

    def test_corrupt_backup_blocks_entire_restore(self):
        urp.install(self.game, self.targets, self.cfg)
        (self.game / ('MENU.INI' + urp.SUFFIX)).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            urp.restore(self.game, self.cfg)
        self.assertEqual((self.game / 'maps/ISLAND.RGM').read_bytes(), self.targets['maps/ISLAND.RGM'])

    def test_write_failure_rolls_back_all_applied_maps(self):
        real = urp.atomic_replace
        calls = 0

        def failing(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError('simulated disk failure')
            return real(*args)

        with patch.object(urp, 'atomic_replace', side_effect=failing):
            with self.assertRaises(OSError):
                urp.install(self.game, self.targets, self.cfg)
        for name, data in self.sources.items():
            self.assertEqual((self.game / name).read_bytes(), data)
