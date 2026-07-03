---
paths:
  - "**/*.java"
  - "**/*.rs"
  - "**/*.py"
---

# 설계 패턴·구조 판단 표준 (언어 무관 원칙 + 언어별 관용구)

> **위상**: 프로젝트 전체·언어 공통 표준. 개인 컬렉션(`ress-claude-agents`) 승격 대상.
> **왜 있나**: 기존 4종은 "어떻게 짜나"(에러·동시성·계층·관측)를 강제하지만 **"무엇으로 짜나"(추상화 도입 판단·타입 불변식·생성 설계·분기 구조)는 게이트가 없어** 패턴 없는 절차식 코드가 리뷰를 통과한다 — 실증: 엔진 `ServerFrame` 수동 조립 4곳(상호배타 미강제), 게이트웨이 room raw `String` 관통, 다가올 영속화 seam(ADR-0013)엔 경계 추상 판단 기준 자체가 부재. 아는데 안 쓴 것 → 체크리스트로 강제. (availability + verification = activation)
> **다섯 번째 표준(2026-07-03)** — 틀은 `error-handling.md` 복제.
> **역할 분담**: 구체 관용구는 `java.md`(빌더·정적 팩토리·record·sealed)·`spring.md`(계층·DI)·`layering-readability.md`(P3 "타입을 만들라"·함수 분해)·`clean-code.md`(길이·복잡도)가 소유. 이 표준 = **패턴 도입/기각의 판단 기준 + 타입 불변식 강제 + 그 규정들의 게이트화**. 심화: `skills/architecture/`·`skills/spring/effective-java.md`·`skills/spring/spring-patterns.md`.

---

## 원칙 (P) — 언어 무관

**P1. 패턴은 문제가 부른다 (problem-first).** 패턴을 먼저 정해 문제를 끼워 맞추지 않는다. diff에서 **반복 신호**가 관찰될 때만 도입하고, 도입하면 이름을 코드에 남긴다.

| 신호 (diff에서 관찰) | 처방 |
|---|---|
| 같은 대상 생성 코드 2곳+ 중복 / 인자 3+ | 정적 팩토리·빌더·`From` (P5) |
| 같은 variant 분기 3곳+ 산재 | 분기점 단일화 — enum 메서드·sealed switch·전략 (P7) |
| 외부 라이브러리 타입이 모듈 밖으로 확산 | 어댑터 — 자기 타입 래핑 (P2) |
| ADR/plan에 교체·이중화 예정인 지점 | 포트(trait/인터페이스) 경계 (P2) |
| "불법 조합" 방어 주석·런타임 체크 | 타입 강제 — enum/sealed/`oneof` (P4) |

**P2. 추상화는 교체점·경계·시험점에만 — 양방향 가드.** trait/인터페이스는 (a) 교체·이중화가 예정됐거나(ADR/plan 근거) (b) 테스트 대역이 필요하거나 (c) 모듈 공개 경계일 때만 도입한다(과설계 가드). **역으로, 이 3조건이 성립하는 지점을 구체 타입 직결로 새로 짜는 것도 결함**이다(과소설계 가드).

**P3. 의존은 안쪽으로, 순환은 금지.** 모듈 그래프는 DAG. 도메인 로직은 전송(gRPC/WS)·영속(DB)의 구체 타입을 import하지 않는다 — 포트는 도메인이 소유하고 인프라가 구현한다. (`layering-readability.md` P2 = 호출 계층 건너뛰기, 이 원칙 = 컴파일 의존 방향.)

**P4. 불법 상태는 표현 불가능하게.** 상호배타 필드·필수 조합·상태 전이를 주석이나 런타임 체크로 방어하지 말고 **타입**(enum/sealed/proto `oneof`)으로 강제한다. 컴파일러가 잡을 수 있는 것을 리뷰어에게 미루지 않는다.

**P5. 생성이 복잡하면 생성을 설계한다.** 수동 필드 조립의 중복·인자 폭발은 정적 팩토리/빌더/`From` 한 곳으로 모은다. 생성자는 불변식 검증의 **유일한 관문**("Parse, don't validate") — 생성 이후엔 타입이 유효성을 보증한다.

**P6. 도메인 타입은 경계에서 만들어 끝까지 관통.** 경계(핸들러·DTO 매핑)에서 원시값→도메인 타입 변환은 1회, 이후 내부 시그니처에 raw 원시값 재등장 금지. (layering P3가 "타입을 만들라", 이 원칙은 "만든 타입을 끝까지 쓰라".)

**P7. 분기 지점은 하나다.** 같은 variant/타입에 대한 분기가 여러 곳에 복제되면(shotgun switch) 분기점을 단일화한다 — enum 메서드/sealed 전수 switch 한 곳/다형성·전략. `match`/`switch` 자체는 관용구, **산재**가 결함.

