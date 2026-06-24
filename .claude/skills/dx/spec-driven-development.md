---
name: spec-driven-development
description: "Spec-Driven Development with Claude Code — Claude Code에서 명세 기반 개발 워크플로우. Research → Spec → Plan → Execute → Review Use when working with dx 도메인의 패턴 / 구현 선택."
effort: low
deprecated: false
---

# Spec-Driven Development with Claude Code

Claude Code에서 명세 기반 개발 워크플로우. Research → Spec → Plan → Execute → Review

## Quick Reference (결정 트리)

```
작업 규모?
    │
    ├─ 소규모 (버그 수정, 단일 파일) ──> SDD 불필요, 바로 구현
    │
    ├─ 중규모 (기능 추가, 2~5 파일) ──> 경량 SDD
    │       └─ SPEC.md 작성 → Plan Mode → 구현
    │
    └─ 대규모 (시스템 설계, 6+ 파일) ──> 전체 SDD
            └─ Research Agent → SPEC.md → Plan → Task 분해 → Agent 팀

Claude Code 워크플로우?
    │
    ├─ 요구사항 불명확 ────> 인터뷰 모드 (Claude가 질문)
    ├─ 요구사항 명확 ──────> SPEC.md 직접 작성
    ├─ 기존 코드 분석 필요 ──> Research Agent 선행
    └─ 구현 시작 ─────────> Plan Mode → 승인 → 구현

스펙 수준?
    │
    ├─ spec-first ──────> 스펙 작성 → AI로 구현 (기본)
    ├─ spec-anchored ──> 스펙 유지, 코드와 함께 진화 (권장)
    └─ spec-as-source ─> 스펙이 소스, 인간은 스펙만 편집 (실험적)
```

---

## 핵심 원칙

### 왜 SDD인가?

```
기존: 대화형 개발                    SDD: 명세 기반 개발
─────────────────                   ─────────────────
"이거 만들어줘" → 구현 →             Spec 작성 → 스펙 리뷰 →
"아 이건 아닌데" → 수정 →             Plan 승인 → 구현 →
"이것도 추가" → 수정 →               (한 번에 완료)
"처음부터 다시" → ...
                                    리뷰 포인트: 구현이 아니라 스펙
```

- **코드 리뷰 대신 스펙 리뷰** — 구현 전에 방향을 확정
- **컨텍스트 효율** — 스펙 문서가 Agent에게 완전한 그림 제공
- **재현 가능** — 같은 SPEC.md로 다른 세션에서 동일 결과

### 3가지 스펙 수준

| 수준 | 설명 | 적합 |
|------|------|------|
| **Spec-First** | 스펙 작성 후 AI로 구현, 완료 후 스펙 폐기 | 일회성 기능 |
| **Spec-Anchored** | 스펙을 유지하며 코드와 함께 진화 | **대부분의 프로젝트 (권장)** |
| **Spec-as-Source** | 스펙이 진짜 소스, 인간은 스펙만 편집 | 실험적, Kiro 스타일 |

---

## Claude Code SDD 워크플로우

### 전체 흐름

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Research │───>│  Specify │───>│   Plan   │───>│ Execute  │───>│  Review  │
│ (조사)   │    │ (명세)   │    │ (설계)   │    │ (구현)   │    │ (검증)   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
  코드베이스      SPEC.md         Plan Mode      Agent 팀         Phase Gate
  분석/이해      작성/검토       Shift+Tab×2     병렬 구현        Success 검증
```

### Phase 1: Research — 코드베이스 이해

```
프롬프트 예시:
"search-service에 벡터 검색 기능을 추가하려고 합니다.
현재 검색 구조, DB 스키마, API 패턴을 조사해서 정리해주세요.
코드를 수정하지 말고 분석만 해주세요."
```

- Explore Agent로 병렬 조사 (최대 3개)
- 기존 패턴, 컨벤션, 아키텍처 파악
- 결과를 다음 단계의 컨텍스트로 활용

### Phase 2: Specify — SPEC.md 작성

**방법 A: 인터뷰 모드** (요구사항이 불명확할 때)

```
"벡터 검색 기능을 추가하고 싶어요.
AskUserQuestion 도구로 상세하게 인터뷰해주세요.
모든 질문이 끝나면 SPEC.md를 작성해주세요."
```

**방법 B: 직접 작성** (요구사항이 명확할 때)

```markdown
# SPEC.md

