---
paths:
  - "**/*.java"
  - "**/*.rs"
  - "**/*.py"
---

# 에러 처리 표준 (언어 무관 원칙 + 언어별 관용구)

> **위상**: 프로젝트 전체·언어 공통 엔지니어링 표준. 개인 컬렉션(`ress-claude-agents`)으로 승격해 재사용 대상.
> **왜 있나**: AI가 방법을 몰라서가 아니라 **활용을 안 해서** 예외가 산재하고 raw 예외가 남는다. 이 문서는 (1)원칙을 명시하고 (2)맨 아래 **검증 체크리스트**로 리뷰 게이트가 강제한다. (availability + verification = activation)
> **첫 표준(2026-06-30)** — 이 틀을 concurrency·layering·observability로 복제한다.

---

## 원칙 (P) — 언어 무관

**P1. 예외는 경계에서 한 곳으로 모은다.** 비즈니스 로직 곳곳에 try-catch를 뿌리지 않는다. 처리는 **중앙 핸들러**(HTTP=advice, gRPC/스트림=경계 매퍼)에서.

**P2. 도메인 실패는 "타입"이다.** raw `RuntimeException`/`String`/불투명 코드로 흘리지 말 것. 실패의 종류를 **명시적 타입**으로 표현해 호출자가 분기·매칭할 수 있게.

**P3. 응답 포맷은 표준·일관.** 클라이언트가 파싱할 수 있는 **하나의 에러 스키마**를 쓴다(HTTP=RFC 9457 ProblemDetail, gRPC=`Status` code+message).

**P4. 원인 체인을 보존한다.** 래핑할 때 원본 원인을 버리지 말 것(`cause`/`#[source]`/`#[from]`). 디버깅의 생명.

**P5. 삼키지 마라(no swallow), 강제 종료하지 마라(no panic on expected).** catch 후 무시·로그만 찍고 정상 반환 금지. **예상 가능한 실패에 `unwrap`/`expect`/`panic`/무근거 `!` 금지** — 예상 실패는 값(`Result`/예외)으로 전파.

**P6. 에러는 관측에 연결한다.** 실패 지점에서 컨텍스트(무엇을 하다 실패했나)를 남기고, 트레이스/로그에 연결(중복 로깅은 금지 — 한 번, 경계에서).

---

## Java / Spring 실현

**중앙화 (P1) — `@RestControllerAdvice`.**
```java
@RestControllerAdvice
class GlobalExceptionHandler extends ResponseEntityExceptionHandler {
    @ExceptionHandler(DocumentNotFoundException.class)
    ProblemDetail handle(DocumentNotFoundException e) {
        var pd = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage());
        pd.setType(URI.create("https://wedocs/errors/document-not-found"));
        pd.setProperty("docId", e.docId());   // 커스텀 필드
        return pd;                              // Content-Type: application/problem+json 자동
    }
}
```
- 컨트롤러엔 try-catch 금지 → 던지고 advice가 받는다(P1).
- `spring.mvc.problemdetails.enabled=true`로 표준 예외도 RFC 9457로(P3).

**타입 (P2) — 도메인 예외 계층.**
```java
// raw RuntimeException("not found") ❌  →  타입 ✅
public sealed class DomainException extends RuntimeException permits DocumentNotFoundException, ... {}
public final class DocumentNotFoundException extends DomainException { ... }
```

**보일러플레이트 (가독성) — Lombok/record 활용.**
- 예외·DTO·값객체의 getter/생성자/equals를 손으로 쓰지 말 것 → `record`(불변 값) 또는 Lombok `@Getter/@RequiredArgsConstructor/@Value`.
- ⚠️ 엔티티(JPA)엔 `@Data`/`@EqualsAndHashCode` 금지(프록시·연관관계 순환). DTO/값객체에만.

**금지 (P5):** `catch (Exception e) {}` 빈 블록 · catch 후 `return null` · `printStackTrace()`.

---

## Rust 실현

