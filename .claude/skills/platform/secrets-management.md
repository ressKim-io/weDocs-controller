---
name: secrets-management
description: "시크릿 관리 가이드 — K8s 시크릿 자동 주입, External Secrets Operator, Vault, Infisical, SOPS — 개발자가 .env 없이 개발하는 환경 Use when working with platform 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# 시크릿 관리 가이드

K8s 시크릿 자동 주입, External Secrets Operator, Vault, Infisical, SOPS — 개발자가 .env 없이 개발하는 환경

## Quick Reference (결정 트리)

```
시크릿 관리 도구 선택?
    ├─ 팀 <10명, 단일 클라우드 ───> Sealed Secrets + SOPS (최소 인프라)
    ├─ 팀 10~50명, 멀티 클라우드 ─> ESO (AWS/GCP/Azure 통합)
    ├─ 엔터프라이즈, 컴플라이언스 ─> Vault (Dynamic Secrets, 감사 로그)
    ├─ 스타트업, DX 최우선 ───────> Infisical (직관적 UI, CLI)
    └─ GitOps + 암호화 저장 ─────> SOPS + age (Git에 암호화 커밋)
```

| 기준 | ESO | Sealed Secrets | Vault | Infisical | SOPS+age |
|------|-----|---------------|-------|-----------|----------|
| 복잡도 | 중간 | 낮음 | 높음 | 낮음 | 낮음 |
| Dynamic Secrets | 백엔드 의존 | 불가 | 지원 | 지원 | 불가 |
| 자동 로테이션 | 지원 | 불가 | 지원 | 지원 | 불가 |
| GitOps 친화 | 우수 | 우수 | 보통 | 우수 | 최고 |
| 월 운영비용 | ~$500 | ~$200 | $2K~5K | ~$500 | ~$100 |

---

## 1. K8s 시크릿 문제점

- **base64 != 암호화:** `echo cGFzc3dvcmQ= | base64 -d`로 즉시 복호화
- **etcd 평문 저장:** EncryptionConfiguration 미설정 시 시크릿이 평문으로 etcd에 저장
- **RBAC 부재 시 네임스페이스 내 모든 Pod 접근 가능**
- **Git 커밋 시 이력에 영구 잔존**

```yaml
# 최소 조치: etcd 암호화 활성화 (/etc/kubernetes/encryption-config.yaml)
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources: [secrets]
    providers:
      - aescbc:
          keys: [{name: key1, secret: <BASE64_32BYTE_KEY>}]
      - identity: {}
```

---

## 2. External Secrets Operator (ESO) 심화

### 설치 및 ClusterSecretStore

```bash
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace --set installCRDs=true
```

```yaml
# AWS Secrets Manager 연동
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-sm
spec:
  provider:
    aws:
      service: SecretsManager
      region: ap-northeast-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
            namespace: external-secrets
---
# GCP Secret Manager (Workload Identity)
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: gcp-sm
spec:
  provider:
    gcpsm:
      projectID: my-gcp-project
      auth:
        workloadIdentity:
          clusterLocation: asia-northeast3
          clusterName: my-gke-cluster
          clusterProjectID: my-gcp-project
          serviceAccountRef: {name: eso-sa, namespace: external-secrets}
---
# Azure Key Vault (Workload Identity)
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: azure-kv
spec:
  provider:
    azurekv:
      tenantId: "<TENANT_ID>"
      vaultUrl: "https://my-vault.vault.azure.net"
      authType: WorkloadIdentity
      serviceAccountRef: {name: eso-sa, namespace: external-secrets}
```

### ExternalSecret 리소스

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef: {name: aws-sm, kind: ClusterSecretStore}
  target: {name: db-credentials, creationPolicy: Owner}
  data:
    - secretKey: DB_HOST
      remoteRef: {key: prod/my-app/database, property: host}
    - secretKey: DB_PASSWORD
      remoteRef: {key: prod/my-app/database, property: password}
