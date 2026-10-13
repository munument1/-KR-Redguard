# 배포 패키지 빌드

게임 원본은 입력으로만 사용하고 생성물은 `output/`에 둡니다. 게임 원본·음원·글꼴 파일과 로컬 검수 자료는 저장소에 넣지 않습니다.

0.1.0은 Python 3.14.3, PyInstaller 6.20.0, bsdiff4 1.2.6으로 빌드했습니다. 엔진 빌드와 격리 검사는 Keystone, Capstone, Unicorn, Pillow, fontTools도 필요합니다.

1. `tools/rtx/build_korean_test_rtx.py`의 `--drafts`에 최종 검수 JSONL 폴더를 지정해 별도 RTX를 생성합니다. 검수 완료 기록의 49개 SHA-256과 입력을 먼저 대조합니다.
2. `tools/encoding/extend_font_pack.py`로 기존 기본 글리프 팩에 최종 검수본의 누락 문자를 추가합니다. `--font`에는 개발에 사용한 NotoSansKR-Regular.ttf를 지정합니다. 기존 글리프는 유지합니다.
3. `tools/encoding/font_colors.py`로 원본 FNT 스타일과 메뉴 대비 메타데이터를 생성합니다. `tools/patch/build_test_exe.py`로 별도 RG.EXE를 빌드합니다.
4. 검증된 MENU.INI/KEYS.INI 번역본과 함께 생성 파일 네 개를 출력 폴더에 모읍니다.
5. `python tools/patch/build_release.py --original ORIGINAL_GAME_DIR --translated GENERATED_DIR --output PACKAGE/data`로 차분을 생성합니다. RTX는 음원 영역을 원본에서 복사하는 명령과 번역 리터럴만 포함하며, 나머지 세 파일은 bsdiff4 차분입니다.
6. `python -m PyInstaller --onefile --windowed --name RedguardKoreanPatcher --distpath PACKAGE --workpath output/installer_build --specpath output --hidden-import bsdiff4 --paths tools/patch tools/patch/release_patcher.py`로 Windows 패처를 빌드합니다. 0.1.1은 manifest에 `memory_config`를 추가하며 `memory_config.py`도 함께 묶습니다. 네 차분의 내용은 0.1.0과 같습니다.
7. 정식 원본 네 파일을 작업 폴더로 복제하고 **패키지 EXE 자체**로 check/apply/apply/check/restore/restore를 실행합니다. 매 단계 결과 해시를 확인합니다. 미지원 파일, 손상 차분, 충돌 백업, 쓰기 실패의 무변경/복구 동작도 검사합니다. 실제 설치 원본을 테스트 대상으로 쓰지 않습니다.
8. `python -m unittest discover -s tests -q`와 `engine_render_probe.py`의 일반·추가 글자 색상 검사를 실행합니다. 전체 번역과 INI 문자 커버리지, 음원 보존, 기존 글리프 보존도 확인합니다.
9. 안내문, 구성 요소 라이선스, 검증 요약, SHA256SUMS.txt를 넣고 ZIP을 만듭니다. ZIP 내부 파일의 해시를 재검증합니다. 게임 원본 파일이 없는지 검사한 후 GitHub Release 첨부 파일로 올립니다.

지원 범위와 실제 게임 검증의 한계는 [0.1.1 안내](RELEASE_0_1_1.md)에 기록합니다. 0.1.1 검증에는 SYSTEM.INI의 변경·설정 보존·복원, 0.1.0에서의 업그레이드, URP 메뉴가 있는 설치에서의 `memory-fix`, 마지막 설정 쓰기 실패 시 네 파일의 롤백을 포함합니다. 개발용 `binary_patcher.py`의 단일 파일 실험 manifest와 배포용 `redguard-ko-release-v1` 패키지는 서로 다른 형식입니다.
