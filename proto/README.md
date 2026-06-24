# proto — 단일 진실 공급원(SSOT)

모든 서비스 간 계약(gRPC)의 출처. 다운스트림 레포(`backend` / `ai-service` / `crdt-engine`)는
이 디렉터리를 **git submodule**로 mount하고 각자 `buf.gen.yaml`로 stub을 생성한다.

## 레이아웃
```
common/common.proto   package common   — Role, DocRef (공용)
crdt/crdt.proto       package crdt     — CrdtEngine (bidi Sync, GetSnapshot)
doc/doc.proto         package doc      — DocService (CheckPermission, SaveSnapshot, GetDocMeta)
ai/ai.proto           package ai       — RagRetriever (내부 검색; 클라이언트向은 REST/SSE)
```

## 규칙
- **lint = `BASIC`** (`buf.yaml`). RPC 요청/응답을 도메인 이름(ClientFrame/ServerFrame/DocRef)으로
  쓰기 위해 STANDARD의 `RPC_*_STANDARD_NAME`/`PACKAGE_VERSION_SUFFIX`는 적용하지 않는다.
  플랫 레이아웃에 맞춰 패키지는 단일 세그먼트(`common`/`crdt`/`doc`/`ai`).
  Java 네임스페이스는 `option java_package = io.synapse.proto.*` 로 분리.
- **breaking = `FILE`** — wire 호환성 게이트(핵심 showcase).
- 향후 v2 도입이 필요하면 `synapse.*.v1` + STANDARD로 승격.

## 명령
```sh
buf lint proto
buf breaking proto --against '.git#branch=main,subdir=proto'
buf generate            # → ../gen (검증용; gitignored)
```

## ⚠️ submodule 주의 (M0 미해결 — SDD §15)
git submodule은 "레포 단위"라 **다른 레포의 하위 디렉터리만** 가져올 수 없다.
다운스트림이 `proto/`만 mount하려면:
- (a) proto를 별도 레포(`synapse-proto`)로 분리해 submodule, 또는
- (b) controller 전체를 submodule로 두고 `proto/` 경로를 참조.

M1 시작 전 확정 필요.
