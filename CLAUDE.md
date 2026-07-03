# Synapse Controller — 작업 가이드 (Claude Code)

이 레포는 5-repo 폴리레포의 **컨트롤 플레인**(proto SSOT · infra · CI · docs)이다.
실제 서비스 코드는 별도 레포에 있다 — **현재 존재**: `frontend` / `backend`(ws-gateway) / `crdt-engine`. **미생성(예정)**: `ai-service`(M4) · backend 내 `doc-service`(M2).

## 진입점
`docs/PRD.md` (무엇·왜) → `docs/SDD.md` (어떻게) → `docs/adr/` (결정 로그).

## 불변 규칙 (가드레일) — SDD §14
1. **proto는 여기서 시작.** 모든 계약 변경은 `proto/`에서 → `buf lint` + `buf breaking` 통과 → 다운스트림 buf 원격 git input ref bump(ADR-0010, **submodule 아님**) → 3언어 재생성. 다운스트림 레포에서 proto를 직접 고치지 않는다.
2. **AI Service는 CRDT 의존성을 가질 수 없다.** AI는 stateless 텍스트 in/out. (설계 위반)
3. **게이트웨이는 native call(JNI)을 도입하지 않는다.** VT pinning 방지.
4. **서비스 간 호출은 gRPC + OTel propagator를 통과한다.** W3C `traceparent` 통일.
5. **CRDT Engine은 "엔진"이다.** 단순 yrs 래퍼 PR은 반려 — 최적화 + `criterion` 벤치마크 동반.
6. **M1 머지 전 `proptest` 수렴 테스트 통과 필수.**
7. **크래프트 게이트 통과 없이 머지 금지.** 서비스 코드 PR은 크래프트 표준 6종 `[B]` 체크리스트(Gate 3 렌즈 🦀/☕) 통과 필수.
8. **무검증 입력·무상한 자원 금지.** 외부 입력은 경계 검증 후 도메인 타입으로, 신규 상태·수신 경로는 상한·수명 동반(`secure-coding.md` P1/P2).

## 언어 배정 (왜)
- I/O 바운드 → **Java 25 Virtual Thread** (ws-gateway, doc-service)
- AI 생태계 → **Python** (ai-service, indexer)
- CPU 바운드 + 정확성 critical → **Rust** (crdt-engine)

## 이 레포에서 자주 하는 일
- proto 편집 → `buf lint proto && buf breaking proto --against '.git#branch=main,subdir=proto'`
- 코드 생성(검증용) → `buf generate` (→ `gen/`, gitignored)
- infra → `infra/` (kustomize · istio ambient · argocd)

