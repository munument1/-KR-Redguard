# 세 번째 시험본: 원본 글자 색과 테두리 적용

2026-10-13. 두 번째 시험본의 한국어 글리프가 고정 팔레트 인덱스 195로 만들어져 모든 상태가 같은 색으로 표시되는 문제를 수정했다. 195는 원래 REDSEL의 붉은 테두리 색이며, 글자 본문 색으로 고정하면 안 됐다.

## 실행

`output/engine_utf8/playtest_v3_colors_20261013/Play Korean Test.cmd`

기존 시험본의 DOSBox를 종료하고 위 CMD를 실행한다. UI 47곳·인트로 72곳·키 표시 21곳의 번역 및 한국어 RTX 초안은 이전 시험본과 같다. Steam 원본과 이전 시험본은 수정하지 않았다.

## 색상 처리

- 원본 FNT 29개의 색상 계열을 추출했다. 현재 게임이 선택한 폰트의 FNHD 정보와 원본 A 비트맵 표본을 확인해 해당 색상 변환표를 적용한다. 원본 글리프 형상이 같은 계열은 팔레트 인덱스 대응을 그대로 보존한다. 형상이 다른 계열은 본문·외곽 표본으로 색을 정한다. 새 한글 획의 음영 모양까지 원본 영문과 같다는 뜻은 아니다.
- 한글 비트맵에는 본문과 1픽셀 테두리를 구분해 넣었다. 메뉴 기본·선택·비활성 색이 하나의 고정 색에 합쳐지지 않게 했다.
- REDONE·Arial 같은 단색 계열에는 추가 테두리를 적용하지 않는다. 현재 전경색 `0x123E04`를 원본 글리프 렌더러가 읽어 출력한다. 같은 글리프라도 현재 전경색이 달라지면 색이 바뀐다. 검정색 인덱스 0도 불투명 글자색으로 출력한다.
- 일반 텍스트에서는 한글 한 글자의 임시 메트릭·비트맵 포인터를 원본 렌더러 `0x34483B`에 넘긴다. 호출 후 원래 폰트 포인터를 복원한다. 원본 폰트 비트맵은 덮어쓰지 않는다.
- 메뉴 비트맵 경로에는 현재 폰트의 변환표로 색을 입힌 비트맵을 전달한다.
- 스타일 선택은 문자열 단위로 수행하고 직전 결과를 캐시한다. 캐시 확인은 32바이트 이름·A 메트릭·픽셀 표본 검사이며, 한글 슬롯 전체를 순회하지 않는다. 픽셀 변환용 64KB 버퍼와 임시 폰트 구조는 EXE에 미리 확보한다. 글자마다 파일 적재나 힙 할당을 하지 않는다.

## 검증

자동 테스트 **58개 통과**. 원본 팔레트 대응, 테두리와 전진 폭 보존, 독립 오브젝트 재배치, 혼합 영문·한글의 동일 스타일 적용, 단색 전경색과 폰트 포인터 복원을 포함한다.

생성 EXE의 실제 후크·원본 렌더러를 에뮬레이터에서 실행했다. 원본 FNT에서 가져온 이름·메트릭·A 표본으로 폰트 상태를 구성하고 다음 **86가지** 경우의 전체 화면 픽셀을 대조했다.

- 22개 다색 계열 × 일반/메뉴 출력 = 44가지.
- 7개 단색 계열 × 빨강·초록·파랑·노랑·흰색·검정 = 42가지.
- 동일한 폰트 구조 주소를 계속 재사용해 폰트 상태와 전경색을 바꿨다. 색 변경이 캐시에 가려지지 않는 것도 확인했다.

검사 이미지는 게임 캡처가 아니라 실제 에뮬레이터 프레임버퍼의 글자 부분을 잘라 배열한 것이다.

- `output/engine_utf8/playtest_v3_colors_20261013/colors_probe/native_color_summary.png`
- `output/engine_utf8/playtest_v3_colors_20261013/colors_probe/native_color_states.png`
- `output/engine_utf8/playtest_v3_colors_20261013/colors_probe/render_probe_report.json`

실제 게임의 메뉴 선택/비활성 전환 및 화자별 자막 색은 사용자 재확인 대기다. 화면별 글꼴 크기·전체 자막 줄바꿈·모든 해상도의 그림자/클리핑을 검증한 결과는 아니다. 인트로 외 동영상과 일부 하드코딩 UI는 여전히 미번역이다.

## 재현

```powershell
python tools/encoding/font_colors.py --font-dir '<원본 설치본>/Redguard/fonts' --base-pack output/engine_utf8/font_v2/redsel_unicode_prototype.kgf --output output/engine_utf8/font_colors_next
python tools/patch/build_test_exe.py --exe '<원본 설치본>/Redguard/RG.EXE' --font-pack output/engine_utf8/font_colors_next/redsel_unicode_prototype.kgf --output output/engine_utf8/playtest_colors_next
python tools/encoding/engine_render_probe.py --exe output/engine_utf8/playtest_colors_next/RG.EXE --font-pack output/engine_utf8/font_colors_next/redsel_unicode_prototype.kgf --check-text-hooks --check-general-text --color-font-dir '<원본 설치본>/Redguard/fonts' --output output/engine_utf8/playtest_colors_next/colors_probe
python tools/patch/prepare_playtest.py --installation '<원본 설치본>' --build output/engine_utf8/playtest_colors_next --rtx output/engine_utf8/test_assets/ENGLISH.RTX --native-ini output/engine_utf8/native_ini_v2
```

색상 변환표·원본 FNT 표본·폰트 팩 및 게임 복사본은 Git 제외 경로에만 보관한다.
