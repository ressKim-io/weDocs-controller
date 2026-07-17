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

**P2. 도메인 실패는 "타입"이다.** raw `RuntimeException`/`String`/불투명 코드로 흘리지 말 것. 실패의 종류를 **명시적 타입**으로 표현해 호출자가 분기·매칭할 수 있게. (카탈로그 enum(P7)은 "불투명 코드"가 아니다 — 호출자는 카테고리 타입으로 매칭하고, 코드는 자기서술 slug라 P2의 실현이다. 금지 대상은 `DOC-001`류 의미 없는 번호가 타입 없이 흘러다니는 것.)

**P3. 응답 포맷은 표준·일관.** 클라이언트가 파싱할 수 있는 **하나의 에러 스키마**를 쓴다(HTTP=RFC 9457 ProblemDetail, gRPC=`Status` code+message).

**P4. 원인 체인을 보존한다.** 래핑할 때 원본 원인을 버리지 말 것(`cause`/`#[source]`/`#[from]`). 디버깅의 생명.

**P5. 삼키지 마라(no swallow), 강제 종료하지 마라(no panic on expected).** catch 후 무시·로그만 찍고 정상 반환 금지. **예상 가능한 실패에 `unwrap`/`expect`/`panic`/무근거 `!` 금지** — 예상 실패는 값(`Result`/예외)으로 전파.

**P6. 에러는 관측에 연결한다.** 실패 지점에서 컨텍스트(무엇을 하다 실패했나)를 남기고, 트레이스/로그에 연결(중복 로깅은 금지 — 한 번, 경계에서).

**P7. 실패 전체 집합은 서비스별 에러 카탈로그 하나에 등록한다.** 서비스(=배포 단위, k8s pod)마다 `ErrorCode` enum이 **slug(kebab)·고정 message·HTTP status·gRPC status**를 보유하는 SSOT. 던지는 쪽은 **카테고리 예외 4~5종**(NotFound/Conflict/Forbidden/Unauthorized/InvariantViolation)이 enum 엔트리를 실어 나른다 — 실패 종류마다 leaf 예외 클래스를 늘리지 않는다(종류 추가 = enum 엔트리 1줄). HTTP advice·gRPC 어댑터는 status를 enum 필드에서 읽는다(정상 매핑 경로에 하드코딩 금지).
- **카탈로그 비대상**: ① 요청 데이터가 아닌 **앱 배선·설정 자체의 불변식 위반**(fail-fast — 발생 시점이 기동이든 요청 중이든 성격 기준) ② **경계 입력검증**(Bean Validation 400, gRPC `INVALID_ARGUMENT`) ③ **매핑 누락 안전망**(unmapped → 500/`INTERNAL` 고정 detail — 이 하드코딩은 허용).
- 메시지는 **고정 문구** — id/내부 상태 보간 금지(컨텍스트는 ProblemDetail property·서버 로그로). 근거: RFC 9457 "detail은 파싱 대상이 아님 — 기계 정보는 확장 멤버로", AIP-193 "동적 정보는 message가 아니라 metadata에".

---

## Java / Spring 실현

**카탈로그 (P2+P7) — 서비스별 enum + 카테고리 예외.**
```java
// 서비스별 enum = 실패 전체 집합의 SSOT (slug·고정 message·HTTP·gRPC status)
public enum DocErrorCode {
    PAGE_NOT_FOUND("page-not-found", "page not found", HttpStatus.NOT_FOUND, Status.Code.NOT_FOUND),
    PAGE_CYCLE("page-cycle", "page move would create a cycle", HttpStatus.CONFLICT, Status.Code.FAILED_PRECONDITION),
    // ...
}
// 던지는 타입은 카테고리 4~5종만 — 실패 종류 추가 = enum 엔트리 1줄, leaf 예외 클래스 증식 ❌
public final class NotFoundException extends DomainException {
    public NotFoundException(DocErrorCode code) { super(code); } // 생성자에서 카테고리↔status 정합 검증
}
```

