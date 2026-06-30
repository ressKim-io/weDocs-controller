# ADR-0015 — outbox = 앱레벨 transactional outbox

- 상태: **Accepted**
- 날짜: 2026-06-30
- 관련: SDD §3.3·§15 · [plan-audit T3-3](../plans/2026-06-30-plan-audit-improvements.md) (M2F-06) · [ADR-0008 pgvector] · 가드레일 4
- 범위: M2 = outbox 테이블 + 트랜잭션 쓰기. relay(폴링 발행)·Kafka 소비·인덱싱 = M4(범위 밖).

## 맥락

SDD §3.3: 문서 변경 → Kafka(`doc.updated`) → 인덱싱 consumer(AI). DB 커밋과 이벤트 발행의 **원자성**이 필요하다(둘 중 하나만 성공하면 인덱스 불일치). 패턴은 outbox로 확정됐으나 **구현 방식**이 미정 — Debezium(CDC, WAL 기반) vs 앱레벨 transactional outbox.

제약: 배포 = **홈랩 KinD + 로컬 GPU**(ADR-0009). 리소스가 빠듯하다. 가드레일 4(OTel 전파 — 이벤트에 traceparent).

## 결정

**앱레벨 transactional outbox.**

1. 페이지 변경 트랜잭션에 **`outbox` 테이블 insert를 동봉**(같은 DB 트랜잭션 = 커밋 원자성). 비즈니스 변경과 이벤트가 함께 커밋되거나 함께 롤백.
2. **traceparent를 payload에 주입**(가드레일 4 — OTel context를 Kafka 경유 전파, otel-expert 권장).
3. **M2 범위 = 테이블 + 트랜잭션 쓰기만.** relay(outbox 폴링 → Kafka 발행) + 소비(인덱싱) = **M4**. M2엔 이벤트가 테이블에 쌓이고, 발행 인프라(Kafka)는 M4에 구성.

`outbox(id, aggregate_id, event_type, payload, traceparent, created_at, published_at)` — `published_at` NULL = 미발행. relay가 `published_at IS NULL`을 순서(`id`)대로 발행 후 마킹(M4).

## 대안 비교

| 방안 | 원자성 | 홈랩 KinD 리소스 | 앱 코드 | 운영 복잡도 | 판정 |
|---|---|---|---|---|---|
| **앱레벨 transactional outbox** (채택) | ✅ 같은 트랜잭션 | 가벼움(테이블 1 + 폴링) | 약간(insert+relay) | 낮음 | ✅ |
| Debezium CDC (WAL) | ✅ WAL 기반 | ❌ Kafka Connect + Debezium + Kafka 상시 | 0(앱 무변경) | 높음 | ❌ KinD 리소스 과중 |
| 듀얼 라이트(DB + Kafka 직접) | ❌ 부분 실패 가능 | 가벼움 | 중간 | 낮음 | ❌ 원자성 깨짐 |

→ 앱레벨: Debezium의 "앱 코드 0" 이점은 크나 홈랩 리소스(상시 Kafka Connect 클러스터)가 MLP에 과중. 테이블 1개 + 폴링 relay가 리소스 대비 합리적.

## 결과

- M2 스키마에 `outbox` 테이블 포함(SDD §5 갱신). 페이지 변경 서비스 메서드가 동일 트랜잭션에서 outbox insert.
- relay·Kafka·인덱싱은 M4에 미룸 → M2는 인프라(Kafka) 없이 테이블·트랜잭션 정합성만 검증(Testcontainers PG).
- SDD §15 "outbox(Debezium vs 앱레벨) → M2" 항목 해소.

## 트레이드오프 (인정)

- **relay 폴링 지연 + at-least-once** → 소비자(M4 인덱서)는 **멱등** 필요(중복 발행 가능). 순서는 `outbox.id` 오름차순으로 보장.
- **M2엔 relay 부재** → 이벤트가 발행되지 않고 쌓이기만 함(M4까지). M2 검증은 "트랜잭션 원자성"까지(발행은 M4 DoD).
- **앱 코드 부담** → Debezium 대비 insert·relay 코드를 직접 작성·운영. 단순성·리소스로 상쇄.
- **outbox 테이블 증가** → 발행 후 정리(파티셔닝/주기 삭제) 필요(M4 relay와 함께).
