"""Build a UTF-8 RTX copy from local drafts; never install into the game.

The vanilla engine cannot display this file correctly. A Unicode game hook is
still required. All voice bytes are preserved and verified by rtx_tool.
"""
from pathlib import Path
import argparse
import hashlib
import json

from rtx_tool import Rtx, import_manifest

ROOT = Path(__file__).resolve().parents[2]


def build(source: Path, manifest_path: Path, drafts: Path, output: Path) -> dict:
    if source.resolve() == output.resolve():
        raise ValueError('cannot overwrite original RTX')
    if output.exists():
        raise FileExistsError('test RTX already exists; choose a new output')
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest.decode('utf-8'))
    entries = manifest['entries']
    translated, source_hashes = {}, {}
    for path in sorted(drafts.glob('rtx_*_ko.jsonl')):
        raw = path.read_bytes()
        source_hashes[path.name] = hashlib.sha256(raw).hexdigest()
        for line in raw.decode('utf-8').splitlines():
            row = json.loads(line)
            idx = row['index']
            if type(idx) is not int or not 0 <= idx < len(entries) or entries[idx]['tag'] != row['tag']:
                raise ValueError('draft source index/tag mismatch')
            if row['tag'] in translated or not isinstance(row.get('translation'), str) or not row['translation']:
                raise ValueError('duplicate or empty translation')
            if '\0' in row['translation']:
                raise ValueError('embedded NUL in translation')
            translated[row['tag']] = row['translation']
    if set(translated) != {entry['tag'] for entry in entries}:
        raise ValueError('missing or unknown translations')
    for entry in entries:
        entry['translation'] = translated[entry['tag']]
    archive = Rtx(source.read_bytes())
    result = import_manifest(archive, manifest, 'utf-8')
    checked = Rtx(result)
    for entry in checked.entries:
        if entry.text.decode('utf-8', errors='strict') != translated[entry.id]:
            raise ValueError('UTF-8 translation roundtrip mismatch')
    for name, digest in source_hashes.items():
        if hashlib.sha256((drafts / name).read_bytes()).hexdigest() != digest:
            raise ValueError('draft changed during build')
    if manifest_path.read_bytes() != raw_manifest:
        raise ValueError('canonical manifest changed during build')
    report = {'status': 'UTF-8 RTX test data; NOT playable with vanilla RG.EXE',
              'entries': len(checked.entries), 'voice_entries_preserved': sum(entry.kind == 1 for entry in checked.entries),
              'source_rtx_sha256': hashlib.sha256(archive.raw).hexdigest(),
              'output_rtx_sha256': hashlib.sha256(result).hexdigest(),
              'output_bytes': len(result), 'codec': 'utf-8',
              'source_manifest_sha256': hashlib.sha256(raw_manifest).hexdigest(),
              'draft_sha256': source_hashes}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as handle:
        handle.write(result)
    output.with_suffix('.build.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return {key: report[key] for key in ['status', 'entries', 'voice_entries_preserved', 'output_bytes']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'output/ENGLISH.urp-source.json')
    parser.add_argument('--drafts', type=Path, default=ROOT / 'output/text_translation/drafts')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/engine_utf8/test_assets/ENGLISH.RTX')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.manifest, args.drafts, args.output)))
