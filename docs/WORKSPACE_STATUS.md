# 레드가드 한국어화 작업 현황 — 2026-10-14

주요 결정과 검증 이력은 [작업일지](WORK_LOG.md)에 기록합니다.

## 현재 배포

- 기본 한국어 패치: **0.1.1**, 항구 편지 아이템 화면의 메모리 할당 오류 수정.
- 별도 URP 한국어 호환판: **1.0.0 + Coyle 수정**, 기본 패치 0.1.1과 호환. Nexus 파일의 기존 표시 버전은 1.0.3.
- RTX 4,866건의 전수 텍스트 검수 완료, 활성 검수 보류 0건.
- 자동 테스트 77개와 배포 EXE의 신규 설치·0.1.0 업데이트·복원 검사 통과.
- 사용자가 기본 한패 + `heap_kbytes=20000`에서 항구 편지 표시와 정상 진행 확인. 전체 게임 플레이 검증은 미완료.

[GitHub 0.1.1](https://github.com/munument1/-KR-Redguard/releases/tag/v0.1.1) · [Nexus](https://www.nexusmods.com/theelderscrollsadventuresredguard/mods/16) · [설치·수정 근거](RELEASE_0_1_1.md) · [검증 요약](RELEASE_0_1_1_VALIDATION.json).

0.1.1 배포 소스 커밋: `5da6ba2dcf2b53fc3b5e42acd419e61e627b197c`.
배포 ZIP SHA-256: `0908f263d6deaec95108430b1d0503cb46aec977a22e49d67cb88eda331ac8c5`.

## 공개 소스

| 용도 | 위치 |
| --- | --- |
| RTX 읽기·재구성 | `tools/rtx/` |
| UTF-8·글리프·색상 처리 | `tools/encoding/` |
| LE 실행 파일 빌더 | `tools/patch/build_test_exe.py` |
| 차분 패키지 빌더·설치·복원 | `tools/patch/build_release.py`, `tools/patch/release_patcher.py` |
| 항구 충돌 수정 설정·복원 | `tools/patch/memory_config.py` |
| 별도 URP 한국어 호환 처리 | `tools/patch/urp_korean.py`, `translations/urp_korean.json` |
| 회귀 검사 | `tests/` |
| 빌드·배포 절차 | [RELEASE_BUILD.md](RELEASE_BUILD.md) |

## 로컬 보존 자료

작업 폴더는 `D:\Codex_Trans\그냥 번역\레드가드`입니다. Steam 설치본은 읽기 전용 참조로 사용하며 실행 비교는 별도 복사본에서 진행했습니다.

| 용도 | 작업 폴더 기준 위치 |
| --- | --- |
| 번역 기준 원문·URP 교정 78건 | `output/ENGLISH.urp-source.json` |
| 최종 검수본·승격된 번역 입력 | `output/text_translation/reviews/final_drafts_20261013/`, `output/text_translation/drafts/` |
| 검수 완료 기록·입력 SHA-256 | `output/text_translation/reviews/final_text_qa_completion_20261013.json` |
| 최종 글리프·색상 빌드 입력 | `output/rebuild_inputs/font_base/`, `output/rebuild_inputs/font_final/` |
| 한국어 MENU/KEYS 빌드 입력 | `output/engine_utf8/native_ini_v2/` |
| 이전 빌드·렌더링·설치 검증 기록 | `output/build_archive/` |
| 배포 패키지·ZIP | `output/releases/` |
| 0.1.1 패키지 EXE 검증 기록 | `output/release_work/0.1.1/installer_verification.json` |
| 항구 충돌 비교 실행·실패/성공 기록 | `output/crash_debug/`, `output/crash_debug/cases/` |
| 이전 시험본의 세이브·설정 | `output/preserved_saves/` |
| 개인 설치용 URP 완성 파일 | `output/urp_korean_complete_files/` |
| Nexus 이미지·업로드 확인 화면 | `output/nexus_images/` |

과거 문서의 `playtest_*`, `texture_exports`, 기존 `urp_work` 등은 정리되어 존재하지 않을 수 있습니다. 재빌드는 위 보존 입력과 새 출력 폴더를 사용하세요. 초기 연구 문서의 미검증 상태는 해당 시점의 기록이며, 현재 상태는 이 문서와 최신 배포 안내가 기준입니다.

`output/`의 원본 게임 에셋·음원·검수 입력, 사용자가 제공한 폰트·URP ZIP·Mod Manager JAR는 Git에 공개하지 않습니다. 공개 저장소의 소스만으로 전체 번역과 글리프를 처음부터 재생성하려면 해당 로컬 입력도 필요합니다. 설치용 차분은 GitHub Release와 Nexus에서 제공합니다.
