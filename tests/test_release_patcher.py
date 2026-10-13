from pathlib import Path
import base64
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/patch'))
import release_patcher as installer


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name) / 'Redguard'
        self.package = Path(self.temp.name) / 'data'
        self.game.mkdir()
        self.package.mkdir()
        self.files = {}
        for name in sorted(installer.FILES):
            source = ('original ' + name).encode()
            target = source + b' Korean'
            delta = zlib.compress(json.dumps([['copy', 0, len(source)], ['literal', base64.b64encode(b' Korean').decode()]]).encode())
            (self.game / name).write_bytes(source)
            (self.package / (name + '.delta')).write_bytes(delta)
            self.files[name] = dict(source_sha256=installer.sha(source), target_sha256=installer.sha(target),
                                    source_size=len(source), target_size=len(target),
                                    delta=name + '.delta', delta_sha256=installer.sha(delta), codec='copy-literal-v1')
        (self.package / 'manifest.json').write_text(json.dumps(dict(format='redguard-ko-release-v1', files=self.files)))

    def test_check_apply_repeat_restore_parent_directory(self):
        installer.run('check', self.game.parent, self.package)
        self.assertFalse(list(self.game.glob('*.bak')))
        installer.run('apply', self.game.parent, self.package)
        self.assertEqual(installer.run('apply', self.game, self.package)['changed'], [])
        for name in self.files:
            self.assertEqual(installer.sha((self.game / name).read_bytes()), self.files[name]['target_sha256'])
        installer.run('restore', self.game, self.package)
        self.assertEqual(installer.run('restore', self.game, self.package)['changed'], [])
        for name in self.files:
            self.assertEqual(installer.sha((self.game / name).read_bytes()), self.files[name]['source_sha256'])

    def test_unknown_last_file_prevents_all_writes(self):
        (self.game / 'RG.EXE').write_bytes(b'other mod')
        with self.assertRaises(ValueError):
            installer.run('apply', self.game, self.package)
        self.assertFalse(list(self.game.glob('*.bak')))
        self.assertEqual((self.game / 'ENGLISH.RTX').read_bytes(), b'original ENGLISH.RTX')

    def test_corrupt_delta_or_backup_prevents_all_writes(self):
        delta = self.package / 'RG.EXE.delta'
        original = delta.read_bytes()
        delta.write_bytes(b'broken')
        with self.assertRaises(ValueError):
            installer.run('apply', self.game, self.package)
        self.assertFalse(list(self.game.glob('*.bak')))
        delta.write_bytes(original)
        (self.game / 'RG.EXE.redguard-ko.bak').write_bytes(b'precious old backup')
        with self.assertRaises(ValueError):
            installer.run('apply', self.game, self.package)
        self.assertEqual((self.game / 'RG.EXE.redguard-ko.bak').read_bytes(), b'precious old backup')

    def test_write_failure_rolls_back_previous_files(self):
        real = installer.atomic_replace
        count = 0

        def failing(*args):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('simulated disk error')
            return real(*args)

        with patch.object(installer, 'atomic_replace', side_effect=failing):
            with self.assertRaises(OSError):
                installer.run('apply', self.game, self.package)
        for name in self.files:
            self.assertEqual(installer.sha((self.game / name).read_bytes()), self.files[name]['source_sha256'])

    def enable_memory_fix(self, heap=22000):
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest['memory_config'] = {'format': 'system-heap-cap-v1', 'max_heap_kbytes': 20000}
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        config = (b'; legacy byte \x82\r\n[screen]\r\nresolution=1\r\n'
                  b'[3dmanager]\r\nheap_kbytes = ' + str(heap).encode() +
                  b' ; reserved heap\r\ntexture_kbytes=12000\r\n'
                  b'[sound]\r\nvolume=173\r\nheap_kbytes=999\r\n')
        (self.game / 'SYSTEM.INI').write_bytes(config)
        return config

    def test_memory_cap_preserves_settings_and_restores_only_heap(self):
        original = self.enable_memory_fix()
        installer.run('check', self.game, self.package)
        self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), original)
        installer.run('apply', self.game, self.package)
        capped = original.replace(b'heap_kbytes = 22000', b'heap_kbytes = 20000')
        self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), capped)
        backup = self.game / installer.memory_config.BACKUP
        self.assertEqual(backup.read_bytes(), original)
        # The player changes audio after installing the Korean patch.
        (self.game / 'SYSTEM.INI').write_bytes(capped.replace(b'volume=173', b'volume=80'))
        self.assertEqual(installer.run('apply', self.game, self.package)['changed'], [])
        installer.run('restore', self.game, self.package)
        self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), original.replace(b'volume=173', b'volume=80'))
        self.assertEqual(installer.run('restore', self.game, self.package)['changed'], [])

    def test_memory_only_upgrade_preserves_urp_menu_controls_and_other_files(self):
        # Install old 0.1.0 first, then simulate URP and customized controls.
        installer.run('apply', self.game, self.package)
        original = self.enable_memory_fix()
        (self.game / 'MENU.INI').write_bytes(b'URP Korean menu')
        (self.game / 'KEYS.INI').write_bytes(b'custom controls')
        result = installer.run('memory-fix', self.game, self.package)
        self.assertEqual(result['changed'], ['SYSTEM.INI'])
        self.assertEqual((self.game / 'MENU.INI').read_bytes(), b'URP Korean menu')
        self.assertEqual((self.game / 'KEYS.INI').read_bytes(), b'custom controls')
        self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), original.replace(b'22000', b'20000'))
        self.assertEqual(installer.run('memory-fix', self.game, self.package)['changed'], [])

    def test_memory_only_fix_requires_the_korean_engine_and_archive(self):
        original = self.enable_memory_fix()
        with self.assertRaises(ValueError):
            installer.run('memory-fix', self.game, self.package)
        self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), original)
        self.assertFalse(list(self.game.glob('*.bak')))

    def test_lower_or_already_capped_custom_heap_is_preserved(self):
        for heap in (15000, 20000):
            with self.subTest(heap=heap):
                config = self.enable_memory_fix(heap)
                installer.run('apply', self.game, self.package)
                self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), config)
                self.assertFalse((self.game / installer.memory_config.BACKUP).exists())
                installer.run('restore', self.game, self.package)
                self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), config)

    def test_bad_memory_config_prevents_all_game_writes(self):
        original = self.enable_memory_fix()
        path = self.game / 'SYSTEM.INI'
        for bad in (original.replace(b'22000', b'bad'),
                    original.replace(b'texture_kbytes=12000', b'heap_kbytes=21000')):
            with self.subTest(config=bad):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    installer.run('apply', self.game, self.package)
                self.assertFalse(list(self.game.glob('*.bak')))
                for name in self.files:
                    self.assertEqual(installer.sha((self.game / name).read_bytes()), self.files[name]['source_sha256'])

    def test_memory_write_failure_rolls_back_all_four_core_files(self):
        original = self.enable_memory_fix()
        real = installer.atomic_replace

        def failing(path, *args):
            if path.name == 'SYSTEM.INI':
                raise OSError('simulated SYSTEM.INI write failure')
            return real(path, *args)

        with patch.object(installer, 'atomic_replace', side_effect=failing):
            with self.assertRaises(OSError):
                installer.run('apply', self.game, self.package)
        self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), original)
        for name in self.files:
            self.assertEqual(installer.sha((self.game / name).read_bytes()), self.files[name]['source_sha256'])

    def test_restore_keeps_a_later_custom_heap(self):
        original = self.enable_memory_fix()
        installer.run('apply', self.game, self.package)
        custom = original.replace(b'22000', b'15000')
        (self.game / 'SYSTEM.INI').write_bytes(custom)
        installer.run('restore', self.game, self.package)
        self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), custom)

    def test_conflicting_memory_backup_prevents_all_writes(self):
        original = self.enable_memory_fix()
        (self.game / installer.memory_config.BACKUP).write_bytes(original.replace(b'22000', b'21000'))
        with self.assertRaises(ValueError):
            installer.run('apply', self.game, self.package)
        self.assertEqual((self.game / 'SYSTEM.INI').read_bytes(), original)
        self.assertEqual((self.game / 'RG.EXE').read_bytes(), b'original RG.EXE')
