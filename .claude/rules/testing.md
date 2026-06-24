---
paths:
  - "**/*test*"
  - "**/*Test*"
  - "**/*spec*"
  - "**/*Spec*"
  - "**/test/**"
  - "**/tests/**"
---

# Testing Rules

테스트 작성 시 반드시 이 규칙을 따르라. 예외 없음.

---

## TDD 원칙

새 기능 구현 전 반드시 테스트를 먼저 작성하라.

**Red → Green → Refactor** 사이클을 준수하라:
1. **Red**: 실패하는 테스트를 작성하고, 실패를 직접 확인하라
2. **Green**: 테스트를 통과시키는 최소한의 구현만 작성하라
3. **Refactor**: 테스트가 통과된 상태에서 코드를 정리하라

테스트가 통과되기 전까지 해당 기능을 완료로 간주하지 말라.
테스트 없이 구현 코드를 먼저 작성하지 말라.

---

## 테스트 분류

세 가지 레벨을 명확히 구분하라:

```
Unit Test        단일 클래스/함수 단위 검증
                 외부 의존성은 모두 mock/stub 처리
                 실행 시간 < 1초

Integration Test 여러 컴포넌트 조합 검증
                 실제 DB, 외부 서비스, 메시지 브로커 사용
                 TestContainers 또는 embedded 서버 활용

E2E Test         전체 시스템 흐름 검증
                 API 엔드포인트 → 응답까지 전체 경로 테스트
                 실제 환경과 동일한 설정 사용
```

---

## 네이밍 규칙

테스트 메서드명만 보고 무엇을 검증하는지 즉시 파악할 수 있어야 한다.

**Java:**
```java
// 영어 메서드명: should_행위_when_조건
void should_returnEmpty_when_userNotFound()

// 또는 한국어 DisplayName
@DisplayName("존재하지 않는 사용자 조회 시 빈 결과를 반환한다")
void findUser_notFound()
```

**Go:**
```go
// TestSubject_행위_when조건
func TestUserService_ReturnEmpty_WhenUserNotFound(t *testing.T)
```

모호한 이름은 금지한다: `test1()`, `testOk()`, `testUser()`.

---

## Given-When-Then 구조

모든 테스트는 세 구역을 주석으로 명시하라:

```java
@Test
void should_applyDiscount_when_couponIsValid() {
    // Given: 테스트 전제 조건 설정
    User user = UserFixture.create();
    Coupon coupon = CouponFixture.validCoupon(10);

    // When: 테스트 대상 행위 실행
    Order order = orderService.place(user, coupon);

    // Then: 결과 검증 (assertion)
    assertThat(order.getDiscountRate()).isEqualTo(10);
    assertThat(order.getStatus()).isEqualTo(OrderStatus.PLACED);
}
```

하나의 테스트에서 `// When`이 두 번 등장하면 테스트를 분리하라.

---

## 커버리지 규칙

| 대상 | 최소 커버리지 |
|------|-------------|
| 전체 코드 | 80% |
| 핵심 비즈니스 로직 (도메인, 서비스) | 95% |

커버리지 숫자 달성보다 의미 있는 assertion을 우선하라.
다음 세 가지 케이스를 반드시 테스트하라:

- **Happy path**: 정상적인 입력과 기대 결과
- **Edge case**: 경계값, 빈 컬렉션, null, 최대/최소값
- **Error case**: 예외 발생, 잘못된 입력, 외부 서비스 실패

assertion 없이 예외만 잡고 넘기는 테스트는 작성하지 말라.

---

## 금지 사항

**테스트 간 순서 의존 금지**
각 테스트는 독립적으로 실행되어야 한다. `@TestMethodOrder`로 순서를 강제하지 말라.

**Sleep/시간 기반 대기 금지**
```java
// 금지
Thread.sleep(1000);

// 허용: Awaitility, polling, 이벤트 기반 대기
await().atMost(5, SECONDS).until(() -> result.isDone());
```

**테스트에서 프로덕션 코드 수정 금지**
테스트 통과를 위해 프로덕션 코드에 `if (isTest)` 분기를 추가하지 말라.

**실패 테스트를 @Disabled/@Skip으로 무시 금지**
실패하는 테스트는 즉시 수정하거나, issue를 등록하고 원인을 명시하라.

---

## Fixture / Test Double

반복되는 테스트 데이터는 Fixture 클래스로 분리하라:
```java
// UserFixture.java — 테스트 전용 객체 생성 유틸
public class UserFixture {
    public static User create() { ... }
    public static User admin() { ... }
}
```

Mock은 행위 검증이 필요할 때만 사용하라. 단순 데이터 반환이 목적이면 Stub을 사용하라.
`@MockBean` 남용은 Spring 컨텍스트 재생성을 유발하므로 최소화하라.
