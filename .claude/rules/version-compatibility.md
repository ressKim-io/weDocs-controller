---
paths:
  - "**/Chart.yaml"
  - "**/values*.yaml"
  - "**/values*.yml"
  - "**/argocd/**"
  - "**/istio/**"
  - "**/build.gradle*"
  - "**/pom.xml"
  - "**/package.json"
  - "**/go.mod"
  - "**/version-matrix*"
---

# Version Compatibility Rules

K8s, Istio, ArgoCD, 모니터링 스택, 언어 런타임 등 **계층화된 dependency 스택**에서 버전 업그레이드/변경 작업 시 적용한다.

## 출발점: 버전 매트릭스를 SoT로

각 프로젝트는 `docs/version-matrix.md`(또는 동등한 파일) 을 **Single Source of Truth** 로 둔다. 이 rule은 매트릭스 자체를 관리하는 방법을 다룬다 — 구체 버전 값은 프로젝트마다 채운다.

**매트릭스에 들어가야 할 최소 항목**:

```
- K8s API server / 노드 OS / kubelet 호환 윈도우
- 컨트롤 플레인 (ArgoCD, Argo Rollouts, cert-manager 등) 지원 K8s 범위
- 서비스 메시 (Istio / Linkerd) 지원 K8s 범위 + 지원 모드
- 모니터링 스택 (Grafana / Prometheus / Tempo / Loki / Mimir / Alloy) 지원 spec
- 언어/프레임워크 (Java/Spring, Go, Python 등) 런타임 + LTS 정책
- 관측 표준 (OTel SDK / instrumentation BOM / OTLP exporter)
- Helm chart repository 출처 (community 이관 추적)
```

---

## 작업 전 확인 (MANDATORY)

다음 작업 수행 전 **반드시 `docs/version-matrix.md`를 읽고** 호환성을 확인한다.

- Helm chart 버전 변경 또는 업그레이드
- K8s manifest 작성/수정 (API version 확인)
- 서비스 메시 설정 변경 (values 구조, CRD 이름)
- ArgoCD Application/ApplicationSet 수정
- 언어 런타임 또는 프레임워크 의존성 변경
- 모니터링 스택 설정 변경
- docker-compose / Dockerfile 베이스 이미지 변경

---

## 버전업 워크플로우 (MANDATORY)

라이브러리/차트/런타임을 업그레이드할 때 다음 순서를 지킨다.

```
1. CHANGELOG / Release Notes / Migration Guide WebFetch
   ↓
2. Breaking change 항목 식별 — 명시값 + 기본값 + 제거된 key
   ↓
3. 의존성 매트릭스 영향 분석 — 상위/하위 호환 윈도우 재확인
   ↓
4. dev 환경에서 검증 → manifest diff 확인
   ↓
5. version-matrix.md 갱신 — 새 버전 + 검증 일자 + 알려진 제약
   ↓
6. prod 적용
```

---

## 의존성 매트릭스의 흔한 함정

| 함정 | 사례 |
|------|------|
| **컨트롤 플레인 지연** | K8s 신규 마이너 출시 후 ArgoCD / Istio 등이 지원할 때까지 업그레이드 차단 (예: ArgoCD가 K8s 새 minor 지원에 ~3개월 지연) |
| **모니터링 스택 분기** | 한 벤더 안에서도 community 이관 / commercial 이관이 chart별로 다름 (Grafana Tempo는 community, Loki는 grafana org 유지 등) |
| **BOM 덮어쓰기** | Spring Boot `dependency-management`가 OTel BOM의 instrumentation 버전을 다운그레이드 |
| **CRD breaking change** | Istio 1.x → 1.y minor 업그레이드 시 CRD 필드 이름 변경 (예: `MeshConfig.localityLbSetting` 위치 이동) |
| **API 버전 deprecation** | K8s manifest의 `networking.k8s.io/v1beta1` 등 사용 잔재 — apply 시점에 silent skip |

---

## 절대 금지 (MANDATORY)

- **버전 매트릭스 외부의 버전 사용** — 매트릭스에 없는 버전 채택 전 반드시 매트릭스 갱신 PR 선행
- **OTel Java Agent + Spring Boot Starter 동시 사용** — 이중 계측 발생, exporter 충돌
- **OTel instrumentation BOM 없이 개별 버전 관리** — Spring dependency-management에 의한 다운그레이드
- **Helm chart 메이저/마이너 업그레이드 시 breaking change 미확인** — production CrashLoop의 주된 원인
- **K8s 마이너 업그레이드 시 컨트롤 플레인 지원 범위 미확인** — ArgoCD/Istio/cert-manager 등이 지원 못 하면 차단됨

---

## 프로젝트 부트스트랩 가이드

신규 프로젝트가 ress-agents fork 후 매트릭스를 시작하는 절차:

```
1. docs/version-matrix.md.template 복사 → docs/version-matrix.md
2. 현재 사용 버전 채우기 (K8s, 컨트롤 플레인, 서비스 메시, 모니터링, 언어)
3. 각 라이브러리의 지원 윈도우 (https://endoflife.date 등) 확인 후 EOL 표기
4. CI에 매트릭스 drift 검출 추가 (예: 실제 deployed 버전 vs 매트릭스 비교)
```

---

## 참조

- 의존성 매트릭스 템플릿: `.claude/templates/version-matrix.md.template` (별도 PR에서 추가)
- breaking change 추적: 각 도메인 skill의 pitfall 카탈로그 (`infrastructure/eks-pitfalls.md`, `service-mesh/istio-pitfalls.md` 등)
