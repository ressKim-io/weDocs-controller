---
name: owasp-top10
description: "OWASP Top 10 방어 가이드 — OWASP Top 10 (2021) 취약점 상세 설명과 언어별 실전 방어 패턴 Use when working with security 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# OWASP Top 10 방어 가이드

OWASP Top 10 (2021) 취약점 상세 설명과 언어별 실전 방어 패턴

## Quick Reference (결정 트리)

```
보안 취약점 유형?
    │
    ├─ 인증/인가 문제 ──────> A01: Broken Access Control
    ├─ 암호화 부재/취약 ────> A02: Cryptographic Failures
    ├─ 외부 입력 미검증 ────> A03: Injection
    ├─ 설계 단계 보안 결함 ──> A04: Insecure Design
    ├─ 잘못된 설정 ─────────> A05: Security Misconfiguration
    ├─ 취약한 컴포넌트 ─────> A06: Vulnerable Components
    ├─ 인증 메커니즘 결함 ──> A07: Authentication Failures
    ├─ 데이터 무결성 ───────> A08: Software & Data Integrity
    ├─ 로깅/모니터링 부재 ──> A09: Logging Failures
    └─ 서버 요청 위조 ──────> A10: SSRF

방어 전략 우선순위?
    │
    ├─ 최다 발생 ───> A01 (Broken Access Control) 먼저 점검
    ├─ 최고 위험 ───> A03 (Injection) + A02 (Crypto) 즉시 대응
    └─ 기본 위생 ───> A05 (Misconfiguration) + A06 (Components)
```

---

## A01: Broken Access Control

접근 제어 실패. 사용자가 의도된 권한을 벗어나 행동할 수 있는 취약점.

### 공격 시나리오

```
- IDOR: GET /api/users/123 → GET /api/users/456 (타인 정보 조회)
- 권한 우회: 일반 사용자가 /admin 엔드포인트 접근
- 메서드 변경: GET은 차단했지만 PUT/DELETE는 허용
- 경로 조작: /api/../admin/config 접근
```

### 방어 패턴

```java
// Java/Spring: 리소스 소유권 검증 (IDOR 방어)
@GetMapping("/orders/{orderId}")
@PreAuthorize("hasRole('USER')")
public Order getOrder(@PathVariable Long orderId, Authentication auth) {
    Order order = orderService.findById(orderId);
    if (!order.getUserId().equals(auth.getName())) {
        throw new AccessDeniedException("접근 권한 없음");
    }
    return order;
}
```

```go
// Go: 미들웨어 기반 접근 제어
func AuthorizeOwner(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        userID := r.Context().Value("userID").(string)
        resourceOwner := getResourceOwner(r)
        if userID != resourceOwner {
            http.Error(w, "Forbidden", http.StatusForbidden)
            return
        }
        next.ServeHTTP(w, r)
    })
}
```

### 체크리스트

| 항목 | 설명 |
|------|------|
| 기본 거부 (Deny by default) | 명시적으로 허용하지 않은 접근은 모두 거부 |
| RBAC/ABAC 적용 | 역할/속성 기반 접근 제어 |
| IDOR 방지 | 리소스 접근 시 소유자 검증 |
| CORS 제한 | 최소한의 origin만 허용 |
| 디렉토리 리스팅 비활성화 | 웹 서버 디렉토리 목록 노출 차단 |
| Rate limiting | API 엔드포인트별 호출 제한 |

---

## A02: Cryptographic Failures

민감 데이터의 암호화 부재 또는 약한 암호화 알고리즘 사용.

### 방어 패턴

| 용도 | 권장 알고리즘 | 금지 |
|------|-------------|------|
| 대칭 암호화 | AES-256-GCM | DES, 3DES, RC4 |
| 비밀번호 해싱 | bcrypt(cost 12+), Argon2id | MD5, SHA-1, SHA-256 단독 |
| 전송 암호화 | TLS 1.3 (최소 1.2) | SSL, TLS 1.0/1.1 |
| 키 교환 | ECDHE | RSA key exchange |
| 서명 | Ed25519, RSA-PSS (2048+) | RSA-1024 |

```python
# Python: 비밀번호 해싱 (bcrypt)
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
```

