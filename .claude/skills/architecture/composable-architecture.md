---
name: composable-architecture
description: "Composable Architecture (MACH) — MACH Alliance 기반 조합형 아키텍처 — Packaged Business Capabilities(PBC)를 교체·조합하여 비즈니스 민첩성을 극대화하는 설계 패턴 Use when working with architecture 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Composable Architecture (MACH)

MACH Alliance 기반 조합형 아키텍처 — Packaged Business Capabilities(PBC)를 교체·조합하여 비즈니스 민첩성을 극대화하는 설계 패턴

## Quick Reference (결정 트리)

```
아키텍처 유연성 필요?
    │
    ├─ 단일 팀, 변경 빈도 낮음 ─────────> Traditional Monolith
    ├─ API 중심 통합, 벤더 1~2개 ────────> API-First Architecture
    ├─ 벤더 교체 유연성 필수 ─────────────> MACH Architecture
    │    ├─ Microservices-based
    │    ├─ API-First
    │    ├─ Cloud-Native SaaS
    │    └─ Headless
    └─ 풀스택 조합 + PBC 교체 ───────────> Composable Architecture
         ├─ PBC 단위 벤더 교체
         ├─ Micro-Frontend 통합
         └─ API Composition Layer

도입 판단 기준:
    ├─ 다채널(Web/Mobile/IoT) 동시 지원 ──> Composable 권장
    ├─ 벤더 계약 주기 < 2년 ───────────────> Composable 권장
    ├─ 비즈니스 변경 주기 < 분기 ──────────> Composable 권장
    └─ 단일 채널, 변경 드묾 ───────────────> Monolith 유지
```

---

## CRITICAL: MACH 원칙

```
MACH Alliance 2025 데이터:
  - 87% 조직이 Composable 도입 진행 중
  - 61% 기술 스택을 MACH 기반으로 전환 목표
  - 평균 Time-to-Market 42% 단축
  - 벤더 교체 비용 70% 절감 (Adapter 패턴 적용 시)
```

### 4가지 핵심 원칙

| 원칙 | 의미 | 핵심 효과 |
|------|------|----------|
| **M**icroservices | 독립 배포·스케일링 가능한 서비스 | 팀 자율성, 장애 격리 |
| **A**PI-First | 모든 기능을 API로 노출 | 통합 유연성, 채널 독립 |
| **C**loud-Native | SaaS 우선, 클라우드 네이티브 | 운영 부담 감소, 탄력적 확장 |
| **H**eadless | 프론트엔드/백엔드 완전 분리 | UI 자유도, 옴니채널 |

### 아키텍처 전체 구조

```
┌─ Experience Layer ──────────────────────────────┐
│  Web App  │  Mobile App  │  IoT Device  │ Kiosk │
└─────┬─────┴──────┬───────┴──────┬───────┴───┬───┘
      │            │              │            │
┌─────▼────────────▼──────────────▼────────────▼───┐
│           BFF (Backend For Frontend)              │
│   Web BFF    │   Mobile BFF    │   Device BFF    │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│          API Composition Layer                     │
│  GraphQL Federation │ API Gateway │ Event Mesh    │
└──┬──────────┬───────────┬──────────┬─────────────┘
   │          │           │          │
┌──▼───┐ ┌───▼──┐ ┌──────▼──┐ ┌────▼─────┐
│ CMS  │ │ Cart │ │ Search  │ │ Payment  │
│ PBC  │ │ PBC  │ │ PBC     │ │ PBC      │
│Cont- │ │Comm- │ │Algolia/ │ │Stripe/  │
│entful│ │erce- │ │Elastic  │ │Adyen    │
└──────┘ └──────┘ └─────────┘ └──────────┘
  PBC = Packaged Business Capability (자체 완결적 비즈니스 단위)
```

---

## 아키텍처 비교

| 항목 | Monolith | Microservices | Composable (MACH) |
|------|----------|---------------|-------------------|
| **배포** | 단일 아티팩트 | 서비스별 독립 | PBC별 독립 + SaaS |
| **벤더 교체** | 전체 재작성 | 서비스 재구현 | Adapter 교체만 |
| **프론트엔드** | 서버 렌더링 | API 기반 | Headless + MFE |
| **통합** | 직접 호출 | API/Event | API Composition |
| **Time-to-Market** | 느림 | 중간 | 빠름 (PBC 조합) |
| **초기 복잡도** | 낮음 | 높음 | 높음 |
| **벤더 비용** | 라이선스 고정 | 자체 구축 | SaaS 종량제 |
| **적합 규모** | 소규모 팀 | 중대규모 팀 | 대규모+옴니채널 |

