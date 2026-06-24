---
name: nats-messaging
description: "NATS 메시징 가이드 — NATS v2.10+ Core NATS, JetStream, Key-Value Store, Object Store, K8s 운영 Use when working with messaging 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# NATS 메시징 가이드

NATS v2.10+ Core NATS, JetStream, Key-Value Store, Object Store, K8s 운영

## Quick Reference (결정 트리)

```
메시징 패턴?
    ├─ 실시간 fire-and-forget ──> Core NATS (Pub/Sub)
    ├─ 요청-응답 (동기) ────────> Core NATS (Request-Reply)
    ├─ 메시지 보장 필요 ────────> JetStream
    ├─ 설정/상태 공유 ──────────> KV Store
    └─ 대용량 파일 저장 ────────> Object Store

JetStream Retention?
    ├─ 모든 메시지 보관 ────────> Limits (기본값)
    ├─ Consumer 처리 후 삭제 ───> Interest
    └─ 작업 큐 (단일 ack) ─────> WorkQueue

Consumer?
    ├─ 수평 확장 + 흐름 제어 ───> Pull Consumer (권장)
    ├─ 간단한 순차 재생 ────────> Ordered Push Consumer
    ├─ 상태 유지 필요 ──────────> Durable Consumer
    └─ 임시 처리 ───────────────> Ephemeral Consumer
```

---

## NATS vs Kafka vs RabbitMQ 비교

| 항목 | NATS + JetStream | Apache Kafka | RabbitMQ |
|------|------------------|--------------|----------|
| **지연시간** | < 1ms (Core), 1-5ms (JS) | 10-50ms (배치) | 1-10ms |
| **처리량** | 200K-400K msg/s (JS) | 500K-1M+ msg/s | 50K-100K msg/s |
| **운영 복잡도** | 낮음 (단일 바이너리) | 높음 (ZK/KRaft) | 중간 |
| **메모리** | 낮음 | 높음 | 중간 |
| **KV/Obj Store** | 내장 | 별도 시스템 | 없음 |
| **Multi-tenancy** | 내장 (Accounts) | Topic ACL | Vhost |
| **적합 사례** | MSA, IoT, Edge | 대용량 스트리밍/로그 | 전통적 메시지 큐 |

**선택 기준**: 경량 + 다기능 = NATS, 대용량 로그/스트리밍 = Kafka, AMQP 호환 = RabbitMQ

---

## Core NATS 패턴

```go
// Pub/Sub (1:N 브로드캐스트)
nc, _ := nats.Connect(nats.DefaultURL)
defer nc.Drain()
nc.Publish("orders.created", []byte(`{"id":"order-123"}`))
nc.Subscribe("orders.created", func(msg *nats.Msg) {
    log.Printf("received: %s", string(msg.Data))
})

// Request-Reply (동기 요청)
nc.Subscribe("user.lookup", func(msg *nats.Msg) {
    msg.Respond([]byte(lookupUser(string(msg.Data))))
})
resp, _ := nc.Request("user.lookup", []byte("user-456"), 2*time.Second)

// Queue Groups (로드 밸런싱 - 동일 그룹 내 1개만 수신)
nc.QueueSubscribe("orders.process", "workers", func(msg *nats.Msg) {
    processOrder(msg.Data)
})
```

---

## JetStream

### Stream 생성

```go
js, _ := jetstream.New(nc)
ctx := context.Background()

stream, _ := js.CreateStream(ctx, jetstream.StreamConfig{
    Name:      "ORDERS",
    Subjects:  []string{"orders.>"},
    Storage:   jetstream.FileStorage,
    Retention: jetstream.LimitsPolicy,  // Limits | Interest | WorkQueue
    MaxAge:    7 * 24 * time.Hour,
    MaxBytes:  10 * 1024 * 1024 * 1024, // 10GB
    Replicas:  3,
    Discard:   jetstream.DiscardOld,
})

// 중복 방지 발행 (Exactly-Once)
js.Publish(ctx, "orders.created", data, jetstream.WithMsgID("order-123-v1"))
```

### Retention / Ack 정책

