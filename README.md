# The Elder Scrolls Adventures: Redguard 한국어화 연구

1998년 원본 PC판의 대사·메뉴·아이템·서적·영상 자막을 한국어로 표시하기 위한 기반 작업입니다.

**현재 상태:** RTX 4,866건의 번역 전수 검수를 마쳤습니다. 검수본과 메뉴 대비 수정을 반영한 **한국어 패치 0.1.0 초기 공개판**을 제공합니다. Windows 패처에서 설치·복원할 수 있습니다. [다운로드](https://github.com/munument1/-KR-Redguard/releases/tag/v0.1.0) · [설치 방법·지원 범위](docs/RELEASE_0_1_0.md).

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

- [한국어 시험 EXE 실행과 검증 범위](docs/TEST_EXE.md)

- [로컬 작업 폴더 및 파일 안내](docs/WORKSPACE_STATUS.md)

- [참조한 외부 소스](docs/RESEARCH_SOURCES.md)
- [엔진 및 표시 영역](docs/ENGINE_ANALYSIS.md)
- [FNT 제한 및 글리프 분석](docs/FONT_ANALYSIS.md)
- [RTX 포맷과 길이 검증](docs/RTX_ANALYSIS.md)
- [한글 인코딩 전략](docs/ENCODING_STRATEGY.md)
- [Software 엔진 UTF-8 지원 조사](docs/UTF8_ENGINE_FINDINGS.md)
- [UTF-8 런타임·배포 패처 개발 현황](docs/UTF8_PATCHER_DEVELOPMENT.md)
- [유니코드 글리프·줄바꿈 코어 구현](docs/UNICODE_GLYPHS_AND_WRAPPING.md)
- [원본 비트맵 렌더러 격리 연결 검사](docs/ORIGINAL_RENDERER_INTEGRATION.md)
- [검증 현황 및 다음 단계](docs/IMPLEMENTATION_PLAN.md)
- [Unofficial Redguard Patch + Coyle 수정 통합](docs/UNOFFICIAL_PATCH_INTEGRATION.md)
- [텍스처 한글화 준비: 목록·추출·검수](docs/TEXTURE_LOCALIZATION.md)

**서체 구분:** 솔뫼 김대건체는 텍스처에 포함된 고정 문구 번역에만 사용합니다. 실제 게임 텍스트(FNT)의 한글 글꼴은 별도로 선정할 예정입니다.

### Unofficial Redguard Patch 연동 (개인 로컬용)

작업 폴더에 있는 원본 URP 1.03 ZIP과 Redguard Mod Manager JAR를 사용해 Coyle의 Hayle 대화 조건을 보완한 합본을 만들 수 있습니다. 원본 모드 데이터는 공개 Git에 포함되지 않습니다.

```powershell
$urp = 'Unofficial Redguard Patch-11-1-03-1777266218.zip'
python tools/patch/build_urp_coyle.py --source $urp --game $game --jar 'Redguard Mod Manager.jar'
python tools/patch/seed_urp_translations.py --urp $urp --rtx "$game/ENGLISH.RTX"
```

원본 URP의 **대사 78건, 영화 자막 6건**의 교정을 우리 번역 원문에 반영합니다. 스크립트 수정과 설치법·저작권 제한은 [통합 문서](docs/UNOFFICIAL_PATCH_INTEGRATION.md)를 참고하세요.

이 저장소의 도구는 자체 구현이며, 타인의 게임 파일·번역 파일 또는 폰트를 포함하지 않습니다. 자료의 출처와 라이선스를 각 문서에 기록했습니다.
