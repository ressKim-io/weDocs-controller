---
name: vertical-slice-architecture
description: "Vertical Slice Architecture — > Feature 단위로 코드를 조직하는 아키텍처 패턴 - Jimmy Bogard 제안 Use when working with architecture 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Vertical Slice Architecture
> Feature 단위로 코드를 조직하는 아키텍처 패턴 - Jimmy Bogard 제안

## Quick Reference

```
아키텍처 선택 의사결정 트리
─────────────────────────────────────────────────────
              프로젝트 시작
                   │
        ┌──────────┴──────────┐
   복잡한 도메인 로직?      단순 CRUD?
        │                     │
      YES                  Layered OK
        │
  ┌─────┴──────┐
도메인 중심?  Feature 중심?
  │              │
Hexagonal    Vertical Slice
Clean Arch     + CQRS 결합

선택 기준:
Layered            │ 단순 CRUD, 전통적 구조
Vertical Slice     │ Feature 독립성, 빠른 변경, 팀 병렬화
Hexagonal/Clean    │ 복잡한 비즈니스 로직, 외부 의존성 격리
VSA + CQRS         │ 읽기/쓰기 분리 + Feature 단위 조직
```

## CRITICAL: Vertical Slice Architecture란?

### 핵심 개념

**Layered의 문제**: 하나의 기능 추가 시 여러 레이어 수정, 레이어 간 강한 결합, Feature 전체 맥락 파악 어려움

**Vertical Slice 해결책:**
- **Feature 단위로 코드 조직** (UI → API → Domain → DB를 하나의 슬라이스로)
- 각 슬라이스는 **독립적이고 자기완결적**
- **높은 응집도** (Feature 내부) + **낮은 결합도** (Feature 간)

```
Vertical Slice = 하나의 완전한 기능 구현
┌─────────────────────────────────────────┐
│ CreateOrder Slice                       │
│ • CreateOrderRequest (API)              │
│ • CreateOrderHandler (Logic)            │
│ • CreateOrderValidator (Validation)     │
│ • CreateOrderResponse (API)             │
└─────────────────────────────────────────┘
각 슬라이스: 독립 개발/테스트, Feature 변경 시 해당 슬라이스만 수정
```

## CRITICAL: 프로젝트 구조 비교

### Layered vs Vertical Slice

```
Layered (전통적):              Vertical Slice:
src/                           src/
├── controller/                ├── features/
│   ├── OrderController        │   ├── orders/
│   └── ProductController      │   │   ├── create/
├── service/                   │   │   │   ├── CreateOrderRequest
│   ├── OrderService           │   │   │   ├── CreateOrderHandler
│   └── ProductService         │   │   │   ├── CreateOrderValidator
├── repository/                │   │   │   └── CreateOrderResponse
│   ├── OrderRepository        │   │   ├── list/
│   └── ProductRepository      │   │   └── cancel/
└── model/                     │   └── products/
    ├── Order                  └── shared/
    └── Product                    ├── infrastructure/
                                   └── common/validation/
Layered: 기능 변경 시 4개 폴더 수정
VSA: 기능 변경 시 한 폴더만
```

## CRITICAL: Spring Boot 구현

### MediatR 패턴

```java
public interface Handler<TRequest, TResponse> {
    TResponse handle(TRequest request);
}

@Component
public class Mediator {
    private final ApplicationContext context;
    public <TRequest, TResponse> TResponse send(TRequest request) {
        String handlerName = request.getClass().getSimpleName()
            .replace("Command", "Handler").replace("Query", "Handler");
        Handler<TRequest, TResponse> handler =
            (Handler<TRequest, TResponse>) context.getBean(handlerName);
        return handler.handle(request);
    }
}
```

### Command Slice 예시

```java
// features/orders/create/CreateOrderCommand.java
@Getter @AllArgsConstructor
public class CreateOrderCommand {
    private final String customerId;
    private final List<OrderItem> items;
    private final String shippingAddress;
}

// features/orders/create/CreateOrderHandler.java
@Component @RequiredArgsConstructor
public class CreateOrderHandler
    implements Handler<CreateOrderCommand, CreateOrderResponse> {
    private final CreateOrderValidator validator;
    private final EntityManager em;
    private final ApplicationEventPublisher eventPublisher;

    @Override @Transactional
    public CreateOrderResponse handle(CreateOrderCommand command) {
        validator.validate(command);
        Order order = new Order();
        order.setCustomerId(command.getCustomerId());
        order.setItems(command.getItems());
        order.setStatus(OrderStatus.PENDING);
        order.calculateTotal();
        em.persist(order);
        eventPublisher.publishEvent(new OrderCreatedEvent(order.getId(), order.getTotal()));
        return new CreateOrderResponse(order.getId(), order.getTotal());
    }
}

// features/orders/create/CreateOrderValidator.java
@Component
public class CreateOrderValidator {
    public void validate(CreateOrderCommand command) {
        if (command.getItems().isEmpty()) throw new ValidationException("Order must have items");
        if (command.getCustomerId() == null) throw new ValidationException("Customer ID required");
    }
}
```

