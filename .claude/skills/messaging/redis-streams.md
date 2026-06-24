---
name: redis-streams
description: "Redis Streams 가이드 — Redis 8.x Streams 기반 메시지 스트리밍, Consumer Group, PEL 관리, K8s 배포 Use when working with messaging 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Redis Streams 가이드

Redis 8.x Streams 기반 메시지 스트리밍, Consumer Group, PEL 관리, K8s 배포

## Quick Reference (결정 트리)

```
메시지 스트리밍 기술 선택?
    │
    ├─ 대규모 이벤트 소싱 ──────> Kafka (파티션 기반 수평 확장)
    ├─ 경량 이벤트 큐 ──────────> Redis Streams (낮은 지연, 간단한 운영)
    ├─ 단순 Pub/Sub ───────────> Redis Pub/Sub (메시지 유실 허용)
    └─ 작업 큐 ─────────────────> Redis Streams + Consumer Group

Consumer Group 전략?
    │
    ├─ 최소 1회 처리 ──────────> XREADGROUP + XACK (at-least-once)
    ├─ 장애 복구 ───────────────> XCLAIM + PEL 모니터링
    └─ 정확히 1회 처리 ────────> XREADGROUP + 외부 idempotency (DB unique key)

Stream 트리밍?
    │
    ├─ 고정 크기 ───────────────> MAXLEN ~ N (근사 트리밍, 성능 우선)
    ├─ 시간 기반 ───────────────> MINID ~ <timestamp> (Redis 6.2+)
    └─ 수동 관리 ───────────────> XTRIM 주기적 실행
```

---

## CRITICAL: Redis Streams 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                  Redis Streams Architecture                    │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Producer ─── XADD ──────> Stream (orders)                    │
│                                │                               │
│                       ┌────────┴────────┐                     │
│                       │  Entry Log       │                     │
│                       │  1718000000-0    │                     │
│                       │  1718000001-0    │                     │
│                       └────────┬────────┘                     │
│                                │                               │
│                       ┌────────┴────────┐                     │
│                       │ Consumer Group   │                     │
│                       │ "order-workers"  │                     │
│                       │ PEL (Pending):   │                     │
│                       │  C1: [0001-0]    │                     │
│                       │  C2: [0000-0]    │                     │
│                       └────────┬────────┘                     │
│                                │                               │
│                  ┌─────────────┼──────────┐                   │
│                [C1]          [C2]        [C3]                 │
│              XREADGROUP    XREADGROUP  XREADGROUP             │
│                + XACK       + XACK      + XACK               │
│                                                                │
└──────────────────────────────────────────────────────────────┘

핵심: Stream = append-only log, Consumer Group = 메시지 분산 전달,
PEL = ACK 안 된 메시지 목록, Entry ID = <밀리초>-<시퀀스>
```

### Redis Streams vs Kafka 비교

| 항목 | Redis Streams | Kafka |
|------|--------------|-------|
| **지연시간** | sub-ms ~ 수 ms | 수 ms ~ 수십 ms |
| **처리량** | 수십만 msg/s (단일 노드) | 수백만 msg/s (클러스터) |
| **내구성** | AOF/RDB (메모리 제약) | 디스크 기반 (무제한 보존) |
| **파티셔닝** | 수동 (여러 Stream key) | 네이티브 파티션 지원 |
| **Exactly-once** | 외부 구현 필요 | 트랜잭션 네이티브 지원 |
| **운영 복잡도** | 낮음 | 높음 (ZooKeeper/KRaft) |
| **적합 시나리오** | 경량 이벤트, 실시간 알림 | 대규모 이벤트 소싱, 로그 |

---

## CRITICAL: Consumer Group 핵심 명령어

```
┌───────────────────────────────────────────────────────┐
│             Consumer Group Lifecycle                   │
├───────────────────────────────────────────────────────┤
│  1. XGROUP CREATE stream group $ MKSTREAM              │
│     └─ 그룹 생성 ($ = 신규만, 0 = 처음부터)            │
│  2. XADD stream * field value                          │
│     └─ 메시지 발행 (* = 자동 ID)                       │
│  3. XREADGROUP GROUP g consumer COUNT n BLOCK ms       │
│     STREAMS stream >                                   │
│     └─ 신규 메시지 읽기 (> = 새 메시지만)               │
│  4. XACK stream group id                               │
│     └─ 처리 완료 (PEL에서 제거)                        │
│  5. XPENDING stream group - + count                    │
│     └─ 미확인 메시지 조회                               │
│  6. XCLAIM stream group consumer min-idle-time id      │
│     └─ 타임아웃 메시지를 다른 Consumer에게 재할당       │
│  7. XAUTOCLAIM stream group consumer min-idle start    │
│     COUNT n                                            │
│     └─ 자동 유휴 메시지 클레임 (Redis 6.2+)            │
└───────────────────────────────────────────────────────┘
```

### PEL (Pending Entry List) 관리 전략

```
장애 복구 흐름:
    ├─ idle time > 임계값 ──> XCLAIM으로 재할당
    ├─ 전달 횟수 > 3회 ────> Dead Letter Stream으로 이동
    └─ Consumer 사망 ──────> XAUTOCLAIM으로 자동 복구
