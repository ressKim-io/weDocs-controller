# ADR-0007 — Istio Ambient Mesh 채택

- 상태: **Accepted**
- 날짜: 2026-06-24 (SDD v2 확정 시 결정, 2026-08-03 정식 ADR 승격)
- 관련: ADR-0004 · SDD §9·§15.7

## 맥락

서비스 간 통신에 mTLS(NFR 보안)와 L7 트래픽 관리(consistent hash 라우팅)가 필요하다.
CRDT 엔진은 stateful이라 **같은 문서 = 같은 인스턴스**로 라우팅해야 한다(ADR-0004).
이 두 요구를 애플리케이션 코드에 구현하면 4개 서비스 × 2개 언어에 중복 배선이 생긴다.

## 결정

**Istio Ambient Mesh**를 채택한다.

- **ztunnel (L4)**: 전 서비스 mTLS 자동 적용 — 사이드카 없이 노드당 1 프록시
- **waypoint (L7)**: CRDT 엔진에만 배치 — gRPC 메타데이터(`doc_id`)로 consistent hash 라우팅
- 나머지 서비스(gateway, doc-service, ai-service)는 ztunnel L4만으로 충분

## 대안 비교

| 대안 | 장점 | 단점 (기각 사유) |
|---|---|---|
| **A. Istio Ambient (채택)** | 사이드카 없음(리소스 절약), L4 기본 + L7 선택적 | 비교적 신규 (GA 2024), 디버깅 경험 적음 |
| **B. Istio Sidecar (전통)** | 가장 성숙, 문서 풍부 | 파드당 envoy = 리소스 2배, 홈랩에 과다, 모든 서비스에 L7 오버헤드 |
| **C. Linkerd** | 경량, Rust 기반 프록시 | consistent hash 라우팅 미지원 (TrafficPolicy 제한적) |
| **D. 앱 레벨 구현** | 외부 의존 없음 | 4서비스 × mTLS + hash ring 직접 구현 = 유지보수 지옥 |
| **E. Service Mesh 없음** | 단순함 | mTLS 수동 배선, 평문 노출 구간, 라우팅은 별도 솔루션 |

## 결과

- M5(인프라 배포)에서 실적용
- ztunnel = 모든 네임스페이스에 활성화 → `PeerAuthentication: STRICT` (평문 거부)
- waypoint = `crdt-engine` 서비스에만 → `HTTPRoute` consistent hash on `doc_id` 메타
- NetworkPolicy: 엔진 직접 접근 차단 (gateway만 허용) — M5에서 "엔진 gRPC 우회" 방어 완성
- 로컬 개발(M2 이하): mesh 없이 직접 연결 (Istio는 M5 이후)
- consistent hash 키 = gRPC 메타데이터 `doc_id` (M3 plan에서 상세화 예정)