### Query Slice 예시

```java
// features/orders/list/ListOrdersQuery.java
@Getter @AllArgsConstructor
public class ListOrdersQuery {
    private final String customerId;
    private final LocalDate startDate, endDate;
    private final int page, size;
}

// features/orders/list/ListOrdersHandler.java
@Component @RequiredArgsConstructor
public class ListOrdersHandler
    implements Handler<ListOrdersQuery, List<OrderSummaryDto>> {
    private final EntityManager em;

    @Override @Transactional(readOnly = true)
    public List<OrderSummaryDto> handle(ListOrdersQuery query) {
        return em.createQuery("""
            SELECT new OrderSummaryDto(o.id, o.customerId, o.total, o.status, o.createdAt)
            FROM Order o
            WHERE o.customerId = :cid AND o.createdAt BETWEEN :start AND :end
            ORDER BY o.createdAt DESC""", OrderSummaryDto.class)
            .setParameter("cid", query.getCustomerId())
            .setParameter("start", query.getStartDate().atStartOfDay())
            .setParameter("end", query.getEndDate().atTime(23, 59, 59))
            .setFirstResult(query.getPage() * query.getSize())
            .setMaxResults(query.getSize())
            .getResultList();
    }
}
```

### Controller (Thin Layer)

```java
@RestController @RequestMapping("/api/orders") @RequiredArgsConstructor
public class OrderController {
    private final Mediator mediator;

    @PostMapping
    public ResponseEntity<CreateOrderResponse> createOrder(@RequestBody CreateOrderCommand cmd) {
        return ResponseEntity.ok(mediator.send(cmd));
    }
    @GetMapping
    public ResponseEntity<List<OrderSummaryDto>> listOrders(
        @RequestParam String customerId, @RequestParam LocalDate startDate,
        @RequestParam LocalDate endDate,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(mediator.send(
            new ListOrdersQuery(customerId, startDate, endDate, page, size)));
    }
}
```

## CRITICAL: Go 구현

### Command Slice

```go
// features/orders/create/handler.go
package create

type CreateOrderRequest struct {
    CustomerID      string      `json:"customer_id"`
    Items           []OrderItem `json:"items"`
    ShippingAddress string      `json:"shipping_address"`
}
type CreateOrderResponse struct {
    OrderID string  `json:"order_id"`
    Total   float64 `json:"total"`
}

type Handler struct {
    db        *sql.DB
    validator *Validator
    events    EventPublisher
}

func NewHandler(db *sql.DB, events EventPublisher) *Handler {
    return &Handler{db: db, validator: NewValidator(), events: events}
}

func (h *Handler) Handle(ctx context.Context, req CreateOrderRequest) (*CreateOrderResponse, error) {
    if err := h.validator.Validate(req); err != nil { return nil, err }
    orderID := uuid.New().String()
    total := calculateTotal(req.Items)

    tx, err := h.db.BeginTx(ctx, nil)
    if err != nil { return nil, err }
    defer tx.Rollback()

    _, err = tx.ExecContext(ctx, `
        INSERT INTO orders (id, customer_id, shipping_address, total, status)
        VALUES ($1, $2, $3, $4, 'PENDING')`, orderID, req.CustomerID, req.ShippingAddress, total)
    if err != nil { return nil, err }

    for _, item := range req.Items {
        _, err = tx.ExecContext(ctx, `
            INSERT INTO order_items (order_id, product_id, quantity, price)
            VALUES ($1, $2, $3, $4)`, orderID, item.ProductID, item.Quantity, item.Price)
        if err != nil { return nil, err }
    }
    if err := tx.Commit(); err != nil { return nil, err }
    h.events.Publish(OrderCreatedEvent{OrderID: orderID, Total: total})
    return &CreateOrderResponse{OrderID: orderID, Total: total}, nil
}
```

### HTTP Routes (Thin Layer)

```go
// features/orders/routes.go
func RegisterRoutes(r *mux.Router, db *sql.DB, events EventPublisher) {
    createHandler := create.NewHandler(db, events)
    listHandler := list.NewHandler(db)

    r.HandleFunc("/api/orders", func(w http.ResponseWriter, r *http.Request) {
        var req create.CreateOrderRequest
        if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
            http.Error(w, err.Error(), http.StatusBadRequest); return
        }
        resp, err := createHandler.Handle(r.Context(), req)
        if err != nil { http.Error(w, err.Error(), http.StatusInternalServerError); return }
        json.NewEncoder(w).Encode(resp)
    }).Methods("POST")
}
```