| Retention | 설명 | 용도 |
|-----------|------|------|
| **Limits** | 크기/시간/개수 한도까지 보관 | 이벤트 로그, 감사 |
| **Interest** | 모든 Consumer ack 후 삭제 | 다중 Consumer 파이프라인 |
| **WorkQueue** | 단일 Consumer ack 후 삭제 | 태스크 분배 |

| Ack 정책 | 설명 | 적합 사례 |
|----------|------|-----------|
| **AckExplicit** | 메시지별 명시적 ack (기본) | 프로덕션 워크로드 |
| **AckAll** | 마지막 ack 시 이전 모두 완료 | 벌크/배치 처리 |
| **AckNone** | ack 불필요 | 모니터링, 로그 수집 |

---

## Consumer 패턴

### Pull Consumer (권장)

```go
cons, _ := js.CreateOrUpdateConsumer(ctx, "ORDERS", jetstream.ConsumerConfig{
    Name:          "order-processor",
    Durable:       "order-processor",
    FilterSubject: "orders.created",
    AckPolicy:     jetstream.AckExplicitPolicy,
    AckWait:       30 * time.Second,
    MaxDeliver:    5,           // 최대 재전송
    MaxAckPending: 1000,        // 미처리 한도
})

// 배치 가져오기
msgs, _ := cons.Fetch(100, jetstream.FetchMaxWait(5*time.Second))
for msg := range msgs.Messages() {
    if err := processOrder(msg); err != nil {
        msg.NakWithDelay(5 * time.Second) // 지연 재전송
    } else {
        msg.DoubleAck(ctx) // Exactly-once Double Ack
    }
}

// 연속 소비
consumeCtx, _ := cons.Consume(func(msg jetstream.Msg) {
    if err := processOrder(msg); err != nil { msg.Nak(); return }
    msg.Ack()
})
defer consumeCtx.Stop()
```

### Push vs Pull 비교

| 항목 | Pull Consumer | Push Consumer |
|------|---------------|---------------|
| **흐름 제어** | 클라이언트 주도 | 서버 주도 |
| **수평 확장** | Fetch 경쟁으로 쉬움 | Queue Group 필요 |
| **배치 처리** | 네이티브 지원 | 불가 |
| **권장** | 신규 프로젝트 | 레거시 호환 |

---

## Key-Value Store

```go
kv, _ := js.CreateKeyValue(ctx, jetstream.KeyValueConfig{
    Bucket:  "user-sessions",
    TTL:     30 * time.Minute,
    History: 5,
    Replicas: 3,
    Storage: jetstream.MemoryStorage,
})

// CRUD
kv.Put(ctx, "session.user-123", []byte(`{"role":"admin"}`))
entry, _ := kv.Get(ctx, "session.user-123")

// CAS (낙관적 잠금)
kv.Update(ctx, "session.user-123", newValue, entry.Revision())

// Watch (변경 감지 - 와일드카드 지원)
watcher, _ := kv.Watch(ctx, "session.>")
for entry := range watcher.Updates() {
    if entry == nil { continue }
    switch entry.Operation() {
    case jetstream.KeyValuePut:
        log.Printf("updated: %s", entry.Key())
    case jetstream.KeyValueDelete:
        log.Printf("deleted: %s", entry.Key())
    }
}
```

**활용**: 세션 관리(TTL), 설정 배포(Watch), 서비스 디스커버리, Feature Flag, 분산 잠금(Create+TTL)

---

## Subject 설계 전략

```
패턴: <domain>.<entity>.<action>.<qualifier>

예시:
  orders.created              orders.payment.completed
  users.profile.updated       inventory.item-123.changed

와일드카드:
  *  단일 토큰 매칭    orders.*           → orders.created (1단계만)
  >  다중 토큰 매칭    orders.>           → orders.payment.completed (모든 하위)

권장사항:
  ✓ 최대 16 토큰, 256자 이내 / 영숫자, -, _ 사용
  ✓ 와일드카드 구독 우선 (개별 구독보다 효율적)
  ✗ 과도하게 깊은 계층 (> 8단계) / 초기부터 복잡한 설계
```

