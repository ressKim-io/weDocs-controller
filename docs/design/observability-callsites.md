# 관측 콜사이트 정의

> M5(인프라·관측) 배포 전에 **어디서 무엇을 계측할지** 확정한다.
> 실제 exporter 배선은 M5에서 하되, 콜사이트 이름·타입·레이블은 여기가 SSOT.
> 이름이 바뀌면 대시보드·알림이 조용히 깨지므로 **이름 변경 = breaking change**.

**최종 갱신**: 2026-08-03

---

## crdt-engine (Rust)

| 이름 | 타입 | 단위 | 레이블 | 설명 | 삽입 위치 |
|---|---|---|---|---|---|
| `crdt.merge_duration` | Histogram | ms | `doc_id` | `apply_v1` 1회 소요 시간. NFR p95 < 100ms의 서버측 측정점 | `doc.rs` apply_v1 진입~반환 |
| `crdt.active_streams` | Gauge | count | — | 현재 열린 Sync bidi 스트림 수. 부하 가시성 | `sync/session.rs` open/close |
| `crdt.lagged_total` | Counter | count | `reason` | 클라이언트가 broadcast lag으로 drop된 횟수 | `sync/session.rs` lagged 판정 |
| `crdt.snapshot_save_duration` | Histogram | ms | `outcome` | sweeper → doc-service SaveSnapshot RPC 소요 | `snapshot/doc_service.rs` save 호출 |
| `crdt.snapshot_load_duration` | Histogram | ms | `outcome` | open 경로 LoadSnapshot RPC 소요 | `snapshot/doc_service.rs` load 호출 |
| `crdt.docs_loaded` | Gauge | count | — | 현재 메모리에 로드된 문서 수 (DocSlot 수) | `doc.rs` insert/remove |

### 구현 참고
- crate: `metrics` (0.24+) + `metrics-exporter-prometheus` 또는 OTel metrics SDK
- M5 전까지는 `NoopRecorder` (컴파일만 확인, 런타임 비용 0)
- `reason` 레이블 값: `slow_consumer` / `channel_full`
- `outcome` 레이블 값: `ok` / `transient` / `not_persistable` / `permanent`

---

## ws-gateway (Java / Spring Boot)

| 이름 | 타입 | 단위 | 레이블 | 설명 | 삽입 위치 |
|---|---|---|---|---|---|
| `ws.active_connections` | Gauge | count | — | 현재 열린 WebSocket 세션 수 | `DocWebSocketHandler` open/close |
| `ws.handshake` | Counter | count | `result` | 핸드셰이크 최종 결과. 기존 구현 유지 | `AuthHandshakeInterceptor` |
| `ws.write.dropped` | Counter | count | `reason` | viewer 쓰기 차단 횟수. 기존 구현 유지 | `DocWebSocketHandler` |
| `ws.frame.inbound` | Counter | count | `type` | 인바운드 프레임 종류별 카운트 (sync_step1/update) | `DocWebSocketHandler` handleBinaryMessage |
| `ws.engine.stream_error` | Counter | count | — | 엔진 스트림 onError 횟수 | `DocWebSocketHandler` engineResponseObserver |
| `authz.check_permission.duration` | Timer | ms | — | CheckPermission gRPC 호출 소요. 기존 구현 유지 | `AuthzHandshakeInterceptor` |
| `authz.backend.error` | Counter | count | — | CheckPermission 백엔드 장애 횟수. 기존 구현 유지 | `AuthzHandshakeInterceptor` |

### 구현 참고
- Spring Boot Actuator + Micrometer (이미 의존성 존재)
- `ws.handshake`, `ws.write.dropped`, `authz.*`는 **이미 구현됨** (Phase 2a-2)
- 신규 = `ws.active_connections`, `ws.frame.inbound`, `ws.engine.stream_error`
- `result` 레이블 값: `ok` / `authn_fail` / `authz_denied` / `backend_error`
- `type` 레이블 값: `sync_step1` / `sync_step2` / `update`

---

## doc-service (Java / Spring Boot)

| 이름 | 타입 | 단위 | 레이블 | 설명 | 삽입 위치 |
|---|---|---|---|---|---|
| `grpc.server.duration` | Histogram | ms | `method` | gRPC 메서드별 처리 시간 (OTel 표준 이름) | gRPC interceptor (OTel agent 자동) |
| `outbox.appended` | Counter | count | `event_type` | outbox 이벤트 발행 횟수 | `OutboxAppender.append` |
| `outbox.cleanup.deleted` | Counter | count | `category` | cleanup job 삭제 행 수 | `OutboxCleanupJob.cleanup` |
| `snapshot.save.size_bytes` | Histogram | bytes | — | SaveSnapshot blob 크기 분포 | `SnapshotService.save` |

### 구현 참고
- OTel Java Agent 자동 계측이 `grpc.server.duration` 제공
- 나머지는 Micrometer `MeterRegistry` 수동 계측
- `category` 레이블 값: `published` / `unpublished`

---

## 대시보드 구성 (M5 Grafana)

| 대시보드 | 핵심 패널 |
|---|---|
| **CRDT Engine** | merge p95/p99, active streams, docs loaded, snapshot save/load latency |
| **WS Gateway** | active connections, handshake rate (by result), write drop rate, engine stream errors |
| **Doc Service** | gRPC latency by method, outbox append rate, snapshot size distribution |
| **Overview** | 3서비스 golden signals (rate/errors/duration/saturation) |

---

## 알림 후보 (M5 배포 후)

| 조건 | 심각도 | 근거 |
|---|---|---|
| `authz.backend.error` > 0 for 1min | Critical | 전 사용자 연결 불가 (ADR-0021) |
| `crdt.active_streams` = 0 for 5min (업무시간) | Warning | 엔진 장애 또는 네트워크 단절 |
| `ws.active_connections` > 2000 | Warning | VT saturation 접근 (NFR 상한) |
| `crdt.merge_duration` p99 > 500ms | Warning | 수렴 지연 — 문서 크기 또는 부하 이상 |
