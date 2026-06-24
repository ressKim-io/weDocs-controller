# proto — 단일 진실 공급원(SSOT)

모든 서비스 간 계약(gRPC)의 출처. gRPC 소비자 다운스트림 레포(`weDocs-crdt-engine`(Rust) / `weDocs-backend`(Java))는
이 디렉터리를 **buf 원격 git input**으로 직접 참조해 stub을 생성한다(submodule 불필요). → [ADR-0010](../docs/adr/0010-proto-distribution-buf-git-input.md)

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
  Java 네임스페이스는 `option java_package = io.wedocs.proto.*` 로 분리.
- **breaking = `FILE`** — wire 호환성 게이트(핵심 showcase).
- 향후 v2 도입이 필요하면 `wedocs.*.v1` + STANDARD로 승격.

## 명령
```sh
# controller (SSOT 검증)
buf lint proto
buf breaking proto --against '.git#branch=main,subdir=proto'
buf generate            # → ../gen (검증용; gitignored)

# 다운스트림 소비 (buf 원격 git input — submodule 없이)
buf export 'https://github.com/ressKim-io/weDocs-controller.git#subdir=proto,ref=<tag>' -o proto
#   Java: 이후 buf generate (java+grpc 플러그인) / Rust: tonic-prost-build 로 생성
```

## proto 배포 = buf 원격 git input (확정 — [ADR-0010](../docs/adr/0010-proto-distribution-buf-git-input.md))

git submodule은 "레포 단위"라 다른 레포의 하위 디렉터리만 가져올 수 없지만, **buf는 원격 git input의 서브디렉터리(`subdir=`)를 직접 지원**한다 — submodule 불필요:

```
buf export 'https://github.com/ressKim-io/weDocs-controller.git#subdir=proto,ref=<tag>,depth=50' -o proto
```

- 다운스트림은 `ref`를 **태그로 핀**해 재현성 확보(예: `proto-v0.1.0`). 계약 변경 = controller에서 태그 → 다운스트림 `ref` 갱신.
- SSOT는 controller에 유지. (검증: buf.build/docs/reference/inputs, 2026-06-25)
- Rust(crdt-engine)는 plugin/tonic 버전 skew 회피를 위해 `buf export` 후 `tonic-prost-build`로 생성, Java(backend)는 `buf generate`(java+grpc 플러그인) 사용.
