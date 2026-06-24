---
name: vector-db
description: "Vector Database — 벡터 데이터베이스 비교, 인덱싱 전략, ANN 알고리즘, 운영 패턴 Use when working with ai 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Vector Database

벡터 데이터베이스 비교, 인덱싱 전략, ANN 알고리즘, 운영 패턴

## Quick Reference (결정 트리)

```
벡터 DB 선택?
    │
    ├─ 관리형 원함 ────────> Pinecone (서버리스, 즉시 시작)
    ├─ 오픈소스 + K8s ────> Milvus 또는 Qdrant
    ├─ 기존 PostgreSQL ───> pgvector (추가 인프라 불필요)
    ├─ 다기능 (BM25+벡터) ─> Weaviate (하이브리드 내장)
    └─ 프로토타입/로컬 ───> Chroma (임베디드, 제로 설정)

인덱스 알고리즘?
    │
    ├─ 정확도 우선 ────────> HNSW (메모리 많이 사용)
    ├─ 메모리 제한 ────────> IVF + PQ (디스크 기반)
    ├─ 균형 ───────────────> HNSW + PQ
    └─ 초대규모 (10B+) ───> ScaNN 또는 DiskANN

규모별 권장?
    │
    ├─ < 100K 벡터 ────────> pgvector / Chroma
    ├─ 100K ~ 10M ─────────> Qdrant / Weaviate / pgvector(HNSW)
    ├─ 10M ~ 1B ───────────> Pinecone / Milvus (분산)
    └─ > 1B ───────────────> Milvus 클러스터 / 전용 솔루션
```

---

## Database Comparison Matrix

| 기능 | Pinecone | Weaviate | Milvus | Qdrant | pgvector | Chroma |
|------|----------|----------|--------|--------|----------|--------|
| **호스팅** | 관리형 | 자체/관리형 | 자체/Zilliz | 자체/관리형 | PostgreSQL | 임베디드 |
| **최대 규모** | 수십억 | 수억 | 수십억 | 수억 | 수백만 | 수백만 |
| **하이브리드 검색** | O | O (내장) | O | O | BM25 별도 | X |
| **메타데이터 필터** | O | O | O | O | O (SQL) | O |
| **다중 벡터** | O | O | O | O | X | X |
| **멀티테넌시** | Namespace | 내장 | Partition | Collection | Schema | Collection |
| **라이선스** | 상용 | BSD-3 | Apache-2 | Apache-2 | PostgreSQL | Apache-2 |
| **언어** | - | Go | Go/C++ | Rust | C | Python |

---

## Indexing Algorithms

### HNSW (Hierarchical Navigable Small World)

```
┌─────────────────────────────────────────┐
│           HNSW 구조                      │
│                                         │
│  Layer 3: ○───────────────○  (소수 노드)  │
│           │               │             │
│  Layer 2: ○───○───────○───○             │
│           │   │       │   │             │
│  Layer 1: ○─○─○─○───○─○─○─○            │
│           │ │ │ │   │ │ │ │             │
│  Layer 0: ○○○○○○○○○○○○○○○○  (전체 노드)  │
│                                         │
│  검색: 상위 레이어 → 하위 레이어 탐색      │
│  시간복잡도: O(log N)                     │
└─────────────────────────────────────────┘
```

| 파라미터 | 설명 | 기본값 | 튜닝 가이드 |
|---------|------|-------|------------|
| `M` | 노드당 연결 수 | 16 | 높을수록 정확, 메모리 증가 (8-64) |
| `ef_construction` | 인덱스 빌드 시 탐색 범위 | 200 | 높을수록 정확, 빌드 느림 (100-500) |
| `ef_search` | 쿼리 시 탐색 범위 | 50 | 높을수록 정확, 쿼리 느림 (50-200) |

### IVF (Inverted File Index)

```
IVF: 벡터를 클러스터로 분할 → 쿼리 시 가까운 클러스터만 검색

nlist = 1024      # 클러스터 수 (sqrt(N) 권장)
nprobe = 16       # 검색할 클러스터 수 (높을수록 정확, 느림)

PQ (Product Quantization): 벡터 압축
  - 1536차원 × 4bytes = 6KB/벡터
  - PQ(m=48) 적용 → 48bytes/벡터 (99% 압축)
  - recall 약 5-10% 감소 vs 메모리 99% 절감
```

---

## pgvector Deep Dive

### 설치 및 설정

```sql
-- 확장 활성화
CREATE EXTENSION vector;

-- 테이블 생성
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),  -- 차원 수 지정
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 인덱스 생성

```sql
-- HNSW 인덱스 (권장: 100K+ 벡터)
CREATE INDEX ON documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200);

-- IVF 인덱스 (메모리 제한 환경)
CREATE INDEX ON documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);  -- sqrt(row_count) 권장

