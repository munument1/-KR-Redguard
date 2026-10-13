"""Build four delta files without redistributing the game or its voice audio."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/rtx'))
from rtx_tool import Rtx
from release_patcher import reconstruct


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rtx_delta(source, target):
    original, translated = Rtx(source), Rtx(target)
    old = {entry.tag: entry for entry in original.entries}
    operations = []
    cursor = 0
    for entry in sorted(translated.entries, key=lambda e: e.offset):
        before = old[entry.tag]
        if before.trailing != entry.trailing:
            raise ValueError('Voice data changed')
        if not entry.trailing:
            continue
        offset = entry.offset + 6 + len(entry.text)
        operations.append(['literal', base64.b64encode(target[cursor:offset]).decode('ascii')])
        operations.append(['copy', before.offset + 6 + len(before.text), len(entry.trailing)])
        cursor = offset + len(entry.trailing)
    operations.append(['literal', base64.b64encode(target[cursor:]).decode('ascii')])
    return zlib.compress(json.dumps(operations, separators=(',', ':')).encode('utf-8'), 9)


def build(original, translated, output, version='0.1.1'):
    import bsdiff4
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'format': 'redguard-ko-release-v1', 'version': version,
                'edition': 'Steam Software RG.EXE', 'files': {},
                'memory_config': {'format': 'system-heap-cap-v1', 'max_heap_kbytes': 20000},
                'validation': 'User reproduced inventory OARD allocation failure at 3dlib.c:435 with heap_kbytes=22000, including an English-letter control. Full Korean release passed the harbor letter popup with heap_kbytes=20000. Other game regions are not fully play-tested.'}
    for name in ['RG.EXE', 'ENGLISH.RTX', 'MENU.INI', 'KEYS.INI']:
        source, target = (original / name).read_bytes(), (translated / name).read_bytes()
        codec = 'copy-literal-v1' if name == 'ENGLISH.RTX' else 'bsdiff4'
        payload = rtx_delta(source, target) if name == 'ENGLISH.RTX' else bsdiff4.diff(source, target)
        if reconstruct(source, payload, codec) != target:
            raise ValueError(f'{name}: delta roundtrip failed')
        filename = name + '.delta'
        (output / filename).write_bytes(payload)
        manifest['files'][name] = {'source_sha256': sha(source), 'source_size': len(source),
                                   'target_sha256': sha(target), 'target_size': len(target),
                                   'delta': filename, 'delta_sha256': sha(payload), 'codec': codec}
        print(f'{name}: delta {len(payload):,} bytes', flush=True)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--translated', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', default='0.1.1')
    args = parser.parse_args()
    build(args.original, args.translated, args.output, args.version)
