# ADR-0012 — CRDT 경계: 내용=CRDT, 트리=관계형

- 상태: **Accepted**
- 날짜: 2026-06-30
- 관련: [PRD §3·§4](../prd/4-data-and-permission-model.md) (D-2) · SDD §5 · [ADR-0011](0011-engine-sync-fanout-bridge.md) · [M2 plan](../plans/2026-06-30-m2-persistence-session.md) · 가드레일 2·5
- 범위: M2 데이터 모델 경계. 트리 CRDT(동시 이동 자동 머지)는 2차 확장(범위 밖).

## 맥락

M2는 평면 `documents`에서 **워크스페이스 + 페이지 트리**(자기참조 `parent_id`) 모델로 확장한다(D-1). 그러면 동시성이 **두 종류**가 된다:

1. **페이지 *내용*의 동시성** — 같은 페이지를 여러 명이 동시 타이핑/블록 이동. M1에서 CRDT(yrs)로 증명한 경로.
2. **페이지 *트리*의 동시성** — 두 명이 같은 페이지를 동시에 다른 위치로 이동(reparent). 트리 사이클·고아 위험.

이 둘을 같은 메커니즘으로 다룰지(전부 CRDT), 분리할지 결정해야 한다. 트리까지 CRDT로 하면 Kleppmann의 *highly-available move operation for replicated trees* 류 구현이 필요하다.

제약: 가드레일 2("AI는 CRDT 의존 불가" — CRDT 경계는 명확해야 함), 가드레일 5("엔진은 한 문서 *내용* 스트림만"), MLP(최소 기능선).

## 결정

**페이지 내용 = CRDT(엔진), 페이지 트리 = 관계형(doc-service 트랜잭션).**

- **내용 동시성** → CRDT. 소유 = CRDT Engine(Rust). 영속 = `page_snapshots`. 머지 순서 무관 수렴(M1 경로 그대로).
- **트리 동시성** → 관계형. 소유 = doc-service(Postgres). 페이지 이동은 단일 트랜잭션으로 `parent_id`/`position` 갱신:
  ```
  move(page P, new_parent N):
    1. N이 P 자신/자손이면 거부 (사이클 방지)
    2. 단일 트랜잭션으로 parent_id·position 갱신
    3. 동시 이동은 row lock으로 직렬화 (마지막 커밋 우선)
  ```
- 이 경계는 가드레일 5("엔진=내용 스트림")와 **정확히 일치**한다 — 엔진은 트리를 모른다.

## 대안 비교

| 방안 | 동시 이동 처리 | 구현 난이도 | 가드레일 5 정합 | 판정 |
|---|---|---|---|---|
| **내용 CRDT + 트리 관계형** (채택) | 마지막 이동 우선 + 사이클 검사 | 낮음(트랜잭션) | ✅ 엔진=내용만 | ✅ |
| 전부 CRDT (트리도 move-op CRDT) | 자동 머지(고가용) | 높음(replicated tree move) | ❌ 엔진이 트리 인지 | ❌ MLP 과설계, 2차 확장 |
| 전부 관계형 (내용도 lock/OT) | — | 중간 | ❌ M1 CRDT 증명 폐기 | ❌ 핵심 증명(분산 수렴) 포기 |

**왜 트리를 CRDT로 안 하나** (PRD §3.2): (a) 페이지 이동은 내용 편집보다 **수 자릿수 드물다**(타이핑=초당 수 회 update, 페이지 이동=세션당 0~수 회 — 이벤트 빈도 차 ≥100×), (b) 충돌 시 "마지막 이동 우선 + 사이클 방지"로 충분하며, (c) 트리 CRDT는 구현 난이도 대비 MLP 효용이 낮다.

## 결과

- M2 스키마가 두 저장소로 명확히 갈린다: `page_snapshots`(CRDT blob, bytea) vs `pages`/`page_permissions`(관계형 트리·권한). SDD §5 갱신의 근거.
- 엔진은 M2에서도 "한 문서 내용 스트림"만 — **`doc_id`(proto/엔진 레이어) = `page_id`(doc-service SQL) 1:1**. proto 필드명은 `doc_id`로 통일(crdt/doc 패키지 공통), doc-service가 `doc_id ↔ page_id`를 1:1 매핑. 트리 구조는 doc-service REST가 단독 소유.
- 권한(`page_permissions` 상속)도 관계형 측에서 해석 → CheckPermission(엔진 무관).

## 트레이드오프 (인정)

- **동시 이동은 자동 머지가 아니다** — row lock 직렬화 "마지막 커밋 우선". 드물게 한쪽 이동이 덮어써질 수 있음(고아는 사이클 검사로 방지). 트리 CRDT는 2차 확장으로 명시 연기.
- **내용/트리 일관성은 최종적(eventual)** — 페이지 삭제와 진행 중 내용 편집이 경합하면 짧은 불일치 윈도. doc-service가 삭제 시 엔진 스트림 종료로 수렴.
