# 세션 저속 진단 — 주범은 레포가 아니라 전역 설정이었다

**날짜**: 2026-07-29 · **plan**: [2026-07-29-context-speed-tuning](../plans/2026-07-29-context-speed-tuning.md)

## 증상

controller 세션이 체감상 느린데 품질 이득이 없다("퀄리티가 엄청 좋은 것도 아닌데 속도가 안 나온다").
레포 룰/에이전트 문제로 추정하고 착수했으나, 전수 점검 결과 **레포는 대체로 결백**했다.

## 원인 (Before)

| # | 위치 | 문제 | 왜 느린가 |
|---|---|---|---|
| 1 | `~/.claude/settings.json` | `effortLevel: "xhigh"` 전역 고정 | 모든 턴에 최고 추론 강제. 자체 SSOT(`context-and-effort`: "기본 = high, xhigh는 명시 지정만")와 정면 모순 — docs/커밋 위주 루틴 작업에서 지연만 지불 |
| 2 | 〃 | `model: "claude-fable-5[1m]"` | Fable = 공식 latency "Slower" + usage credit. `[1m]`은 자동 컴팩션을 사실상 제거해 **세션이 길수록 턴이 느려짐** + `token-budget.md` "80% 재시작" 룰이 800k 기준으로 무력화 |
| 3 | `.claude/agents/` | opus 4개 전부 `effort: max` | SSOT 기준 max = "frontier only, overthinking 위험". 게다가 SSOT의 "harness가 frontmatter effort를 안 읽는다"는 노트가 stale — **현 harness는 읽으므로 정말 max로 돌고 있었다** |
| 4 | `.claude/settings.json` 훅 | 모든 Bash 호출마다 `python3` 기동 | 가드 자체는 정당(플래그 순서 우회 차단)하나, `ls` 한 번에도 인터프리터 기동 비용 지불 |
| 5 | 전역 플러그인 | swift-lsp(Swift 전무)·rust-analyzer-lsp(controller 무관) user 스코프 | 무관 레포에서 로드 |

레포 쪽 무혐의 확인: 상시 룰 4개 224줄 + CLAUDE.md 76줄(2026-07-28 예산 게이트로 관리 중),
에이전트 20개 중 15 sonnet + 1 haiku로 모델 티어링 양호, 스코프 룰 24개 `paths:` 정상.

## 해결 (After)

| # | 조치 | 커밋 |
|---|---|---|
| 1 | `effortLevel` 제거 → 기본 `high` | (레포 밖) |
| 2 | `model` → **`claude-opus-5`** (작업 중 사용자 확인: Opus 5 출시 → 4.8 아닌 5로. WebFetch 재검증: $5/$25·1M ctx·"complex agentic coding" 기본 추천, 4.8은 legacy) | (레포 밖) |
| 3 | architect-agent·tech-lead·debugging-expert `max`→`xhigh`, rust-expert만 max 유지(CRDT 수렴 정확성) + SSOT stale 노트 폐기·재검증 | `38e9e15` · `bd69253` |
| 4 | 훅에 shell `case` 프리필터 — RULES 3종은 `kubectl`/`argocd`/`git…push` 리터럴 없이 발화 불가하므로 미포함 명령은 python 미기동 | `0f69f67` |
| 5 | 전역 플러그인 해제, rust-analyzer는 crdt-engine `.claude/settings.local.json`으로 (서비스 레포 커밋 승인이 필요 없는 로컬 파일) | (레포 밖) |

## 검증

- 프리필터 대조군 8케이스: 안전 명령(`git status`·`ls`) python 미기동 / `kubectl delete`·
  `argocd sync --force`·`git push --force`·전역 플래그 선행 `kubectl --namespace x delete` 전부 차단 유지 /
  정상 `git push` 통과 / heredoc 인용문 오탐 방지 유지
- `claude_context_budget.py --tier all` ✓ 예산 내 (상시 5파일 · ~9,253토큰)
- 모델·effort 사실은 공식 docs WebFetch 재검증(models overview + effort, 2026-07-29)

## 교훈

1. **전역 설정은 SSOT 문서의 감사 범위 밖에서 조용히 상시 비용을 만든다.** 레포에 검증된 티어링
   기준이 있어도 `~/.claude`가 그걸 무시하면 매 턴이 그 모순을 지불한다. 기준 문서를 갱신할 때
   **실제 설정값도 대조**할 것.
2. **harness 동작에 대한 주장은 세대가 바뀌면 재검증 대상이다.** "frontmatter effort를 안 읽는다"
   (2026-07-17 실측)는 이번 세대에선 반대가 됐고, 그 사이 opus 에이전트 4개가 의도보다 비싸게 돌았다.
3. **매 호출 훅에는 인터프리터 기동 비용이 곱해진다.** 가드의 발화 조건이 리터럴 부분문자열을
   필요로 하면 shell 프리필터로 안전하게 생략 가능 — 단 RULES↔프리필터 동기화가 새 커플링이므로
   스크립트 docstring에 경고를 남겼다.

## 남은 것 (후속 후보 — 미착수)

- **스코프 룰의 광역 `paths:` 관찰**: `**/*.py`가 유틸 스크립트(`scripts/guard_destructive.py`)에도
  크래프트 표준 6종(~1,000줄+)을 로드하고, `**/debug*`가 `.claude/agents/debugging-expert.md`에
  매칭돼 `debugging.md`(195줄)를 끌어온다. 서비스 코드용 표준이 controller 유틸 편집에도 발화하는
  것 — 오탐이라기보다 과포함. 체감 시 `paths:` 정밀화 후보.
