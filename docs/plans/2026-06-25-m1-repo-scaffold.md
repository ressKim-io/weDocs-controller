---
date: 2026-06-25
slug: m1-repo-scaffold
status: in-progress
related:
  - adr/0010-proto-distribution-buf-git-input.md
  - dev-logs/2026-06-25-m1-repo-scaffold.md
  - dev-logs/2026-06-25-m0-controller-scaffold.md
---

# weDocs — M1 수직 슬라이스 3레포 스캐폴딩 + proto 배포 확정

## Context

M0 완료 후 이전 세션이 남긴 블로커 3개를 이번 세션에 확정:
- **제품명 = weDocs** (Synapse 폐기) → proto `java_package` `io.synapse.*` → `io.wedocs.*`
- **proto 배포 = buf 원격 git input** — 다운스트림이 `buf`로 controller git의 `proto/` 서브디렉터리를 직접 input. **submodule 불필요**, SSOT=controller 유지. (검증: buf.build/docs/reference/inputs, 2026-06-25)
  - `buf export 'https://github.com/ressKim-io/weDocs-controller.git#subdir=proto,ref=<tag>' -o proto`
- **범위 = M1 3레포 골격**: `weDocs-crdt-engine`(Rust) + `weDocs-backend`(Java/ws-gateway) + `weDocs-frontend`(React). doc-service·ai-service 보류.
- **네이밍** = `weDocs-frontend / -backend / -ai-service / -crdt-engine` (org `ressKim-io`, 로컬 `~/my-file/weDocs/`)

### 검증된 스택 (공식 출처, 2026-06-25)

| 레포 | 스택 | codegen |
|---|---|---|
| crdt-engine (Rust) | yrs 0.27.2 · tonic 0.14.6 + prost 0.14.4 (hyper 1.0) · tokio 1.x · proptest · criterion · edition 2024 | `tonic-prost-build` (build.rs) |
| backend (Java) | Java 25 · Spring Boot 4.0.x (Java 25 first-class) · grpc-java 1.82.0 · Gradle 9.x | `buf generate` (java+grpc) |
| frontend (React) | React 19 · Vite · Tiptap 3 (`@tiptap/extension-collaboration`,`@tiptap/y-tiptap`) · yjs · y-websocket · y-protocols | proto 의존 없음 (WS만) |

### M1 아키텍처

```
Browser A (React+Tiptap+Yjs) ─WS(y-protocols sync)─┐
                                                    ├─► Java ws-gateway ─gRPC bidi(CrdtEngine.Sync)─► Rust crdt-engine
Browser B (React+Tiptap+Yjs) ─WS(y-protocols sync)─┘    (VT, 브리지)                                  (yrs 머지, doc별)
```
proto 소비자 = crdt-engine + backend 둘뿐. frontend는 gRPC 모름(표준 y-websocket provider).

---

## 실행 체크리스트

### Phase 0 — Plan-Logging 상시화 (이 plan 시작 전 먼저)
- [x] `.claude/rules/plan-logging.md` 신설
- [x] `CLAUDE.md` 항상-적용 import에 `@.claude/rules/plan-logging.md` 추가
- [x] memory `plan-logging-mandatory`(feedback) + `MEMORY.md` 인덱스
- [x] 이 파일(`docs/plans/2026-06-25-m1-repo-scaffold.md`) 작성
- [x] commit `docs(plans): add plan-logging rule and M1 scaffold plan` (18e5138) → 이 커밋 후 Phase A

### Phase A — controller 반영 (main 직접 커밋 허용) ✅
- [x] A1. `io.synapse.proto.*` → `io.wedocs.proto.*` (4 .proto + proto/README = 5)
- [x] A2. `proto/README.md` + `proto/buf.yaml`: submodule → buf git-input 메커니즘
- [x] A3. `docs/adr/0010-proto-distribution-buf-git-input.md` (대안 5종 비교표) + adr/README 인덱스 갱신
- [x] A4. SDD §12/§15: 레포명 weDocs-*, proto=buf git-input, blocker resolved→ADR-0010
- [x] A5. `docs/dev-logs/2026-06-25-m1-repo-scaffold.md` (category: decision, status: open)
- [x] A6. 검증 `buf lint proto && buf build proto` → 통과 ✅ (buf 1.71)
- [x] A7. commit 분할 (proto / adr / sdd / dev-log+plan)