```

---

## Go 구현 (go-redis v9)

### Producer

```go
package stream

import (
    "context"
    "fmt"
    "github.com/redis/go-redis/v9"
)

type StreamProducer struct {
    client    *redis.Client
    streamKey string
    maxLen    int64
}

// Publish는 MAXLEN ~ (근사 트리밍)으로 메시지를 추가한다.
func (p *StreamProducer) Publish(ctx context.Context, fields map[string]interface{}) (string, error) {
    return p.client.XAdd(ctx, &redis.XAddArgs{
        Stream: p.streamKey,
        MaxLen: p.maxLen,
        Approx: true,  // ~ 근사 트리밍: 성능 최적화
        ID:     "*",
        Values: fields,
    }).Result()
}
```

### Consumer (Consumer Group + PEL + DLQ)

```go
package stream

import (
    "context"
    "log/slog"
    "time"
    "github.com/redis/go-redis/v9"
)

type MessageHandler func(ctx context.Context, msg redis.XMessage) error

type StreamConsumer struct {
    client       *redis.Client
    streamKey    string
    groupName    string
    consumerName string
    handler      MessageHandler
    batchSize    int64
    blockTime    time.Duration
    claimMinIdle time.Duration
    maxRetries   int
    dlqStream    string
}

// EnsureGroup은 Consumer Group이 없으면 생성한다.
func (c *StreamConsumer) EnsureGroup(ctx context.Context) error {
    err := c.client.XGroupCreateMkStream(ctx, c.streamKey, c.groupName, "0").Err()
    if err != nil && err.Error() != "BUSYGROUP Consumer Group name already exists" {
        return err
    }
    return nil
}

// Run은 메시지 소비 루프를 시작한다. ctx 취소 시 graceful 종료.
func (c *StreamConsumer) Run(ctx context.Context) error {
    if err := c.EnsureGroup(ctx); err != nil {
        return err
    }
    // 1단계: 미처리 pending 메시지 복구
    c.processPending(ctx)
    // 2단계: 신규 메시지 소비 루프
    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        default:
        }
        streams, err := c.client.XReadGroup(ctx, &redis.XReadGroupArgs{
            Group:    c.groupName,
            Consumer: c.consumerName,
            Streams:  []string{c.streamKey, ">"},  // ">" = 신규 메시지만
            Count:    c.batchSize,
            Block:    c.blockTime,
        }).Result()
        if err == redis.Nil {
            continue
        }
        if err != nil {
            time.Sleep(time.Second)
            continue
        }
        for _, s := range streams {
            for _, msg := range s.Messages {
                if err := c.handler(ctx, msg); err != nil {
                    slog.Error("처리 실패", "id", msg.ID, "error", err)
                    continue // ACK 안 함 → PEL에 남아 재처리 대상
                }
                c.client.XAck(ctx, c.streamKey, c.groupName, msg.ID)
            }
        }
    }
}

// processPending은 재시작 시 PEL에 남은 메시지를 XCLAIM으로 복구한다.
func (c *StreamConsumer) processPending(ctx context.Context) {
    pending, _ := c.client.XPendingExt(ctx, &redis.XPendingExtArgs{
        Stream: c.streamKey, Group: c.groupName,
        Start: "-", End: "+", Count: c.batchSize,
    }).Result()

    for _, p := range pending {
        if int(p.RetryCount) > c.maxRetries {
            c.moveToDLQ(ctx, p.ID)
            c.client.XAck(ctx, c.streamKey, c.groupName, p.ID)
            continue
        }
        msgs, _ := c.client.XClaim(ctx, &redis.XClaimArgs{
            Stream: c.streamKey, Group: c.groupName,
            Consumer: c.consumerName, MinIdle: c.claimMinIdle,
            Messages: []string{p.ID},
        }).Result()
        for _, msg := range msgs {
            if c.handler(ctx, msg) == nil {
                c.client.XAck(ctx, c.streamKey, c.groupName, msg.ID)
            }
        }
    }
}