```

### IRSA 설정 (AWS)

```bash
# IAM Policy → ServiceAccount 연결
cat <<'EOF' > eso-policy.json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
  "Action":["secretsmanager:GetSecretValue","secretsmanager:DescribeSecret"],
  "Resource":"arn:aws:secretsmanager:ap-northeast-2:*:secret:prod/*"}]}
EOF
aws iam create-policy --policy-name ESOAccess --policy-document file://eso-policy.json
eksctl create iamserviceaccount --name external-secrets-sa \
  --namespace external-secrets --cluster my-cluster \
  --attach-policy-arn arn:aws:iam::123456789:policy/ESOAccess --approve
```

---

## 3. HashiCorp Vault 연동

### Agent Injector vs CSI vs VSO

| 기능 | Agent Injector | CSI Provider | VSO (2026 권장) |
|------|--------------|-------------|----------------|
| 사이드카 | 필요 | 불필요 | 불필요 |
| 인증 방식 | 모든 방식 | K8s Auth만 | 모든 방식 |
| 자동 갱신 | 지원 | 미지원 | 지원 |
| K8s Secret 생성 | 미생성 | 선택적 | 네이티브 |
| 상태 | 유지보수 모드 | 유지보수 모드 | 적극 개발중 |

**2026년 권장:** Vault Secrets Operator(VSO). Agent Injector/CSI는 레거시.

### VSO 설정

```bash
helm install vault-secrets-operator hashicorp/vault-secrets-operator \
  -n vault-secrets-operator-system --create-namespace
```

```yaml
apiVersion: secrets.hashicorp.com/v1beta1
kind: VaultConnection
metadata: {name: vault-conn, namespace: my-app}
spec:
  address: https://vault.example.com:8200
---
apiVersion: secrets.hashicorp.com/v1beta1
kind: VaultAuth
metadata: {name: vault-auth, namespace: my-app}
spec:
  vaultConnectionRef: vault-conn
  method: kubernetes
  mount: kubernetes
  kubernetes: {role: my-app-role, serviceAccount: my-app-sa}
---
apiVersion: secrets.hashicorp.com/v1beta1
kind: VaultStaticSecret
metadata: {name: db-creds, namespace: my-app}
spec:
  vaultAuthRef: vault-auth
  mount: secret
  path: data/my-app/db
  type: kv-v2
  refreshAfter: 60s
  destination: {name: db-credentials, create: true}
```

### Dynamic Secrets (DB 자동 로테이션)

```bash
vault secrets enable database
vault write database/config/my-postgres \
  plugin_name=postgresql-database-plugin \
  connection_url="postgresql://{{username}}:{{password}}@postgres:5432/mydb" \
  allowed_roles="my-app-role" username="vault_admin" password="admin_pw"
vault write database/roles/my-app-role db_name=my-postgres \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' \
  VALID UNTIL '{{expiration}}'; GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" max_ttl="24h"
```

```yaml
# VaultDynamicSecret: TTL 기반 자동 발급/갱신/만료
apiVersion: secrets.hashicorp.com/v1beta1
kind: VaultDynamicSecret
metadata: {name: dynamic-db, namespace: my-app}
spec:
  vaultAuthRef: vault-auth
  mount: database
  path: creds/my-app-role
  renewalPercent: 67
  destination: {name: dynamic-db-creds, create: true}
  rolloutRestartTargets:
    - {kind: Deployment, name: my-app}
```

### Transit Engine (앱 레벨 암호화)

```bash
vault secrets enable transit
vault write -f transit/keys/my-app-key type=aes256-gcm96
# 암호화: vault write transit/encrypt/my-app-key plaintext=$(echo -n "data" | base64)
# 복호화: vault write transit/decrypt/my-app-key ciphertext="vault:v1:..."
```

---

## 4. Infisical (개발자 친화적 대안)

```bash
brew install infisical/get-cli/infisical
infisical login
infisical secrets --env=dev          # 환경별 시크릿 조회
infisical run --env=dev -- go run main.go    # 시크릿 주입 실행
infisical run --env=dev -- ./gradlew bootRun  # Spring Boot
```

### K8s Operator

```yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata: {name: my-app-secrets, namespace: my-app}
spec:
  hostAPI: https://app.infisical.com/api
  resyncInterval: 60
  authentication:
    universalAuth:
      secretsScope: {projectSlug: my-project, envSlug: prod, secretsPath: /}
      credentialsRef: {secretName: infisical-identity, secretNamespace: infisical}
  managedSecretReference:
    secretName: my-app-managed
    secretNamespace: my-app
    creationPolicy: Owner
