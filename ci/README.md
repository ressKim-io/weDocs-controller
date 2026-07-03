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

## 다운스트림 트리거 (M5)
main에 proto가 머지되면 → 다운스트림 레포(`backend` / `ai-service` / `crdt-engine`)에
`repository_dispatch`(또는 submodule bump PR)로 재생성·빌드를 트리거.

> 폴리레포 비용(proto 동기화, CI 5벌)을 컨트롤러의 멀티레포 오케스트레이션 + buf 게이트로
> 관리하는 것 자체가 DevOps showcase (SDD §12).

## 가드레일
proto 변경은 **반드시 여기서 시작**한다. 다운스트림에서 직접 수정한 proto는 SSOT 위반.
