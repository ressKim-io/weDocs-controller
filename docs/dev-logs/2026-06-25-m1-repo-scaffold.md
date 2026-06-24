---
date: 2026-06-25
category: decision
tier: 1
importance: major
status: resolved
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

## 한 일 (Phase B — 3레포 골격 완료, 로컬 커밋)
검증된 스택으로 각 레포 빌드까지 통과(로컬 환경: buf 1.71/cargo 1.96/java 25.0.3/node 26 전부 가용).
- **B1 weDocs-crdt-engine** (3eca141): yrs 0.27 + tonic 0.14(tonic-prost-build, vendored protoc) + proptest/criterion. `cargo check --all-targets`·`cargo test`(수렴 골격 2개) 통과.
- **B2 weDocs-backend** (f25491e): Gradle 9.1 + Spring Boot 4.1 + Java 25 VT, ws-gateway(WS 핸들러·EngineClient 스텁), `buf generate`(java v34.1/grpc v1.82.1) → `CrdtEngineGrpc`. `./gradlew :ws-gateway:compileJava` 통과.
- **B3 weDocs-frontend** (4527bec): Vite 8 + React 19 + Tiptap 3.27 + Yjs, WebsocketProvider→gateway. `npm run build`(tsc --noEmit + vite build) 통과.

## Phase C (완료 — PUBLIC push, 사용자 승인)
- controller main + `proto-v0.1.0` 태그 → origin push.
- `gh repo create ressKim-io/weDocs-{crdt-engine,backend,frontend} --public --push` 완료.
- 4레포 전부 GitHub PUBLIC. 이후 서비스 레포 변경은 일반 룰(브랜치+PR+승인).

## 학습 / 비고
- prost-build는 protoc 바이너리 필요 → `protoc-bin-vendored`로 시스템 설치 없이 해결(ADR-0010 codegen 경로 유지).
- backend는 Spring BOM이 protobuf-java를 다른 버전으로 관리할 수 있어 **4.34.1 명시 고정**(buf v34.1 정렬, config-contract-audit).
- proto 소비자는 crdt-engine·backend 둘뿐 — frontend는 y-websocket(gRPC 비소비자).
- **Linux 재현성 검증**: `.claude`(254: rules/skills198/agents21/templates)·`docs/plans`·lockfile(Cargo.lock·package-lock)·gradle wrapper(실행권한 보존)·protoc-bin-vendored(linux 포함) 전부 커밋 → `git pull`로 따라옴. 유일 gap = user-level `~/.claude/memory`(머신 로컬·홈경로 key) — plan-logging은 룰(`.claude/rules`)로 강제되므로 비핵심. 정리: [onboarding/guide.md](../onboarding/guide.md).

## 재개
> `docs/plans/2026-06-25-m1-repo-scaffold.md` 재개 지점 참조. Phase 0/A/B 완료(로컬). Phase C(push/gh/태그)는 사용자 승인 후.
