# 배포 가이드 (개발자용)

## 1. 로컬에서 .app 만들기 (맥)
```bash
bash packaging/build_macos.sh      # -> dist/TypeGrass.app, dist/TypeGrass-macOS.zip
open dist/TypeGrass.app            # 직접 실행해 확인
```
확인할 것: 메뉴바 아이콘 / 권한 안내창 / 입력 모니터링 허용 후 타수 증가 / 풀이 바탕화면(아이콘 아래)에 표시 / 로그 `~/Library/Application Support/TypeGrass/typegrass.log`.

## 2. GitHub Releases 로 자동 배포
```bash
git tag v0.2.0 && git push origin v0.2.0
```
`.github/workflows/release.yml` 이 macOS 러너에서 빌드해 Releases 에 `TypeGrass-macOS.zip` 을 첨부합니다.
(처음에는 로컬 빌드로 먼저 동작을 확인한 뒤 태그를 푸시하세요.)

## 3. 서명 수준과 사용자가 겪는 일
| 방식 | 비용 | 사용자 경험 |
|---|---|---|
| 서명 없음/임시 서명(기본) | 무료 | 처음 실행 시 "확인되지 않은 개발자" 경고 → 우클릭-열기 필요. 업데이트마다 입력 모니터링 권한이 초기화될 수 있음 |
| Developer ID 서명 + 공증(notarization) | Apple Developer Program 연회비 | 더블클릭으로 바로 실행, 업데이트 후에도 권한 유지(같은 Team/ID 유지 시) |

공증 흐름(참고, 직접 검증 필요):
```bash
export CODESIGN_IDENTITY="Developer ID Application: 이름 (TEAMID)"
bash packaging/build_macos.sh
xcrun notarytool submit dist/TypeGrass-macOS.zip --apple-id "<id>" --team-id "<TEAMID>" --password "<앱 전용 암호>" --wait
xcrun stapler staple dist/TypeGrass.app
ditto -c -k --sequesterRsrc --keepParent dist/TypeGrass.app dist/TypeGrass-macOS.zip
```

## 4. 알아둘 점
* 번들 ID(`io.github.<아이디>.typegrass`)는 처음 배포 전에 정하고 바꾸지 마세요. 바뀌면 권한이 초기화됩니다. (`TYPEGRASS_BUNDLE_ID` 환경변수 / `packaging/typegrass.spec`)
* 기본 빌드는 빌드한 맥의 CPU 용입니다(Apple Silicon 러너 → arm64). Intel 맥 지원이 필요하면 별도 빌드가 필요합니다.
* 용량은 Qt 때문에 수백 MB 가 될 수 있습니다.
* 개인정보: 키 내용은 읽지 않고 횟수만 셉니다. README/릴리스 노트에 이 점과 필요한 권한(입력 모니터링)을 명시하세요.
* 외부 이미지를 에셋에 쓰면 `assets/LICENSES.md` 에 출처·라이선스를 기록하고, 재배포가 허용된 것만 포함하세요.
