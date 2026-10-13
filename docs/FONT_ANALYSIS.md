# FNT 글리프 구조와 한글 렌더링 제한

## 검증한 실제 파일

Steam판 `fonts/`의 **29개 FNT 파일 전체를 읽고 구조 검증**했습니다. 글리프 개수 종류는 `[95, 97, 98, 104, 112, 208]`. 대사 폰트 `REDSEL.FNT`는 **208개 글리프, 시작 코드 32, line_height 26**, 즉 FNT 헤더상의 코드 범위 32~239입니다. `tools/fnt/fnt_tool.py`가 이를 PNG 아틀라스와 JSON으로 추출합니다.

## FNT 내부 구조

| 영역 | 내용 |
|---|---|
| 청크 | `FNHD`, `BPAL` 또는 `FPAL`, `FBMP`, 선택적 `RDAT`, `END ` |
| 청크 헤더 | 태그(4) + payload 길이(u32 BE) |
| `FNHD` | 56바이트. 문자 시작(u16 LE, offset `0x2E`), 글리프 개수(u16 LE, `0x30`), 행 높이(u16 LE, `0x2C`) |
| 팔레트 | RGB 256개 × 3바이트, 6비트 각 채널. 인덱스 0 = 투명 |
| FBMP 글리프 | enabled(u16), left(i16), top(i16), width(u16), height(u16), width × height 팔레트 픽셀 |

참조: [Preservation FNT.md](https://github.com/michidk/redguard-preservation/blob/main/docs/formats/FNT.md), [fnt.rs](https://github.com/michidk/redguard-preservation/blob/main/src/import/fnt.rs). Rust 파서는 `character_count`만큼 읽을 수 있으나 **원본 엔진의 실제 로더가 256글리프로 제한한다는 내용**이 FNT.md에 명시돼 있습니다.

**주의:** FNT 수량 필드가 16비트라는 사실이 65,535개 글리프를 게임에서 쓸 수 있다는 뜻은 아닙니다. 문자 인덱스가 실제로 8비트라면 32~255에 대응되는 코드는 **224개**뿐입니다. 208개가 이미 사용 중인 REDSEL은 재매핑 가능 후보가 극히 적습니다. 256개 로딩 한계가 `cmp` 한 개 때문인지, 고정 배열·메모리 구조·8비트 인덱싱 때문인지 정확한 판정에는 `RG.EXE` 런타임 역어셈블이 필요합니다.

## 검증 순서

1. **바이트 문자 치환 시험:** 정식 게임 복제본의 RTX 자막 1건에 안전한 영문 1바이트를 쓰고, 같은 ASCII 슬롯의 FNT 비트맵을 테스트용 한글 1자로 교체하여 표시 여부 확인.
2. **코드포인트 도달 범위:** 글리프 슬롯 240~255가 정상 표시되는지, 256 이상을 로더가 어떻게 처리하는지 디버거로 관찰. 실패 가능성이 크므로 원본 설치본에서 수행하지 않음.
3. **문자 디코더 분석:** 텍스트 렌더링 함수에 문자 바이트가 들어오는 경로, 부호확장/배열 인덱스, 문자열 복사·버퍼 길이 검증.
4. **한국어 구현:** 단일 바이트 매핑으로 충분하지 않을 경우 멀티바이트 디코더와 완성형 글리프 테이블 또는 별도 합성 루틴 작성.
5. **모든 UI 경로:** REDSEL 자막/HUD, FONTNORM/SEL 메뉴, 기타 UI/영화 글꼴을 개별 검증. 특히 Software·Glide의 렌더 경로를 구분.

`RedguardFNTImporter`라는 기존 도구의 존재를 확인했지만 UESP 직접 페이지가 403이므로 실제 기능·확장 가능 여부를 재검증해야 합니다. 아틀라스 추출에 대해서는 [Preservation의 기존 `convert fnt`](https://github.com/michidk/redguard-preservation)를 재사용할 수도 있습니다.

## 파일 변환 PoC 결과

Windows에 설치된 `NotoSansKR-Regular.ttf`에서 한글 `가`를 19×19 픽셀로 래스터라이즈했고, 코드 65(`A`) 슬롯에 그 비트맵을 넣은 `REDSEL_A_ga.FNT` 복제본을 생성했습니다. 기존 207글리프, 원본 팔레트와 헤더 및 메타데이터를 보존한 상태로 FNT 구조 재검증이 통과했습니다. 생성 파일은 `output/`에만 있습니다. **실제 게임 실행/자막 출력 여부는 검사하지 않았습니다.**
