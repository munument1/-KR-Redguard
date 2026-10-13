"""Redguard RTX reader/writer. Edits text bytes while preserving audio exactly.

Importing into a vanilla Redguard executable requires a compatible byte-to-glyph
mapping. This tool handles the container only; it does not enable Korean display.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import struct


class RtxError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    tag: bytes
    offset: int
    size: int
    kind: int
    text: bytes
    trailing: bytes

    @property
    def id(self) -> str:
        return self.tag.decode("ascii")


class Rtx:
    def __init__(self, raw: bytes):
        self.raw = raw
        if len(raw) < 12 or raw[-12:-8] != b"RNAV":
            raise RtxError("missing RNAV footer")
        self.index_offset, count = struct.unpack_from("<II", raw, len(raw) - 8)
        if self.index_offset + count * 12 != len(raw) - 12:
            raise RtxError("invalid RTX index extent")
        seen: set[bytes] = set()
        entries: list[Entry] = []
        for i in range(count):
            tag, offset, size = struct.unpack_from("<4sII", raw, self.index_offset + 12 * i)
            if tag in seen:
                raise RtxError(f"duplicate index tag {tag!r}")
            seen.add(tag)
            if offset < 8 or offset + size > self.index_offset:
                raise RtxError(f"index {i}: payload outside data region")
            disk_tag, disk_size = struct.unpack_from(">4sI", raw, offset - 8)
            if (disk_tag, disk_size) != (tag, size):
                raise RtxError(f"index {i}: chunk header/index mismatch")
            payload = raw[offset:offset + size]
            if len(payload) < 6 or payload[0] != 0 or payload[1] not in (0, 1):
                raise RtxError(f"index {i}: unsupported text/audio header")
            text_length = struct.unpack_from("<H", payload, 2)[0]
            text_end = 6 + text_length
            if text_end > len(payload):
                raise RtxError(f"index {i}: truncated text")
            trailing = payload[text_end:]
            kind = payload[1]
            if kind == 0 and trailing:
                raise RtxError(f"index {i}: excess text payload bytes")
            if kind == 1:
                if len(trailing) < 27:
                    raise RtxError(f"index {i}: truncated audio header")
                audio_length = struct.unpack_from("<I", trailing, 22)[0]
                if len(trailing) != 27 + audio_length:
                    raise RtxError(f"index {i}: invalid audio length")
            entries.append(Entry(tag, offset, size, kind, payload[6:text_end], trailing))
        ordered = sorted(entries, key=lambda x: x.offset)
        for a, b in zip(ordered, ordered[1:]):
            if a.offset + a.size > b.offset - 8:
                raise RtxError("overlapping chunks")
        self.entries = entries

    def manifest(self, codec: str = "cp437") -> dict:
        return {
            "format": "redguard-rtx-translation-v1",
            "source_sha256": hashlib.sha256(self.raw).hexdigest(),
            "source_codec": codec,
            "entries": [{
                "tag": entry.id,
                "kind": "audio" if entry.kind else "text",
                "original": entry.text.decode(codec, errors="replace"),
                "translation": None,
            } for entry in self.entries],
        }

    def repack(self, changes: dict[str, str], codec: str = "cp437") -> bytes:
        """Preserve every untouched byte, original entry order, and all voice data."""
        existing = {entry.id for entry in self.entries}
        if not changes.keys() <= existing:
            raise RtxError(f"unknown tags: {sorted(changes.keys() - existing)[:5]}")
        encoded: dict[str, bytes] = {}
        for tag, translated in changes.items():
            if not isinstance(translated, str):
                raise RtxError(f"{tag}: translation must be text")
            try:
                data = translated.encode(codec, errors="strict")
            except UnicodeError as error:
                raise RtxError(f"{tag}: text cannot be encoded as {codec}") from error
            if len(data) > 0xFFFF:
                raise RtxError(f"{tag}: text exceeds 65535 bytes")
            encoded[tag] = data
        if not encoded or all(encoded.get(e.id, e.text) == e.text for e in self.entries):
            return self.raw
        rebuilt = bytearray()
        relocated: dict[bytes, tuple[int, int]] = {}
        cursor = 0
        for entry in sorted(self.entries, key=lambda e: e.offset):
            chunk_start = entry.offset - 8
            rebuilt.extend(self.raw[cursor:chunk_start])
            before = self.raw[entry.offset:entry.offset + entry.size]
            if encoded.get(entry.id, entry.text) == entry.text:
                payload = before
            else:
                update = encoded[entry.id]
                payload = before[:2] + struct.pack("<H", len(update)) + before[4:6] + update + entry.trailing
            if len(payload) > 0xFFFFFFFF:
                raise RtxError("payload exceeds u32")
            rebuilt.extend(entry.tag)
            rebuilt.extend(struct.pack(">I", len(payload)))
            relocated[entry.tag] = (len(rebuilt), len(payload))
            rebuilt.extend(payload)
            cursor = entry.offset + entry.size
        rebuilt.extend(self.raw[cursor:self.index_offset])
        offset = len(rebuilt)
        if offset > 0xFFFFFFFF:
            raise RtxError("index offset exceeds u32")
        for entry in self.entries:  # preserve original index ordering
            pos, size = relocated[entry.tag]
            rebuilt.extend(struct.pack("<4sII", entry.tag, pos, size))
        rebuilt.extend(struct.pack("<4sII", b"RNAV", offset, len(self.entries)))
        final = bytes(rebuilt)
        checked = Rtx(final)
        for old, new in zip(self.entries, checked.entries):
            if old.trailing != new.trailing or old.kind != new.kind:
                raise RtxError(f"{old.id}: audio/metadata was not preserved")
        return final


def import_manifest(archive: Rtx, data: dict, codec: str) -> bytes:
    if data.get("format") != "redguard-rtx-translation-v1":
        raise RtxError("unsupported translation manifest")
    if data.get("source_sha256") != hashlib.sha256(archive.raw).hexdigest():
        raise RtxError("input file differs from manifest source SHA256")
    records = data.get("entries")
    if not isinstance(records, list):
        raise RtxError("expected entries array")
    original = {e.id: e for e in archive.entries}
    changes = {}
    found: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("tag"), str):
            raise RtxError("invalid manifest entry")
        tag = record["tag"]
        if tag in found or tag not in original:
            raise RtxError(f"duplicate/unknown tag: {tag}")
        found.add(tag)
        # A null means 'not yet translated'; an empty string is an intentional blank.
        translation = record.get("translation")
        if translation is not None:
            changes[tag] = translation
        elif record.get("corrected_by_urp") is True:
            # The seed script marks the 78 corrected source strings. Preserve
            # those bug fixes when building a mixed/partially Korean RTX too.
            if "patch" not in data or not isinstance(record.get("vanilla_original"), str):
                raise RtxError("upstream correction missing verified source context")
            if original[tag].text != record["vanilla_original"].encode("cp437"):
                raise RtxError(f"{tag}: original text differs from patch baseline")
            correction = record.get("original")
            if not isinstance(correction, str):
                raise RtxError(f"{tag}: corrected source must be a string")
            changes[tag] = correction
    if len(found) != len(archive.entries):
        raise RtxError("manifest has missing entries")
    return archive.repack(changes, codec)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    extract = sub.add_parser("export", help="export a UTF-8 JSON translation manifest")
    extract.add_argument("source", type=Path)
    extract.add_argument("output", type=Path)
    extract.add_argument("--codec", default="cp437")
    rebuild = sub.add_parser("pack", help="rebuild RTX with translated text")
    rebuild.add_argument("source", type=Path)
    rebuild.add_argument("manifest", type=Path)
    rebuild.add_argument("output", type=Path)
    rebuild.add_argument("--codec", default="cp437", help="output bytes; engine patch needed for Korean")
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("output must differ from the original RTX file")
    archive = Rtx(args.source.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.action == "export":
        args.output.write_text(json.dumps(archive.manifest(args.codec), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Exported {len(archive.entries)} RTX entries: {args.output}")
    else:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = import_manifest(archive, manifest, args.codec)
        args.output.write_bytes(result)
        print(f"Rebuilt and validated {len(archive.entries)} RTX entries ({len(result)} bytes): {args.output}")


if __name__ == "__main__":
    main()
