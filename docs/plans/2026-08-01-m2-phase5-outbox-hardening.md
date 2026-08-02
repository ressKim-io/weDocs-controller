---
date: 2026-08-01
slug: m2-phase5-outbox-hardening
status: done
related:
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0015-outbox-app-level.md
  - plans/2026-07-29-m2-phase34-engine-persistence.md
---

# M2 Phase 5 — Outbox 하드닝 (실무 수준 전환)

> ADR-0015의 M2 범위(테이블 + 트랜잭션 동봉)는 Phase 1a에서 기본 구현됐다.
> 이 plan은 **M4(relay+Kafka)로 진입할 때 코드를 뒤엎지 않도록** 현 outbox 구현을
> 실무 수준으로 끌어올리는 하드닝 트랙이다.
>
> 성공 조건: 기존 OutboxIntegrationTest 유지 + 새 검증 추가, 기존 REST API 동작 무변경.

## Context

### 현재 상태 (2026-08-01)

Phase 1a~1c에서 이미 구현된 것:
- `outbox` 테이블 DDL (V1 마이그레이션)
- `OutboxEvent` JPA 엔티티 / `OutboxRepository` / `OutboxAppender`
- `PageTreeService`의 4개 이벤트 발행: `page.created` / `page.renamed` / `page.moved` / `page.archived`
- `OutboxIntegrationTest` (Testcontainers, 트랜잭션 원자성 검증)

### 실무와 동떨어진 점 (이 plan에서 해소)

| # | 문제 | 위험 | 해법 |
|---|---|---|---|
| **F1** | payload를 `String.formatted()` + 자체 `escapeJson()`으로 조립 | 개행·유니코드 제어문자·nested quote에서 malformed JSON 생성 → M4 소비자 dead-letter | Jackson `ObjectMapper` 직렬화 |
| **F2** | 이벤트 타입이 magic string (`"page.created"`) | 오타 감지 불가, relay 토픽 매핑 시 동기화 어려움 | `OutboxEventType` enum |
| **F3** | `aggregate_type` 컬럼 부재 | workspace·멤버·권한 이벤트 추가 시 aggregate 구분 불가, 토픽 라우팅 불가 | 스키마 추가(V2) |
| **F4** | `actor_id` 컬럼 부재 | 감사 로그·인덱서 변경 이력에 "누가" 빠짐 | 스키마 추가(V2) |
| **F5** | M2 기간 중 outbox 무한 증가 | 개발/테스트 DB에 불필요한 행 누적 | 발행완료 행 주기삭제(scheduled) |
| **F6** | relay 설계 미확정 | M4 착수 시 스키마·계약 재논의 반복 | ADR-0015 보강 (이 plan의 설계 절) |

### 범위 확정

**이 plan(M2 Phase 5)에서 하는 것:**
- F1~F4: 코드 + V2 마이그레이션 (PR 1건)
- F5: scheduled cleanup job (같은 PR에 동승)
- F6: 이 plan 안에 relay 설계 절을 기록 (ADR-0015 보강은 별도 커밋)

**하지 않는 것 (M4):**
- relay 구현 (폴링 → Kafka 발행)
- Kafka 인프라 (브로커·토픽·consumer)
- OTel traceparent 주입 (런타임 미설치)
- 소비자(인덱서) 구현

## 설계

### 1. 스키마 변경 — `V2__outbox_aggregate_type_actor.sql`

```sql
-- F3: aggregate_type — relay가 토픽 라우팅에 사용, 소비자가 deserializer 선택 기준
alter table outbox add column aggregate_type varchar(32);
update outbox set aggregate_type = 'page' where aggregate_type is null;
alter table outbox alter column aggregate_type set not null;

-- F4: actor_id — 변경 주체. 감사·인덱서에서 "누가" 필수
alter table outbox add column actor_id uuid;
-- 기존 행은 actor 복원 불가 → null 허용 유지. 신규 행은 애플리케이션이 NOT NULL 강제.
-- DB 레벨 NOT NULL은 기존 행 때문에 걸지 않되, 앱 코드에서 null 전달을 금지한다.

-- F5 조회용 인덱스 (cleanup: published_at IS NOT NULL AND created_at < ?)
create index idx_outbox_cleanup on outbox(created_at) where published_at is not null;
```

> ⚠️ `aggregate_type`을 NOT NULL로 만들려면 기존 행 갱신이 필요하다. V1에서 insert된 행은
> 전부 page 이벤트이므로 `'page'`로 채운다. production 아닌 dev DB라 데이터 마이그레이션 부담 0.

