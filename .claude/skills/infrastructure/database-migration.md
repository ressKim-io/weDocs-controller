---
name: database-migration
description: "Database Migration Patterns — Flyway, Liquibase, golang-migrate, 안전한 스키마 변경 패턴 Use when working with infrastructure 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Database Migration Patterns

Flyway, Liquibase, golang-migrate, 안전한 스키마 변경 패턴

## Quick Reference (결정 트리)

```
마이그레이션 도구 선택
    │
    ├─ 단순함 우선 ────────> Flyway (SQL 기반)
    │
    ├─ 복잡한 환경 ────────> Liquibase (YAML/XML, 롤백)
    │
    └─ Go 프로젝트 ────────> golang-migrate

스키마 변경
    │
    ├─ 컬럼 추가 ──────────> ALTER TABLE ADD (안전)
    │
    ├─ 인덱스 생성 ────────> CREATE INDEX CONCURRENTLY
    │
    └─ NOT NULL 추가 ─────> 3단계 (컬럼 추가 → 데이터 채움 → 제약 추가)
```

---

## Flyway (권장: 단순함)

### 네이밍 규칙

```
V{version}__{description}.sql

V1__Create_users_table.sql
V2__Add_email_to_users.sql
V3__Create_orders_table.sql
R__Refresh_views.sql         (Repeatable - 매번 실행)
```

### Spring Boot 설정

```yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true
```

### 마이그레이션 예시

```sql
-- V1__Create_users_table.sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status) WHERE status = 'active';
```

---

## Liquibase (권장: 복잡한 환경)

### 구조

```yaml
# db/changelog/db.changelog-master.yaml
databaseChangeLog:
  - include:
      file: db/changelog/changes/001-create-users.yaml
  - include:
      file: db/changelog/changes/002-add-orders.yaml
```

### ChangeSet 예시

```yaml
# db/changelog/changes/001-create-users.yaml
databaseChangeLog:
  - changeSet:
      id: 1
      author: developer
      changes:
        - createTable:
            tableName: users
            columns:
              - column:
                  name: id
                  type: bigint
                  autoIncrement: true
                  constraints:
                    primaryKey: true
              - column:
                  name: email
                  type: varchar(255)
                  constraints:
                    nullable: false
                    unique: true
```

### 장점

- 롤백 자동 생성
- 다양한 DB 지원 (DB 간 이식성)
- 변경 추적 용이

---

## golang-migrate (Go)

### 설치

```bash
go install -tags 'postgres' github.com/golang-migrate/migrate/v4/cmd/migrate@latest
```

### 마이그레이션 생성

```bash
migrate create -ext sql -dir migrations -seq create_users_table
```

```sql
-- migrations/000001_create_users_table.up.sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- migrations/000001_create_users_table.down.sql
DROP TABLE IF EXISTS users;
```

### 코드에서 실행

```go
import "github.com/golang-migrate/migrate/v4"

m, err := migrate.New(
    "file://migrations",
    "postgres://user:pass@localhost:5432/mydb?sslmode=disable",
)
if err != nil {
    log.Fatal(err)
}

if err := m.Up(); err != nil && err != migrate.ErrNoChange {
    log.Fatal(err)
}
```

---

## CRITICAL: 안전한 스키마 변경

### 1. 컬럼 추가 (안전)

```sql
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
```

### 2. 인덱스 생성 (락 없이)

```sql
-- CONCURRENTLY: 테이블 락 없이 인덱스 생성
CREATE INDEX CONCURRENTLY idx_users_phone ON users(phone);
```

### 3. NOT NULL 추가 (3단계)

**IMPORTANT**: 한 번에 NOT NULL 추가하면 테이블 풀 스캔 발생

```sql
-- Step 1: 컬럼 추가 (nullable)
ALTER TABLE users ADD COLUMN country VARCHAR(50);

-- Step 2: 기존 데이터 업데이트
UPDATE users SET country = 'KR' WHERE country IS NULL;

-- Step 3: NOT NULL 제약 추가
ALTER TABLE users ALTER COLUMN country SET NOT NULL;
```

### 4. 컬럼 삭제 (역순)

```sql
-- Step 1: 앱에서 사용 중지 (코드 배포)
-- Step 2: 마이그레이션에서 삭제
ALTER TABLE users DROP COLUMN old_column;
```

### 5. 컬럼 타입 변경 (신중하게)

```sql
-- 안전: VARCHAR 길이 증가
ALTER TABLE users ALTER COLUMN name TYPE VARCHAR(200);

-- 위험: 타입 변경 (데이터 검증 필요)
ALTER TABLE users ALTER COLUMN age TYPE INTEGER USING age::integer;
```

---

## 통계 업데이트

```sql
-- 마이그레이션 후 반드시 실행
ANALYZE users;
ANALYZE orders;

-- 전체 DB
ANALYZE;
```

---

## Anti-Patterns

| 실수 | 올바른 방법 |
|------|------------|
| 직접 프로덕션 DDL | 마이그레이션 도구 사용 |
| 롤백 스크립트 없음 | up/down 스크립트 쌍 |
| 락 걸리는 인덱스 생성 | `CREATE INDEX CONCURRENTLY` |
| NOT NULL 바로 추가 | 3단계 접근법 |
| 테스트 없이 프로덕션 | 스테이징에서 먼저 실행 |
| 대용량 테이블 한 번에 변경 | 배치로 나눠서 |

---

## 체크리스트

### 마이그레이션 작성
- [ ] 버전 관리 도구 사용 (Flyway/Liquibase/golang-migrate)
- [ ] 롤백 스크립트 준비
- [ ] 네이밍 규칙 준수

### 배포 전
- [ ] 스테이징 환경에서 테스트
- [ ] 예상 실행 시간 확인
- [ ] 백업 준비

### 배포 후
- [ ] ANALYZE 실행 (통계 업데이트)
- [ ] 쿼리 성능 모니터링
- [ ] 롤백 준비
