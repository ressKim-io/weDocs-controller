---
name: secure-coding
description: "Secure Coding Practices 가이드 — 언어별 시큐어 코딩, 입력 검증, 암호화 패턴, 에러 처리, 보안 헤더 Use when working with security 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Secure Coding Practices 가이드

언어별 시큐어 코딩, 입력 검증, 암호화 패턴, 에러 처리, 보안 헤더

## Quick Reference (결정 트리)

```
보안 코딩 영역?
    │
    ├─ 입력 검증 ──────────> Input Validation & Sanitization
    ├─ 출력 인코딩 ────────> Output Encoding (XSS 방어)
    ├─ 암호화 ─────────────> Encryption at Rest & in Transit
    ├─ 에러 처리 ──────────> Secure Error Handling
    ├─ 파일 처리 ──────────> File Upload Security
    ├─ 보안 헤더 ──────────> HTTP Security Headers
    └─ 비밀번호 ──────────> Password Hashing

입력 검증 전략?
    │
    ├─ 정형 데이터 (이메일, 전화) ──> 정규식 + 타입 검증
    ├─ 자유 텍스트 ────────────────> 길이 제한 + sanitize
    ├─ 파일 업로드 ────────────────> MIME 검증 + 이름 재생성
    └─ URL/경로 ───────────────────> 화이트리스트 + canonicalize

암호화 선택?
    │
    ├─ 데이터 저장 (at rest) ──> AES-256-GCM
    ├─ 전송 (in transit) ─────> TLS 1.3 / mTLS
    ├─ 비밀번호 해싱 ─────────> Argon2id 또는 bcrypt(12+)
    └─ 키 관리 ───────────────> KMS (AWS/GCP) 또는 Vault
```

---

## Input Validation

### 검증 원칙

```
1. 화이트리스트 우선 (허용 목록 > 차단 목록)
2. 서버측 검증 필수 (클라이언트 검증은 UX 보조용)
3. 검증 순서: 타입 → 길이 → 범위 → 패턴 → 비즈니스 규칙
4. 정규화 먼저 (canonicalize → validate → use)
5. 실패 시 거부 (Fail closed)
```

### 언어별 검증 프레임워크

```java
// Java: Bean Validation (JSR 380)
public record CreateUserRequest(
    @NotBlank @Size(min = 2, max = 50)
    String name,

    @NotBlank @Email
    String email,

    @NotBlank @Size(min = 12, max = 128)
    @Pattern(regexp = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[@$!%*?&]).*$",
             message = "대소문자, 숫자, 특수문자 포함 필수")
    String password,

    @Min(0) @Max(150)
    Integer age
) {}

@PostMapping("/users")
public User createUser(@Valid @RequestBody CreateUserRequest req) {
    // @Valid 실패 시 MethodArgumentNotValidException 자동 발생
    return userService.create(req);
}
```

```python
# Python: Pydantic 검증
from pydantic import BaseModel, EmailStr, Field, field_validator
import re

class CreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    age: int = Field(ge=0, le=150)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("대문자 포함 필수")
        if not re.search(r"[a-z]", v):
            raise ValueError("소문자 포함 필수")
        if not re.search(r"\d", v):
            raise ValueError("숫자 포함 필수")
        return v
```

```typescript
// TypeScript: Zod 검증
import { z } from 'zod';

const CreateUserSchema = z.object({
  name: z.string().min(2).max(50),
  email: z.string().email(),
  password: z.string().min(12).max(128)
    .regex(/[A-Z]/, '대문자 포함 필수')
    .regex(/[a-z]/, '소문자 포함 필수')
    .regex(/\d/, '숫자 포함 필수'),
  age: z.number().int().min(0).max(150),
});

type CreateUserRequest = z.infer<typeof CreateUserSchema>;
```

```go
// Go: validator 패키지
type CreateUserRequest struct {
    Name     string `json:"name" validate:"required,min=2,max=50"`
    Email    string `json:"email" validate:"required,email"`
    Password string `json:"password" validate:"required,min=12,max=128"`
    Age      int    `json:"age" validate:"gte=0,lte=150"`
}

func (h *Handler) CreateUser(w http.ResponseWriter, r *http.Request) {
    var req CreateUserRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "Invalid request", http.StatusBadRequest)
        return
    }
    if err := validator.New().Struct(req); err != nil {
        http.Error(w, "Validation failed", http.StatusBadRequest)
        return
    }
}
```

