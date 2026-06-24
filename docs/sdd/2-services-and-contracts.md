# SDD — 서비스 · 언어 배정 · proto 계약
> [← 인덱스](../SDD.md)

## 2. 기술 스택 및 언어 배정

| 서비스 | 언어/런타임 | 핵심 라이브러리 | 지배적 제약 | 선택 근거 |
|---|---|---|---|---|
| WS Gateway + Presence | **Java 25 / Spring Boot 4.1** | Spring WebSocket, Virtual Thread, go-redis 대응(Lettuce), grpc-java | I/O 바운드, 대량 동시 커넥션 | VT(JEP 491로 pinning 해소)로 blocking 코드로 수만 커넥션. 한국 Java 시장 적합 |
| CRDT Engine | **Rust** | `yrs`(y-crdt), `tonic`(gRPC), `sqlx`, `criterion`(벤치), `proptest` | CPU 바운드 + 정확성 critical | 머지는 CPU 바운드, 수렴 정확성이 생명, yrs가 클라 Yjs와 wire 호환. **엔진 레벨 최적화** |
| Doc/Session | **Java 25 / Spring Boot 4.1** | Spring Security, Spring Data JPA, grpc-spring | 복잡한 도메인 로직 | 권한·트랜잭션·인증 생태계 |
| AI Service | **Python 3.12+ / FastAPI** | **LlamaIndex**, grpcio, pgvector client, sse-starlette | AI 생태계 깊이 | RAG 품질(고급 청킹·쿼리 분해)이 LlamaIndex 강점. AI는 Python이 명백한 정답 영역 |
| Indexing Consumer | **Python** | kafka-python/aiokafka, LlamaIndex, 임베딩(Ollama) | AI 인덱싱 | AI Service와 같은 스택·임베딩 파이프라인 공유 |

핵심 버전 노트:
- **Spring Boot 4.1** + **Java 25 LTS** (VT 기본, JEP 491 pinning 해소 포함). gRPC는 4.1 정식 지원.
- **Rust**: yrs는 Yjs의 Rust 포트로 클라이언트 Yjs와 동일 binary wire format.
- **Python**: FastAPI(async) + LlamaIndex. GIL은 AI Service가 I/O 바운드(LLM 대기)라 async로 우회, 무거운 계산은 Ollama가 처리.
- proto: proto3, **buf** 툴체인.

**언어 일관 논리 (면접 방어용 한 줄)**: "I/O 바운드는 Java Virtual Thread, AI 생태계는 Python, CPU 바운드 + 정확성 critical(CRDT)은 Rust — 각 서비스의 지배적 제약에 언어를 배치했다."

---

## 3. 서비스 명세

### 3.1 WS Gateway + Presence (Java / Virtual Thread)
- **책임**: WebSocket 종단, JWT 핸드셰이크 검증, 문서 sync relay(엔진과 bidi), awareness fan-out
- **외부 I/F**: WebSocket / **내부 I/F**: gRPC(bidi) → CRDT Engine, gRPC → Doc Service, Redis pub/sub
- **동시성 모델**:
  - **Virtual Thread per connection** — blocking 코드로 단순하게. JEP 491로 synchronized pinning 없음.
  - VT 풀링 금지(task당 생성). 동시성 제한은 **Semaphore**로.
  - 남은 pinning은 native call뿐 — 게이트웨이는 native 의존 피함(엔진은 별도 서비스라 JNI 불필요).
- **백프레셔**: 느린 클라이언트 대비 — 송신 큐 임계 초과 시 메시지 드롭/연결 종료 정책.
- **재연결**: heartbeat + exponential backoff + state reconciliation(서버 state vector와 diff). ⚠️ Istio ztunnel 업그레이드가 long-lived 연결을 리셋할 수 있어 day-one 필수.

### 3.2 CRDT Engine (Rust) — ★핵심 엔진
- **책임**: 문서별 yrs 상태, update 머지, state vector diff, 스냅샷 생성/적용, tombstone GC
- **I/F**: gRPC(server), **bidi streaming** (게이트웨이와 연결 유지, 매 update마다 새 호출 X)
- **엔진 깊이 (단순 래퍼와 차별)**:
  - 머지 핫패스 최적화 — 메모리 레이아웃, 배치 머지, 락 최소화/락프리 고려
  - 제로카피 직렬화 경로, update 배칭/파이프라이닝
  - 동시 다문서 처리 (문서별 격리)
  - **criterion 벤치마크**로 "Java 단순 래퍼 대비 N배" 정량 증명
