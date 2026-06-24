---
name: auth-patterns
description: "Authentication & Authorization Patterns 가이드 — OAuth2/OIDC, PKCE, JWT, Session, API Key 인증/인가 패턴 및 구현 가이드 Use when working with security 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Authentication & Authorization Patterns 가이드

OAuth2/OIDC, PKCE, JWT, Session, API Key 인증/인가 패턴 및 구현 가이드

## Quick Reference (결정 트리)

```
인증 방식 선택?
    │
    ├─ SPA/모바일 앱 ────────> OAuth2 + PKCE (Authorization Code)
    ├─ 서버간 통신 ──────────> Client Credentials Grant
    ├─ 전통적 웹 앱 ─────────> Session-based (HttpOnly Cookie)
    ├─ 마이크로서비스 내부 ──> JWT + mTLS
    ├─ 외부 API 제공 ────────> API Key + Rate Limiting
    └─ SSO 통합 ─────────────> OIDC (OpenID Connect)

토큰 저장 위치?
    │
    ├─ 브라우저 웹 앱 ───────> HttpOnly + Secure + SameSite Cookie
    ├─ SPA (BFF 패턴) ──────> Backend에서 쿠키 관리
    ├─ 모바일 앱 ────────────> Secure Storage (Keychain/Keystore)
    └─ 서버/CLI ─────────────> 환경변수 또는 Vault

인가 모델?
    │
    ├─ 역할 기반 ────────────> RBAC (Role-Based Access Control)
    ├─ 속성 기반 ────────────> ABAC (Attribute-Based Access Control)
    ├─ 관계 기반 ────────────> ReBAC (Relationship-Based AC)
    └─ 하이브리드 ──────────> RBAC + ABAC 조합
```

---

## OAuth2 Flows

### Authorization Code + PKCE (SPA/모바일 권장)

```
┌──────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│Client│     │Auth Server│     │  Token   │     │ Resource │
│(SPA) │     │ /authorize│     │ Endpoint │     │  Server  │
└──┬───┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
   │               │               │               │
   │ 1. code_challenge              │               │
   │   + code_challenge_method=S256 │               │
   │──────────────>│               │               │
   │               │               │               │
   │ 2. auth_code  │               │               │
   │<──────────────│               │               │
   │               │               │               │
   │ 3. auth_code + code_verifier  │               │
   │──────────────────────────────>│               │
   │               │               │               │
   │ 4. access_token + refresh_token               │
   │<──────────────────────────────│               │
   │               │               │               │
   │ 5. API call (Bearer token)    │               │
   │──────────────────────────────────────────────>│
```

### PKCE 구현

```typescript
// TypeScript: PKCE 코드 생성
import crypto from 'crypto';

function generateCodeVerifier(): string {
  return crypto.randomBytes(32).toString('base64url');
}

function generateCodeChallenge(verifier: string): string {
  return crypto.createHash('sha256').update(verifier).digest('base64url');
}

// 인증 요청 시
const codeVerifier = generateCodeVerifier();
const codeChallenge = generateCodeChallenge(codeVerifier);

const authUrl = new URL('https://auth.example.com/authorize');
authUrl.searchParams.set('response_type', 'code');
authUrl.searchParams.set('client_id', clientId);
authUrl.searchParams.set('redirect_uri', redirectUri);
authUrl.searchParams.set('code_challenge', codeChallenge);
authUrl.searchParams.set('code_challenge_method', 'S256');
authUrl.searchParams.set('scope', 'openid profile email');
```

### Client Credentials Grant (서버간 통신)