### Path Traversal 방어

```go
// Go: 경로 검증 (canonicalize → validate → use)
func securePath(baseDir, userInput string) (string, error) {
    // 정규화
    cleaned := filepath.Clean(userInput)
    fullPath := filepath.Join(baseDir, cleaned)
    absPath, err := filepath.Abs(fullPath)
    if err != nil {
        return "", err
    }
    // 기본 디렉토리 내부인지 검증
    if !strings.HasPrefix(absPath, baseDir) {
        return "", fmt.Errorf("path traversal detected: %s", userInput)
    }
    return absPath, nil
}
```

---

## Output Encoding

### 컨텍스트별 인코딩

| 출력 컨텍스트 | 인코딩 방식 | 예시 |
|-------------|-----------|------|
| HTML body | HTML entities | `<` → `&lt;` |
| HTML attribute | Attribute encoding | `"` → `&quot;` |
| JavaScript | JSON.stringify + CSP | `'` → `\'` |
| URL parameter | encodeURIComponent | `&` → `%26` |
| CSS value | CSS escaping | `\` → `\\` |

```typescript
// TypeScript: 컨텍스트별 안전한 출력
// HTML: textContent 사용 (innerHTML 금지)
element.textContent = userInput;

// URL: encodeURIComponent
const safeUrl = `/search?q=${encodeURIComponent(userInput)}`;

// JSON API 응답: 프레임워크가 자동 인코딩
// Express는 res.json()이 자동으로 JSON serialize
res.json({ message: userInput });
```

### Content Security Policy (CSP)

```
# 엄격한 CSP 설정
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'nonce-{random}';
  style-src 'self' 'nonce-{random}';
  img-src 'self' data: https:;
  font-src 'self';
  object-src 'none';
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
  upgrade-insecure-requests;
```

---

## Encryption

### At Rest (저장 암호화)

```java
// Java: AES-256-GCM 암호화
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;

public class AESEncryptor {
    private static final int GCM_TAG_LENGTH = 128;
    private static final int IV_LENGTH = 12;

    public byte[] encrypt(byte[] plaintext, byte[] key) throws Exception {
        byte[] iv = new byte[IV_LENGTH];
        new SecureRandom().nextBytes(iv);

        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE,
            new SecretKeySpec(key, "AES"),
            new GCMParameterSpec(GCM_TAG_LENGTH, iv));
        byte[] ciphertext = cipher.doFinal(plaintext);

        // IV + ciphertext 결합 (IV는 공개 가능)
        byte[] result = new byte[iv.length + ciphertext.length];
        System.arraycopy(iv, 0, result, 0, iv.length);
        System.arraycopy(ciphertext, 0, result, iv.length, ciphertext.length);
        return result;
    }
}
```

```python
# Python: Fernet (AES-128-CBC + HMAC, 간편한 대칭 암호화)
from cryptography.fernet import Fernet

key = Fernet.generate_key()  # 안전하게 보관 (KMS/Vault)
f = Fernet(key)
encrypted = f.encrypt(b"sensitive data")
decrypted = f.decrypt(encrypted)
```

### Password Hashing

```python
# Python: Argon2id (권장)
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=3,        # 반복 횟수
    memory_cost=65536,  # 64MB
    parallelism=4,
    hash_len=32,
    type=argon2.Type.ID # Argon2id
)

hashed = ph.hash("user_password")
# 검증
try:
    ph.verify(hashed, "user_password")
except argon2.exceptions.VerifyMismatchError:
    raise AuthenticationError("비밀번호 불일치")
```

### 암호화 알고리즘 선택 가이드

| 용도 | 권장 | 금지 |
|------|------|------|
| 대칭 암호화 | AES-256-GCM, ChaCha20-Poly1305 | DES, 3DES, RC4, ECB 모드 |
| 비밀번호 해싱 | Argon2id, bcrypt(12+), scrypt | MD5, SHA-1, SHA-256 단독 |
| 디지털 서명 | Ed25519, RSA-PSS(2048+), ECDSA(P-256) | RSA-1024, DSA |
| 키 교환 | ECDHE, X25519 | static RSA, DH-1024 |
| TLS | TLS 1.3 (최소 1.2) | SSL 2/3, TLS 1.0/1.1 |

---

## Secure Error Handling

### 원칙

```
프로덕션 환경:
  - 사용자에게: generic error + correlation ID
  - 내부 로그에: 상세 에러 + 스택트레이스 + 컨텍스트
  - 절대 노출 금지: SQL 쿼리, 파일 경로, 스택트레이스, 서버 버전