```java
// Java: AES-256-GCM 암호화
Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
SecretKeySpec keySpec = new SecretKeySpec(key, "AES");
GCMParameterSpec gcmSpec = new GCMParameterSpec(128, iv);
cipher.init(Cipher.ENCRYPT_MODE, keySpec, gcmSpec);
byte[] encrypted = cipher.doFinal(plaintext);
```

---

## A03: Injection

외부 입력이 쿼리, 명령어, 표현식에 삽입되어 의도치 않은 동작을 유발.

### SQL Injection 방어

```java
// Java: PreparedStatement (필수)
PreparedStatement ps = conn.prepareStatement(
    "SELECT * FROM users WHERE email = ? AND status = ?");
ps.setString(1, email);
ps.setString(2, status);

// 금지: 문자열 연결
// String q = "SELECT * FROM users WHERE email = '" + email + "'";
```

```go
// Go: 파라미터 바인딩
row := db.QueryRow("SELECT id, name FROM users WHERE email = $1", email)
```

```python
# Python: SQLAlchemy 파라미터 바인딩
result = db.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
```

### XSS 방어

```typescript
// TypeScript: DOMPurify로 sanitize
import DOMPurify from 'dompurify';
const clean = DOMPurify.sanitize(userInput);
// innerHTML 대신 textContent 사용
element.textContent = userInput;
```

### Command Injection 방어

```python
# Python: subprocess에 shell=False (기본값) 사용
import subprocess
# 안전: 인자를 리스트로 전달
subprocess.run(["ls", "-la", directory], check=True)
# 금지: shell=True + 사용자 입력
# subprocess.run(f"ls {user_input}", shell=True)
```

### Content-Security-Policy 헤더

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none';
```

---

## A04: Insecure Design

설계 단계에서 보안이 고려되지 않은 근본적인 결함.

### 방어 원칙

```
Security by Design 프로세스:
  1. 위협 모델링 (STRIDE) — 설계 단계에서 위협 식별
  2. Abuse Case 작성 — 악의적 사용자 시나리오 도출
  3. 보안 요구사항 정의 — 기능 요구사항과 동등하게 관리
  4. 보안 설계 리뷰 — 아키텍처 리뷰에 보안 항목 포함
  5. Secure Defaults — 기본 설정이 안전한 상태

핵심 원칙:
  - Defense in Depth: 다중 보안 레이어 적용
  - Least Privilege: 최소 권한만 부여
  - Fail Secure: 실패 시 안전한 상태로 전환
  - Complete Mediation: 모든 접근에 대해 권한 검증
```

### Abuse Case 예시

```
기능: 비밀번호 재설정
정상 케이스: 사용자가 이메일로 재설정 링크 수신
Abuse Case:
  - 공격자가 타인의 이메일로 대량 재설정 요청 (DoS)
  - 재설정 토큰 예측/브루트포스
  - 재설정 링크를 통한 계정 탈취
대응:
  - Rate limiting (IP + 이메일 기준)
  - 토큰: 128bit 이상 crypto random, 15분 만료
  - 사용 후 즉시 무효화
```

---

## A05: Security Misconfiguration

기본 설정 미변경, 불필요한 기능 활성화, 에러 상세 노출.

### 체크리스트

```
서버/애플리케이션:
  □ 기본 비밀번호 변경 완료
  □ 불필요한 포트/서비스 비활성화
  □ 디버그 모드 비활성화 (프로덕션)
  □ 디렉토리 리스팅 비활성화
  □ 에러 메시지에 스택트레이스 미포함

HTTP 헤더:
  □ X-Content-Type-Options: nosniff
  □ X-Frame-Options: DENY
  □ Strict-Transport-Security 설정
  □ Content-Security-Policy 설정

Kubernetes:
  □ Pod Security Standards (restricted) 적용
  □ NetworkPolicy 기본 Deny 설정
  □ automountServiceAccountToken: false
  □ readOnlyRootFilesystem: true
