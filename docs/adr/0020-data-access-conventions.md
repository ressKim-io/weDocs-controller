# ADR-0020 — 데이터 접근 컨벤션 (ID-only 연관 · DB FK 정책 · QueryDSL 채택 기준)

- 상태: **Accepted**
- 날짜: 2026-07-17
- 관련: [ADR-0012](0012-crdt-boundary-content-vs-tree.md)(트리=관계형) · [layering-readability.md](../../.claude/rules/layering-readability.md) · [plan 2026-07-17](../plans/2026-07-17-error-catalog-package-by-feature.md)
- 범위: JPA 엔티티 연관 스타일 · DB FK 제약 정책 · 쿼리 기술 채택 기준. 리뷰마다 재론되지 않도록 3건을 선답하는 **슬림 ADR**.

## 맥락

사용자 요구(2026-07-17): "JPA는 단순하게, FK 과결합 금지, 샤딩 확장 가능해야". 실측(doc-service 1c 시점): 엔티티는 이미 `@ManyToOne`/`@OneToMany` 0건 — 전 연관이 UUID FK 컬럼(관행이지만 명문 규칙 없음). 반면 DB 스키마(Flyway V1)는 실제 FK 제약 + `ON DELETE CASCADE` 보유. 쿼리는 전부 Spring Data 파생 쿼리(QueryDSL/jOOQ/JPQL 0건), 조상 탐색은 Java 루프(`findById` N회).

## 결정

1. **엔티티 연관 = UUID FK 컬럼만. `@ManyToOne`/`@OneToMany`/`@OneToOne`/`@ManyToMany` 금지** (현행 관행의 명문화). 객체 그래프 탐색 대신 명시적 `repository.findById()`. 근거: ① lazy 로딩·N+1·프록시 함정 제거(JPA "단순하게") ② 애그리거트 경계가 코드에 드러남 ③ 샤드 간 조인이 불가능한 토폴로지에서 객체 참조는 어차피 성립 안 함 — ORM 계층을 미리 샤드 중립으로.
2. **DB FK 제약 + `ON DELETE CASCADE`는 유지** (Flyway 무변경). 단일 DB인 M2~M3에서 FK는 정합성 안전망이고 제거는 무근거 최적화. **제거 트리거 = 샤딩 실행 결정**(그 시점에 별도 ADR로 cascade의 앱 레벨 이관 설계) — 지금 하는 것은 "제거"가 아니라 "제거 시점의 정의".
3. **QueryDSL/jOOQ 지금 채택 안 함.** 채택 트리거 = **파생 쿼리·단순 `@Query`로 표현 불가한 요구가 2건+ 누적** 시(예: 자손 서브트리 재귀 CTE, 동적 필터 검색). 현재 최장 파생 쿼리(`findByWorkspaceIdAndArchivedFalseOrderBy…`)는 가독성 경계지만 동작 문제 없음. 조상 탐색 Java 루프(cap 64)는 depth-bounded라 성능 이슈 실측 전까지 유지.

## 대안 비교

| 논점 | 채택 | 기각 대안 | 기각 사유 |
|---|---|---|---|
| 연관 | UUID FK 컬럼 | `@ManyToOne` 객체 참조 | lazy/N+1/프록시 복잡도, 애그리거트 경계 흐림, 샤드 비친화 |
| DB FK | 유지 + 트리거 정의 | 지금 제거(샤딩 선제) | 단일 DB에서 정합성 안전망 포기 — 얻는 것 없음(YAGNI 역방향). cascade 의존 동작(멤버·권한 정리)의 앱 이관은 샤딩 ADR 몫 |
| 쿼리 | 파생 쿼리 + 트리거 정의 | QueryDSL 즉시 도입 | 복잡 쿼리 0건인데 의존·Q클래스 생성 비용 선지불. "필요하면 쓴다"의 '필요'를 측정 가능하게 정의하는 게 이 ADR |

## 결과

- 리뷰 게이트: `@ManyToOne` 류 등장 시 이 ADR 인용 반려(layering P3·P7과 함께). Pageable 미적용 무상한 쿼리는 secure-coding P2 소관(retrofit plan P2 항목).
- 조상 탐색이 성능 병목으로 실측되면(M3 부하) 재귀 CTE(`@Query` native) 우선 검토 — 그 시점에 QueryDSL 트리거 카운트에 산입.

## 트레이드오프 (인정)

- **ID-only 연관** → JPA의 편의(cascade persist, orphanRemoval, 객체 그래프)를 포기하고 서비스 코드가 조율 책임을 짐. 이 프로젝트에선 이미 그렇게 짜여 있고(1a~1c), 명시성이 AI 관리에도 유리.
- **FK 유지** → 샤딩 시점에 마이그레이션 비용 발생(제약 drop + 앱 레벨 정리 로직). 의도된 이연 — 그 비용은 샤딩이 실제일 때만 지불.
- **파생 쿼리 고수** → 메서드명이 길어지는 가독성 비용. 2건+ 트리거로 상한 관리.
