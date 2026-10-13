"""Experimental Software renderer hooks. ASCII strings retain original paths.

The embedded KGF1 supplies mixed UTF-8 shapes. Native font palettes and live
monochrome text colors determine the ink. General text uses the original native
glyph renderer with a temporary glyph descriptor; menu text uses bitmap drawing.
No file I/O, heap allocation or full glyph-table scan occurs while drawing.
Its LE relocations are emitted by build_test_exe.py.
"""
from unicode_layout_x86 import LOOKUP, decoder

BASE = 0x500000
PACK_OFFSET = 0x4000
STYLES_OFFSET = 0x1000
SCRATCH_OFFSET = 0x90000
NATIVE_FONT_OFFSET = 0xa0000
DRAW = 0x76E98
MEASURE = 0x77185
BLIT = 0x9F0B8
HOOK_BYTES = {DRAW: bytes.fromhex('56575589e5'), MEASURE: bytes.fromhex('5351525657'),
              0x1835C: bytes.fromhex('8b45f8803800'),
              0x186AD: bytes.fromhex('c745f400000000'),
              0x188E4: bytes.fromhex('c745f400000000'),
              0x19023: bytes.fromhex('c745f000000000'),
              0x190D1: bytes.fromhex('5351525657')}

SOURCE = """
jmp draw_entry
jmp measure_entry
jmp general_draw
jmp clipped_draw
jmp general_measure
jmp token_measure
jmp cursor_draw
draw_entry:
pushad
mov esi, ecx
call scan_text
test edx, edx
popad
jnz draw_unicode
draw_original:
push esi
push edi
push ebp
mov ebp, esp
jmp 0x76e9d
draw_unicode:
push ebp
mov ebp, esp
sub esp, 48
pushad
mov dword ptr [ebp - 4], eax
mov dword ptr [ebp - 8], edx
mov dword ptr [ebp - 12], ebx
mov dword ptr [ebp - 16], ecx
call choose_style
mov dword ptr [ebp - 36], eax
mov esi, ecx
call scan_text
mov dword ptr [ebp - 20], eax
test dword ptr [ebp - 12], 3
jz draw_aligned
mov eax, dword ptr [ebp - 16]
call measure_entry
test dword ptr [ebp - 12], 4
jz draw_align_scale_done
shl eax, 1
draw_align_scale_done:
test dword ptr [ebp - 12], 1
jz draw_align_right
shr eax, 1
draw_align_right:
sub dword ptr [ebp - 4], eax
draw_aligned:
mov eax, dword ptr [ebp - 4]
mov dword ptr [ebp - 32], eax
draw_loop:
cmp dword ptr [ebp - 20], 0
je draw_done
mov eax, dword ptr [ebp - 16]
mov edx, dword ptr [ebp - 20]
call decode_utf8
add dword ptr [ebp - 16], edx
sub dword ptr [ebp - 20], edx
cmp eax, 13
je draw_loop
cmp eax, 10
je draw_newline
cmp eax, 9
jne draw_lookup
mov eax, 32
draw_lookup:
call find_glyph
test eax, eax
jz draw_loop
mov dword ptr [ebp - 24], eax
cmp word ptr [eax + 18], 0
je draw_loop
cmp word ptr [eax + 8], 2
jbe draw_advance
cmp word ptr [eax + 10], 2
jbe draw_advance
mov edi, 0x504000
mov edx, dword ptr [eax + 4]
add edx, edi
call colorize_glyph
push edx
push 1
movzx edx, word ptr [eax + 10]
push edx
movzx edx, word ptr [eax + 8]
push edx
movzx ebx, word ptr [eax + 8]
movzx ecx, word ptr [eax + 10]
movsx edx, word ptr [eax + 14]
movsx eax, word ptr [eax + 12]
test dword ptr [ebp - 12], 4
jz draw_scale_done
shl eax, 1
shl edx, 1
shl ebx, 1
shl ecx, 1
draw_scale_done:
add eax, dword ptr [ebp - 4]
add edx, dword ptr [ebp - 8]
test dword ptr [ebp - 12], 0x100
jnz draw_general_backend
call 0x9f0b8
jmp draw_advance
draw_general_backend:
add esp, 16
call native_glyph
draw_advance:
mov eax, dword ptr [ebp - 24]
movzx eax, word ptr [eax + 16]
test dword ptr [ebp - 12], 4
jz draw_advance_scale_done
shl eax, 1
draw_advance_scale_done:
add dword ptr [ebp - 4], eax
jmp draw_loop
draw_newline:
mov eax, dword ptr [ebp - 32]
mov dword ptr [ebp - 4], eax
mov eax, LINE_HEIGHT
test dword ptr [ebp - 12], 4
jz draw_newline_scale_done
shl eax, 1
draw_newline_scale_done:
add dword ptr [ebp - 8], eax
jmp draw_loop
draw_done:
popad
mov esp, ebp
pop ebp
ret

measure_entry:
pushad
mov esi, eax
call scan_text
test edx, edx
popad
jnz measure_unicode
measure_original:
push ebx
push ecx
push edx
push esi
push edi
jmp 0x7718a
measure_unicode:
push ebp
mov ebp, esp
sub esp, 16
pushad
mov dword ptr [ebp - 4], eax
mov esi, eax
call scan_text
mov dword ptr [ebp - 8], eax
mov dword ptr [ebp - 12], 0
mov dword ptr [ebp - 16], 0
measure_loop:
cmp dword ptr [ebp - 8], 0
je measure_done
mov eax, dword ptr [ebp - 4]
mov edx, dword ptr [ebp - 8]
call decode_utf8
add dword ptr [ebp - 4], edx
sub dword ptr [ebp - 8], edx
cmp eax, 13
je measure_loop
cmp eax, 10
je measure_newline
cmp eax, 9
jne measure_lookup
mov eax, 32
measure_lookup:
call find_glyph
test eax, eax
jz measure_loop
cmp word ptr [eax + 18], 0
je measure_loop
movzx eax, word ptr [eax + 16]
add dword ptr [ebp - 12], eax
jmp measure_loop
measure_newline:
call measure_max
mov dword ptr [ebp - 12], 0
jmp measure_loop
measure_done:
call measure_max
mov eax, dword ptr [ebp - 16]
mov dword ptr [esp + 28], eax
popad
mov esp, ebp
pop ebp
ret
measure_max:
mov eax, dword ptr [ebp - 12]
cmp eax, dword ptr [ebp - 16]
jbe measure_max_done
mov dword ptr [ebp - 16], eax
measure_max_done:
ret

scan_text:
xor eax, eax
xor edx, edx
scan_loop:
cmp eax, 65535
jae scan_done
mov cl, byte ptr [esi + eax]
test cl, cl
jz scan_done
test cl, 0x80
jz scan_ascii
mov edx, 1
scan_ascii:
inc eax
jmp scan_loop
scan_done:
ret

find_glyph:
mov edx, 0x504000
call lookup_glyph
test eax, eax
jnz find_done
mov eax, 63
call lookup_glyph
find_done:
ret

general_draw:
pushad
mov esi, dword ptr [ebp - 8]
call scan_text
test edx, edx
popad
jnz general_draw_unicode
mov dword ptr [ebp - 12], 0
jmp 0x186b4
general_draw_unicode:
mov eax, dword ptr [ebp + 28]
mov edx, dword ptr [ebp + 32]
mov ebx, 0x100
mov ecx, dword ptr [ebp - 8]
call draw_unicode
mov eax, dword ptr [ebp - 8]
call measure_unicode
add dword ptr [ebp + 28], eax
jmp 0x187d7

clipped_draw:
pushad
mov esi, dword ptr [ebp - 8]
call scan_text
test edx, edx
popad
jnz clipped_draw_unicode
mov dword ptr [ebp - 12], 0
jmp 0x188eb
clipped_draw_unicode:
mov eax, dword ptr [ebp + 28]
mov edx, dword ptr [ebp + 32]
mov ebx, 0x100
mov ecx, dword ptr [ebp - 8]
call draw_unicode
mov eax, dword ptr [ebp - 8]
call measure_unicode
add dword ptr [ebp + 28], eax
jmp 0x18a0e

general_measure:
pushad
mov esi, dword ptr [ebp - 12]
call scan_text
test edx, edx
popad
jnz general_measure_unicode
mov dword ptr [ebp - 16], 0
jmp 0x1902a
general_measure_unicode:
mov eax, dword ptr [ebp - 12]
call measure_unicode
mov dword ptr [ebp - 20], eax
jmp 0x190b7

token_measure:
pushad
mov esi, eax
call scan_text
test edx, edx
popad
jnz token_measure_unicode
push ebx
push ecx
push edx
push esi
push edi
jmp 0x190d6
token_measure_unicode:
push ebp
mov ebp, esp
sub esp, 1024
pushad
mov esi, eax
token_skip:
cmp byte ptr [esi], 32
jne token_copy_start
inc esi
jmp token_skip
token_copy_start:
xor ecx, ecx
token_copy:
cmp ecx, 1023
jae token_end
mov al, byte ptr [esi + ecx]
cmp al, 32
je token_end
cmp al, 10
je token_end
test al, al
jz token_end
mov byte ptr [ebp + ecx - 1024], al
inc ecx
jmp token_copy
token_end:
mov byte ptr [ebp + ecx - 1024], 0
lea eax, [ebp - 1024]
call measure_unicode
mov dword ptr [esp + 28], eax
popad
mov esp, ebp
pop ebp
ret

cursor_draw:
pushad
mov esi, dword ptr [ebp - 8]
call scan_text
test edx, edx
popad
jnz cursor_draw_unicode
mov eax, dword ptr [ebp - 8]
cmp byte ptr [eax], 0
jmp 0x18362
cursor_draw_unicode:
mov eax, dword ptr [ebp - 32]
mov edx, dword ptr [ebp - 28]
mov ebx, 0x100
mov ecx, dword ptr [ebp - 8]
call draw_unicode
mov eax, dword ptr [ebp - 8]
call measure_unicode
add dword ptr [ebp - 32], eax
jmp 0x18486

choose_style:
pushad
mov edi, dword ptr [0x123e00]
mov ebx, 0x501000
cmp edi, dword ptr [ebx + 16]
jne style_scan
mov esi, dword ptr [ebx + 20]
test esi, esi
jz style_scan
call style_matches
test eax, eax
jnz style_selected
style_scan:
lea esi, [ebx + 32]
mov ecx, dword ptr [ebx + 4]
style_scan_loop:
call style_matches
test eax, eax
jnz style_selected
add esi, 320
dec ecx
jnz style_scan_loop
lea esi, [ebx + 32]
style_selected:
mov dword ptr [ebx + 16], edi
mov dword ptr [ebx + 20], esi
mov dword ptr [esp + 28], esi
popad
ret

style_matches:
push ebx
push ecx
push edx
push ebp
test edi, edi
jz style_no_match
xor ebx, ebx
mov ecx, 8
style_name_loop:
mov eax, dword ptr [edi + ebx + 20]
cmp eax, dword ptr [esi + ebx]
jne style_no_match
add ebx, 4
dec ecx
jnz style_name_loop
movzx ecx, word ptr [edi + 0x42]
mov ebp, 65
sub ebp, ecx
js style_no_match
movzx ecx, word ptr [edi + 0x44]
cmp ebp, ecx
jae style_no_match
movzx eax, word ptr [edi + ebp * 2 + 0x250]
cmp ax, word ptr [esi + 32]
jne style_no_match
movzx eax, word ptr [edi + ebp * 2 + 0x450]
cmp ax, word ptr [esi + 34]
jne style_no_match
mov edx, dword ptr [edi + ebp * 4 + 0xa50]
test edx, edx
jz style_no_match
mov ecx, dword ptr [esi + 36]
movzx eax, byte ptr [edx + ecx]
cmp eax, dword ptr [esi + 40]
jne style_no_match
mov eax, 1
jmp style_match_return
style_no_match:
xor eax, eax
style_match_return:
pop ebp
pop edx
pop ecx
pop ebx
ret

colorize_glyph:
pushad
mov ecx, dword ptr [eax + 20]
mov esi, edx
mov edi, 0x590000
mov ebx, dword ptr [ebp - 36]
color_loop:
test ecx, ecx
jz color_done
movzx eax, byte ptr [esi]
inc esi
test eax, eax
jz color_write
cmp dword ptr [ebx + 44], 0
je color_lut
cmp eax, 195
je color_no_outline
test dword ptr [ebp - 12], 0x100
jnz color_logical_ink
mov al, byte ptr [0x123e04]
jmp color_write
color_logical_ink:
mov eax, 1
jmp color_write
color_no_outline:
xor eax, eax
jmp color_write
color_lut:
test dword ptr [ebp - 12], 0x100
jnz color_native_lut
cmp byte ptr [ebx + 309], 0
je color_native_lut
cmp eax, 195
jne color_menu_body
mov al, byte ptr [ebx + 304]
jmp color_write
color_menu_body:
cmp byte ptr [ebx + 305], 0
je color_native_lut
cmp eax, 81
jne color_menu_highlight
mov al, byte ptr [ebx + 305]
jmp color_write
color_menu_highlight:
cmp eax, 112
jne color_menu_mid
mov al, byte ptr [ebx + 306]
jmp color_write
color_menu_mid:
cmp eax, 116
jne color_menu_shade
mov al, byte ptr [ebx + 307]
jmp color_write
color_menu_shade:
cmp eax, 119
jne color_native_lut
mov al, byte ptr [ebx + 308]
jmp color_write
color_native_lut:
mov al, byte ptr [ebx + eax + 48]
color_write:
mov byte ptr [edi], al
inc edi
dec ecx
jmp color_loop
color_done:
mov dword ptr [esp + 20], 0x590000
popad
ret

native_glyph:
pushad
mov edi, 0x5a0000
mov byte ptr [edi], 1
mov dword ptr [edi + 9], 0
mov word ptr [edi + 0x42], 65
mov word ptr [edi + 0x44], 1
mov word ptr [edi + 0x50], 1
mov esi, dword ptr [ebp - 24]
mov cx, word ptr [esi + 8]
mov word ptr [edi + 0x250], cx
mov cx, word ptr [esi + 10]
mov word ptr [edi + 0x450], cx
mov word ptr [edi + 0x650], 0
mov word ptr [edi + 0x850], 0
mov dword ptr [edi + 0xa50], 0x590000
push dword ptr [0x123e00]
mov dword ptr [0x123e00], edi
mov ebx, edx
mov esi, 65
call 0x34483b
pop edx
mov dword ptr [0x123e00], edx
popad
ret
"""


