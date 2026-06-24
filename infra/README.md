# infra — GitOps 컨트롤 플레인

배포 타겟: **홈랩 KinD** + 로컬 GPU(Ollama, RTX 4060Ti). 클라우드/멀티클라우드 생략.

## 구성
- `k8s/` — kustomize `base/` + `overlays/homelab/`. 서비스 매니페스트(M5에서 채움).
- `istio/` — **Ambient** 메시.
  - `ambient/` — 네임스페이스 `istio.io/dataplane-mode=ambient` 라벨 → ztunnel L4 mTLS 자동(코드 무관).
  - `waypoint/` — **CRDT Engine에만** L7 waypoint + `DestinationRule`(consistentHash by docId 헤더).
- `argocd/` — app-of-apps (컨트롤러가 전체 배포 오케스트레이션).
- `terraform/` — (옵션) 클러스터 부트스트랩.

## 주의 (SDD §9)
- ⚠️ **WebSocket**: ztunnel 업그레이드가 long-lived TCP 연결을 리셋할 수 있음(pod는 생존) → 게이트웨이 재연결 필수.
- ⚠️ **health probe**: Ambient에서 kubelet probe가 ztunnel을 우회할 수 있음 → **in-pod gRPC/HTTP probe** 사용.
- **GPU**: AI Service만 GPU node affinity. CRDT Engine·게이트웨이는 일반 노드.
- **Rust 이미지**: 멀티스테이지 + `cargo-chef` 의존성 레이어 캐싱, distroless 런타임.
