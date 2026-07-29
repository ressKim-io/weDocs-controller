---
date: 2026-07-29
slug: context-speed-tuning
status: planned
related:
  - plans/2026-07-28-claude-context-budget.md
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

- 전역 model → `claude-opus-4-8` · `effortLevel` 제거(→ 기본 high)
- architect-agent·tech-lead·debugging-expert `max` → `xhigh`, **rust-expert만 max 유지**
  (CRDT 수렴 정확성 — SKILL.md 티어링 판단 기록 근거)
- SKILL.md의 Outlier note "Claude Code는 frontmatter `effort:`를 읽지 않는다"는 **stale** —
  현 harness(Fable 5 세대, 2026-07-29 세션 실측: Agent 도구 스펙이 "model, reasoning effort, and
  tools come from its definition (frontmatter)" 명시)는 읽는다 → 정정 필요
- 플러그인: swift-lsp 제거, rust-analyzer-lsp 전역 해제 후 crdt-engine project 스코프로 이동
- 문제 없음 확인: 상시 룰 4개 224줄 + CLAUDE.md 76줄(lean), 에이전트 15/20 sonnet(티어링 양호),
  스코프 룰 24개 `paths:` 정상

## 실행 체크리스트

- [ ] **C1** `docs(plan):` 본 plan 커밋 (작업 시작 전 — plan-logging.md)
- [ ] **C2** 전역 `~/.claude/settings.json`: `effortLevel` 제거 + `model: "claude-opus-4-8"` (커밋 대상 아님 — 레포 밖)
- [ ] **C3** `claude(agents):` architect-agent·tech-lead·debugging-expert `effort: max` → `xhigh`
- [ ] **C4** `claude(skills):` context-and-effort SKILL.md — stale Outlier note 정정 + agents 매핑 표 effort 갱신 + 검증일 갱신
- [ ] **C5** `claude(hooks):` PreToolUse Bash 훅에 shell `case` 프리필터 — 위험 접두사만 python3 위임
- [ ] **C6** 전역 플러그인: swift-lsp 제거, rust-analyzer-lsp 전역 해제 → crdt-engine `.claude/settings.json`으로 (레포 밖 + crdt-engine 레포 1파일)
- [ ] **C7** `docs(plan):` status: done + dev-log 링크

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
마지막 완료 = plan 작성
다음        = C1 (plan 커밋)
주의        = C2·C6은 레포 밖(전역 설정) — 커밋 없음, 체크박스로만 추적.
              C5는 guard_destructive.py의 차단 목록과 프리필터 접두사가 어긋나면
              가드가 뚫린다 — 대조군 시뮬레이션 필수.
```

## 범위 밖

- 상시 룰/워크플로우 룰(plan-logging·user-approval 등) 축소 — 사고 이력 기반 의도된 프로세스
- 에이전트 sonnet 추가 하향 — 이미 15/20 sonnet
- 서비스 레포 설정 변경 — crdt-engine의 plugin 스코프 1파일만 예외
