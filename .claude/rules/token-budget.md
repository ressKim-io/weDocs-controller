# Token Budget 원칙 (Claude 5 / Opus 4.8 세대 기준)

모든 대화에서 공통 적용되는 컨텍스트·토큰 운영 원칙.
Rules는 매 대화마다 주입되므로 핵심만 유지 — 상세는 `/token-budget` 스킬 참조.

> 모델·수치 출처: [prompt-caching](https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching) · [effort](https://platform.claude.com/docs/en/docs/build-with-claude/effort) · [models overview](https://platform.claude.com/docs/en/docs/about-claude/models/overview) (✅ verified 2026-07-17, WebFetch)

## Context Window 관리 (Claude Code)

- MUST 컨텍스트 **80% 초과 시** 세션 종료 후 재시작
- MUST **무관한 태스크 전환** 시 `/clear`로 context reset
- PREFER **마일스톤 완료 직후** `/compact` 선제 실행 (차기 전)
- MUST 2회 이상 같은 실수 교정 시 `/clear` + 재프롬프트 — context 오염 방지
- NEVER 같은 파일 2회 이상 읽기 (`workflow.md` §Context 효율화 참조)

## Subagent를 Context 절약 도구로

- MUST **10+ 파일 탐색/조사**는 subagent에 위임 — 주 context 보호
- MUST 병렬 fan-out이 필요하면 프롬프트에 명시 — 예: "Use subagents to investigate X in parallel"
- NEVER 단일 함수 리팩토링·이미 읽은 파일 수정에 subagent 사용 (오버헤드만 발생)

## Effort Level 선택

매핑·모델별 지원표·기본값은 [`effort-guide.md`](effort-guide.md)가 SOT. 핵심만:

- **기본값 = `high`** (API·Claude Code·claude.ai 전 surface — "Claude Code 기본 xhigh"는 Opus 4.7 시절 정보로 폐기)
- Opus 4.8 코딩/agentic은 `xhigh` **명시 지정** 권장 · Fable 5는 `high`로 시작(낮은 effort로도 이전 세대 xhigh 이상인 경우 많음)
- MUST 얕은 추론 관찰 시 prompting 우회 대신 effort 레벨 **상향**
- NEVER 일반 코딩에 `max` 사용 — overthinking 위험, 비용 대비 이득 작음(공식 가이드)
- **Haiku 4.5는 effort 미지원**

## Tokenizer & Prompt Cache (✅ 2026-07-17)

- Fable 5·Opus 4.8/4.7 세대 tokenizer: **pre-4.7 모델 대비 같은 텍스트 ~30% 더 많은 토큰**(공식 "roughly 30% more", 내용에 따라 변동) → `max_tokens`에 ~30% headroom, 클라이언트 토큰 추정 로직 fixed-ratio 가정 금지
- **최소 cacheable 길이 (모델별 상이 — 구버전 "4096 일괄"은 폐기)**: Fable 5 = **512** / Opus 4.8·Sonnet 5·Sonnet 4.6 = **1024** / Opus 4.7 = **2048** / Haiku 4.5 = **4096**. 미만은 무에러로 캐시 스킵
- TTL: **5분**(기본, write 1.25x base) / **1시간**(`ttl: "1h"`, write 2x base) · cache read = **0.1x base**

## Adaptive Thinking

- Claude Code: 런타임 자동 관리 — **신경 쓰지 않음**
- API 직접 호출 (skill 예제 코드 등):
  - Fable 5: 상시 on — `thinking` 설정 불요, `{type: "disabled"}`는 **거부됨**
  - Opus 4.8 / 4.7: `thinking: {type: "adaptive"}` 명시 — manual `budget_tokens`는 **400 에러**
  - Sonnet 5: 기본 on — `{type: "disabled"}`로 끌 수 있음
  - thinking 깊이 제어 수단 = **effort** (`output_config: {effort: ...}`)

## 토큰 절약 실전

- PREFER 독립 파일은 **병렬 Read 호출** (한 응답에 묶기)
- MUST 큰 파일은 `wc -l` 선확인 후 범위 지정 읽기
- MUST 의도·제약·수락 기준·파일 경로 **첫 턴에 완전 명세** — 다회 왕복 금지
- PREFER 낮은 effort는 literal 해석 경향 → 일반화가 필요하면 "유사 케이스에도 적용" **명시**

## 5가지 실패 패턴 (공식 문서)

- **Kitchen sink session** — 무관 태스크 축적 → `/clear`
- **Over-correction** — 2회 실패 시 `/clear` + 재프롬프트
- **Over-specified CLAUDE.md** — 룰 묻힘, 가지치기 필요
- **Trust-then-verify gap** — 검증(tests/scripts) 없이 ship 금지
- **Infinite exploration** — 범위 미설정 → subagent로 격리

---

상세 가이드, 코드 예시, Prompt Caching 구조: `/token-budget` 스킬 참조 (⚠️ 스킬 본문도 Opus 4.7 기준일 수 있음 — 수치는 본 rule이 우선)
