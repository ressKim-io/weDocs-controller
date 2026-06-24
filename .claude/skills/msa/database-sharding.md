---
name: database-sharding
description: "데이터베이스 샤딩 가이드 — 대규모 트래픽 환경에서 수평 확장을 위한 샤딩 전략, Shard Key 선택, Citus/Vitess 구현, Read Replica 패턴 Use when working with msa 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# 데이터베이스 샤딩 가이드

대규모 트래픽 환경에서 수평 확장을 위한 샤딩 전략, Shard Key 선택, Citus/Vitess 구현, Read Replica 패턴

## Quick Reference (결정 트리)

```
데이터베이스 확장 필요?
    ├─ 읽기 부하만 높음 ──────────> Read Replica (가장 간단)
    ├─ 단일 테이블 너무 큼 ───────> 파티셔닝 (같은 인스턴스 내)
    │   ├─ 시계열 데이터 ──> Range Partition
    │   └─ 균등 분배 ─────> Hash Partition
    └─ 쓰기 + 읽기 모두 한계 ────> 샤딩 (다중 인스턴스)
        ├─ 멀티테넌트 SaaS ──> Hash Sharding (tenant_id)
        ├─ 시계열/로그 ──────> Range Sharding (날짜)
        └─ 특수 라우팅 ──────> Directory Sharding

샤딩 전략 선택
    ├─ 균등 분배 중요 ────> Hash-based (Consistent Hashing)
    ├─ 범위 쿼리 중요 ────> Range-based
    └─ 유연한 매핑 필요 ──> Directory-based
```

---

## CRITICAL: 샤딩 vs 파티셔닝 vs Read Replica 비교

| 항목 | 파티셔닝 | 샤딩 | Read Replica |
|------|----------|------|--------------|
| **범위** | 단일 DB 인스턴스 내 | 다중 DB 인스턴스 | 다중 인스턴스 (복제) |
| **확장 방향** | 수직 (Scale Up) | 수평 (Scale Out) | 읽기 수평 확장 |
| **쓰기 확장** | 제한적 | 선형 확장 | 불가 (Primary만 쓰기) |
| **복잡도** | 낮음 | 높음 | 중간 |
| **JOIN** | 제약 없음 | Cross-Shard JOIN 어려움 | 제약 없음 |
| **트랜잭션** | 단일 DB | 분산 트랜잭션 필요 | Primary 단일 트랜잭션 |
| **적합 사례** | 대용량 단일 테이블 | 쓰기+읽기 모두 병목 | 읽기 비율 높은 서비스 |
| **도구** | PostgreSQL/MySQL 내장 | Citus, Vitess, ShardingSphere | 기본 Replication |

**IMPORTANT**: 샤딩 전에 반드시 파티셔닝과 Read Replica를 먼저 검토할 것. 샤딩은 마지막 수단이다.

---

## 샤딩 전략

### Range-based Sharding

