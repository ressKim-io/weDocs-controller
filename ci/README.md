# ci — proto 게이트 + 다운스트림 트리거

컨트롤러 CI의 책임: **proto 계약을 지키는 문지기**.

## 게이트 (`.github/workflows/proto-ci.yml`)
1. `buf lint proto` — 스타일 강제.
2. `buf format --diff` — 포맷 검사.
3. `buf breaking proto --against <main>` — wire 호환성 파괴 차단.

`proto/**` 변경 PR은 이 셋을 통과해야 머지 가능.

## 보안 스캔 (`.github/workflows/security-scan.yml`, 2026-07-03~)

폴리레포 공통 스캔 레인 표준 — [secure-coding](../.claude/rules/secure-coding.md) 게이트의 도구 축([도입 plan](../docs/plans/2026-07-03-security-quality-standards.md) 트랙 2):

| 레포 | 시크릿 | 의존성(SCA) |
|---|---|---|
| controller | gitleaks-action v3 | — (앱 의존성 없음) |
| crdt-engine | gitleaks-action v3 | rustsec/audit-check v2 (cargo-audit, RustSec DB) |
| backend | gitleaks-action v3 | gradle dependency-submission v6 + dependency-review v5 (PR 게이트 + Dependabot alerts, lockfile 불요) |
| frontend | gitleaks-action v3 | npm audit |

- 트리거: PR + push(main) + **주간 schedule**(코드 무변경 의존성 드리프트 검출). gitleaks는 `fetch-depth: 0`(전 히스토리).
- 실패 = 머지 차단(`[B]`성). 오탐은 각 레포 `.gitleaks.toml` allowlist에 **근거 주석과 함께**.
- 개인(User) 계정이라 GITLEAKS_LICENSE 불요(2026-07-03 확인). 빌드/테스트 CI 전체(T4)·SAST 확장(semgrep/CodeQL)은 M5 — SDD §15.

## 컨텍스트 예산 (`.github/workflows/claude-context-budget.yml`, 2026-07-28~)

Claude Code가 **매 세션 상시 로드**하는 지시문의 크기 게이트 — [plan](../docs/plans/2026-07-28-claude-context-budget.md).
측정 대상 = `CLAUDE.md` + `.claude/rules/` 중 `paths:` 없는 것 + 실제 `@import`(재귀).
`scripts/claude_context_budget.py`가 SSOT이고, 로컬에서도 같은 명령으로 재현된다.

| 계층 | 대상 | 성격 |
|---|---|---|
| Tier A | 상시 로드 총량·CLAUDE.md 줄수·개별 룰 줄수·`@import` 수 | 빡빡하게 — 통제 대상 |
| Tier B | 스코프 룰·SKILL.md·레퍼런스 스킬·에이전트 본문/설명 길이 | 오늘의 최댓값보다 살짝 위 — 진짜 회귀에만 발화 |

- **이 게이트가 할 수 있는 것과 없는 것**: 이 레포는 [CLAUDE.md §커밋·push 규칙](../CLAUDE.md)상 main 직접 push라
  **`pull_request` 레그는 controller 변경에 실제로 걸리지 않는다.** `push: main` 레그는 **사후 탐지**(main에 빨간 X).
  **실시간 차단은 `.claude/settings.json`의 `PostToolUse` 훅** — `.claude/**` 편집 즉시 같은 스크립트가 세션 안에서 돈다. 둘은 역할이 다르다.
- `schedule:` 없음 — gitleaks와 달리 **커밋 없이 드리프트하는 경로가 없다**(파일이 바뀌어야 예산이 바뀐다).
- 임계값은 **실측 기준**으로만 내린다. 희망치로 잡으면 게이트가 상시 red가 되고,
  그건 배선 안 한 것보다 나쁘다([secure-coding §자동 스캔 게이트](../.claude/rules/secure-coding.md)). 하향(래칫)은 **항상 별도 커밋**.

## 다운스트림 트리거 (M5)
main에 proto가 머지되면 → 다운스트림 레포(`backend` / `ai-service` / `crdt-engine`)에
`repository_dispatch`(또는 submodule bump PR)로 재생성·빌드를 트리거.

> 폴리레포 비용(proto 동기화, CI 5벌)을 컨트롤러의 멀티레포 오케스트레이션 + buf 게이트로
> 관리하는 것 자체가 DevOps showcase (SDD §12).

## 가드레일
proto 변경은 **반드시 여기서 시작**한다. 다운스트림에서 직접 수정한 proto는 SSOT 위반.
