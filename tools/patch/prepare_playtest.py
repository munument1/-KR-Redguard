"""Prepare a private, standalone Steam installation copy for user play tests."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def prepare(installation, build, rtx, native_ini=None):
    installation, build, rtx = installation.resolve(), build.resolve(), rtx.resolve()
    if build.is_relative_to(installation) or installation.is_relative_to(build):
        raise ValueError('installation and output must be separate directories')
    game = installation / 'Redguard'
    source_exe, source_rtx = game / 'RG.EXE', game / 'ENGLISH.RTX'
    hashes = {'RG.EXE': sha(source_exe), 'ENGLISH.RTX': sha(source_rtx)}
    native_report = None
    if native_ini:
        native_report = json.loads((native_ini / 'native_ini_report.json').read_text(encoding='utf-8'))
        for name, digest in native_report['outputs'].items():
            if name not in ['MENU.INI', 'KEYS.INI'] or sha(native_ini / name) != digest:
                raise ValueError('native INI input mismatch')
            hashes[name] = sha(game / name)
    report = json.loads((build / 'build_report.json').read_text(encoding='utf-8'))
    if hashes['RG.EXE'] != report['source_sha256'] or sha(build / 'RG.EXE') != report['output_sha256']:
        raise ValueError('installation or experimental executable mismatch')
    rtx_report = json.loads(rtx.with_suffix('.build.json').read_text(encoding='utf-8'))
    if sha(rtx) != rtx_report['output_rtx_sha256']:
        raise ValueError('test RTX mismatch')
    target = build / 'game'
    if target.exists():
        raise ValueError('playtest installation copy already exists')
    print('Copying private Steam installation...', flush=True)
    shutil.copytree(installation, target)
    copied_game = target / 'Redguard'
    for name, digest in hashes.items():
        if sha(copied_game / name) != digest:
            raise ValueError('installation copy mismatch')
    shutil.copy2(build / 'RG.EXE', copied_game / 'RG.EXE')
    shutil.copy2(rtx, copied_game / 'ENGLISH.RTX')
    if native_report:
        for name in native_report['outputs']:
            shutil.copy2(native_ini / name, copied_game / name)
    # Source config already starts the Software executable, rg, through DOSBox.
    launcher = ('@echo off\r\npushd "%~dp0game\\DOSBox-0.73"\r\n'
                'dosbox.exe -noconsole -conf rg.conf\r\npopd\r\n')
    (build / 'Play Korean Test.cmd').write_bytes(launcher.encode('ascii'))
    # Preserve the original EXE/RTX pair for restoring this private copy.
    backup = build / 'original_files'
    backup.mkdir()
    for name in hashes:
        shutil.copy2(game / name, backup / name)
    for name, digest in hashes.items():
        if sha(game / name) != digest:
            raise ValueError('original installation changed during preparation')
    record = {'installation_source': str(installation), 'copied_installation': str(target),
              'original_hashes': hashes, 'test_exe_sha256': sha(copied_game / 'RG.EXE'),
              'test_rtx_sha256': sha(copied_game / 'ENGLISH.RTX'),
              'native_ini': native_report,
              'launcher': str(build / 'Play Korean Test.cmd'), 'original_installation_unchanged': True}
    (build / 'playtest_manifest.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--rtx', type=Path, required=True)
    parser.add_argument('--native-ini', type=Path)
    args = parser.parse_args()
    prepare(args.installation, args.build, args.rtx, args.native_ini)
