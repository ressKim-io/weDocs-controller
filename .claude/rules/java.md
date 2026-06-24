---
paths: "**/*.java"
---

# Java 코드 패턴 규칙

## 객체 생성

파라미터 3개 이상이거나 선택적 파라미터가 있으면 MUST `@Builder` 사용.

여러 생성 방법이 필요하거나 캐싱이 필요하면 PREFER Static Factory (`of()`, `from()`, `valueOf()`).

불변 데이터(DTO, VO, 이벤트, API 응답)는 PREFER `record` 사용 (Java 16+).
Lombok `@Value` 또는 수동 불변 클래스도 허용 — 팀 컨벤션에 따른다.
NEVER JPA `@Entity`에 record 사용 — JPA는 기본 생성자와 가변 상태가 필요하다.

## 의존성 주입

MUST `@RequiredArgsConstructor` + `private final` 필드 조합 사용.
NEVER `@Autowired` 필드 주입 — 테스트 불가, 불변성 파괴.

순환 참조는 설계 문제다. NEVER 순환 참조를 허용하고, 이벤트 또는 인터페이스로 해결.

## 불변성

MUST 클래스 필드를 `private final`로 선언.
NEVER setter 메서드 추가 — 불변 객체 우선 설계.
컬렉션 반환 시 MUST `List.copyOf()` 또는 `Collections.unmodifiableList()` 사용.

```java
// BAD
public List<Item> getItems() { return items; }
// GOOD
public List<Item> getItems() { return List.copyOf(items); }
```

## Modern Java

**Sealed class**: 닫힌 타입 계층은 PREFER `sealed interface` + `record` 구현체.

**Virtual Threads (Java 21+)**: I/O 바운드 작업에만 사용.
NEVER Virtual Thread 내 `synchronized` 블록에서 I/O 수행 — pinning 발생.
NEVER CPU 바운드 작업에 Virtual Thread 남용.

**Pattern Matching**: MUST `instanceof Type var` 패턴 사용, 명시적 캐스팅 제거.
```java
// BAD
if (obj instanceof String) { String s = (String) obj; }
// GOOD
if (obj instanceof String s) { ... }
```

**Stream**: PREFER `filter → map → collect` 체인.
`break` / `continue`가 필요한 로직은 for loop 사용이 더 명확하다.

## 제네릭 & 열거형

NEVER raw type 사용 — `List` 대신 `List<String>`.
고정 값 집합은 MUST `enum` 사용. NEVER `int` 또는 `String` 상수로 대체.

## 메서드 구조 (Composed Method)

비즈니스 로직은 같은 추상화 수준의 메서드 호출로 구성한다 (SLAP 원칙).

- 조건문/로직 블록이 3줄 이상이면 MUST 의도를 드러내는 메서드로 추출
- 1-2줄 로직은 메서드 추출 대신 MUST 목적을 설명하는 인라인 주석 사용
- 한 메서드는 PREFER 20-50줄 이내로 유지 (Cognitive Complexity ≤ 15 기준 병행)

```java
// BAD: 추상화 수준이 뒤섞임
public void reserve(User user, Seat seat) {
    if (seat.getStatus() != AVAILABLE) throw new SeatUnavailableException();
    if (seat.isBlocked()) throw new SeatBlockedException();
    if (seat.isExpired()) throw new SeatExpiredException();
    if (user.getReservations().size() >= MAX_LIMIT) throw new LimitExceededException();
    // 예약 생성 로직 10줄...
}

// GOOD: Composed Method — 메서드명이 곧 문서
public void reserve(User user, Seat seat) {
    validateSeatAvailable(seat);
    validateReservationLimit(user);
    createReservation(user, seat);
}

// GOOD: 1-2줄은 주석으로 의도 표현
public void cancel(Reservation reservation) {
    // 취소 가능 상태 확인
    if (!reservation.isCancellable()) throw new CancelNotAllowedException();

    reservation.cancel();
    publishEvent(new ReservationCancelled(reservation.getId()));
}
```

## 예외 처리

비즈니스 예외는 MUST custom `RuntimeException` 서브클래스 정의.
표준 예외 PREFER: `IllegalArgumentException` (잘못된 인수), `IllegalStateException` (잘못된 상태).
MUST 예외 메시지에 실패 값 포함 — 디버깅 가능성 확보.
NEVER 빈 catch 블록 — 에러 삼키기 절대 금지.

```java
// BAD
catch (Exception e) {}
// GOOD
catch (Exception e) { throw new DataProcessingException("Failed for id=" + id, e); }
```

## 동시성

NEVER `new Thread()` 직접 생성 — MUST `ExecutorService` 또는 Virtual Thread 사용.
공유 가변 데이터는 MUST `AtomicInteger`, `ConcurrentHashMap` 또는 불변 객체로 보호.

---

상세 가이드: `/effective-java` 스킬 참조
