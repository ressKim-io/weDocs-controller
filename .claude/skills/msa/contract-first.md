---
name: contract-first
description: "Contract-First Development — API 계약을 먼저 정의하고 코드를 생성하는 개발 방법론 — OpenAPI, Protobuf, AsyncAPI, Pact Use when working with msa 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Contract-First Development

API 계약을 먼저 정의하고 코드를 생성하는 개발 방법론 — OpenAPI, Protobuf, AsyncAPI, Pact

## Quick Reference (결정 트리)

```
API 유형별 계약 도구 선택
    │
    ├─ REST API (공개/외부) ──────> OpenAPI 3.1 + Spectral
    │
    ├─ 내부 서비스 간 통신 ───────> gRPC/Protobuf + buf
    │
    ├─ 이벤트/메시지 기반 ────────> AsyncAPI 3.0
    │
    └─ GraphQL ───────────────────> SDL-first + codegen

계약 검증 전략
    │
    ├─ Provider 주도 ─────────────> Schema Registry + 호환성 검사
    │
    ├─ Consumer 주도 ─────────────> Pact (CDC Testing)
    │
    └─ 양방향 검증 ──────────────> Schema Registry + Pact 조합
```

---

## OpenAPI 3.1 Spec-First Workflow

### 워크플로우

```
spec 작성 → lint/validate → 리뷰 → code generation → 구현 → contract test
```

### OpenAPI 3.1 핵심 구조

```yaml
# openapi/order-api.yaml
openapi: "3.1.0"
info:
  title: Order API
  version: "1.0.0"
paths:
  /orders:
    post:
      operationId: createOrder
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CreateOrderRequest"
      responses:
        "201":
          description: Created
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Order"
  /orders/{orderId}:
    get:
      operationId: getOrder
      parameters:
        - name: orderId
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Order"
components:
  schemas:
    Order:
      type: object
      required: [id, status, items]
      properties:
        id: { type: string, format: uuid }
        status: { type: string, enum: [PENDING, CONFIRMED, SHIPPED] }
        items:
          type: array
          items:
            $ref: "#/components/schemas/OrderItem"
    OrderItem:
      type: object
      required: [productId, quantity]
      properties:
        productId: { type: string }
        quantity: { type: integer, minimum: 1 }
    CreateOrderRequest:
      type: object
      required: [items]
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/OrderItem"
```

### Spec Validation (Spectral)

```yaml
# .spectral.yaml
extends: ["spectral:oas"]
rules:
  operation-operationId: error
  oas3-schema: error
  no-eval-in-markdown: warn
  operation-tag-defined: warn
```

```bash
# lint 실행
npx @stoplight/spectral-cli lint openapi/order-api.yaml

# Redocly 검증 (대안)
npx @redocly/cli lint openapi/order-api.yaml
```

### Mock Server (Prism)

```bash
# spec 기반 mock 서버 기동 — 프론트엔드/소비자 팀 즉시 개발 가능
npx @stoplight/prism-cli mock openapi/order-api.yaml -p 4010
```

### Code Generation (openapi-generator)

```bash
# Java Spring 서버 스텁
openapi-generator-cli generate \
  -i openapi/order-api.yaml \
  -g spring \
  -o gen/java \
  --additional-properties=interfaceOnly=true,useSpringBoot3=true

# Go 서버
openapi-generator-cli generate \
  -i openapi/order-api.yaml \
  -g go-server \
  -o gen/go

# TypeScript 클라이언트
openapi-generator-cli generate \
  -i openapi/order-api.yaml \
  -g typescript-axios \
  -o gen/ts-client
```

---

## Protobuf/gRPC Contract-First

> 상세 gRPC 패턴은 `msa/grpc.md` 참조

### buf.yaml + buf.gen.yaml

```yaml
# buf.yaml
version: v2
modules:
  - path: proto
lint:
  use:
    - DEFAULT
breaking:
  use:
    - FILE    # 엄격: 필드 삭제, 타입 변경 감지
```

### Breaking Change Detection

```bash
# main 브랜치 대비 호환성 검사
buf breaking --against '.git#branch=main'

# 원격 레지스트리 대비
buf breaking --against 'buf.build/myorg/myapi'
```