```go
// Go: Client Credentials 토큰 요청
func getServiceToken(clientID, clientSecret, tokenURL string) (string, error) {
    data := url.Values{
        "grant_type":    {"client_credentials"},
        "client_id":     {clientID},
        "client_secret": {clientSecret},
        "scope":         {"api:read api:write"},
    }
    resp, err := http.PostForm(tokenURL, data)
    if err != nil {
        return "", fmt.Errorf("token request failed: %w", err)
    }
    defer resp.Body.Close()

    var result struct {
        AccessToken string `json:"access_token"`
        ExpiresIn   int    `json:"expires_in"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return "", fmt.Errorf("token decode failed: %w", err)
    }
    return result.AccessToken, nil
}
```

---

## OIDC (OpenID Connect)

OAuth2 위에 인증(Authentication) 레이어를 추가한 프로토콜.

### ID Token vs Access Token

| 구분 | ID Token | Access Token |
|------|----------|-------------|
| 목적 | 사용자 인증 (누구인가) | 리소스 접근 인가 (무엇을 할 수 있는가) |
| 대상 | Client (RP) | Resource Server (API) |
| 형식 | 항상 JWT | JWT 또는 opaque |
| 검증 주체 | Client | Resource Server |
| 포함 정보 | sub, email, name 등 | scope, permissions |
| 전송 | Client에서만 사용 | API 호출 시 Bearer 헤더 |

### ID Token Claims

```json
{
  "iss": "https://auth.example.com",
  "sub": "user-uuid-1234",
  "aud": "client-id-5678",
  "exp": 1700000000,
  "iat": 1699999000,
  "nonce": "random-nonce-value",
  "email": "user@example.com",
  "email_verified": true,
  "name": "홍길동"
}
```

### UserInfo Endpoint

```python
# Python: OIDC UserInfo 요청
import httpx

async def get_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://auth.example.com/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        resp.raise_for_status()
        return resp.json()
```

---

## JWT 심화

### JWT 구조와 서명 알고리즘

```
Header.Payload.Signature

서명 알고리즘 선택:
  RS256 (RSA + SHA-256)
    - 비대칭 키: 서명(private key) / 검증(public key)
    - 마이크로서비스 환경에 적합 (public key만 배포)
    - 키 크기: 2048bit 이상

  ES256 (ECDSA + P-256)
    - 비대칭 키, RS256보다 작은 키와 서명
    - 성능 우수, 모바일/IoT 적합

  HS256 (HMAC + SHA-256)
    - 대칭 키: 동일 키로 서명/검증
    - 단일 서비스 내부에서만 사용
    - 키 공유 필요 → MSA에서 부적합

  금지: none, HS256(공개키를 secret으로 오용하는 공격 주의)
```

### JWT 검증 구현

```java
// Java: JWT 검증 (RS256)
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

public class JwtValidator {
    private final PublicKey publicKey;

    public Claims validate(String token) {
        return Jwts.parserBuilder()
            .setSigningKey(publicKey)
            .requireIssuer("https://auth.example.com")
            .requireAudience("my-api")
            .build()
            .parseClaimsJws(token)
            .getBody();
    }
}
```

```go
// Go: JWT 검증 미들웨어
func JWTMiddleware(publicKey *rsa.PublicKey) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            tokenStr := extractBearerToken(r)
            token, err := jwt.Parse(tokenStr, func(t *jwt.Token) (interface{}, error) {
                if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
                    return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
                }
                return publicKey, nil
            })
            if err != nil || !token.Valid {
                http.Error(w, "Unauthorized", http.StatusUnauthorized)
                return
            }
            claims := token.Claims.(jwt.MapClaims)
            ctx := context.WithValue(r.Context(), "claims", claims)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

### Refresh Token 전략

```
Refresh Token Rotation:
  1. Client가 refresh_token으로 새 토큰 요청
  2. 서버가 새 access_token + 새 refresh_token 발급
  3. 기존 refresh_token 즉시 무효화
  4. 재사용 탐지: 무효화된 토큰 사용 시 전체 세션 강제 종료

설정 권장값:
  - Access Token TTL: 15분
  - Refresh Token TTL: 7일 (Rotation 적용 시)
  - Absolute Session TTL: 30일
```

---

## Session-based Authentication

### 세션 구현

