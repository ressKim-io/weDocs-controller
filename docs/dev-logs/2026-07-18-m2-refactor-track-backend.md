---
date: 2026-07-18
category: migration
tier: 2
importance: major
status: resolved
tags: [refactoring, error-catalog, package-by-feature, idor, move-only, craft-gate, doc-service, m2]
related:
  - plans/2026-07-17-error-catalog-package-by-feature.md
  - dev-logs/2026-07-17-error-catalog-package-standards.md
  - adr/0018-error-catalog.md
  - adr/0019-package-by-feature-java.md
  - adr/0020-data-access-conventions.md
---

# M2 리팩토링 트랙 — doc-service 4 PR (findings → 에러 카탈로그 → 중복 제거 → package-by-feature)

## 무엇

"코드 구조를 초기에 안 잡아 읽기 힘들다"(사용자, 2026-07-17)에 대해 표준 정립(Step ①, 별도 dev-log) 후 doc-service를 4개 PR로 리팩토링. 전부 크래프트 6종 게이트 2-렌즈(java-expert+code-reviewer) 통과, 매 단계 colima+Testcontainers green.

| PR | 내용 | 결과 |
|---|---|---|
| [#10](https://github.com/ressKim-io/weDocs-backend/pull/10) `a40bae5` | 1c 게이트 findings — 아카이브 자손 도달성 숨김·move 락 순서·테스트 보강 | 113건 |
| [#11](https://github.com/ressKim-io/weDocs-backend/pull/11) `080cec7` | 에러 카탈로그 — DocErrorCode enum+카테고리 예외 5종, HTTP/gRPC 매핑 일원화, leaf 12 삭제 | 145건 |
| [#12](https://github.com/ressKim-io/weDocs-backend/pull/12) `9c870a5` | 중복 제거 — 공유 인가 통합(IDOR 보존)·canRead 위임·MAX_ANCESTOR_DEPTH를 Page 도메인 단일화 | 148건 |
| [#13](https://github.com/ressKim-io/weDocs-backend/pull/13) `3b51772` | package-by-feature 재편(move-only) — auth/workspace/page/snapshot/common | 148건 |

## 교훈 1 — 게이트 리뷰가 "실증"으로 자기 주장을 깼다 (#10)

레이스 테스트(`PageTreeMoveRaceTest`)를 "move 락 순서 회귀 실증"이라 커밋했으나, code-reviewer가 **수정 전 코드로 되돌려 실행**해 그 테스트가 여전히 green임을 실증. 2-루트 스왑 토폴로지는 사이클 검사의 id-동등성으로 항상 잡혀 stale 필드와 무관 → 판별력 0. HIGH-2 회귀 가드를 Mockito `InOrder`(인가→락→clear 순서 결정적 고정)로 옮기고, 레이스 테스트는 "실-DB 직렬화 가드"로 역할을 낮췄다. **"실증"이라는 단어는 실제로 회귀를 재현해봐야 붙일 수 있다.**

## 교훈 2 — "중복 제거"가 IDOR 회귀를 유발할 뻔 (#12)

`PageSharingService.requireSharableBy`를 `WorkspaceAccessGuard.requireOwner`로 단순 재사용하면, 비멤버가 `workspace-not-found`(404)를 받아 **미존재 페이지의 `page-not-found`(404)와 구분 가능**해진다 — 공격자가 pageId 존재를 추론하는 IDOR 회귀. 원래 코드는 미존재·비멤버를 **같은 page-not-found로 붕괴**시켜 이를 막고 있었다. 해소: `requireOwner`에 not-found 코드 파라미터 오버로드를 추가해 붕괴 보존 + 교차 feature repo 주입 제거(layering P7 [A] 개선) + 붕괴 증명 가드 테스트. **finding의 제안(그냥 재사용)을 그대로 따르면 보안이 깨지는 경우 — dedup도 행동/보안 불변을 먼저 따진다.**

## 교훈 3 — move-only PR은 "로직 diff 비어있음"으로 증명한다 (#13)

96파일 재배치를 `git mv`(rename 보존) + 경로 파생 package 재작성 + 타입별 import 재작성(perl) + 컴파일러 오라클로 교차 feature import 보강. 검증 = `git diff -M50% ... | grep -vE '^[+-](package |import |$)'`가 **비어있음**(RestTestSupport 가시성 1줄 제외) → 로직 0 변경 증명. base package `io.wedocs.doc` 불변이라 컴포넌트 스캔·JPA·Flyway 무영향(148 통합 테스트 green이 실증).
- ⚠️ 함정: same-package self-import 정리(재작성 부산물)로 소형 파일 유사도가 낮아져 rename 인식이 -M90%→-M50%로 내려감. git.md에 쓴 90% 임계는 "import 정리까지 하면" 안 맞을 수 있다 — 핵심은 임계가 아니라 "로직 diff 비어있음"이다.
- macOS bash 3.2는 `declare -A` 미지원 → portable 매핑(공백 구분 리스트)로 우회.

## 교훈 4 — 카탈로그는 계약이므로 테스트도 계약 (#11)

`DocErrorCode` enum이 HTTP·gRPC wire의 SSOT가 되면서, "내부 에러 판정"이 HTTP(`is5xxServerError`)와 gRPC(`==INTERNAL`)에서 **독립 재계산**되던 것을 `isInternal()`(category==INVARIANT) 단일 소스로 통합하고, 3채널 동치(isInternal ⟺ HTTP 5xx ⟺ gRPC INTERNAL)를 전 엔트리에 강제하는 테스트를 추가. 불변식 위반이 내부 상태(workspaceId)를 클라이언트로 흘리지 않음(P4)을 HTTP·gRPC 양쪽 회귀 가드로 고정. **enum 매핑표는 EnumMap 기대표로 전수 검증(키 커버리지 강제)해야 새 엔트리 누락이 잡힌다.**

## 다음

리팩토링 트랙(Step ①~③) 완결. 남은 것 = **④ secure-coding retrofit(Phase 2 분기 전) → ⑤ Phase 2 인증**(M2 본류). 로컬 backend 테스트 = colima 필요(메모리 `backend-testcontainers-colima`).
