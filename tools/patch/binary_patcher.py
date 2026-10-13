"""Hash-locked, reversible single-file patcher for a future Redguard release.

No executable bytes or game patches are bundled here. A release manifest must
be produced and game-tested separately. Only data edits are supported, never
commands or executable Python from a manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


class PatchError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_manifest(manifest: dict) -> list[tuple[int, bytes, bytes]]:
    if not isinstance(manifest, dict) or manifest.get('format') != 'redguard-binary-patch-v1':
        raise PatchError('unsupported manifest')
    for key in ['source_sha256', 'target_sha256']:
        value = manifest.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise PatchError(f'invalid {key}')
    for key in ['source_size', 'target_size']:
        if type(manifest.get(key)) is not int or not 0 < manifest[key] <= 64 * 1024 * 1024:
            raise PatchError(f'invalid {key}')
    if manifest['target_size'] < manifest['source_size']:
        raise PatchError('shrinking a file is unsupported')
    records = manifest.get('edits')
    if not isinstance(records, list) or not records:
        raise PatchError('missing edits')
    edits = []
    for record in records:
        if not isinstance(record, dict) or type(record.get('offset')) is not int:
            raise PatchError('invalid edit offset')
        try:
            old = bytes.fromhex(record['before'])
            new = bytes.fromhex(record['after'])
        except (KeyError, TypeError, ValueError) as error:
            raise PatchError('invalid hex edit') from error
        offset = record['offset']
        if not new or offset < 0:
            raise PatchError('invalid edit range')
        if offset == manifest['source_size'] and not old:
            if offset + len(new) != manifest['target_size']:
                raise PatchError('append must produce declared target size')
        elif len(old) != len(new) or offset + len(old) > manifest['source_size']:
            raise PatchError('edits must replace equal-length bytes or append at EOF')
        edits.append((offset, old, new))
    edits.sort(key=lambda row: row[0])
    for first, second in zip(edits, edits[1:]):
        if first[0] + len(first[2]) > second[0]:
            raise PatchError('overlapping edits')
    return edits


def build_target(source: bytes, manifest: dict) -> bytes:
    edits = validate_manifest(manifest)
    if len(source) != manifest['source_size'] or sha(source) != manifest['source_sha256']:
        raise PatchError('unsupported original file; size/SHA256 mismatch')
    result = bytearray(source)
    for offset, old, new in edits:
        if source[offset:offset + len(old)] != old:
            raise PatchError(f'original instruction bytes mismatch at {offset:#x}')
        result[offset:offset + len(old)] = new
    target = bytes(result)
    if len(target) != manifest['target_size'] or sha(target) != manifest['target_sha256']:
        raise PatchError('patch output hash/size mismatch')
    return target


def checked_path(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise PatchError('target must be an existing regular file, not a symlink')
    return path


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + '.redguard-ko.bak')


def atomic_replace(path: Path, data: bytes, expected_current: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        if path.is_symlink() or path.read_bytes() != expected_current:
            raise PatchError('target changed while preparing patch; aborted')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(path: Path, manifest: dict, dry_run: bool = False) -> str:
    validate_manifest(manifest)
    checked_path(path)
    source = path.read_bytes()
    if sha(source) == manifest['target_sha256'] and len(source) == manifest['target_size']:
        return 'already_patched'
    target = build_target(source, manifest)
    if dry_run:
        return 'validated_without_writing'
    if manifest.get('game_verified') is not True:
        raise PatchError('release blocked: manifest is not marked game-verified')
    backup = backup_path(path)
    if backup.exists() or backup.is_symlink():
        if backup.is_symlink() or backup.read_bytes() != source:
            raise PatchError('existing backup differs; refusing to overwrite')
    else:
        # Exclusive creation prevents overwriting an older backup.
        with backup.open('xb') as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
    if backup.read_bytes() != source:
        raise PatchError('backup verification failed')
    atomic_replace(path, target, source)
    return 'patched_with_backup'


def restore(path: Path, manifest: dict) -> str:
    validate_manifest(manifest)
    checked_path(path)
    current = path.read_bytes()
    if len(current) == manifest['source_size'] and sha(current) == manifest['source_sha256']:
        return 'already_original'
    if len(current) != manifest['target_size'] or sha(current) != manifest['target_sha256']:
        raise PatchError('current file differs from expected patch; refusing restore')
    backup = checked_path(backup_path(path)).read_bytes()
    if len(backup) != manifest['source_size'] or sha(backup) != manifest['source_sha256']:
        raise PatchError('backup hash/size mismatch')
    atomic_replace(path, backup, current)
    return 'restored_original'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'apply', 'restore'])
    parser.add_argument('file', type=Path)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        result = restore(args.file, manifest) if args.action == 'restore' else apply(args.file, manifest, args.action == 'check')
    except (PatchError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f'Patch failed: {error}\n')
    print(result)


if __name__ == '__main__':
    main()
