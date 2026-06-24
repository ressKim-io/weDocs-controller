# Security Rules

Claude Code가 코드 작성 시 반드시 준수해야 할 보안 규칙.
이 규칙은 모든 언어, 프레임워크에 적용된다.

---

## 시크릿 관리 (Secret Management)

- 비밀번호, API 키, 토큰, DB credentials를 코드에 하드코딩 절대 금지
- 시크릿은 환경변수(`process.env`, `os.Getenv`, `System.getenv`) 또는 Secret Manager(AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault) 사용
- `.env` 파일은 `.gitignore`에 반드시 포함 — 커밋 전 확인 필수
- 코드 예시에서도 실제 값 대신 플레이스홀더 사용: `YOUR_API_KEY`, `<token>`
- 커밋 전 시크릿 스캔 도구 권장: `gitleaks`, `truffleHog`, `git-secrets`

```bash
# 올바른 예
export DATABASE_URL="..."  # 환경변수로 주입
db.connect(os.Getenv("DATABASE_URL"))

# 금지
db.connect("postgresql://user:password@host/db")
```

---

## 입력 검증 (Input Validation)

외부에서 오는 모든 입력은 신뢰하지 않는다: 사용자 입력, API 요청, 파일 업로드, URL 파라미터.

**SQL Injection 방지**
- PreparedStatement / 파라미터 바인딩 사용, 문자열 연결(concatenation) 금지
- ORM 사용 시에도 raw query에 사용자 입력 직접 삽입 금지

```java
// 올바른 예 (Java)
PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?");
ps.setInt(1, userId);

// 금지
String query = "SELECT * FROM users WHERE id = " + userId;
```

**XSS 방지**
- 사용자 입력을 HTML에 렌더링할 때 반드시 이스케이핑
- `innerHTML` 직접 할당 금지, `textContent` 또는 sanitize 라이브러리 사용
- Content-Security-Policy(CSP) 헤더 설정 권장

**Command Injection 방지**
- 사용자 입력을 shell 명령에 직접 사용 금지
- `exec()`, `system()`, `subprocess.call(shell=True)` 에 외부 입력 전달 금지
- 파일명, 경로에 대한 path traversal(`../`) 검증 필수

---

## 인증/인가 (Authentication / Authorization)

**인증 토큰**
- JWT, session token은 HttpOnly + Secure Cookie 또는 Authorization 헤더로 전달
- LocalStorage에 민감한 토큰 저장 금지 (XSS에 취약)
- 토큰 만료(expiry) 및 갱신(refresh) 로직 필수 구현

**비밀번호 처리**
- 비밀번호는 반드시 bcrypt, scrypt, Argon2로 해시 후 저장
- MD5, SHA-1 단독 사용 금지 (해시 알고리즘으로 부적합)
- 평문(plain text) 비밀번호 저장 절대 금지

**인가(Authorization) 체크**
- 모든 API 엔드포인트에 인가 체크 필수 — 인증(Authentication)과 별개
- 최소 권한 원칙(Principle of Least Privilege) 적용: 필요한 권한만 부여
- IDOR(Insecure Direct Object Reference) 방지: 리소스 접근 시 소유자 검증

```python
# 올바른 예
if resource.owner_id != current_user.id:
    raise PermissionDenied("접근 권한 없음")
```

---

## 의존성 보안 (Dependency Security)

- CVE 데이터베이스에 알려진 취약점이 있는 라이브러리 사용 금지
- 의존성 취약점 스캔: `npm audit`, `pip-audit`, `govulncheck`, `trivy`
- 의존성 업데이트 시 CHANGELOG 및 breaking changes 확인
- 정기적인 의존성 업데이트 권장 (자동화: Dependabot, Renovate)
- SBOM(Software Bill of Materials) 생성 고려: `syft`, `cyclonedx`

---

## 로깅 보안 (Logging Security)

- PII(Personally Identifiable Information) 로깅 금지: 이름, 이메일, 전화번호, 주민번호
- 비밀번호, API 키, 토큰, 세션 ID 로그 출력 절대 금지
- 에러 스택트레이스(stack trace)를 프로덕션 API 응답에 노출 금지
  - 내부 로그에만 기록, 클라이언트에는 generic error message 반환
- 로그에 SQL 쿼리 전체를 기록할 때 바인딩 파라미터 값 마스킹

```go
// 금지
log.Printf("Login attempt: user=%s password=%s", username, password)

// 올바른 예
log.Printf("Login attempt: user=%s", username)

// API 응답 (프로덕션)
// {"error": "Internal server error"}  ← stack trace 미포함
```

---

## 체크리스트 (PR/커밋 전 확인)

- [ ] 코드에 하드코딩된 시크릿 없음
- [ ] 외부 입력 검증 로직 존재
- [ ] SQL 쿼리는 파라미터 바인딩 사용
- [ ] 인가 체크가 필요한 엔드포인트에 적용됨
- [ ] 로그에 PII/시크릿 없음
- [ ] 신규 의존성에 알려진 CVE 없음
