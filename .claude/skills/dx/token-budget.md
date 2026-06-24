---
name: token-budget
description: "Claude Opus 4.7 토큰·컨텍스트·effort 운영 심화 가이드. Context Window(1M), Subagent 위임 전략, Effort Level, Task Budget API, Prompt Caching, Adaptive Thinking, Tokenizer 변경 대응을 공식 문서 기반 코드 예시와 함께 제공."
category: dx
---

# Token Budget 심화 가이드 (Opus 4.7)

`.claude/rules/token-budget.md`의 상세판. API 파라미터, 코드 예시, 비용 계산 포함.
Claude Code 세션 내 도구 사용 효율은 `/token-efficiency` 참조.

## Quick Reference

| 상황 | 해결책 | 참조 |
|------|------|------|
| context 80% 도달 | `/clear` 또는 세션 재시작 | #context-window |
| 탐색성 작업 10+ 파일 | subagent 위임 | #subagent-delegation |
| 코딩/agentic 작업 | effort `xhigh` | #effort-level |
| agentic loop 비용 제어 | Task Budget (beta) | #task-budget |
| 반복 prompt 90% 절감 | Prompt Caching | #prompt-caching |
| 모델 전환 후 캐시 무효화 | tokenizer 변경 대응 | #tokenizer-change |

---

## Context Window (1M tokens)

### Claude Code vs API

| 항목 | Claude Code | Messages API |
|------|------------|--------------|
| Context size | 1M tokens (자동) | 1M tokens |
| 80% 경고 | 상태바 표시 | 클라이언트 직접 추적 |
| Compaction | `/compact` 명령 | 수동 구현 |
| Cache management | 자동 | `cache_control` 수동 |

### 세션 관리 원칙 (Claude Code)

```
# 무관 태스크 전환
/clear

# 마일스톤 완료 직후 (선제)
/compact Focus on API changes and test results

# 부분 요약 (checkpoint에서)
Esc + Esc → 메시지 선택 → "Summarize from here"

# 세션 간 이동
/rename oauth-migration
claude --resume
```

### 공식 실패 패턴 (Claude Code Best Practices)

- **Kitchen sink session** — 무관 태스크 누적 → `/clear`
- **Over-correction** — 2회 이상 같은 실수 교정 → `/clear` + 재프롬프트
- **Over-specified CLAUDE.md** — 룰 묻힘 → 가지치기 (ask "removing this causes mistakes?")
- **Trust-then-verify gap** — 검증(tests/scripts) 없이 ship 금지
- **Infinite exploration** — 범위 미설정 → subagent로 격리

---

## Subagent Delegation (Opus 4.7 특화)

### 핵심 변화

Opus 4.7은 subagent를 **기본적으로 덜 spawn**한다. 필요 시 명시 지시.

### 위임 기준

| 상황 | 주 대화 | Subagent |
|------|----|----|
| 10+ 파일 탐색/조사 | ❌ | ✅ |
| 복잡 코드베이스 구조 파악 | ❌ | ✅ |
| 리뷰/검증 (편향 방지) | ❌ | ✅ |
| 단일 함수 리팩토링 | ✅ | ❌ |
| 이미 읽은 파일 수정 | ✅ | ❌ |

### 명시 지시 패턴

```
# ✅ Fan-out 필요
"Use subagents to investigate X, Y, Z in parallel and report back"
"Spawn specialists for each of: frontend, backend, database"

# ✅ Context 격리
"Use a subagent to explore the auth system and summarize findings"

# ❌ 모호 (4.7은 spawn 안 함)
"Look into this codebase"
```

### 공식 Writer/Reviewer 패턴

| Session A (Writer) | Session B (Reviewer) |
|--------------------|----------------------|
| "Implement rate limiter" | - |
| - | "Review @src/middleware/rateLimiter.ts for race conditions" |
| "Address: [Session B feedback]" | - |

Fresh context = 편향 없는 리뷰.

---

## Effort Level (Opus 4.7)

### 레벨별 특성

| 레벨 | 비용 | 사용 상황 |
|------|------|---------|
| `max` | xhigh 대비 2x, +3%p만 | 진짜 frontier 문제만. 일반 코딩 금지 (overthinking 위험) |
| `xhigh` | high 대비 ~2x | **코딩/agentic 기본** (권장) |
| `high` | 기본값 | 지능 민감 작업 최소 기준 |
| `medium` | ~50% | 비용 민감 + 품질 타협 |
| `low` | ~25% | 단순 조회·subagent·속도 우선 |

### API 코드 예시

```python
import anthropic

client = anthropic.Anthropic()

# 코딩/agentic → xhigh
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=64000,  # xhigh는 64k 이상 권장
    output_config={"effort": "xhigh"},
    messages=[{"role": "user", "content": "..."}],
)

# 분류·단순 추출 → low
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=2048,
    output_config={"effort": "low"},
    messages=[{"role": "user", "content": "..."}],
)
```