```

```yaml
# Kubernetes: 보안 강화 Pod 설정
apiVersion: v1
kind: Pod
spec:
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: app
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
```

---

## A06: Vulnerable and Outdated Components

알려진 취약점이 있는 라이브러리/프레임워크 사용.

### SCA (Software Composition Analysis) 도구

| 도구 | 언어/대상 | 명령 |
|------|----------|------|
| npm audit | Node.js | `npm audit --production` |
| pip-audit | Python | `pip-audit -r requirements.txt` |
| govulncheck | Go | `govulncheck ./...` |
| Trivy | 컨테이너/IaC | `trivy image myapp:latest` |
| Snyk | 다중 언어 | `snyk test` |
| OWASP Dependency-Check | Java | `mvn dependency-check:check` |

### 의존성 관리 원칙

```
1. 버전 고정 (lock file): package-lock.json, go.sum, poetry.lock
2. 자동 업데이트: Dependabot, Renovate 설정
3. 주기적 스캔: CI에 SCA 통합
4. SBOM 생성: syft, cyclonedx-cli
5. 사용하지 않는 의존성 제거
```

---

## A07: Identification and Authentication Failures

인증 메커니즘의 결함: 브루트포스 허용, 약한 비밀번호, 세션 관리 미흡.

### 방어 패턴

```
비밀번호 정책:
  - 최소 12자, 대소문자+숫자+특수문자
  - 유출된 비밀번호 DB 확인 (Have I Been Pwned API)
  - bcrypt(cost 12+) 또는 Argon2id로 해싱

브루트포스 방어:
  - 5회 실패 후 계정 잠금 (15분)
  - 점진적 지연: 1초, 2초, 4초, 8초...
  - CAPTCHA 적용 (3회 실패 후)
  - IP 기반 Rate Limiting

세션 관리:
  - 세션 ID: 128bit 이상 crypto random
  - 로그인 성공 시 세션 ID 재생성
  - 유휴 타임아웃: 15~30분
  - 절대 타임아웃: 8~24시간
  - 로그아웃 시 서버측 세션 즉시 파기

MFA (Multi-Factor Authentication):
  - TOTP (Google Authenticator, Authy)
  - WebAuthn/FIDO2 (하드웨어 키)
  - SMS는 최후의 수단 (SIM swapping 취약)
```

---

## A08: Software and Data Integrity Failures

코드/데이터 무결성 검증 없이 업데이트 또는 CI/CD 파이프라인 공격.

### Supply Chain 보안

```
CI/CD: 의존성 소스 검증, ephemeral build, 아티팩트 서명(cosign), SLSA Level 3+
이미지: 서명 검증, 허용 레지스트리 (Admission Controller), digest 사용 (태그 금지)
직렬화: Java ObjectInputStream 금지, Python pickle 금지 → JSON, Protobuf 사용
```

---

## A09: Security Logging and Monitoring Failures

보안 이벤트의 로깅/모니터링/알림 부재로 공격 탐지 실패.

### 필수 로깅 이벤트

```
인증 관련:
  - 로그인 성공/실패 (IP, 사용자, 시간)
  - 비밀번호 변경
  - MFA 활성화/비활성화
  - 계정 잠금/해제

인가 관련:
  - 접근 거부 이벤트 (403)
  - 권한 변경 (RBAC 수정)
  - 관리자 작업

데이터 관련:
  - 민감 데이터 접근 (조회/수정/삭제)
  - 대량 데이터 내보내기
  - 비정상 쿼리 패턴
```

### 로깅 구현

```java
// Java: 보안 이벤트 구조화 로깅
@Component
public class SecurityEventLogger {
    private static final Logger secLog = LoggerFactory.getLogger("SECURITY");

    public void logAuthEvent(String event, String userId, String ip, boolean success) {
        secLog.info("event={} userId={} ip={} success={} timestamp={}",
            event, userId, ip, success, Instant.now());
    }
    // PII, 비밀번호, 토큰은 절대 로깅하지 않음
}
```

### 알림 규칙

| 이벤트 | 임계값 | 심각도 |
|--------|--------|--------|
| 로그인 실패 (동일 IP) | 5회/분 | Warning |
| 로그인 실패 (전체) | 20회/분 | Critical |
| 권한 변경 | 모든 변경 | Info |
| 403 응답 (동일 사용자) | 10회/분 | Warning |

---

## A10: Server-Side Request Forgery (SSRF)

서버가 공격자가 지정한 URL로 요청을 보내도록 유도.

### 공격 시나리오

```
- 내부 네트워크 스캔: http://192.168.1.1/admin
- 클라우드 메타데이터 접근: http://169.254.169.254/latest/meta-data/
- 로컬 파일 읽기: file:///etc/passwd
- 내부 서비스 접근: http://internal-api:8080/admin
```

### 방어 패턴

```python
# Python: URL 화이트리스트 기반 SSRF 방어
from urllib.parse import urlparse
import ipaddress