## 현재 상태
**M1 ✅ 완료(2026-06-30) + M2 readiness 게이트 ✅ 완료(2026-06-30).** M1 = "두 브라우저 동시 편집 수렴"(Phase 1~3) + 폴리글랏 단일 trace(Phase 4) + 마감(Phase 5), **proto 변경 없이 완수**. M2 readiness = 4 ADR + proto-v0.2.0 확정 → **M2 구현 착수 가능**(아래). proto 배포 = buf 원격 git input(ADR-0010, 현 태그 `proto-v0.2.0`·로컬, push는 서비스 레포 착수 시 승인).
- **Phase 1 ✅ crdt-engine(PR #1 머지, fbd25fe)**: yrs v1 권위 머지 + `tokio::broadcast` fan-out + gRPC bidi `Sync` 브리지. proptest 수렴·criterion 벤치 통과, 코드리뷰 8건 반영. doc-id=gRPC 메타데이터, 모든 인코딩 lib0 v1(Yjs 호환).
- **Phase 2 ✅ ws-gateway 브리지(Java, PR #1 머지, e0e8277)**: lib0 코덱(`varUint`/`varBuffer`) TDD + `DocWebSocketHandler` 세션당 Sync 스트림(메타데이터 `doc-id`=URL room) + `ServerFrame`→WS `Update(2)` + awareness/auth drop. 22 test pass, java-expert+code-reviewer 2-lens 반영.
- **Phase 3 ✅ frontend E2E 수렴(React, PR #1 머지, e8f0c83)**: `?room=` 다중문서 + vitest 2클라 y-websocket E2E(`disableBc:true`로 게이트웨이 경로만). 로컬 engine+gateway 실기동 → `WS→gateway→gRPC→engine→fan-out` 수렴 실측 green(gateway 로그로 gRPC 경로 확인). 'synced' 비의존 텍스트 폴링.
- **Phase 4.1 ✅ engine OTel(Rust, PR #2 머지, f2cdea2)**: W3C `traceparent` 수동 추출(`MetadataExtractor`→`span.set_parent`→`.instrument`) + OTLP/stdout 익스포터(구성 실패 시 콘솔만 degrade) + `eprintln!`→`tracing`. otel-expert cross-check 반영(shutdown→`spawn_blocking`·endpoint 로그·샘플러 주석). **thin 2-hop**: stream-open 1회 전파 → "한 WS 세션이 Java span→Rust span"(per-edit span·풀 관측 스택=M5). build/clippy -D warnings/fmt/test 8 pass.
- **Phase 4.2 ✅ gateway OTel javaagent(Java, backend PR #2 머지, 30e0aca)**: `make run-otel`(jar v2.29.0→`java -javaagent -jar`), **앱 코드·build.gradle 0**. live서 javaagent 2.x 기본 OTLP=http/protobuf 함정 발견→`OTEL_EXPORTER_OTLP_PROTOCOL=grpc` 수정(c8374d5, config-contract-audit 사례).
- **Phase 4.3 ✅ live 단일 trace 실측(Linux+docker Jaeger v2)**: traceID `eb852a8d…` — `[ws-gateway] crdt.CrdtEngine/Sync`(root) → `[wedocs-crdt-engine] crdt.sync`(child), 같은 trace(가드레일 4). 회귀 E2E 수렴 green. M1R-09(endpoint) 검증 기각=engine 무변경. `infra/local/docker-compose.jaeger.yml`.
- **Phase 5 ✅ 마감**: Phase 4 dev-log·M1 회고(`docs/retrospective/`)·ADR-0011(엔진 브리지)·SDD §15 미해결 소유 마일스톤 재배정.
- **M1.5 ✅ 벤치 Tier1 위생(engine PR #3 머지, 0b97c4a)**: `iter_batched`로 alloc/decode 분리(`merge`/`build_doc` 2그룹)·워크로드 4종(sequential/concurrent/with_deletes/large_paste)·`--save-baseline` 회귀 가드(Makefile, CI 신설 없이). 방법론 §4/§7 구현. dev-log=`docs/dev-logs/2026-06-30-m1.5-bench-hygiene.md`. (Tier2 샤딩 "N배"=M2/M3, Tier3 하니스=M5)
- **M2 readiness 게이트 ✅ 완료(2026-06-30, T3)** — M2 진입 blocker·결정 전부 확정. 산출: **ADR 0012**(CRDT 경계 내용/트리)·**0013**(스냅샷 영속화=**엔진 push**, `build_client(true)`, M2F-02 해소)·**0014**(인증/인가=JWT 발급 doc-service·검증 gateway·Sec-WebSocket-Protocol·viewer write-block)·**0015**(outbox 앱레벨, relay=M4) + **proto-v0.2.0**(LoadSnapshot·DocMeta page-tree, 로컬 태그·additive) + **PRD D-1~6 확정**(page-tree+workspace) + SDD §5 스키마·§15 갱신. M2 plan = `docs/plans/2026-06-30-m2-persistence-session.md`.
- **M2 구현 진행 중 — Phase 1a ✅ ([backend PR #3](https://github.com/ressKim-io/weDocs-backend/pull/3) 머지, `54a8b48`)**: doc-service 모듈 + Flyway page-tree 7테이블 + 핵심 엔티티 4종 + Testcontainers 영속 테스트 3건 green. 빌드 함정 2건(Spring Boot 4.x autoconfig 모듈화→스타터 필수·TC 2.x 좌표) = `docs/dev-logs/2026-06-30-m2-doc-service-1a-version-traps.md`.
- **크래프트 표준 정합 사이드트랙 ✅ 완료(2026-07-01)** — M2 Phase 1b 착수 전, 신규 도입된 4개 크래프트 표준(error-handling/concurrency/layering-readability/observability)이 지적한 기존 코드 갭을 정합. [crdt-engine PR #4](https://github.com/ressKim-io/weDocs-crdt-engine/pull/4) 머지(`65772d3`, thiserror+DashMap 샤딩+parking_lot+DocId newtype) → [backend PR #4](https://github.com/ressKim-io/weDocs-backend/pull/4) 머지(`18e1aa1`, 엔티티 Lombok 전환) → [crdt-engine PR #5](https://github.com/ressKim-io/weDocs-crdt-engine/pull/5) 머지(`0355a58`, `sync()` 함수 분해). 외부 제안(bumpalo Arena/jemalloc/write-behind) 검증 결과 Arena는 yrs 소유권 모델과 상충으로 영구 반려, jemalloc은 벤치 근거 없이 보류, write-behind는 이미 ADR-0013과 정합 확인(M2 Phase 3 몫). plan = `docs/plans/2026-07-01-craft-standards-alignment.md`(done).
- **크래프트 표준 v2 + 보안 스캔 CI 사이드트랙 ✅ 완료(2026-07-03)** — `design-patterns.md`·`secure-coding.md` 신설로 **크래프트 표준 6종 체제**(커밋 전 게이트 시뮬레이션: 기대 [B] 6종 발화·오탐 0·ADR-0013 seam 오지목 교정) + 렌즈/Gate 3 배선 + **PRD §6 NFR(보안 확장·코드 품질 행)·SDD §14 불변 규칙 ⑦⑧ 승격** + 4레포 보안 스캔 CI: controller gitleaks(`2b37069`) · [engine PR #6](https://github.com/ressKim-io/weDocs-crdt-engine/pull/6) 머지(`e925078`, +cargo-audit) · [backend PR #5](https://github.com/ressKim-io/weDocs-backend/pull/5) 머지(`0992f70`, +dependency-submission/review — 레포 dependency graph 활성화 함정) · [frontend PR #2](https://github.com/ressKim-io/weDocs-frontend/pull/2) 머지(`1d4dad5`, +npm audit). plan = `docs/plans/2026-07-03-security-quality-standards.md`(done) · dev-log = `docs/dev-logs/2026-07-03-craft-standards-v2-security-quality.md`. **기존 코드 소급 = `docs/plans/2026-07-03-secure-coding-retrofit.md`(planned, P0=3-레포 DoS 체인, M2 Phase 2 분기 전 실행)**.
- **다음 = Phase 1b(gRPC `DocService` 4 RPC)** — 사이드트랙 종료로 복귀. 새 브랜치. 이어 1c REST/JWT → **(Phase 2 분기 전: secure-coding retrofit)** → Phase 2 인증 / 3 엔진 저장(build_client flip) / 4 복원 / 5 outbox / 6 E2E. 횡단(T4) 병행. **1b부터 신규 PR은 크래프트 6종 게이트 적용**(unary deadline·인가 배선 [B] 즉시 해당).

> **재개 SSOT(M2 Phase 1b 진입)**: 진입점 = **`docs/plans/2026-06-30-m2-persistence-session.md`** §재개지점(1a=backend PR #3 머지 완료, 다음=1b gRPC — 크래프트 표준 사이드트랙 완료로 복귀). Phase 1 분해(1a/1b/1c)·구현 패턴은 같은 plan 참조. 게이트 트랙 = `docs/plans/2026-06-30-plan-audit-improvements.md`(T3 done·T4). M2 ADR = `docs/adr/0012`~`0015`. M2 readiness 후향 = `docs/dev-logs/2026-06-30-m2-readiness-gate.md` · 1a 빌드함정 = `docs/dev-logs/2026-06-30-m2-doc-service-1a-version-traps.md`. 크래프트 표준 정합 = `docs/plans/2026-07-01-craft-standards-alignment.md`(done) · **표준 v2+스캔 CI = `docs/plans/2026-07-03-security-quality-standards.md`(done)** · **retrofit = `docs/plans/2026-07-03-secure-coding-retrofit.md`(planned, Phase 2 분기 전)**. M1 회고 = `docs/retrospective/2026-06-30-m1-convergence.md`. ⚠️ 서비스 레포(backend/crdt-engine/frontend)는 branch+PR+건별 승인·push 승인. controller만 main 직접.
> ⚠️ 서비스 레포(backend/frontend/crdt-engine)는 일반 룰 = branch+PR+**건별 승인**. controller만 main 직접.

---

## 엔지니어링 표준 (도입: `ress-claude-agents`, 2026-05 기준)

개인 에이전트 컬렉션에서 이 프로젝트에 맞는 것만 도입 (제외: Go, frontend, business/payment/legal — 비범위).

### 항상 적용 (import)
@.claude/rules/clean-code.md
@.claude/rules/workflow.md
@.claude/rules/security.md
@.claude/rules/testing.md
@.claude/rules/debugging.md
@.claude/rules/user-approval.md
@.claude/rules/plan-logging.md

### 상황별 룰 (해당 작업 시 `.claude/rules/` 참조 — `paths:` frontmatter로 스코프됨)
- `git.md`·`code-review.md`·`deep-thinking.md` — 커밋/PR/품질 (보편)
- `java.md`·`spring.md` — ws-gateway, doc-service
- `error-handling.md`·`concurrency.md`·`layering-readability.md`·`observability.md`·`design-patterns.md`·`secure-coding.md` — 언어 무관 크래프트 표준 세트 6종(P1~N 원칙 + Java/Rust 실현 + `[B]`/`[A]` 체크리스트). `code-review.md` 크래프트 렌즈(🦀/☕)가 전부 실행
- `istio.md`·`k8s-manifest.md` — infra/istio, infra/k8s, argocd
- `monitoring.md` — OTel/PromQL/Grafana (폴리글랏 trace showcase)
- `version-compatibility.md` — K8s/Istio/ArgoCD/OTel 버전 매트릭스
- `config-contract-audit.md`·`documentation.md`·`phase-workflow.md`·`cloud-cli-safety.md`·`terraform.md`·`professional-writing.md`·`devlog-lifecycle.md`

> ⚠️ **stale (미import)**: `token-budget.md`·`effort-guide.md`는 **Opus 4.7 기준**(현재 4.8). 카운트·effort 단계가 현행과 달라 자동 적용 제외 — 참고만.

### 서브에이전트 (`Agent` 도구, `subagent_type`)
**Rust/CRDT `rust-expert`** ★(엔진 핵심) / 언어 `java-expert`·`python-expert` / 리뷰 `code-reviewer`·`cicd-reviewer`·`dockerfile-reviewer` / 아키텍처 `architect-agent`(proto·계약)·`saga-agent`(outbox) / 메시 `service-mesh-expert`(Istio Ambient) / 관측 `otel-expert`·`observability-reviewer` / K8s·GitOps `k8s-troubleshooter`·`k8s-reviewer`·`gitops-reviewer`·`platform-engineer` / 데이터 `database-expert`·`redis-expert` / 메시징 `messaging-expert` / 기타 `debugging-expert`·`git-workflow`·`tech-lead`

지식 참조: `.claude/skills/<category>/` (on-demand, 17개 카테고리 — `rust/`에 `crdt-yrs`·`crdt-convergence-testing` 신규). 신규 작성 표준: `.claude/templates/`.

---

## 커밋·push 규칙 (이 레포 전용 오버라이드)

> 일반 룰 `git.md`("main 직접 push 금지")·`user-approval.md`("push는 승인 후")를 **이 controller 레포에 한해** 오버라이드한다. controller는 솔로 컨트롤 플레인이라 PR 게이트가 불필요.

- ✅ **controller는 `main`에 직접 commit·push 허용** — push마다 별도 승인 안 받아도 됨(사용자 사전 승인됨).
- ✅ **커밋은 논리 단위로 분할** — 한 커밋에 몰지 말 것. 영역별(proto / docs / infra / ci / claude …) Conventional Commit.
- ⛔ **서비스 레포는 예외 아님** — `backend` / `ai-service` / `crdt-engine` / `frontend`는 일반 룰 적용(브랜치 + PR + 승인).
- 그 외(force push 금지, 시크릿 커밋 금지, `git add .` 지양·명시적 스테이징)는 `git.md` 그대로.
