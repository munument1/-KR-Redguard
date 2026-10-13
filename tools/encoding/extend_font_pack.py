"""Add missing reviewed characters while preserving every tested glyph."""
import argparse
import json
from pathlib import Path
import shutil

from unicode_font import Glyph, pack, unpack


def extend(base, drafts, ttf, output):
    from PIL import Image, ImageDraw, ImageFont
    from fontTools.ttLib import TTFont
    glyphs = unpack(base.read_bytes())
    existing = {g.scalar for g in glyphs}
    rows = [json.loads(line) for path in sorted(drafts.glob('rtx_*_ko.jsonl'))
            for line in path.read_text(encoding='utf-8').splitlines()]
    if not rows:
        raise ValueError('No translations')
    missing = {ord(c) for row in rows for c in row['translation']} - existing - {9, 10, 13}
    if any(cp < 32 for cp in missing):
        raise ValueError('Unsupported control character')
    with TTFont(ttf) as font:
        if not missing <= font.getBestCmap().keys():
            raise ValueError('Source font lacks required characters')
    face = ImageFont.truetype(str(ttf), 20)
    for cp in sorted(missing):
        char = chr(cp)
        box = face.getbbox(char)
        width, height = box[2] - box[0], box[3] - box[1]
        image = Image.new('L', (width, height))
        ImageDraw.Draw(image).text((-box[0], -box[1]), char, font=face, fill=255)
        pixels = bytes(195 if alpha >= 128 else 0 for alpha in image.tobytes())
        glyphs.append(Glyph(cp, width, height, box[0], 3, round(face.getlength(char)) + 1, pixels))
    output.mkdir(parents=True, exist_ok=False)
    (output / base.name).write_bytes(pack(glyphs))
    shutil.copy2(base.parent / 'palette.json', output / 'palette.json')
    return {'added': [f'U+{cp:04X}' for cp in sorted(missing)], 'glyphs': len(glyphs)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--drafts', type=Path, required=True)
    parser.add_argument('--font', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(extend(args.base, args.drafts, args.font, args.output)))