개발 환경:
  - 상세 에러 메시지 허용 (프로덕션과 분리)
```

```java
// Java/Spring: 전역 에러 핸들러
@RestControllerAdvice
public class GlobalExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleException(Exception ex, HttpServletRequest req) {
        String correlationId = UUID.randomUUID().toString();
        // 내부 로그: 상세 정보
        log.error("correlationId={} path={} error={}",
            correlationId, req.getRequestURI(), ex.getMessage(), ex);
        // 외부 응답: generic error만
        return ResponseEntity.status(500).body(
            new ErrorResponse("Internal server error", correlationId));
    }

    record ErrorResponse(String message, String correlationId) {}
}
```

```go
// Go: 에러 래핑 + 로깅
func (h *Handler) GetUser(w http.ResponseWriter, r *http.Request) {
    user, err := h.service.FindUser(r.Context(), userID)
    if err != nil {
        correlationID := uuid.New().String()
        h.logger.Error("user lookup failed",
            "correlationId", correlationID,
            "userId", userID,
            "error", err)
        // 클라이언트에는 상세 에러 미노출
        http.Error(w, fmt.Sprintf(`{"error":"Internal server error","correlationId":"%s"}`, correlationID),
            http.StatusInternalServerError)
        return
    }
}
```

---

## File Upload Security

### 검증 순서

```
1. 파일 크기 제한: 일반 10MB, 이미지 5MB (서버 설정 레벨)
2. MIME type 검증: magic bytes 확인 (Content-Type 헤더 신뢰 금지)
3. 확장자 화이트리스트: .jpg, .png, .pdf 허용 / .exe, .sh, .php 금지
4. 파일명 재생성: UUID 사용 (원본 파일명 사용 금지)
5. 별도 스토리지: S3/CDN 저장, 실행 권한 제거
6. 바이러스 스캔: ClamAV 연동 (선택)
```

```python
# Python/FastAPI: 안전한 파일 업로드
import uuid, magic, mimetypes

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB

@app.post("/upload")
async def upload_file(file: UploadFile):
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "파일 크기 초과")
    mime_type = magic.from_buffer(content[:2048], mime=True)
    if mime_type not in ALLOWED_MIME:
        raise HTTPException(400, f"허용되지 않은 파일 형식: {mime_type}")
    ext = mimetypes.guess_extension(mime_type) or ""
    safe_filename = f"{uuid.uuid4()}{ext}"
    await storage.upload(safe_filename, content)
    return {"filename": safe_filename}
