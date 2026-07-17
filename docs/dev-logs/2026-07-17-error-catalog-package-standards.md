---
date: 2026-07-17
category: meta
tier: 2
importance: major
status: resolved
tags: [craft-standards, error-catalog, package-by-feature, error-handling, layering-readability, adr, model-tiering, effort-guide, gate-simulation]
related:
  - plans/2026-07-17-error-catalog-package-by-feature.md
  - adr/0018-error-catalog.md
  - adr/0019-package-by-feature-java.md
  - adr/0020-data-access-conventions.md
  - dev-logs/2026-07-03-craft-standards-v2-security-quality.md
---

# 표준 확장 Step ① — 에러 카탈로그·package-by-feature 룰 + ADR 3건 + 모델 가이드 현행화

## 무엇

"코드 구조/규칙을 초기에 안 잡아서 읽기 힘들다 — 표준을 찾아 적용하고 리팩토링하자"(사용자, 2026-07-17)에 대한 표준 정립 단계. **탐색 실측이 통념을 뒤집은 것이 출발점**: 메서드 길이(최장 24줄)·정적 팩토리·ID-only 연관은 이미 양호했고, 진짜 문제는 ① `service/` god-package(22파일, leaf 예외 12개 혼재) ② HTTP/gRPC 에러 매핑 이원화+드리프트(REST=uuid 보간 노출 vs gRPC=별도 하드코딩 문구) ③ 카탈로그·패키지 조직 룰의 표준 공백이었다.

산출(controller 커밋 5개): `error-handling.md` **P7**(서비스별 ErrorCode enum SSOT + 카테고리 예외 4~5종) · `layering-readability.md` **P7**(package-by-feature, feature 평면) · `spring.md` ProblemDetail 정합(구 `ErrorResponse(code,message,timestamp)` 조항이 error-handling.md와 **모순**이었음 — 교체) · `git.md` move-only PR 산정 단서 · **ADR-0018/0019/0020** · `effort-guide.md`/`token-budget.md` 현행화 + CLAUDE.md stale 해소.

## 교훈 1 — 게이트 시뮬레이션이 또 문구 결함을 잡았다 (2026-07-03 방법론 재현)

신규 행 5개를 backend HEAD `290bf69`에 소급 실행(java-expert): 기대 발화 전부 fire·**오탐 0**. 그러나 문구 결함 4건이 나와 커밋 전 교정:

1. **fail-fast 제외 조건을 "시점"이 아니라 "성격"으로** — `CurrentUserIdArgumentResolver`는 요청 처리 중에 raw `IllegalStateException`을 던지지만 본질은 배선 불변식(fail-fast). "스타트업/구성"을 시점으로 읽으면 오탐. → "요청 데이터가 아닌 앱 배선·설정 자체의 불변식 위반(발생 시점 무관)"으로 재정의.
2. **매핑 누락 안전망 허용 예외 명시** — REST `handleUnmappedDomain`·gRPC `failInternal`은 하드코딩처럼 보이지만 "정상 매핑 경로"가 아님 → 행에 병기 안 하면 판정자마다 갈림.
3. **어댑터 예외에 구체 예시** — "크로스-feature 전송 어댑터"만으론 `grpc/` 해당 여부가 재량 → "예: 단일 gRPC 서비스 구현, 메시지 컨슈머".
4. **LR-2 backstop** — 소유 feature API가 그 오퍼레이션을 노출 안 하는 경우(`PageTreeService`의 workspace 비관 락)의 기준 부재 → "직접 주입 허용 + 사유 주석 필수".

기각한 제안 1건: "카테고리 예외 **또는** enum" OR 완화 — 기존 12-클래스 계층이 발화하는 게 부담스러워 보이지만, 그 소급 발화가 정확히 ③-1 retrofit의 근거다. 칼리브레이션 규칙([B]=diff 신규 코드, 기존 위반=[A]+retrofit)이 이 긴장을 이미 해소하므로 표준을 약화할 이유 없음.

## 교훈 2 — 표준끼리도 모순 난다 (spring.md ↔ error-handling.md)

`spring.md`는 `ErrorResponse(code, message, timestamp)` 표준화를 MUST로 강제하고 있었고, `error-handling.md` P3는 ProblemDetail을 강제 — **둘 다 항상-스코프 룰인데 서로 모순**인 채 6주 공존(실코드는 ProblemDetail 선택). 크래프트 표준 신설 시 인접 룰 grep(이번엔 `ErrorResponse`)으로 모순 스캔이 필요하다 — 표준 도입 체크리스트에 추가할 가치.

## 교훈 3 — 모델 문서 현행화에서 "수치 삭제"가 갱신의 절반

effort-guide/token-budget의 Opus 4.7 기준 수치 중 공식 문서에서 사라졌거나 달라진 것: 레벨별 비용 %(~25/~50/~200%) 삭제됨 · "Claude Code 기본 xhigh" → **전 surface 기본 high** · "Haiku 4.5 effort 지원" → **미지원** · "최소 캐시 4096 일괄" → **모델별 512/1024/2048/4096**. deep-thinking 룰대로 검증 불가 수치는 추정 기입 대신 삭제. 티어링 판단(리뷰=sonnet 유지: 게이트가 기계적 체크리스트라 충분, frontier는 opus+max 에스컬레이션)은 effort-guide에 기록.

## 다음

② 1c 게이트 findings 소PR(backend) → ③ 리팩토링 PR ×3(에러 카탈로그 → 중복 제거 → package-by-feature 이동) → ④ secure-coding retrofit → ⑤ Phase 2. 상세·findings 소속 할당표 = plan `2026-07-17-error-catalog-package-by-feature.md`.