---

## Go 클라이언트 프로덕션 패턴

```go
nc, _ := nats.Connect(
    "nats://nats-1:4222,nats://nats-2:4222,nats://nats-3:4222",
    nats.Name("order-service"),
    nats.MaxReconnects(-1),
    nats.ReconnectWait(2*time.Second),
    nats.ReconnectBufSize(5*1024*1024),
    nats.DisconnectErrHandler(func(nc *nats.Conn, err error) {
        log.Printf("disconnected: %v", err)
    }),
    nats.ReconnectHandler(func(nc *nats.Conn) {
        log.Printf("reconnected to %s", nc.ConnectedUrl())
    }),
)
defer nc.Drain() // Close 대신 Drain 권장

// 서비스 프레임워크 (자동 디스커버리 + Queue Group)
svc, _ := micro.AddService(nc, micro.Config{
    Name: "order-service", Version: "1.0.0",
})
group := svc.AddGroup("orders")
group.AddEndpoint("create", micro.HandlerFunc(func(req micro.Request) {
    req.Respond(processOrder(req.Data()))
}))
```

---

## Spring Integration

```xml
<dependency>
    <groupId>io.nats</groupId>
    <artifactId>jnats</artifactId>
    <version>2.20.5</version>
</dependency>
```

```java
@Configuration
public class NatsConfig {
    @Bean
    public Connection natsConnection() throws Exception {
        return Nats.connect(new Options.Builder()
            .servers(new String[]{"nats://nats-1:4222","nats://nats-2:4222"})
            .maxReconnects(-1).reconnectWait(Duration.ofSeconds(2))
            .connectionListener((c, t) -> log.info("NATS: {}", t))
            .build());
    }
}

@Service
@RequiredArgsConstructor
public class OrderPublisher {
    private final Connection nc;
    public void publish(OrderEvent event) throws Exception {
        JetStream js = nc.jetStream();
        PublishOptions opts = PublishOptions.builder()
            .messageId(event.getId()).build();  // 중복 방지
        js.publish("orders.created", toBytes(event), opts);
    }
}

@Component
public class OrderConsumer {
    @PostConstruct
    public void start() throws Exception {
        JetStream js = nc.jetStream();
        var sub = js.subscribe("orders.created",
            PullSubscribeOptions.builder().durable("order-processor").build());
        executor.submit(() -> {
            while (!Thread.interrupted()) {
                for (Message msg : sub.fetch(100, Duration.ofSeconds(5))) {
                    try { process(msg.getData()); msg.ack(); }
                    catch (Exception e) { msg.nak(); }
                }
            }
        });
    }
}
```

---

## K8s 배포

### Helm Chart

```bash
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm install nats nats/nats -n nats-system --create-namespace \
  --set config.cluster.enabled=true \
  --set config.cluster.replicas=3 \
  --set config.jetstream.enabled=true \
  --set config.jetstream.fileStore.pvc.size=50Gi
```

```yaml
# values-production.yaml
config:
  cluster: { enabled: true, replicas: 3 }
  jetstream:
    enabled: true
    fileStore: { pvc: { size: 50Gi, storageClassName: gp3 } }
    memoryStore: { maxSize: 1Gi }
  monitor: { enabled: true, port: 8222 }
container:
  resources:
    requests: { cpu: 500m, memory: 1Gi }
    limits: { cpu: "2", memory: 4Gi }
  env:
    GOMEMLIMIT: "3GiB"  # 메모리 한도의 80-90%
podTemplate:
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule
podDisruptionBudget: { enabled: true, minAvailable: 2 }
```

**참고**: NATS Operator는 deprecated - Helm Chart가 공식 배포 방식

### KEDA 오토스케일링

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-processor-scaler
spec:
  scaleTargetRef:
    name: order-processor
  pollingInterval: 10
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
    - type: nats-jetstream
      metadata:
        natsServerMonitoringEndpoint: "nats.nats-system.svc:8222"
        account: "$G"
        stream: "ORDERS"
        consumer: "order-processor"
        lagThreshold: "100"
        activationLagThreshold: "10"
