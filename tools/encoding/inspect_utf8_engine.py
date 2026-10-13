"""Read-only static inspection of the observed Steam RG.EXE text path.

Requires capstone. This is an analyzer, NOT an executable patch or LE loader.
Addresses are preferred LE addresses before runtime relocation. Fixup records
are not applied. The specific function offsets are accepted only after matching
instruction signatures; other executable versions must be investigated anew.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGIONS = {
    "byte_to_glyph": (0x187F8, 0x1885D),
    "draw_text": (0x76E98, 0x77185),
    "measure_text": (0x77185, 0x77252),
    "font_loader": (0xA731B, 0xA78D6),
}
SIGNATURES = {
    "single_byte_read": (0x1880E, "8a02"),
    "draw_pointer_increment": (0x76F61, "ff45f8"),
    "measure_pointer_increment": (0x771CB, "ff45f8"),
    "font_count_compare_256": (0xA7569, "668178440001"),
    "font_count_clamp_256": (0xA7574, "66c740440001"),
}


def inspect(executable: Path, draft_dir: Path, output: Path) -> dict:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32

    raw = executable.read_bytes()
    before_hash = hashlib.sha256(raw).hexdigest()
    if raw[:2] != b"MZ" or len(raw) < 64:
        raise ValueError("not an MZ executable")
    header = struct.unpack_from("<I", raw, 60)[0]
    if raw[header:header + 4] != b"LE\0\0":
        raise ValueError("expected little-endian LE image")
    u32 = lambda offset: struct.unpack_from("<I", raw, header + offset)[0]
    page_size, pages, data_start = u32(0x28), u32(0x14), u32(0x80)
    if page_size != 4096:
        raise ValueError("unexpected LE page size")
    object_table, page_table = header + u32(0x40), header + u32(0x48)
    objects = []
    for idx in range(u32(0x44)):
        size, base, flags, map_index, count, _ = struct.unpack_from("<6I", raw, object_table + idx * 24)
        objects.append(dict(number=idx + 1, size=size, base=base, flags=flags,
                            map_index=map_index, mapped_pages=count))
    code = objects[0]
    if code["base"] != 0x10000 or not code["flags"] & 4:
        raise ValueError("unexpected code object layout")

    def file_offset(address: int) -> int:
        relative = address - code["base"]
        if not 0 <= relative < code["size"]:
            raise ValueError("address outside code object")
        map_at = page_table + (code["map_index"] - 1 + relative // page_size) * 4
        physical = int.from_bytes(raw[map_at:map_at + 3], "big")
        if raw[map_at + 3] != 0 or not 1 <= physical <= pages:
            raise ValueError("unsupported LE page type")
        result = data_start + (physical - 1) * page_size + relative % page_size
        if result >= len(raw):
            raise ValueError("page points outside file")
        return result

    signatures = {}
    for name, (address, expected) in SIGNATURES.items():
        pos = file_offset(address)
        actual = raw[pos:pos + len(expected) // 2].hex()
        if actual != expected:
            raise ValueError(f"different executable version: {name} at {address:#x}: {actual}")
        signatures[name] = dict(preferred_address=hex(address), file_offset=hex(pos), bytes=actual)

    output.mkdir(parents=True, exist_ok=True)
    disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
    for name, (start, end) in REGIONS.items():
        blob = bytes(raw[file_offset(address)] for address in range(start, end))
        lines = [f"{ins.address:08x}  {ins.bytes.hex():24s} {ins.mnemonic} {ins.op_str}"
                 for ins in disassembler.disasm(blob, start)]
        (output / f"{name}.asm.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Relative direct CALLs within this object require no assumed data segment
    # base. Treat these as candidates until caller functions are investigated.
    direct_call_candidates = {name: [] for name in REGIONS}
    code_bytes = bytes(raw[file_offset(address)] for address in range(code["base"], code["base"] + code["size"]))
    for offset in range(len(code_bytes) - 4):
        if code_bytes[offset] != 0xE8:
            continue
        address = code["base"] + offset
        target = address + 5 + struct.unpack_from('<i', code_bytes, offset + 1)[0]
        for name, (start, _) in REGIONS.items():
            if target == start:
                direct_call_candidates[name].append({"preferred_address": hex(address),
                                                      "file_offset": hex(file_offset(address))})

    texts, seen = [], set()
    for path in sorted(draft_dir.glob("rtx_*_ko.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry["tag"] in seen:
                raise ValueError("duplicate translation tag")
            seen.add(entry["tag"])
            text = entry.get("translation")
            if not isinstance(text, str) or not text:
                raise ValueError("empty or missing translation")
            texts.append(text)
    chars = Counter("".join(texts))
    report = dict(
        status="static analysis only; UTF-8 support NOT implemented or game-tested",
        executable=str(executable), executable_sha256=before_hash,
        le_header_offset=hex(header), objects=objects, signatures=signatures,
        direct_call_candidates=direct_call_candidates,
        translation_coverage=dict(entries=len(texts), unique_characters=len(chars),
            unique_hangul_syllables=sum(0xAC00 <= ord(ch) <= 0xD7A3 for ch in chars),
            max_utf8_bytes=max((len(text.encode("utf-8")) for text in texts), default=0),
            unique_non_ascii=sum(ord(ch) >= 128 for ch in chars)),
        required_changes=["UTF-8 decoding with byte consumption and bounds checking",
            "character-aware draw and width loops", "replace fixed 256-entry glyph tables",
            "audit wrapping, copies, text lifetime, other UI paths and LE relocations"],
        source_reference="https://github.com/open-watcom/open-watcom-v2/blob/master/bld/watcom/h/exeflat.h",
    )
    if hashlib.sha256(executable.read_bytes()).hexdigest() != before_hash:
        raise RuntimeError("executable changed during inspection")
    (output / "engine_utf8_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--drafts", type=Path, default=ROOT / "output/text_translation/drafts")
    parser.add_argument("--output", type=Path, default=ROOT / "output/engine_utf8")
    args = parser.parse_args()
    report = inspect(args.exe, args.drafts, args.output)
    print(json.dumps({"status": report["status"], "coverage": report["translation_coverage"],
                      "matched_signatures": len(report["signatures"])}, ensure_ascii=True))


if __name__ == "__main__":
    main()
