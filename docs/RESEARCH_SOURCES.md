# 조사 자료 및 검증 범위 (2026-10-13)

## 직접 확인한 코드·문서

| 프로젝트 | 관련 위치 | 확인 내용 |
|---|---|---|
| [Redguard Preservation](https://github.com/michidk/redguard-preservation) | [FNT.md](https://github.com/michidk/redguard-preservation/blob/main/docs/formats/FNT.md), [fnt.rs](https://github.com/michidk/redguard-preservation/blob/main/src/import/fnt.rs), [fnt_export.rs](https://github.com/michidk/redguard-preservation/blob/main/src/import/fnt_export.rs) | 청크 구조, 폰트 헤더, 글리프·PNG 아틀라스 변환 |
| 같은 프로젝트 | [RTX.md](https://github.com/michidk/redguard-preservation/blob/main/docs/formats/RTX.md), [rtx.rs](https://github.com/michidk/redguard-preservation/blob/main/src/import/rtx.rs) | 인덱스·오디오 헤더·자막 바이트 구조 |
| 같은 프로젝트 | [subtitles.md](https://github.com/michidk/redguard-preservation/blob/main/docs/engine/subtitles.md), [movies.md](https://github.com/michidk/redguard-preservation/blob/main/docs/engine/movies.md), [menu.md](https://github.com/michidk/redguard-preservation/blob/main/docs/engine/menu.md), [hud.md](https://github.com/michidk/redguard-preservation/blob/main/docs/engine/hud.md) | Glide 렌더러의 자막, 영화, 메뉴, HUD 표시 경로 |
| [Redguard Mod Manager](https://github.com/Dillonn241/redguard-mod-manager) | [RtxDatabase.java](https://github.com/Dillonn241/redguard-mod-manager/blob/main/src/redguard/RtxDatabase.java), [RtxEntry.java](https://github.com/Dillonn241/redguard-mod-manager/blob/main/src/redguard/RtxEntry.java), [Utils.java](https://github.com/Dillonn241/redguard-mod-manager/blob/main/src/redguard/Utils.java) | 레코드 수정/재저장, IBM437 텍스트 출력, `String.length()` 사용 |
| [우크라이나어 번역](https://www.nexusmods.com/theelderscrollsadventuresredguard/mods/5) | Description / Posts | 번역 파일 및 폰트 교체, Software·Glide 별도 패키지, 모드 관리자의 `ENGLISH.RTX` 덮어쓰기 충돌 보고 |
| [모드 관리자 게시글](https://www.nexusmods.com/theelderscrollsadventuresredguard/mods/10?tab=posts) | 러시아어 문자인식 질문과 제작자 답변 | 키릴 문자가 `?`로 저장되고, 문자 코드 재매핑이 필요할 수 있음을 언급 |
| [FNT Importer 안내](https://en.uesp.net/wiki/Mod:RedguardFNTImporter) | UESP | 외부 페이지는 403으로 직접 본문을 확인하지 못함. 존재 및 이미지 입출력 기능은 모드 관리자 소개에서 간접 확인. 상세 기능 미검증. |

문서에 명시된 256글리프 제한·자막 폭 규칙은 **Redguard Preservation 작성자의 분석**으로 확인한 것이며, 본 프로젝트가 엔진 내부 루틴을 역어셈블한 결과는 아닙니다.

## Unofficial Redguard Patch

원본 자료: [Unofficial Redguard Patch 1.03](https://www.nexusmods.com/theelderscrollsadventuresredguard/mods/11), [Coyle 버그 제보](https://www.nexusmods.com/theelderscrollsadventuresredguard/mods/11?tab=bugs). ZIP에 포함된 RTX·Map·INI Changes와 Mod Manager의 `MapChanges.java`, `MapFile.java`, `RtxDatabase.java`, `ScriptReader.java` 소스를 비교했습니다. 원본 모드의 수정·재배포는 별도 허락이 필요합니다. 로컬 생성 방법과 실제 파일 검증은 [통합 문서](UNOFFICIAL_PATCH_INTEGRATION.md)를 확인하세요.

본 저장소에 타인의 소스를 복사하지 않았습니다. 조사 대상 레포지터리의 명시적 라이선스는 이번 작업에서 확인되지 않았으므로, 후속 재사용 시 개별 라이선스를 반드시 확인해야 합니다. 번역 데이터 및 폰트는 권리자 허락 없이 번들에 포함하지 않습니다.

## 로컬 검증 자료

사용자 소유 Steam 설치 폴더 (`Redguard/`)의 `ENGLISH.RTX`와 `fonts/*.FNT`를 **읽기 전용**으로 분석했습니다. 정식 게임 바이너리, 음성, 번역 원문은 Git에 넣지 않았습니다. 실제 검증 수치는 [RTX](RTX_ANALYSIS.md)와 [FNT](FONT_ANALYSIS.md)에 수록했습니다.
