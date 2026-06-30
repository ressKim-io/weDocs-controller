# SDD — 데이터 · 실시간 동기화 · AI · 인증
> [← 인덱스](../SDD.md)

## 5. 데이터 모델 / 저장소

### PostgreSQL (Doc 서비스) — page-tree + workspace (M2, [PRD §4 D-1](../prd/4-data-and-permission-model.md), [ADR-0012](../adr/0012-crdt-boundary-content-vs-tree.md))
```
users(id, email, password_hash, display_name, created_at)
workspaces(id, name, owner_id, created_at)
workspace_members(workspace_id, user_id, role)        -- role: owner | member
pages(id, workspace_id, parent_id, title, position, archived, created_at, updated_at)  -- self-tree(parent_id)
page_permissions(page_id, user_id, level)             -- level: editor | viewer (override, 트리 상속)
page_snapshots(page_id, snapshot bytea, version, created_at)  -- CRDT blob(lib0 v1)
outbox(id, aggregate_id, event_type, payload, traceparent, created_at, published_at)  -- 앱레벨(ADR-0015)
```
> 평면 `documents` 구조를 대체(M1 전제). 페이지 *내용* 동시성=CRDT(page_snapshots), 페이지 *트리* 동시성=관계형(pages, doc-service 트랜잭션·사이클 검사). 유효 권한 = 명시 page_permissions > 조상 상속 > workspace baseline(member 기본=editor) > 거부.
### Redis (게이트웨이/AI 공용)
- `presence:{docId}` — 접속자·커서 (TTL)
- pub/sub `doc:{docId}` — update·awareness fan-out
- AI 추론 큐(depth 모니터링)
### pgvector (AI 서비스)
```
doc_chunks(id, doc_id, chunk_text, embedding vector(N), metadata, created_at)
```

---

## 6. 실시간 동기화 설계

### 6.1 두 축 분리
| 축 | 채널 | 영속성 | 경로 |
|---|---|---|---|
| 문서 sync | binary update | 영속(스냅샷) | Yjs ↔ Gateway ↔ CRDT Engine(**bidi**) |
| awareness | awareness update | 휘발(TTL) | Yjs ↔ Gateway ↔ Redis pub/sub |

휘발 커서를 CRDT에 섞지 말 것(tombstone 오염).

### 6.2 신규 접속 시퀀스
```
client → gateway: connect(docId, JWT)
gateway → doc: CheckPermission ⇒ role
gateway ↔ crdt: Sync 스트림 open (docId 메타데이터 → consistent hash 라우팅)
gateway → crdt: ClientFrame(state_vector) ; crdt → gateway: ServerFrame(diff update)
client: 로컬 Yjs 적용(즉시 편집 가능)
이후: update가 bidi 스트림으로 양방향 흐름 + Redis fan-out
```

### 6.3 수평 확장
- CRDT Engine: docId consistent hashing(같은 문서 = 같은 인스턴스). Istio waypoint + DestinationRule.
- WS Gateway: 무상태, 크로스-인스턴스 전파는 Redis pub/sub.
- 장애: 엔진 인스턴스 down → 문서 재라우팅 → 복원. **M2 보장경계 = 최신 스냅샷**(엔진 ensure→`LoadSnapshot`→`decode_v1`→apply→SyncStep2, [ADR-0013](../adr/0013-snapshot-persistence-lifecycle.md)). 무손실(Redis 버퍼) = M5.

---

## 7. AI 파이프라인 (Python)

### 7.1 인덱싱 (쓰기, 비동기) — outbox=[ADR-0015](../adr/0015-outbox-app-level.md)
```
문서 변경 → Doc 앱레벨 outbox(트랜잭션 동봉) → [relay] → Kafka(doc.updated)
  → Indexing Consumer(Python): LlamaIndex 청킹 → 임베딩(Ollama) → pgvector upsert
```
> M2 = outbox 테이블 + 트랜잭션 쓰기(traceparent 주입)만. relay 발행·Kafka·소비 = **M4**. Debezium은 홈랩 KinD 리소스로 기각.
### 7.2 질의 (읽기, 스트리밍)
```
POST /ai/qa {docId, query}
  → 임베딩(query) → LlamaIndex 검색(top_k, 메타 필터) → 컨텍스트 증강
  → LLM stream(Ollama/폴백) → SSE 토큰 스트림
```
### 7.3 추론 큐 + 폴백
```
요청 → [asyncio 큐] ──(GPU 여유)──▶ Ollama(로컬)
                     └─(큐 초과/타임아웃/장애)─▶ 클라우드 폴백 or 429
```
SSE 중단 처리: 추론 실패 시 error 이벤트 + 폴백 재시도.

---

## 8. 인증 / 인가 ([ADR-0014](../adr/0014-auth-authz-boundary.md))
- **인증**: JWT 발급=Doc 서비스(REST 로그인). 검증=게이트웨이(WS 핸드셰이크)·Doc 서비스(REST). M2는 doc-service 내장(분리=후속).
- **WS 토큰 전달**: `Sec-WebSocket-Protocol` 서브프로토콜(브라우저 헤더 커스텀 불가 우회, query param 로그유출 회피).
- **인가**: connect 시 `DocService.CheckPermission(user_id, page_id)` → effective level(상속 해석). 게이트웨이가 JWT 검증 후 user_id 전달(proto 토큰필드 불요).
- **viewer write-block**: 게이트웨이 1차(client→server update drop) + 엔진 방어(D-5). 실패 close: 인증=4401·인가=4403.
- **서비스 간**: Istio Ambient ztunnel mTLS (코드 무관). 게이트웨이→doc-service user_id 신뢰의 전제.

---
