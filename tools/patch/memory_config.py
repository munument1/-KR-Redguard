"""Reversible heap cap for the Software inventory model allocation failure.

Keep the original bytes of every unrelated setting, including line endings and
legacy encodings. Restore only the heap value, so later game preferences survive.
"""
from pathlib import Path
import re

MAX_HEAP_KBYTES = 20000
BACKUP = 'SYSTEM.INI.redguard-ko-memory.bak'


def heap_setting(data):
    sections = list(re.finditer(rb'(?m)^[ \t]*\[([^\]\r\n]+)\][ \t]*\r?$', data))
    managers = [i for i, match in enumerate(sections)
                if match[1].strip().lower() == b'3dmanager']
    if len(managers) != 1:
        raise ValueError('SYSTEM.INI: [3dmanager] 설정을 하나만 찾을 수 있어야 합니다.')
    index = managers[0]
    start = sections[index].end()
    end = sections[index + 1].start() if index + 1 < len(sections) else len(data)
    matches = list(re.finditer(
        rb'(?mi)^[ \t]*heap_kbytes[ \t]*=[ \t]*([0-9]+)[ \t]*(?:;[^\r\n]*)?\r?$',
        data[start:end]))
    keys = list(re.finditer(rb'(?mi)^[ \t]*heap_kbytes[ \t]*=', data[start:end]))
    if len(matches) != 1 or len(keys) != 1:
        raise ValueError('SYSTEM.INI: heap_kbytes 숫자 설정이 없거나 중복됐습니다.')
    match = matches[0]
    value = int(match[1])
    if not 1 <= value <= 1048576:
        raise ValueError('SYSTEM.INI: 지원하지 않는 heap_kbytes 값입니다.')
    return value, start + match.start(1), start + match.end(1)


def plan(directory, action):
    path = Path(directory) / 'SYSTEM.INI'
    backup = Path(directory) / BACKUP
    if path.is_symlink() or not path.is_file() or backup.is_symlink():
        raise ValueError('SYSTEM.INI: 일반 설정 파일과 백업이 필요합니다.')
    current = path.read_bytes()
    value, start, end = heap_setting(current)
    previous = None
    if backup.exists():
        if not backup.is_file():
            raise ValueError('SYSTEM.INI: 백업 경로가 파일이 아닙니다.')
        previous = heap_setting(backup.read_bytes())[0]
    state = 'capped' if value == MAX_HEAP_KBYTES else ('lower_custom' if value < MAX_HEAP_KBYTES else 'needs_cap')
    if action == 'restore':
        # An independently changed heap is a user preference; leave it alone.
        if previous is None or value != MAX_HEAP_KBYTES or previous == value:
            return None, state
        target_value = previous
    else:
        if value <= MAX_HEAP_KBYTES:
            return None, state
        if previous is not None and previous != value:
            raise ValueError('SYSTEM.INI: 현재 메모리 설정이 기존 백업과 다릅니다.')
        target_value = MAX_HEAP_KBYTES
    target = current[:start] + str(target_value).encode('ascii') + current[end:]
    return (path, backup, current, target), state