**타입 (P2) — 라이브러리/서비스는 `thiserror`.**
```rust
// 현재 엔진 코드: 수동 impl Display + impl Error = 보일러플레이트 (= Rust판 "Lombok 안 씀")
// 개선: thiserror derive로 대체 (원인 체인 #[from]도 공짜)
#[derive(Debug, thiserror::Error)]
pub enum EngineError {
    #[error("unknown doc: {0}")]
    UnknownDoc(String),
    #[error("v1 codec error")]
    Codec(#[from] yrs::error::Error),   // #[from] = 원인 체인 보존(P4) + ? 연동
}
```
- **라이브러리/모듈 = `thiserror`**(호출자가 매칭). **바이너리/최상위 = `anyhow`**(`.context()`로 맥락 누적).

**전파 (P5) — `?` + `Result`, unwrap 금지.**
```rust
let decoded = Update::decode_v1(update)?;        // ❌ .unwrap()  ✅ ?
```
- 프로덕션 경로 `unwrap`/`expect` 금지. **테스트 코드는 예외**(`expect("...")` 허용).
- `.await` 보유 중 락 금지는 concurrency 표준 소관(별도).

**경계 매핑 (P1) — 도메인 에러 → 전송 계층.**
```rust
// gRPC 경계에서 EngineError → tonic::Status 로 한 번 매핑(핸들러 산재 X)
impl From<EngineError> for Status {
    fn from(e: EngineError) -> Self { match e { EngineError::UnknownDoc(_) => Status::not_found(...), ... } }
}
```

**금지 (P5):** 프로덕션 `unwrap`/`expect`/`panic!` · `let _ = result;`로 에러 삼키기(의도적 무시는 근거 주석 필수) · 원인 버리고 `.to_string()`만 남기기(P4 위반).

---

## ✅ 리뷰 체크리스트 (게이트 실행 — 위반 시 반려)

> Gate 3 코드 리뷰에서 `java-expert`/`rust-expert`가 diff에 대고 실행. **[B]=blocking(반려), [A]=advisory(코멘트).**

**공통**
- [ ][B] 비즈니스 로직에 try-catch 산재 없음 → 중앙 핸들러 위임 (P1)
- [ ][B] 실패가 타입으로 표현됨 (raw RuntimeException/String/불투명 코드 아님) (P2)
- [ ][B] 원인 체인 보존 (cause/`#[source]`/`#[from]`) (P4)
- [ ][B] 예외 삼키기(빈 catch·`let _ =`·log-후-정상반환) 없음 (P5)
- [ ][A] 실패 지점에 컨텍스트 로그 1회(중복 로깅 없음) (P6)

**Java/Spring**
- [ ][B] 에러 응답이 `ProblemDetail`(RFC 9457) 일관 포맷 (P3)
- [ ][B] 컨트롤러에 try-catch 없음 · `printStackTrace()` 없음
- [ ][A] 예외/DTO/값객체 보일러플레이트를 `record`/Lombok로 제거 (엔티티엔 `@Data` 금지)

**Rust**
- [ ][B] 프로덕션 경로에 `unwrap`/`expect`/`panic!` 없음 (테스트 제외) (P5)
- [ ][B] 라이브러리/서비스 에러가 `thiserror` derive (수동 `impl Display+Error` 보일러플레이트 아님) (P2)
- [ ][A] 바이너리 최상위는 `anyhow` + `.context()`
- [ ][A] 도메인 에러 → 전송(`tonic::Status` 등) 매핑이 경계 한 곳 (P1)

---

## 게이트 배선 (활용 강제)

1. `code-review.md` 멀티관점에 **🦀 rust-expert / ☕ java-expert 크래프트 렌즈**를 추가 → 이 체크리스트를 실행.
2. `[B]` 위반은 **PR 반려**(수정 후 재리뷰), `[A]`는 코멘트.
3. 리뷰가 새 함정을 잡으면 → `review-gaps.md` 기록 → **이 문서 체크리스트에 한 줄 승격**(gap→standard loop 폐쇄).

---

## 출처

- Spring: [Error Responses (Spring Framework Ref)](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-ann-rest-exceptions.html) · [Baeldung — REST Exception Handling](https://www.baeldung.com/exception-handling-for-rest-with-spring) · RFC 9457(구 7807) Problem Details
- Rust: [thiserror & anyhow 설계](https://oneuptime.com/blog/post/2026-01-25-error-types-thiserror-anyhow-rust/view) · [Momori — thiserror/anyhow 언제 무엇](https://momori.dev/posts/rust-error-handling-thiserror-anyhow/) · Rust API Guidelines(에러 타입)
