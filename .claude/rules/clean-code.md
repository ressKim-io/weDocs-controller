# Clean Code 원칙 (언어 공통)

모든 코드 작성 및 리뷰 시 적용되는 핵심 가독성 원칙.

## 메서드/함수 길이

- PREFER 20-50줄 이내로 유지 (실무 sweet spot)
- 50줄 초과 시 MUST 분할 검토 — 단일 책임 위반 가능성
- 100줄 초과 NEVER — SonarQube/Checkstyle 기본 경고 수준
- **Cognitive Complexity ≤ 15** (줄 수보다 중요) — 중첩 깊이에 비례하는 인지 부하 측정

## Guard Clause (Early Return)

MUST 중첩 조건문 대신 조기 반환으로 happy path를 최외곽에 배치.

```
// BAD: 중첩 피라미드
if (valid) {
    if (authorized) {
        if (available) {
            // 핵심 로직이 3단 중첩 안에 묻힘
        }
    }
}

// GOOD: Guard Clause
if (!valid) return error;
if (!authorized) return forbidden;
if (!available) return unavailable;
// 핵심 로직이 최외곽 스코프
```

## 주석 철학

- MUST 주석은 **WHY**(왜 이렇게 했는가)만 작성
- NEVER WHAT(무엇을 하는가) / HOW(어떻게 하는가) 주석 — 코드 자체가 표현해야 함
- PREFER 비즈니스 규칙, 비자명한 최적화, 외부 시스템 우회 사유에 주석
- NEVER `// counter 증가` 같은 코드 반복 주석

## 네이밍

- MUST 의도를 드러내는 이름 (Intention-Revealing Names)
- NEVER 축약어 남용 — `usr`, `proc`, `mgr` 대신 `user`, `processor`, `manager`
- MUST Boolean은 `is/has/can/should` 접두사 사용
- MUST Enum/상수로 매직 넘버 제거 — `if (status == 3)` 금지
- PREFER 도메인 용어(Ubiquitous Language) 사용

## Tell, Don't Ask

객체 상태를 꺼내서 외부에서 판단하지 말고, 객체에게 행동을 위임하라.

```
// BAD: 상태를 꺼내서 외부 판단
if (account.getBalance() > amount) {
    account.setBalance(account.getBalance() - amount);
}

// GOOD: 객체가 자신의 로직을 수행
account.withdraw(amount);
```

## 추상화 수준 통일 (SLAP)

한 메서드 안의 모든 코드는 같은 추상화 수준이어야 한다.
고수준 비즈니스 흐름과 저수준 구현 세부사항이 섞이면 MUST 추출.

## 가독성 vs 성능

- MUST 프로파일링 먼저, 최적화는 나중에
- NEVER 측정 없이 가독성을 희생하는 최적화
- 예외: 핫 패스(초당 수만 호출)는 성능 우선 후 주석으로 사유 명시

---

상세 가이드 및 언어별 예시: `/clean-code` 스킬 참조
