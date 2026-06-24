---
name: graphql-federation
description: "GraphQL Federation 가이드 — Apollo Federation v2 기반 Supergraph 설계, Subgraph 구현 (Go gqlgen / Spring DGS), Router 배포, Schema CI Use when working with msa 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# GraphQL Federation 가이드

Apollo Federation v2 기반 Supergraph 설계, Subgraph 구현 (Go gqlgen / Spring DGS), Router 배포, Schema CI

## Quick Reference (결정 트리)

```
GraphQL API 전략 선택
    │
    ├─ 단일 서비스, 단일 팀 ──────────> Standalone GraphQL (Federation 불필요)
    ├─ 다수 서비스, 통합 Graph 필요 ──> Apollo Federation v2
    │   ├─ Go 서비스 ────────────────> gqlgen + federation plugin
    │   ├─ Spring 서비스 ────────────> Netflix DGS Framework
    │   └─ Router ───────────────────> GraphOS Router (Rust 기반, 고성능)
    ├─ gRPC 서비스만 존재 ──────────> gRPC Gateway 또는 직접 gRPC 사용
    └─ REST + GraphQL 혼합 ────────> Federation + REST Data Source

Subgraph 경계 설계
    │
    ├─ DDD Bounded Context 정의됨 ──> Context = Subgraph (권장)
    ├─ 팀 경계 기반 ────────────────> 팀당 1~2 Subgraph
    └─ Entity 공유 필요 ────────────> @key + Entity Resolver 패턴
```

---

## CRITICAL: Federation v2 아키텍처

```
  Client (Web / Mobile / BFF)
      │  단일 GraphQL 엔드포인트
      ▼
  ┌─────────────────────────────┐
  │     GraphOS Router          │  ← Rust 기반, Query Planning, 인증
  │  (Supergraph Schema 보유)   │     OTel Tracing, Rate Limiting
  └──────┬──────┬──────┬────────┘
         │      │      │
    ┌────▼──┐ ┌▼─────┐ ┌▼───────┐
    │ User  │ │Order │ │Product │  ← 각 Subgraph = Bounded Context
    │ (DGS) │ │(gqlgen)│ │ (DGS) │    독립 배포, 독립 스키마
    └──┬────┘ └──┬───┘ └──┬─────┘
    ┌──▼───┐ ┌──▼───┐ ┌──▼──────┐
    │UserDB│ │OrderDB│ │ProductDB│  ← Database per Service
    └──────┘ └──────┘ └─────────┘

Composition: Subgraph SDL → CI Compose → Supergraph Schema → Router
```

### Federation v2 핵심 디렉티브

| 디렉티브 | 용도 |
|----------|------|
| `@key(fields: "id")` | Entity의 고유 식별 필드 지정 |
| `@shareable` | 여러 Subgraph에서 같은 필드 정의 허용 |
| `@external` | 다른 Subgraph에서 정의된 필드 참조 |
| `@override` | 필드 소유권을 다른 Subgraph로 이전 (마이그레이션) |
| `@provides` | 특정 쿼리 경로에서 외부 필드 제공 (성능 최적화) |
| `@requires` | 필드 resolve 시 다른 필드 필요 (계산 필드) |
| `@inaccessible` | Supergraph에서 숨김 (내부 전용) |

---

## CRITICAL: Subgraph 스키마 설계

```
Entity 소유권 원칙:
  Subgraph A (User)              Subgraph B (Order)
  ┌──────────────────┐           ┌──────────────────────┐
  │ type User @key   │           │ type Order @key      │
  │   id: ID!        │  ◄─ ref ─│   id: ID!            │
  │   email: String! │           │   user: User!        │
  │   name: String!  │           │   items: [OrderItem!]│
  └──────────────────┘           │ type User @key       │
  ※ User 원본 소유자              │   id: ID!            │
                                 │   orders: [Order!]   │
                                 └──────────────────────┘
                                 ※ User에 orders 확장
규칙: 1) Entity 원본 소유는 하나의 Subgraph만
      2) 다른 Subgraph는 Entity 확장으로 필드 추가
      3) Subgraph 경계 = Bounded Context 경계
      4) 순환 의존 금지 (A→B→A 설계 결함)
```

### Subgraph 스키마 예시

