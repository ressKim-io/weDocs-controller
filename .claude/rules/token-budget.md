# Token Budget 원칙 (Opus 4.7 기준)

모든 대화에서 공통 적용되는 컨텍스트·토큰 운영 원칙.
Rules는 매 대화마다 주입되므로 핵심만 유지 — 상세는 `/token-budget` 스킬 참조.

## Context Window 관리 (Claude Code)

- MUST 컨텍스트 **80% 초과 시** 세션 종료 후 재시작
- MUST **무관한 태스크 전환** 시 `/clear`로 context reset
- PREFER **마일스톤 완료 직후** `/compact` 선제 실행 (차기 전)
- MUST 2회 이상 같은 실수 교정 시 `/clear` + 재프롬프트 — context 오염 방지
- NEVER 같은 파일 2회 이상 읽기 (`workflow.md` §Context 효율화 참조)

## Subagent를 Context 절약 도구로

Opus 4.7은 기본적으로 subagent를 덜 spawn하므로 필요 시 **명시 지시**.

- MUST **10+ 파일 탐색/조사**는 subagent에 위임 — 주 context 보호
- MUST 병렬 fan-out이 필요하면 프롬프트에 명시 — 예: "Use subagents to investigate X in parallel"
- NEVER 단일 함수 리팩토링·이미 읽은 파일 수정에 subagent 사용 (오버헤드만 발생)

## Effort Level 선택 (Opus 4.7)

| 레벨 | 사용 상황 | 비용 |
|------|---------|------|
| `xhigh` | **코딩/agentic 기본** (권장 시작점) | high 대비 ~2x |
| `high` | 지능 민감 작업 최소 기준 | 기본값 |
| `medium` | 비용 민감 + 품질 타협 | ~50% |
| `low` | 단순 조회·subagent·속도 우선 | ~25% |
| `max` | 진짜 frontier 문제만 | xhigh 대비 2x, +3%p만 |

- MUST 얕은 추론 관찰 시 prompting 우회 대신 effort 레벨 **상향**
- NEVER 일반 코딩에 `max` 사용 — overthinking 위험, 비용 대비 효과 미미
- PREFER Claude Code 기본값(`xhigh`) 유지 — 수동 설정 필요 시에만 조정

> 49 agents / 273 skills 카테고리별 effort 매핑: [`effort-guide.md`](effort-guide.md)

## Tokenizer & Prompt Cache (4.6 → 4.7)

- 같은 텍스트가 **1.0~1.35x 토큰** 사용 (최대 +35%)
- MUST `max_tokens` 파라미터에 **35% headroom** 확보
- MUST 클라이언트 쪽 토큰 추정 로직 **재검증** (fixed ratio 가정 파기)
- 4.6 prompt cache는 tokenizer 경계 변경으로 **전부 무효화** → 재빌드 가정
- **최소 cacheable 길이: 4096 tokens** (Opus 4.7 / 4.6 / 4.5 / Haiku 4.5). Sonnet 4.6 / 4.5 / Opus 4.1 은 1024. 짧은 prompt 는 cache 안 됨 (no error)
- 5-min TTL (default, 자동 refresh) / 1-hour TTL (write cost 2x base)

## Adaptive Thinking (4.7)

- Claude Code: 런타임 자동 관리 — **신경 쓰지 않음**
- API 직접 호출 (skill 예제 코드 등):
  - `thinking: {type: "adaptive"}` 명시 (기본 off)
  - NEVER `budget_tokens` 사용 (400 에러)
  - NEVER `temperature`·`top_p`·`top_k` 사용 (400 에러)

## 토큰 절약 실전

- PREFER 독립 파일은 **병렬 Read 호출** (한 응답에 묶기)
- MUST 큰 파일은 `wc -l` 선확인 후 범위 지정 읽기
- MUST 의도·제약·수락 기준·파일 경로 **첫 턴에 완전 명세** — 다회 왕복 금지
- PREFER Opus 4.7은 literal 해석 → 일반화가 필요하면 "유사 케이스에도 적용" **명시**

## 5가지 실패 패턴 (공식 문서)

- **Kitchen sink session** — 무관 태스크 축적 → `/clear`
- **Over-correction** — 2회 실패 시 `/clear` + 재프롬프트
- **Over-specified CLAUDE.md** — 룰 묻힘, 가지치기 필요
- **Trust-then-verify gap** — 검증(tests/scripts) 없이 ship 금지
- **Infinite exploration** — 범위 미설정 → subagent로 격리

---

상세 가이드, 코드 예시, Task Budget API, Prompt Caching 구조: `/token-budget` 스킬 참조
