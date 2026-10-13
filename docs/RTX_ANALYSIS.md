# RTX 대사·음성 바이너리 분석

## 파일 구조

`[tag(4) | payload_size(u32 BE) | payload] ... [END ][index][RNAV footer]`

- 맨 끝 `RNAV` (4바이트) + index_offset(u32 LE) + entry_count(u32 LE).
- 인덱스는 `[tag(4) | payload_offset(u32 LE) | payload_size(u32 LE)]` 12바이트 항목.
- 인덱스 offset은 청크 헤더가 아닌 **payload 시작 위치**. 디스크 청크 헤더의 길이는 빅엔디언.
- payload 접두 6바이트: `[0x00, subtype(0/1), string_len(u16 LE), reserved(u16)]`.
- subtype 0은 `string_len`바이트 원문, subtype 1은 원문 뒤 27바이트 오디오 헤더와 PCM.
- 오디오 헤더의 offset 22에 `audio_length(u32 LE)` 존재. 원본 자료의 인덱스는 *payload offset 역순*.

정확한 필드 정의: [Preservation RTX spec](https://github.com/michidk/redguard-preservation/blob/main/docs/formats/RTX.md), [RTX 파서](https://github.com/michidk/redguard-preservation/blob/main/src/import/rtx.rs).

## Steam 실파일 확인 결과 (2026-10-13)

| 항목 | 관찰값 |
|---|---:|
| ENGLISH.RTX 크기 | 184,687,877바이트 |
| 중앙 인덱스 시작 | 184,629,473 |
| 전체 인덱스 | 4,866건 |
| 음성 포함 | 3,933건 |
| 텍스트 전용 | 933건 |
| 최대 원문 문자열 | 801바이트 |

`tools/rtx/rtx_tool.py`는 4,866건을 실제 파일에서 파싱했고, **변경 없음**으로 재구성할 때 원본 바이트와 동일했습니다. 임의의 음성 자막 1건을 1바이트 늘린 뒤 새 인덱스를 재검증한 결과, 전 3,933건의 음성 헤더·PCM이 바이트 단위로 보존됐고 다른 텍스트도 동일했습니다. 원본 파일을 덮어쓰지 않았습니다.

## 바이트 수와 충돌 위험

- 문자열 `string_len`이 `u16`이므로 **바이트** 최대 65,535. 이는 원본 실행 파일의 문자열 버퍼 최대치가 아닙니다.
- 고정 크기 스택/힙 버퍼, `strcpy`, `sprintf`, `strlen`, 자동 줄바꿈의 포인터 처리 방식은 **미분석**.
- 모드 관리자 Java 코드의 `RtxEntry.length()`와 `subtitleLength()`는 Java 문자 수 `String.length()`를 사용. `Utils.writeString()`은 IBM437로 **인코딩하여 출력**하므로, 다중 바이트 인코딩에 활용하면 바이트 길이가 일치하지 않거나 치환 문자(`?`)가 나올 수 있습니다.
- RTX를 바꾸면 모든 후속 인덱스와 청크 길이를 다시 계산해야 합니다. 모드 관리자/기타 모드와 함께 쓰면 RTX 전체가 다시 쓰일 수 있어 덮어쓰기 우선순위 검사가 필요합니다.
- 게임 원본 텍스트 제한과 외부 저장 파일(세이브·로그)의 문자열 관련 제한은 별도 조사 대상.

기본 출력 인코딩은 IBM437이며, 한글 `--codec cp949`는 엔진 수정을 거친 테스트용으로만 적합합니다. 포맷 레벨 왕복 성공은 한글 출력 성공을 증명하지 않습니다.
