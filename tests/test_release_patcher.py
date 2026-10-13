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