---

## CRITICAL: Packaged Business Capabilities (PBCs)

### PBC 정의

PBC는 자체 완결적 비즈니스 기능 단위로, 다음 특성을 갖는다:
- **자율적**: 독립 배포·운영 가능
- **교체 가능**: Adapter 패턴으로 벤더 추상화
- **API Contract**: REST/GraphQL/gRPC 인터페이스 명세
- **Event Contract**: 도메인 이벤트 발행·구독 명세

### PBC 인터페이스 설계

```
┌─────────────────────────────────────┐
│           PBC Contract              │
│  ┌─ API Contract ─────────────────┐ │
│  │ GET /contents/{id}             │ │
│  │ POST /contents/search          │ │
│  │ Response: Content DTO          │ │
│  └────────────────────────────────┘ │
│  ┌─ Event Contract ───────────────┐ │
│  │ content.published  → Topic     │ │
│  │ content.updated    → Topic     │ │
│  │ content.deleted    → Topic     │ │
│  └────────────────────────────────┘ │
│  ┌─ SLA Contract ────────────────┐  │
│  │ Latency: p99 < 200ms         │  │
│  │ Availability: 99.9%          │  │
│  │ Rate Limit: 1000 req/s       │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### PBC 벤더 교체 매트릭스

| PBC | Option A | Option B | Adapter 전략 |
|-----|----------|----------|-------------|
| CMS | Contentful | Strapi | ContentService 인터페이스 |
| Commerce | Commercetools | Medusa | CommerceService 인터페이스 |
| Search | Algolia | Elasticsearch | SearchService 인터페이스 |
| Payment | Stripe | Adyen | PaymentService 인터페이스 |
| Auth | Auth0 | Keycloak | AuthService 인터페이스 |

---

## Spring Boot 구현

### PBC Interface (Port 정의)

```java
// === PBC Port (비즈니스 인터페이스) ===
public interface ContentService {
    Content getContent(String id);
    List<Content> search(SearchQuery query);
    void publish(String id);
}

public interface CommerceService {
    Product getProduct(String id);
    List<Product> getProducts(List<String> ids);
    Cart addToCart(String cartId, String productId, int qty);
}

// === Content DTO (벤더 독립) ===
public record Content(
    String id,
    String title,
    String body,
    Map<String, Object> metadata,
    Instant publishedAt
) {}
```

### Adapter 구현 (벤더별)

```java
// === Contentful Adapter ===
@Component
@ConditionalOnProperty(name = "cms.provider", havingValue = "contentful")
public class ContentfulAdapter implements ContentService {
    private final ContentfulClient client;

    @Override
    public Content getContent(String id) {
        var entry = client.getEntry(id);
        return mapToContent(entry);  // 벤더 모델 → 도메인 모델 변환
    }

    @Override
    public List<Content> search(SearchQuery query) {
        var params = ContentfulQueryBuilder.from(query);
        return client.search(params).stream()
            .map(this::mapToContent)
            .toList();
    }
}

// === Strapi Adapter (교체 시 이것만 변경) ===
@Component
@ConditionalOnProperty(name = "cms.provider", havingValue = "strapi")
public class StrapiAdapter implements ContentService {
    private final StrapiClient client;

    @Override
    public Content getContent(String id) {
        var article = client.findOne("articles", id);
        return mapToContent(article);
    }

    @Override
    public List<Content> search(SearchQuery query) {
        var filters = StrapiFilterBuilder.from(query);
        return client.find("articles", filters).stream()
            .map(this::mapToContent)
            .toList();
    }
}
```

### API Composition (BFF Layer)

```java
@RestController
@RequestMapping("/api/v1/pages")
public class ProductPageController {
    private final ContentService cms;
    private final CommerceService commerce;
    private final SearchService search;