```graphql
# schema/user.graphql (User Subgraph - Entity 원본 소유)
extend schema @link(url: "https://specs.apollo.dev/federation/v2.7",
  import: ["@key", "@shareable"])

type Query {
  user(id: ID!): User
  users(first: Int = 20, after: String): UserConnection!
}
type User @key(fields: "id") {
  id: ID!
  email: String!
  name: String!
  status: UserStatus!
}
type UserConnection { edges: [UserEdge!]!; pageInfo: PageInfo! }
type PageInfo @shareable { hasNextPage: Boolean!; endCursor: String }
```

```graphql
# schema/order.graphql (Order Subgraph - User Entity 확장)
extend schema @link(url: "https://specs.apollo.dev/federation/v2.7",
  import: ["@key", "@external"])

type Order @key(fields: "id") {
  id: ID!
  user: User!
  items: [OrderItem!]!
  totalAmount: Int!
  status: OrderStatus!
}
type User @key(fields: "id") {     # User 확장: orders 필드 추가
  id: ID!
  orders(first: Int = 10): [Order!]!
}
type Product @key(fields: "id") { id: ID! }  # Product Subgraph 참조
```

---

## Go gqlgen Federation 구현

### gqlgen.yml

```yaml
schema:
  - graph/schema/*.graphql
exec:   { filename: graph/generated.go, package: graph }
model:  { filename: graph/model/models_gen.go, package: model }
resolver: { layout: follow-schema, dir: graph }
federation:
  filename: graph/federation.go
  package: graph
  version: 2   # Federation v2 활성화
```

### Entity Resolver (Federation 핵심)

```go
// graph/entity.resolvers.go - Router가 Entity를 ID로 조회할 때 호출
func (r *entityResolver) FindOrderByID(ctx context.Context, id string) (*model.Order, error) {
    order, err := r.orderRepo.FindByID(ctx, id)
    if err != nil {
        return nil, fmt.Errorf("order %s 조회 실패: %w", id, err)
    }
    return order, nil
}

// User stub - orders 필드만 이 Subgraph에서 resolve
func (r *entityResolver) FindUserByID(ctx context.Context, id string) (*model.User, error) {
    return &model.User{ID: id}, nil
}
```

### Query Resolver

```go
func (r *queryResolver) Order(ctx context.Context, id string) (*model.Order, error) {
    return r.orderRepo.FindByID(ctx, id)
}

func (r *userResolver) Orders(ctx context.Context, obj *model.User, first *int) ([]*model.Order, error) {
    limit := 10
    if first != nil { limit = *first }
    return r.orderRepo.FindByUserID(ctx, obj.ID, limit)
}
```

### DataLoader (N+1 방지 - 필수)

```go
func NewProductLoader(repo repository.ProductRepo) *dataloader.Loader[string, *model.Product] {
    return dataloader.NewBatchedLoader(
        func(ctx context.Context, keys []string) []*dataloader.Result[*model.Product] {
            products, _ := repo.FindByIDs(ctx, keys) // 배치 조회
            m := make(map[string]*model.Product)
            for _, p := range products { m[p.ID] = p }
            results := make([]*dataloader.Result[*model.Product], len(keys))
            for i, k := range keys {
                results[i] = &dataloader.Result[*model.Product]{Data: m[k]}
            }
            return results
        },
        dataloader.WithWait[string, *model.Product](2*time.Millisecond),
    )
}
```

---

## Spring Netflix DGS Federation 구현

### 의존성

```kotlin
// build.gradle.kts
plugins { id("com.netflix.dgs.codegen") version "7.0.3" }
dependencies {
    implementation(platform("com.netflix.graphql.dgs:graphql-dgs-platform-dependencies:9.1.2"))
    implementation("com.netflix.graphql.dgs:graphql-dgs-spring-graphql-starter")
}
```

### DGS DataFetcher + Entity Resolver

```java
@DgsComponent
@RequiredArgsConstructor
public class UserDataFetcher {
    private final UserRepository userRepository;

    @DgsQuery
    public User user(@InputArgument String id) {
        return userRepository.findById(id)
            .orElseThrow(() -> new DgsEntityNotFoundException("User not found: " + id));
    }

    // Federation Entity Resolver - Router가 User를 ID로 조회할 때 호출
    @DgsEntityFetcher(name = "User")
    public User resolveUser(Map<String, Object> values) {
        String id = (String) values.get("id");
        return userRepository.findById(id)
            .orElseThrow(() -> new DgsEntityNotFoundException("User(" + id + ") not found"));
    }
}
```

