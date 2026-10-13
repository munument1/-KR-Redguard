"""Synthetic asset tests; neither installation nor game content is needed."""

import csv
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.texture.texture_workflow import classify, extract, inventory, sheets, write_inventory


class TextureWorkflowTests(unittest.TestCase):
    def test_classification_and_sorted_csv(self):
        self.assertEqual(classify("TEXBSI.302")[0], "texbsi")
        self.assertEqual(classify("TEXTURE.012")[0], "texture_software")
        self.assertEqual(classify("menu.GXA")[0], "gxa")
        self.assertEqual(classify("gui.lbm")[0], "lbm")
        self.assertEqual(classify("gui.anm")[0], "anm")
        self.assertEqual(classify("SKY_61.PCX")[0], "pcx")
        self.assertEqual(classify("ISLAND.COL")[0], "palette")
        self.assertEqual(classify("ENGLISH.RTX"), None)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "assets"
            (root / "3dart").mkdir(parents=True)
            (root / "fonts").mkdir()
            (root / "output").mkdir()
            (root / "3dart" / "TEXBSI.302").write_bytes(b"sample")
            (root / "fonts" / "REDSEL.FNT").write_bytes(b"dummy")
            (root / "output" / "ignored.GXA").write_bytes(b"dummy")
            rows = inventory(root)
            self.assertEqual({x["path"] for x in rows}, {"3dart/TEXBSI.302", "fonts/REDSEL.FNT"})
            dest = Path(temp) / "inventory.csv"
            write_inventory(root, dest)
            with dest.open(encoding="utf-8-sig", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 2)
            self.assertIn("candidate_for_text", csv_rows[0])

    def test_sheet_images_and_review_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root, output = Path(temp) / "exported", Path(temp) / "review"
            root.mkdir()
            Image.new("RGB", (64, 64), (10, 20, 30)).save(root / "poster.png")
            Image.new("RGB", (16, 16), (40, 50, 60)).save(root / "sign.png")
            total = sheets(root, output, per_sheet=1)
            self.assertEqual(total, 2)
            self.assertTrue((output / "texture_sheet_001.png").is_file())
            self.assertTrue((output / "texture_sheet_002.png").is_file())
            with (output / "texture_review.csv").open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([x["status"] for x in rows], ["ok", "ok"])

    def test_extract_never_writes_inside_game_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "assets"
            root.mkdir()
            with self.assertRaises(ValueError):
                extract(root, root / "converted", "python", None, None)


if __name__ == "__main__":
    unittest.main()