    @GetMapping("/{slug}")
    public Mono<PageResponse> getPage(@PathVariable String slug) {
        var content = Mono.fromCallable(() -> cms.getContent(slug));
        var recommendations = Mono.fromCallable(() ->
            search.recommend(slug, 4));

        return Mono.zip(content, recommendations)
            .map(tuple -> {
                var c = tuple.getT1();
                var products = commerce.getProducts(c.metadata()
                    .get("productIds"));
                return PageResponse.compose(c, products, tuple.getT2());
            });
    }
}

// 설정으로 벤더 전환 (application.yml)
// cms.provider: contentful  →  cms.provider: strapi
// commerce.provider: commercetools  →  commerce.provider: medusa
```

### PBC Event 발행

```java
@Component
public class ContentEventPublisher {
    private final ApplicationEventPublisher publisher;

    public void contentPublished(String contentId) {
        publisher.publishEvent(new ContentPublishedEvent(contentId, Instant.now()));
    }
}

// PBC 간 Event 수신
@Component
public class CommerceContentListener {
    @EventListener
    public void onContentPublished(ContentPublishedEvent event) {
        commerceService.refreshProductPage(event.contentId());
    }
}
```

---

## Go 구현

### PBC Interface + Factory

```go
// PBC Interface
type ContentService interface {
    GetContent(ctx context.Context, id string) (*Content, error)
    Search(ctx context.Context, query SearchQuery) ([]*Content, error)
    Publish(ctx context.Context, id string) error
}

type CommerceService interface {
    GetProduct(ctx context.Context, id string) (*Product, error)
    GetProducts(ctx context.Context, ids []string) ([]*Product, error)
}

// Content DTO (벤더 독립)
type Content struct {
    ID          string                 `json:"id"`
    Title       string                 `json:"title"`
    Body        string                 `json:"body"`
    Metadata    map[string]interface{} `json:"metadata"`
    PublishedAt time.Time              `json:"published_at"`
}

// Provider Factory
func NewContentService(cfg *config.Config) (ContentService, error) {
    switch cfg.CMS.Provider {
    case "contentful":
        return contentful.NewAdapter(cfg.CMS.Contentful)
    case "strapi":
        return strapi.NewAdapter(cfg.CMS.Strapi)
    default:
        return nil, fmt.Errorf("unsupported CMS provider: %s", cfg.CMS.Provider)
    }
}
```

### API Composition Handler

```go
func (h *PageHandler) GetPage(w http.ResponseWriter, r *http.Request) {
    slug := chi.URLParam(r, "slug")
    g, ctx := errgroup.WithContext(r.Context())

    var content *Content
    var recommendations []*Product

    g.Go(func() error {
        var err error
        content, err = h.cms.GetContent(ctx, slug)
        return err
    })
    g.Go(func() error {
        var err error
        recommendations, err = h.search.Recommend(ctx, slug, 4)
        return err
    })

    if err := g.Wait(); err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    products, _ := h.commerce.GetProducts(ctx, content.ProductIDs())
    json.NewEncoder(w).Encode(ComposePage(content, products, recommendations))
}
```

---

## Micro-Frontends 통합

### 조합 전략 비교

| 전략 | 방식 | 장점 | 단점 |
|------|------|------|------|
| Module Federation | Webpack/Vite 런타임 조합 | 유연한 로딩 | 번들 복잡도 |
| Web Components | Custom Elements 기반 | 프레임워크 독립 | 상태 공유 어려움 |
| Server-Side Composition | Edge/SSR에서 HTML 조합 | SEO 우수 | 실시간 인터랙션 제한 |
| iframe Composition | iframe으로 PBC UI 삽입 | 완전 격리 | UX/성능 저하 |

### Module Federation 구성

```
┌─ Shell App (Host) ──────────────────────┐
│  ┌─ Header ─┐ ┌─ Nav ─┐  (shared)      │
│  └──────────┘ └────────┘                │
│  ┌─ CMS Widget ──┐ ┌─ Cart Widget ───┐ │
│  │ Remote: CMS   │ │ Remote: Commerce│ │
│  │ MFE Bundle    │ │ MFE Bundle     │ │
│  └───────────────┘ └────────────────┘ │
│  ┌─ Search Widget ──────────────────┐   │
│  │ Remote: Search MFE Bundle        │   │
│  └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
각 Widget = PBC의 UI 부분 (독립 배포)
```

### Web Components 기반 PBC UI

```html
<!-- PBC별 Web Component -->
<cms-content-block content-id="hero-banner"></cms-content-block>
<commerce-product-grid category="featured" limit="8"></commerce-product-grid>
<search-bar placeholder="Search products..." provider="algolia"></search-bar>
<!-- PBC UI는 독립 번들로 배포, Custom Element로 등록 -->
```

---

## API Composition 패턴

### GraphQL Federation으로 PBC 통합

```
┌─ Apollo Gateway / GraphQL Mesh ─────────┐
│        Federated Supergraph              │
│  ┌─ CMS Subgraph ──┐                   │
│  │ type Content     │                   │
│  │   @key(id)       │                   │
│  └──────────────────┘                   │
│  ┌─ Commerce Subgraph ─┐               │
│  │ type Product         │               │
│  │   @key(id)           │               │
│  │ extend type Content  │               │
│  │   products: [Product]│               │
│  └──────────────────────┘               │
│  ┌─ Search Subgraph ───┐               │
│  │ type SearchResult    │               │
│  │ extend type Query    │               │
│  │   search(): [Result] │               │
│  └──────────────────────┘               │
└──────────────────────────────────────────┘
```

### Event-Driven PBC 통신

```
CMS PBC                    Commerce PBC              Search PBC
   │                           │                         │
   │── content.published ─────>│                         │
   │                           │── product.updated ─────>│
   │                           │                         │── index.rebuilt ──>
   │<── catalog.synced ────────│                         │

