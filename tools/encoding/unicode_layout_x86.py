"""Sparse glyph lookup and UTF-8 line layout in relocatable 32-bit x86.

layout ABI (cdecl): (bytes, length, validated_KGF1, max_width, output, capacity).
Returns EAX=line count, EDX=status: 0 success, 1 output full, 2 invalid width.
Output records: start/end BYTE offsets, pixel width, flags (1 oversized scalar,
2 explicit newline). All fields u32, stride 16. Caller owns bounded buffers.
Preserves EBX/ESI/EDI/EBP. Input is never rewritten. Not hooked into RG.EXE yet.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('rg_utf8_decoder', Path(__file__).with_name('utf8_x86.py'))
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)

# Lookup ABI: EAX=scalar, EDX=validated KGF1 base; EAX=record pointer or zero.
# Preserves all other general registers. Binary search has no 8-bit slot index.
LOOKUP = """
lookup_glyph:
push ebx
push ecx
push esi
push edi
push ebp
mov ebp, eax
mov esi, edx
add esi, dword ptr [edx + 12]
xor ebx, ebx
mov ecx, dword ptr [edx + 4]
lookup_loop:
cmp ebx, ecx
jae lookup_missing
mov edi, ecx
sub edi, ebx
shr edi, 1
add edi, ebx
imul eax, edi, 24
add eax, esi
cmp ebp, dword ptr [eax]
je lookup_done
jb lookup_lower
lea ebx, [edi + 1]
jmp lookup_loop
lookup_lower:
mov ecx, edi
jmp lookup_loop
lookup_missing:
xor eax, eax
lookup_done:
pop ebp
pop edi
pop esi
pop ecx
pop ebx
ret
"""

LAYOUT = """
layout_utf8:
push ebp
mov ebp, esp
sub esp, 60
push ebx
push esi
push edi
mov dword ptr [ebp - 4], 0
mov dword ptr [ebp - 8], 0
mov dword ptr [ebp - 12], 0
mov dword ptr [ebp - 16], -1
mov dword ptr [ebp - 28], 0
mov dword ptr [ebp - 60], 0
cmp dword ptr [ebp + 20], 0
je layout_invalid
cmp dword ptr [ebp + 20], 0x7fffffff
ja layout_invalid
layout_loop:
mov eax, dword ptr [ebp - 4]
cmp eax, dword ptr [ebp + 12]
jae layout_finish
mov edx, dword ptr [ebp + 12]
sub edx, eax
add eax, dword ptr [ebp + 8]
call decode_utf8
mov dword ptr [ebp - 32], edx
mov dword ptr [ebp - 36], eax
cmp eax, 10
je layout_newline
cmp eax, 13
je layout_newline
cmp eax, 9
jne layout_lookup
mov eax, 32
layout_lookup:
mov edx, dword ptr [ebp + 16]
call lookup_glyph
test eax, eax
jnz layout_found
mov eax, 63
call lookup_glyph
test eax, eax
jnz layout_found
mov ecx, 1
jmp layout_advance_ready
layout_found:
xor ecx, ecx
cmp word ptr [eax + 18], 0
je layout_advance_ready
movzx ecx, word ptr [eax + 16]
layout_advance_ready:
cmp dword ptr [ebp - 36], 9
jne layout_no_tab
shl ecx, 2
layout_no_tab:
mov dword ptr [ebp - 40], ecx
add ecx, dword ptr [ebp - 12]
cmp ecx, dword ptr [ebp + 20]
ja layout_overflow
mov eax, dword ptr [ebp - 36]
cmp eax, 32
je layout_space
cmp eax, 9
jne layout_consume
layout_space:
mov eax, dword ptr [ebp - 4]
mov dword ptr [ebp - 16], eax
add eax, dword ptr [ebp - 32]
mov dword ptr [ebp - 20], eax
mov eax, dword ptr [ebp - 12]
mov dword ptr [ebp - 24], eax
layout_consume:
mov dword ptr [ebp - 12], ecx
mov eax, dword ptr [ebp - 32]
add dword ptr [ebp - 4], eax
mov dword ptr [ebp - 60], 0
jmp layout_loop
layout_overflow:
mov dword ptr [ebp - 52], 0
mov dword ptr [ebp - 60], 0
mov eax, dword ptr [ebp - 4]
cmp eax, dword ptr [ebp - 8]
je layout_oversized
cmp dword ptr [ebp - 36], 32
je layout_drop_space
cmp dword ptr [ebp - 36], 9
je layout_drop_space
mov ecx, dword ptr [ebp - 16]
cmp ecx, -1
je layout_break_here
cmp ecx, dword ptr [ebp - 8]
jbe layout_break_here
mov dword ptr [ebp - 44], ecx
mov eax, dword ptr [ebp - 24]
mov dword ptr [ebp - 48], eax
mov eax, dword ptr [ebp - 20]
mov dword ptr [ebp - 56], eax
jmp layout_emit_reset
layout_break_here:
mov dword ptr [ebp - 44], eax
mov dword ptr [ebp - 56], eax
mov eax, dword ptr [ebp - 12]
mov dword ptr [ebp - 48], eax
jmp layout_emit_reset
layout_drop_space:
mov dword ptr [ebp - 44], eax
add eax, dword ptr [ebp - 32]
mov dword ptr [ebp - 56], eax
mov eax, dword ptr [ebp - 12]
mov dword ptr [ebp - 48], eax
jmp layout_emit_reset
layout_oversized:
add eax, dword ptr [ebp - 32]
mov dword ptr [ebp - 44], eax
mov dword ptr [ebp - 56], eax
mov eax, dword ptr [ebp - 40]
mov dword ptr [ebp - 48], eax
mov dword ptr [ebp - 52], 1
jmp layout_emit_reset
layout_newline:
mov eax, dword ptr [ebp - 4]
mov dword ptr [ebp - 44], eax
add eax, dword ptr [ebp - 32]
cmp dword ptr [ebp - 36], 13
jne layout_newline_ready
cmp eax, dword ptr [ebp + 12]
jae layout_newline_ready
mov ecx, dword ptr [ebp + 8]
cmp byte ptr [ecx + eax], 10
jne layout_newline_ready
inc eax
layout_newline_ready:
mov dword ptr [ebp - 56], eax
mov eax, dword ptr [ebp - 12]
mov dword ptr [ebp - 48], eax
mov dword ptr [ebp - 52], 2
mov dword ptr [ebp - 60], 1
layout_emit_reset:
call layout_emit
test eax, eax
jz layout_full
mov eax, dword ptr [ebp - 56]
mov dword ptr [ebp - 4], eax
mov dword ptr [ebp - 8], eax
mov dword ptr [ebp - 12], 0
mov dword ptr [ebp - 16], -1
jmp layout_loop
layout_finish:
mov eax, dword ptr [ebp - 4]
cmp eax, dword ptr [ebp - 8]
jne layout_final_line
cmp dword ptr [ebp - 28], 0
je layout_final_line
cmp dword ptr [ebp - 60], 0
je layout_success
layout_final_line:
mov dword ptr [ebp - 44], eax
mov eax, dword ptr [ebp - 12]
mov dword ptr [ebp - 48], eax
mov dword ptr [ebp - 52], 0
call layout_emit
test eax, eax
jz layout_full
layout_success:
xor edx, edx
jmp layout_return
layout_full:
mov edx, 1
jmp layout_return
layout_invalid:
mov edx, 2
layout_return:
mov eax, dword ptr [ebp - 28]
pop edi
pop esi
pop ebx
mov esp, ebp
pop ebp
ret
layout_emit:
mov ecx, dword ptr [ebp - 28]
cmp ecx, dword ptr [ebp + 28]
jae layout_emit_full
shl ecx, 4
add ecx, dword ptr [ebp + 24]
mov eax, dword ptr [ebp - 8]
mov dword ptr [ecx], eax
mov eax, dword ptr [ebp - 44]
mov dword ptr [ecx + 4], eax
mov eax, dword ptr [ebp - 48]
mov dword ptr [ecx + 8], eax
mov eax, dword ptr [ebp - 52]
mov dword ptr [ecx + 12], eax
inc dword ptr [ebp - 28]
mov eax, 1
ret
layout_emit_full:
xor eax, eax
ret
"""


def assemble() -> bytes:
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    # Decoder labels are local to this concatenated source and do not overlap.
    source = LAYOUT + LOOKUP + '\ndecode_utf8:\n' + decoder.ASM
    code, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source)
    return bytes(code)


if __name__ == '__main__':
    output = ROOT / 'output/engine_utf8/runtime'
    output.mkdir(parents=True, exist_ok=True)
    binary = assemble()
    (output / 'unicode_layout_x86.bin').write_bytes(binary)
    (output / 'unicode_layout_x86.asm').write_text(LAYOUT + LOOKUP + '\ndecode_utf8:\n' + decoder.ASM, encoding='ascii')
    print(json.dumps({'bytes': len(binary), 'status': 'x86 prototype; no RG.EXE hooks installed'}))
