---
date: 2026-06-25
category: decision
tier: 1
importance: major
status: open
tags: [m1, proto, buf, naming, wedocs, scaffold, plan-logging, session-handoff]
related:
  - plans/2026-06-25-m1-repo-scaffold.md
  - adr/0010-proto-distribution-buf-git-input.md
  - dev-logs/2026-06-25-m0-controller-scaffold.md
---

# M1 — weDocs 네이밍 확정 + proto 배포(buf git-input) + 3레포 골격 (세션)

## Context
- repo: `weDocs-controller`. M0 완료, 이전 세션이 블로커 3개(proto 배포 / 제품명 / M1 착수)를 남김.
- 이번 세션 목표: 블로커 확정 → controller 반영(+ADR) → M1 수직 슬라이스 3레포 골격.

## 결정 (decisions)
1. **제품명 = weDocs** (Synapse 코드네임 폐기). proto `java_package` `io.synapse.proto.*` → `io.wedocs.proto.*` (4 .proto).
2. **proto 배포 = buf 원격 git input** → [ADR-0010](../adr/0010-proto-distribution-buf-git-input.md). 다운스트림이 `buf export/generate`로 controller git의 `proto/` 서브디렉터리를 `subdir=`로 직접 참조. **submodule 불필요** — 이전 세션의 "submodule은 서브디렉터리 못 가져옴" 블로커가 무의미해짐. SSOT=controller 유지. ADR-0006의 submodule 가정 supersede.
3. **범위 = M1 3레포 골격**: `weDocs-crdt-engine`(Rust) + `weDocs-backend`(ws-gateway) + `weDocs-frontend`. doc-service·ai-service 보류.
4. **네이밍** = `weDocs-{frontend,backend,ai-service,crdt-engine}` (org `ressKim-io`).
5. **신규 상시 룰**: plan은 `docs/plans/`에 기록·**작업 전 커밋**(세션 유실 대비 재개) — `.claude/rules/plan-logging.md` + CLAUDE.md import + memory(feedback).

## 검증된 스택 (공식 출처, 2026-06-25) ✅
| 항목 | 값 | 출처 |
|---|---|---|
| buf 원격 git input `subdir=,ref=,depth=` | 지원(submodule 불요) | buf.build/docs/reference/inputs |
| yrs | 0.27.2 (2026-06-12) | crates.io/api/v1/crates/yrs |
| tonic / prost | 0.14.6 / 0.14.4 (hyper 1.0) | crates.io · ⚠️ devlog M0의 "tonic 0.12+"에서 상향 |
| Spring Boot | 4.0.x (Java 25 first-class) | spring.io blog 2025-11-20 |
| grpc-java | 1.82.0 | github grpc/grpc-java |
| Tiptap / 프론트 | 3 + yjs + y-websocket + y-protocols | tiptap.dev docs |

## 한 일 (Phase 0 / A)
- **Phase 0**: plan-logging 룰 신설 + CLAUDE.md import + memory + `docs/plans/2026-06-25-m1-repo-scaffold.md` 기록 (커밋 18e5138).
- **Phase A**: java_package rename(5곳) · `proto/README.md`+`buf.yaml` submodule→buf git-input · ADR-0010 작성(대안 5종 비교표) · `adr/README.md` 인덱스(0010 추가, 0006 주석, 미해결서 proto 항목 제거) · SDD §12/§15 갱신.

## 다음 (Phase B — 진행 중)
- B1 crdt-engine(Rust): Cargo+build.rs(tonic-prost-build)+엔진/서비스 스텁+proptest 골격(M1 가드레일).
- B2 backend(Java): Gradle 멀티모듈+ws-gateway(VT, WS↔gRPC 브리지 스텁).
- B3 frontend(React): Vite+Tiptap3+yjs+y-websocket(→gateway).
- 외부(Phase C, gh repo create/push)는 건별 승인 전 보류.

## 재개
> `docs/plans/2026-06-25-m1-repo-scaffold.md`의 재개 지점 참조. status: open — Phase B 완료 시 이 dev-log를 resolved로 갱신.
