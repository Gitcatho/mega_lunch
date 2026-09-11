# 변경 이력

이 프로젝트의 주요 변경 사항을 이 파일에 기록합니다.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따르며,
버전은 [Semantic Versioning](https://semver.org/spec/v2.0.0.html)을 따릅니다.

## [미출시]

### 추가

- `/배고파`에 주말, 점심 전, 70분 점심시간, 퇴근 전과 퇴근 후 응답을 추가합니다. 관리자는 `/점심시간설정`, `/퇴근시간설정`으로 서버 공통 `HH:MM` 일정을 저장할 수 있으며 기본 점심시간은 12:00입니다. (commit: f9fec14)
- 매주 토요일 오전 9시(KST)에 다음 주 식단표를 미리 캐시하여 최초 명령이 준비된 캐시를 사용하게 합니다. 사전 캐시 실패는 봇을 중단하지 않고 로그로 남깁니다. (commit: b83f1fa)

### 버그 수정 (Fixed)

- 주간 이미지의 세로 위치가 달라져도 요일별 이미지가 어긋나지 않고 Take-Out 영역을 제외하도록 식단표 경계를 감지하며, 검출 실패 시 설정된 크롭 비율을 사용합니다. (commit: 78a97c2)

[미출시]: https://github.com/Gitcatho/mega_lunch/compare/main...HEAD
