# Unofficial Redguard Patch 1.03 + Coyle 수정 연동

**한국어 호환판 추가:** 한국어 패치 0.1.0용 별도 구성을 만들었습니다. 최신 설치·복원 안내는 [URP 한국어 호환판](URP_KOREAN.md)을 참고하세요. 아래는 기존 로컬 Mod Manager 조합 방식의 연구 기록입니다.

## 목적 및 원본

- 원작자: **Dillonn241**, [Unofficial Redguard Patch (Nexus #11)](https://www.nexusmods.com/theelderscrollsadventuresredguard/mods/11).
- 기준: 사용자가 정식 다운로드한 `Unofficial Redguard Patch-11-1-03-1777266218.zip` (Nexus 공개 버전 1.03, 2026-04-27 업데이트).
- 원본 ZIP 안 `About.txt`에는 **1.01**로 기록돼 있으나, 외부 페이지 및 ZIP 파일명의 버전은 1.03입니다.
- 이 프로젝트의 공개 Git 저장소에는 원본 모드의 RTX/INI/Map Changes 본문, 압축 파일 및 게임 데이터가 **포함되지 않습니다**.

## Coyle의 Hayle 대화 버그

Nexus에 ["Can't become friends with Coyle after rescuing Iszara"](https://www.nexusmods.com/theelderscrollsadventuresredguard/mods/11?tab=bugs)라는 미해결 제보가 있습니다. 원본 맵 스크립트에서 다음을 확인했습니다.

- 위치: `MAPS/ISLAND.RGM`, Redguard Mod Manager가 역해석한 **0기준 1520번 줄**.
- 기존 조건: `if after_iszara = 0 and CyrusFriend = 0 and HayleStory = 1`
- 수정 조건: `if CyrusFriend = 0 and HayleStory = 1`
- 바로 뒤 `menuAddItem("?hay", var35, 7)`는 유지합니다.

원본 패치가 `VILE` 스크립트에서 `after_iszara = 1`로 값을 설정한 이후에도 Coyle의 Hayle 대화를 막지 않도록, 이 한 조건만 변경합니다. **CyrusFriend와 HayleStory는 유지**하므로 기존 대화 진행 제약은 보존합니다. 게임상 실제 대화 진행 및 세이브 호환성은 아직 검증되지 않았습니다.

## 로컬 통합 패치 제작

Python 3.10+와 **Java 24**, 사용자가 다운로드한 Redguard Mod Manager JAR가 필요합니다. PowerShell에서 이 저장소 폴더를 현재 디렉터리로 설정한 뒤 실행합니다.

```powershell
$game = 'C:\Games\Steam\steamapps\common\The Elder Scrolls Adventures Redguard\Redguard'
$urp = 'Unofficial Redguard Patch-11-1-03-1777266218.zip'

python tools/patch/build_urp_coyle.py --source $urp --game $game --jar 'Redguard Mod Manager.jar'
java -Xmx2g -cp '.;Redguard Mod Manager.jar' tools/script/ValidateUrp.java $game 'output/Unofficial Redguard Patch + Coyle Fix (Local).zip'
```

출력: `output/Unofficial Redguard Patch + Coyle Fix (Local).zip`.

빌더는 설치된 **원본** `ISLAND.RGM`을 Mod Manager의 역분석 코드를 통해 확인해 예상한 조건과 라인 번호가 정확할 때만 작동합니다. 압축 파일의 모든 기존 Map/RTX/INI 수정 사항을 유지하면서 `ISLAND` 섹션에 아래 두 레코드를 추가합니다.

```text
  1520\tnull
  1520\t  if CyrusFriend = 0 and HayleStory = 1
```

여기서 `\t`는 실제 파일에서 탭 문자이며, `null`은 Mod Manager가 **기존 1520번 줄을 삭제**하도록 지시합니다. 후속 줄은 동일 위치에 새 조건을 추가합니다. 같은 맵의 기존 URP 수정은 모두 남깁니다.

### 적용

1. Mod Manager JAR와 같은 위치의 `Mods/` 디렉터리에 위 로컬 ZIP을 **압축 해제**합니다. 결과 경로는 `Mods/Unofficial Redguard Patch + Coyle Fix (Local)/About.txt`처럼 되어야 합니다.
2. Mod Manager에서 기존 `Unofficial Redguard Patch` 항목이 있다면 **비활성화**하고 로컬 합본 하나만 활성화합니다.
3. 먼저 세이브 및 게임 파일을 백업하고 Mod Manager의 **Apply Changes**를 눌러 적용합니다. 이 단계는 게임 파일을 변경할 수 있으므로, 패치 툴이 자동으로 실행하지 않습니다.

지금 생성한 통합 파일은 개인 로컬 테스트용입니다. 제작자가 Nexus에서 **타 사이트 업로드와 무허가 수정을 금지**하고 있으므로, 합본 ZIP 배포 및 한국어 패치 내부에 원본 데이터를 동봉하려면 **사전 허락을 받아야** 합니다. 공개 배포에서는 사용자가 원본 URP를 별도로 내려받아 로컬에서 조합하는 방식을 사용합니다.

## 한국어 번역 원문에 교정 사항 포함

```powershell
python tools/patch/seed_urp_translations.py --urp $urp --rtx "$game/ENGLISH.RTX"
python tools/rtx/rtx_tool.py pack "$game/ENGLISH.RTX" output/ENGLISH.urp-source.json output/ENGLISH.urp-test.RTX
```

- `output/ENGLISH.urp-source.json`: RTX **4,866건** 가운데 원본 패치의 **78건**을 교정된 영어 원문으로 반영한 UTF-8 번역용 파일. `translation`은 미번역이면 `null`입니다.
- `output/MENU.urp-source.json`: 영화 자막의 **INI 수정 6건**을 별도 번역 항목으로 제공. 이후 `MENU.INI` 번역 도구와 통합 예정입니다.
- `pack` 실행 시 교정된 78건은 미번역이어도 RTX 데이터에 반영되며, 한국어 번역이 있으면 해당 번역을 우선합니다. 한국어 인코딩 및 게임 내 출력은 별도 엔진 작업이 필요합니다.

### 검사 결과 (2026-10-13)

- 원본 9개 맵을 모두 수정 후 **컴파일 → 역해석** 검증했고 모든 맵 통과.
- `ISLAND`의 Coyle 조건이 예상 내용으로 재생성되고 `?hay` 메뉴 호출이 남아 있음을 확인.
- 실제 RTX 4,866건을 재작성해, 기대한 **78건만** 달라지고 음성 3,933건은 전부 바이트 동일함을 검증.
- 테스트 로컬 FNT 및 RTX 산출물은 `output/`에만 저장. 원본 Steam 게임 파일을 변경하지 않음.

**남은 검증:** Coyle 친구 관계/구출 이후 진행 상황의 게임 플레이 실증, 향후 한국어 출력 패치와의 최종 결합, 동영상 자막의 한국어 표시 및 길이 제한.
