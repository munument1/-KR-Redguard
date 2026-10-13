# Software판 한국어 시험 EXE — 2026-10-13

**첫 시험본은 사용자의 인게임 검사에서 자막 깨짐이 보고됐다. 최신 실행 파일은 [두 번째 시험본 안내](TEST_EXE_V2.md)를 사용한다.** 아래는 첫 시험본의 개발 기록이다.

**로컬 실행용 복사본을 만들었다. 실제 DOS 시작 및 게임 플레이는 아직 검증하지 않았다.** 사용자 요청에 따라 게임 실행은 사용자가 직접 한다.

## 실행

작업 폴더의 다음 파일을 더블클릭한다.

`output/engine_utf8/playtest_20261013/Play Korean Test.cmd`

이 CMD는 같은 폴더의 `game/DOSBox-0.73`을 작업 디렉터리로 설정하고 복제된 DOSBox와 `rg.conf`로 **Software RG.EXE**를 실행한다. Windows에서 RG.EXE를 직접 실행하지 않는다. Steam 설치본과 별도의 게임 복사본이며, 저장 게임도 복사본 내부에 기록된다. 약 1.4GB의 설치 파일을 로컬 복사했다.

첫 실행에서는 시작 화면 진입, 새 게임이나 기존 저장 불러오기, 대화 자막의 한글 표시를 확인한다. 오류가 나면 오류 문구와 발생 시점, 글자가 깨지면 해당 화면과 대사를 기록한다. 긴 대사의 줄바꿈, 작은 글꼴 화면의 크기, 그림자·클리핑·확대 출력은 후속 확인 대상이다.

## 적용 내용과 한계

- 원본 Software RG.EXE의 문자열 그리기 `0x76E98`와 너비 계산 `0x77185` 진입점을 새 x86 코드로 연결했다.
- ASCII만 있는 문자열은 원본 함수로 돌아간다. 비ASCII 바이트를 포함한 문자열은 bounded UTF-8 디코더와 KGF1 이진 검색을 사용한다.
- LE 다섯 번째 오브젝트에 어댑터 **815바이트**와 선택했던 Noto Serif KR 600 시험 팩 **1,206글리프**를 넣었다. 별도 KGF 파일 복사나 런타임 파일 열기가 필요 없다.
- 행 높이는 빌드 시 **27px**로 계산한다. 출력 경로에는 전체 폰트 순회·폰트 재적재·시험 문구 출력이 없다.
- 혼합 문자열에는 하나의 REDSEL 기반 시험 폰트를 사용한다. 화면별 폰트 선택·색상 전환·작은 글꼴 대응은 완료하지 않았다. 기존 노란색·붉은 테두리 디자인 시안을 적용한 결과도 아니다.
- **원본의 바이트 단위 자막 분할 코드는 아직 교체하지 않았다.** 긴 대사는 UTF-8 중간에서 잘리거나 줄 배치가 어긋날 수 있다. 별도로 개발한 유니코드 줄바꿈 코어를 연결해야 한다.
- `RG3DFX` 및 Glide판용 패치가 아니다. 메뉴·아이템·영상 등 모든 표시 경로를 한국어화한 완성본도 아니다.
- 한국어 RTX 초안 **4,866건**, 보존한 음성 **3,933건**을 복사본에 배치했다. 번역 검수 완료를 의미하지 않는다.

## 검증

- 자동 테스트 **49개 통과**. 독립적인 오브젝트 주소 재배치, 원본 호출 규약·레지스터·스택 보존, 혼합 UTF-8, 누락 글리프·잘린 입력, 중앙·우측 정렬, 확대 호출 인자, LE 페이지를 걸치는 fixup 등을 포함한다.
- 실제 생성한 EXE의 LE 페이지와 fixup을 에뮬레이터에 적재했다. 패치한 문자열 함수에 UTF-8 문장 두 개를 전달하고 원본 비트맵 렌더러를 실행했다. 너비 계산 일치, **34글리프 출력**, 전체 **640×480 프레임버퍼 바이트 일치**를 확인했다.
- 원본 4개 오브젝트와 기존 fixup을 유지하고 원본 코드에서는 두 진입점의 각 5바이트만 변경했음을 검사했다. 새 런타임 fixup은 5건, 기존 코드의 후크 fixup은 2건이다. XVER 트레일러도 유지했다.
- 원본 설치본 EXE·RTX의 작업 전후 SHA-256이 일치했다.
- 에뮬레이터 검사에서는 DOS 시작·파일 시스템·게임 상태를 재현하지 않았다. selector fixup 2건은 격리 검사에서 적용하지 않는다. 실행 파일의 실제 DOS 적재 성공을 대신하는 검사가 아니다.

LE 구조는 [Open Watcom의 LE/LX 정의](https://github.com/open-watcom/open-watcom-v2/blob/master/bld/watcom/h/exeflat.h)를 참조했다.

## 산출물

| 경로 | 내용 |
| --- | --- |
| `output/engine_utf8/playtest_20261013/RG.EXE` | 시험 EXE 단독 산출물 |
| `output/engine_utf8/playtest_20261013/game/Redguard/RG.EXE` | 실제 실행용 복사본의 시험 EXE |
| `output/engine_utf8/playtest_20261013/game/Redguard/ENGLISH.RTX` | UTF-8 한국어 초안 |
| `output/engine_utf8/playtest_20261013/build_report.json` | EXE·폰트 해시, 연결 지점, 제약 |
| `output/engine_utf8/playtest_20261013/playtest_manifest.json` | 원본·복사본 EXE/RTX 해시 |
| `output/engine_utf8/playtest_20261013/probe/` | 실제 패치 진입점의 에뮬레이터 검증 기록과 이미지 |
| `output/engine_utf8/playtest_20261013/original_files/` | 복사본 복구용 원본 EXE·RTX 쌍 |

복사본을 원문으로 되돌릴 때는 DOSBox를 종료한 후 `original_files/`의 두 파일을 모두 `game/Redguard/`에 복사한다. Steam 원본에 파일을 넣을 필요가 없다. 모든 게임 복사본·글리프 팩은 Git 제외 경로에 있으며 공개 배포용 자료가 아니다. 배포 패처의 `game_verified`는 여전히 **false**다.

## 재현

새 출력 폴더를 선택한다. 기존 시험 EXE를 덮어쓰지 않는다.

```powershell
python tools/patch/build_test_exe.py --exe 'C:\Games\Steam\steamapps\common\The Elder Scrolls Adventures Redguard\Redguard\RG.EXE' --font-pack output/engine_utf8/test_serif600_20261013/redsel_unicode_prototype.kgf --output output/engine_utf8/playtest_next
python tools/encoding/engine_render_probe.py --exe output/engine_utf8/playtest_next/RG.EXE --font-pack output/engine_utf8/test_serif600_20261013/redsel_unicode_prototype.kgf --check-text-hooks --output output/engine_utf8/playtest_next/probe
python tools/patch/prepare_playtest.py --installation 'C:\Games\Steam\steamapps\common\The Elder Scrolls Adventures Redguard' --build output/engine_utf8/playtest_next --rtx output/engine_utf8/test_assets/ENGLISH.RTX
python -m unittest discover -s tests -q
```
