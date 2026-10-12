# 타자수만큼 풀자라기 (TypeGrass)

키보드를 칠 때마다 바탕화면에 풀잎이 하나씩 자랍니다. **타자 1회 = 풀잎 1개.**

![40타](docs/sample_40_blades.png) ![4천타](docs/sample_4000_blades.png)

* 입력한 **내용은 수집·저장하지 않고 '횟수'만** 셉니다. (키코드/문자를 읽지 않음, 데이터는 내 컴퓨터에만 저장)
* 오늘 타수는 `127.0.0.1` 로컬 API 로 다른 프로그램이 조회할 수 있습니다.
* 하루 = 풀밭 하나. 자정에 새 풀밭이 시작되고 지난 풀밭은 보존됩니다.

---

## A. 그냥 쓰고 싶다면 (다운로드)

1. [Releases](../../releases) 에서 `TypeGrass-macOS.zip` 다운로드 → 압축 해제 → `TypeGrass.app` 을 `응용 프로그램` 폴더로 이동.
2. **처음 한 번**: 앱을 *우클릭 → 열기 → 열기*. (공증되지 않은 앱이면 그냥 더블클릭 시 막힐 수 있음)
3. 권한 안내 창이 뜨면 **시스템 설정 → 개인정보 보호 및 보안 → 입력 모니터링** 에서 TypeGrass 를 켜고, 앱을 한 번 종료 후 다시 실행.
4. 메뉴바의 풀 아이콘에서 오늘 타수 확인 / 풀 숨기기 / 지난 풀밭 보기 / 종료.
5. 로그인 때 자동 시작: *시스템 설정 → 일반 → 로그인 항목* 에 TypeGrass 추가.

> Apple Silicon(M1 이상) 맥용으로 빌드됩니다. 데이터: `~/Library/Application Support/TypeGrass/`, 로그: 같은 폴더의 `typegrass.log`

## B. 소스로 실행 (개발자/기여자)

```bash
git clone https://github.com/songjm0819/typegrass.git && cd typegrass
python3 -m venv .venv && source .venv/bin/activate     # Python 3.11 이상
pip install -r requirements.txt
python -m typegrass doctor                              # 설치/권한 점검
```

| 하고 싶은 것 | 명령 |
|---|---|
| 권한 없이 구경(가짜 타수, 일반 창) | `python -m typegrass grass --demo` |
| **올인원: 바탕화면 + 카운터 + 메뉴바** | `python -m typegrass app` |
| 올인원이지만 일반 창으로 시험 | `python -m typegrass app --window` |
| 가짜 키 입력으로 시험 | `python -m typegrass app --simulate` |
| 모니터 선택 / 풀 투명도 | `python -m typegrass app --screen 1 --opacity 0.8` |
| 카운터만 / 풀밭 창만(터미널 2개) | `python -m typegrass counter` / `python -m typegrass grass` |
| 실시간 타수 보기 | `python -m typegrass watch` |
| 날짜별 기록 / CSV | `python -m typegrass history` / `python -m typegrass export-csv` |
| 단계별 풀밭 PNG 저장 | `python -m typegrass preview --counts 40,400,4000,40000` |
| 지난 풀밭 보기 | `python -m typegrass grass --date 2026-10-03` |

### macOS 권한
**시스템 설정 → 개인정보 보호 및 보안 → 입력 모니터링** 에 *명령을 실행하는 앱*(터미널/iTerm/VS Code)을 추가·허용 → 그 앱을 Cmd+Q 후 재실행.
안 되면 '손쉬운 사용' 에도 추가해 보세요. (macOS 버전에 따라 다를 수 있음)

### 타수 조회 API
```bash
curl http://127.0.0.1:47831/count          # 1234
curl http://127.0.0.1:47831/today          # {"date":"2026-10-04","count":1234}
curl "http://127.0.0.1:47831/history?days=7"
```

### 테스트
```bash
pip install -r requirements-dev.txt && python -m pytest -q
```

## 풀잎 이미지 바꾸기
`assets/README.md` 참고. 앱을 다시 빌드하지 않고도 `~/Library/Application Support/TypeGrass/assets/blades/` 에 PNG 를 넣으면 그쪽이 우선 사용됩니다.

## 문제 해결
| 증상 | 해결 |
|---|---|
| 숫자가 안 오름 / 권한 안내창 | 입력 모니터링 허용 후 앱 재실행 |
| 앱이 "확인되지 않은 개발자" 라며 막힘 | 우클릭 → 열기, 또는 `xattr -dr com.apple.quarantine /Applications/TypeGrass.app` |
| 앱을 업데이트했더니 다시 권한 요청 | 임시 서명 앱은 업데이트마다 서명이 바뀌어 권한이 초기화될 수 있음 (`docs/DISTRIBUTION.md`) |
| 포트 47831 사용 중 | 이미 실행 중. `--port` 로 변경 |
| 풀이 안 보임 | 타수가 적은 초반엔 드문드문. `--window --simulate` 로 확인 |

## 구조
```
typegrass/counter/  키 감지(listener_macos), 저장(store), 집계(tally), 조회 API(api), 앱 내장용(service)
typegrass/grass/    군락 알고리즘(layout), 풀밭 저장(meadow_store), 에셋/렌더링, 창/바탕화면/메뉴바
typegrass/app.py    올인원 앱     packaging/  .app 빌드     tools/  에셋·아이콘 생성
```
타수 측정(counter)과 시각화(grass)는 HTTP 로만 연결되어 서로 독립입니다.

## 라이선스
MIT (`LICENSE`). 서드파티: `THIRD_PARTY_NOTICES.md`. 기존 KeyCounter(MIT)는 설계 아이디어만 참고했고 코드는 복사하지 않았습니다.