```sql
-- 데이터 범위로 샤드 배정: Shard1(1~100만), Shard2(100만~200만)
-- PostgreSQL Range Partition (시계열 데이터에 적합)
CREATE TABLE orders (
    id BIGSERIAL, created_at TIMESTAMPTZ NOT NULL,
    user_id BIGINT NOT NULL, amount DECIMAL(10,2)
) PARTITION BY RANGE (created_at);

CREATE TABLE orders_2025_01 PARTITION OF orders
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

| 장점 | 단점 |
|------|------|
| 범위 쿼리 효율적, 시계열에 적합 | Hot Shard 위험 (최신 샤드에 쓰기 집중) |
| 구현이 직관적 | 데이터 불균형, Rebalancing 어려움 |

### Hash-based Sharding

```
shard_id = hash(shard_key) % num_shards
-- user_id=12345 -> hash(12345) % 4 = 1 -> Shard 1
```

| 장점 | 단점 |
|------|------|
| 균등 분배, Hot Shard 방지 | 범위 쿼리 비효율 (모든 샤드 스캔) |
| 구현 단순 | 샤드 추가 시 대규모 재배치 (Consistent Hashing으로 해결) |

#### Consistent Hashing

샤드 추가/제거 시 최소한의 데이터만 이동시키는 기법이다. Hash Ring 기반으로 인접 샤드의 데이터만 이동한다. DynamoDB, Cassandra가 사용하며, 노드 추가/제거 시 K/N 비율의 키만 재배치된다.

```
기존 Hash: hash(key) % N  -> 샤드 변경 시 대부분 데이터 재배치
Consistent Hashing: Hash Ring -> 인접 구간 데이터만 이동
새 샤드 추가 시: 전체가 아닌 해당 구간의 키만 이전
```

### Directory-based Sharding

```sql
-- Lookup 테이블로 데이터 위치 관리 (유연한 매핑)
CREATE TABLE shard_directory (
    tenant_id BIGINT PRIMARY KEY,
    shard_id INT NOT NULL, shard_host VARCHAR(255) NOT NULL
);
-- 유명 계정(Hot Key)은 전용 샤드로 격리 가능
INSERT INTO shard_directory VALUES (999, 5, 'db-shard-vip.internal');
```

| 장점 | 단점 |
|------|------|
| 유연한 매핑, Hot Key 격리 가능 | Lookup 테이블이 SPOF, 캐싱 필요 |

---

## Shard Key 선택 (CRITICAL)

### 선택 기준

| 기준 | 설명 | 중요도 |
|------|------|--------|
| **높은 카디널리티** | 고유 값이 충분히 많아야 함 (샤드 수 x 100 이상) | 필수 |
| **균등 분배** | 데이터가 특정 샤드에 몰리지 않아야 함 | 필수 |
| **쿼리 패턴 일치** | 자주 사용하는 WHERE 조건과 일치 | 필수 |
| **불변성** | 한번 결정되면 변경되지 않는 값 | 권장 |
| **JOIN 최적화** | 관련 테이블이 같은 샤드에 위치 (Co-location) | 권장 |

### 좋은 Shard Key vs 나쁜 Shard Key

```
좋은 예: tenant_id (멀티테넌트 격리), user_id (균등 분배), order_id (고유값)
나쁜 예: status (2개값), country (편중), created_at (단조증가), boolean (2개값)
```

### Compound Shard Key

단일 키의 한계(낮은 카디널리티, 편중)를 극복하기 위해 복합 키를 사용한다.

```sql
-- shard_id = hash(region + user_id) % num_shards
-- MongoDB: sh.shardCollection("mydb.orders", {"region":1, "user_id":1})
```

### Co-location 원칙

**IMPORTANT**: 관련 테이블은 동일 Shard Key를 사용하여 같은 샤드에 배치한다. users, orders 테이블을 tenant_id로 샤딩하면 같은 샤드에서 Local JOIN이 가능하다. 변경이 적은 공통 테이블(products 등)은 Reference Table로 모든 샤드에 복제한다.

---

## 구현 도구

### PostgreSQL + Citus

```sql
-- Citus 설치 및 분산 테이블 생성
CREATE EXTENSION citus;
SELECT citus_set_coordinator_host('coord.internal', 5432);
SELECT * FROM citus_add_node('worker-1.internal', 5432);
SELECT * FROM citus_add_node('worker-2.internal', 5432);

