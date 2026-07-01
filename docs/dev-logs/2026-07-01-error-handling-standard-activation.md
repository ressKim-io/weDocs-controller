---
date: 2026-07-01
category: meta
tier: 2
importance: major
status: resolved
tags: [error-handling, code-review, phase-workflow, rules, gate-wiring, standard-activation]
related:
  - rules/error-handling.md
---

# 첫 크래프트 표준 활성화 — error-handling.md + 리뷰 게이트 배선

## Context
- 배경: AI가 에러 처리 "방법"을 몰라서가 아니라 "활용을 안 해서" raw 예외·삼킨 예외가 산재. availability(문서 존재)만으로는 부족 — verification(리뷰 게이트 강제)까지 만나야 activation.
- 목표: 언어 무관 원칙(P1~6) + Java/Rust 언어별 실현 + `[B]`/`[A]` 체크리스트를 담은 표준 문서를 작성하고, 문서 작성으로 끝내지 않고 `code-review.md`/`phase-workflow.md` 게이트에 실제로 배선.
- 이 표준이 **첫 사례** — 같은 틀(원칙 P1~N + 언어별 실현 + 체크리스트 + 게이트 배선)을 concurrency·layering·observability 표준에도 순차 복제 예정.

## 한 일

### 1. `.claude/rules/error-handling.md` 신규 작성
- `paths: **/*.java, **/*.rs, **/*.py` 스코프.
- 원칙 P1(경계 집중)~P6(관측 연결) 언어 무관 정의.
- Java/Spring 실현: `@RestControllerAdvice` + `ProblemDetail`(RFC 9457) 중앙화, sealed 도메인 예외 계층, Lombok/record로 보일러플레이트 제거(엔티티엔 `@Data` 금지 명시).
- Rust 실현: `thiserror` derive(라이브러리) vs `anyhow`(바이너리), `?` 전파, gRPC 경계 `From<EngineError> for Status` 매핑.
- **사실 확인**(`deep-thinking.md` 검증 의무): 문서가 인용한 "현재 엔진 코드는 수동 impl Display+Error" 주장을 `weDocs-crdt-engine/src/engine.rs` 실제 조회로 검증 → 정확(수동 `impl fmt::Display`/`impl std::error::Error` 존재, `Cargo.toml`에 `thiserror` 없음). production `src/` 내 `unwrap`/`expect` 0건도 확인 — P5는 이미 준수 중이며 실제 갭은 P2(전용 에러 타입 부재는 아님)·P4(원인을 `.to_string()`으로 버림) 쪽.
- `[B]`(blocking)/`[A]`(advisory) 체크리스트 태그를 이 문서에서 최초 정의 — 후속 표준 문서들이 재사용할 공통 표기.

### 2. 게이트 배선
- `code-review.md` 멀티 관점 표에 `Rust 크래프트`(🦀, `rust-expert`) · `Java 크래프트`(☕, `java-expert`) 2행 추가. "3개 관점" → "5개 관점" 텍스트도 동기화(표만 바꾸고 카운트 문구를 안 갱신하면 즉시 stale — 이 표준 문서가 지적하는 "일관성" 원칙을 스스로 어길 뻔한 지점).
- `phase-workflow.md` Gate 3에 "표준 체크리스트 `[B]` 위반 = 반려, 새 갭은 체크리스트로 승격(gap→standard loop 폐쇄)" 1줄 추가 — 기존 `code-review.md`의 리뷰 갭 추적(`docs/review-gaps.md`) 메커니즘과 연결.
- `CLAUDE.md` "상황별 룰" 인덱스에 `error-handling.md` 등록 — 신규 rule 파일은 인덱스 갱신 없이는 다음 세션이 발견 불가.

### 3. 보류 — 개인 컬렉션(`ress-claude-agents`) 승격
- 원계획: 재사용을 위해 `ress-claude-agents/rules/`에도 동일 파일 승격.
- 로컬 전체 검색(`find` maxdepth 5·6, `mdfind`)으로도 클론된 경로를 찾지 못함 — memory 기록상 원격 `git@github.com:ressKim-io/ress-claude-agents.git`만 확인.
- 사용자 확인 결과: **일단 controller만 적용, 개인 컬렉션 승격은 스킵**(2026-07-01). 로컬 경로가 확보되면 재개.

## 결정 (decisions)
- `[B]`/`[A]` 체크리스트 태그는 **표준 문서 자체에서 정의**하고 `phase-workflow.md`는 일반 참조만 한다 — 표준마다 반복 정의하지 않고 `error-handling.md`가 관례를 만들면 후속 표준(concurrency 등)이 그대로 재사용.
- 멀티 관점 표에서 새 행은 기존 3열 스키마(관점/태그/핵심체크)를 그대로 유지 — 사용자 원안은 "관점" 열에 이모지+라벨, "태그" 열에 에이전트명을 넣는 형태였으나, 기존 "태그" 열이 PR 코멘트 포맷(`[CR-001] 🔒 제목`)의 이모지 소스로 재사용되는 구조라 스키마를 깨지 않도록 이모지는 태그 열에 두고 에이전트명+체크리스트 참조는 핵심체크 열로 재배치.

## 다음 세션 할 일 (TODO)
1. `ress-claude-agents` 로컬 클론 경로가 확보되면 `error-handling.md` 승격 진행.
2. 다음 표준(concurrency/layering/observability) 작성 시 이번 활성화 패턴(표준 문서 + 멀티관점 표 2행 + phase-workflow 1줄 + CLAUDE.md 인덱스 등록)을 그대로 반복.
3. (선택, 별도 세션 범위) crdt-engine `EngineError::Codec(String)`이 `.to_string()`으로 원인을 버리는 P4 위반이 실제 코드에 존재 — 표준을 기존 코드에 소급 적용하는 것은 이번 작업 범위 밖.

## 관련 자료
- `.claude/rules/error-handling.md` — 표준 본문
- `.claude/rules/code-review.md` §멀티 관점 리뷰 — 게이트 배선 지점
- `.claude/rules/phase-workflow.md` §Gate 3 — 반려 조건
- 원본 컬렉션(승격 보류): `git@github.com:ressKim-io/ress-claude-agents.git`