---

## Java 실현

**P4/P7 — sealed + `default` 없는 switch 패턴매칭.** 닫힌 계층의 exhaustiveness를 컴파일러에 위임 — 새 variant 추가 시 모든 분기 누락이 컴파일 에러로 드러난다.
```java
public sealed interface InboundFrame permits SyncStep1, SyncStep2, Awareness {}

// ❌ if (f instanceof SyncStep1 s) … else if … else { }   → variant 추가 시 무성음 누락
// ✅ default 없는 switch → variant 추가 = 컴파일 에러
return switch (frame) {
    case SyncStep1 s -> replyStateVector(s);
    case SyncStep2 s -> applyUpdate(s);
    case Awareness a -> drop(a);
};
```

**P2 — 협력자는 DI, `new` 직접 생성 금지.** 스프링 빈을 `new`로 만들면 프록시를 우회해 `@Transactional`/AOP가 조용히 무력화된다(무성음 실버그). 순수 무상태 유틸의 직접 생성만 예외(근거 주석). 생성 관용구 자체(빌더·정적 팩토리·record)는 `java.md` 소유 — 이 표준은 그 게이트.

**P7 — 전략의 스프링 관용구.** 같은 분기가 산재하면 다형 빈 주입으로 분기점을 스프링에 위임:
```java
private final Map<MessageType, FrameHandler> handlers;  // 타입별 빈을 스프링이 수집
```

**P6 — 도메인 타입 관통 (게이트웨이 처방 예고).** 엔진은 `DocId` newtype인데 게이트웨이는 room을 raw `String`으로 관통(폴리레포 비대칭). 처방: 경계(`roomFromUri`)에서 `RoomId` 생성 → 내부 시그니처(`SessionBridge`·`EngineClient`) 관통. 기존 코드 소급은 retrofit plan 몫.

---

## Rust 실현

**P2 — 포트 trait는 ADR이 명시한 seam에만 (양방향 가드의 실례).** ADR-0013 영속화의 실제 seam은 레지스트리 뒤 저장 백엔드가 아니라 **엔진→doc-service 아웃바운드 호출**(`SaveSnapshot`/`LoadSnapshot`) — M2 Phase 3에서 이 경계가 신설될 때 trait로 도입해 시험 대역을 확보한다(3조건 a·b 성립):
```rust
// 신설 예정 경계(ADR-0013 seam)만 trait — 실물 doc-service 없이 영속화 로직 테스트 가능
pub trait SnapshotStore {
    async fn save(&self, id: &DocId, snapshot: Vec<u8>) -> Result<(), EngineError>;
}
```
반면 `DocRegistry`는 교체가 예정되지 않은 내부 구현 — trait를 씌우면 추측성 추상화(과설계 가드 위반). **교체점의 위치는 ADR 원문의 메커니즘으로 특정하고 해석·추측하지 않는다**(게이트 시뮬레이션 2026-07-03에서 오지목이 교정된 사례).

**P4/P5 — 상호배타는 타입으로, 조립은 한 곳으로.** `ServerFrame`의 `state_vector`/`update`는 상호배타인데 struct 병렬 필드라 "둘 다 set"이 표현 가능(게이트웨이가 런타임 경고로 방어 중 = 대칭 결함). 신규 proto 메시지는 `oneof` 우선(기존 메시지 개조는 `buf breaking` 게이트—가드레일 1—통과 전제). proto를 못 바꾸는 동안은 스마트 생성자가 유일 조립 경로:
```rust
impl ServerFrame {
    fn state_vector(doc: &DocId, sv: Vec<u8>) -> Self { /* 단일 관문 — 수동 조립 4곳 제거 */ }
    fn update(doc: &DocId, update: Vec<u8>) -> Self { /* … */ }
}
```

**P5/P6 — validated construction.** 불변식 있는 pub struct는 전 필드 pub 금지, 실패 가능한 변환은 `TryFrom`. `DocId::from`(순수 wrap)은 검증 관문이 없다 → `TryFrom<&str>`(길이·문자집합) — 보안면은 `secure-coding.md` P1과 같은 처방의 양면.

**P2 — 외부 크레이트 타입 격리.** yrs 타입/에러를 pub 경계로 누출하지 않고 자기 타입으로 래핑(어댑터). 단 `EngineError::Codec(String)` 유지 판정(2026-07-01 plan)은 존중 — 변형 세분화는 후속.

**P7 — 반복 match 단일화.** 같은 enum `match`가 3곳+이면 enum에 메서드로 행위를 부착해 분기점을 한 곳으로. 복잡한 상태 전이는 타입스테이트 검토(`skills/architecture/state-machine.md`).

