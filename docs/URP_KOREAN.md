# Unofficial Redguard Patch 한국어 호환판 1.0.0 + Coyle 수정

레드가드 한국어 패치 0.1.0 위에 설치하는 별도 URP 한국어 구성입니다. 기존 한글패치 배포물은 변경하지 않습니다.

## 내용

- URP 1.03의 버그 수정·복원 콘텐츠가 들어간 맵 9개를 원본 ZIP에서 생성합니다.
- URP가 교정한 대사·텍스트 78건은 한국어 패치 0.1.0에 이미 검수 반영되어 있습니다. 이 한국어 번역을 확인하고 영어 파일로 덮어쓰지 않습니다. 복원되는 대사도 기존 RTX 전체 한국어 번역을 사용합니다.
- URP 수정 영상 자막 6건을 한국어로 맞춥니다. 이 중 도입부 1건은 이미 한국어여서 유지되며 나머지 5건이 변경됩니다. 타이밍·색상은 유지합니다. 가상 언어 두 문장은 의미를 추정하지 않고 소리를 한글로 옮깁니다.
- Coyle의 Hayle 대화에서 after_iszara 조건만 제거합니다. CyrusFriend = 0, HayleStory = 1 조건과 ?hay 대화 항목은 유지합니다.

## 먼저 준비할 것

1. Steam Software판에 [한국어 패치 0.1.0](https://github.com/munument1/-KR-Redguard/releases/tag/v0.1.0)을 설치합니다. 이때 생성된 *.redguard-ko.bak 원본 백업을 보존하세요.
2. 원작자 Dillonn241의 [Unofficial Redguard Patch 1.03 ZIP](https://www.nexusmods.com/theelderscrollsadventuresredguard/mods/11)을 받습니다.
3. 같은 원작자의 [Redguard Mod Manager and Texture Viewer 1.13](https://www.nexusmods.com/theelderscrollsadventuresredguard/mods/10)에서 Redguard Mod Manager.jar를 받습니다.
4. Java 24 이상을 준비합니다. Java 24.0.2로 검증했습니다. 다른 Java 버전의 추가 검증은 수행하지 않았습니다.

URP ZIP과 JAR은 지원 파일 SHA-256을 검사합니다. 새로운 버전이나 다른 파일은 자동 적용하지 않습니다. 이번 공개 ZIP에는 원본 URP/JAR/게임 맵/게임 음원을 포함하지 않습니다. 원작자 페이지가 재업로드와 무허가 수정을 제한하고 있어 사용자가 받은 원본을 PC에서 조합합니다. 생성된 완성 파일은 개인 설치용입니다.

## 설치

게임과 DOSBox를 종료하고 ZIP 전체를 압축 해제합니다. URP_Korean_Coyle.exe를 실행해 게임 폴더, 원본 URP ZIP, Mod Manager JAR을 선택합니다. Java가 PATH에 없으면 Java 실행 경로에서 java.exe를 선택합니다. **한국어판 URP 적용**을 누르면 한국어 상태를 검증한 뒤 맵 9개와 MENU.INI를 백업하고 적용합니다.

RG.EXE, ENGLISH.RTX, KEYS.INI, 세이브는 수정하지 않습니다. 다른 맵 모드와 수정 파일은 자동으로 덮어쓰지 않습니다. Mod Manager에서 영어 URP를 별도로 다시 적용하지 마세요. 원본 Mod Manager는 RTX 문자열을 IBM437로 저장하므로 한국어 RTX를 다시 저장하면 한글이 손상될 수 있습니다.

## 덮어쓰기용 완성 파일

**완성 파일 생성**을 누르면 선택한 상위 폴더의 URP-Korean-Coyle 아래에 maps/*.RGM 9개와 MENU.INI가 생성됩니다. 이를 Redguard 게임 폴더에 덮어쓸 수 있습니다. 수동 설치는 직접 백업해야 합니다. 자동 설치를 사용해야 아래 복원 기능에 필요한 백업과 상태 기록이 생성됩니다.

## 복원

같은 프로그램의 **URP만 복원**은 *.urp-ko.bak를 사용해 URP 적용 전의 맵과 한국어 MENU.INI로 되돌립니다. 한글패치를 전부 지울 경우 **URP부터 복원한 뒤 기본 한국어 패처로 원본을 복원**하세요. 백업과 .redguard-urp-ko.json 상태 파일은 보존하세요.

## 검증 범위

맵 9개를 컴파일 후 역해석했습니다. 주석·사용되지 않는 라벨·재배치 주소 및 upstream VILE 객체 별칭을 정규화해 스크립트를 비교했습니다. Coyle 조건과 ?hay 항목도 확인했습니다. 자동 테스트 69개와 공개용 EXE의 적용·재적용·복원·재복원·완성 파일 생성 검사를 통과했습니다. 한국어 대사 아카이브와 엔진은 바이트 단위로 유지됩니다.

실제 게임에서 Iszara 구출 후 Coyle 대화를 진행한 검증은 아직 하지 않았습니다. 기본 한글패치의 도입부 외 영상 전체 번역, UI 하드코딩 문구와 줄바꿈 제한은 그대로 남아 있습니다.

## 크레딧

URP 및 Redguard Mod Manager: Dillonn241. 이 호환판은 원작자의 공식 배포물이 아닙니다. 한국어 번역·호환 처리와 Coyle 수정 코드는 이 프로젝트에서 작성했습니다. 구성 요소 고지는 licenses 폴더를 참고하세요.