def assemble(line_height: int):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    source = SOURCE.replace('LINE_HEIGHT', str(line_height)) + LOOKUP + '\ndecode_utf8:\n' + decoder.ASM
    code, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, addr=BASE)
    code = bytearray(code)
    # Cross-object code, native state, style table and scratch pointers need LE fixups.
    fixes = []
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    instructions = list(md.disasm(bytes(code), BASE))
    exports = [int(ins.op_str, 16) for ins in instructions[:7]]
    external = {0x76e9d, 0x7718a, 0x9f0b8, 0x186b4, 0x187d7, 0x188eb, 0x18a0e,
                0x1902a, 0x190b7, 0x190d6, 0x18362, 0x18486}
    absolute = {BASE + PACK_OFFSET: (5, PACK_OFFSET), BASE + STYLES_OFFSET: (5, STYLES_OFFSET),
                BASE + SCRATCH_OFFSET: (5, SCRATCH_OFFSET), BASE + NATIVE_FONT_OFFSET: (5, NATIVE_FONT_OFFSET),
                0x123e00: (2, 0x3e00), 0x123e04: (2, 0x3e04)}
    for ins in instructions:
        if ins.mnemonic in ('call', 'jmp') and ins.op_str.startswith('0x') and int(ins.op_str, 16) in external:
            fixes.append((ins.address - BASE + ins.imm_offset, 8, 1, int(ins.op_str, 16) - 0x10000))
        if ins.mnemonic == 'call' and ins.op_str == '0x34483b':
            fixes.append((ins.address - BASE + ins.imm_offset, 8, 2, 0x22483b))
        if ins.imm_size == 4:
            value = int.from_bytes(code[ins.address - BASE + ins.imm_offset:ins.address - BASE + ins.imm_offset + 4], 'little')
            if value in absolute:
                obj, offset = absolute[value]
                fixes.append((ins.address - BASE + ins.imm_offset, 7, obj, offset))
        if ins.disp_size == 4 and ins.disp in absolute:
            obj, offset = absolute[ins.disp]
            fixes.append((ins.address - BASE + ins.disp_offset, 7, obj, offset))
    if len(fixes) != 25:
        raise ValueError(f'unexpected adapter relocations: {fixes}')
    if len(code) > PACK_OFFSET:
        raise ValueError('adapter overlaps embedded font')
    names = ['draw', 'measure', 'general_draw', 'clipped_draw', 'general_measure', 'token_measure', 'cursor_draw']
    return bytes(code), dict(zip(names, (e - BASE for e in exports))), fixes, source