| 변경 유형 | FILE 모드 | PACKAGE 모드 |
|-----------|----------|-------------|
| 필드 번호 변경 | Breaking | Breaking |
| 필드 삭제 | Breaking | Breaking |
| 메시지 이름 변경 | Breaking | 허용 |
| 패키지 이동 | Breaking | Breaking |

### CI Pipeline 통합

```yaml
# .github/workflows/proto-ci.yml
- name: Buf Lint
  uses: bufbuild/buf-action@v1
  with:
    input: proto
- name: Buf Breaking
  uses: bufbuild/buf-action@v1
  with:
    input: proto
    breaking_against: "buf.build/myorg/myapi"
```

---

## AsyncAPI (Event-Driven Contracts)

### AsyncAPI 3.0 기본 구조

```yaml
# asyncapi/order-events.yaml
asyncapi: "3.0.0"
info:
  title: Order Events
  version: "1.0.0"
channels:
  orderCreated:
    address: orders.created
    messages:
      OrderCreatedEvent:
        $ref: "#/components/messages/OrderCreatedEvent"
operations:
  publishOrderCreated:
    action: send
    channel:
      $ref: "#/channels/orderCreated"
  consumeOrderCreated:
    action: receive
    channel:
      $ref: "#/channels/orderCreated"
components:
  messages:
    OrderCreatedEvent:
      payload:
        type: object
        required: [orderId, userId, createdAt]
        properties:
          orderId: { type: string, format: uuid }
          userId: { type: string }
          items:
            type: array
            items:
              type: object
              properties:
                productId: { type: string }
                quantity: { type: integer }
          createdAt: { type: string, format: date-time }
```

### Kafka Channel Binding

```yaml
channels:
  orderCreated:
    address: orders.created
    bindings:
      kafka:
        partitions: 6
        replicas: 3
        topicConfiguration:
          retention.ms: 604800000
          cleanup.policy: ["delete"]
```

### Code Generation

```bash
# AsyncAPI Generator
npx @asyncapi/cli generate fromTemplate \
  asyncapi/order-events.yaml \
  @asyncapi/java-spring-template \
  -o gen/async-java

# TypeScript
npx @asyncapi/cli generate fromTemplate \
  asyncapi/order-events.yaml \
  @asyncapi/typescript-nats-template \
  -o gen/async-ts
```

---

## Consumer-Driven Contract Testing (Pact)

### 워크플로우

```
Consumer Test → Pact File 생성 → Pact Broker 업로드
    → Provider Verification → can-i-deploy 체크 → 배포
```

### Consumer 측 (Java 예시)

```java
@ExtendWith(PactConsumerTestExt.class)
@PactTestFor(providerName = "OrderService", port = "8080")
class OrderClientPactTest {

    @Pact(consumer = "PaymentService")
    V4Pact getOrderPact(PactDslWithProvider builder) {
        // Given: 계약 정의
        return builder
            .given("order 123 exists")
            .uponReceiving("get order by id")
            .path("/orders/123")
            .method("GET")
            .willRespondWith()
            .status(200)
            .body(newJsonBody(body -> {
                body.stringType("id", "123");
                body.stringMatcher("status", "PENDING|CONFIRMED|SHIPPED", "PENDING");
            }).build())
            .toPact(V4Pact.class);
    }

    @Test
    @PactTestFor(pactMethod = "getOrderPact")
    void should_getOrder(MockServer mockServer) {
        // When: mock 서버로 호출
        Order order = new OrderClient(mockServer.getUrl()).getOrder("123");

        // Then: 응답 검증
        assertThat(order.getId()).isEqualTo("123");
    }
}
```

### Provider 측 검증

```java
@Provider("OrderService")
@PactBroker(url = "https://pact-broker.example.com")
@SpringBootTest(webEnvironment = RANDOM_PORT)
class OrderProviderPactTest {

    @TestTemplate
    @ExtendWith(PactVerificationInvocationContextProvider.class)
    void verifyPact(PactVerificationContext context) {
        context.verifyInteraction();
    }

    @State("order 123 exists")
    void setupOrder() {
        orderRepository.save(new Order("123", OrderStatus.PENDING));
    }
}
```

### Pact Broker CI/CD

```bash
# Consumer: Pact 파일 발행
pact-broker publish pacts/ \
  --consumer-app-version=$(git rev-parse --short HEAD) \
  --branch=$(git branch --show-current)

# 배포 전 호환성 확인
pact-broker can-i-deploy \
  --pacticipant=PaymentService \
  --version=$(git rev-parse --short HEAD) \
  --to-environment=production
```