-- 거리 연산자
-- vector_cosine_ops   : <=>  코사인 거리 (추천)
-- vector_l2_ops       : <->  유클리드 거리
-- vector_ip_ops       : <#>  내적 (음수 반환)
```

### 쿼리 최적화

```sql
-- 코사인 유사도 검색
SELECT id, content, 1 - (embedding <=> $1) AS similarity
FROM documents
WHERE metadata->>'category' = 'tech'
ORDER BY embedding <=> $1
LIMIT 10;

-- HNSW ef_search 튜닝 (세션별)
SET hnsw.ef_search = 100;  -- 기본 40, 높이면 정확도 증가

-- IVF probes 튜닝
SET ivfflat.probes = 10;   -- 기본 1, 높이면 정확도 증가

-- EXPLAIN으로 인덱스 사용 확인
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
```

### Python 연동

```python
import psycopg
import numpy as np

conn = psycopg.connect("postgresql://user:pass@localhost/vectordb")

# pgvector 타입 등록
from pgvector.psycopg import register_vector
register_vector(conn)

# 삽입
embedding = np.random.rand(1536).astype(np.float32)
conn.execute(
    "INSERT INTO documents (content, embedding, metadata) VALUES (%s, %s, %s)",
    ("문서 내용", embedding, '{"source": "blog"}')
)

# 검색
query_vec = np.random.rand(1536).astype(np.float32)
results = conn.execute(
    """
    SELECT id, content, 1 - (embedding <=> %s) AS similarity
    FROM documents
    ORDER BY embedding <=> %s
    LIMIT 5
    """,
    (query_vec, query_vec)
).fetchall()
```

---

## Weaviate Deep Dive

### Schema 및 Vectorization

```python
import weaviate
from weaviate.classes.config import Configure, Property, DataType

client = weaviate.connect_to_local()

# 컬렉션 생성 (자동 벡터화)
client.collections.create(
    name="Document",
    vectorizer_config=Configure.Vectorizer.text2vec_openai(
        model="text-embedding-3-small",
    ),
    properties=[
        Property(name="content", data_type=DataType.TEXT),
        Property(name="category", data_type=DataType.TEXT),
        Property(name="source", data_type=DataType.TEXT),
    ],
)

# 데이터 삽입 (벡터 자동 생성)
collection = client.collections.get("Document")
collection.data.insert(
    properties={
        "content": "RAG는 검색 증강 생성을 의미합니다.",
        "category": "ai",
        "source": "blog",
    }
)
```

### Hybrid Search

```python
from weaviate.classes.query import MetadataQuery, Filter

collection = client.collections.get("Document")

# Hybrid search (BM25 + vector)
results = collection.query.hybrid(
    query="RAG 아키텍처 설명",
    alpha=0.75,     # 0=BM25 only, 1=vector only, 0.75=vector 중심 하이브리드
    limit=5,
    filters=Filter.by_property("category").equal("ai"),
    return_metadata=MetadataQuery(score=True, explain_score=True),
)

for obj in results.objects:
    print(f"Score: {obj.metadata.score:.4f} | {obj.properties['content'][:80]}")
```

### Multi-tenancy

```python
# 멀티테넌시 활성화 컬렉션
client.collections.create(
    name="TenantDocument",
    multi_tenancy_config=Configure.multi_tenancy(enabled=True),
    # ...
)

collection = client.collections.get("TenantDocument")

# 테넌트 추가
from weaviate.classes.tenants import Tenant
collection.tenants.create([Tenant(name="tenant_A"), Tenant(name="tenant_B")])

# 테넌트별 데이터 접근
tenant_col = collection.with_tenant("tenant_A")
tenant_col.data.insert(properties={"content": "테넌트 A 데이터"})
```

---

## Pinecone Deep Dive

### Serverless vs Pods

```
┌──────────────────────────────────────────┐
│           Pinecone 배포 모델              │
├──────────────────┬───────────────────────┤
│   Serverless     │   Pods               │
├──────────────────┼───────────────────────┤
│ 자동 스케일링     │ 수동 Pod 수 관리      │
│ 사용량 과금       │ Pod 단위 과금         │
│ 빠른 시작        │ 대규모 (10B+)         │
│ 대부분 추천      │ 극한 성능 필요 시     │
└──────────────────┴───────────────────────┘
```

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="...")

# Serverless 인덱스 생성
pc.create_index(
    name="documents",
    dimension=1536,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
)

index = pc.Index("documents")

# Upsert (batch)
vectors = [
    {"id": "doc1", "values": embedding1, "metadata": {"source": "blog"}},
    {"id": "doc2", "values": embedding2, "metadata": {"source": "docs"}},
]
index.upsert(vectors=vectors, namespace="production")

# 검색 + 메타데이터 필터
results = index.query(
    vector=query_embedding,
    top_k=5,
    namespace="production",
    filter={"source": {"$eq": "blog"}},
    include_metadata=True,
)
```

---

## Common Operations

### Batch Upsert (대량 삽입)

