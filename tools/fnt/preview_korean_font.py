"""Compare a locally selected Korean font with original REDSEL bitmap text.

This produces design previews only. It does not change the game or font pack.
"""
from pathlib import Path
import json
import runpy

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[2]


def main():
    output = ROOT / 'output/font_selection'
    face = output / 'NotoSerifKR-SemiBold-prototype.ttf'
    original = Path('C:/Games/Steam/steamapps/common/The Elder Scrolls Adventures Redguard/Redguard/fonts/REDSEL.FNT')
    parser = runpy.run_path(str(ROOT / 'tools/fnt/fnt_tool.py'))['read_font']
    font = parser(original.read_bytes())
    palette = [tuple(min(channel * 4, 255) for channel in font['palette'][i:i+3]) for i in range(0, 768, 3)]
    canvas = Image.new('RGB', (640, 430), (25, 27, 31))
    pen = ImageDraw.Draw(canvas)
    label_font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 13)
    pen.text((16, 12), '레드가드 한글 폰트 시안 · 게임 화면 캡처 아님', font=label_font, fill='white')
    pen.text((16, 38), '원본 REDSEL 비트맵', font=label_font, fill=(180, 190, 200))
    x, y = 18, 62
    for char in 'CYRUS: I NEED TO SPEAK WITH GOVERNOR RICHTON.':
        glyph = font['glyphs'][ord(char) - font['start']]
        im = Image.new('RGBA', (glyph['width'], glyph['height']))
        im.putdata([(*palette[value], 255) if value else (0, 0, 0, 0) for value in glyph['pixels']])
        canvas.paste(im, (x + glyph['offset_left'], y + glyph['offset_top']), im)
        x += glyph['width'] + 1 + (font['glyphs'][1]['width'] if char == ' ' else 0)
    samples = [('선택안: Noto Serif KR 600 · 20px / 행간 26px', face, 20, 120),
               ('작은 크기: 같은 서체 · 14px / 행간 16px', face, 14, 224),
               ('가독성 비교: Noto Sans KR Regular · 20px', Path('C:/Windows/Fonts/NotoSansKR-Regular.ttf'), 20, 314)]
    text = ['사이러스: 리히튼 총독을 만나야겠어.', '훈딩 만에서 이자라의 행방을 찾아야 해.']
    for label, path, size, top in samples:
        pen.text((16, top), label, font=label_font, fill=(180, 190, 200))
        raster = ImageFont.truetype(str(path), size)
        for line, string in enumerate(text):
            mask = Image.new('L', (608, 32), 0)
            ImageDraw.Draw(mask).text((2, 0), string, font=raster, fill=255, anchor='lt')
            mask = mask.point(lambda value: 255 if value >= 128 else 0)
            edge = mask.filter(ImageFilter.MaxFilter(3))
            at = (16, top + 26 + line * (26 if size == 20 else 16))
            canvas.paste(palette[195], at, edge)
            canvas.paste(palette[81], at, mask)
    pen.text((16, 408), '실제 크기 640×430 · 아래 확대본은 픽셀을 그대로 2배 표시', font=label_font, fill=(180, 190, 200))
    canvas.save(output / 'font_comparison_native.png')
    canvas.resize((1280, 860), Image.Resampling.NEAREST).save(output / 'font_comparison_2x.png')
    (output / 'selection.json').write_text(json.dumps({
        'family': 'Noto Serif KR', 'weight': 600, 'status': 'visual proposal; not installed in game',
        'large_size': 20, 'small_size': 14, 'colors': {'face_index':81, 'outline_index':195},
        'outline': 'one pixel dilation for preview only; current runtime pack is unchanged',
        'notes': ['KimDaeGeon remains texture-only', 'No game hook or executable produced by this tool']
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Created original / serif / sans comparison PNGs')


if __name__ == '__main__':
    main()