## CQRS와의 자연스러운 결합

```
features/orders/
├── commands/
│   ├── create/CreateOrderCommand + Handler + Validator
│   ├── cancel/
│   └── update-status/
└── queries/
    ├── list/ListOrdersQuery + Handler + OrderSummaryDto
    ├── get-by-id/
    └── search/

각 슬라이스가 독립적:
  Command: 쓰기 모델, 트랜잭션, 도메인 로직
  Query: 읽기 모델, DTO 최적화, 성능
```

### 복잡도에 따른 슬라이스 내부 구조 차등화

```
단순: ListProductsQuery + Handler (2파일)
중간: CreateOrderCommand + Handler + Validator + Response (4파일)
복잡: ProcessPaymentCommand + Handler + Validator + domain/ + Response (5+파일)
원칙: 필요한 만큼만 복잡도 추가, 동일 구조 강제 ❌
```

## 공유 코드 관리 전략

```
shared/
├── infrastructure/ (database, messaging, cache)
├── common/ (validation, exceptions, utils)
└── security/

원칙:
✓ 진짜 공유 인프라만 shared에
✓ 의심스러우면 슬라이스 내부에 (중복 허용)
✓ "Rule of Three" - 3번 반복되면 추출
```

## 아키텍처 비교

| 특성 | Layered | Vertical Slice | Hexagonal |
|------|---------|----------------|-----------|
| **조직 원칙** | 기술 레이어 | Feature | 도메인 중심 |
| **변경 범위** | 여러 레이어 | 한 슬라이스 | Port/Adapter |
| **응집도** | 낮음 | 높음 | 매우 높음 |
| **학습 곡선** | 낮음 | 중간 | 높음 |
| **코드 중복** | 낮음 | 허용 | 낮음 |
| **병렬 개발** | 어려움 | 쉬움 | 중간 |
| **적합한 경우** | 단순 CRUD | Feature 독립 변경 | 복잡한 비즈니스 로직 |

## Anti-Patterns

| 실수 | 문제 | 해결 |
|------|------|------|
| Slice 간 직접 호출 | Handler가 다른 Handler 의존 → 강결합 | 이벤트를 통한 간접 통신 |
| 과도한 추상화로 Slice 이점 상실 | Slice 내부에 Controller/Service/Repo 레이어 재생성 | Handler에 모든 로직, 복잡하면 분리 |
| 모든 Slice에 동일 복잡도 | 단순 쿼리에도 Validator/Mapper/Domain 생성 | 복잡도에 맞춘 구조 |
| shared에 무분별한 코드 추가 | Order전용 Utils가 shared에 → Feature 경계 침범 | Feature 전용은 슬라이스에, 범용만 shared |
| 도메인 모델 파편화 | 각 Slice가 자체 모델 → 일관성 문제 | 핵심 도메인은 shared/domain에 |

## Testing

```java
// Slice 단위 통합 테스트
@SpringBootTest
class CreateOrderHandlerTest {
    @Autowired private Mediator mediator;
    @Autowired private EntityManager em;

    @Test @Transactional
    void shouldCreateOrderSuccessfully() {
        var cmd = new CreateOrderCommand("customer-123",
            List.of(new OrderItem("product-1", 2, 10.00)), "123 Main St");
        var response = mediator.send(cmd);
        assertNotNull(response.getOrderId());
        assertEquals(20.00, response.getTotal());
        assertNotNull(em.find(Order.class, response.getOrderId()));
    }
    @Test void shouldFailWhenNoItems() {
        var cmd = new CreateOrderCommand("customer-123", Collections.emptyList(), "addr");
        assertThrows(ValidationException.class, () -> mediator.send(cmd));
    }
}
```

## 체크리스트

### 설계
- [ ] Feature 단위로 폴더 구조 조직
- [ ] Command/Query 분리 (CQRS 결합)
- [ ] 각 슬라이스가 자기완결적 (Request → Response)
- [ ] 공유 코드는 진짜 인프라/유틸만 shared에
- [ ] 슬라이스 간 직접 호출 금지 (이벤트 사용)

### 구현
- [ ] Handler 또는 MediatR 패턴 적용
- [ ] 슬라이스 복잡도는 Feature 요구사항에 맞춤
- [ ] DTO는 슬라이스 내부에 (재사용 금지)
- [ ] Controller는 Thin Layer (라우팅만)

### 테스트 및 운영
- [ ] 슬라이스 단위 통합 테스트
- [ ] ADR로 슬라이스 구조 표준화
- [ ] "Rule of Three" 적용 (3번 중복 시 추출)
- [ ] 슬라이스 간 이벤트 통신 모니터링

**관련 스킬**: `/msa-cqrs-eventsourcing`, `/hexagonal-clean-architecture`, `/msa-ddd`, `/msa-saga`