### 2. `OutboxEventType` enum (F2)

```java
package io.wedocs.doc.outbox;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

/// outbox 이벤트 유형. aggregate_type + event_type의 조합.
/// M4에서 relay가 토픽을 결정하는 매핑도 여기에 둔다.
@RequiredArgsConstructor
@Getter
public enum OutboxEventType {

    PAGE_CREATED("page", "page.created"),
    PAGE_RENAMED("page", "page.renamed"),
    PAGE_MOVED("page", "page.moved"),
    PAGE_ARCHIVED("page", "page.archived"),
    PAGE_RESTORED("page", "page.restored");   // 향후 복원 기능

    private final String aggregateType;
    private final String eventType;

    /// M4에서 relay가 쓸 토픽 결정. 지금은 미사용이지만 계약을 확정해둔다.
    public String topic() {
        return "doc." + aggregateType;  // e.g. "doc.page"
    }
}
```

### 3. Payload 타입 안전 직렬화 (F1)

`OutboxAppender`가 `Object payload`를 받아 Jackson으로 직렬화한다.
호출부는 이벤트별 record를 넘긴다:

```java
// outbox/payload/ 패키지에 이벤트별 record 정의
public record PageCreatedPayload(UUID workspaceId, UUID parentId, String title) {}
public record PageRenamedPayload(String title) {}
public record PageMovedPayload(UUID parentId, int position) {}
public record PageArchivedPayload() {}
```

`OutboxAppender` 시그니처 변경:

```java
public void append(UUID actorId, UUID aggregateId, OutboxEventType type, Object payload)
```

- `actorId`: 변경 주체 (F4)
- `aggregateId`: 대상 식별자
- `type`: enum에서 `aggregateType` + `eventType` 추출
- `payload`: Jackson이 JSON으로 변환

### 4. `OutboxEvent` 엔티티 변경

```java
// 기존 필드 유지 + 추가
@Column(name = "aggregate_type", nullable = false, updatable = false, length = 32)
private String aggregateType;

@Column(name = "actor_id", updatable = false)
private UUID actorId;
```

생성자:
```java
OutboxEvent(UUID actorId, UUID aggregateId, String aggregateType,
            String eventType, String payload, String traceparent) {
    this.actorId = actorId;
    this.aggregateId = aggregateId;
    this.aggregateType = aggregateType;
    this.eventType = eventType;
    this.payload = payload;
    this.traceparent = traceparent;
    this.createdAt = Instant.now();
}
```

### 5. Outbox Cleanup Job (F5)

```java
package io.wedocs.doc.outbox;

@Component
@RequiredArgsConstructor
class OutboxCleanupJob {

    private static final Duration RETENTION = Duration.ofDays(7);

    private final OutboxRepository repository;

    /// 발행 완료(published_at != null) 후 7일 지난 행을 삭제한다.
    /// M2에서는 relay가 없어 published_at이 항상 null이므로 실질적으로 삭제가 발생하지 않는다.
    /// M4에서 relay가 마킹을 시작하면 이 job이 자동으로 동작한다.
    ///
    /// 추가로, M2 한정으로 created_at이 30일 이상인 미발행 행도 삭제한다.
    /// (relay가 없으니 무한 적재 방지)
    @Scheduled(cron = "0 0 3 * * *")  // 매일 새벽 3시
    @Transactional
    public void cleanup() {
        Instant publishedCutoff = Instant.now().minus(RETENTION);
        int publishedDeleted = repository.deletePublishedBefore(publishedCutoff);

        // M2 안전장치: relay 없는 동안 30일 초과 미발행 행도 정리
        Instant unpublishedCutoff = Instant.now().minus(Duration.ofDays(30));
        int unpublishedDeleted = repository.deleteUnpublishedBefore(unpublishedCutoff);

        if (publishedDeleted + unpublishedDeleted > 0) {
            log.info("outbox cleanup: published={} unpublished={}", publishedDeleted, unpublishedDeleted);
        }
    }
}
```

`OutboxRepository`에 커스텀 쿼리 추가:
```java
@Modifying
@Query("DELETE FROM OutboxEvent e WHERE e.publishedAt IS NOT NULL AND e.createdAt < :cutoff")
int deletePublishedBefore(@Param("cutoff") Instant cutoff);

@Modifying
@Query("DELETE FROM OutboxEvent e WHERE e.publishedAt IS NULL AND e.createdAt < :cutoff")
int deleteUnpublishedBefore(@Param("cutoff") Instant cutoff);
```