### 얕은 추론 감지 시

```
# ❌ prompting으로 우회
"This is complex. Think very carefully..."

# ✅ effort 레벨 상향
output_config={"effort": "xhigh"}
```

단, `low`를 유지해야 할 이유(지연)가 있으면 타겟팅된 가이드 추가:
```
"This task involves multi-step reasoning. Think carefully before responding."
```

---

## Task Budget (beta, API only)

> **Claude Code 미지원**. Messages API 직접 호출 시만 해당.

### 핵심 특성

- **Advisory cap** (soft hint) — hard cap 아님
- **Agentic loop 전체** target (multiple requests 합산)
- **최소 20,000 토큰** (아래는 400 에러)
- `max_tokens`와 **독립** (per-request ceiling과 다름)

### API 사용법

```python
response = client.beta.messages.create(
    model="claude-opus-4-7",
    max_tokens=128000,  # per-request hard cap
    output_config={
        "effort": "high",
        "task_budget": {"type": "tokens", "total": 64000},  # loop advisory
    },
    messages=[...],
    betas=["task-budgets-2026-03-13"],
)
```

### Budget 크기 결정 (공식 권장)

1. 대표 샘플을 **budget 없이** 실행
2. `usage.output_tokens` + thinking + tool result 토큰 합산
3. **p99 값**을 초기 budget으로 설정
4. 테스트하며 ±20% 조정

### 주의 사항

| 패턴 | 결과 |
|------|------|
| 너무 작은 budget | **refusal-like behavior** — 작업 거부하거나 조기 종료 |
| Follow-up마다 `remaining` 변경 | **cache prefix 무효화** (90% 절감 소실) |
| 오픈엔디드 품질 우선 작업에 사용 | 부적합 — budget 설정하지 말 것 |

### Caching 보존 패턴

```python
# ✅ 초기 요청에만 budget 설정
output_config = {"effort": "high", "task_budget": {"type": "tokens", "total": 128000}}

# ✅ 후속 요청: budget 생략, 서버가 countdown 유지
# (단, compaction이 있을 때만 remaining 재전달)

# ❌ 매번 remaining 감소하며 전달 → cache 무효화
output_config = {"task_budget": {"total": 128000, "remaining": 89000}}  # 매 turn 바뀜
```

---

## Prompt Caching

### 경제학 (Opus 4.7 $5/MTok 기준)

| 비용 | 배수 | 실제 |
|------|------|------|
| 기본 입력 | 1.0x | $5/MTok |
| 5분 캐시 쓰기 | 1.25x | $6.25/MTok |
| 1시간 캐시 쓰기 | 2.0x | $10/MTok |
| **캐시 읽기** | **0.1x** | **$0.50/MTok (90% 절감)** |

ROI: 1회 재사용만 해도 5분 TTL 회수, 2회면 1시간 TTL 회수.

### 구조 규칙 (MUST)

```python
# ✅ 정적 → 동적 순서, 캐시 지점은 불변 블록
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are a legal document analyst.",  # 정적
        },
        {
            "type": "text",
            "text": f"[50페이지 문서]",                     # 정적 대용량
            "cache_control": {"type": "ephemeral"},         # ← 여기 캐시
        },
    ],
    messages=[
        {"role": "user", "content": "주요 조항 분석"},      # 동적 (뒤)
    ],
)
```

### 안티패턴

```python
# ❌ 변동 콘텐츠에 cache_control
{"text": f"Current time: {now()}", "cache_control": {...}}

# ❌ 짧은 TTL을 긴 TTL보다 앞에
system=[
    {"text": "...", "cache_control": {"type": "ephemeral"}},          # 5분
    {"text": "...", "cache_control": {"type": "ephemeral", "ttl": "1h"}},  # 1시간 (역순 — 무효화)
]
```

### TTL 선택

| TTL | 용도 |
|-----|------|
| **5분 (기본)** | 빈번한 반복, 자주 쓰는 시스템 프롬프트 |
| **1시간** | 장기 agentic 루프, 사용자 응답 대기 긴 대화 |

### 캐시 무효화 조건

| 변경 | 도구 캐시 | 시스템 캐시 | 메시지 캐시 |
|------|---------|----------|----------|
| 도구 정의 수정 | ✘ | ✘ | ✘ |
| tool_choice 변경 | ✓ | ✓ | ✘ |
| 이미지 추가/제거 | ✓ | ✓ | ✘ |
| thinking 파라미터 | ✓ | ✓ | ✘ |

### 성능 모니터링

```python
print(response.usage)
# {
#   "cache_read_input_tokens": 100000,      # ← 캐시 적중
#   "cache_creation_input_tokens": 248,
#   "input_tokens": 50,
# }
```

`cache_read_input_tokens`와 `cache_creation_input_tokens` 모두 0이면 캐시 미작동 — 최소 토큰 길이(1024~4096), 캐시 지점 위치, TTL 내 재요청 여부 점검.

