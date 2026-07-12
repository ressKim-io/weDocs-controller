---
date: 2026-07-13
category: troubleshoot
tier: 2
importance: major
status: resolved
tags: [m2, doc-service, spring-boot-4, jackson-3, testcontainers-2, webmvc-test, config-contract]
related:
  - dev-logs/2026-06-30-m2-doc-service-1a-version-traps.md
  - plans/2026-07-12-m2-phase1c-rest-jwt.md
---

# M2 doc-service 1c — Spring Boot 4.x 생태계 함정 3건 (테스트 슬라이스·Jackson 3·TC 2.x 클래스)

## 무엇

1c PR①(REST+JWT)에서 **1a와 같은 계열(메이저 버전 신규 도입)의 함정 3건**을 추가로 밟았다. 셋 다 "기존 지식의 좌표/패키지가 Boot 4.x 생태계에서 이동·재설계"된 패턴 — 컴파일 에러로 드러나 즉시 실측(로컬 jar 확인)으로 해소. 후속 Java 작업(1c PR②, Phase 2 gateway REST 테스트, M3)에서 재발 확실이라 기록.

환경: Spring Boot **4.1.0** · Spring Security 7.1.0 · **Jackson 3.1.4** · Testcontainers **2.0.5** · Java 25.

## 함정 1 — `@WebMvcTest`가 `starter-test`에 없다: 테스트 슬라이스도 기술별 스타터로 분리

**증상**: `error: package org.springframework.boot.test.autoconfigure.web.servlet does not exist`.

**근본 원인**: Boot 4.x는 auto-config 모듈화(1a 함정 1)를 **테스트 슬라이스까지 확장**했다. `@WebMvcTest`/`@AutoConfigureMockMvc`는 `spring-boot-starter-test`가 아니라 전용 **`spring-boot-starter-webmvc-test`**에 있고, 패키지도 이동했다.

```java
// ❌ Boot 3.x 패키지 (4.x에 없음)
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
// ✅ Boot 4.x — spring-boot-webmvc-test-4.1.0.jar 실측
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
```

**전수 원칙**: Boot 4.x에서 `@XxxTest` 슬라이스를 쓸 때는 `spring-boot-starter-<기술>-test` 스타터를 먼저 추가하고, import는 IDE 자동완성이 아니라 **jar 내용으로 확인**(`unzip -l`). BOM엔 `-test` 스타터가 기술별로 전부 분리돼 있다(webmvc-test·security-test·jackson-test·validation-test…).

## 함정 2 — Jackson 3 전환: `com.fasterxml.jackson` → `tools.jackson`

**증상**: `package com.fasterxml.jackson.databind does not exist`.

**근본 원인**: Boot 4.x 기본 JSON 스택이 **Jackson 3**. groupId/패키지가 `tools.jackson`으로 바뀌었다(`tools.jackson.core:jackson-databind:3.1.4`). `jackson-annotations`만 2.x 좌표(`com.fasterxml.jackson.core:jackson-annotations:2.21`)로 남아 혼재 — annotations는 하위호환 유지 전략.

```java
// ❌            import com.fasterxml.jackson.databind.ObjectMapper;
// ✅ Jackson 3   import tools.jackson.databind.ObjectMapper;
jsonNode.asText();   // ❌ deprecated
jsonNode.asString(); // ✅ Jackson 3 신 API
```

## 함정 3 — TC 2.x 신규 컨테이너 클래스는 비제네릭 (self-type 제거)

**증상**: 1a에서 좌표만 바꾸고(`testcontainers-postgresql`) 쓰던 `org.testcontainers.containers.PostgreSQLContainer`가 **deprecated 경고**를 냄. 신 패키지로 바꾸자 이번엔 `cannot use '<>' with non-generic class PostgreSQLContainer`.

**근본 원인**: TC 2.x는 신 패키지(`org.testcontainers.postgresql.PostgreSQLContainer`)에서 1.x의 **self-type(CRTP) 제네릭 `<SELF extends …<SELF>>`을 제거**했다. 이 제네릭은 플루언트 체이닝용 트릭일 뿐 데이터 타입 매개화가 아니어서(사용자 코드에 `<?>`/raw 경고만 유발) 타입 안전성 손실 없이 비제네릭으로 재설계된 것. 구 패키지 클래스는 deprecated로 잔존(1a에서 컴파일이 통과한 이유).

```java
// ❌ 1.x 관용구:  PostgreSQLContainer<?> P = new PostgreSQLContainer<>("postgres:16-alpine");
// ✅ 2.x 신형:    PostgreSQLContainer P = new PostgreSQLContainer("postgres:16-alpine");
//                (import org.testcontainers.postgresql.PostgreSQLContainer)
```

기존 1a/1b 테스트 4파일도 전수 정리(debugging.md 패턴 전수 스캔, backend `3b89975`).

## 교훈 / 진단법

- **1a 교훈의 확장**: "라이브러리 추가=자동 동작" 붕괴가 **테스트 인프라·JSON 스택·컨테이너 클래스 설계**까지 미친다. Boot 4.x에서 컴파일 에러가 나면 좌표→패키지→클래스 시그니처 순으로 이동을 의심.
- **진단 키**: 로컬 Gradle 캐시 jar를 직접 연다 — `find ~/.gradle/caches -name "<artifact>*.jar" | head -1` → `unzip -l | grep <Class>`. 추측·블로그보다 빠르고 정확(deep-thinking).
- **deprecation 0 유지**: `-Xlint:deprecation` 일회 컴파일(init script)로 조용한 deprecated 사용을 주기 점검 — 이번에 TC 구 패키지·`asText()`를 잡았다.

## 검증

`./gradlew :doc-service:test` 49건 green + `-Xlint:deprecation` 경고 0 + `:doc-service:build` green.
