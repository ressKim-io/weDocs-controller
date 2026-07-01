---
paths:
  - "**/*.java"
  - "**/*.rs"
---

# 계층·가독성 표준 (언어 무관 원칙 + 언어별 관용구)

> **위상**: 프로젝트 전체·언어 공통 표준. 개인 컬렉션(`ress-claude-agents`)으로 승격.
> **왜 있나**: "객체지향적으로 읽기 좋게 / 보일러플레이트 없이"가 스펙에 없다는 이유로 안 지켜진다(Lombok 미적용·raw String 남용). 아는데 안 쓴 것 → 체크리스트로 강제.
> **세 번째 표준(2026-06-30)** — 틀은 `error-handling.md`와 동일. `spring.md`의 계층 규칙을 언어 공통으로 확장.

---

## 원칙 (P) — 언어 무관

**P1. 단일 책임.** 한 타입/함수는 "하나의 변경 이유"만 갖는다. God object/거대 함수 금지. 함수는 한 화면(≈40줄) 안에 읽히게.

**P2. 계층 경계를 지킨다.** 표현(HTTP/gRPC) · 도메인(로직) · 영속(DB) 분리. 경계를 건너뛰는 의존 금지(컨트롤러가 리포지토리 직접 호출 ❌). → `spring.md` 계층 규칙과 동일.

**P3. 원시 강박(primitive obsession) 회피.** 도메인 개념을 raw `String`/`long`으로 흘리지 말 것 → **전용 타입**으로. `docId: String` → `DocId`. 컴파일러가 오용을 잡고 의도가 드러난다.

**P4. 보일러플레이트는 도구로 제거.** getter/생성자/equals/toString을 손으로 쓰지 말 것 → 언어 기능/라이브러리로. 코드가 짧아야 로직이 보인다.

**P5. 경계 데이터는 전용 타입(DTO).** 내부 모델(엔티티·도메인 객체)을 API 경계 밖으로 누출 금지. 입출력은 DTO로 명시적 매핑.

**P6. 이름이 곧 문서.** 의도가 드러나는 명명. 주석으로 나쁜 이름을 변명하지 말 것.

---

## Java 실현

**P4/P5 — DTO는 `record`, 엔티티는 Lombok(단 `@Data` 금지).**
```java
// DTO/값객체 = record (불변, JDK 네이티브, 보일러플레이트 0)
public record CreatePageRequest(String title, String parentId) {}

// JPA 엔티티 = Lombok, 단 @Data ❌ (아래 이유)
@Entity @Getter @NoArgsConstructor(access = PROTECTED)
@EqualsAndHashCode(onlyExplicitlyIncluded = true)   // ← id만
class Page {
    @Id @EqualsAndHashCode.Include Long id;
    @OneToMany @ToString.Exclude List<Page> children;  // 관계는 제외
}
```
> ⛔ **엔티티에 `@Data`/`@ToString`/`@EqualsAndHashCode`(기본) 금지.** lazy 관계 `toString()`/`hashCode()`가 무한 재귀·의도치 않은 로딩을 유발하고, null PK에서 `equals`가 깨져 `Set`에 못 넣는다.
> - record는 엔티티가 될 수 없다(불변·무인자 생성자 없음) → 엔티티는 Lombok, DTO는 record.

**P2 — 계층.** Controller(파싱·검증·`ResponseEntity`) → Service(`@Transactional`·로직) → Repository(DB). 건너뛰기 금지. (`spring.md` 참조)

---

## Rust 실현

**P3 — newtype로 primitive obsession 회피.** (엔진 `doc_id: String` 남용의 처방)
```rust
// ❌ 함수 시그니처마다 raw String — 뭐가 doc_id고 뭐가 user_id인지 컴파일러가 모름
fn open(&self, doc_id: &str) { ... }

// ✅ newtype — 오용은 컴파일 에러, 의도가 타입에 박힘
pub struct DocId(String);
fn open(&self, doc_id: &DocId) { ... }
```

**P4 — derive로 보일러플레이트 제거.**
```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash)]   // 손으로 impl 하지 말 것
pub struct DocId(String);
```

**P1/P6 — 작은 함수·평탄화.** 깊은 중첩 대신 `?`·early return·`match`. 한 함수 한 책임. (엔진이 `handle_inbound`/`handle_broadcast`로 분리한 것 = 좋은 예)

**복잡한 생성은 빌더.** 필드 많은 구성은 builder 패턴 or `Default` + 필드 갱신.

**모듈 경계.** `pub`은 최소로(공개 표면 관리). 내부 타입은 `pub(crate)`.

---

## ✅ 리뷰 체크리스트 (게이트 실행 — 위반 시 반려)

> Gate 3에서 `rust-expert`/`java-expert`가 실행. **[B]=blocking, [A]=advisory.**

**공통**
- [ ][B] 계층 경계 위반 없음(표현→도메인→영속 건너뛰기 없음) (P2)
- [ ][B] 내부 모델(엔티티/도메인)이 API 경계로 누출 안 됨 → DTO 사용 (P5)
- [ ][A] 함수 단일 책임·과도한 길이/중첩 없음 (P1)
- [ ][A] 도메인 개념이 raw 원시타입 아님 (primitive obsession) (P3)

**Java**
- [ ][B] **JPA 엔티티에 `@Data`/기본 `@EqualsAndHashCode`/`@ToString` 없음** (무한재귀·Set 버그)
- [ ][A] DTO/값객체는 `record` (Lombok `@Data`는 비-엔티티 값객체에만)
- [ ][A] getter/생성자 수기 작성 없음 → Lombok/record

**Rust**
- [ ][A] 도메인 식별자에 newtype (raw `String`/`u64` 남용 아님) (P3)
- [ ][A] `Debug`/`Clone`/`PartialEq` 등 수기 impl 대신 derive (P4)
- [ ][A] `pub` 표면 최소화, 깊은 중첩 대신 `?`/early return (P1/P6)

> 이 표준은 대부분 `[A]`다 — 가독성은 취향 폭이 넓어 강제보다 권장 위주. **단 엔티티 `@Data`는 실제 버그를 유발**하므로 `[B]`.

---

## 게이트 배선 (활용 강제)

`code-review.md` 크래프트 렌즈(🦀/☕)가 이 체크리스트도 실행. `[B]`(엔티티 @Data·계층 위반·모델 누출)=반려, 나머지 가독성은 `[A]` 코멘트. 새 함정은 `review-gaps.md` → 이 문서로 승격.

---

## 출처

- Java: [Thorben Janssen — Lombok & Hibernate 함정](https://thorben-janssen.com/lombok-hibernate-how-to-avoid-common-pitfalls/) · [JPA Buddy — Lombok & JPA](https://jpa-buddy.com/blog/lombok-and-jpa-what-may-go-wrong/) · [Records vs Lombok for DTO](https://toolshref.com/java-records-vs-lombok-dto-guide/) · Effective Java(불변·빌더)
- Rust: [Rust Design Patterns — Idioms](https://rust-unofficial.github.io/patterns/idioms/) · [Newtype 패턴](https://doc.rust-lang.org/rust-by-example/generics/new_types.html) · [Rust API Guidelines] · [idiomatic-rust 모음](https://github.com/mre/idiomatic-rust)
