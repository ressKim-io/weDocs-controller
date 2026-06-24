---
name: observability
description: "Observability Patterns — 로깅, 트레이싱, 메트릭을 위한 기본 패턴 Use when working with observability 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Observability Patterns

로깅, 트레이싱, 메트릭을 위한 기본 패턴

## Quick Reference (결정 트리)

```
Observability 구성
    │
    ├─ Logs ────────> 구조화 JSON + trace_id
    │
    ├─ Traces ──────> OpenTelemetry (/observability-otel 참조)
    │
    └─ Metrics ─────> RED Method (Rate, Errors, Duration)
```

---

## 3 Pillars of Observability

| Pillar | 목적 | 질문 |
|--------|------|------|
| **Logs** | 이벤트 기록 | "무슨 일이 일어났나?" |
| **Traces** | 요청 흐름 추적 | "어디서 느려졌나?" |
| **Metrics** | 수치 측정 | "얼마나 많이/빠르게?" |

---

## CRITICAL: 구조화된 로깅

**IMPORTANT**: 반드시 JSON 구조화 로깅 사용

```json
{
  "timestamp": "2025-01-24T10:30:00Z",
  "level": "error",
  "message": "Failed to process order",
  "service": "order-service",
  "trace_id": "abc123def456",
  "span_id": "789xyz",
  "user_id": 42,
  "order_id": "ORD-001",
  "error": "insufficient stock",
  "duration_ms": 150
}
```

### 로그 레벨 가이드

| Level | 사용 시점 | 프로덕션 |
|-------|----------|----------|
| `ERROR` | 즉시 조치 필요 | ✅ |
| `WARN` | 잠재적 문제 | ✅ |
| `INFO` | 주요 비즈니스 이벤트 | ✅ |
| `DEBUG` | 개발/디버깅용 | ❌ (필요시만) |

### 필수 컨텍스트

```
✅ 포함해야 할 것:
- trace_id, span_id (분산 추적)
- user_id, request_id (요청 식별)
- service, version (서비스 식별)
- duration_ms (성능)

❌ 제외해야 할 것:
- 비밀번호, 토큰
- 개인정보 (이메일, 전화번호)
- 전체 요청/응답 바디
```

---

## 메트릭: RED Method

| 메트릭 | 설명 | 예시 |
|--------|------|------|
| **R**ate | 요청 수/초 | `http_requests_total` |
| **E**rrors | 에러율 | `http_errors_total / http_requests_total` |
| **D**uration | 응답 시간 | `http_request_duration_seconds` |

### Spring Boot Actuator

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,prometheus,metrics
  metrics:
    tags:
      application: ${spring.application.name}
```

```java
@PostMapping("/orders")
public Order createOrder(@RequestBody OrderRequest request) {
    Timer.Sample sample = Timer.start(meterRegistry);
    try {
        Order order = orderService.create(request);
        meterRegistry.counter("orders.created", "status", "success").increment();
        return order;
    } catch (Exception e) {
        meterRegistry.counter("orders.created", "status", "error").increment();
        throw e;
    } finally {
        sample.stop(meterRegistry.timer("orders.create.duration"));
    }
}
```

### Go Prometheus

```go
var httpRequestsTotal = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "http_requests_total",
    },
    []string{"method", "path", "status"},
)

var httpRequestDuration = prometheus.NewHistogramVec(
    prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Buckets: prometheus.DefBuckets,
    },
    []string{"method", "path"},
)
```

---

## Context Propagation

### HTTP 헤더 (W3C Trace Context)

```
traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
             └── trace_id ──────────────────────┘ └── span_id ──────┘
```

### 로그에 trace_id 주입

**Spring Boot (Logback)**
```xml
<encoder class="net.logstash.logback.encoder.LogstashEncoder">
    <includeMdcKeyName>traceId</includeMdcKeyName>
    <includeMdcKeyName>spanId</includeMdcKeyName>
</encoder>
```

**Go (zerolog)**
```go
span := trace.SpanFromContext(ctx)
logger.With().
    Str("trace_id", span.SpanContext().TraceID().String()).
    Logger()
```

---

## OpenTelemetry

**상세 설정**: `/observability-otel` skill 참조

| 항목 | 내용 |
|------|------|
| Spring Boot | `spring-boot-starter-opentelemetry` |
| Go | `go.opentelemetry.io/otel` |
| 샘플링 | 프로덕션 10-20% 권장 |

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| trace_id 없는 로그 | 분산 추적 불가 | OTel 자동 주입 |
| 전체 payload 로깅 | 로그 폭발 | ID/상태만 기록 |
| 100% 샘플링 | 비용 폭발 | 프로덕션 10-20% |
| 문자열 로그만 | 검색 어려움 | 구조화 JSON |
| 민감정보 로깅 | 보안 위험 | 마스킹 필터 |

---

## 체크리스트

### 로깅
- [ ] JSON 구조화 로깅
- [ ] 로그 레벨 적절히 사용
- [ ] 민감정보 마스킹

### Traces
- [ ] trace_id 로그 연동
- [ ] 샘플링 비율 설정

### 메트릭
- [ ] RED 메트릭 수집
- [ ] 알림 규칙 설정