```python
# Python/FastAPI: Redis 세션 관리
import secrets
import redis.asyncio as redis

SESSION_TTL = 1800  # 30분

class SessionManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def create(self, user_id: str, metadata: dict) -> str:
        session_id = secrets.token_urlsafe(32)  # 128bit random
        await self.redis.hset(f"session:{session_id}", mapping={
            "user_id": user_id,
            "created_at": str(time.time()),
            **metadata,
        })
        await self.redis.expire(f"session:{session_id}", SESSION_TTL)
        return session_id

    async def validate(self, session_id: str) -> dict | None:
        data = await self.redis.hgetall(f"session:{session_id}")
        if not data:
            return None
        # 슬라이딩 만료 갱신
        await self.redis.expire(f"session:{session_id}", SESSION_TTL)
        return data

    async def destroy(self, session_id: str) -> None:
        await self.redis.delete(f"session:{session_id}")
```

### CSRF 방어

```
SameSite Cookie 속성:
  - Strict: 외부 사이트에서 쿠키 전송 차단 (가장 안전)
  - Lax: 안전한 메서드(GET)에만 쿠키 허용 (기본값 권장)
  - None: 모든 요청에 쿠키 허용 (Secure 필수, 가능하면 피할 것)

Double Submit Cookie:
  1. 서버가 CSRF 토큰을 non-HttpOnly 쿠키로 설정
  2. Client가 요청 시 쿠키 값을 커스텀 헤더(X-CSRF-Token)에 복사
  3. 서버가 쿠키와 헤더 값 일치 확인
```

### 세션 쿠키 설정

```java
// Java/Spring: 보안 세션 쿠키
@Configuration
public class SessionConfig {
    @Bean
    public CookieSerializer cookieSerializer() {
        DefaultCookieSerializer serializer = new DefaultCookieSerializer();
        serializer.setCookieName("SESSION_ID");
        serializer.setUseHttpOnlyCookie(true);   // XSS 방어
        serializer.setUseSecureCookie(true);      // HTTPS 전용
        serializer.setSameSite("Lax");            // CSRF 방어
        serializer.setCookiePath("/");
        serializer.setCookieMaxAge(1800);         // 30분
        return serializer;
    }
}
```

---

## API Key 패턴

### 키 생성 및 관리

```go
// Go: API Key 생성 및 해시 저장
import (
    "crypto/rand"
    "crypto/sha256"
    "encoding/hex"
)

func GenerateAPIKey() (plainKey string, hashedKey string, err error) {
    bytes := make([]byte, 32)
    if _, err = rand.Read(bytes); err != nil {
        return "", "", err
    }
    plainKey = "sk_live_" + hex.EncodeToString(bytes)
    hash := sha256.Sum256([]byte(plainKey))
    hashedKey = hex.EncodeToString(hash[:])
    return plainKey, hashedKey, nil
    // plainKey: 사용자에게 1회만 표시
    // hashedKey: DB에 저장 (원문 저장 금지)
}
```

### API Key 검증 + Rate Limiting

```
API Key 보안 원칙:
  1. 해시하여 저장 (SHA-256), 원문 저장 금지
  2. Scope 제한: read-only, write, admin 구분
  3. IP 화이트리스트 연동
  4. Rate Limiting: 키별 분당/시간당 호출 제한
  5. 만료일 설정: 90일 이내 자동 만료
  6. 사용 로그: 모든 API Key 사용 기록
  7. 긴급 폐기: 즉시 무효화 메커니즘
```

---

## RBAC vs ABAC vs ReBAC

### 비교

| 모델 | 접근 결정 기준 | 적합한 시나리오 | 복잡도 |
|------|-------------|-------------|--------|
| RBAC | 역할 (Admin, Editor, Viewer) | 조직 구조가 명확한 시스템 | 낮음 |
| ABAC | 속성 (부서, 시간, IP, 데이터 분류) | 세밀한 접근 제어 필요 시 | 중간 |
| ReBAC | 관계 (소유자, 공유 대상, 조직 멤버) | Google Drive, Notion 같은 공유 모델 | 높음 |

### RBAC 구현

```java
// Java/Spring: RBAC
@PreAuthorize("hasRole('ADMIN')")
@DeleteMapping("/users/{id}")
public void deleteUser(@PathVariable Long id) { ... }

@PreAuthorize("hasAnyRole('ADMIN', 'EDITOR')")
@PutMapping("/articles/{id}")
public Article updateArticle(@PathVariable Long id, @RequestBody ArticleDto dto) { ... }
```