```

---

## HTTP Security Headers

### 필수 헤더

| 헤더 | 값 | 목적 |
|------|---|------|
| Strict-Transport-Security | max-age=31536000; includeSubDomains; preload | HTTPS 강제 |
| X-Content-Type-Options | nosniff | MIME 스니핑 방지 |
| X-Frame-Options | DENY | Clickjacking 방지 |
| Content-Security-Policy | (아래 참조) | XSS/인젝션 방지 |
| Referrer-Policy | strict-origin-when-cross-origin | Referrer 정보 제한 |
| Permissions-Policy | camera=(), microphone=(), geolocation=() | 브라우저 기능 제한 |
| X-XSS-Protection | 0 | 레거시 필터 비활성화 (CSP로 대체) |
| Cache-Control | no-store (민감 페이지) | 민감 데이터 캐시 방지 |

---

## 언어별 보안 체크리스트

### Java

| 취약점 | 방어 |
|--------|------|
| SQL Injection | PreparedStatement, JPA 파라미터 바인딩 |
| Deserialization | ObjectInputStream 금지, allowlist (JEP 290) |
| XML External Entity (XXE) | DTD/외부 엔티티 비활성화 |
| SSRF | URL 화이트리스트, 내부 IP 차단 |
| Log Injection | 로그 입력 개행문자 제거, 구조화 로깅 |

### Go

| 취약점 | 방어 |
|--------|------|
| Command Injection | exec.Command (shell=false), 인자 분리 전달 |
| Template Injection | html/template (자동 이스케이핑), text/template 금지 |
| Path Traversal | filepath.Clean + filepath.Abs + prefix 검증 |
| Integer Overflow | math.MaxInt 확인, overflow 검증 |
| Race Condition | -race 플래그, sync.Mutex, channel |

### Python

| 취약점 | 방어 |
|--------|------|
| eval()/exec() | 절대 사용 금지 (사용자 입력) |
| pickle | 신뢰할 수 없는 데이터에 사용 금지, JSON 대체 |
| SQL Injection | SQLAlchemy 파라미터 바인딩, raw SQL 금지 |
| SSRF | URL 검증, ipaddress 모듈로 내부 IP 차단 |
| ReDoS | 복잡한 정규식 회피, re2 라이브러리 고려 |

### TypeScript/JavaScript

| 취약점 | 방어 |
|--------|------|
| Prototype Pollution | Object.freeze, Map 사용, lodash merge 주의 |
| ReDoS | 정규식 복잡도 제한, re2 라이브러리 |
| innerHTML XSS | textContent 사용, DOMPurify sanitize |
| Path Traversal | path.resolve + prefix 검증 |
| Dependency Confusion | package-lock.json, .npmrc registry 고정 |

---

## Secure Random 생성

```
Java:   SecureRandom.getInstanceStrong().nextBytes(new byte[32])
Go:     crypto/rand.Read(b)  (math/rand 금지)
Python: secrets.token_urlsafe(32)  (random 모듈 금지)
TS:     crypto.randomBytes(32).toString('base64url')
```

---

## Anti-Patterns

| Anti-Pattern | 위험 | 올바른 접근 |
|-------------|------|-----------|
| 자체 암호화 알고리즘 구현 | 수학적으로 검증되지 않아 취약점 내포 | 표준 라이브러리 사용 (nacl, libsodium) |
| 클라이언트 검증만 의존 | JavaScript 비활성화/우회로 무력화 | 서버측 검증 필수 |
| 에러에 DB 스키마/쿼리 노출 | 공격자에게 내부 구조 정보 제공 | generic error + correlation ID |
| math/rand로 토큰 생성 | 예측 가능한 시퀀스 → 토큰 위조 | crypto/rand, secrets, SecureRandom |
| 블랙리스트 기반 입력 검증 | 우회 패턴이 항상 존재 | 화이트리스트 기반 검증 |
| try-catch 빈 블록 | 에러 무시 → 디버깅 불가, 보안 이벤트 누락 | 에러 로깅 + 적절한 처리 |
| Content-Type 헤더로 파일 검증 | 헤더는 클라이언트가 조작 가능 | magic bytes로 실제 MIME 확인 |
| SQL 문자열 연결 | SQL Injection의 직접적 원인 | PreparedStatement, 파라미터 바인딩 |

---

## Security Testing (CI 통합)

```
SAST: semgrep scan --config=auto --error
Dependency: npm audit / pip-audit / govulncheck
Secrets: gitleaks detect --source .
Container: trivy image --severity HIGH,CRITICAL $IMAGE
```

---

## Sources

| 출처 | URL |
|------|-----|
| OWASP Secure Coding Practices | https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/ |
| CWE Top 25 (2023) | https://cwe.mitre.org/top25/ |
| OWASP Cheat Sheet Series | https://cheatsheetseries.owasp.org/ |
| NIST SP 800-63B (Digital Identity) | https://pages.nist.gov/800-63-3/sp800-63b.html |
| Mozilla Web Security Guidelines | https://infosec.mozilla.org/guidelines/web_security |

---

## Related Skills

| 스킬 | 용도 |
|------|------|
| `security/owasp-top10` | OWASP Top 10 취약점별 방어 패턴 |
| `security/auth-patterns` | OAuth2, JWT, 세션 인증 구현 |
| `security/threat-modeling` | STRIDE/DREAD 위협 분석 |
| `security/compliance-frameworks` | SOC2/HIPAA/GDPR 기술 요구사항 |
| `cicd/supply-chain-security` | 의존성 보안, SBOM, 이미지 서명 |
