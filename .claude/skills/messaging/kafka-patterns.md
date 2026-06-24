---
name: kafka-patterns
description: "Kafka Producer/Consumer 패턴 — Producer/Consumer 구현, KEDA 오토스케일링, 모니터링 Use when working with messaging 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Kafka Producer/Consumer 패턴

Producer/Consumer 구현, KEDA 오토스케일링, 모니터링

## Quick Reference

```
Producer 패턴?
    │
    ├─ 신뢰성 우선 ───────> acks=all, idempotence=true
    ├─ 처리량 우선 ───────> batch.size↑, linger.ms↑
    └─ 지연시간 우선 ────> batch.size↓, linger.ms=0

Consumer 패턴?
    │
    ├─ At-least-once ────> 수동 커밋, 처리 후 커밋
    ├─ At-most-once ─────> 자동 커밋 (메시지 유실 허용)
    └─ Exactly-once ─────> 트랜잭션 + idempotent consumer
```

---

## Producer 패턴

### Java Producer

```java
import org.apache.kafka.clients.producer.*;
import java.util.Properties;

public class OrderProducer {
    private final KafkaProducer<String, String> producer;

    public OrderProducer(String bootstrapServers) {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,
                  "org.apache.kafka.common.serialization.StringSerializer");
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,
                  "org.apache.kafka.common.serialization.StringSerializer");

        // 신뢰성 설정
        props.put(ProducerConfig.ACKS_CONFIG, "all");  // 모든 ISR 확인
        props.put(ProducerConfig.RETRIES_CONFIG, 3);
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);

        // 성능 설정
        props.put(ProducerConfig.BATCH_SIZE_CONFIG, 16384);
        props.put(ProducerConfig.LINGER_MS_CONFIG, 5);
        props.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "snappy");

        this.producer = new KafkaProducer<>(props);
    }

    public void sendOrder(String orderId, String orderJson) {
        ProducerRecord<String, String> record =
            new ProducerRecord<>("orders", orderId, orderJson);

        producer.send(record, (metadata, exception) -> {
            if (exception != null) {
                log.error("Failed to send order: {}", orderId, exception);
            } else {
                log.info("Order sent: partition={}, offset={}",
                         metadata.partition(), metadata.offset());
            }
        });
    }

    public void close() {
        producer.flush();
        producer.close();
    }
}
```

### Go Producer

```go
package main

import (
    "github.com/IBM/sarama"
    "log"
)

type OrderProducer struct {
    producer sarama.SyncProducer
}

func NewOrderProducer(brokers []string) (*OrderProducer, error) {
    config := sarama.NewConfig()
    config.Producer.RequiredAcks = sarama.WaitForAll
    config.Producer.Retry.Max = 3
    config.Producer.Return.Successes = true
    config.Producer.Compression = sarama.CompressionSnappy
    config.Producer.Idempotent = true
    config.Net.MaxOpenRequests = 1

    producer, err := sarama.NewSyncProducer(brokers, config)
    if err != nil {
        return nil, err
    }

    return &OrderProducer{producer: producer}, nil
}

func (p *OrderProducer) SendOrder(orderId, orderJson string) error {
    msg := &sarama.ProducerMessage{
        Topic: "orders",
        Key:   sarama.StringEncoder(orderId),
        Value: sarama.StringEncoder(orderJson),
    }

    partition, offset, err := p.producer.SendMessage(msg)
    if err != nil {
        return err
    }

    log.Printf("Order sent: partition=%d, offset=%d", partition, offset)
    return nil
}
```

### CRITICAL: Producer 설정

| 설정 | 권장값 | 이유 |
|------|--------|------|
| **acks** | all | 메시지 유실 방지 |
| **retries** | 3+ | 일시적 오류 복구 |
| **enable.idempotence** | true | 중복 방지 |
| **batch.size** | 16KB-64KB | 처리량 최적화 |
| **linger.ms** | 5-10 | 배치 효율 |
| **compression.type** | snappy/lz4 | 네트워크 절약 |

---

## Consumer 패턴

### Java Consumer

```java
import org.apache.kafka.clients.consumer.*;
import java.time.Duration;
import java.util.Collections;
import java.util.Properties;

public class OrderConsumer {
    private final KafkaConsumer<String, String> consumer;

    public OrderConsumer(String bootstrapServers, String groupId) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ConsumerConfig.GROUP_ID_CONFIG, groupId);
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,
                  "org.apache.kafka.common.serialization.StringDeserializer");
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,
                  "org.apache.kafka.common.serialization.StringDeserializer");

        // 오프셋 관리
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);  // 수동 커밋
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");

        // 성능 설정
        props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 500);
        props.put(ConsumerConfig.FETCH_MIN_BYTES_CONFIG, 1024);
        props.put(ConsumerConfig.FETCH_MAX_WAIT_MS_CONFIG, 500);

        this.consumer = new KafkaConsumer<>(props);
    }

    public void consume() {
        consumer.subscribe(Collections.singletonList("orders"));

        try {
            while (true) {
                ConsumerRecords<String, String> records =
                    consumer.poll(Duration.ofMillis(100));

                for (ConsumerRecord<String, String> record : records) {
                    processOrder(record.key(), record.value());
                }

                // 배치 처리 후 커밋
                consumer.commitSync();
            }
        } finally {
            consumer.close();
        }
    }

    private void processOrder(String orderId, String orderJson) {
        log.info("Processing order: {}", orderId);
    }
}
```

### Go Consumer

