# 시스템 개요 (Architecture Overview)

> 한 페이지로 시스템 전체를 조망한다. 상세는 각 링크 문서 참조.

**최종 갱신**: 2026-08-03

---

## 한 줄 정의

실시간 협업 문서 편집(CRDT) + AI co-pilot(RAG). 폴리글랏 MSA(Java/Rust/Python).

## 서비스 토폴로지

```
┌──────────────┐       WebSocket        ┌──────────────┐     gRPC bidi     ┌──────────────┐
│   Frontend   │ ◄───────────────────► │  WS Gateway  │ ◄──────────────► │ CRDT Engine  │
│  (React/Yjs) │                       │ (Java VT)    │                   │   (Rust/yrs) │
└──────────────┘                       └──────┬───────┘                   └──────┬───────┘
                                              │ gRPC                              │ gRPC
                                              ▼                                  ▼
                                       ┌──────────────┐              SaveSnapshot/LoadSnapshot
                                       │ Doc Service  │ ◄───────────────────────────┘
                                       │ (Java/Spring)│
                                       └──────┬───────┘
                                              │ SQL
                                              ▼
                                       ┌──────────────┐
                                       │  PostgreSQL   │
                                       └──────────────┘

                    ┌──────────────┐     Kafka (M4)     ┌──────────────┐
                    │  Outbox Relay │ ──────────────── → │  AI Service  │
                    │  (M4, Java)  │                    │ (Python/RAG) │
                    └──────────────┘                    └──────────────┘
```

## 레포 구조 (5-repo 폴리레포)

| 레포 | 언어 | 역할 |
|---|---|---|
| `weDocs-controller` | — | proto SSOT, ADR, plan, infra(kustomize) |
| `weDocs-backend` | Java 25 | ws-gateway + doc-service (Spring Boot) |
| `weDocs-crdt-engine` | Rust | yrs 기반 CRDT 엔진 (tonic gRPC) |
| `weDocs-frontend` | TypeScript | React + Tiptap + Yjs |
| `weDocs-ai-service` | Python | FastAPI + LlamaIndex (M4 신설 예정) |

## 핵심 결정 (ADR)

| ADR | 결정 |
|---|---|
| [0001](../adr/0001-language-strategy-b.md) | 언어 전략: I/O=Java VT, AI=Python, CPU=Rust |
| [0004](../adr/0004-rust-bidi-engine.md) | Rust 독립 gRPC 엔진 + bidi streaming |
| [0005](../adr/0005-yrs-crdt-library.md) | CRDT 라이브러리 = yrs |
| [0007](../adr/0007-istio-ambient.md) | Istio Ambient (ztunnel L4 + waypoint L7) |
| [0010](../adr/0010-proto-distribution-buf-git-input.md) | proto 배포 = buf 원격 git input |
| [0013](../adr/0013-snapshot-persistence-lifecycle.md) | 스냅샷 영속화 = 엔진 push |
| [0014](../adr/0014-auth-authz-boundary.md) | 인증/인가 경계 (JWT + CheckPermission) |

## 마일스톤

| M | 목표 | 상태 |
|---|---|---|
| M1 | CRDT 코어 — 두 브라우저 수렴 | ✅ |
| M2 | 영속화·세션·권한 | ✅ |
| M3 | Presence — 커서·선택 fan-out (멀티인스턴스) | ⬜ |
| M4 | AI co-pilot — RAG 스트리밍, GPU 폴백 | ⬜ |
| M5 | 인프라·관측 — GitOps, 단일 trace | ⬜ |
| M6 | 마감 — 문서·데모·벤치마크 | ⬜ |

## 진입점

- 제품 요구: [PRD](../PRD.md)
- 설계 상세: [SDD](../SDD.md)
- 현재 위치: [status/current.md](../status/current.md)
- DoD 추적: [status/dod-tracker.md](../status/dod-tracker.md)
- 관측 설계: [design/observability-callsites.md](observability-callsites.md)
