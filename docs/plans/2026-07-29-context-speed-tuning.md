---
date: 2026-07-29
slug: context-speed-tuning
status: done
related:
  - plans/2026-07-28-claude-context-budget.md
  - dev-logs/2026-07-29-context-speed-tuning.md
---

# Claude Code 속도 저하 진단 · 설정 튜닝

> 세션 체감 저속("느린데 퀄리티는 그만큼 아님")의 원인을 전수 진단하고 전역·레포 설정을 교정한다.
> 성공 조건 = 전역 model/effort 교정 + 에이전트 effort 티어 정합 + Bash 훅 오버헤드 제거 + SSOT stale 정정.

## Context

**왜 이 작업인가** — controller 세션이 체감상 느린데 품질 이득이 없었다. 레포 `.claude/` + 전역
`~/.claude` 전수 점검(2026-07-29) 결과, 주범은 레포가 아니라 **전역 설정 2개**:

1. `~/.claude/settings.json`의 `effortLevel: "xhigh"` — 모든 턴에 최고 추론 강제.
   자체 SSOT(`skills/context-and-effort/SKILL.md`, ✅ 2026-07-17)의 "모든 surface 기본 = high,
   xhigh는 capability-critical만 명시 지정"과 정면 모순. 루틴 작업(docs/커밋) 위주인 controller에서
   비용·지연만 지불.
2. `model: "claude-fable-5[1m]"` — 1M 컨텍스트 변형: 롱컨텍스트 처리 저속 + 200k 초과분 프리미엄
   과금 + 자동 컴팩션 실종으로 세션이 길수록 턴이 느려짐. `token-budget.md`의 "80% 재시작" 룰이
   800k 기준이 되어 무력화(룰은 200k 전제).

부차: opus 에이전트 4개 전부 `effort: max`(SSOT 기준 max = frontier only) · 모든 Bash 호출마다
`guard_destructive.py`의 python3 기동 · 전역 플러그인 swift-lsp(Swift 전무)/rust-analyzer-lsp
(controller 무관).

**무엇을 확정했는가** (사용자 결정, 2026-07-29):

- 전역 model → ~~`claude-opus-4-8`~~ **`claude-opus-5`** (실행 중 사용자 정정: Opus 5 출시 확인 —
  WebFetch 재검증: $5/$25·1M ctx·agentic 코딩 기본 추천, 4.8은 legacy 강등) · `effortLevel` 제거(→ 기본 high)
- architect-agent·tech-lead·debugging-expert `max` → `xhigh`, **rust-expert만 max 유지**
  (CRDT 수렴 정확성 — SKILL.md 티어링 판단 기록 근거)
- SKILL.md의 Outlier note "Claude Code는 frontmatter `effort:`를 읽지 않는다"는 **stale** —
  현 harness(Fable 5 세대, 2026-07-29 세션 실측: Agent 도구 스펙이 "model, reasoning effort, and
  tools come from its definition (frontmatter)" 명시)는 읽는다 → 정정 필요
- 플러그인: swift-lsp 제거, rust-analyzer-lsp 전역 해제 후 crdt-engine project 스코프로 이동
- 문제 없음 확인: 상시 룰 4개 224줄 + CLAUDE.md 76줄(lean), 에이전트 15/20 sonnet(티어링 양호),
  스코프 룰 24개 `paths:` 정상

## 실행 체크리스트

- [x] **C1** `docs(plan):` 본 plan 커밋 (작업 시작 전 — plan-logging.md) — `37e29bc`
- [x] **C2** 전역 `~/.claude/settings.json`: `effortLevel` 제거 + `model: "claude-opus-5"` (커밋 대상 아님 — 레포 밖)
- [x] **C3** `claude(agents):` architect-agent·tech-lead·debugging-expert `effort: max` → `xhigh` — `38e9e15`
- [x] **C4** `claude(skills):` context-and-effort SKILL.md — Opus 5 반영 + stale Outlier note 폐기 + 매핑 표·검증일 갱신 — `bd69253`
- [x] **C5** `claude(hooks):` PreToolUse Bash 훅에 shell `case` 프리필터(대조군 8케이스 통과) — `0f69f67`
- [x] **C6** 전역 플러그인: 둘 다 전역 해제, rust-analyzer-lsp → crdt-engine `.claude/settings.local.json` (레포 밖 — 로컬 파일이라 서비스 레포 승인 불요)
- [x] **C7** `docs(plan):` status: done + dev-log = [2026-07-29-context-speed-tuning](../dev-logs/2026-07-29-context-speed-tuning.md)

## 검증

```bash
# 컨텍스트 예산 게이트 (C3·C4 후 PostToolUse 훅이 자동 실행, 수동 재확인)
python3 scripts/claude_context_budget.py --tier all

# C5 프리필터 대조군: 안전 명령은 python 미기동(즉시 exit 0), 위험 명령은 여전히 차단
echo '{"tool_input":{"command":"git status"}}' | <프리필터 명령>          # → 통과, python 미기동
echo '{"tool_input":{"command":"kubectl delete pod x"}}' | <프리필터 명령> # → exit 2 차단 유지
```

- 새 세션에서 `/model` · `/status`로 opus-4-8 + effort 기본 반영 확인
- `git diff` 전체 리뷰 후 영역별 분할 커밋

## 재개 지점 (Resume)

```
마지막 완료 = 전 단계 (C1~C7) — 2026-07-29 완결
다음        = 없음. 새 세션에서 /model·/status로 opus-5 + effort 기본 반영만 확인
주의        = guard RULES에 명령어 추가 시 settings.json 프리필터 패턴도 동기화
              (스크립트 docstring에 경고 있음)
```

## 범위 밖

- 상시 룰/워크플로우 룰(plan-logging·user-approval 등) 축소 — 사고 이력 기반 의도된 프로세스
- 에이전트 sonnet 추가 하향 — 이미 15/20 sonnet
- 서비스 레포 설정 변경 — crdt-engine의 plugin 스코프 1파일만 예외
