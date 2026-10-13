# 레드가드 한국어화 로컬 작업 기준

**작업 기준 폴더:** `D:\Codex_Trans\그냥 번역\레드가드`

게임 설치 원본은 `C:\Games\Steam\steamapps\common\The Elder Scrolls Adventures Redguard\Redguard`에 있으며, 여기서는 **읽기 전용 참조**로만 사용합니다. 모든 새 파일은 위 작업 기준 폴더에 작성합니다.

## 지금까지의 작업 자료

| 용도 | 작업 폴더 기준 위치 | 상태 |
| --- | --- | --- |
| RTX 전체 대사 원문 | `output/ENGLISH.translation.json` | 4,866건 추출 |
| 비공식 패치 수정 원문 | `output/ENGLISH.urp-source.json` | 번역 **기준본**, 78건 교정 반영 |
| JSONL 번역 배치 | `output/text_translation/rtx_*.jsonl` | 번역 입력용. `index.json` 참고 |
| 지도 한국어 초안 | `output/texture_ko/map_ko_draft.png` | 검토용 PNG, ‘훈딩 만’, ‘척추 열도’ 반영 |
| 지도 원본 비교 | `output/texture_ko/map_before_after.png` | 원본과 번역본을 가로로 비교 |
| 기타 텍스처 추출 | `output/texture_exports/` | 추출본, 게임 재삽입 미완료 |
| 글꼴 실험 | `output/REDSEL*`, `output/ga.json` | 인게임 한국어 표시는 미검증 |
| UTF-8 시험 EXE·게임 복사본 | `output/engine_utf8/playtest_v4_menu_final_20261013/` | v4 표시 사용자 확인 완료. 최종 검수본은 별도 0.1.0 패치에 반영 |
| 한국어 번역 초안 | `output/text_translation/drafts/rtx_*_ko.jsonl` | 4,866건. 시험 RTX 생성, 검수 완료 아님 |
| 비공식 패치·Coyle 수정 합본 | `output/Unofficial Redguard Patch + Coyle Fix (Local).zip` | 로컬 검증용 |
| RTX 도구 | `tools/rtx/` | 파싱·재구성, JSONL 작업 준비 |
| 지도 PNG 제작 도구 | `tools/texture/` | `localize_map.py` |
| 연구·검증 문서 | `docs/` | 포맷·한글 처리·패치 통합 등 |

## 텍스트 번역 시작

다음 명령으로 **이미 추출해 둔 원문 JSON**을 100건씩 UTF-8 JSONL로 나눌 수 있습니다. CSV를 사용하지 않습니다.

```powershell
cd 'D:\Codex_Trans\그냥 번역\레드가드'
python tools/rtx/prepare_jsonl_batches.py
```

각 JSONL 줄은 `index`, `tag`, `kind`, `original`, `translation` 필드를 가집니다. 원문·태그는 그대로 두고 `translation`에 한국어를 넣습니다. 기존 배치가 있으면 프로그램은 덮어쓰지 않고 중단합니다. **현재 번역 초안 4,866건이 있으며**, UTF-8 시험 RTX와 Software 시험 EXE도 생성했습니다. 실제 게임 검증과 자막 줄바꿈·화면별 글꼴 연결은 남아 있습니다. [실행 안내](TEST_EXE.md)를 참고하세요.

`output/`의 게임 원문·음성·이미지와 루트의 제공받은 글꼴·ZIP·JAR 파일은 **Git에 공개하지 않습니다**. README와 도구, 문서만 버전 관리합니다.

## 배포 0.1.0

- 최종 검수본: `output/text_translation/reviews/final_drafts_20261013/` (4,866건, 활성 보류 0건).
- 배포 패키지: `output/releases/Redguard-Korean-0.1.0/`.
- 설치·복원 검사 기록: `output/release_work/installer_verification.json`.
- [배포 안내](RELEASE_0_1_0.md), [검증 요약](RELEASE_VALIDATION.json).