```

---

## 5. SOPS + age (GitOps 친화적)

### 설정 및 암호화

```bash
age-keygen -o age-key.txt  # 키 생성
# .sops.yaml (프로젝트 루트)
cat <<'EOF' > .sops.yaml
creation_rules:
  - path_regex: secrets/prod/.* 
    age: age1prodkeyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  - path_regex: secrets/dev/.*
    age: age1devkeyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EOF
sops -e secret.yaml > secret.enc.yaml   # 암호화
sops -d secret.enc.yaml                 # 복호화
```

### ArgoCD + SOPS 플러그인

```yaml
# ArgoCD Application
spec:
  source:
    repoURL: https://github.com/org/config
    path: k8s/overlays/prod
    plugin:
      name: sops   # argocd-cm에 SOPS 플러그인 등록 필요
```

### Flux + SOPS 연동

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata: {name: my-app, namespace: flux-system}
spec:
  interval: 10m
  path: ./k8s/overlays/prod
  prune: true
  sourceRef: {kind: GitRepository, name: my-app-config}
  decryption:
    provider: sops
    secretRef: {name: sops-age-key}  # age 비밀키를 담은 K8s Secret
```

---

## 6. 시크릿 로테이션 자동화

```yaml
# ESO: refreshInterval로 자동 동기화
spec:
  refreshInterval: 15m
  target:
    deletionPolicy: Retain  # ExternalSecret 삭제 시 Secret 유지

# VSO: renewalPercent + rolloutRestartTargets로 Pod 자동 재시작
spec:
  renewalPercent: 67
  rolloutRestartTargets:
    - {kind: Deployment, name: my-app}
```

---

## 7. 개발자 워크플로우 (로컬 개발 시 시크릿 접근)

```bash
# 방법 1: Infisical CLI (권장)
infisical run --env=dev -- go run main.go

# 방법 2: Vault CLI
vault login -method=oidc && vault kv get -format=json secret/dev/my-app

# 방법 3: AWS CLI
aws secretsmanager get-secret-value --secret-id dev/my-app/db | jq -r .SecretString

# 방법 4: Tilt/Skaffold + 로컬 K8s에 ESO 설치 후 dev SecretStore 연결
# ANTI-PATTERN: .env 파일 슬랙/이메일로 공유하지 말 것!
```

---

## 8. Go 코드 예제

### Vault SDK

```go
package main

import (
	"context"
	"log"
	"os"
	vault "github.com/hashicorp/vault/api"
)

func main() {
	client, _ := vault.NewClient(&vault.Config{Address: "https://vault.example.com:8200"})
	// K8s SA 토큰 인증
	k8sAuth, _ := client.Logical().Write("auth/kubernetes/login", map[string]interface{}{
		"role": "my-app-role",
		"jwt":  string(must(os.ReadFile("/var/run/secrets/kubernetes.io/serviceaccount/token"))),
	})
	client.SetToken(k8sAuth.Auth.ClientToken)

	secret, _ := client.KVv2("secret").Get(context.Background(), "my-app/db")
	log.Printf("DB Host: %s", secret.Data["host"])

	// Dynamic Secret
	dbCreds, _ := client.Logical().Read("database/creds/my-app-role")
	log.Printf("Dynamic user: %s (TTL: %ds)", dbCreds.Data["username"], dbCreds.LeaseDuration)
}

func must(b []byte, err error) []byte { if err != nil { panic(err) }; return b }
```

### ESO 활용 (환경변수 주입 — 앱 코드는 백엔드를 모름)

```go
// ESO/VSO가 K8s Secret 동기화 -> Pod env -> os.Getenv
cfg := &Config{
	DBHost: os.Getenv("DB_HOST"),
	DBPass: os.Getenv("DB_PASSWORD"),
	APIKey: os.Getenv("API_KEY"),
}
```