// moveToDLQ는 재시도 초과 메시지를 Dead Letter Stream으로 이동한다.
func (c *StreamConsumer) moveToDLQ(ctx context.Context, msgID string) {
    msgs, _ := c.client.XRangeN(ctx, c.streamKey, msgID, msgID, 1).Result()
    if len(msgs) == 0 {
        return
    }
    msgs[0].Values["original_id"] = msgID
    msgs[0].Values["failed_at"] = time.Now().UnixMilli()
    c.client.XAdd(ctx, &redis.XAddArgs{
        Stream: c.dlqStream, MaxLen: 10000, Approx: true,
        ID: "*", Values: msgs[0].Values,
    })
}
```

### 사용 예시

```go
func main() {
    rdb := redis.NewClient(&redis.Options{Addr: "redis:6379", Password: os.Getenv("REDIS_PASSWORD")})
    ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer cancel()

    producer := &StreamProducer{client: rdb, streamKey: "orders", maxLen: 100000}
    producer.Publish(ctx, map[string]interface{}{"order_id": "ord-123", "action": "created"})

    consumer := &StreamConsumer{
        client: rdb, streamKey: "orders", groupName: "order-workers",
        consumerName: "worker-" + os.Getenv("HOSTNAME"),
        handler: func(ctx context.Context, msg redis.XMessage) error {
            slog.Info("주문 처리", "id", msg.ID, "order_id", msg.Values["order_id"])
            return nil
        },
        batchSize: 10, blockTime: 5 * time.Second,
        claimMinIdle: 30 * time.Second, maxRetries: 3, dlqStream: "orders:dlq",
    }
    consumer.Run(ctx)
}
```

---

## Spring Data Redis 구현

### StreamListener 구현

```java
// build.gradle: implementation 'org.springframework.boot:spring-boot-starter-data-redis'

@Configuration
public class RedisStreamConfig {
    @Value("${stream.key:orders}") private String streamKey;
    @Value("${stream.group:order-workers}") private String groupName;

    @Bean
    public Subscription orderStreamSubscription(
            RedisConnectionFactory factory, OrderStreamListener listener) {
        // Consumer Group 생성
        try {
            StringRedisTemplate tpl = new StringRedisTemplate(factory);
            tpl.opsForStream().createGroup(streamKey, ReadOffset.from("0"), groupName);
        } catch (Exception ignored) {} // 이미 존재하면 무시

        var options = StreamMessageListenerContainer
            .StreamMessageListenerContainerOptions.builder()
            .pollTimeout(Duration.ofSeconds(2)).batchSize(10)
            .targetType(String.class).build();
        var container = StreamMessageListenerContainer.create(factory, options);
        String consumerName = "consumer-" + UUID.randomUUID().toString().substring(0, 8);
        Subscription sub = container.receive(
            Consumer.from(groupName, consumerName),
            StreamOffset.create(streamKey, ReadOffset.lastConsumed()), listener);
        container.start();
        return sub;
    }
}

