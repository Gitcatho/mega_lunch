# mega-lunch

메가스터디 구내식당의 주간 식단표를 Discord에서 확인하는 봇입니다.
네이버 블로그에 게시된 식단표를 주차별로 찾아 오늘·내일 메뉴를 보기 좋게 잘라서 보여줍니다.

## 기능

| 명령어 | 설명 |
|---|---|
| `/오늘점심` | 오늘 점심 메뉴를 표시합니다. 주말에는 휴무를 안내합니다. |
| `/내일점심` | 내일 점심 메뉴를 표시합니다. 일요일에는 다음 주 월요일 메뉴를 조회합니다. |
| `/이번주` | 이번 주 전체 식단표를 표시합니다. |
| `/다음주` | 다음 주 전체 식단표를 표시합니다. 게시 전에는 안내 메시지를 반환합니다. |

봇은 한국 표준시(KST)를 사용합니다. 식단표 게시일에 7일을 더해 실제 메뉴 주차를 계산하므로,
공휴일 등의 이유로 게시물이 금요일보다 일찍 올라와도 다음 주 식단표로 처리합니다.

## 프로젝트 구조

```text
app.py                    디스호스트 및 로컬 실행 진입점
mega_lunch/
  bot.py                  Discord 봇과 슬래시 명령어
  calendar.py             날짜, 요일 및 ISO 주차 계산
  source.py               네이버 블로그 게시물 조회
  cache.py                이미지 다운로드, 자르기 및 파일 캐시
  service.py              게시물 조회와 캐시 조정
  settings.py             환경변수와 실행 설정
  models.py               내부 데이터 모델
tests/
  test_calendar.py        주차 경계와 내일 메뉴 계산 테스트
```

## 요구 사항

- Python 3.10 이상
- Discord 봇 토큰
- 외부 네트워크 연결

## 설치

```bash
git clone https://github.com/Gitcatho/mega_lunch.git
cd mega_lunch
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell에서는 가상환경을 다음과 같이 활성화합니다.

```powershell
.venv\Scripts\Activate.ps1
```

## Discord 봇 설정

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 애플리케이션과 봇을 생성합니다.
2. OAuth2 URL Generator에서 `bot`, `applications.commands` 스코프를 선택해 서버에 초대합니다.
3. 프로젝트 루트에 `.env` 파일을 만들고 토큰을 설정합니다.

```env
DISCORD_TOKEN=your_discord_bot_token
```

토큰은 환경변수, `.env`, `token.txt` 순으로 읽습니다. 토큰 파일은 Git에 포함되지 않습니다.
토큰이 노출되면 Developer Portal에서 즉시 재발급하세요.

## 실행

```bash
python app.py
```

로그에 `로그인 완료`가 표시되면 사용할 수 있습니다. Discord의 전역 슬래시 명령어 반영에는 시간이 조금 걸릴 수 있습니다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

테스트에는 다음 항목이 포함됩니다.

- 게시일과 실제 식단 주차의 매핑
- 목요일 등 조기 게시 상황
- 연말·연초 ISO 주차 경계
- 평일과 주말 판별
- 일요일 기준 `/내일점심`의 다음 주 월요일 계산

## 선택 설정

블로그나 식단표 레이아웃이 변경되면 환경변수로 기본 설정을 조정할 수 있습니다.

| 환경변수 | 기본값 | 설명 |
|---|---:|---|
| `MENU_BLOG_ID` | `megafs01` | 식단표를 게시하는 네이버 블로그 ID |
| `MENU_CATEGORY_NO` | `41` | 조회할 블로그 카테고리 번호 |
| `MENU_TITLE_KEYWORD` | `[메가스터디 구내식당]` | 식단표 게시물 제목 식별 문자열 |
| `MENU_REQUEST_TIMEOUT` | `10` | 외부 요청 제한 시간(초) |
| `MENU_CROP_TOP` | `0.232` | 이미지 높이 대비 메뉴 영역 시작점 |
| `MENU_CROP_HEIGHT` | `0.25` | 이미지 높이 대비 메뉴 영역 높이 |
| `MENU_CROP_LEFT` | `0.169` | 이미지 폭 대비 월요일 영역 시작점 |
| `MENU_CROP_WIDTH` | `0.81` | 이미지 폭 대비 월~금 전체 영역 폭 |

## 캐시와 운영

- 다운로드와 이미지 처리는 주차별 최초 요청에서 한 번만 실행합니다.
- 생성한 파일은 `cache/`에 저장하며 이번 주와 다음 주 캐시만 유지합니다.
- 다운로드 크기와 이미지 픽셀 수에 상한을 적용합니다.
- 블로그 HTML 또는 식단표 이미지 레이아웃이 바뀌면 조회나 이미지 자르기가 실패할 수 있습니다.
- 식단의 정확한 원본은 네이버 블로그 게시물을 기준으로 합니다.

## 저작권

이 저장소의 새 구현 코드는 프로젝트에 포함된 기능 요구사항을 바탕으로 작성되었습니다.
식단표 게시물과 이미지의 권리는 해당 콘텐츠의 권리자에게 있습니다.

공개 배포 전에는 저장소의 이전 Git 이력에 제3자의 코드가 포함되어 있지 않은지 확인해야 합니다.
새 구현에 오픈소스 라이선스를 적용하려면 이전 이력과 외부 콘텐츠의 권리 관계를 먼저 정리하세요.