---

## Schema Registry

### 스키마 포맷 비교

| 항목 | Avro | Protobuf | JSON Schema |
|------|------|----------|-------------|
| 직렬화 크기 | 최소 (바이너리) | 소 (바이너리) | 대 (텍스트) |
| 스키마 진화 | 우수 (기본값 필수) | 우수 (필드 번호) | 보통 |
| 코드 생성 | 필요 | 필요 | 선택 |
| 가독성 | JSON 스키마 | .proto 파일 | JSON |
| 권장 용도 | Kafka 이벤트 | gRPC/내부 통신 | REST API |

### Confluent Schema Registry

```bash
# 스키마 등록
curl -X POST http://schema-registry:8081/subjects/orders-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{"schemaType":"AVRO","schema":"{\"type\":\"record\",\"name\":\"Order\",\"fields\":[{\"name\":\"id\",\"type\":\"string\"},{\"name\":\"status\",\"type\":\"string\"}]}"}'

# 호환성 검사
curl -X POST http://schema-registry:8081/compatibility/subjects/orders-value/versions/latest \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d @new-schema.json
```

### 호환성 모드

| 모드 | 허용 | 금지 | 용도 |
|------|------|------|------|
| BACKWARD | 필드 삭제, 기본값 있는 필드 추가 | 필수 필드 추가 | Consumer 먼저 배포 |
| FORWARD | 필수 필드 추가 | 필드 삭제 | Provider 먼저 배포 |
| FULL | 기본값 있는 필드 추가/삭제만 | 필수 필드 변경 | 순서 무관 배포 |
| NONE | 모든 변경 | - | 개발 환경 전용 |

```bash
# Subject 호환성 모드 설정
curl -X PUT http://schema-registry:8081/config/orders-value \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{"compatibility":"BACKWARD"}'
```

---

## Code Generation CI/CD Pipeline

```yaml
# .github/workflows/contract-ci.yml
name: Contract CI
on:
  push:
    paths: ["openapi/**", "proto/**", "asyncapi/**"]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npx @stoplight/spectral-cli lint openapi/*.yaml
      - uses: bufbuild/buf-action@v1
        with:
          breaking_against: "buf.build/myorg/myapi"
      - run: npx @asyncapi/cli validate asyncapi/*.yaml
  generate:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate & commit
        run: |
          openapi-generator-cli batch openapitools.json
          buf generate
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "chore(codegen): regenerate from contract changes"
          file_pattern: "gen/**"
  pact-verify:
    needs: generate
    runs-on: ubuntu-latest
    steps:
      - run: ./gradlew pactVerify
      - run: |
          pact-broker can-i-deploy \
            --pacticipant=${{ github.event.repository.name }} \
            --version=${{ github.sha }} \
            --to-environment=production
```

---

## Anti-Patterns

| 실수 | 올바른 방법 |
|------|------------|
| 코드 먼저 작성 후 spec 역생성 | Spec-first: 계약 정의 → 코드 생성 |
| 생성된 코드 수동 편집 | 생성 코드는 읽기 전용, 커스텀 로직은 별도 계층 |
| Breaking change 검사 없이 배포 | CI에서 buf breaking / 호환성 검사 필수 |
| 단일 spec 파일에 모든 API 정의 | 도메인별 spec 분리, $ref로 참조 |
| Pact 없이 통합 테스트만 의존 | CDC 테스트로 소비자-공급자 계약 검증 |

---

## 체크리스트

- [ ] API 유형에 맞는 계약 도구 선택 (OpenAPI / Protobuf / AsyncAPI)
- [ ] Spec validation 및 lint를 CI에 통합
- [ ] Breaking change detection 설정 (buf breaking / Schema Registry)
- [ ] Code generation 파이프라인 자동화
- [ ] Consumer-driven contract test (Pact) 적용
- [ ] Mock server로 병렬 개발 환경 구축
- [ ] 생성된 코드는 VCS에 커밋하되 수동 편집 금지

---

## 관련 Skills

- `/grpc` — gRPC 서비스 설계 상세
- `/api-design` — REST API 설계 원칙
- `/kafka` — Kafka 메시징 패턴
- `/event-driven` — 이벤트 기반 아키텍처
