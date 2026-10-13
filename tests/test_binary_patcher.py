import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('binary_patcher', ROOT / 'tools/patch/binary_patcher.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class PatcherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / 'synthetic.exe'
        self.original = b'0123456789'
        self.target = b'01XY456789ADD'
        self.file.write_bytes(self.original)
        self.manifest = {'format': 'redguard-binary-patch-v1',
                         'source_sha256': patcher.sha(self.original),
                         'target_sha256': patcher.sha(self.target),
                         'source_size': len(self.original), 'target_size': len(self.target),
                         'game_verified': True,
                         'edits': [{'offset': 2, 'before': b'23'.hex(), 'after': b'XY'.hex()},
                                   {'offset': 10, 'before': '', 'after': b'ADD'.hex()}]}

    def test_apply_restore_and_repeated_operations(self):
        self.assertEqual(patcher.apply(self.file, self.manifest), 'patched_with_backup')
        self.assertEqual(self.file.read_bytes(), self.target)
        self.assertEqual(patcher.backup_path(self.file).read_bytes(), self.original)
        self.assertEqual(patcher.apply(self.file, self.manifest), 'already_patched')
        self.assertEqual(patcher.restore(self.file, self.manifest), 'restored_original')
        self.assertEqual(patcher.restore(self.file, self.manifest), 'already_original')

    def test_dry_run_and_unverified_release_do_not_write(self):
        self.manifest['game_verified'] = False
        self.assertEqual(patcher.apply(self.file, self.manifest, True), 'validated_without_writing')
        with self.assertRaises(patcher.PatchError):
            patcher.apply(self.file, self.manifest)
        self.assertEqual(self.file.read_bytes(), self.original)
        self.assertFalse(patcher.backup_path(self.file).exists())

    def test_unknown_original_and_incorrect_output_hash(self):
        self.file.write_bytes(b'unknown')
        with self.assertRaises(patcher.PatchError):
            patcher.apply(self.file, self.manifest)
        self.file.write_bytes(self.original)
        self.manifest['target_sha256'] = '0' * 64
        with self.assertRaises(patcher.PatchError):
            patcher.apply(self.file, self.manifest)
        self.assertFalse(patcher.backup_path(self.file).exists())

    def test_original_instruction_and_overlap_rejected(self):
        self.manifest['edits'][0]['before'] = b'ZZ'.hex()
        with self.assertRaises(patcher.PatchError):
            patcher.apply(self.file, self.manifest)
        self.manifest['edits'][0]['before'] = b'23'.hex()
        self.manifest['edits'].append({'offset': 3, 'before': '33', 'after': '34'})
        with self.assertRaises(patcher.PatchError):
            patcher.apply(self.file, self.manifest)

    def test_existing_backup_preserved(self):
        backup = patcher.backup_path(self.file)
        backup.write_bytes(b'older backup')
        with self.assertRaises(patcher.PatchError):
            patcher.apply(self.file, self.manifest)
        self.assertEqual(backup.read_bytes(), b'older backup')
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_changed_patch_and_damaged_backup_cannot_restore(self):
        patcher.apply(self.file, self.manifest)
        self.file.write_bytes(b'changed by another mod')
        with self.assertRaises(patcher.PatchError):
            patcher.restore(self.file, self.manifest)
        self.file.write_bytes(self.target)
        patcher.backup_path(self.file).write_bytes(b'damaged')
        with self.assertRaises(patcher.PatchError):
            patcher.restore(self.file, self.manifest)
        self.assertEqual(self.file.read_bytes(), self.target)

    def test_atomic_replace_failure_leaves_original_and_backup(self):
        with patch.object(patcher.os, 'replace', side_effect=OSError('simulated write failure')):
            with self.assertRaises(OSError):
                patcher.apply(self.file, self.manifest)
        self.assertEqual(self.file.read_bytes(), self.original)
        self.assertEqual(patcher.backup_path(self.file).read_bytes(), self.original)
        self.assertFalse(list(self.file.parent.glob('*.tmp')))


if __name__ == '__main__':
    unittest.main()
