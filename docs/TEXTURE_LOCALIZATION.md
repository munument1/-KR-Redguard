# 레드가드 텍스처 한국어화 준비

## 한국어 서체 적용 원칙

- **솔뫼 김대건체** (`font_kdg.zip`에서 추출한 Light/Medium TTF·OTF)는 간판, 표지판, 메뉴 배경처럼 **이미지 픽셀로 고정된 문구**의 번역에만 사용합니다.
- Light와 Medium 중 실제 배경과 크기에 맞는 굵기를 선택합니다. 편집 후에는 원본 이미지의 해상도, 투명 영역, 팔레트 제약을 확인합니다.
- **게임이 실시간으로 그리는 자막·대사·HUD·동적 메뉴 문자열(FNT)**에는 김대건체를 사용하지 않습니다. 인게임용 서체는 추후 별도로 선정합니다.
- 한글화 이미지의 재삽입 및 게임 내 출력은 아직 검증되지 않았습니다. 원본 서체 파일은 Git에 올리지 않습니다.

## 확인된 범위

`redguard-preservation`의 `rgpre`는 `TEXBSI.###` 텍스처 뱅크와 `.GXA` 그래픽 아카이브를 각각 PNG·GIF 등으로 **추출**할 수 있습니다. 이 기능은 **게임 안으로 다시 집어넣는 기능을 제공한다고 확인된 것은 아닙니다**. 먼저 화면상의 문자 포함 그래픽을 찾는 데 활용합니다.

- `3dart/`: 기존 Steam Software 렌더러용 리소스. 팔레트 `art_pal.col` 참고.
- `fxart/`: Glide 렌더러용 리소스. 존재하는 배포판에서 씬별 `.COL`을 지정해야 할 수 있음.
- `TEXBSI.###`: 3D 텍스처 뱅크 후보. 간판, 표식 등의 문자를 추출 후 사람이 확인.
- `.GXA`: 메뉴·그래픽/애니메이션의 문자 후보.
- `.FNT`: 문자 렌더링 폰트이며 본 작업과 별도 관리.
- `.3D`, `.3DC`, `.ROB`, `.WLD`: 표면 텍스처가 걸린 위치를 이해하기 위한 참고 데이터.

형식·CLI 출처: [michidk/redguard-preservation](https://github.com/michidk/redguard-preservation), README의 Conversion Matrix와 Asset Directories.

## 로컬 작업 명령 (PowerShell)

게임 설치 폴더 접근이 허용된 환경에서만 사용합니다. 아래 예시는 게임 파일을 읽고, 모든 결과를 별도의 `output/` 아래에 생성합니다.

```powershell
$game = 'C:\Games\Steam\steamapps\common\The Elder Scrolls Adventures Redguard\Redguard'
python tools/texture/texture_workflow.py scan "$game" --csv output/texture_inventory.csv

# 선행 작업: cargo install redguard-preservation
# 이미 설치된 rgpre 명령을 사용해, 우선 5개만 시험 추출
python tools/texture/texture_workflow.py extract "$game" --limit 5 --output output/texture_exports

# PNG/GIF 썸네일 + 번역 필요 여부를 기입할 CSV
python tools/texture/texture_workflow.py sheets output/texture_exports --output output/texture_review
```

`scan`은 파일명/형식/크기/텍스트 후보 여부만 기록합니다. **파일명을 통한 분류이므로 실제 한글화 대상 여부는 시각 검수가 필수**입니다. `extract`는 `rgpre`가 없으면 오류로 종료합니다. 손상된 리소스나 외부 도구 오류는 `export_report.json`에 남습니다.

출력 폴더가 게임 데이터 폴더 내부이면 추출을 거부합니다. 원본 리소스, 변환 이미지, 번역된 이미지 등은 공개 Git 저장소에 커밋하지 않습니다. `texture_review.csv`에서 `translation_needed`와 `comment`를 작성하여 후보를 추려 갑니다.

## 후속 구현에서 해결해야 할 것

1. 추출된 그림을 조사해 실제 영어 문자가 박혀 있는 리소스만 선별하고, 화면/씬과 매칭.
2. 원본 팔레트/투명색/인덱스를 보존하며 한글 이미지 제작. 변환 과정에서 픽셀 크기·애니메이션 프레임 변경 주의.
3. `TEXBSI` 및 `GXA`에 대한 **재삽입 도구 확보 또는 별도 구현**. 원본 무결성 및 동작 재검증.
4. Software/Glide의 분리된 리소스와 해당 사용 경로를 실제 게임에서 확인.

현재 이 저장소의 새 도구가 제공하는 범위는 **자산 목록 작성, 외부 도구를 이용한 추출, 검수용 미리보기**까지입니다. 인게임 텍스처 한글 표시와 재삽입 성공은 아직 검증하지 않았습니다.
