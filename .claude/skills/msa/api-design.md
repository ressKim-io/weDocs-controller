---
name: api-design
description: "REST API Design Patterns — REST API 설계 원칙, RFC 9457 에러 처리, 페이지네이션, 버저닝 Use when working with msa 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# REST API Design Patterns

REST API 설계 원칙, RFC 9457 에러 처리, 페이지네이션, 버저닝

## Quick Reference (결정 트리)

```
API 설계 시작
    │
    ├─ URL 설계 ──────> 명사, 복수형, 케밥케이스
    │
    ├─ 에러 응답 ─────> RFC 9457 (Problem Details)
    │
    ├─ 페이지네이션
    │   ├─ 실시간/대용량 ──> Cursor 기반 (권장)
    │   └─ 페이지 이동 필요 ─> Offset 기반
    │
    └─ 버저닝 ────────> URL Path (/v1/)
```

---

## URL 설계 원칙

| 규칙 | Good | Bad |
|------|------|-----|
| 명사 사용 | `/orders` | `/createOrder` |
| 복수형 | `/users/123` | `/user/123` |
| 케밥케이스 | `/order-items` | `/orderItems` |
| 계층 관계 | `/users/123/orders` | `/orders?userId=123` |

### HTTP 메서드

| 메서드 | 용도 | 멱등성 |
|--------|------|--------|
| GET | 조회 | ✅ |
| POST | 생성 | ❌ |
| PUT | 전체 수정 | ✅ |
| PATCH | 부분 수정 | ✅ |
| DELETE | 삭제 | ✅ |

### 비-CRUD 액션

```
# Bad
POST /orders/123/cancel

# Good: 명사화
POST /orders/123/cancellation

# Good: 상태 변경
PATCH /orders/123 { "status": "cancelled" }
```

---

## CRITICAL: RFC 9457 에러 응답

**IMPORTANT**: 모든 API 에러는 RFC 9457 형식 사용

```json
{
  "type": "https://api.example.com/errors/insufficient-funds",
  "title": "Insufficient Funds",
  "status": 400,
  "detail": "Your balance is $30, but requires $50.",
  "instance": "/accounts/123/transactions/456"
}
```

| 필드 | 설명 |
|------|------|
| `type` | 에러 유형 URI (문서 링크) |
| `title` | 에러 요약 (고정) |
| `status` | HTTP 상태 코드 |
| `detail` | 구체적 설명 (클라이언트용) |
| `instance` | 발생 리소스 URI |

### HTTP 상태 코드

```
2xx 성공: 200 OK, 201 Created, 204 No Content
4xx 클라이언트: 400 Bad Request, 401 Unauthorized, 403 Forbidden,
               404 Not Found, 409 Conflict, 422 Unprocessable, 429 Rate Limit
5xx 서버: 500 Internal, 502 Bad Gateway, 503 Unavailable
```

### Spring Boot 구현

```java
@RestControllerAdvice
public class GlobalExceptionHandler extends ResponseEntityExceptionHandler {
    @ExceptionHandler(ResourceNotFoundException.class)
    public ProblemDetail handleNotFound(ResourceNotFoundException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
            HttpStatus.NOT_FOUND, ex.getMessage());
        problem.setType(URI.create("https://api.example.com/errors/not-found"));
        return problem;
    }
}
```

### Go 구현

```go
type ProblemDetail struct {
    Type     string `json:"type,omitempty"`
    Title    string `json:"title"`
    Status   int    `json:"status"`
    Detail   string `json:"detail,omitempty"`
    Instance string `json:"instance,omitempty"`
}
```

---

## 페이지네이션

### Offset vs Cursor

| | Offset | Cursor (권장) |
|---|--------|---------------|
| 용도 | 페이지 이동 | 실시간/대용량 |
| 성능 | 큰 offset 시 느림 | 일정한 성능 |
| 데이터 변경 | 중복/누락 가능 | 안정적 |

### Cursor 기반 (권장)

```
GET /users?cursor=eyJpZCI6MTIzfQ&limit=20
```

```json
{
  "data": [...],
  "pagination": {
    "limit": 20,
    "hasNext": true,
    "nextCursor": "eyJpZCI6MTQzfQ"
  }
}
```

### 기본값 및 제한

```java
@GetMapping("/users")
public Page<User> getUsers(
    @RequestParam(defaultValue = "0") int page,
    @RequestParam(defaultValue = "20") int limit) {
    int safeLimit = Math.min(limit, 100);  // 최대 100 (DoS 방지)
    return userService.findAll(PageRequest.of(page, safeLimit));
}
```

---

## 필터링 & 정렬

```
# 필터링
GET /users?status=active&role=admin
GET /products?price[gte]=100&price[lte]=500

# 정렬 (- 는 DESC)
GET /users?sort=-created_at,name

# 필드 선택
GET /users?fields=id,name,email
```

---

## 응답 구조

### 단일 리소스

```json
{
  "id": 123,
  "name": "John Doe",
  "email": "john@example.com",
  "createdAt": "2025-01-24T10:30:00Z",
  "links": {
    "self": "/users/123",
    "orders": "/users/123/orders"
  }
}
```

### 컬렉션

```json
{
  "data": [...],
  "meta": { "total": 150, "page": 1, "limit": 20 },
  "links": { "self": "/users?page=1", "next": "/users?page=2" }
}
```

### 날짜/시간 (ISO 8601 + UTC)

```
"createdAt": "2025-01-24T10:30:00Z"
"scheduledAt": "2025-01-24T10:30:00+09:00"
```

---

## 버저닝

**권장: URL Path**
```
GET /v1/users
GET /v2/users
```

### Breaking Change 기준

| Breaking (버전 업) | Non-Breaking |
|-------------------|--------------|
| 필드 삭제 | 필드 추가 |
| 필드 타입 변경 | 선택적 파라미터 추가 |
| 필수 파라미터 추가 | 에러 메시지 개선 |

---

## 보안

```
# 필수 헤더
Content-Type: application/json
Authorization: Bearer <token>
X-Request-ID: uuid

# Rate Limiting 헤더
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
```

**IMPORTANT**: 프로덕션 에러 응답에서 숨길 것:
- 내부 스택트레이스
- DB 쿼리
- 서버 경로

---

## Anti-Patterns

| 실수 | 올바른 방법 |
|------|------------|
| `GET /getUsers` | `GET /users` |
| `POST /users/123/delete` | `DELETE /users/123` |
| 에러에 200 반환 | 적절한 4xx/5xx |
| 에러 형식 불일치 | RFC 9457 표준 |
| SELECT * 응답 | 필요한 필드만 |
| 버전 없이 배포 | `/v1/` 처음부터 |

---

## 체크리스트

### URL 설계
- [ ] 명사, 복수형, 소문자, 케밥케이스
- [ ] 버전 포함 (`/v1/`)

### 에러 처리
- [ ] RFC 9457 형식
- [ ] 적절한 HTTP 상태 코드
- [ ] 프로덕션에서 내부 정보 숨김

### 페이지네이션
- [ ] 기본값 (limit=20)
- [ ] 최대값 제한 (max=100)

### 보안
- [ ] Rate Limiting
- [ ] 입력 검증
