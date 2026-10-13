"""Build the bounded x86 UTF-8 decoder intended for a future DOS engine hook.

ABI: EAX = byte pointer, EDX = remaining bytes. Returns EAX = Unicode scalar,
EDX = consumed bytes (zero only on empty input). Invalid input returns U+FFFD
and consumes one byte. Preserves EBX/ECX/ESI/EDI/EBP and ESP; flags may change.
This ABI is NOT the original RG.EXE character function ABI. No game hook yet.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEPS = ROOT / "output/engine_utf8/deps"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))

ASM = """push ebx
push ecx
push esi
push edi
push ebp
mov esi, eax
mov ebx, edx
test ebx, ebx
jz empty
movzx eax, byte ptr [esi]
cmp eax, 0x80
jb ascii
cmp eax, 0xc2
jb invalid
cmp eax, 0xdf
jbe two
cmp eax, 0xef
jbe three
cmp eax, 0xf4
jbe four
jmp invalid
two:
mov ecx, 2
mov ebp, 0x80
and eax, 0x1f
jmp continuation
three:
mov ecx, 3
mov ebp, 0x800
and eax, 0x0f
jmp continuation
four:
mov ecx, 4
mov ebp, 0x10000
and eax, 0x07
continuation:
cmp ebx, ecx
jb invalid
mov edx, 1
next_byte:
movzx edi, byte ptr [esi + edx]
and edi, 0xc0
cmp edi, 0x80
jne invalid
movzx edi, byte ptr [esi + edx]
and edi, 0x3f
shl eax, 6
or eax, edi
inc edx
cmp edx, ecx
jb next_byte
cmp eax, ebp
jb invalid
cmp eax, 0x10ffff
ja invalid
cmp eax, 0xd800
jb done
cmp eax, 0xdfff
jbe invalid
jmp done
ascii:
mov edx, 1
jmp done
empty:
mov eax, 0xfffd
xor edx, edx
jmp done
invalid:
mov eax, 0xfffd
mov edx, 1
done:
pop ebp
pop edi
pop esi
pop ecx
pop ebx
ret
"""


def assemble() -> bytes:
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(ASM)
    return bytes(encoded)


def build(output: Path) -> dict:
    code = assemble()
    output.mkdir(parents=True, exist_ok=True)
    (output / "utf8_decode_x86.bin").write_bytes(code)
    (output / "utf8_decode_x86.asm").write_text(ASM, encoding="ascii")
    result = {"format": "redguard-utf8-decoder-prototype-v1",
              "status": "standalone decoder; NOT linked into RG.EXE",
              "bytes": len(code), "sha256": hashlib.sha256(code).hexdigest(),
              "abi": "eax=input pointer, edx=remaining; eax=scalar, edx=consumed; preserves ebx/ecx/esi/edi/ebp",
              "invalid": "U+FFFD, one byte consumed; empty input consumes zero"}
    (output / "utf8_decode_build.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(build(ROOT / "output/engine_utf8/runtime"), indent=2))