---

## ✅ 리뷰 체크리스트 (게이트 실행 — 위반 시 반려)

> Gate 3에서 `rust-expert`/`java-expert`가 diff에 대고 실행. **[B]=blocking(반려), [A]=advisory(코멘트).**
> **칼리브레이션**: `[B]`는 **diff가 생성·변경하는 코드**에 적용 — diff 밖 기존 위반은 `[A]` 코멘트 + retrofit 이슈로. 정당한 예외는 **근거 주석+이슈 링크**로 `[B]` 통과(escape hatch — 근거 없는 위반만 반려).

**공통**
- [ ][B] 모듈 간 순환 의존 신설 없음 · 도메인이 전송/영속 구체 타입을 import하지 않음 (P3)
- [ ][B] 교체·이중화·시험 대역이 예정된 지점을 구체 결합으로 신규 구현하지 않음 — 경계 추상 또는 근거 주석+이슈. 교체점 위치는 **ADR/plan이 명시한 seam**으로 특정(해석·추측 금지) (P2)
- [ ][B] 상호배타·필수 조합 불변식을 가진 타입을 diff가 **선언하거나 조립**할 때(신규 선언 여부 무관) 타입(enum/sealed/`oneof`)으로 강제 — 타입 변경 불가(proto 소유 등)면 스마트 생성자가 유일 조립 경로 (P4/P5)
- [ ][A] 같은 대상 생성 코드 2곳+ 중복 없음 → 정적 팩토리/빌더/`From` 단일화 (P5)
- [ ][A] 경계에서 만든 도메인 타입이 내부 시그니처를 관통 — raw 재등장 없음 (P6)
- [ ][A] 같은 variant/타입 분기 3곳+ 산재 없음 — 분기점 단일화 (P7)
- [ ][A] 추측성 추상화 신설 없음 — 구현 1개·교체 계획 없음·대역 불필요한 인터페이스/trait 금지 (P1/P2 과설계 가드)

**Java**
- [ ][B] 닫힌 계층 분기에 instanceof-else 체인 없음 → sealed + `default` 없는 switch 또는 다형성 (P4/P7)
- [ ][B] 스프링 빈 협력자를 `new`로 직접 생성하지 않음 — 프록시 우회로 `@Transactional`/AOP 무력화 (P2)
- [ ][A] 인자 3+/선택 인자 생성은 빌더/정적 팩토리 (P5, `java.md` 연동)

**Rust**
- [ ][B] **타입이 강제 가능한 필드 불변식**(범위·필드 간 상호의존)을 가진 신규 pub struct의 전 필드 pub 노출 없음 → 생성자/빌더 경유 validated construction (P5)
- [ ][A] 외부 크레이트 타입(yrs 등)의 pub 경계 누출 없음 → 자기 타입 래핑 (P2)
- [ ][A] **검증이 필요한 값**의 변환에 무검증 `From` 금지 → `TryFrom`(infallible이어도 도메인 불변식이 필요하면 대상 — `secure-coding.md` P1 접점) · 복잡 상태 전이는 타입스테이트 검토 (P4/P5/P6)

> `[B]`는 전부 "타입·경계가 막을 수 있는 무성음 실버그 소지"(순환·프록시 우회·불법 상태·불변식 붕괴)에, 취향 폭이 있는 구조 개선은 `[A]`에 있다 — `layering-readability.md`의 [B]/[A] 경계와 동일 논리.

---

## 게이트 배선 (활용 강제)

`code-review.md` 크래프트 렌즈(🦀 rust-expert / ☕ java-expert)가 이 체크리스트도 실행. `[B]` 위반=반려(escape hatch: 근거 주석+이슈 링크). 새 함정은 `review-gaps.md` → 이 문서 체크리스트로 승격(gap→standard loop).

---

## 출처

- 판단 기준: [Refactoring Guru — 패턴 카탈로그/선택](https://refactoring.guru/design-patterns) · [Parse, don't validate (Alexis King)](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/) · [Effective ML — make illegal states unrepresentable (Yaron Minsky)](https://blog.janestreet.com/effective-ml-revisited/)
- Java: Effective Java 3e(아이템 1·2 — 정적 팩토리·빌더) · [JEP 409 — Sealed Classes](https://openjdk.org/jeps/409) · [Spring — 프록시 기반 AOP(우회 함정)](https://docs.spring.io/spring-framework/reference/core/aop/proxying.html)
- Rust: [Rust Design Patterns — newtype·builder·typestate](https://rust-unofficial.github.io/patterns/) · [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/) · [`TryFrom` 문서](https://doc.rust-lang.org/std/convert/trait.TryFrom.html)