### Phase B1 — weDocs-crdt-engine (Rust)
- [ ] Cargo.toml(edition 2024; yrs/tonic/tonic-prost/prost/tokio + build-dep tonic-prost-build + dev proptest/criterion)
- [ ] build.rs (tonic-prost-build), Makefile `proto-sync`(buf export, ref=main 시작)
- [ ] src/main.rs · src/engine.rs · src/service.rs 스텁
- [ ] tests/convergence_proptest.rs (commutative/associative/idempotent 골격)
- [ ] benches/convergence.rs, README, .gitignore
- [ ] 검증 `make proto-sync && cargo check` (buf/cargo 설치 시) · git init + 초기 커밋

### Phase B2 — weDocs-backend (Java/ws-gateway)
- [ ] settings/build.gradle.kts (Java25 toolchain, SpringBoot 4.0.x, Gradle 9.x wrapper)
- [ ] buf.gen.yaml(java+grpc) + Makefile proto-sync
- [ ] ws-gateway 모듈: GatewayApplication(VT), DocWebSocketHandler 스텁, EngineClient 스텁, application.yml
- [ ] README, .gitignore
- [ ] 검증 `./gradlew :ws-gateway:compileJava`(JDK25+net 가용 시; 아니면 미실행 명시) · git init + 초기 커밋

### Phase B3 — weDocs-frontend (React/Vite/TS)
- [ ] Vite React-TS scaffold (package.json, vite.config.ts, tsconfig.json, index.html)
- [ ] src/Editor.tsx (Tiptap3 + Collaboration + Y.Doc + WebsocketProvider→gateway), main/App
- [ ] .env.example(VITE_WS_URL), README, .gitignore
- [ ] 검증 `tsc --noEmit`/`npm run build`(install 비용 크면 lockfile까지) · git init + 초기 커밋

### Phase C — 외부 (건별 승인 필수, 도달 시 별도 요청) — **아직 안 함**
- [ ] gh repo create + push (3 레포)
- [ ] controller `proto-v0.1.0` 태그 → 다운스트림 ref 핀 전환

---

## 검증

- controller: `buf lint proto && buf build proto`, ADR 번호 0001→0002 연속
- crdt-engine: `cargo check`/`cargo test`(proptest 골격 컴파일)
- backend: `./gradlew :ws-gateway:compileJava`
- frontend: `tsc --noEmit` 또는 `npm run build`
- 로컬 환경(JDK25/Node/buf/cargo) 미설치로 못 돌린 검증은 **추정 통과 표기 금지** — "미실행" 명시 (deep-thinking.md)

## 범위 밖

- doc-service / ai-service 레포
- M1 수렴 로직 본체 (골격만; y-protocols↔gRPC 브리지·yrs 머지·proptest 본문은 후속)
- infra/ 서비스명·네임스페이스 갱신 (후속)
- 외부 GitHub 레포 생성·push (Phase C, 승인 전 보류)

## 미결 (write-time 재검증)

Gradle 정확 버전(Java25 toolchain), Spring Boot 패치(4.0.6 vs 4.1.0), Vite/React/Tiptap/proptest/criterion 정확 버전 — 각 빌드파일 작성 직전 확정 (workflow.md §spec 사전검증).

---

## 재개 지점 (Resume)

> **마지막 완료**: Phase A 전체 (proto rename·ADR-0010·SDD·dev-log; `buf lint/build` 통과).
> **다음**: Phase B1(weDocs-crdt-engine Rust 골격) → B2(backend) → B3(frontend).
> **주의**: 외부 작업(Phase C, push/gh)은 건별 승인 전까지 금지. 서비스 레포 골격은 로컬 git init+커밋까지만.
> **환경**: buf 1.71 · cargo 1.96 · java 25.0.3 · node 26 · gh 2.95 설치 확인 → 로컬 빌드 검증 가능.
