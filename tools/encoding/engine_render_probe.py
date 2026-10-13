"""Isolated execution of the original Software RG.EXE bitmap renderer.

Loads preferred LE object addresses and internal offset fixups into Unicorn.
Not a DOS loader or a patched playable executable. Selector fixups are recorded
but not applied: only flat-address isolated drawing routines are exercised.
The Python harness initializes the framebuffer and row-code scratch buffer.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import runpy

from unicode_layout_x86 import ROOT
from unicode_font import unpack


def probe(exe: Path, pack_path: Path, output: Path, check_loader: bool = False,
          check_text_hooks: bool = False, check_general_text: bool = False,
          color_font_dir: Path | None = None, color_text: str = '가나다') -> dict:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_MEM_INVALID, UC_HOOK_CODE
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_EDX, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EDI)
    from PIL import Image

    raw = exe.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if check_text_hooks:
        report = json.loads((exe.parent / 'build_report.json').read_text(encoding='utf-8'))
        if report['output_sha256'] != digest or report['embedded_font_sha256'] != hashlib.sha256(pack_path.read_bytes()).hexdigest():
            raise ValueError('patched EXE or font does not match build report')
        if check_loader:
            raise ValueError('font loader probe requires original installation font path')
    elif digest != '43450fb0fa82091fe4e4e9ad73e16fc35586c1091a25f11cec07d18078255097':
        raise ValueError('unsupported RG.EXE version')
    header = struct.unpack_from('<I', raw, 60)[0]
    u32 = lambda pos: struct.unpack_from('<I', raw, header + pos)[0]
    if raw[header:header + 4] != b'LE\0\0' or u32(0x28) != 4096:
        raise ValueError('unexpected executable format')
    objects = [struct.unpack_from('<6I', raw, header + u32(0x40) + idx * 24) for idx in range(u32(0x44))]
    pages = u32(0x14)
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    def unmapped(cpu, access, address, size, value, user):
        raise ValueError(f'unmapped access at EIP={cpu.reg_read(UC_X86_REG_EIP):#x}: address={address:#x} size={size}')
    machine.hook_add(UC_HOOK_MEM_INVALID, unmapped)
    page_addresses = {}
    for size, base, flags, first, count, _ in objects:
        machine.mem_map(base, (size + 4095) // 4096 * 4096)
        for idx in range(count):
            logical = first - 1 + idx
            page_addresses[logical] = base + idx * 4096
            at = header + u32(0x48) + logical * 4
            physical = int.from_bytes(raw[at:at + 3], 'big')
            if raw[at + 3] != 0 or not 1 <= physical <= pages:
                raise ValueError('unsupported page mapping')
            length = u32(0x2C) if physical == pages else 4096
            source = u32(0x80) + (physical - 1) * 4096
            if source + length > len(raw):
                raise ValueError('page beyond file')
            machine.mem_write(base + idx * 4096, raw[source:source + length])
    fixup_table = struct.unpack_from('<' + str(pages + 1) + 'I', raw, header + u32(0x68))
    fixup_base = header + u32(0x6C)
    fixes, selector_skips, targets = 0, 0, {}
    outside_object_offsets = []
    for page in range(pages):
        at, end = fixup_base + fixup_table[page], fixup_base + fixup_table[page + 1]
        while at < end:
            source_type, flags, displacement, obj = struct.unpack_from('<BBhB', raw, at)
            at += 5
            if source_type not in (2, 7, 8) or flags not in (0, 16) or not 1 <= obj <= len(objects):
                raise ValueError('unsupported internal fixup')
            if source_type == 2:
                selector_skips += 1
                continue
            width = 4 if flags & 16 else 2
            offset = int.from_bytes(raw[at:at + width], 'little')
            at += width
            if offset >= objects[obj - 1][0]:
                # An encoded offset is relocation arithmetic, not a buffer
                # access. Preserve 32-bit arithmetic; do not silently omit it.
                outside_object_offsets.append({'page':page, 'object':obj, 'offset':hex(offset)})
            source = page_addresses[page] + displacement
            target = (objects[obj - 1][1] + offset) & 0xFFFFFFFF
            value = target if source_type == 7 else target - source - 4
            machine.mem_write(source, struct.pack('<I', value & 0xFFFFFFFF))
            targets[source] = target
            fixes += 1
        if at != end:
            raise ValueError('fixup extent mismatch')

    # Locate data object from the actual relocated operand of mov esi,[width].
    width_address = struct.unpack('<I', machine.mem_read(0x9F0D2, 4))[0]
    data_base = width_address - 0x91A8
    if data_base not in [row[1] for row in objects]:
        raise ValueError('renderer data relocation mismatch')
    # Initialized data and BSS live in DIFFERENT LE objects. Resolve each global
    # through its own code fixup, rather than adding one guessed DS base.
    globals_by_offset = {}
    for source, target in targets.items():
        if 0x9F0B8 <= source < 0x9F500:
            old = struct.unpack_from('<I', raw, u32(0x80) + source - 0x10000)[0]
            globals_by_offset.setdefault(old, set()).add(target)
    def global_address(offset):
        candidates = globals_by_offset.get(offset, set())
        if len(candidates) != 1:
            raise ValueError(f'global {offset:#x} does not resolve uniquely')
        return next(iter(candidates))
    write32 = lambda offset, value: machine.mem_write(global_address(offset), struct.pack('<I', value))
    framebuffer, scratch, bitmap, stack = 0x600000, 0x650000, 0x670000, 0x69F000
    machine.mem_map(framebuffer, 0x50000)
    machine.mem_map(scratch, 0x10000)
    machine.mem_map(bitmap, 0x10000)
    machine.mem_map(0x690000, 0x10000)
    machine.mem_map(0x6B0000, 0x1000)  # Return sentinel.
    loader_result = None
    if check_loader:
        font_path = exe.parent / 'fonts/REDSEL.FNT'
        font_bytes = font_path.read_bytes()
        expected_font = runpy.run_path(str(ROOT / 'tools/fnt/fnt_tool.py'))['read_font'](font_bytes)
        machine.mem_map(0x800000, 0x200000)
        state = {'position': 0, 'heap': 0x800000, 'reads': 0, 'allocations': 0}
        helper_calls = {}

        def find_chunk(tag):
            pos = 0
            while pos + 8 <= len(font_bytes):
                name, size = struct.unpack_from('>4sI', font_bytes, pos)
                if name == tag:
                    return pos + 8, size
                pos += 8 + size
            return None

        def read_bytes(size):
            start = state['position']
            data = font_bytes[start:start + size]
            if len(data) != size:
                raise ValueError('original font loader requested past file end')
            state['position'] += size
            state['reads'] += 1
            return data

        def helper(cpu, address, size, user):
            eax, edx, ebx = [cpu.reg_read(reg) for reg in [UC_X86_REG_EAX, UC_X86_REG_EDX, UC_X86_REG_EBX]]
            helper_calls[hex(address)] = helper_calls.get(hex(address), 0) + 1
            result = 0
            if address == 0xB4114:  # File open, bridged to local immutable bytes.
                state['position'] = 0
                result = 0x77
            elif address == 0xB2C44:  # Locate requested chunk payload.
                found = find_chunk(bytes(cpu.mem_read(eax, 4)))
                if found:
                    state['position'] = found[0]
                    result = 1
            elif address == 0xB2D40:  # Read named palette chunk.
                found = find_chunk(bytes(cpu.mem_read(eax, 4)))
                if found:
                    state['position'] = found[0]
                    cpu.mem_write(edx, read_bytes(found[1]))
                    result = 1
            elif address == 0xB2E2C:
                result = int.from_bytes(read_bytes(2), 'little')
            elif address == 0xB2F0C:
                cpu.mem_write(eax, read_bytes(edx))
                result = edx
            elif address == 0xB1BBC:
                result = state['heap']
                state['heap'] += (max(eax, 1) + 15) & ~15
                if state['heap'] > 0xA00000:
                    raise ValueError('font loader exceeded heap probe limit')
                state['allocations'] += 1
            elif address == 0xB4A37:
                cpu.mem_write(eax, bytes([edx & 255]) * ebx)
                result = eax
            elif address == 0xB6138:
                cpu.mem_write(eax, bytes(cpu.mem_read(edx, ebx)))
                result = eax
            # Remaining hooks are debug output, close and free; no host I/O.
            esp = cpu.reg_read(UC_X86_REG_ESP)
            return_address = struct.unpack('<I', cpu.mem_read(esp, 4))[0]
            cpu.reg_write(UC_X86_REG_EAX, result)
            cpu.reg_write(UC_X86_REG_ESP, esp + 4)
            cpu.reg_write(UC_X86_REG_EIP, return_address)

        hooks = [machine.hook_add(UC_HOOK_CODE, helper, begin=address, end=address)
                 for address in [0x6356F, 0xB4114, 0xB2C44, 0xB2D40, 0xB2E2C,
                                 0xB2F0C, 0xB1BBC, 0xB4A37, 0xB6138, 0xB4268, 0xB1C92]]
        machine.mem_write(bitmap, b'FONTS\\REDSEL.FNT\0')
        machine.mem_write(stack, struct.pack('<I', 0x6B0000))
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.reg_write(UC_X86_REG_EAX, bitmap)
        machine.emu_start(0xA731B, 0x6B0000, count=1000000)
        if machine.reg_read(UC_X86_REG_EIP) != 0x6B0000 or machine.reg_read(UC_X86_REG_ESP) != stack + 4:
            raise ValueError('original font loader did not return normally')
        loaded = machine.reg_read(UC_X86_REG_EAX)
        if loaded < 0x800000 or loaded + 0xE50 > state['heap']:
            raise ValueError('invalid original font loader result')
        count = struct.unpack('<H', machine.mem_read(loaded + 0x44, 2))[0]
        if count != expected_font['count']:
            raise ValueError('font count differs after original loader')
        for idx, glyph in enumerate(expected_font['glyphs']):
            for offset, key in [(0x50, 'enabled'), (0x250, 'width'), (0x450, 'height')]:
                if struct.unpack('<H', machine.mem_read(loaded + offset + idx * 2, 2))[0] != glyph[key]:
                    raise ValueError('original font metric mismatch')
            address = struct.unpack('<I', machine.mem_read(loaded + 0xA50 + idx * 4, 4))[0]
            if glyph['pixels'] and bytes(machine.mem_read(address, len(glyph['pixels']))) != glyph['pixels']:
                raise ValueError('original font bitmap mismatch')
        for handle in hooks:
            machine.hook_del(handle)
        loader_result = {'status':'original loader executed; file/heap helpers supplied by harness',
                         'glyphs_verified':count, 'allocations':state['allocations'],
                         'file_reads':state['reads'], 'helper_calls':helper_calls}
    write32(0x91A8, 640)
    write32(0x91B0, 640 * 480)  # Framebuffer byte extent used by generated end check.
    write32(0x91B8, 0)
    write32(0x91BC, 0)
    write32(0x91C0, 639)
    write32(0x91C4, 479)
    write32(0x13BD, framebuffer)
    write32(0x38FC7, scratch)
    write32(0x3ACD8, 0x9F2CA)  # Original unscaled row-code generator, normally set at startup.
    write32(0x3E08, 0)  # Disable optional shadow transform in isolated probe.
    for y in range(480):
        machine.mem_write(global_address(0x91C8) + y * 4, struct.pack('<I', y * 640))
    callback = struct.unpack('<I', machine.mem_read(global_address(0x3ACD8), 4))[0]
    if callback != 0x9F2CA:
        raise ValueError(f'unexpected row generator {callback:#x}')
    glyphs = {glyph.scalar: glyph for glyph in unpack(pack_path.read_bytes())}
    lines = ['사이러스: 리히튼 총독을 만나야겠어.', '훈딩 만에서 이자라의 행방을 찾아야 해.']
    if check_general_text:
        lines.append('사이러스')
    calls = 0
    native_calls = 0
    hook_widths = []
    format_calls = 0
    if check_general_text:
        if not check_text_hooks:
            raise ValueError('general text check requires patched text hooks')
        # Use the REAL original cdecl wrappers and real original prologue /
        # epilogue. Only the C library formatter/heap helpers are supplied.
        machine.mem_write(targets[0x18614], struct.pack('<I', bitmap + 0x8000))
        machine.mem_write(targets[0x1861C], struct.pack('<I', bitmap + 0xC000))
        for operand in (0x18625, 0x18632, 0x1864C):
            machine.mem_write(targets[operand], struct.pack('<I', 0))
        for address, value in [(0x120308, 640), (0x12030C, 480), (0x123E14, 0),
                               (0x123E18, 0), (0x123E06, 0)]:
            machine.mem_write(address, struct.pack('<I', value))
        for row in range(480):
            machine.mem_write(0x120354 + row * 4, struct.pack('<I', row * 640))
        def native_glyph_call(cpu, address, size, user):
            nonlocal native_calls
            native_calls += 1
        machine.hook_add(UC_HOOK_CODE, native_glyph_call, begin=0x34483B, end=0x34483B)

        def cstring(address):
            data = bytearray()
            for i in range(1024):
                value = bytes(machine.mem_read(address + i, 1))
                if value == b'\0':
                    return bytes(data)
                data.extend(value)
            raise ValueError('probe format exceeds original buffer')

        def library(cpu, address, size, user):
            nonlocal format_calls
            eax = cpu.reg_read(UC_X86_REG_EAX)
            edx = cpu.reg_read(UC_X86_REG_EDX)
            ebx = cpu.reg_read(UC_X86_REG_EBX)
            result = 0
            if address == 0xB6189:
                fmt = cstring(edx)
                if fmt != b'%s':
                    raise ValueError('probe expects original %s varargs formatting')
                va_list = struct.unpack('<I', cpu.mem_read(ebx, 4))[0]
                pointer = struct.unpack('<I', cpu.mem_read(va_list, 4))[0]
                text = cstring(pointer)
                cpu.mem_write(eax, text + b'\0')
                result = len(text)
                format_calls += 1
            elif address == 0xB1BBC:
                if eax > 1024:
                    raise ValueError('unexpected probe allocation')
                result = bitmap + 0x9000
            elif address == 0xB4A37:
                cpu.mem_write(eax, bytes([edx & 255]) * ebx)
                result = eax
            esp = cpu.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack('<I', cpu.mem_read(esp, 4))[0]
            cpu.reg_write(UC_X86_REG_EAX, result)
            cpu.reg_write(UC_X86_REG_ESP, esp + 4)
            cpu.reg_write(UC_X86_REG_EIP, ret)
        for address in [0xB6189, 0xB1BBC, 0xB1C92, 0xB4A37]:
            machine.hook_add(UC_HOOK_CODE, library, begin=address, end=address)
    if check_text_hooks:
        def before_blit(cpu, address, size, user):
            nonlocal calls
            calls += 1
            machine.ctl_remove_cache(scratch, scratch + 0x10000)
            machine.ctl_remove_cache(0x9F0B8, 0x9F419)
        machine.hook_add(UC_HOOK_CODE, before_blit, begin=0x9F0B8, end=0x9F0B8)
    color_checks = []
    if color_font_dir:
        if not check_general_text:
            raise ValueError('color probe requires original general text state')
        from font_colors import style_lut, native_style, menu_lut
        from PIL import ImageDraw, ImageFont
        read = runpy.run_path(str(ROOT / 'tools/fnt/fnt_tool.py'))['read_font']
        reference = read((color_font_dir / 'REDSEL.FNT').read_bytes())
        pal = json.loads((pack_path.parent / 'palette.json').read_text())
        palette = [min(value * 4, 255) for value in pal]
        color_names = [('red', (255, 0, 0)), ('green', (0, 255, 0)), ('blue', (0, 0, 255)),
                       ('yellow', (255, 255, 0)), ('white', (255, 255, 255)), ('black', (0, 0, 0))]
        foregrounds = [(name, min(range(256), key=lambda i: sum((palette[i * 3 + j] - rgb[j]) ** 2 for j in range(3))))
                       for name, rgb in color_names]
        views = []
        for font_path in sorted(color_font_dir.glob('*.FNT')):
            native = read(font_path.read_bytes())
            sample, _, _, _, mono = native_style(native)
            lut = style_lut(reference, native)
            choices = foregrounds if mono else [('native', 81), ('menu', 81)]
            for color_name, foreground in choices:
                case_lut = menu_lut(reference, native, font_path.name) if color_name == 'menu' else lut
                font_ptr = bitmap + 0xC000
                font_data = bytearray(0xE50)
                font_data[0] = 1
                font_data[0x14:0x34] = native['raw_chunks'][b'FNHD'][:32]
                struct.pack_into('<HH', font_data, 0x42, native['start'], native['count'])
                idx = 65 - native['start']
                for off, value in [(0x50, 1), (0x250, sample['width']), (0x450, sample['height'])]:
                    struct.pack_into('<H', font_data, off + idx * 2, value)
                struct.pack_into('<I', font_data, 0xA50 + idx * 4, bitmap + 0xF000)
                machine.mem_write(font_ptr, bytes(font_data))
                machine.mem_write(bitmap + 0xF000, sample['pixels'])
                machine.mem_write(0x123E00, struct.pack('<I', font_ptr))
                machine.mem_write(0x123E04, bytes([foreground]))
                # Nonblack background makes opaque black foreground testable.
                background_rgb = (215, 185, 135) if color_name == 'menu' else (32, 32, 32)
                background = min(range(1, 256), key=lambda i: sum((palette[i * 3 + j] - background_rgb[j]) ** 2 for j in range(3)))
                machine.mem_write(framebuffer, bytes([background]) * (640 * 480))
                text = color_text
                machine.mem_write(bitmap, text.encode('utf-8') + b'\0')
                machine.mem_write(stack, struct.pack('<I', 0x6B0000))
                machine.reg_write(UC_X86_REG_ESP, stack)
                machine.reg_write(UC_X86_REG_EAX, 30)
                machine.reg_write(UC_X86_REG_EDX, 40)
                machine.reg_write(UC_X86_REG_EBX, 0 if color_name == 'menu' else 0x100)
                machine.reg_write(UC_X86_REG_ECX, bitmap)
                machine.emu_start(0x76E98, 0x6B0000, count=3000000)
                if machine.reg_read(UC_X86_REG_EIP) != 0x6B0000 or machine.reg_read(UC_X86_REG_ESP) != stack + 4:
                    raise ValueError('native color backend did not return')
                if struct.unpack('<I', machine.mem_read(0x123E00, 4))[0] != font_ptr:
                    raise ValueError('native current font was not restored')
                expected = bytearray([background] * (640 * 480))
                x = 30
                for char in text:
                    glyph = glyphs[ord(char)]
                    for gy in range(glyph.height):
                        for gx in range(glyph.width):
                            value = glyph.pixels[gy * glyph.width + gx]
                            if value:
                                if mono and value == 195:
                                    continue
                                ink = foreground if mono else case_lut[value]
                                expected[(40 + glyph.top + gy) * 640 + x + glyph.left + gx] = ink
                    x += glyph.advance
                actual = bytes(machine.mem_read(framebuffer, 640 * 480))
                if actual != bytes(expected):
                    raise ValueError(f'native color pixel mismatch: {font_path.name}/{color_name}')
                image = Image.frombytes('P', (640, 480), actual)
                image.putpalette(palette)
                crop = image.convert('RGB').crop((26, 36, 110, 72)).resize((168, 72), Image.Resampling.NEAREST)
                views.append((font_path.stem + ' / ' + color_name, crop))
                color_checks.append({'font': font_path.name, 'foreground': foreground,
                                     'color': color_name, 'pixel_match': True})
        # Labels are added around actual emulator framebuffer crops.
        sheet = Image.new('RGB', (720, ((len(views) + 1) // 2) * 96), (24, 24, 28))
        pen = ImageDraw.Draw(sheet)
        for idx, (label, crop) in enumerate(views):
            x, y = (idx % 2) * 360, (idx // 2) * 96
            pen.text((x + 8, y + 4), label, fill='white')
            sheet.paste(crop, (x + 8, y + 22))
        output.mkdir(parents=True, exist_ok=True)
        sheet.save(output / 'native_color_states.png')
        selected = {'FONTNORM / native', 'FONTSEL / native', 'REDDARK / native', 'REDSEL / native',
                    'REDONE / red', 'REDONE / green', 'REDONE / white', 'REDONE / blue'}
        summary = Image.new('RGB', (720, 4 * 96), (24, 24, 28))
        pen = ImageDraw.Draw(summary)
        for idx, (label, crop) in enumerate(v for v in views if v[0] in selected):
            x, y = (idx % 2) * 360, (idx // 2) * 96
            pen.text((x + 8, y + 4), label, fill='white')
            summary.paste(crop, (x + 8, y + 22))
        summary.save(output / 'native_color_summary.png')
        menu_views = [v for v in views if v[0] in {'FONTNORM / menu', 'FONTSEL / menu', 'FONTPALE / menu', 'FONTRED / menu'}]
        menu_summary = Image.new('RGB', (720, 192), (24, 24, 28))
        pen = ImageDraw.Draw(menu_summary)
        for idx, (label, crop) in enumerate(menu_views):
            x, y = idx % 2 * 360, idx // 2 * 96
            pen.text((x + 8, y + 4), label + ' / light background', fill='white')
            menu_summary.paste(crop, (x + 8, y + 22))
        menu_summary.save(output / 'menu_contrast_summary.png')
        machine.mem_write(framebuffer, b'\0' * (640 * 480))
        machine.mem_write(bitmap + 0xC000, b'\0' * 0xE50)
        machine.mem_write(0x123E04, b'\0')
    for line, text in enumerate(lines):
        x, y = 30, 180 + line * 26
        if check_text_hooks:
            machine.mem_write(bitmap, text.encode('utf-8') + b'\0')
            machine.mem_write(bitmap + 0x7000, b'%s\0')
            machine.mem_write(stack, struct.pack('<I', 0x6B0000))
            machine.reg_write(UC_X86_REG_ESP, stack)
            machine.reg_write(UC_X86_REG_EAX, bitmap)
            if check_general_text:
                machine.mem_write(stack, struct.pack('<3I', 0x6B0000, bitmap + 0x7000, bitmap))
            machine.emu_start(0x18FBF if check_general_text else 0x77185, 0x6B0000, count=1000000)
            expected_width = sum(glyphs[ord(c)].advance for c in text if glyphs[ord(c)].enabled)
            width = machine.reg_read(UC_X86_REG_EAX)
            if width != expected_width or machine.reg_read(UC_X86_REG_ESP) != stack + 4:
                raise ValueError(f'patched measure mismatch: {width} != {expected_width}')
            hook_widths.append(width)
            machine.mem_write(stack, struct.pack('<I', 0x6B0000))
            machine.reg_write(UC_X86_REG_ESP, stack)
            machine.reg_write(UC_X86_REG_EAX, x)
            machine.reg_write(UC_X86_REG_EDX, y)
            machine.reg_write(UC_X86_REG_EBX, 0)
            machine.reg_write(UC_X86_REG_ECX, bitmap)
            if check_general_text:
                machine.mem_write(stack, struct.pack('<5I', 0x6B0000, x, y, bitmap + 0x7000, bitmap))
                if line == 2:
                    machine.mem_write(stack, struct.pack('<3I', 0x6B0000, bitmap + 0x7000, bitmap))
                    for address, value in [(0x3B5F08, x), (0x3B5F04, y), (0x3A431E, x)]:
                        machine.mem_write(address, struct.pack('<I', value))
            entry = [0x185FF, 0x1885D, 0x182AF][line] if check_general_text else 0x76E98
            machine.emu_start(entry, 0x6B0000, count=3000000)
            if machine.reg_read(UC_X86_REG_EIP) != 0x6B0000 or machine.reg_read(UC_X86_REG_ESP) != stack + 4:
                raise ValueError('patched draw did not return with original stack')
            continue
        for char in text:
            glyph = glyphs[ord(char)]
            if glyph.enabled and glyph.width > 2 and glyph.height > 2:
                machine.mem_write(bitmap, glyph.pixels)
                machine.mem_write(stack, struct.pack('<5I', 0x6B0000, glyph.width, glyph.height, 1, bitmap))
                machine.reg_write(UC_X86_REG_ESP, stack)
                machine.reg_write(UC_X86_REG_EAX, x + glyph.left)
                machine.reg_write(UC_X86_REG_EDX, y + glyph.top)
                machine.reg_write(UC_X86_REG_EBX, glyph.width)
                machine.reg_write(UC_X86_REG_ECX, glyph.height)
                # Unicorn caches translated generated code between glyphs.
                # Flush only the original renderer's writable code buffer.
                machine.ctl_remove_cache(scratch, scratch + 0x10000)
                machine.ctl_remove_cache(0x9F0B8, 0x9F419)
                try:
                    machine.emu_start(0x9F0B8, 0x6B0000, count=1000000)
                except Exception as error:
                    raise ValueError(f'render failure EIP={machine.reg_read(UC_X86_REG_EIP):#x} EDI={machine.reg_read(UC_X86_REG_EDI):#x} ESP={machine.reg_read(UC_X86_REG_ESP):#x}: {error}') from error
                if machine.reg_read(UC_X86_REG_EIP) != 0x6B0000 or machine.reg_read(UC_X86_REG_ESP) != stack + 20:
                    raise ValueError('original renderer failed to return or preserve stack')
                calls += 1
                stride = struct.unpack('<I', machine.mem_read(0x9F233, 4))[0]
                if stride != glyph.width:
                    raise ValueError(f'row stride self-modification failed: {stride} != {glyph.width}')
            x += glyph.advance
    pixels = bytes(machine.mem_read(framebuffer, 640 * 480))
    if not any(pixels):
        raise ValueError('original renderer produced no framebuffer pixels')
    palette_path = pack_path.parent / 'palette.json'
    palette = [min(value * 4, 255) for value in json.loads(palette_path.read_text())]
    image = Image.frombytes('P', (640, 480), pixels)
    image.putpalette(palette)
    output.mkdir(parents=True, exist_ok=True)
    image.convert('RGB').save(output / 'original_renderer_korean_probe.png')
    # Compare all destination pixels against the same positioned bitmaps.
    expected = bytearray(640 * 480)
    for line, text in enumerate(lines):
        x, y = 30, 180 + line * 26
        for char in text:
            glyph = glyphs[ord(char)]
            if glyph.enabled and glyph.width > 2 and glyph.height > 2:
                for gy in range(glyph.height):
                    for gx in range(glyph.width):
                        value = glyph.pixels[gy * glyph.width + gx]
                        if value:
                            expected[(y + glyph.top + gy) * 640 + x + glyph.left + gx] = value
            x += glyph.advance
    if pixels != bytes(expected):
        raise ValueError(f'original renderer pixel mismatch: {sum(a != b for a, b in zip(pixels, expected))}')
    if hashlib.sha256(exe.read_bytes()).hexdigest() != digest:
        raise ValueError('original changed during probe')
    result = {'status': ('patched UTF-8 draw/measure entries and original bitmap renderer executed in isolation; DOS/game execution unverified'
                        if check_text_hooks else 'original bitmap renderer executed in isolation; NOT a playable game hook'),
              'original_sha256': digest, 'internal_fixups_applied': fixes,
              'selector_fixups_not_applied': selector_skips, 'renderer_data_base': hex(data_base),
              'nonlocal_data_fixups_deferred': [],
              'offsets_outside_target_object': outside_object_offsets,
              'original_blitter_calls': calls, 'pixel_match': True, 'font_pack': str(pack_path),
              'original_native_glyph_calls': native_calls,
              'font_loader_probe': loader_result,
              'patched_text_hooks_checked': check_text_hooks, 'patched_text_widths': hook_widths,
              'original_general_text_entries_checked': check_general_text,
              'original_printf_format_calls': format_calls,
              'native_color_cases': color_checks,
              'limitations': (['no DOS startup, subtitle wrapping, font selection, clipping edge or shadow-path test']
                              if check_text_hooks else ['no DOS startup, game font loader, UTF-8 string draw hook, clipping edge or shadow-path test'])}
    (output / 'render_probe_report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--font-pack', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/engine_utf8/render_probe')
    parser.add_argument('--check-font-loader', action='store_true')
    parser.add_argument('--check-text-hooks', action='store_true')
    parser.add_argument('--check-general-text', action='store_true')
    parser.add_argument('--color-font-dir', type=Path)
    parser.add_argument('--color-text', default='가나다')
    args = parser.parse_args()
    result = probe(args.exe, args.font_pack, args.output, args.check_font_loader,
                   args.check_text_hooks, args.check_general_text, args.color_font_dir, args.color_text)
    print(json.dumps({key: result[key] for key in ['status', 'internal_fixups_applied',
          'selector_fixups_not_applied', 'original_blitter_calls', 'pixel_match']}, ensure_ascii=True))