**중앙화 (P1+P7) — `@RestControllerAdvice` 하나, status는 enum에서.**
```java
@RestControllerAdvice
class GlobalExceptionHandler {
    @ExceptionHandler(DomainException.class)
    ProblemDetail handle(DomainException e) {
        var code = e.code();
        var pd = ProblemDetail.forStatusAndDetail(code.http(), code.message()); // 고정 문구(P7)
        pd.setType(URI.create("https://wedocs.io/errors/" + code.slug()));
        pd.setProperty("code", code.slug()); // detail 파싱 금지 → 기계 정보는 확장 멤버(RFC 9457)
        return pd;                           // Content-Type: application/problem+json 자동
    }
}
```
- 컨트롤러엔 try-catch 금지 → 던지고 advice가 받는다(P1).
- `spring.mvc.problemdetails.enabled=true`로 표준 예외도 RFC 9457로(P3).
- gRPC 어댑터도 같은 enum 경유: `Status.fromCode(e.code().grpc()).withDescription(e.code().message())` — 경계 한 곳(P1).

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
- **P7의 Rust 실현 = `thiserror` enum 그 자체가 카탈로그**(variant=엔트리) — 별도 카테고리 클래스 불요. 전송 status의 SSOT는 아래 경계 매핑 한 곳.

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
- [ ][B] 요청 처리 중의 도메인 실패는 **카테고리 예외 + ErrorCode 엔트리**로만 — 실패 종류별 leaf 예외 신설·raw `RuntimeException`/`IllegalState`/`IllegalArgument`로 도메인 실패 표현 금지. 앱 배선·설정 불변식 fail-fast(시점 무관)·경계 입력검증은 비대상 (P7)
- [ ][B] HTTP/gRPC 매핑이 카탈로그 status 필드 경유 — advice·어댑터의 정상 매핑 경로에 상태코드/description 하드코딩 없음. 매핑 누락 안전망(unmapped→500/`INTERNAL` 고정)은 허용 (P7)
- [ ][A] 도메인 에러 메시지는 카탈로그 고정 문구 — id/내부 상태 보간 금지, 컨텍스트는 property·로그로 (P7)
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

> **P7 게이트 시뮬레이션 (2026-07-17, backend `290bf69` doc-service 소급)**: 기대 발화 — leaf 예외 12클래스·`DocMetaService` raw `IllegalStateException`(카탈로그 [B]) / advice 상태 하드코딩 4곳·gRPC `failNotFound` description 하드코딩([B]) / NotFound 계열 uuid 보간([A]). **오탐 0** — `parseUuidOrFail`(경계 검증)·`failInternal`/`handleUnmappedDomain`(안전망)·Bean Validation·`JwtKeys` 등 스타트업 fail-fast·`CurrentUserIdArgumentResolver`(요청 중 발견되는 배선 불변식 — 성격 기준으로 비대상) 전부 비발화. 소급 위반은 [B]가 아니라 [A]+retrofit — `plans/2026-07-17-error-catalog-package-by-feature.md` ③-1이 소거.

---

## 출처

- Spring: [Error Responses (Spring Framework Ref)](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-ann-rest-exceptions.html) · [Baeldung — REST Exception Handling](https://www.baeldung.com/exception-handling-for-rest-with-spring) · [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html)(구 7807) Problem Details
- P7 (✅ verified 2026-07-17, WebFetch): RFC 9457 — "type=문제 유형의 1차 식별자", "detail은 파싱 금지 → 확장 멤버" · [Google AIP-193](https://google.aip.dev/193) — 기계식별자(reason)와 message 분리, 동적 정보는 metadata · [gRPC Status Codes](https://grpc.io/docs/guides/status-codes/) — `FAILED_PRECONDITION`="상태 교정 전 재시도 불가", `INTERNAL`="불변식 파손" · Spring ProblemDetail — `setProperty`가 Jackson mixin으로 top-level JSON 렌더
- Rust: [thiserror & anyhow 설계](https://oneuptime.com/blog/post/2026-01-25-error-types-thiserror-anyhow-rust/view) · [Momori — thiserror/anyhow 언제 무엇](https://momori.dev/posts/rust-error-handling-thiserror-anyhow/) · Rust API Guidelines(에러 타입)
