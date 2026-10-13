# 엔진 텍스트 출력 영역과 미해결 바이너리 검증

## 설치본

읽기 전용 확인한 Steam 설치본에는 `RG.EXE` (4,241,144B), `REDGUARD.EXE` (1,003,008B), `ENGLISH.RTX` 및 `3dart/`, `fonts/`가 있습니다. `fxart/`는 확인한 설치본 최상위에 존재하지 않았습니다. **Glide판 전용 서술을 Steam Software판에 그대로 적용하지 않습니다.**

## 외부 엔진 분석에서 확인한 표시 경로

- 일반 대사: RTX 엔트리 텍스트, `FONTS/REDSEL.FNT`. [Glide 자막 분석](https://github.com/michidk/redguard-preservation/blob/main/docs/engine/subtitles.md)에 따르면 가상 화면 640×480에서 중앙 정렬, 기본 폭 제한 500px, glyph width+1 전진, 공백은 추가 폭, 공백 단위 줄바꿈.
- 음성 포함 대사는 음성이 끝날 때 자막이 사라지고, 음성 없는 경우 별도 시간 계산. 자막 슬롯 수 20은 **20줄 제한이 아님**. 같은 문서 참조.
- HUD/상호작용 문자열: `REDSEL.FNT` 공유. [HUD 분석](https://github.com/michidk/redguard-preservation/blob/main/docs/engine/hud.md).
- 책 모양의 설정·시작 메뉴: `MENU.INI`의 레이블을 사용하는 영역도 있으며, [Glide 메뉴 분석](https://github.com/michidk/redguard-preservation/blob/main/docs/engine/menu.md)에는 `FONTNORM`, `FONTSEL` 및 저해상도 변형 언급.
- 동영상 자막: `MENU.INI`의 `[page3]` 자막 정보이며 RTX와 별개. [영화 문서](https://github.com/michidk/redguard-preservation/blob/main/docs/engine/movies.md)에는 **원본 35문자 기준 줄바꿈**이 기술되어 있습니다.
- 아이템·키 설정 등 기타 INI 문자열은 RTX와 별개로 검토해야 합니다. `ITEM.INI`, `MENU.INI`, `KEYS.INI`에 대한 변경 도구는 미구현.

## 디버거로 확인해야 할 엔진 제약

1. `RG.EXE` (Software판)에서 `REDSEL.FNT` 로더 진입점, 읽는 글리프 개수, 배열/힙 할당, 인덱스 자료형.
2. 렌더링 진입점에 입력되는 `char` 값이 unsigned인지, 확장 유니코드/2바이트 경로가 있는지, 글리프 주소 산출이 어떻게 이뤄지는지.
3. RTX 문자열 복사 함수의 수신 버퍼 크기, NUL 종료 방식, 정렬·줄바꿈·폭 계산의 바이트/글리프 단위 여부.
4. 긴 자막 입력, CP949 멀티바이트 시퀀스, 새 줄/탭 등 제어 문자가 충돌 없이 처리되는지.
5. 책·메뉴·HUD·영상 자막·로그·저장 데이터의 독립적인 폰트·문자 처리 경로.
6. Glide 버전이 추가로 확보되면 각 renderer의 별도 결과 비교.

**현 상태:** 2026-10-13에 Software판의 문자 해석, 그리기, 너비 계산, 폰트 로더를 정적 분석했습니다. 1바이트 읽기·포인터 이동과 고정 256글리프 배열을 확인했습니다. [UTF-8 엔진 조사 기록](UTF8_ENGINE_FINDINGS.md)을 참고하세요. 게임 내부 버퍼 전수 분석, UTF-8 패치 및 게임 출력 검증은 미완료입니다.