### ABAC 구현

```python
# Python: ABAC 정책 평가
class ABACPolicy:
    def evaluate(self, subject: dict, resource: dict, action: str, context: dict) -> bool:
        # 업무 시간 내 접근만 허용
        if context.get("hour") not in range(9, 18):
            return False
        # 동일 부서 데이터만 접근 허용
        if subject.get("department") != resource.get("department"):
            return False
        # 민감 데이터는 매니저 이상만 접근
        if resource.get("classification") == "sensitive":
            return subject.get("level") >= 3
        return True
```

---

## Multi-tenancy 인증

### JWT에 Tenant 정보 포함

```json
{
  "sub": "user-uuid",
  "iss": "https://auth.example.com",
  "tenant_id": "org-abc123",
  "roles": ["admin"],
  "permissions": ["read:users", "write:users"]
}
```

### Tenant 격리 패턴

```
Schema-per-Tenant:
  - 각 tenant가 별도 DB 스키마 사용
  - 완전한 데이터 격리
  - 단점: 스키마 마이그레이션 복잡

Row-Level Security:
  - 모든 테이블에 tenant_id 컬럼
  - DB 레벨 RLS 정책 적용
  - PostgreSQL: CREATE POLICY, SET app.tenant_id

미들웨어 검증:
  - 모든 쿼리에 WHERE tenant_id = :current_tenant 강제
  - ORM 레벨에서 자동 필터링 (Hibernate Filter, Django Manager)
```

---

## Anti-Patterns

| Anti-Pattern | 위험 | 올바른 접근 |
|-------------|------|-----------|
| JWT를 세션처럼 사용 | JWT는 발급 후 revocation 어려움, 로그아웃 불완전 | 짧은 TTL + Refresh Token Rotation |
| Access Token을 localStorage에 저장 | XSS로 토큰 탈취 가능 | HttpOnly Cookie 또는 BFF 패턴 |
| HS256 + 공개키 혼동 | RS256 public key를 HS256 secret으로 사용하는 알고리즘 혼동 공격 | 알고리즘 명시적 검증 (allowlist) |
| Refresh Token 미갱신 | 탈취된 Refresh Token이 장기간 유효 | Refresh Token Rotation 필수 |
| 비밀번호 평문 저장/전송 | 데이터 유출 시 즉각적 대규모 피해 | bcrypt/Argon2id 해싱, TLS 전송 |
| API Key를 URL에 포함 | 서버 로그, 브라우저 히스토리에 노출 | Authorization 헤더로 전달 |
| CORS: Access-Control-Allow-Origin: * | 모든 사이트에서 인증된 요청 가능 | 명시적 origin 허용 목록 |
| 자체 인증 프로토콜 구현 | 검증되지 않은 구현은 취약점 내포 | 표준 프로토콜 사용 (OAuth2, OIDC) |

---

## Security Headers for Auth

```
# 인증 관련 필수 HTTP 보안 헤더
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Cache-Control: no-store
Pragma: no-cache
```

---

## Sources

| 출처 | URL |
|------|-----|
| OAuth 2.1 Draft | https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-10 |
| OpenID Connect Core 1.0 | https://openid.net/specs/openid-connect-core-1_0.html |
| RFC 7636 (PKCE) | https://datatracker.ietf.org/doc/html/rfc7636 |
| RFC 7519 (JWT) | https://datatracker.ietf.org/doc/html/rfc7519 |
| OWASP Auth Cheat Sheet | https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html |
| OWASP Session Management | https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html |

---

## Related Skills

| 스킬 | 용도 |
|------|------|
| `security/owasp-top10` | OWASP Top 10 취약점 방어 (A01, A07) |
| `security/secure-coding` | 입력 검증, 암호화 구현 패턴 |
| `security/threat-modeling` | STRIDE 기반 인증 위협 분석 |
| `service-mesh/istio-security` | mTLS, AuthorizationPolicy |
| `msa/api-gateway` | API Gateway 인증/인가 패턴 |