## Problem
현재 검색은 키워드 기반이라 의미 기반 검색이 불가능하다.

## Solution
PgVector를 활용한 벡터 검색 추가. 기존 키워드 검색과 하이브리드.

## Non-Goals
- 실시간 임베딩 업데이트 (배치로 처리)
- 다국어 검색 (한국어만)

## Success Criteria
- [ ] 의미 유사 검색 정확도 > 80% (수동 평가)
- [ ] P95 응답시간 < 200ms
- [ ] 기존 키워드 검색 성능 저하 없음
- [ ] 테스트 커버리지 > 80%

## Technical Constraints
- Go + PgVector (기존 PostgreSQL 활용)
- LangChainGo 임베딩 통합
- 기존 API 하위 호환 유지
```

**Phase Gate 1**: Non-Goals가 명확한가? Success Criteria가 측정 가능한가?

### Phase 3: Plan — Plan Mode 활용

```
Plan Mode 진입: Shift+Tab × 2

"SPEC.md를 기반으로 구현 계획을 세워주세요.
기존 코드 패턴에 맞춰서, 변경할 파일 목록과 순서를 정리해주세요."
```

Plan Mode에서 Claude는:
- 파일을 읽고 분석만 함 (수정 불가)
- 구현 계획을 plan 파일에 작성
- 사용자 승인 후에만 구현 시작

**Phase Gate 2**: 계획이 SPEC의 Success Criteria를 모두 커버하는가?

### Phase 4: Execute — 구현

```
단일 Agent:
  Plan 승인 → Claude가 순차 구현

Agent 팀 (대규모):
  Orchestrator가 Task 분해 →
  Agent A: 데이터 레이어 구현
  Agent B: API 엔드포인트 구현
  Agent C: 테스트 작성
  → 각 Agent에게 SPEC.md + 담당 부분 전달
```

**핵심**: 각 Agent에게 전체 SPEC.md를 전달하되, 담당 범위를 명확히 지정.

### Phase 5: Review — 검증

```markdown
## Review Checklist (SPEC.md의 Success Criteria 기반)

- [ ] 의미 유사 검색 정확도 > 80%
  → 테스트 결과: ___
- [ ] P95 응답시간 < 200ms
  → 벤치마크 결과: ___
- [ ] 기존 키워드 검색 성능 저하 없음
  → 회귀 테스트: ___
- [ ] 테스트 커버리지 > 80%
  → coverage: ___%
```

---

## SPEC.md 작성 가이드

### 필수 섹션

| 섹션 | 목적 | 없으면? |
|------|------|--------|
| **Problem** | 왜 이걸 하는가 | Agent가 방향을 잘못 잡음 |
| **Solution** | 어떤 방향으로 | Agent가 과도한 자유도 |
| **Non-Goals** | 뭘 안 하는가 | Agent가 스코프를 벗어남 |
| **Success Criteria** | 완료 기준 | "됐나?" 판단 불가 |

### 선택 섹션 (규모에 따라)

| 섹션 | 언제 |
|------|------|
| Technical Constraints | 기술 스택 제약이 있을 때 |
| API Design | 엔드포인트 변경/추가 시 |
| Data Model | DB 스키마 변경 시 |
| Open Questions | 미결 사항이 있을 때 |
| Alternatives Considered | 대안 비교가 필요할 때 |

### SPEC.md 크기 가이드

```
소규모 기능: 20-50줄 (Problem + Solution + Success Criteria)
중규모 기능: 50-100줄 (+ Non-Goals + Technical Constraints)
대규모 설계: 100-200줄 (+ API Design + Data Model + Alternatives)
```

---

## 실전 패턴

### 패턴 1: 새 세션에서 SPEC 기반 구현

```
세션 1: SPEC.md 작성 (인터뷰 / 분석)
         ↓
