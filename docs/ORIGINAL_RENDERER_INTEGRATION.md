# 원본 Software 렌더러 격리 연결 검사

**후속 단계 완료:** 실제 시험 EXE의 그리기·너비 계산 진입점을 연결하고, 그 파일을 에뮬레이터에 적재해 UTF-8 문장 출력·너비·전체 화면 픽셀 일치를 확인했다. 실제 DOS 실행은 미검증이다. [시험 EXE 안내](TEST_EXE.md).

2026-10-13. `tools/encoding/engine_render_probe.py`로 실제 RG.EXE의 비트맵 그리기 함수 `0x9F0B8`과 행 코드 생성 함수 `0x9F2CA`를 Unicorn에서 실행했다. 원본 코드의 내부 offset fixup을 반영하고 프레임버퍼, 클리핑 범위, 행 코드 생성 버퍼를 검사 하네스가 초기화했다.

**결과:** 선택한 Noto Serif KR 600 시험 팩에서 34글리프를 원본 함수로 그렸다. 결과 전체 640×480 프레임버퍼가 원본 비트맵을 같은 위치에 놓은 기준값과 바이트 단위로 일치했다. 단순히 Pillow로 만든 문장 이미지가 아니라 원본 그리기 함수의 실제 기계어를 실행한 결과다. 단, 글리프를 선택하고 호출하는 주체는 Python 하네스이며, 게임의 UTF-8 문자열 그리기·폰트 로더를 후킹한 결과는 아니다.

## 확인한 호출 조건

- EAX=x, EDX=y, EBX=출력 폭, ECX=출력 높이. 스택에 원본 폭, 원본 높이, 모드, 픽셀 주소를 전달한다.
- 함수는 `ret 0x10`으로 스택 인자를 해제한다. 검사에서는 반환 주소 및 ESP 일치를 확인한다.
- 행 그리기 코드를 메모리에 생성한다. 코드 생성용 메모리, 화면 너비, 프레임버퍼 바이트 한도 및 행별 시작 위치가 필요하다.
- 함수 자체의 명령 즉시값도 변경한다. 에뮬레이터의 코드 캐시와 자기 수정 코드를 함께 고려해야 한다.
- 초기화 데이터와 BSS가 서로 다른 LE 오브젝트에 있다. 모든 전역 변수에 같은 데이터 베이스를 더하는 방식은 잘못된다. 각 명령의 재배치 대상 주소로 개별 해결했다.

## 남은 제약

이 하네스는 DOS 실행 환경 전체를 구현하지 않는다. 처음에는 내부 offset fixup 중 대상 오프셋이 오브젝트 크기를 넘는 111건을 보류했으나, 후속 수정에서 모두 32비트 주소 계산으로 반영했다. 현재 반영한 offset fixup은 **51,568건**, 보류한 offset fixup은 0건이다. 범위 밖 오프셋 111건은 `offsets_outside_target_object`에 별도 기록하며, 해당 값의 실제 게임 내 사용 의미까지 검증한 것은 아니다. selector fixup 2건은 여전히 적용하지 않았다. 이 격리 하네스를 DOS 패처나 실행 가능한 LE 이미지 생성에 그대로 사용할 수 없다.

검사는 화면 중앙의 일반 비트맵 경로만 다룬다. 그림자, 화면 가장자리 클리핑, 게임 시작, 실제 폰트 적재·선택·해제, 자막 음성 동기화, UTF-8 문자열 그리기 후크는 아직 검증하지 않았다.

## 원본 폰트 로더 후속 검사

`--check-font-loader`를 지정하면 `0xA731B`의 원본 폰트 로더도 실제 x86 코드로 실행한다. 파일 열기·청크 위치 검색·읽기·메모리 할당·복사 등의 보조 함수 11개는 Python 하네스가 제공한다. DOS 파일 시스템과 원본 힙 구현을 실행한 검사는 아니다.

원본 REDSEL.FNT를 읽힌 결과 **208글리프의 활성 여부·폭·높이·비트맵 전체 일치**를 확인했다. 할당 호출 210회, 파일 읽기 호출 1,262회가 발생했다. 이는 한 번의 로드 검사 기록이며, 글꼴 선택이나 문자 출력 때마다 전체 폰트를 다시 로드한 것이 아니다. 로더 검사 후 원본 그리기 함수로 34한글 글리프를 출력한 결과도 픽셀 단위로 일치했다.

```powershell
python tools/encoding/engine_render_probe.py --exe 'C:\Games\Steam\steamapps\common\The Elder Scrolls Adventures Redguard\Redguard\RG.EXE' --font-pack output/engine_utf8/test_serif600_20261013/redsel_unicode_prototype.kgf --check-font-loader --output output/engine_utf8/loader_render_probe
```

후속 결과는 `output/engine_utf8/loader_render_probe/render_probe_report.json`에 저장한다. 전체 기존 테스트 41개도 통과했다. 아직 원본 로더가 KGF1 파일을 읽는 후크나 원본 문자열 함수가 UTF-8을 받아 새 글리프를 선택하는 후크를 설치하지 않았다. 다음 단계는 이 검사로 확인한 호출 규약을 이용해 게임에서 실행되는 어댑터를 작성하고 LE에 배치하는 것이다.

재배치 구조 참고: [Open Watcom LE/LX 정의](https://github.com/open-watcom/open-watcom-v2/blob/master/bld/watcom/h/exeflat.h). 주소 산술 반영이 실제 DOS 초기화 검증을 대신하지 않는다.

## 산출물

- `output/engine_utf8/render_probe/original_renderer_korean_probe.png`
- `output/engine_utf8/render_probe/render_probe_report.json`

이미지 색은 현재 시험 팩의 단색 팔레트 인덱스 195다. 앞서 만든 노란 글자·붉은 테두리의 디자인 시안을 적용한 결과가 아니다.

동시에 `tools/rtx/build_korean_test_rtx.py`로 초안 4,866건을 UTF-8 RTX 복사본에 넣었다. 태그·순서를 대조하고 번역문 UTF-8 왕복, 음성 3,933건의 헤더·PCM 보존을 검사했다. 원문 JSON, 번역 초안 및 설치 원본은 덮어쓰지 않았다.

- `output/engine_utf8/test_assets/ENGLISH.RTX` (184,750,875바이트)
- `output/engine_utf8/test_assets/ENGLISH.build.json`

이 RTX는 **후크 개발용 데이터**다. 원본 RG.EXE는 해당 UTF-8 텍스트를 올바르게 처리하지 못한다. 아직 플레이 가능한 테스트 EXE나 설치 배포본은 없다.