- **상태/확장**:
  - 문서별 yrs `Doc` 인메모리 + 주기/임계 스냅샷을 PostgreSQL에 영속화
  - **수평 확장**: docId **consistent hashing** → 같은 문서 = 같은 인스턴스 (인메모리 일관성). Istio waypoint + DestinationRule(consistentHash by header)로 라우팅, docId는 gRPC 메타데이터에.
- **동기화 메커니즘**:
  - 신규 접속: 클라 state vector → `encode_diff` → 최소 diff만 전송
  - 스냅샷: update N개/T초마다 `encode_state_as_update` → blob 저장. 복원 시 적용.
  - GC: yrs가 인접 struct 병합·삭제 콘텐츠 비움으로 tombstone 메타 축소(완전 삭제 불가, 완화)

### 3.3 Doc/Session 서비스 (Java)
- **책임**: 문서 메타데이터·권한·멤버십, 룸 lifecycle, 스냅샷 영속화 오케스트레이션, JWT 발급/검증
- **I/F**: REST(클라이언트: 문서 CRUD, 인증) + gRPC(내부: 권한 체크, 스냅샷 저장)
- **저장소**: PostgreSQL
- **이벤트**: 문서 변경을 Kafka로 발행(인덱싱 트리거) — **outbox 패턴**(트랜잭션 정합). ⚠️ Kafka는 async 경계라 OTel context를 메시지 페이로드에 주입해야 trace가 이어짐.

### 3.4 AI Service (Python / FastAPI)
- **책임**: RAG Q&A, 요약/리라이트. 추론 큐잉·백프레셔·폴백.
- **I/F**: REST + **SSE**(클라이언트: 토큰 스트림) / gRPC(내부 필요 시)
- **저장소**: pgvector
- **설계 포인트**:
  - **RAG**: LlamaIndex로 인제스천(청킹·노드 파싱)·인덱싱·쿼리 엔진. 검색 품질 튜닝이 차별점.
  - **provider 추상화**: Ollama(1순위) ↔ 클라우드(폴백). 라우터/팩토리 패턴.
  - **추론 큐**: 단일 GPU 보호 — 동시성 제한(asyncio semaphore), 큐 초과 시 폴백 또는 429
  - **stateless**: 문서 텍스트 in → 답/요약 텍스트 out. CRDT 미인지.
  - **Indexing Consumer**(별도 프로세스/워커): Kafka 소비 → 청킹 → 임베딩 → pgvector upsert

---

## 4. 서비스 간 통신 — proto 계약 + buf

> proto는 `controller/proto/`에 SSOT. 각 레포가 **git submodule**로 참조하고 **buf**로 stub 생성.

### 4.1 buf 전략
- **buf CLI** 사용 (BSR는 옵션; 개인 프로젝트엔 CLI로 충분)
- `buf lint` — 스타일 강제
- `buf breaking --against` — proto 변경 시 호환성 검사 (FILE/PACKAGE/WIRE 카테고리)
- `buf generate` — Java/Python/Rust stub 동시 생성 (`buf.gen.yaml`에 플러그인 정의)
- **CI 게이트**: controller CI에서 `buf breaking` 통과 → 다운스트림 빌드 트리거
- 참고: buf는 CNCF 프로젝트가 아닌 Buf사 OSS(de facto 표준). CNCF인 건 gRPC, Buf의 Connect RPC는 CNCF 합류.

### 4.2 proto 정의 (요지)
```proto
// common/common.proto
enum Role { ROLE_UNSPECIFIED=0; ROLE_VIEWER=1; ROLE_EDITOR=2; ROLE_OWNER=3; }

// crdt/crdt.proto
service CrdtEngine {
  rpc Sync(stream ClientFrame) returns (stream ServerFrame);  // bidi streaming
  rpc GetSnapshot(DocRef) returns (Snapshot);
}
message ClientFrame { string doc_id=1; bytes update=2; bytes state_vector=3; }
message ServerFrame { bytes update=1; bytes state_vector=2; }
message Snapshot { string doc_id=1; bytes data=2; }

// doc/doc.proto
service DocService {
  rpc CheckPermission(CheckPermissionRequest) returns (CheckPermissionResponse);
  rpc SaveSnapshot(SaveSnapshotRequest) returns (SaveSnapshotResponse);
  rpc GetDocMeta(DocRef) returns (DocMeta);
}

// ai/ai.proto (내부 RAG 검색; 클라이언트는 REST/SSE)
service RagRetriever { rpc Retrieve(RetrieveRequest) returns (RetrieveResponse); }
```
> v1 대비 변경: CrdtEngine을 단발 `ApplyUpdate`에서 **bidi `Sync` 스트림**으로 (네트워크 홉 최소화). docId는 스트림 메타데이터로 전달해 consistent hash 라우팅.

---