ALLOWED_HOSTS = {"api.example.com", "cdn.example.com"}
BLOCKED_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # 클라우드 메타데이터
    ipaddress.ip_network("127.0.0.0/8"),
]

def validate_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("https",):
        return False
    if parsed.hostname not in ALLOWED_HOSTS:
        return False
    # DNS rebinding 방어: resolve 후 IP 확인
    resolved_ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
    for blocked in BLOCKED_RANGES:
        if resolved_ip in blocked:
            return False
    return True
```

```yaml
# Kubernetes: 메타데이터 API 차단 NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: block-cloud-metadata
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except: [169.254.169.254/32]
```

---

## Anti-Patterns

| Anti-Pattern | 위험 | 올바른 접근 |
|-------------|------|-----------|
| "보안은 나중에" | 설계 결함은 나중에 수정 비용이 기하급수적으로 증가 | Security by Design, 설계 단계부터 위협 모델링 |
| 자체 암호화 알고리즘 | 수학적으로 검증되지 않은 알고리즘은 취약 | 표준 라이브러리 사용 (AES-GCM, bcrypt) |
| 에러에 스택트레이스 노출 | 내부 구조/기술 스택 노출 → 공격 표면 확대 | 프로덕션은 generic error + correlation ID |
| 클라이언트 검증만 의존 | 클라이언트 검증은 우회 가능 | 서버측 검증 필수 (클라이언트는 UX용) |
| 시크릿 하드코딩 | 코드 유출 시 즉각적 보안 사고 | 환경변수, Secret Manager 사용 |
| 모든 입력 신뢰 | Injection, XSS, SSRF 등 모든 공격의 시작점 | 화이트리스트 기반 입력 검증 |
| CORS wildcard (*) | 모든 origin에서 API 접근 허용 | 명시적 origin 허용 목록 |

---

## OWASP Top 10 요약 매트릭스

| # | 취약점 | CWE 매핑 | 발생 빈도 | 영향도 | 핵심 방어 |
|---|--------|---------|----------|--------|----------|
| A01 | Broken Access Control | CWE-200, 284 | 94% 앱 테스트 | Critical | RBAC, IDOR 검증 |
| A02 | Cryptographic Failures | CWE-259, 327 | 높음 | Critical | AES-GCM, TLS 1.3, bcrypt |
| A03 | Injection | CWE-79, 89 | 높음 | Critical | PreparedStatement, CSP |
| A04 | Insecure Design | CWE-209, 256 | 중간 | High | Threat Modeling, Abuse Cases |
| A05 | Misconfiguration | CWE-16, 611 | 90% 앱 | Medium | 보안 기본값, 자동화 검증 |
| A06 | Vulnerable Components | CWE-1104 | 높음 | High | SCA, SBOM, 자동 업데이트 |
| A07 | Auth Failures | CWE-287, 384 | 중간 | Critical | MFA, bcrypt, 세션 관리 |
| A08 | Integrity Failures | CWE-502, 829 | 중간 | High | 서명 검증, SLSA |
| A09 | Logging Failures | CWE-778 | 높음 | Medium | 보안 이벤트 로깅, SIEM |
| A10 | SSRF | CWE-918 | 중간 | High | URL 화이트리스트, NetworkPolicy |

---

## Sources

| 출처 | URL |
|------|-----|
| OWASP Top 10 (2021) | https://owasp.org/Top10/ |
| OWASP Cheat Sheet Series | https://cheatsheetseries.owasp.org/ |
| CWE Top 25 (2023) | https://cwe.mitre.org/top25/ |
| NIST Cryptographic Standards | https://csrc.nist.gov/projects/cryptographic-standards-and-guidelines |

---

## Related Skills

| 스킬 | 용도 |
|------|------|
| `security/auth-patterns` | OAuth2, JWT, 세션 인증 패턴 |
| `security/secure-coding` | 언어별 시큐어 코딩 패턴 |
| `security/threat-modeling` | STRIDE/DREAD 위협 모델링 |