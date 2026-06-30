---
date: 2026-06-30
category: troubleshoot
tier: 2
importance: major
status: resolved
tags: [m2, doc-service, spring-boot-4, testcontainers-2, flyway, config-contract]
related:
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0013-snapshot-persistence-lifecycle.md
---

# M2 doc-service 1a — Spring Boot 4.x / Testcontainers 2.x 버전 함정 2건

## 무엇

doc-service Phase 1a(데이터 레이어 + Testcontainers 영속 테스트)를 세우며 **메이저 버전 신규 도입 함정 2건**에 막혔다. 둘 다 "라이브러리를 추가했는데 동작 안 함" 패턴 — config-contract-audit의 전형. 후속 Java 모듈(doc-service 1b/1c, M3)에서 재발하므로 기록.

환경: Spring Boot **4.1.0**(BOM이 Testcontainers **2.0.5** 관리) · Java 25 · Gradle 9.1 · Hibernate 7.4.1.

## 함정 1 — Spring Boot 4.x auto-config 모듈화: `flyway-core` jar만으론 Flyway 자동구성 안 됨

**증상**: 테스트가 `org.hibernate.tool.schema.spi.SchemaManagementException: Schema validation: missing table [page_snapshots]`로 실패. 컨테이너는 떴고 DB 연결됨. **Flyway 로그가 전혀 안 찍힘** = 마이그레이션이 아예 안 돎 → 빈 DB에 JPA `validate` → 테이블 없음.

**근본 원인**: Spring Boot 3.x는 `spring-boot-autoconfigure` 한 덩어리에 모든 auto-config가 있어, `org.flywaydb:flyway-core` jar만 추가해도 `FlywayAutoConfiguration`이 켜졌다. **Spring Boot 4.x는 auto-config를 모듈별로 분리**했다 — Flyway 통합·자동구성은 전용 `spring-boot-flyway` 모듈에 있고, 라이브러리 jar만 추가해선 활성화되지 않는다.

**해결**: 베어 라이브러리 대신 **전용 스타터** 사용.
```kotlin
// ❌ Spring Boot 4.x에서 자동구성 안 켜짐
implementation("org.flywaydb:flyway-core")
implementation("org.flywaydb:flyway-database-postgresql")
// ✅
implementation("org.springframework.boot:spring-boot-starter-flyway")
runtimeOnly("org.flywaydb:flyway-database-postgresql") // Flyway 10+ Postgres 방언
```

**전수 적용(회귀 방지)**: Spring Boot 4.x에서 통합 기능은 **`spring-boot-starter-<X>`**로 끌어온다(베어 라이브러리 금지). BOM에 `spring-boot-starter-{flyway,jdbc,data-jpa,session-jdbc,batch-jdbc,...}`가 전부 분리돼 있음(`grep spring-boot-starter spring-boot-dependencies-4.1.0.pom`). doc-service 1b/1c에서 web·security·validation 추가 시 동일 원칙.

## 함정 2 — Testcontainers 2.x 아티팩트 좌표 변경(`testcontainers-` 접두사)

**증상**: `Could not find org.testcontainers:junit-jupiter:` / `org.testcontainers:postgresql:` (버전 빈 값). BOM(spring-boot 4.1.0)이 Testcontainers **2.0.5**를 관리하는데도 해소 실패.

**근본 원인**: Testcontainers **2.x에서 모든 모듈 artifactId에 `testcontainers-` 접두사**가 붙었다. `testcontainers-bom-2.0.5.pom` 확인 결과 `junit-jupiter`/`postgresql`이 아니라 `testcontainers-junit-jupiter`/`testcontainers-postgresql`.

**해결**:
```kotlin
// ❌ TC 1.x 좌표 (2.x BOM에 없음)
testImplementation("org.testcontainers:junit-jupiter")
testImplementation("org.testcontainers:postgresql")
// ✅ TC 2.x
testImplementation("org.testcontainers:testcontainers-junit-jupiter")
testImplementation("org.testcontainers:testcontainers-postgresql")
```
패키지/클래스 경로(`org.testcontainers.containers.PostgreSQLContainer`, `org.testcontainers.junit.jupiter.{Container,Testcontainers}`)는 **유지**됨(컴파일 통과 확인). 좌표만 변경.

## 교훈 / 진단법

- **"라이브러리 추가 = 자동 동작" mental model은 메이저 버전에서 깨진다**(config-contract-audit). Spring Boot 4.x=모듈 분리, TC 2.x=좌표 변경.
- **진단 키**: `validate` 실패 시 "missing table"만 보고 스키마를 의심하지 말 것. **Flyway 로그 부재 = 마이그레이션 미실행**을 먼저 확인(테이블이 진짜 없는 것). XML 결과의 system-out에서 `Migrating schema` 유무로 1초 판별.
- **BOM은 직접 열어 확인**(`~/.gradle/caches/.../spring-boot-dependencies-4.1.0.pom`)했다 — 추측 대신 관리 버전·좌표 확인(deep-thinking).

## 검증

`./gradlew :doc-service:test` → `tests="3" failures="0" errors="0"`. Flyway 7테이블 마이그레이션 + JPA validate + page-tree/snapshot UPSERT 통과.
