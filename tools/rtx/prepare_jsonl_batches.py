"""Split the local Redguard RTX translation manifest into reviewable JSONL batches.

No game installation files are touched. Output is kept under the ignored
``output/`` folder; batches contain copyrighted game dialogue and are local.

Example:
    python tools/rtx/prepare_jsonl_batches.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "output" / "ENGLISH.urp-source.json"
DEFAULT_DEST = ROOT / "output" / "text_translation"


def prepare(source: Path, dest: Path, batch_size: int = 100) -> dict:
    if batch_size < 1:
        raise ValueError("batch size must be positive")
    raw = source.read_bytes()
    manifest = json.loads(raw.decode("utf-8"))
    if manifest.get("format") != "redguard-rtx-translation-v1":
        raise ValueError("unexpected RTX translation manifest format")
    records = manifest.get("entries")
    if not isinstance(records, list) or not records:
        raise ValueError("RTX manifest does not contain entries")
    tags = [row.get("tag") for row in records]
    if len(set(tags)) != len(tags) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("duplicate or invalid RTX tags")

    # Do not overwrite work already performed in any of the JSONL batches.
    dest.mkdir(parents=True, exist_ok=True)
    if list(dest.glob("rtx_*.jsonl")):
        raise FileExistsError(f"Existing JSONL batches in {dest}; refusing to overwrite translations")

    batches = []
    for start in range(0, len(records), batch_size):
        end = min(start + batch_size, len(records))
        filename = f"rtx_{start + 1:04d}_{end:04d}.jsonl"
        target = dest / filename
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            for idx in range(start, end):
                row = records[idx]
                exported = {
                    "index": idx,
                    "tag": row["tag"],
                    "kind": row.get("kind"),
                    "original": row.get("original"),
                    "translation": row.get("translation"),
                }
                if row.get("corrected_by_urp") is True:
                    exported["corrected_by_urp"] = True
                handle.write(json.dumps(exported, ensure_ascii=False) + "\n")
        batches.append({"file": filename, "first": start + 1, "last": end, "count": end - start})

    index = {
        "format": "redguard-rtx-jsonl-batches-v1",
        "source_manifest": source.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_rtx_sha256": manifest["source_sha256"],
        "total": len(records),
        "batch_size": batch_size,
        "urp_corrections": sum(row.get("corrected_by_urp") is True for row in records),
        "initial_translated": sum(row.get("translation") is not None for row in records),
        "batches": batches,
        "note": "Keep the canonical source JSON; merge translations back by tag and validate before RTX packing.",
    }
    (dest / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    result = prepare(args.source, args.output, args.batch_size)
    print(f"Prepared {result['total']} records in {len(result['batches'])} JSONL batches: {args.output}")


if __name__ == "__main__":
    main()
