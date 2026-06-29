# SDD — 인프라 · 관측 · 테스트
> [← 인덱스](../SDD.md)

## 9. 인프라 / 배포 (Istio Ambient 상세)

- **메인 타겟**: 홈랩 KinD (Ollama GPU 로컬). 클라우드/멀티클라우드 생략.
- **서비스 메시 = Istio Ambient**:
  - **ztunnel** (노드 DaemonSet, L4) — 전 서비스 자동 mTLS. 코드 무관.
  - **waypoint** (L7) — **CRDT Engine에만** 붙임. 이유: gRPC consistent hash 라우팅(docId) 필요. 나머지는 L4 mTLS면 충분 → waypoint 불필요(리소스 절약).
  - consistent hash: `DestinationRule.trafficPolicy.loadBalancer.consistentHash` (by header = docId)
  - ⚠️ **WebSocket 주의**: ztunnel 업그레이드가 long-lived TCP 연결 리셋 가능(pod는 생존) → 게이트웨이 재연결 필수
  - ⚠️ **health probe**: Ambient에서 노드 발 kubelet probe가 ztunnel 우회 가능 → **in-pod gRPC/HTTP probe** 사용
- **GitOps**: ArgoCD app-of-apps (controller 관리)
- **GPU 스케줄링**: AI Service만 GPU node affinity. CRDT Engine·게이트웨이는 일반 노드.
- **Rust 이미지 빌드(M5 — 현재 미구현)**: 멀티스테이지 + **cargo-chef**로 의존성 레이어 캐싱(컴파일 느림 완화), distroless 런타임. (서비스 레포 Dockerfile/CI 전반 = M5)

---

## 10. 관측 (폴리글랏 OTel — 핵심 showcase)

3언어 단일 trace가 이 프로젝트의 차별점. 폴리글랏의 가장 큰 운영 난점(JVM↔Python↔Rust 추적 갭)을 OTel로 해결.

- **SDK**: Java(Micrometer/spring-boot-starter-opentelemetry), Python(opentelemetry-python), Rust(`tracing` + `opentelemetry`). 전부 **OTLP**로 통일.
- **propagation**: **W3C traceparent** 통일. gRPC는 otelgrpc 인터셉터.
- ⚠️ **async 경계**: Kafka(Doc→Indexing Consumer)는 HTTP 헤더 전파가 안 됨 → trace context를 **메시지 페이로드에 주입·추출**.
- ⚠️ **clock skew**: 멀티노드 span 타임스탬프 → **NTP 동기화**.
- ⚠️ **SDK 버전**: 언어별 SDK의 OTLP·semantic convention 버전 정합.
- **메트릭**: AI 추론 **큐 대기시간 vs 추론시간 분리**, CRDT 머지 지연, WS 활성 커넥션 수.
- **백엔드**: LGTM(기존 경험 재활용).

---

## 11. 테스트 전략

- **CRDT 수렴 (최중요)**: property-based testing(Rust `proptest`) — 랜덤 연산 시퀀스를 여러 순서로 적용해 모든 replica 동일 수렴을 수천 회 검증.
- **엔진 성능**: `criterion` 벤치마크 — 머지/diff/스냅샷 처리량, "단순 래퍼 대비" 비교 수치.
- **Yjs ↔ yrs 상호운용 (M1 필수)**: 클라 Yjs update를 서버 yrs가 적용·복원, 역방향도.
- **gRPC 계약**: `buf breaking`(M1 ✅, controller proto-ci) + 통합 테스트(Testcontainers: PG/Redis/Kafka) **(M2)**.
- **AI (M4)**: RAG 검색 정확도(고정 코퍼스), 폴백 트리거(GPU 포화 모킹), SSE 스트림 무결성.

---