### 6. Relay 설계 (M4 착수 시 참조 — 코드 미구현)

M4에서 구현할 relay의 확정 설계:

```
┌────────────────┐   poll (1s)   ┌──────────┐   produce    ┌───────┐
│  outbox table  │ ────────────→ │  relay   │ ───────────→ │ Kafka │
│ (published_at  │               │ (Spring  │              │       │
│  IS NULL       │               │  @Sched) │              │       │
│  ORDER BY id)  │               └──────────┘              └───────┘
└────────────────┘                     │
                                       │ 성공 후
                                       ▼
                              UPDATE published_at = now()
                              WHERE id IN (...)
```

**확정 파라미터:**
- 폴링 주기: 1초 (`@Scheduled(fixedDelay = 1000)`)
- 배치 크기: 100건 (`LIMIT 100`)
- Kafka partition key: `aggregate_id` (같은 aggregate의 이벤트 순서 보장)
- Kafka topic: `OutboxEventType.topic()` (= `"doc.page"`)
- 발행 후 마킹: 배치 단위 `UPDATE ... SET published_at = now() WHERE id IN (:ids)`
- 멱등 키(Kafka header): `outbox-id: {id}` — 소비자 dedupe 기준
- traceparent(Kafka header): `traceparent: {traceparent}` — null이면 헤더 생략

**at-least-once 보장:**
- relay가 Kafka produce 후 `published_at` 마킹 전 죽으면 → 재시작 시 같은 행을 재발행
- 소비자는 `outbox-id`로 dedupe → exactly-once semantics at consumer level
- Kafka `enable.idempotence=true` + `acks=all` → 프로듀서 레벨 중복 방지는 네트워크 재시도 범위만

**행 정리:**
- F5 cleanup job이 `published_at IS NOT NULL AND created_at < 7일 전` 삭제
- 볼륨이 커지면 `PARTITION BY RANGE (created_at)` + 월별 파티션 drop으로 전환

## 실행 체크리스트

> 서비스 레포는 **branch + PR + 건별 승인**. controller(C1·C4)만 main 직접.

- [x] **C1** `docs(plan):` 이 파일 신설 — controller main 직접
- [x] **C2** backend PR `refactor(outbox): 실무 수준 하드닝` — PR #24 머지 (`5df4b3f`)
- [x] **C3** 기존 테스트 통과 확인 (`./gradlew :doc-service:test`) — 164 tests, 0 failed
- [x] **C4** `docs:` `current.md` 갱신 + 이 plan `done` — controller main 직접

### PR 크기 추정

| 커밋 | 신규/변경 | 추정 줄 |
|---|---|---|
| c2-1 | V2 마이그레이션 | ~10 |
| c2-2 | enum + record 4종 | ~50 |
| c2-3 | OutboxAppender 변경 | ~30 |
| c2-4 | OutboxEvent 필드 추가 | ~15 |
| c2-5 | PageTreeService 호출 전환 | ~40 |
| c2-6 | CleanupJob + Repository | ~50 |
| c2-7 | 테스트 갱신 | ~60 |
| **합계** | | **~255줄** |

## 검증

- 기존 `OutboxIntegrationTest` 3건 통과 (시그니처 변경 반영)
- 새 검증:
  - `aggregate_type`이 `"page"`로 기록되는지
  - `actor_id`가 null이 아닌지
  - payload가 유효한 JSON인지 (Jackson 파싱 역검증)
  - 특수문자 title (`"개행\n탭\t"따옴표"`)이 valid JSON으로 직렬화되는지 (F1 핵심)
  - cleanup job이 cutoff 이전 행만 삭제하는지

## 범위 밖

- **relay 구현** — M4 (이 plan §6의 설계를 참조해 구현)
- **Kafka 인프라** — M4/M5
- **traceparent 주입** — M4 (OTel 런타임 설치 후)
- **workspace/member 이벤트 추가** — Phase 5 이후 필요 시 enum에 추가
- **ADR-0015 개정** — 이 plan의 §6 내용이 ADR보다 상세하므로, M4 착수 시 ADR에 역반영

## 재개 지점 (Resume)

```
완료 = 2026-08-01. C2 backend PR #24 머지(5df4b3f). 164 테스트 전체 통과.
브랜치 feat/m2-phase5-outbox-hardening → main 머지, 로컬/원격 브랜치 삭제.
```
