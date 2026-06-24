---
paths: "**/*.java"
---

# Spring Boot 패턴 규칙

## 계층 구조 (Layered Architecture)

**Controller**: HTTP 요청 파싱, `@Valid` 검증, `ResponseEntity` 반환만 담당.
NEVER Controller에 비즈니스 로직 작성 — Service로 위임.

**Service**: 비즈니스 로직과 트랜잭션 경계를 담당. Repository를 조율.
NEVER Service에서 HTTP 관련 객체(`HttpServletRequest` 등) 참조.

**Repository**: DB 접근만 담당.
NEVER Repository에 비즈니스 로직 작성.

NEVER Controller에서 Repository 직접 주입 — 반드시 Service를 거칠 것.

## @Transactional

MUST Service 레이어에만 `@Transactional` 사용. Controller, Repository에는 금지.

클래스 레벨에 `@Transactional(readOnly = true)` 기본 적용,
쓰기 메서드에만 `@Transactional`을 개별 오버라이드.

```java
@Transactional(readOnly = true)
public class OrderService {
    public OrderResponse getOrder(Long id) { ... }

    @Transactional
    public OrderResponse createOrder(OrderRequest req) { ... }
}
```

NEVER `private` 메서드에 `@Transactional` — AOP 프록시가 미작동.
NEVER 같은 클래스 내에서 `@Transactional` 메서드를 직접 호출 — self-invocation은 트랜잭션을 무시.

**NEVER `@Transactional` 메서드 내에서 외부 시스템 호출 (HTTP, 결제, 메시지 큐 등).**
- DB 락이 외부 latency 동안 유지 → connection pool 고갈
- 메시 retry (Istio 5xx retry 등)와 결합 시 **중복 결제 / 중복 발송** 사고 발생 (실제 사례: 비멱등 POST + Istio retry → 중복 결제)
- 외부 호출은 트랜잭션 커밋 후 또는 Outbox / SAGA 패턴으로 분리

```java
// BAD: @Tx 안에 HTTP 호출
@Transactional
public void pay(Order o) {
    paymentClient.charge(o);  // 외부 latency 동안 DB lock 점유
    o.markPaid();
}

// GOOD: Outbox 패턴
@Transactional
public void pay(Order o) {
    o.markPaid();
    outbox.save(new PaymentRequested(o.id));  // 동일 트랜잭션
}
// 별도 worker가 outbox → paymentClient 호출 + 멱등성 키 사용
```

---

## BeanPostProcessor / BeanInitialization 순서

`BeanPostProcessor` (BPP) 안에서 다른 빈을 참조할 때 **반드시 lazy resolution 패턴** 사용:

- MUST `ObjectProvider<T>` 또는 `@Lazy`로 늦은 주입
- MUST `postProcessAfterInitialization`에서 처리 — `postProcessBeforeInitialization`은 빈이 미완성
- NEVER 생성자에서 다른 빈 직접 주입 (BPP는 다른 BPP보다 먼저 초기화될 수 있음)

```java
// BAD: 순환 초기화 가능
public class OtelInstrumentation implements BeanPostProcessor {
    private final MeterRegistry registry;  // 다른 BPP일 수 있음
    public OtelInstrumentation(MeterRegistry r) { this.registry = r; }
}

// GOOD: 지연 해석
public class OtelInstrumentation implements BeanPostProcessor {
    private final ObjectProvider<MeterRegistry> registry;

    @Override
    public Object postProcessAfterInitialization(Object bean, String name) {
        if (bean instanceof DataSource ds) {
            registry.getIfAvailable(); // 이 시점엔 다른 빈 완성됨
        }
        return bean;
    }
}
```

실제 사례: HikariCP + OTel 자동 계측 BPP 순서 문제로 DataSource 가 instrumented 되지 않음.

---

## OTel 의존성 관리

Spring Boot의 `dependency-management`가 OTel BOM 버전을 덮어쓸 수 있다.

- MUST OTel 의존성은 instrumentation BOM 으로 일괄 관리: `io.opentelemetry.instrumentation:opentelemetry-instrumentation-bom`
- NEVER 개별 OTel 모듈 버전을 따로 지정 — Spring BOM에 의해 다운그레이드되어 spec 위반 발생
- NEVER OTel Java Agent + Spring Boot Starter 동시 사용 — 이중 계측 발생

```kotlin
// build.gradle.kts
dependencies {
    implementation(platform("io.opentelemetry.instrumentation:opentelemetry-instrumentation-bom:${otelVersion}"))
    implementation("io.opentelemetry.instrumentation:opentelemetry-spring-boot-starter")
}
```

## DTO vs Entity

NEVER Controller 응답에 Entity 직접 노출 — 스키마 변경이 API 변경으로 전파됨.

Request DTO 수신 → Service 처리 → Response DTO 반환 흐름 MUST 준수.

DTO 변환은 `ResponseDto.from(entity)` static factory 패턴 PREFER.

```java
public record OrderResponse(Long id, String status) {
    public static OrderResponse from(Order order) {
        return new OrderResponse(order.getId(), order.getStatus().name());
    }
}
```

DTO는 MUST `record` 사용 (Java 16+). 불변이고 보일러플레이트가 없다.
NEVER `@Entity` 클래스에 record 사용 — java.md 참조.

## 예외 처리

MUST `@RestControllerAdvice` 글로벌 핸들러 하나에 모든 예외 처리 집중.
NEVER Controller 메서드 내 try-catch — 핸들러로 위임.

도메인 예외는 MUST `BusinessException extends RuntimeException`으로 정의.

에러 응답은 MUST 표준화: `ErrorResponse(code, message, timestamp)`.
NEVER 프로덕션 응답에 스택트레이스 포함 — 내부 구조 노출 금지.

```java
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> handle(BusinessException e) {
        return ResponseEntity.badRequest().body(ErrorResponse.of(e));
    }
}
```

## 설정

PREFER `@ConfigurationProperties` > `@Value` — 타입 안전하고 검증 가능.
NEVER `application.yml`에 시크릿(비밀번호, API 키) 하드코딩 — 환경변수 또는 Secret Manager 사용.

## API 설계

MUST RESTful 명사형 URI: `POST /orders`, `GET /orders/{id}`, `DELETE /orders/{id}`.
MUST 입력 검증: `@Valid` + Bean Validation(`@NotNull`, `@Size` 등) 조합.
페이징은 PREFER `Pageable` 파라미터 — Spring Data가 자동 처리.

## 테스트

`@WebMvcTest`: Controller 슬라이스 테스트 — Service는 `@MockBean` 처리.
`@DataJpaTest`: Repository 슬라이스 테스트 — 인메모리 DB 자동 구성.
`@SpringBootTest`: 통합 테스트 — PREFER 최소화, 느리고 무겁다.

NEVER `@MockBean` 남용 — 실제 빈 우선. 모킹이 많으면 테스트 신뢰도가 낮아진다.

---

상세 가이드: `/spring-patterns` 스킬 참조
