"""Translate displayed MENU/KEYS values without changing keys or movie timing.

Writes UTF-8 without BOM to a separate output directory. ITEM.INI names are
RTX identifiers and must NOT be translated as literal display strings.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

LABELS = dict(zip(
    ['SAVE', 'LOAD', 'NEW', 'OPTIONS', 'MOVIES', 'CONTINUE', 'QUIT', 'SAVE GAME', 'LOAD GAME',
     'INTRODUCTION', 'RESTLESS LEAGUE', 'ISZARA RESTORED', 'SWORD OF CROWN', 'ENDING', 'MAIN PAGE',
     'DISPLAY', 'SOUND', 'CONTROLS', 'SCREEN SIZE', 'RESOLUTION', 'GAMMA', 'SUBTITLES',
     'MOVIE INTERLACE', 'OPTIONS PAGE', 'SOUND VOLUME', 'MUSIC VOLUME', 'VOICE', 'FORWARD',
     'BACK', 'LEFT', 'RIGHT', 'USE', 'VIEW', 'JUMP', 'WALK', 'ITEMS', 'MAP', 'LOG', 'SWORD',
     'HEALTH', 'NEXT', 'PREV'],
    ['저장', '불러오기', '새 게임', '설정', '동영상', '계속하기', '종료', '게임 저장', '게임 불러오기',
     '도입부', '레스트리스 연맹', '이자라의 귀환', '크라운의 검', '결말', '주 메뉴',
     '화면', '소리', '조작', '화면 크기', '해상도', '밝기', '자막',
     '영상 주사 방식', '설정 메뉴', '효과음 크기', '음악 크기', '음성', '앞으로',
     '뒤로', '왼쪽', '오른쪽', '사용', '시점', '점프', '걷기', '소지품', '지도', '일지', '검',
     '회복', '다음', '이전']))

INTRO = [
    '제2시대 말기, 전쟁의 시대였다.',
    '타이버 셉팀의 제국은 탐리엘의 왕국들을 휩쓸며',
    '영광스러운 정복을 향해 나아갔다.',
    '셉팀은 사방에서 저항에 부딪혔으나, 가장 거세게 맞선 곳은 해머펠이었다.',
    '레드가드의 조상 대대로 내려온 고향이었다.',
    '해머펠의 대왕 타사드 2세는',
    '다른 왕국들이 무너지는 와중에도 제국의 침공에 저항했다.',
    '그러나 마침내, 예고도 궁정의 음모도 없이',
    '죽음이 그를 찾아왔다.',
    '대왕을 잃은 해머펠은 힘을 잃고',
    '조국의 주권을 지키려는 크라운과',
    '황제의 지배를 받아들인 포어베어 사이의 피비린내 나는 내전에 빠졌다.',
    '타사드의 후계자 아토르 왕자가 이끄는 크라운은 거듭 승리하며',
    '해머펠의 모래 위에 포어베어의 피를 쏟았다.',
    '항구 도시 스트로스 므카이를 거점으로',
    '아토르 왕자는 분열된 아버지의 왕국을 서서히 통합해 나갔다.',
    '패배가 다가옴을 느낀 포어베어는 황제와 협정을 맺었다.',
    '제국군을 끌어들여 크라운을 무너뜨리고 해머펠을 황제에게 넘긴 것이다.',
    '타이버 셉팀의 군대는 자긍심 높은 레드가드 크라운이 감당하기에 너무 강했다.',
    '타이버 셉팀은 최고의 지휘관 리히튼 경을 스트로스 므카이로 보내 왕자와 크라운을 압박했다.',
    '왕자는 마지막 항전을 위해 병력을 집결시켰다.',
    '해머펠의 주권이 걸렸음을 아는 크라운 병사들은 제국군에 당당히 맞서',
    '스트로스 므카이 항구에서 최후의 전투를 벌였다.',
    '전투는 치열했다. 왕자의 해전 승리를 이미 목격한 리히튼 경은',
    '마지막 수단을 꺼내 들었다.',
    '제국 왕관의 자랑스러운 보석, 용 나팔릴라르구스였다.',
    '아토르는 궁수들에게 무기를 준비하라 명령했지만',
    '리히튼의 암살자가 쏜 화살에 쓰러졌다.',
    '화살의 독은 걷잡을 수 없이 퍼졌다.',
    '왕자의 마법사가 그를 구하려 했으나, 용은 그 마법과 크라운의 승리를 향한 희망을',
    '단 한 번의 불길로 끝내 버렸다.',
    '크라운을 정복한 황제의 군대는 해머펠 전역에 대한 지배를 선포했다.',
    '모든 도시에 제국군이 주둔했고, 리히튼은 스트로스 므카이의 임시 총독으로 임명되었다.',
    '몇 달이 흘렀다. 크라운과 포어베어를 막론하고 해머펠의 레드가드들은',
    '제국의 새로운 지배에 적응했고, 타이버 셉팀은 탐리엘의 나머지 땅으로 세력을 뻗쳤다.',
    '이 모든 일이 우리의 영웅 사이러스와 얽히게 된 것은 운명의 장난이었다.',
    '그는 오래전 해머펠을 떠나 제국의 변경을 떠돌던 레드가드였다.',
    '웃어, 사이러스. 자네가 찾던 구실이 여기 있으니.',
    '짧게 끝내자, 스라스라. 할 일이 있어.',
    '용병들은 하나같이 똑같군.',
    '앉아.',
    '한 시간 뒤에 두아딘의 부하들과 떠나야 해.',
    '제국의 돈을 두둑이 챙긴 건달들이 밤중에 가난한 농부를 쫓는 일이지. 왕국에 아내를 빚진 농부 말이야.',
    '잘 아네. 네가 구해 준 일이니까.',
    '이 몸이 준 일은 이 몸이 거두기도 하지. 자네 앞으로 왔어.',
    '다시는 해머펠에 돌아가지 않겠다고 한 건 스라스라도 알아. 하지만 중요한 일 같더군.',
    '봉인이 뜯겼군.',
    '스라스라는 걱정이 됐거든.',
    '그래, 그랬겠지.',
    '두아딘은 걱정 마. 스라스라가 해결해. 스라스라는 뭐든 해결하지.',
    '…이자라…',
    '누나가 사라졌다니 소름이 돋는군.',
    '배가 필요해.',
    '항구에 널렸지. 스라스라의 이름이면 뱃삯도 꽤 깎을 수 있어.',
    '돈도 필요하고.',
    '두아딘에게 받은 착수금을 가져가. 가족 일이잖아. 그런데 왜 누나 이야기를 한 번도 안 했나?',
    '십 년 동안 말을 섞지 않았어. 일이 좀 있었지.',
    '무슨 일?',
    '그녀의 남편을 죽였어.',
    '해머펠의 탕아 사이러스는 자신이 태어난 땅으로 돌아온다.',
    '그는 누나를 구할 희망을 품고 스트로스 므카이 섬으로 향하는 배에 오른다.',
    '이자라를.',
    '해적은 풋내기 선원들에게 말했지. 아래로 내려가라.',
    '이 화물은 레스트리스 연맹이 접수한다.',
    '다른 자가 잔인하리만치 또렷한 목소리로 말했지.',
    '이럴 시간이 없다고 해도 달라질 건 없겠지.',
    '레드가드의 명예가 걸린 일이다, 애송이. 비켜라.',
    '그래, 해적질과 정치라니 의심스러운 조합이지만, 현실이 그렇다네.',
    '정치엔 별 관심 없어. 내 시절엔 해적질도 정직한 일이었지.',
    '영웅 노릇 하지 마라, 애송이.',
    '그걸로 돈이 되나?',
    '그래, 그의 용기에 감탄하긴 했지. 아주 잠깐 동안은…',
]

KEY_LABELS = {'empty': '미지정', 'left mouse': '마우스 왼쪽', 'right mouse': '마우스 오른쪽',
              'mouse x': '마우스 가로', 'mouse y': '마우스 세로', 'kbd up': '위 화살표',
              'kbd down': '아래 화살표', 'kbd left': '왼쪽 화살표', 'kbd right': '오른쪽 화살표',
              'joy left': '조이스틱 왼쪽', 'joy right': '조이스틱 오른쪽',
              'joy up': '조이스틱 위', 'joy down': '조이스틱 아래', 'space': '스페이스',
              'l shift': '왼쪽 Shift', 'r shift': '오른쪽 Shift'}


def translate_menu(raw):
    text = raw.decode('ascii')
    counts = {'ui': 0, 'intro': 0}
    found_intro = set()
    result = []
    for line in text.splitlines(keepends=True):
        match = re.match(r'(text\[\d+\]\s*=\s*)([^\r\n]*)(\r?\n|$)', line)
        movie = re.match(r'(movie0_text\[(\d+)\]\s*=\s*)([^\r\n]*)(\r?\n|$)', line)
        if match and match[2].strip() in LABELS:
            line = match[1] + LABELS[match[2].strip()] + match[3]
            counts['ui'] += 1
        elif movie:
            index = int(movie[2])
            parts = movie[3].split(',', 6)
            if len(parts) != 7 or not 0 <= index < len(INTRO) or index in found_intro:
                raise ValueError('unexpected intro schema')
            line = movie[1] + ','.join(parts[:6]) + ',' + INTRO[index] + movie[4]
            found_intro.add(index)
            counts['intro'] += 1
        result.append(line)
    if found_intro != set(range(len(INTRO))):
        raise ValueError('incomplete intro source')
    return ''.join(result).encode('utf-8'), counts


def translate_keys(raw):
    result, count = [], 0
    for line in raw.decode('ascii').splitlines(keepends=True):
        match = re.match(r'((?:key\[\d+\]|waiting_message)\s*=\s*)([^\r\n]*)(\r?\n|$)', line)
        if match:
            value = match[2].strip()
            translated = '키를 누르세요' if value == 'HIT KEY' else KEY_LABELS.get(value)
            if value.startswith('button '):
                translated = '버튼 ' + value[7:]
            if translated:
                line = match[1] + translated + match[3]
                count += 1
        result.append(line)
    return ''.join(result).encode('utf-8'), count


def build(source, output):
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError('use a separate output directory')
    menu, counts = translate_menu((source / 'MENU.INI').read_bytes())
    keys, key_count = translate_keys((source / 'KEYS.INI').read_bytes())
    output.mkdir(parents=True, exist_ok=True)
    for name, data in [('MENU.INI', menu), ('KEYS.INI', keys)]:
        with (output / name).open('xb') as f:
            f.write(data)
    report = {**counts, 'key_labels': key_count, 'encoding': 'utf-8 without BOM',
              'remaining_movies_untranslated': [1, 2, 3, 4],
              'outputs': {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                          for name in ['MENU.INI', 'KEYS.INI']}}
    (output / 'native_ini_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))