### DGS DataLoader (N+1 방지)

```java
@DgsDataLoader(name = "users")
@RequiredArgsConstructor
public class UserDataLoader implements BatchLoaderWithContext<String, User> {
    private final UserRepository userRepository;

    @Override
    public CompletionStage<List<User>> load(List<String> ids, BatchLoaderEnvironment env) {
        return CompletableFuture.supplyAsync(() -> userRepository.findAllByIdIn(ids));
    }
}

@DgsComponent
public class OrderUserFetcher {
    @DgsData(parentType = "Order", field = "user")
    public CompletableFuture<User> user(DgsDataFetchingEnvironment dfe) {
        Order order = dfe.getSource();
        return dfe.<String, User>getDataLoader("users").load(order.getUserId());
    }
}
```

---

## CRITICAL: Router 배포 및 운영

### Supergraph 구성

```bash
# supergraph.yaml
federation_version: =2.7.1
subgraphs:
  user:  { routing_url: "http://user-subgraph:4000/graphql",  schema: { file: ./schemas/user.graphql } }
  order: { routing_url: "http://order-subgraph:4000/graphql", schema: { file: ./schemas/order.graphql } }

rover supergraph compose --config supergraph.yaml > supergraph.graphql
rover subgraph check my-graph@prod --name user --schema ./schemas/user.graphql
```

### Router 설정 (router.yaml)

```yaml
supergraph: { path: /supergraph.graphql }
authentication:
  router: { jwt: { jwks: [{ url: "https://auth.example.com/.well-known/jwks.json" }] } }
headers:
  all: { request: [{ propagate: { named: Authorization } }, { propagate: { named: X-Request-ID } }] }
traffic_shaping:
  all: { timeout: 30s }
  subgraphs: { user: { timeout: 5s }, order: { timeout: 10s } }
telemetry:
  exporters:
    tracing: { otlp: { enabled: true, endpoint: "http://otel-collector:4317", protocol: grpc } }
    metrics: { prometheus: { enabled: true, listen: "0.0.0.0:9090", path: /metrics } }
  instrumentation:
    spans: { mode: spec_compliant, subgraph: { attributes: { subgraph.name: true, graphql.operation.name: true } } }
```

### K8s Deployment + HPA

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: graphql-router }
spec:
  replicas: 3
  selector: { matchLabels: { app: graphql-router } }
  template:
    metadata:
      labels: { app: graphql-router }
      annotations: { prometheus.io/scrape: "true", prometheus.io/port: "9090" }
    spec:
      containers:
        - name: router
          image: ghcr.io/apollographql/router:v2.1.1
          args: ["--config", "/app/config/router.yaml", "--supergraph", "/app/config/supergraph.graphql"]
          ports: [{ name: http, containerPort: 4000 }, { name: metrics, containerPort: 9090 }]
          resources: { requests: { cpu: 500m, memory: 512Mi }, limits: { cpu: "2", memory: 1Gi } }
          livenessProbe:  { httpGet: { path: /health, port: 4000 }, periodSeconds: 10 }
          readinessProbe: { httpGet: { path: "/health?ready", port: 4000 }, periodSeconds: 5 }
          volumeMounts: [{ name: config, mountPath: /app/config }]
      volumes: [{ name: config, configMap: { name: router-config } }]
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: graphql-router-hpa }
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: graphql-router }
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
    - type: Pods
      pods: { metric: { name: http_requests_per_second }, target: { type: AverageValue, averageValue: "1000" } }
  behavior: { scaleUp: { stabilizationWindowSeconds: 30 }, scaleDown: { stabilizationWindowSeconds: 300 } }
```

---

## OTel 분산 트레이싱

### Go Subgraph

```go
func initTracer(ctx context.Context) (*sdktrace.TracerProvider, error) {
    exp, _ := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("otel-collector:4317"), otlptracegrpc.WithInsecure(),
    )
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exp),
        sdktrace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL, semconv.ServiceNameKey.String("order-subgraph"),
        )),
        sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(0.1))),
    )
    otel.SetTracerProvider(tp)
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
        propagation.TraceContext{}, propagation.Baggage{},
    ))
    return tp, nil
}
// main: http.Handle("/graphql", otelhttp.NewHandler(srv, "graphql"))
```

### Spring DGS

```yaml
# application.yaml
management:
  tracing: { sampling: { probability: 0.1 } }
  otlp: { tracing: { endpoint: "http://otel-collector:4318/v1/traces" } }
