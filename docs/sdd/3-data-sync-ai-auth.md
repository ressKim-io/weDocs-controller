# SDD — 데이터 · 실시간 동기화 · AI · 인증
> [← 인덱스](../SDD.md)

## 5. 데이터 모델 / 저장소

### PostgreSQL (Doc 서비스)
```
documents(id, title, owner_id, created_at, updated_at)
document_members(doc_id, user_id, role)
document_snapshots(doc_id, snapshot bytea, version, created_at)
users(id, email, password_hash, created_at)
```
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
- 장애: 엔진 인스턴스 down → 문서 재라우팅 → 최신 스냅샷 + Redis 버퍼 복원 (M2/M5 구체화)

---

## 7. AI 파이프라인 (Python)

### 7.1 인덱싱 (쓰기, 비동기)
```
문서 변경 → Doc outbox → Kafka(doc.updated)
  → Indexing Consumer(Python): LlamaIndex 청킹 → 임베딩(Ollama) → pgvector upsert
```
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

## 8. 인증 / 인가
- **인증**: JWT(Doc 서비스 발급), WS 핸드셰이크·REST 검증
- **인가**: 문서 권한 = `DocService.CheckPermission`(gRPC), 게이트웨이·AI가 호출
- **서비스 간**: Istio Ambient ztunnel mTLS (코드 무관)

---