```go
package main

import (
    "context"
    "github.com/IBM/sarama"
    "log"
)

type OrderConsumer struct {
    ready chan bool
}

func (c *OrderConsumer) Setup(sarama.ConsumerGroupSession) error {
    close(c.ready)
    return nil
}

func (c *OrderConsumer) Cleanup(sarama.ConsumerGroupSession) error {
    return nil
}

func (c *OrderConsumer) ConsumeClaim(session sarama.ConsumerGroupSession,
    claim sarama.ConsumerGroupClaim) error {

    for message := range claim.Messages() {
        log.Printf("Processing: key=%s, partition=%d, offset=%d",
            string(message.Key), message.Partition, message.Offset)

        // 주문 처리
        processOrder(string(message.Key), string(message.Value))

        // 오프셋 커밋
        session.MarkMessage(message, "")
    }
    return nil
}

func StartConsumer(brokers []string, groupID string) {
    config := sarama.NewConfig()
    config.Consumer.Group.Rebalance.Strategy = sarama.NewBalanceStrategyRoundRobin()
    config.Consumer.Offsets.Initial = sarama.OffsetOldest

    consumer := &OrderConsumer{ready: make(chan bool)}
    client, _ := sarama.NewConsumerGroup(brokers, groupID, config)

    ctx := context.Background()
    go func() {
        for {
            client.Consume(ctx, []string{"orders"}, consumer)
        }
    }()
}
```

---

## KEDA Kafka Autoscaling

### ScaledObject 설정

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-consumer-scaler
  namespace: default
spec:
  scaleTargetRef:
    name: order-consumer  # Deployment 이름
  pollingInterval: 15
  cooldownPeriod: 30
  minReplicaCount: 1
  maxReplicaCount: 12  # 파티션 수 이하
  advanced:
    restoreToOriginalReplicaCount: true
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: my-cluster-kafka-bootstrap.kafka:9092
        consumerGroup: order-consumer-group
        topic: orders
        lagThreshold: "100"  # lag > 100이면 스케일업
        offsetResetPolicy: earliest
        allowIdleConsumers: "false"
        scaleToZeroOnInvalidOffset: "false"
```

### Consumer Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-consumer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: order-consumer
  template:
    metadata:
      labels:
        app: order-consumer
    spec:
      containers:
        - name: consumer
          image: order-consumer:latest
          env:
            - name: KAFKA_BROKERS
              value: "my-cluster-kafka-bootstrap.kafka:9092"
            - name: KAFKA_GROUP_ID
              value: "order-consumer-group"
            - name: KAFKA_TOPIC
              value: "orders"
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

### CRITICAL: KEDA 설정 팁

| 설정 | 권장 | 이유 |
|------|------|------|
| **maxReplicaCount** | ≤ 파티션 수 | 초과 시 유휴 Consumer |
| **lagThreshold** | 처리량 기반 | 너무 낮으면 플래핑 |
| **cooldownPeriod** | 30-60초 | 안정적 스케일다운 |
| **pollingInterval** | 15-30초 | 빠른 반응 |

---

## 모니터링

### Kafka Exporter

```yaml
# Helm 설치
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kafka-exporter prometheus-community/prometheus-kafka-exporter \
  --set kafkaServer=my-cluster-kafka-bootstrap.kafka:9092 \
  --namespace kafka
```

### 핵심 메트릭

```promql
# Consumer Lag (가장 중요!)
kafka_consumergroup_lag_sum{consumergroup="order-consumer-group"}

# Consumer Lag by Partition
kafka_consumergroup_lag{consumergroup="order-consumer-group",topic="orders"}

# 메시지 처리율
rate(kafka_topic_partition_current_offset{topic="orders"}[5m])

# Under-replicated Partitions (클러스터 상태)
kafka_topic_partition_under_replicated_partition
```

### Grafana 대시보드

```json
{
  "panels": [
    {
      "title": "Consumer Lag",
      "type": "timeseries",
      "targets": [{
        "expr": "sum(kafka_consumergroup_lag{consumergroup=\"$consumer_group\"}) by (topic)",
        "legendFormat": "{{topic}}"
      }]
    },
    {
      "title": "Messages In/Out Rate",
      "targets": [{
        "expr": "sum(rate(kafka_topic_partition_current_offset{topic=\"$topic\"}[5m]))",
        "legendFormat": "Messages In"
      }]
    },
    {
      "title": "Consumer Group Members",
      "targets": [{
        "expr": "count(kafka_consumergroup_members{consumergroup=\"$consumer_group\"})",
        "legendFormat": "Active Consumers"
      }]
    }
  ]
}
```

### 알림 설정

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: kafka-alerts
spec:
  groups:
    - name: kafka
      rules:
        - alert: KafkaConsumerLagHigh
          expr: sum(kafka_consumergroup_lag{consumergroup="order-consumer-group"}) > 10000
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Kafka consumer lag is high"

        - alert: KafkaUnderReplicatedPartitions
          expr: kafka_topic_partition_under_replicated_partition > 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Kafka has under-replicated partitions"
```

---

## 체크리스트

### Producer
- [ ] acks=all 설정
- [ ] idempotence 활성화
- [ ] 배치/압축 최적화
- [ ] 에러 핸들링/재시도

### Consumer
- [ ] 수동 오프셋 커밋
- [ ] Consumer Group 설정
- [ ] 적절한 poll 설정
- [ ] Graceful shutdown

### KEDA
- [ ] maxReplicaCount ≤ 파티션 수
- [ ] lagThreshold 적절히 설정
- [ ] cooldownPeriod 설정
- [ ] 모니터링 연동

### 모니터링
- [ ] Consumer Lag 알림
- [ ] Under-replicated 알림
- [ ] Grafana 대시보드

**관련 skill**: `/kafka` (기본 개념, Strimzi), `/k8s-autoscaling`, `/sre-sli-slo`