```yaml
# Deployment에서 ESO가 생성한 Secret 사용
spec:
  containers:
    - name: my-app
      envFrom:
        - secretRef: {name: db-credentials}  # ESO 동기화 Secret
```

---

## 9. Spring 코드 예제

### Spring Cloud Vault

```yaml
# application.yml
spring:
  cloud:
    vault:
      uri: https://vault.example.com:8200
      authentication: KUBERNETES
      kubernetes:
        role: my-spring-app
        service-account-token-file: /var/run/secrets/kubernetes.io/serviceaccount/token
      kv: {enabled: true, backend: secret, default-context: my-spring-app}
  config:
    import: vault://
```

```java
@Configuration
public class DatabaseConfig {
    @Value("${db.host}") private String dbHost;       // Vault KV에서 자동 주입
    @Value("${db.password}") private String dbPassword;

    @Bean
    public DataSource dataSource() {
        HikariConfig c = new HikariConfig();
        c.setJdbcUrl("jdbc:postgresql://" + dbHost + ":5432/mydb");
        c.setPassword(dbPassword);
        return new HikariDataSource(c);
    }
}
```

### ESO + Spring (환경변수 주입)

```yaml
# application.yml — ESO가 동기화한 K8s Secret → 환경변수 → Spring @Value
spring:
  datasource:
    url: jdbc:postgresql://${DB_HOST}:5432/mydb
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}
```

---

## 10. Anti-Patterns

| 하지 말 것 | 해야 할 것 |
|-----------|-----------|
| `.env` 파일 Git 커밋 | ESO/Vault/Infisical 사용 |
| 시크릿 하드코딩 | 환경변수 또는 Secret Store |
| 슬랙/이메일로 시크릿 공유 | Infisical Dashboard / Vault UI |
| 만료 없는 API 토큰 | Dynamic Secrets + TTL |
| 모든 서비스 같은 시크릿 공유 | 서비스별 최소 권한 발급 |
| base64를 암호화로 착각 | SOPS/Vault Transit 적용 |
| 이미지 빌드 시 시크릿 포함 | 런타임 주입 (envFrom) |
| 로테이션 없이 영구 사용 | 자동 로테이션 정책 수립 |
| etcd 암호화 미설정 | EncryptionConfiguration 필수 |

---

## 11. 체크리스트

**기본 보안:**
- [ ] etcd 암호화 활성화 (EncryptionConfiguration)
- [ ] Secret RBAC 정책, NetworkPolicy 설정
- [ ] `.gitignore`에 `.env`, `*.key`, `*-secret.yaml` 추가

**시크릿 도구:**
- [ ] ESO 또는 Vault(VSO) 도입
- [ ] IRSA/Workload Identity 설정 (정적 자격증명 제거)
- [ ] refreshInterval 적절히 설정 (15m~1h)

**로테이션:**
- [ ] DB 자격증명 자동 로테이션 (Vault Dynamic Secrets)
- [ ] API 키 만료 정책 (max TTL 24h~7d)
- [ ] rolloutRestartTargets 설정 (시크릿 변경 시 Pod 재시작)
- [ ] 로테이션 실패 알림 (PagerDuty/Slack)

**개발자 경험:**
- [ ] 로컬 개발용 시크릿 접근 방법 문서화
- [ ] `infisical run` 또는 `vault` CLI 팀 표준화
- [ ] CI/CD 시크릿 주입 자동화
- [ ] Pre-commit 시크릿 스캐닝 (gitleaks, truffleHog)

**감사:**
- [ ] Vault Audit Log 활성화
- [ ] ExternalSecret 동기화 Prometheus 모니터링
- [ ] 분기별 시크릿 접근 권한 리뷰

---

## 12. 관련 Skills

- `/k8s-security` - K8s 보안 강화 (RBAC, PSP, OPA)
- `/terraform-security` - IaC 보안 (tfsec, Sentinel)
- `/gitops-argocd` - ArgoCD GitOps 워크플로우
- `/observability` - 모니터링 및 알림 설정
