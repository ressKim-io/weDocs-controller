---
date: 2026-07-18
category: troubleshoot
tier: 2
importance: major
status: resolved
tags: [dependabot, dependency-graph, dependency-submission, sbom, false-positive, security-scan-ci, commons-lang3, gate-activation]
related:
  - dev-logs/2026-07-17-gitleaks-fingerprint-squash-trap.md
  - plans/2026-07-17-error-catalog-package-by-feature.md
---

# Dependabot 제출형 스냅샷 알림이 버전 상향 후에도 자동 해제 안 됨 (commons-lang3 스테일)

## 무엇

backend PR #10 push 시 dependabot 알림 #1(`org.apache.commons:commons-lang3` medium, Uncontrolled Recursion, 취약 `< 3.18.0`)이 노출. 조사 결과 **실제 유출/취약 없음** — 현 빌드는 전 구성에서 commons-lang3를 **3.20.0**(≥ 패치 3.18.0)으로 해석하고, 심지어 test 스코프 한정(ws-gateway 미포함). PR #10과 무관한 기존 항목.

## 근본 원인 — 제출형 그래프 알림은 자동 해제되지 않는다

| 단서 | 값 |
|---|---|
| 알림 `created` = `updated` | 둘 다 `2026-07-03T12:35:44Z` — 그래프 활성화 첫날 이후 한 번도 재평가 안 됨 |
| main dependency-submission 실행 | 매 push **성공**(마지막 2026-07-17 PR #9 머지) |
| SBOM 실기록 | commons-lang3 **3.16.0 + 3.20.0 공존** |
| 실 해석(`./gradlew :m:dependencies`) | 전 구성 **3.20.0**(`3.18.0 → 3.20.0` 업그레이드 표시뿐, 3.16 선택 노드 0) |

- 2026-07-03 최초 제출 시점엔 Spring Boot가 commons-lang3 3.16.0을 관리 → 알림이 **당시엔 정확히** 생성됨.
- 이후 Spring Boot 4.1.0 → commons-lang3 3.20.0으로 상향. 실 해석은 패치됨.
- 그러나 **Dependabot 자동 해제는 manifest 파일 기반 탐지에만 동작** — Dependency Submission API(스냅샷) 알림은 실 버전이 올라가도 해제되지 않는다(GitHub 한계). 오래된 스냅샷이 SBOM에 잔존 → 알림 상시 open.
- `updated_at`이 2주간 불변인 것이 결정적 단서: 매 제출이 3.20.0을 보고해도 알림은 재평가조차 안 됨.

## 조치

1. `./gradlew :m:dependencies`로 취약 버전이 "최종 해석 노드"가 아님을 확정(‘requested→resolved’ 업그레이드 표시와 구분).
2. `gh api .../dependency-graph/sbom`으로 SBOM 실기록 확인 — 3.16.0이 스테일 잔존임을 입증.
3. 알림 #1을 **`inaccurate`로 dismiss** + 근거 코멘트(실 해석 3.20.0·스냅샷 잔존·GitHub 한계).
4. 재발 방지: `secure-coding.md` §게이트 배선에 "제출형 그래프 알림은 SBOM 실버전으로 트리아지" 항목 추가.

## 교훈 — gitleaks 사이드트랙과 동형

[gitleaks fingerprint-squash 함정](2026-07-17-gitleaks-fingerprint-squash-trap.md)과 정확히 같은 부류: **아무도 안 보는 스캔 신호가 실상태와 어긋난 채 상시 red**. gitleaks는 "push green이 전체 히스토리 red 은폐", 여기는 "제출형 알림이 버전 상향 후 자동 해제 안 됨". 공통 교훈 = **게이트 배선의 완료 조건은 '워크플로 존재'가 아니라 '신호가 실상태와 일치'**. 스캐너 신호는 실 해석(SBOM/실행 로그)으로 대조 검증해야 신뢰할 수 있다.

⚠️ 미결 관찰: 이 알림 클래스는 앞으로도 버전 상향 시 수동 dismiss가 필요할 수 있다. Renovate/Dependabot 자동 PR 도입 또는 주기적 `gh api dependabot/alerts` 대조를 M5 SAST 확장 트랙에서 검토.