@Component @Slf4j
public class OrderStreamListener
        implements StreamListener<String, MapRecord<String, String, String>> {
    private final StringRedisTemplate redisTemplate;
    @Value("${stream.key:orders}") private String streamKey;
    @Value("${stream.group:order-workers}") private String groupName;

    public OrderStreamListener(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    @Override
    public void onMessage(MapRecord<String, String, String> message) {
        try {
            log.info("수신: id={}, order={}", message.getId(),
                     message.getValue().get("order_id"));
            processOrder(message.getValue());
            // 처리 성공 시 ACK
            redisTemplate.opsForStream().acknowledge(streamKey, groupName, message.getId());
        } catch (Exception e) {
            log.error("처리 실패: {}", message.getId(), e);
            // ACK 안 함 → PEL에 남아 재처리 대상
        }
    }
    private void processOrder(Map<String, String> data) { /* 비즈니스 로직 */ }
}
```

### Producer (Spring)

```java
@Service @RequiredArgsConstructor
public class OrderStreamProducer {
    private final StringRedisTemplate redisTemplate;
    @Value("${stream.key:orders}") private String streamKey;

    public RecordId publish(String orderId, String action, String payload) {
        StringRecord record = StreamRecords.string(Map.of(
            "order_id", orderId, "action", action, "payload", payload,
            "ts", String.valueOf(System.currentTimeMillis())
        )).withStreamKey(streamKey);
        return redisTemplate.opsForStream().add(record);
    }
}
```

---

## K8s 배포

### Redis (Bitnami Helm)

```bash
helm install redis bitnami/redis --namespace redis --create-namespace \
  --set architecture=replication --set replica.replicaCount=3 \
  --set sentinel.enabled=true --set sentinel.quorum=2 \
  --set master.persistence.size=10Gi --set master.persistence.storageClass=gp3 \
  --set master.resources.requests.memory=1Gi --set auth.password=<PASSWORD>
```

### Redis Operator (OpsTree) CRD

```yaml
apiVersion: redis.redis.opstreelabs.in/v1beta2
kind: RedisReplication
metadata:
  name: redis-streams
  namespace: redis
spec:
  clusterSize: 3
  kubernetesConfig:
    image: redis:8.0-alpine
    resources:
      requests: { cpu: 500m, memory: 1Gi }
      limits: { cpu: "1", memory: 2Gi }
  storage:
    volumeClaimTemplate:
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: gp3
        resources:
          requests: { storage: 10Gi }
  redisConfig:
    additionalRedisConfig: |
      maxmemory 1gb
      maxmemory-policy noeviction
      stream-node-max-bytes 4096
      stream-node-max-entries 100
```

### Consumer Deployment + KEDA Scaler

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-stream-consumer
spec:
  replicas: 1  # KEDA가 관리
  selector:
    matchLabels: { app: order-stream-consumer }
  template:
    metadata:
      labels: { app: order-stream-consumer }
    spec:
      terminationGracePeriodSeconds: 30
      containers:
        - name: consumer
          image: order-stream-consumer:latest
          env:
            - name: REDIS_ADDR
              value: "redis-streams-master.redis:6379"
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef: { name: redis-secret, key: password }
            - name: CONSUMER_NAME
              valueFrom:
                fieldRef: { fieldPath: metadata.name }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits: { cpu: 500m, memory: 256Mi }
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-stream-scaler
spec:
  scaleTargetRef:
    name: order-stream-consumer
  pollingInterval: 15
  cooldownPeriod: 30
  minReplicaCount: 1
  maxReplicaCount: 10
  triggers:
    - type: redis-streams
      metadata:
        addressFromEnv: REDIS_ADDR
        passwordFromEnv: REDIS_PASSWORD
        stream: orders
        consumerGroup: order-workers
        pendingEntriesCount: "50"  # pending > 50이면 스케일업
        enableTLS: "false"
        databaseIndex: "0"
```

---

## MAXLEN 트리밍 전략

```
XADD 시 트리밍 (권장):
    ├─ XADD stream MAXLEN ~ 100000 * field value
    │   └─ 근사 트리밍: radix tree 노드 단위 정리, 성능 좋음
    ├─ XADD stream MAXLEN 100000 * field value
    │   └─ 정확한 트리밍: 정확히 N개 유지, 성능 영향 있음
    └─ XADD stream MINID ~ <timestamp>-0 * field value
        └─ 시간 기반: 특정 시점 이전 메시지 제거 (Redis 6.2+)
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| XREAD만 사용 | 모든 Consumer가 전체 메시지 수신 | XREADGROUP 사용 |
| XACK 누락 | PEL 무한 증가, 메모리 누수 | 처리 후 반드시 XACK |
| MAXLEN 미설정 | Stream 무한 증가, OOM | XADD 시 MAXLEN ~ N |
| BLOCK 0 사용 | graceful shutdown 불가 | BLOCK 2000~5000ms |
| Consumer 이름 고정 | Pod 간 이름 충돌 | Pod 이름/UUID 사용 |
| PEL 모니터링 안 함 | 장애 메시지 방치 | XCLAIM/XAUTOCLAIM 주기 실행 |
| DLQ 없음 | 무한 재시도 | 재시도 초과 시 DLQ 이동 |
| noeviction 미설정 | Stream 데이터 삭제됨 | maxmemory-policy noeviction |
| 큰 메시지 저장 | 메모리 낭비 | 참조 ID만, 본문은 외부 저장 |

---

## 체크리스트

### Stream 설정
- [ ] MAXLEN 또는 MINID 트리밍 설정
- [ ] maxmemory-policy noeviction 설정
- [ ] stream-node-max-bytes / stream-node-max-entries 튜닝
- [ ] 메시지 크기 최소화 (참조 패턴)

### Consumer Group
- [ ] XGROUP CREATE MKSTREAM으로 그룹 생성
- [ ] Consumer 이름에 Pod 이름 또는 UUID 사용
- [ ] XREADGROUP + XACK 쌍으로 at-least-once 보장
- [ ] 시작 시 pending 메시지 먼저 처리

### PEL / 장애 복구
- [ ] XPENDING으로 미처리 메시지 모니터링
- [ ] XCLAIM 또는 XAUTOCLAIM으로 장애 복구
- [ ] 재시도 횟수 초과 시 DLQ로 이동
- [ ] DLQ 모니터링 및 알림

### K8s 배포
- [ ] Redis Sentinel 또는 Replication 구성 (HA)
- [ ] KEDA redis-streams scaler 설정
- [ ] pendingEntriesCount 임계값 적절히 설정
- [ ] terminationGracePeriodSeconds 설정 (graceful shutdown)
- [ ] Redis 비밀번호 Secret으로 관리

**관련 skill**: `/kafka` (대규모 이벤트 스트리밍), `/kafka-patterns` (Producer/Consumer 패턴, KEDA), `/distributed-lock` (Redis 분산 락)