### Workspace Isolation (2026-02-05부터)

- Anthropic API: Organization → **Workspace** 격리
- Bedrock/Vertex: 조직 수준 유지 (미변경)
- 영향: 여러 workspace 사용 시 독립 캐시 — 전략 재검토

---

## Adaptive Thinking

### 4.6 → 4.7 변경

```python
# ❌ Before (Opus 4.6) — 4.7에서 400 에러
thinking = {"type": "enabled", "budget_tokens": 32000}

# ✅ After (Opus 4.7)
thinking = {"type": "adaptive"}
output_config = {"effort": "high"}  # 깊이는 effort로 제어
```

### 기본값 주의

- Opus 4.7에서 **adaptive thinking은 기본 off**
- `thinking` 필드 없으면 사고 안 함 (4.6 default와 동일)
- 필요 시 `thinking: {"type": "adaptive"}` 명시

### Thinking 표시

```python
# 기본: omitted (응답 속도 향상)
# UI에 표시하려면:
thinking = {
    "type": "adaptive",
    "display": "summarized",  # 또는 "omitted"
}
```

### 제거된 파라미터 (4.7)

- `temperature`, `top_p`, `top_k` — 400 에러
- `thinking.budget_tokens` — 400 에러
- assistant message prefill — 400 에러

---

## Tokenizer 변경 (4.6 → 4.7)

### 영향

- 같은 텍스트 **1.0~1.35x 토큰** 사용 (content type 따라)
- `/v1/messages/count_tokens` 결과값 변화
- 4.6 prompt cache 전부 **무효화** (tokenizer 경계 변경)

### 대응 체크리스트

- [ ] `max_tokens` 파라미터 **35% headroom** 추가
- [ ] Compaction 트리거 임계값 재조정
- [ ] 클라이언트 쪽 토큰 추정 로직 재검증
- [ ] 모델 전환 후 cache 재빌드 가정
- [ ] xhigh/max effort에서 `max_tokens` 64k 이상

---

## 비용 계산 예시

### 시나리오: 코드 리뷰 에이전트 (agentic loop)

```
가정:
- System prompt (정적): 5,000 토큰 (cache 후보)
- 리포 context (정적): 50,000 토큰 (cache 후보)
- 리뷰 질문 (동적): 평균 500 토큰
- 응답 (reasoning + text): 10,000 토큰
- 일 100회 호출
```

### Prompt Caching 적용 전

```
입력:  55,500 × $5/M    = $0.278/회
출력:  10,000 × $25/M   = $0.250/회
──────────────────────────
회당: $0.528
일:   $52.80 (100회)
월:   $1,584
```

### Prompt Caching 적용 후 (5분 TTL)

```
첫 요청 (cache write):
  입력 cache write: 55,000 × $6.25/M = $0.344
  입력 basic:          500 × $5/M     = $0.003
  출력:             10,000 × $25/M    = $0.250
  = $0.597

이후 99회 (cache hit):
  입력 cache read:  55,000 × $0.50/M  = $0.0275
  입력 basic:          500 × $5/M     = $0.003
  출력:             10,000 × $25/M    = $0.250
  = $0.281/회

일 총:  $0.597 + ($0.281 × 99) = $28.4 (46% 절감)
월:     $852 (연 $8,784 절감)
```

---

## 체크리스트

### 작업 전
- [ ] context 80% 미만 확인
- [ ] 무관 태스크면 `/clear` 실행
- [ ] 10+ 파일 탐색이면 subagent 지시 명시

### 프롬프트 작성
- [ ] 의도·제약·수락 기준·파일 경로 첫 턴에 완전 명세
- [ ] Opus 4.7 literal 해석 대응 (일반화 필요 시 명시)
- [ ] Positive framing 선호 ("Don't X" → "Do Y")

### API 호출
- [ ] `effort` 명시 (`xhigh` 기본)
- [ ] `max_tokens` 64k 이상 (xhigh/max)
- [ ] 제거된 파라미터 확인 (`temperature`, `budget_tokens` 등)
- [ ] Prompt cache 구조 정적→동적 순서

### Task Budget (해당 시)
- [ ] 최소 20k 토큰
- [ ] Follow-up에서 `remaining` 변경 금지 (cache 보존)
- [ ] 오픈엔디드 작업엔 미사용

---

## 참조

- `rules/token-budget.md` — 핵심 원칙 (auto-load)
- `/token-efficiency` — Claude Code 세션 내 도구 사용 효율
- `/clean-code` — 코드 가독성 원칙
- [공식: What's new in Claude Opus 4.7](https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7)
- [공식: Task budgets](https://platform.claude.com/docs/en/build-with-claude/task-budgets)
- [공식: Effort parameter](https://platform.claude.com/docs/en/build-with-claude/effort)
- [공식: Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [공식: Best Practices for Claude Code](https://code.claude.com/docs/en/best-practices)