```

---

## 모니터링

### Prometheus Exporter

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nats-exporter
spec:
  template:
    spec:
      containers:
        - name: exporter
          image: natsio/prometheus-nats-exporter:latest
          args: ["-varz", "-connz", "-jsz=all", "http://nats.nats-system.svc:8222"]
          ports: [{ containerPort: 7777, name: metrics }]
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata: { name: nats-exporter }
spec:
  selector: { matchLabels: { app: nats-exporter } }
  endpoints: [{ port: metrics, interval: 15s }]
```

### 핵심 메트릭

| 메트릭 | 임계값 |
|--------|--------|
| `nats_server_cpu` | > 80% 경고 |
| `nats_server_mem` | > 85% 경고 |
| `nats_jetstream_consumer_num_pending` | > 1000 경고 |
| `nats_jetstream_consumer_num_ack_pending` | > MaxAckPending 80% |
| `nats_jetstream_stream_bytes` | > MaxBytes 80% |

**nats-surveyor**: 클러스터 전체 모니터링, Grafana 대시보드 `2279`(Server), `14725`(JetStream)

---

## Anti-Patterns

| Anti-Pattern | 문제 | 해결 |
|--------------|------|------|
| **무한 Stream** | 디스크 고갈 | MaxAge/MaxBytes/MaxMsgs 필수 |
| **Ack 누락** | 무한 재전송 | AckWait + MaxDeliver + DLQ |
| **Consumer >100K** | 서버 불안정 | Republish + Direct Get 대체 |
| **과도한 복제 (R=5)** | 쓰기 성능 저하 | 용도별: R=1(임시), R=3(기본) |
| **큰 메시지** | 네트워크 병목 | 참조만 전송 + Object Store |
| **Consumer Info 남용** | 서버 부하 | Fetch 메타데이터 활용 |
| **Fan-out 과다** | Core NATS 유실 | JetStream + Queue Group |
| **disjoint filter >300** | 인덱싱 오버헤드 | 필터 축소 또는 Stream 분리 |

### Dead Letter Queue

```go
// MaxDeliver 초과 시 Advisory 이벤트 구독 → DLQ로 이동
nc.Subscribe("$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.>", func(msg *nats.Msg) {
    js.Publish(ctx, "dlq.orders.failed", msg.Data)
})
```

---

## 체크리스트

- [ ] 홀수 노드 (3/5), GOMEMLIMIT 80-90%, Zone 분산, PDB
- [ ] Stream: Retention 선택, MaxAge/MaxBytes 한도, Replicas 설정
- [ ] Consumer: Pull 우선, AckWait+MaxDeliver, MaxAckPending(1K-10K), DLQ
- [ ] 클라이언트: MaxReconnects(-1), Drain(), 메시지 ID 중복 방지
- [ ] 모니터링: Prometheus Exporter, Consumer lag 알림, KEDA

**관련 Skills**: `/kafka` (대용량 스트리밍), `/kafka-patterns` (이벤트 패턴), `/k8s-helm` (Helm), `/monitoring-metrics` (Prometheus)

## 참고 레퍼런스

- [Saga_Pattern_with_NATS_Go](https://github.com/ChikenduHillary/Saga_Pattern_with_NATS_Go) -- Go + NATS JetStream Saga 패턴
- [go-microservices (NATS)](https://github.com/f4nt0md3v/go-microservices) -- Go + NATS Streaming + CockroachDB
- [Go + NATS + gRPC Clean Architecture](https://dev.to/aleksk1ng/go-nats-grpc-and-postgresql-clean-architecture-microservice-with-monitoring-and-tracing-2kka) -- 모니터링/트레이싱 포함
- [Building Distributed Systems with Go and NATS (O'Reilly)](https://www.oreilly.com/library/view/building-distributed-systems/9798868820892/) -- DDD + Hexagonal + Reactive
- [How to Use NATS in Go (2026)](https://oneuptime.com/blog/post/2026-01-07-go-nats/view) -- 2026년 최신 가이드
