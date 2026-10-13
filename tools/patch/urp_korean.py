"""Generate/install a Korean URP add-on using the user's upstream ZIP and JAR."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

from binary_patcher import atomic_replace

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rtx'))

STATE = '.redguard-urp-ko.json'
SUFFIX = '.urp-ko.bak'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def location(path):
    path = Path(path).resolve()
    return path / 'Redguard' if (path / 'Redguard/RG.EXE').is_file() else path


def config(package):
    return json.loads((package / 'urp_korean.json').read_text(encoding='utf-8'))


def originals(game, cfg):
    result = {}
    for name, digest in cfg['map_originals'].items():
        current = game / name
        backup = current.with_name(current.name + SUFFIX)
        source = backup if backup.exists() else current
        if current.is_symlink() or source.is_symlink() or not source.is_file():
            raise ValueError(f'{name}: 일반 파일이 필요합니다.')
        data = source.read_bytes()
        if sha(data) != digest:
            raise ValueError(f'{name}: 지원하는 원본 맵이 아닙니다.')
        result[name] = data
    return result


def generate(game, upstream, jar, package, java='java'):
    game = location(game)
    cfg = config(package)
    if sha(Path(upstream).read_bytes()) != cfg['urp_sha256']:
        raise ValueError('지원하는 URP 1.03 ZIP이 아닙니다.')
    if sha(Path(jar).read_bytes()) != cfg['jar_sha256']:
        raise ValueError('지원하는 Redguard Mod Manager JAR이 아닙니다.')
    for name, digest in cfg['korean_base'].items():
        if sha((game / name).read_bytes()) != digest:
            raise ValueError(f'{name}: 먼저 한국어 패치 0.1.0을 적용하세요.')
    maps = originals(game, cfg)
    menu_path = game / 'MENU.INI'
    menu_backup = menu_path.with_name(menu_path.name + SUFFIX)
    menu_data = (menu_backup if menu_backup.exists() else menu_path).read_bytes()
    if menu_backup.is_symlink() or sha(menu_data) != cfg['menu_base_sha256']:
        raise ValueError('MENU.INI: 한국어 기본 메뉴 또는 백업이 다릅니다.')
    # All 78 corrected RTX lines are already reviewed in Korean patch 0.1.0.
    # Verify them explicitly and leave the complete Korean voice archive intact.
    from rtx_tool import Rtx
    archive = Rtx((game / 'ENGLISH.RTX').read_bytes())
    lines = {entry.id: entry.text.decode('utf-8') for entry in archive.entries}
    if any(lines.get(tag) != text for tag, text in cfg['rtx_translations'].items()):
        raise ValueError('URP의 수정 대사 78건이 한국어 검수본과 다릅니다.')
    with tempfile.TemporaryDirectory(prefix='redguard-urp-ko-') as temporary:
        stage = Path(temporary) / 'source'
        output = Path(temporary) / 'generated'
        for name, data in maps.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for name, digest in cfg['support_originals'].items():
            source = game / name
            if name == 'ENGLISH.RTX':
                source = source.with_name(source.name + '.redguard-ko.bak')
            if source.is_symlink() or sha(source.read_bytes()) != digest:
                raise ValueError(f'{name}: 정식 원본/한국어 패치 백업이 필요합니다.')
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        command = [java, '-Xmx2g', '-cp', str(Path(jar).resolve()),
                   str((package / 'ExportUrp.java').resolve()), str(stage),
                   str(Path(upstream).resolve()), str(output)]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                       errors='replace', timeout=120,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except FileNotFoundError as error:
            raise ValueError('Java 24 이상이 필요합니다. java 실행 경로를 확인하세요.') from error
        if completed.returncode:
            raise ValueError('URP 맵 생성 실패:\n' + completed.stderr[-2500:])
        targets = {name: (output / name).read_bytes() for name in maps}
    import re
    text = menu_data.decode('utf-8')
    for key, translation in cfg['movie_translations'].items():
        pattern = re.compile(r'(^' + re.escape(key) + r'\s*=\s*)((?:[^,\r\n]*,){6})[^\r\n]*', re.MULTILINE)
        text, count = pattern.subn(lambda m: m[1] + m[2] + translation, text)
        if count != 1:
            raise ValueError(f'{key}: 영화 자막 키가 유일하지 않습니다.')
    targets['MENU.INI'] = text.encode('utf-8')
    return targets


def install(game, targets, cfg):
    game = location(game)
    allowed = set(cfg['map_originals']) | {'MENU.INI'}
    if set(targets) != allowed:
        raise ValueError('Incomplete generated add-on')
    source_hashes = dict(cfg['map_originals'], **{'MENU.INI': cfg['menu_base_sha256']})
    records, pending = {}, []
    for name, target in targets.items():
        path = game / name
        backup = path.with_name(path.name + SUFFIX)
        current = path.read_bytes()
        if path.is_symlink() or backup.is_symlink() or sha(current) not in {source_hashes[name], sha(target)}:
            raise ValueError(f'{name}: 다른 수정 파일은 덮어쓰지 않습니다.')
        if backup.exists() and sha(backup.read_bytes()) != source_hashes[name]:
            raise ValueError(f'{name}: 기존 백업과 충돌합니다.')
        if current != target and not backup.exists():
            pending.append((path, backup, current, target))
        elif current != target:
            pending.append((path, backup, current, target))
        elif not backup.exists():
            raise ValueError(f'{name}: 이미 수정됐지만 복원 백업이 없습니다.')
        records[name] = {'source': source_hashes[name], 'target': sha(target)}
    state = game / STATE
    if state.is_symlink():
        raise ValueError('Invalid add-on state path')
    old_state = state.read_bytes() if state.exists() else None
    for path, backup, current, target in pending:
        if not backup.exists():
            with backup.open('xb') as handle:
                handle.write(current)
        if backup.read_bytes() != current:
            raise ValueError(f'{path.name}: 백업 검증 실패')
    written = []
    try:
        for path, backup, current, target in pending:
            atomic_replace(path, target, current)
            written.append((path, current, target))
        data = json.dumps({'format': 'redguard-urp-ko-v1', 'files': records}, indent=2).encode()
        if old_state is None:
            with state.open('xb') as handle:
                handle.write(data)
        else:
            atomic_replace(state, data, old_state)
    except Exception:
        for path, current, target in reversed(written):
            atomic_replace(path, current, target)
        raise
    return {'installed_maps': 9, 'localized_rtx_verified': 78, 'localized_movie_lines': 6, 'changed': len(pending)}


def restore(game, cfg):
    game = location(game)
    state = game / STATE
    if state.is_symlink():
        raise ValueError('Invalid state path')
    data = json.loads(state.read_text(encoding='utf-8'))
    allowed = set(cfg['map_originals']) | {'MENU.INI'}
    if data.get('format') != 'redguard-urp-ko-v1' or set(data['files']) != allowed:
        raise ValueError('Invalid add-on restore state')
    expected = dict(cfg['map_originals'], **{'MENU.INI': cfg['menu_base_sha256']})
    pending = []
    for name, record in data['files'].items():
        path = game / name
        backup = path.with_name(path.name + SUFFIX)
        if path.is_symlink() or backup.is_symlink() or record['source'] != expected[name]:
            raise ValueError('Invalid restore record')
        current, original = path.read_bytes(), backup.read_bytes()
        if sha(original) != expected[name] or sha(current) not in {expected[name], record['target']}:
            raise ValueError(f'{name}: 파일/백업이 달라 복원할 수 없습니다.')
        if current != original:
            pending.append((path, current, original))
    written = []
    try:
        for path, current, original in pending:
            atomic_replace(path, original, current)
            written.append((path, current, original))
    except Exception:
        for path, current, original in reversed(written):
            atomic_replace(path, current, original)
        raise
    return {'restored': len(pending), 'korean_base_preserved': True}


def gui(package):
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.title('Unofficial Redguard Patch 한국어판 + Coyle 수정')
    root.geometry('780x340')
    tk.Label(root, text='한국어 패치 0.1.0용 별도 URP 한국어 호환판\n원본 URP 1.03 ZIP / Mod Manager JAR / Java 24 이상 필요', pady=12).pack()
    fields = {}
    for key, label in [('game', '게임 폴더'), ('zip', '원본 URP ZIP'), ('jar', 'Mod Manager JAR'), ('java', 'Java 실행 경로')]:
        row = tk.Frame(root)
        row.pack(fill='x', padx=15, pady=4)
        tk.Label(row, text=label, width=20, anchor='w').pack(side='left')
        value = tk.StringVar(value='java' if key == 'java' else '')
        fields[key] = value
        tk.Entry(row, textvariable=value).pack(side='left', fill='x', expand=True)

        def choose(k=key, v=value):
            selected = filedialog.askdirectory() if k == 'game' else filedialog.askopenfilename()
            if selected:
                v.set(selected)
        tk.Button(row, text='선택', command=choose).pack(side='right')
    tk.Label(root, text='맵 9개 + URP 수정 영상 자막 한국어 6개 적용 · 한국어 대사 78건 확인\n원본 URP 파일은 동봉하지 않습니다. 복원하면 한국어 기본 패치 상태로 돌아갑니다.', pady=10).pack()

    def execute(action):
        try:
            if not fields['game'].get():
                raise ValueError('게임 폴더를 선택하세요.')
            if action == 'restore':
                restore(fields['game'].get(), config(package))
            else:
                destination = None
                if action == 'export':
                    destination = filedialog.askdirectory(title='완성 파일을 생성할 상위 폴더')
                    if not destination:
                        return
                    destination = Path(destination) / 'URP-Korean-Coyle'
                    if destination.exists():
                        raise ValueError('출력 폴더가 이미 있습니다. 다른 폴더를 선택하세요.')
                targets = generate(fields['game'].get(), fields['zip'].get(), fields['jar'].get(), package, fields['java'].get())
                if destination:
                    for name, data in targets.items():
                        path = destination / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                else:
                    install(fields['game'].get(), targets, config(package))
            messagebox.showinfo('완료', '완료했습니다. 생성된 완성 파일은 개인 설치용입니다.' if action == 'export' else '완료했습니다.')
        except Exception as error:
            messagebox.showerror('오류', str(error))
    row = tk.Frame(root)
    row.pack()
    for label, action in [('한국어판 URP 적용', 'apply'), ('완성 파일 생성', 'export'), ('URP만 복원', 'restore')]:
        tk.Button(row, text=label, command=lambda a=action: execute(a), width=22).pack(side='left', padx=5)
    root.mainloop()


def main():
    home = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['apply', 'restore', 'export'])
    parser.add_argument('--game', type=Path)
    parser.add_argument('--urp', type=Path)
    parser.add_argument('--jar', type=Path)
    parser.add_argument('--java', default='java')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--package', type=Path, default=home / 'data')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if not args.action:
        gui(args.package)
        return
    if not args.game:
        parser.error('--game required')
    try:
        if args.action == 'restore':
            result = restore(args.game, config(args.package))
        else:
            targets = generate(args.game, args.urp, args.jar, args.package, args.java)
            if args.action == 'export':
                if args.output is None or args.output.exists():
                    raise ValueError('새 --output 폴더를 지정하세요.')
                for name, data in targets.items():
                    path = args.output / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                result = {'generated': sorted(targets)}
            else:
                result = install(args.game, targets, config(args.package))
    except Exception as error:
        parser.exit(1, str(error) + '\n')
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(output, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