```

```kotlin
dependencies {
    implementation("io.micrometer:micrometer-tracing-bridge-otel")
    implementation("io.opentelemetry:opentelemetry-exporter-otlp")
}
```

---

## Schema CI/CD 파이프라인

```yaml
# .github/workflows/schema-ci.yaml
name: GraphQL Schema CI
on:
  pull_request:
    paths: ['schemas/**', '**/resources/schema/**', '**/graph/schema/**']
jobs:
  schema-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: curl -sSL https://rover.apollo.dev/nix/latest | sh && echo "$HOME/.rover/bin" >> $GITHUB_PATH
      - name: Breaking Change 검증
        run: |
          for file in $(git diff --name-only origin/main -- schemas/); do
            rover subgraph check my-graph@prod --name "$(basename $file .graphql)" --schema "$file"
          done
      - run: rover supergraph compose --config supergraph.yaml > /dev/null
  deploy-schema:
    needs: schema-check
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: curl -sSL https://rover.apollo.dev/nix/latest | sh && echo "$HOME/.rover/bin" >> $GITHUB_PATH
      - name: Publish
        env: { APOLLO_KEY: "${{ secrets.APOLLO_KEY }}" }
        run: |
          rover subgraph publish my-graph@prod --name user \
            --schema schemas/user.graphql --routing-url http://user-subgraph:4000/graphql
          rover subgraph publish my-graph@prod --name order \
            --schema schemas/order.graphql --routing-url http://order-subgraph:4000/graphql
```

---

## Anti-Patterns

| 실수 | 문제 | 올바른 방법 |
|------|------|------------|
| 단일 거대 Subgraph | 모놀리스와 동일 | DDD Bounded Context 기반 분리 |
| Subgraph 간 순환 참조 | 배포 순서 의존, 장애 전파 | 단방향 의존, 이벤트 기반 동기화 |
| N+1 Query 미처리 | Entity Resolver 호출 폭발 | DataLoader 패턴 필수 적용 |
| Router 없이 직접 호출 | 클라이언트가 Subgraph 위치 인지 필요 | 항상 Router 경유, 단일 엔드포인트 |
| Schema CI 미구축 | Breaking Change 프로덕션 유입 | PR에서 `rover subgraph check` 필수 |
| 모든 필드 @shareable | 소유권 모호, 데이터 불일치 | 원본 소유 Subgraph 명확히 지정 |
| Subgraph에 인증 중복 | 코드 중복, 정책 불일치 | Router JWT 검증 + 헤더 전파 |
| Query depth 제한 없음 | 깊은 쿼리로 DoS 가능 | Router에서 depth/complexity 제한 |

---

## 체크리스트

### 스키마 설계
- [ ] Subgraph 경계가 DDD Bounded Context와 일치하는가?
- [ ] Entity `@key`가 모든 공유 타입에 정의되어 있는가?
- [ ] `@external`, `@requires` 필드 의존성이 명확한가?
- [ ] Relay Cursor Pagination (Connection 패턴) 적용했는가?

### 구현
- [ ] Entity Resolver가 모든 `@key` 타입에 구현되어 있는가?
- [ ] DataLoader로 N+1 문제를 해결했는가?
- [ ] Subgraph health check 엔드포인트가 있는가?

### Router 운영
- [ ] HPA가 CPU/RPS 기반으로 설정되어 있는가?
- [ ] JWT 인증이 Router 레벨에서 처리되는가?
- [ ] Subgraph별 timeout이 설정되어 있는가?
- [ ] Query depth/complexity 제한이 설정되어 있는가?

### Observability & CI/CD
- [ ] OTel tracing이 Router → Subgraph 전 구간에 설정되어 있는가?
- [ ] Prometheus 메트릭이 Router에서 노출되고 있는가?
- [ ] PR에서 `rover subgraph check`로 Breaking Change 탐지하는가?
- [ ] Main 머지 시 `rover subgraph publish`로 Schema Registry 업데이트하는가?

---

## 관련 Skills

- `/api-design` - REST API 설계 원칙, GraphQL과의 비교
- `/msa-ddd` - Bounded Context 설계, Subgraph 경계 도출
- `/grpc` - gRPC 서비스 통신, Subgraph 간 내부 통신 대안