세션 2: "SPEC.md를 읽고 Plan Mode로 구현 계획을 세워주세요"
         → 깨끗한 컨텍스트 + 완전한 명세 = 최적 품질
```

### 패턴 2: GitHub spec-kit 스타일

```
specs/
├── 001-vector-search.md      # Specify
├── 001-vector-search-plan.md  # Plan
└── 001-vector-search-tasks.md # Tasks
```

### 패턴 3: Phase Gate 자동화 (hooks)

```json
// .claude/settings.json — Phase Gate hook
{
  "hooks": {
    "preToolCall": [{
      "matcher": "Edit|Write",
      "command": "test -f SPEC.md || (echo 'SPEC.md 없이 코드 수정 불가' && exit 1)"
    }]
  }
}
```

---

## 다른 방법론과의 관계

```
기획/전략 ────────────── 구현/실행
│                        │
├─ PRD (product-thinking.md)
│   └─ 비즈니스 요구사항 → SPEC의 Problem 섹션 입력
│
├─ RFC/ADR (rfc-adr.md)
│   └─ 아키텍처 결정 → SPEC의 Technical Constraints 입력
│
├─ Design Doc
│   └─ 시스템 설계 → SPEC의 Solution + API Design 입력
│
└─ SDD (이 문서) ◄─────── 위 산출물을 SPEC.md로 통합하여 AI 구현
```

- **PRD**: 비즈니스 "무엇을" → `product-thinking.md` 참조
- **RFC/ADR**: 기술 "왜 이렇게" → `rfc-adr.md` 참조
- **SDD**: 구현 "어떻게" → **이 문서**

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| SPEC 없이 "만들어줘" | 방향 불일치, 재작업 | 최소 Problem + Success Criteria |
| SPEC이 너무 상세 | 구현 자유도↓, Agent 경직 | Non-Goals로 범위만 잡기 |
| SPEC 작성 후 방치 | 구현과 스펙 괴리 | 구현 완료 시 스펙 최종 업데이트 |
| Plan 없이 바로 구현 | 큰 작업에서 일관성↓ | Plan Mode (Shift+Tab×2) 활용 |
| 모든 작업에 SDD 적용 | 과잉 프로세스 | 소규모는 바로 구현 |
| 한 세션에서 SPEC+구현 | 컨텍스트 오염 | 세션 분리 (SPEC → 새 세션 → 구현) |

---

## 체크리스트

### SPEC 작성
- [ ] Problem이 구체적이고 측정 가능
- [ ] Non-Goals가 명시됨
- [ ] Success Criteria가 측정 가능
- [ ] 기존 코드 패턴 조사 완료

### Plan
- [ ] Plan Mode에서 구현 계획 승인
- [ ] 변경 파일 목록과 순서 확정
- [ ] Success Criteria 커버 확인

### Execute & Review
- [ ] SPEC 기반 구현 완료
- [ ] Success Criteria 전체 검증
- [ ] 테스트 통과
- [ ] SPEC.md 최종 업데이트 (spec-anchored)

---

## 참조 스킬

- `product-thinking.md` — PRD, RICE, Story Mapping (비즈니스 기획)
- `rfc-adr.md` — RFC/ADR 워크플로우 (아키텍처 결정)
- `agentic-coding.md` — Agentic Coding 모드, Agent Supervision
- `ai-first-playbook.md` — AI-First 조직 전략, 워크플로우 재설계
- `engineering-strategy.md` — Tech Radar, 로드맵, 기술 부채 관리

---

## Sources

- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices)
- [Spec-Driven Development with Claude Code](https://heeki.medium.com/using-spec-driven-development-with-claude-code-4a1ebe5d9f29)
- [Panaversity: SDD with Claude Code](https://agentfactory.panaversity.org/docs/General-Agents-Foundations/spec-driven-development)
- [Kiro: Agentic AI Development](https://kiro.dev/)