Event Bus: Kafka / RabbitMQ / Cloud Events
Topic Naming: {pbc}.{entity}.{action}
  예: cms.content.published, commerce.cart.updated
```

### API Gateway 구성 (Kong)

```yaml
# Kong Gateway - PBC 라우팅
services:
  - name: cms-pbc
    url: http://cms-service:8080
    routes:
      - paths: ["/api/v1/contents"]
  - name: commerce-pbc
    url: http://commerce-service:8080
    routes:
      - paths: ["/api/v1/products", "/api/v1/carts"]
  - name: search-pbc
    url: http://search-service:8080
    routes:
      - paths: ["/api/v1/search"]
plugins:
  - name: rate-limiting
    config: { minute: 1000 }
  - name: jwt
    config: { claims_to_verify: ["exp"] }
```

---

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| PBC 간 직접 DB 공유 | 강결합, 독립 배포 불가 | API/Event Contract으로만 통신 |
| 벤더 SDK 직접 사용 | 벤더 lock-in, 교체 비용 폭증 | Adapter 패턴으로 Port 추상화 |
| 과도한 PBC 분리 | 통합 복잡도 급증 | 비즈니스 가치 단위로 묶기 |
| Monolithic BFF | BFF가 God Service화 | 채널별 BFF 분리, 얇게 유지 |
| Event 스키마 미관리 | PBC 간 호환성 깨짐 | Schema Registry + 버전 관리 |
| SLA 미정의 | 장애 시 책임 불명확 | PBC별 SLA Contract 명시 |

---

## 체크리스트

### 설계
- [ ] 비즈니스 도메인 기반 PBC 경계 식별
- [ ] PBC별 API Contract 정의 (OpenAPI/GraphQL Schema)
- [ ] PBC별 Event Contract 정의 (CloudEvents 스키마)
- [ ] PBC별 SLA Contract 정의 (latency, availability, rate limit)
- [ ] Adapter 패턴으로 벤더 추상화 설계

### 구현
- [ ] Port/Adapter 인터페이스 구현 (Spring ConditionalOnProperty / Go Factory)
- [ ] API Composition Layer 구현 (BFF 또는 GraphQL Federation)
- [ ] Event Bus 연동 (Kafka/RabbitMQ)
- [ ] Schema Registry 설정 (API + Event)

### 프론트엔드
- [ ] Micro-Frontend 전략 선택 (Module Federation / Web Components)
- [ ] Shell App + Remote Widget 구성
- [ ] 공유 디자인 시스템 적용

### 운영
- [ ] PBC별 독립 배포 파이프라인
- [ ] PBC 헬스체크 및 Circuit Breaker
- [ ] 벤더 교체 runbook 작성
- [ ] Contract Testing (Pact/Spring Cloud Contract)

**관련 스킬**: `/msa-api-gateway-patterns`, `/graphql-federation`, `/msa-event-driven`, `/msa-ddd`
