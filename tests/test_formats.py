"""Synthetic binary fixtures: no copyrighted game files needed."""

import hashlib
import json
from pathlib import Path
import struct
import unittest

from tools.fnt.fnt_tool import FntError, make_png, metadata, read_font, replace_glyph
from tools.encoding.hangul_report import decompose_syllable, report
from tools.rtx.rtx_tool import Rtx, RtxError, import_manifest


def build_rtx(records):
    chunks = bytearray()
    index = []
    for tag, kind, text, tail in records:
        payload = b"\x00" + bytes([kind]) + struct.pack("<HH", len(text), 0) + text + tail
        chunks.extend(tag + struct.pack(">I", len(payload)))
        index.append((tag, len(chunks), len(payload)))
        chunks.extend(payload)
    chunks.extend(b"END ")
    pos = len(chunks)
    for entry in reversed(index):
        chunks.extend(struct.pack("<4sII", *entry))
    chunks.extend(struct.pack("<4sII", b"RNAV", pos, len(index)))
    return bytes(chunks)


def audio_blob(data=b"\x01\x02\x03\x04"):
    return struct.pack("<III", 0, 0, 11025) + b"\x64\x00" + struct.pack("<II", 0, 0xFFFFFFFF) + struct.pack("<I", len(data)) + b"\x00" + data


def build_fnt():
    fn = bytearray(56)
    struct.pack_into("<HHH", fn, 44, 12, 32, 2)
    struct.pack_into("<H", fn, 54, 1)
    palette = bytes([0] * 768)
    fbmp = struct.pack("<HhhHH", 1, 0, 0, 1, 1) + b"\x00" + struct.pack("<HhhHH", 1, 1, 2, 2, 1) + b"\x01\x02"
    def chunk(tag, blob):
        return tag + struct.pack(">I", len(blob)) + blob
    return chunk(b"FNHD", fn) + chunk(b"BPAL", palette) + chunk(b"FBMP", fbmp) + b"END "


class RtxTests(unittest.TestCase):
    def setUp(self):
        self.voice = audio_blob()
        self.original = build_rtx([(b"TXT1", 0, b"Hello", b""), (b"AUD1", 1, b"Voice", self.voice)])
        self.archive = Rtx(self.original)

    def test_noop_is_byte_identical(self):
        self.assertEqual(self.archive.repack({}), self.original)
        self.assertEqual(self.archive.repack({"TXT1": "Hello"}), self.original)

    def test_edits_reindex_preserve_all_audio_bytes(self):
        result = Rtx(self.archive.repack({"TXT1": "A much longer subtitle", "AUD1": "Voiced label"}))
        self.assertEqual(result.entries[1].text, b"A much longer subtitle")
        self.assertEqual(result.entries[0].trailing, self.voice)
        self.assertEqual([e.tag for e in result.entries], [b"AUD1", b"TXT1"])
        self.assertEqual(result.entries[0].offset, self.archive.entries[0].offset + len("A much longer subtitle") - 5)

    def test_manifest_and_cp949_byte_encoding(self):
        manifest = self.archive.manifest()
        self.assertEqual(manifest["source_sha256"], hashlib.sha256(self.original).hexdigest())
        for item in manifest["entries"]:
            if item["tag"] == "AUD1":
                item["translation"] = "한글"
        rebuilt = Rtx(import_manifest(self.archive, manifest, "cp949"))
        self.assertEqual(rebuilt.entries[0].text, "한글".encode("cp949"))
        self.assertEqual(rebuilt.entries[0].trailing, self.voice)

    def test_sha_and_invalid_codec_rejected(self):
        manifest = self.archive.manifest()
        manifest["source_sha256"] = "0" * 64
        with self.assertRaises(RtxError):
            import_manifest(self.archive, manifest, "cp437")
        with self.assertRaises(RtxError):
            self.archive.repack({"TXT1": "한글"}, "cp437")

    def test_string_boundaries(self):
        almost = "Q" * 65535
        result = Rtx(self.archive.repack({"TXT1": almost}))
        self.assertEqual(len(result.entries[-1].text), 65535)
        with self.assertRaises(RtxError):
            self.archive.repack({"TXT1": "x" * 65536})

    def test_corrupt_footer_or_index_or_audio(self):
        with self.assertRaises(RtxError):
            Rtx(self.original[:-12] + b"XXXX" + self.original[-8:])
        broken = bytearray(self.original)
        struct.pack_into("<I", broken, -8, 0xFFFFFFFF)
        with self.assertRaises(RtxError):
            Rtx(bytes(broken))
        broken = bytearray(self.original)
        voice = broken.index(b"AUD1")
        self.assertTrue(voice > 0)
        # First text record's size field is big endian.
        struct.pack_into(">I", broken, 4, 0xFFFF)
        with self.assertRaises(RtxError):
            Rtx(bytes(broken))

    def test_empty_string_is_intentional(self):
        manifest = self.archive.manifest()
        next(x for x in manifest["entries"] if x["tag"] == "TXT1")["translation"] = ""
        rebuilt = Rtx(import_manifest(self.archive, manifest, "cp437"))
        self.assertEqual(rebuilt.entries[-1].text, b"")


class FntTests(unittest.TestCase):
    def test_roundtrip_analysis_atlas(self):
        data = build_fnt()
        parsed = read_font(data)
        self.assertEqual(parsed["source"], data)
        self.assertEqual(parsed["count"], 2)
        self.assertEqual(parsed["glyphs"][1]["pixels"], b"\x01\x02")
        self.assertEqual(metadata(parsed)["glyphs"][1]["codepoint"], 33)
        self.assertEqual(make_png(parsed)[:8], b"\x89PNG\r\n\x1a\n")

    def test_bad_chunk_rejected(self):
        with self.assertRaises(FntError):
            read_font(build_fnt()[:-1])
        with self.assertRaises(FntError):
            read_font(build_fnt().replace(b"FBMP", b"WRNG", 1))

    def test_replace_one_glyph_preserves_others(self):
        font = read_font(build_fnt())
        data = replace_glyph(font, 33, {"width": 2, "height": 2, "pixels": [1, 0, 3, 5], "offset_left": 2, "offset_top": 1})
        new = read_font(data)
        self.assertEqual(new["glyphs"][0], font["glyphs"][0])
        self.assertEqual(new["glyphs"][1]["pixels"], b"\x01\x00\x03\x05")
        self.assertEqual(new["palette"], font["palette"])
        with self.assertRaises(FntError):
            replace_glyph(font, 256, {"width": 1, "height": 1, "pixels": [1]})


class EncodingTests(unittest.TestCase):
    def test_hangul_composition_metrics(self):
        self.assertEqual(decompose_syllable("가"), (0, 0, 0))
        self.assertEqual(decompose_syllable("각"), (0, 0, 1))
        self.assertEqual(decompose_syllable("힣"), (18, 20, 27))
        data = report(["한글 A!", "한글"])
        self.assertEqual(data["unique_hangul_syllables"], 2)
        self.assertEqual(data["hangul_occurrences"], 4)
        self.assertEqual(data["cp949_total_bytes"], len("한글 A!".encode("cp949")) + len("한글".encode("cp949")))


if __name__ == "__main__":
    unittest.main()
