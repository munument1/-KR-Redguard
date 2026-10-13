# The Elder Scrolls Adventures: Redguard 한국어화 연구

1998년 원본 PC판의 대사·메뉴·아이템·서적·영상 자막을 한국어로 표시하기 위한 기반 작업입니다.

**현재 상태:** RTX 텍스트 추출·재구성 및 FNT 추출 도구 완성, 실제 Steam 게임 파일로 구조 검증 성공. **인게임 한글 출력 / 실행 파일 패치 성공은 아직 검증되지 않았습니다.**

## 실행 방법 (Python 3.10+)

아래는 PowerShell 예시입니다. `$game` 경로는 자신의 정식 게임 설치 위치로 바꾸세요.

```powershell
$game = 'C:\Games\Steam\steamapps\common\The Elder Scrolls Adventures Redguard\Redguard'
python tools/rtx/rtx_tool.py export "$game/ENGLISH.RTX" output/ENGLISH.translation.json
python tools/fnt/fnt_tool.py "$game/fonts/REDSEL.FNT" --atlas output/REDSEL.png --json output/REDSEL.json
python -m unittest discover -s tests -v
```

번역 JSON의 `entries[].translation` 필드를 수정한 후 임시 RTX를 재구성할 수 있습니다.

```powershell
python tools/rtx/rtx_tool.py pack "$game/ENGLISH.RTX" output/ENGLISH.translation.json output/ENGLISH.test.RTX
```

`translation: null`은 미번역(원문 유지), `translation: ""`은 의도적으로 빈 자막을 뜻합니다. 파일 원본 SHA256과 레코드 식별자를 검사합니다. 기본 인코딩은 기존 도구와 호환성을 고려한 `cp437`이며 한국어는 이 인코딩으로 저장할 수 없습니다. `pack --codec cp949`는 **바이너리 형식 연구용**이며, 원본 게임이 이를 출력할 수 있다는 의미가 아닙니다.

### 한글 글리프 한 슬롯 치환 PoC

실제 설치본을 수정하지 않고, `A`(코드 65)를 한글 `가` 비트맵으로 바꾼 **FNT 복제 파일**을 만들어 아틀라스로 확인합니다. 여기서 생성된 파일은 게임에 자동 설치되지 않습니다. 아래 `NotoSansKR-Regular.ttf`는 예시로, 자신이 사용 권한을 갖는 한글 폰트 파일을 선택해야 합니다. 이 작업에는 Pillow가 필요합니다.

```powershell
python -m pip install pillow
python tools/fnt/hangul_glyph.py --font 'C:\Windows\Fonts\NotoSansKR-Regular.ttf' --text 가 --size 20 --output output/ga.json
python tools/fnt/fnt_tool.py "$game/fonts/REDSEL.FNT" --replace-code 65 --glyph-json output/ga.json --write-fnt output/REDSEL_A_ga.FNT --atlas output/REDSEL_A_ga.png
python tools/encoding/hangul_report.py --sample '사이러스, 안녕하세요!'
```

원본 파일을 변경하지 않도록 출력 경로를 별도로 지정해야 합니다. `output/`은 `.gitignore`로 Git 추적에서 제외하며, 원본 게임 에셋은 저장소에 넣지 않습니다.

## 문서

- [참조한 외부 소스](docs/RESEARCH_SOURCES.md)
- [엔진 및 표시 영역](docs/ENGINE_ANALYSIS.md)
- [FNT 제한 및 글리프 분석](docs/FONT_ANALYSIS.md)
- [RTX 포맷과 길이 검증](docs/RTX_ANALYSIS.md)
- [한글 인코딩 전략](docs/ENCODING_STRATEGY.md)
- [검증 현황 및 다음 단계](docs/IMPLEMENTATION_PLAN.md)

이 저장소의 도구는 자체 구현이며, 타인의 게임 파일·번역 파일 또는 폰트를 포함하지 않습니다. 자료의 출처와 라이선스를 각 문서에 기록했습니다.