-- 분산 테이블 (Hash Sharding, tenant_id 기준)
CREATE TABLE orders (
    id BIGSERIAL, tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL, amount DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_distributed_table('orders', 'tenant_id');

-- 관련 테이블 Co-location (같은 키로 분산)
CREATE TABLE order_items (
    id BIGSERIAL, tenant_id BIGINT NOT NULL,
    order_id BIGINT NOT NULL, product_id BIGINT, quantity INT
);
SELECT create_distributed_table('order_items', 'tenant_id');

-- Reference Table (모든 Worker에 복제, Local JOIN 가능)
SELECT create_reference_table('products');

-- tenant_id 포함 쿼리 -> 단일 샤드 실행
SELECT o.id, p.name FROM orders o
JOIN order_items oi ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id
JOIN products p ON oi.product_id = p.id
WHERE o.tenant_id = 42;

-- 온라인 리밸런싱 (다운타임 없음)
SELECT rebalance_table_shards();
```

```yaml
# Citus Worker StatefulSet (K8s)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: citus-worker
spec:
  serviceName: citus-worker
  replicas: 3
  template:
    spec:
      containers:
        - name: postgres
          image: citusdata/citus:12.1
          ports: [{containerPort: 5432}]
          env:
            - name: POSTGRES_PASSWORD
              valueFrom: {secretKeyRef: {name: citus-secret, key: password}}
          resources:
            requests: {cpu: "1", memory: 4Gi}
            limits: {cpu: "4", memory: 16Gi}
  volumeClaimTemplates:
    - metadata: {name: citus-data}
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: gp3-encrypted
        resources: {requests: {storage: 100Gi}}
```

### MySQL + Vitess

```
아키텍처: App -> vtgate(쿼리 라우터) -> vttablet(MySQL 프록시) -> MySQL
vtgate: Stateless, 수평 확장 가능 / vttablet: Shard당 1개
```

```json
// VSchema 설정 (user_id 기준 xxhash 샤딩)
{
  "sharded": true,
  "vindexes": { "xxhash": { "type": "xxhash" } },
  "tables": {
    "users": {
      "column_vindexes": [{"column": "user_id", "name": "xxhash"}],
      "auto_increment": {"column": "user_id", "sequence": "user_seq"}
    },
    "orders": {
      "column_vindexes": [{"column": "user_id", "name": "xxhash"}],
      "auto_increment": {"column": "order_id", "sequence": "order_seq"}
    }
  }
}
```

```yaml
# Vitess K8s 배포 (Operator)
# helm install vitess-operator planetscale/vitess-operator -n vitess
apiVersion: planetscale.com/v2
kind: VitessCluster
metadata:
  name: my-vitess
spec:
  cells:
    - name: zone1
      gateway: {replicas: 2, resources: {requests: {cpu: "1", memory: 1Gi}}}
  keyspaces:
    - name: commerce
      partitionings:
        - equal:
            parts: 4  # 4개 샤드
            shardTemplate:
              tabletPools:
                - cell: zone1
                  type: replica
                  replicas: 3  # Primary 1 + Replica 2
                  mysqld: {resources: {requests: {cpu: "2", memory: 4Gi}}}
                  dataVolumeClaimTemplate:
                    storageClassName: gp3-encrypted
                    resources: {requests: {storage: 100Gi}}
```

---

## Resharding (리샤딩)

### 필요 시점

단일 샤드 용량 80% 이상, 특정 샤드 CPU/IO 지속 포화, p99 레이턴시 증가, 데이터 증가율 급등 시 리샤딩을 수행한다.

### 온라인 리샤딩 전략

```
1. Shadow Copy (Vitess/Citus 지원)
   ┌──────────┐     ┌──────────┐
   │ Shard 1  │ ──> │ Shard 1a │ (Binlog/WAL 동기화)
   │ (기존)   │ ──> │ Shard 1b │ (검증 후 트래픽 전환, 수 초 read-only)
   └──────────┘     └──────────┘

2. Vitess Resharding
   $ vtctlclient Reshard -- --source_shards '0' --target_shards '-80,80-' \
       Create commerce.reshard1
   $ vtctlclient Reshard -- SwitchTraffic commerce.reshard1

3. Citus: SELECT rebalance_table_shards();  -- 온라인, 다운타임 없음
```

### 다운타임 최소화

- 사전 새 샤드 프로비저닝 완료
- Binlog/WAL 기반 실시간 동기화 + Checksum 검증 후에만 전환
- 롤백 계획 수립 (기존 샤드 즉시 복구 가능)
- Blue/Green 방식 점진적 전환

## Cross-Shard 쿼리

### JOIN 제약사항

```sql
-- 같은 Shard Key로 분산된 테이블 간 JOIN -> Local 실행
SELECT u.name, o.amount FROM users u JOIN orders o ON u.user_id = o.user_id
WHERE u.user_id = 42;

-- Reference Table JOIN -> Local 실행
SELECT o.id, p.name FROM orders o JOIN products p ON o.product_id = p.id;

-- Shard Key 아닌 컬럼 JOIN -> 모든 샤드 스캔 (회피할 것)
```

### Scatter-Gather 패턴

```
[Router] -> 동일 쿼리를 S1, S2, S3에 전송
         -> 각 샤드 결과 반환
[Aggregator] -> 결과 병합 (UNION, SUM, ORDER BY)
```

- COUNT/SUM: 각 샤드 결과를 합산
- ORDER BY + LIMIT: 각 샤드에서 Top-K 반환 후 최종 정렬
- Shard Key 필터를 포함하여 단일 샤드 쿼리로 전환 권장

### Global Table (Reference Table)

```sql
-- Citus: 변경 적고 모든 샤드에서 JOIN 필요한 테이블
SELECT create_reference_table('countries');
SELECT create_reference_table('currencies');
-- 모든 Worker에 전체 복사, Local JOIN 가능. 대용량 변경 잦은 테이블에는 부적합
```

---

## Read Replica 전략

### Primary-Replica 구성

```
[Write] ──> [Primary DB]
                │
         ┌──────┼──────┐  (비동기 복제)
     [Replica1] [Replica2] [Replica3]
         └──────┼──────┘
[Read] ─────────┘  (Load Balancer로 분배)
```

### Spring Boot Read/Write 분리

```java
// 1. DataSource 라우팅 (@Transactional readOnly 여부로 결정)
public class ReadWriteRoutingDataSource extends AbstractRoutingDataSource {
    @Override
    protected Object determineCurrentLookupKey() {
        return TransactionSynchronizationManager
            .isCurrentTransactionReadOnly() ? "replica" : "primary";
    }
}

// 2. 설정: LazyConnectionDataSourceProxy로 트랜잭션 속성 결정 후 연결
@Configuration
public class DataSourceConfig {
    @Bean
    public DataSource routingDataSource(
            @Qualifier("primaryDataSource") DataSource primary,
            @Qualifier("replicaDataSource") DataSource replica) {
        ReadWriteRoutingDataSource routing = new ReadWriteRoutingDataSource();
        Map<Object, Object> targets = Map.of("primary", primary, "replica", replica);
        routing.setTargetDataSources(targets);
        routing.setDefaultTargetDataSource(primary);
        return new LazyConnectionDataSourceProxy(routing);
    }
}

// 3. 서비스: 쓰기 -> Primary, 읽기 -> Replica
@Service
public class OrderService {
    @Transactional
    public Order createOrder(OrderRequest req) { return orderRepository.save(new Order(req)); }

    @Transactional(readOnly = true)  // Replica로 라우팅
    public List<Order> getOrdersByUser(Long userId) { return orderRepository.findByUserId(userId); }
}
```

```yaml
# application.yml
spring:
  datasource:
    primary:
      url: jdbc:postgresql://primary-db:5432/mydb
      hikari: {maximum-pool-size: 20}
    replica:
      url: jdbc:postgresql://replica-db:5432/mydb
      hikari: {maximum-pool-size: 40}  # 읽기 많으므로 풀 크게
```

### Replication Lag 처리

- 동기 복제: 0ms (성능 비용), 비동기: 보통 10~100ms, 부하 시 수 초
- 쓰기 직후 읽기 필요 시 `@Transactional` (readOnly=false)로 Primary 강제 사용
- Write-After-Read 일관성이 필요한 로직은 같은 트랜잭션에서 처리

---

## Hot Shard 문제 해결

| 원인 | 증상 | 해결 |
|------|------|------|
| 단조 증가 키 | 최신 샤드에 쓰기 집중 | Hash Sharding 적용 |
| 인기 계정 (Celebrity) | 특정 샤드 CPU 포화 | 전용 샤드 격리 (Directory) |
| 시간대별 편중 | 피크 시 특정 샤드 과부하 | Compound Key (region+time) |
| 글로벌 카운터/Lock | 단일 행에 쓰기 집중 | Sharded Counter / CRDT |
| 잘못된 Shard Key | 카디널리티 부족으로 편중 | Shard Key 재설계 + 리샤딩 |

### 해결 전략 상세

```
1. 캐싱 (읽기 Hot Shard)
   Application -> Redis/Memcached -> DB (캐시 미스 시만 접근)

2. Sharded Counter (쓰기 Hot Shard)
   -- 단일 카운터 대신 N개로 분산, total = SUM(shard_1..N)
   UPDATE counters SET value = value + 1
   WHERE id = ? AND shard = (random() * 10)::int;

3. Request Coalescing (Discord 방식)
   -- 동일 키 동시 요청을 하나로 합침 + Consistent Hash 라우팅

4. 동적 샤드 분할
   -- 과부하 샤드 자동 감지 -> 2개로 분할 (Vitess 지원)
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| 샤딩을 첫 번째 선택으로 | 불필요한 복잡도 | 인덱스->캐시->Replica->파티셔닝->샤딩 순서 |
| 낮은 카디널리티 Shard Key | 데이터 편중 | 샤드 수 x100 이상 고유값 보장 |
| Cross-Shard JOIN 남용 | 레이턴시 폭증 | Co-location, Reference Table |
| Shard Key 없는 쿼리 | Scatter-Gather | 주요 쿼리에 Shard Key 필터 포함 |
| 트랜잭션 경계 무시 | 데이터 불일치 | Saga 패턴, 단일 샤드 설계 |
| 글로벌 Auto Increment | 시퀀스 병목 | UUID v7, Snowflake ID |
| 리샤딩 계획 없이 시작 | 확장 불가 | 논리 샤드 >> 물리 노드 (10~100배) |
| Replication Lag 무시 | 읽기 불일치 | Read-Your-Write (Primary 강제) |

---

## 체크리스트

### 샤딩 도입 전

```
[ ] 인덱스 최적화를 먼저 수행했는가?
[ ] 캐싱 레이어 (Redis)를 적용했는가?
[ ] Read Replica로 읽기 부하를 분산했는가?
[ ] 파티셔닝으로 충분하지 않은지 확인했는가?
[ ] 예상 데이터 규모가 단일 인스턴스 한계를 넘는가?
```

### Shard Key 설계

```
[ ] 카디널리티가 충분히 높은가? (샤드 수 x 100 이상)
[ ] 데이터가 균등하게 분배되는가?
[ ] 주요 쿼리 패턴과 일치하는가?
[ ] 값이 불변인가? (변경 시 샤드 이동 필요)
[ ] 관련 테이블에 동일 Shard Key를 적용했는가? (Co-location)
```

### 운영 준비

```
[ ] Cross-Shard 쿼리를 최소화했는가?
[ ] Reference Table을 식별하고 설정했는가?
[ ] 분산 트랜잭션 전략을 수립했는가? (2PC / Saga)
[ ] 리샤딩 절차와 자동화를 준비했는가?
[ ] 모니터링: 샤드별 CPU, 디스크, 쿼리 레이턴시
[ ] ID 생성 전략 (UUID v7, Snowflake)
[ ] Replication Lag 모니터링과 대응 전략
[ ] 롤백 계획 수립
```

---

## 참조 스킬

- `/database` - 인덱스 최적화, N+1 해결, 쿼리 성능
- `/msa-cqrs-eventsourcing` - CQRS, Event Sourcing, Saga 패턴
- `/high-traffic-design` - 대규모 트래픽 아키텍처 설계
- `/database-migration` - 스키마 마이그레이션, 무중단 배포