```python
def batch_upsert(index, vectors: list[dict], batch_size: int = 100):
    """대량 벡터 삽입 (배치 처리)"""
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch)

# 임베딩 생성 + 삽입 파이프라인
def embed_and_upsert(texts: list[str], metadata_list: list[dict]):
    """텍스트를 임베딩하고 벡터 DB에 삽입"""
    embeddings = []
    for i in range(0, len(texts), 2048):  # OpenAI batch limit
        batch = texts[i:i + 2048]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )
        embeddings.extend([d.embedding for d in response.data])

    vectors = [
        {"id": f"doc_{i}", "values": emb, "metadata": meta}
        for i, (emb, meta) in enumerate(zip(embeddings, metadata_list))
    ]
    batch_upsert(index, vectors)
```

### Filtered Search

```python
# Pinecone 필터 문법
filter_examples = {
    # 단일 조건
    "exact_match": {"category": {"$eq": "tech"}},
    # 범위 조건
    "date_range": {"created_at": {"$gte": "2024-01-01"}},
    # AND 조건
    "multiple": {
        "$and": [
            {"category": {"$eq": "tech"}},
            {"score": {"$gte": 0.8}},
        ]
    },
    # OR 조건
    "or_condition": {
        "$or": [
            {"source": {"$eq": "blog"}},
            {"source": {"$eq": "docs"}},
        ]
    },
    # IN 조건
    "in_list": {"category": {"$in": ["tech", "ai", "ml"]}},
}
```

---

## Performance Tuning

### 인덱스 파라미터 가이드

| 시나리오 | HNSW M | ef_construction | ef_search | 예상 Recall |
|---------|--------|-----------------|-----------|------------|
| 속도 우선 | 8 | 100 | 30 | ~90% |
| 균형 (추천) | 16 | 200 | 50 | ~95% |
| 정확도 우선 | 32 | 400 | 100 | ~99% |
| 최고 정확도 | 64 | 500 | 200 | ~99.5% |

### 메모리 예측

```
메모리 사용량 = N × (d × 4 + M × 2 × 8 + overhead) bytes

예시: 1M 벡터, 1536차원, M=16
  = 1,000,000 × (1536 × 4 + 16 × 2 × 8 + 64)
  = 1,000,000 × 6,464
  ≈ 6.5 GB

PQ 압축 적용 시 (m=48):
  = 1,000,000 × (48 + 16 × 2 × 8 + 64)
  ≈ 0.4 GB (94% 절감)
```

---

## Production Patterns

### 모니터링 체크리스트

```
┌─────────────────────────────────────────────┐
│          벡터 DB 모니터링 항목                 │
├─────────────────────────────────────────────┤
│ 성능                                        │
│  - p50/p95/p99 쿼리 지연시간                  │
│  - 초당 쿼리 수 (QPS)                        │
│  - 인덱스 빌드 시간                           │
│                                             │
│ 품질                                        │
│  - Recall@K (정기 샘플링)                     │
│  - 검색 결과의 평균 유사도 점수                 │
│                                             │
│ 리소스                                       │
│  - 메모리 사용량 vs 할당량                     │
│  - 디스크 사용량 (PQ/IVF 인덱스)               │
│  - CPU 사용률 (인덱스 빌드 시 피크)             │
│                                             │
│ 운영                                        │
│  - 벡터 수 증가 추세                          │
│  - 인덱스 리빌드 주기                         │
│  - 백업 성공/실패                             │
└─────────────────────────────────────────────┘
```

### 마이그레이션 패턴

```python
def migrate_vectors(source_db, target_db, batch_size: int = 500):
    """벡터 DB 간 마이그레이션"""
    offset = 0
    total = 0

    while True:
        # Source에서 읽기
        batch = source_db.fetch(limit=batch_size, offset=offset)
        if not batch:
            break

        # Target에 쓰기
        vectors = [
            {"id": item.id, "values": item.values, "metadata": item.metadata}
            for item in batch
        ]
        target_db.upsert(vectors)

        offset += batch_size
        total += len(batch)
        print(f"Migrated {total} vectors...")

    print(f"Migration complete: {total} vectors transferred")
```

---

## Cost Analysis

| DB | 1M 벡터 (1536d) 월 비용 | 10M 벡터 월 비용 | 비고 |
|----|------------------------|-----------------|------|
| Pinecone Serverless | ~$35 | ~$200 | 사용량 과금 |
| Weaviate Cloud | ~$55 | ~$350 | Sandbox 무료 |
| Qdrant Cloud | ~$45 | ~$280 | 1GB 무료 |
| Milvus (Zilliz) | ~$65 | ~$400 | 자체 호스팅 무료 |
| pgvector (RDS) | ~$30 | ~$150+ | DB 인스턴스 비용 |
| Chroma | $0 | $0 | 로컬 전용 |

> 비용은 대략적인 추정치이며 사용 패턴에 따라 크게 달라질 수 있음
