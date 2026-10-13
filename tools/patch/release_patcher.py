"""Standalone installer for a hash-locked four-file Korean delta package."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import sys
import zlib

from binary_patcher import atomic_replace
import memory_config

FILES = {'RG.EXE', 'ENGLISH.RTX', 'MENU.INI', 'KEYS.INI'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def reconstruct(source, payload, codec):
    if codec == 'bsdiff4':
        import bsdiff4
        return bsdiff4.patch(source, payload)
    if codec != 'copy-literal-v1':
        raise ValueError('Unknown delta format')
    result = bytearray()
    for op in json.loads(zlib.decompress(payload)):
        if op[0] == 'copy' and len(op) == 3:
            offset, length = op[1:]
            if type(offset) is not int or type(length) is not int or offset < 0 or length < 0 or offset + length > len(source):
                raise ValueError('Invalid copy range')
            result.extend(source[offset:offset + length])
        elif op[0] == 'literal' and len(op) == 2:
            result.extend(base64.b64decode(op[1], validate=True))
        else:
            raise ValueError('Invalid delta operation')
    return bytes(result)


def game_directory(path):
    path = Path(path).resolve()
    if not (path / 'RG.EXE').is_file() and (path / 'Redguard' / 'RG.EXE').is_file():
        path /= 'Redguard'
    return path


def run(action, directory, package):
    directory = game_directory(directory)
    manifest = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'redguard-ko-release-v1' or set(manifest['files']) != FILES:
        raise ValueError('Invalid release manifest')
    if action not in {'apply', 'restore', 'check', 'memory-fix'}:
        raise ValueError('Unknown action')
    memory = manifest.get('memory_config')
    if memory is not None and memory != {'format': 'system-heap-cap-v1', 'max_heap_kbytes': 20000}:
        raise ValueError('Invalid memory configuration manifest')
    if action == 'memory-fix' and memory is None:
        raise ValueError('This package does not include the inventory memory fix')
    pending = []
    states = {}
    # Validate every target, backup and reconstructed output before any writes.
    for name, record in manifest['files'].items():
        if action == 'memory-fix' and name not in {'RG.EXE', 'ENGLISH.RTX'}:
            continue
        path = directory / name
        backup = directory / (name + '.redguard-ko.bak')
        if path.is_symlink() or not path.is_file() or backup.is_symlink():
            raise ValueError(f'{name}: regular game file required')
        current = path.read_bytes()
        digest = sha(current)
        if digest not in (record['source_sha256'], record['target_sha256']):
            raise ValueError(f'{name}: 지원하지 않는 파일입니다. Steam 원본 Software 버전이 필요합니다.')
        if backup.exists() and (not backup.is_file() or sha(backup.read_bytes()) != record['source_sha256']):
            raise ValueError(f'{name}: 기존 백업이 원본과 다릅니다.')
        states[name] = 'original' if digest == record['source_sha256'] else 'patched'
        if action == 'memory-fix':
            if states[name] != 'patched':
                raise ValueError(f'{name}: 먼저 기본 한국어 패치를 적용하세요.')
            continue
        if action == 'restore':
            if states[name] == 'original':
                continue
            if not backup.exists():
                raise ValueError(f'{name}: 복원용 백업이 없습니다.')
            target = backup.read_bytes()
        else:
            if states[name] == 'patched':
                continue
            delta_name = record['delta']
            if Path(delta_name).name != delta_name:
                raise ValueError('Invalid delta filename')
            payload = (package / delta_name).read_bytes()
            if sha(payload) != record['delta_sha256']:
                raise ValueError(f'{name}: 패치 데이터 손상')
            target = reconstruct(current, payload, record['codec'])
            if sha(target) != record['target_sha256'] or len(target) != record['target_size']:
                raise ValueError(f'{name}: 패치 결과 검증 실패')
        pending.append((path, backup, current, target))
    if memory is not None:
        memory_pending, memory_state = memory_config.plan(directory, action)
        states['SYSTEM.INI'] = memory_state
        if memory_pending is not None:
            pending.append(memory_pending)
    if action == 'check':
        return {'action': action, 'states': states, 'validated': True}
    # Back up all originals first, never replace a previous backup.
    if action in {'apply', 'memory-fix'}:
        for path, backup, current, target in pending:
            if not backup.exists():
                with backup.open('xb') as handle:
                    handle.write(current)
            if path.name != 'SYSTEM.INI' and backup.read_bytes() != current:
                raise ValueError(f'{path.name}: 백업 검증 실패')
    written = []
    try:
        for path, backup, current, target in pending:
            atomic_replace(path, target, current)
            written.append((path, current, target))
    except Exception:
        for path, current, target in reversed(written):
            atomic_replace(path, current, target)
        raise
    return {'action': action, 'changed': [p.name for p, _, _, _ in pending], 'verified': True}


def gui(package):
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    version = json.loads((package / 'manifest.json').read_text(encoding='utf-8')).get('version', '')
    root.title(f'레드가드 한국어 패치 {version}')
    root.geometry('700x280')
    path = tk.StringVar()
    tk.Label(root, text='게임을 종료한 뒤 Steam Redguard 설치 폴더를 선택하세요.\nSoftware RG.EXE 전용 · 원본 자동 백업 · 복원 지원', pady=15).pack()
    row = tk.Frame(root)
    row.pack(fill='x', padx=20)
    tk.Entry(row, textvariable=path).pack(side='left', fill='x', expand=True)
    tk.Button(row, text='폴더 선택', command=lambda: path.set(filedialog.askdirectory() or path.get())).pack(side='right')
    status = tk.StringVar(value='RTX 4,866건 / 메뉴 / 도입부 번역 · 항구 아이템 화면 메모리 수정 포함\n기존 한패 또는 URP 설치자는 항구 충돌 수정만 눌러도 됩니다.')
    tk.Label(root, textvariable=status, wraplength=600, pady=15).pack()

    def execute(action):
        if not path.get():
            messagebox.showerror('폴더 선택', '게임 설치 폴더를 먼저 선택하세요.')
            return
        try:
            status.set('파일 검증 중...')
            root.update_idletasks()
            result = run(action, path.get(), package)
            status.set({'check': '검증 완료', 'apply': '한국어 패치 적용 완료', 'memory-fix': '항구 충돌 수정 적용 완료', 'restore': '원본 복원 완료'}[action])
            messagebox.showinfo('완료', status.get())
        except Exception as error:
            status.set('작업을 완료하지 못했습니다.')
            messagebox.showerror('오류', str(error))

    buttons = tk.Frame(root)
    buttons.pack()
    for label, action in [('파일 확인', 'check'), ('패치 적용', 'apply'), ('항구 충돌 수정', 'memory-fix'), ('원본 복원', 'restore')]:
        tk.Button(buttons, text=label, width=16, command=lambda a=action: execute(a)).pack(side='left', padx=5)
    root.mainloop()


def main():
    home = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['check', 'apply', 'restore', 'memory-fix'])
    parser.add_argument('directory', nargs='?', type=Path)
    parser.add_argument('--package', type=Path, default=home / 'data')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if not args.action:
        gui(args.package)
        return
    if not args.directory:
        parser.error('directory required')
    try:
        result = run(args.action, args.directory, args.package)
    except Exception as error:
        parser.exit(1, f'{error}\n')
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(output, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
