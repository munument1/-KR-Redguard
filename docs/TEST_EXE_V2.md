# 두 번째 시험본: 자막 경로 보완 및 UI·인트로 번역

**후속 수정:** 모든 한글이 고정 색으로 표시되는 문제를 보완했다. 현재 실행 파일은 [세 번째 시험본](TEST_EXE_V3_COLORS.md)을 사용한다.

2026-10-13. 사용자가 첫 시험본에서 **UI·인트로 영문 유지, 인게임 자막이 발음기호처럼 깨짐**을 보고했다. 첫 시험본을 한글 출력 성공본으로 취급하지 않는다. 기존 격리 검사는 패치한 두 진입점만 직접 호출했으므로 일반 게임 텍스트 경로의 연결 누락을 검출하지 못했다.

## 새 실행 파일

`output/engine_utf8/playtest_v2b_20261013/Play Korean Test.cmd`

첫 시험본과 다른 폴더다. 이전 DOSBox를 종료한 뒤 위 CMD를 실행한다. Steam 원본이나 첫 시험본에 파일을 덮어쓰지 않았다. 새 복사본은 원본 설치본의 저장 파일에서 시작하며, 첫 시험본에서 새로 저장한 파일은 자동 이동하지 않았다.

## 바꾼 부분

- 일반 텍스트 함수 `0x185FF`, `0x1885D`, `0x182AF`의 원본 포맷 처리 이후 지점에 UTF-8 그리기를 연결했다. 원본 포맷 문자열 및 가변 인자 처리를 유지한다. ASCII 경로는 기존 루프로 돌아간다.
- 일반 너비 계산 `0x18FBF`의 포맷 처리 이후와 단어 너비 `0x190D1`도 연결했다. 기존 메뉴 그리기·너비 후크와 합쳐 **7개 후크**, 신규 런타임 fixup **14건**이다.
- `MENU.INI`의 메뉴·옵션·조작 문구 **47곳**을 한국어로 바꿨다.
- `movie0_text[0..71]`의 인트로 자막 **72곳**을 번역했다. 원래 6개 메타데이터 필드(플래그·RGB·시작/끝 프레임)는 유지했다. 레스트리스 연맹 등 명칭은 RTX 초안과 맞췄다.
- `KEYS.INI`의 키 표시 및 안내 **21곳**을 번역했다. 실제 키 바인딩 번호는 변경하지 않았다.
- 추가 문구에 필요한 **9개 글리프**를 보충해 시험 팩은 **1,215글리프**가 됐다. 네이티브 INI의 비ASCII 고유 문자 **354종** 전체가 팩에 존재함을 확인했다.
- `ITEM.INI`의 이름·설명 필드는 RTX 식별자다. 이를 한국어 문장으로 덮어쓰지 않았다.

## 이번에 검증한 경로

첫 시험본과 같은 메뉴용 진입점 검사에 더해, 원본 일반 텍스트 함수 세 곳과 원본 일반 너비 함수에 **실제 `%s` 형식과 가변 인자 스택**을 전달했다. C 라이브러리 포맷·할당·해제는 검사 하네스가 제공했고, 원본 함수의 진입·스택 구성·후크·후처리와 실제 비트맵 렌더러는 기계어로 실행했다.

그 결과 문장 너비 일치, 일반 경로 **38글리프** 출력, 전체 640×480 프레임버퍼 바이트 일치를 확인했다. 기존 메뉴 경로 검사 **34글리프**도 통과했다. 자동 테스트 **53개 통과**. INI의 동영상 타이밍 보존, 누락·중복 자막 거부, 키 바인딩 보존 및 UTF-8 단어 너비 검사를 추가했다.

실제 게임의 자막 호출자를 포함한 전체 실행·원본 C 라이브러리·INI 적재·동영상 재생은 에뮬레이터 검사에 포함하지 않았다. 따라서 사용자 환경에서 자막 깨짐이 해결됐다고 아직 단정하지 않는다.

## 남은 범위

- 실제 게임에서 새 메뉴·인트로·대화 자막 표시 재확인.
- 자막·동영상의 기존 바이트 기반 줄 분할, 화면별 폰트 크기·색상·클리핑·그림자 처리.
- 실행 파일에 하드코딩된 일부 UI 문구. `MENU.INI`에 있는 문구만 이번에 번역했다.
- 인트로 외 동영상 `movie1..4`는 아직 영문이다.

## 재현과 기록

```powershell
python tools/patch/native_ini_ko.py --source '<원본 설치본>/Redguard' --output output/engine_utf8/native_ini_next
python tools/patch/build_test_exe.py --exe '<원본 설치본>/Redguard/RG.EXE' --font-pack output/engine_utf8/font_v2/redsel_unicode_prototype.kgf --output output/engine_utf8/playtest_next
python tools/encoding/engine_render_probe.py --exe output/engine_utf8/playtest_next/RG.EXE --font-pack output/engine_utf8/font_v2/redsel_unicode_prototype.kgf --check-text-hooks --check-general-text --output output/engine_utf8/playtest_next/general_probe
python tools/patch/prepare_playtest.py --installation '<원본 설치본>' --build output/engine_utf8/playtest_next --rtx output/engine_utf8/test_assets/ENGLISH.RTX --native-ini output/engine_utf8/native_ini_next
```

현재 시험 폴더의 `general_probe/render_probe_report.json`, `menu_probe/render_probe_report.json`, `build_report.json`, `playtest_manifest.json`에 검사 범위와 해시를 보관한다. 원본 EXE·RTX·MENU.INI·KEYS.INI는 작업 전후 동일하다. 게임·폰트 산출물은 계속 Git 제외 경로에만 있다.
