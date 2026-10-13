"""Count Hangul codepoints and compare byte budgets for a future engine PoC."""

from collections import Counter
import argparse
import json
from pathlib import Path


def decompose_syllable(ch: str) -> tuple[int, int, int]:
    value = ord(ch) - 0xAC00
    if not 0 <= value < 11172:
        raise ValueError("only precomposed modern Hangul syllables are supported")
    return value // 588, (value % 588) // 28, value % 28


def report(texts: list[str]) -> dict:
    text = "".join(texts)
    syllables = Counter(ch for ch in text if 0xAC00 <= ord(ch) <= 0xD7A3)
    components = [decompose_syllable(ch) for ch in syllables]
    cp949_sizes = []
    for item in texts:
        try:
            cp949_sizes.append(len(item.encode("cp949")))
        except UnicodeEncodeError:
            cp949_sizes.append(None)
    return {
        "text_count": len(texts),
        "hangul_occurrences": sum(syllables.values()),
        "unique_hangul_syllables": len(syllables),
        "unique_choseong": len({row[0] for row in components}),
        "unique_jungseong": len({row[1] for row in components}),
        "unique_jongseong_including_none": len({row[2] for row in components}),
        "utf8_total_bytes": sum(len(s.encode("utf-8")) for s in texts),
        "cp949_total_bytes": None if None in cp949_sizes else sum(cp949_sizes),
        "max_entry_cp949_bytes": None if None in cp949_sizes else max(cp949_sizes, default=0),
        "most_common_hangul": syllables.most_common(20),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, help="UTF-8 RTX export with translations filled in")
    ap.add_argument("--sample", help="one mixed-language test string")
    args = ap.parse_args()
    if args.sample is None and args.manifest is None:
        ap.error("provide --sample or --manifest")
    texts = []
    if args.sample is not None:
        texts.append(args.sample)
    if args.manifest:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        texts.extend(x["translation"] for x in data["entries"] if isinstance(x.get("translation"), str))
    print(json.dumps(report(texts), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
