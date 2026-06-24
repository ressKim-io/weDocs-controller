# SDD — 설계 원칙 & 아키텍처 개요
> [← 인덱스](../SDD.md)

## 0. 설계 원칙

1. **언어는 지배적 제약이 선택한다.**
   - **I/O 바운드** (게이트웨이, 도메인) → Java Virtual Thread
   - **AI 생태계** (RAG·임베딩 도구) → Python
   - **CPU 바운드 + 정확성 critical** (CRDT 머지) → Rust
   - 이 셋이 "왜 이 언어?"에 대한 일관 논리다. Go를 뺀 이유: Virtual Thread가 goroutine의 동시성 우위를 상쇄해 "왜 Go?"를 방어하기 어려움.
2. **proto가 단일 진실 공급원(SSOT).** buf로 lint·breaking-change·codegen을 강제한다.
3. **AI는 CRDT를 모른다.** AI Service는 stateless 텍스트 in/out. 문서 수정은 항상 클라이언트의 Yjs 연산으로만.
4. **Rust는 래퍼가 아니라 엔진이다.** yrs를 gRPC로 감싸기만 하는 게 아니라 머지/스냅샷/직렬화를 근본 최적화하고 벤치마크로 증명한다.
5. **상태는 가장 다루기 싼 곳에.** 휘발성(presence)은 Redis, 영속(스냅샷)은 PostgreSQL, 문서 상태(stateful)는 엔진 인스턴스에 consistent hashing.
6. **리스크 우선 구현.** 가장 불확실한 것(CRDT/Rust)을 먼저 검증한다(M1).

---

## 1. 아키텍처 개요

```
                       [ 브라우저: React + Tiptap + Yjs ]
                          │                          │
              WebSocket   │                          │  SSE (AI 토큰 스트림)
            (CRDT update, │                          │  REST (AI 요청)
             awareness)   ↓                          ↓
        ┌────────────────────────────┐   ┌────────────────────────┐
        │   WS Gateway + Presence     │   │      AI Service        │
        │   (Java / Virtual Thread)   │   │  (Python / FastAPI)    │
        │  - WS 종단, JWT 검증          │   │  - LlamaIndex RAG      │
        │  - VT per-connection         │   │  - 추론 큐 + 백프레셔   │
        │  - awareness fan-out         │   │  - Ollama / 클라우드 폴백│
        └────┬──────────────┬─────────┘   └──────┬──────────┬──────┘
             │ gRPC(bidi)   │ Redis              │ gRPC     │
             ↓              ↓ (pub/sub,          ↓          ↓
     ┌──────────────────┐  │  presence)  ┌─────────────┐  [Ollama]
     │  CRDT Engine     │  │             │ Doc/Session │  4060Ti GPU
     │  (Rust / yrs)    │◀─┼──gRPC──────▶│  (Java)     │      +
     │  ★엔진: 머지 최적화│  │             │ - 권한/멤버  │  [클라우드 폴백]
     │  - state vec/diff │  │             │ - 룸 lifecycle│
     │  - snapshot/GC    │  │             │ - 인증(JWT) │
     │  - bidi streaming │  │             └──────┬──────┘
     │  - consistent hash│  │                    │ domain event
     └────────┬─────────┘  │                    ↓
              │ snapshot    │              [Kafka] ──▶ Indexing Consumer (Python)
              ↓             ↓                                 │ embed
         [PostgreSQL]   [Redis]                               ↓
         (메타,스냅샷)                                    [pgvector] (RAG 인덱스)

   서비스 메시: Istio Ambient (ztunnel = L4 mTLS 전부 / waypoint = L7, CRDT Engine만)
   관측: OTel 단일 trace (Java → Rust → Python), OTLP → LGTM
```

데이터 흐름:
- **편집**: 브라우저(Yjs) → WS Gateway → CRDT Engine(머지, **bidi streaming**) → 주기 스냅샷 → PostgreSQL
- **presence**: 브라우저 → WS Gateway → Redis pub/sub → 타 게이트웨이 → 타 브라우저 (휘발)
- **AI 질의**: 브라우저 → AI Service(Python) → 임베딩 → pgvector 검색 → 컨텍스트 증강 → LLM → SSE
- **AI 인덱싱**: 문서 변경 → Kafka → Indexing Consumer(Python) → 임베딩 → pgvector

---
