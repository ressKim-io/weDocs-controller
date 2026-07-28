# Token Budget 원칙 — 세션 운영

상시 로드. **수치는 여기 두지 않는다** — 모델 라인업·가격·effort 매핑·캐시 최소 길이/TTL·
tokenizer 증가율·adaptive thinking API 설정은 전부 `/context-and-effort` 스킬에 있다.
자주 바뀌는 값을 상시 로드에 두면 그 자리가 곧 드리프트 지점이 된다.

## 세션 관리

- MUST 컨텍스트 **80% 초과 시** 세션 종료 후 재시작 · **무관한 태스크 전환** 시 `/clear`
- MUST 같은 실수를 **2회 이상** 교정하게 되면 `/clear` + 재프롬프트 — 오염된 컨텍스트로 계속 가지 않는다
- PREFER 마일스톤 완료 직후 `/compact` 선제 실행

## 읽기 비용

- NEVER 같은 파일을 2회 이상 읽는다 (`workflow.md` §EXPLORE)
- MUST 큰 파일은 `wc -l` 선확인 후 범위 지정 읽기
- PREFER 독립적인 파일들은 **한 응답에 병렬 Read**

## Subagent

- MUST **10+ 파일 탐색/조사**는 subagent에 위임 — 주 컨텍스트를 보호한다
- NEVER 단일 함수 리팩토링·이미 읽은 파일 수정에 subagent (오버헤드만 발생)
- subagent의 effort는 주 에이전트와 **독립** — 가벼운 fan-out은 낮게, 깊은 분석만 높게

## 프롬프트

- MUST 의도·제약·수락 기준·파일 경로를 **첫 턴에 완전 명세** — 다회 왕복이 가장 비싸다
- 낮은 effort는 literal 해석 경향 → 일반화가 필요하면 "유사 케이스에도 적용"을 **명시**
- MUST 얕은 추론이 관찰되면 prompting 우회 대신 **effort 레벨을 올린다**

## 실패 패턴 (공식)

무관 태스크 축적 → `/clear` · 2회 실패 후 같은 시도 반복 → `/clear`+재프롬프트 ·
룰이 묻힐 만큼 비대한 CLAUDE.md → 가지치기 · 검증 없이 ship → 테스트/스크립트 ·
범위 없는 탐색 → subagent로 격리.
