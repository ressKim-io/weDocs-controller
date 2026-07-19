# Synapse Controller — 작업 가이드 (Claude Code)

이 레포는 5-repo 폴리레포의 **컨트롤 플레인**(proto SSOT · infra · CI · docs)이다.
실제 서비스 코드는 별도 레포에 있다 — **현재 존재**: `frontend` / `backend`(ws-gateway + doc-service) / `crdt-engine`. **미생성(예정)**: `ai-service`(M4).

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
- **M2 구현 진행 중 — Phase 1b ✅ ([backend PR #6](https://github.com/ressKim-io/weDocs-backend/pull/6) 머지, `1d7ce7b`)**: gRPC `DocService` 4 RPC(`CheckPermission`/`SaveSnapshot`/`LoadSnapshot`/`GetDocMeta`) 구현 + `WorkspaceMember`/`PagePermission` 복합키(`@EmbeddedId`, 이 코드베이스 최초) 엔티티 + PRD §4.2 유효 권한 해석(명시 권한>조상 상속>workspace baseline>거부, 조상 탐색 캡 fail-closed) + gRPC 서버 배선(`SmartLifecycle`+VT executor). 2라운드 리뷰(크래프트 게이트 java-expert+code-reviewer, max-effort 10-앵글 코드리뷰) 전부 반영, 32개 테스트 green. plan = `docs/plans/2026-07-04-m2-phase1b-docservice-grpc.md`(done).
- **M2 구현 진행 중 — Phase 1c PR① ✅ ([backend PR #7](https://github.com/ressKim-io/weDocs-backend/pull/7) 머지, squash `a7e3a27`)**: RS256 JWT 발급(`JwtKeys`/`JwtTokenService`, kid=RFC 7638 thumbprint, ADR-0017) + JWKS 공개 엔드포인트 + Security 배선(stateless·기본 거부·CSRF disable 근거·`@CurrentUserId` 경계 변환) + signup/login REST(계정 존재 비노출 동일 401) + 도메인 예외 계층·ProblemDetail(RFC 9457). 크래프트 게이트 2-리뷰 반영, 53건 green. Boot 4.x 함정 3건(테스트 슬라이스 스타터 분리·Jackson 3 `tools.jackson`·TC 2.x 비제네릭) = `docs/dev-logs/2026-07-13-m2-doc-service-1c-boot4-traps.md`.
- **gitleaks 오탐 베이스라인 사이드트랙 ✅ 완료(2026-07-17)** — 보안 스캔 CI(2026-07-03 신설)의 **오탐 베이스라인을 한 번도 green으로 만들지 않았던 갭** 정합. 실제 유출 0, 오탐 4건. 원인 2개: ① **fingerprint 커밋 핀 ↔ squash 머지** — `.gitleaksignore`는 `<commit>:<path>:<rule>:<line>`이라 squash의 SHA 재작성에 즉사(backend PR #7: PR green → main red = **게이트 false pass**) ② **트리거별 스캔 범위 차이** — push=마지막 커밋만/schedule=전체 히스토리라 **controller 주간 red가 최초 실행부터 2주간 은폐**. 조치: `.gitleaks.toml` allowlist(SHA 비의존, `condition="AND"`로 경로+모양 한정, **경로 blanket 금지**) + `workflow_dispatch`(전체 히스토리 즉시 검증). ⚠️ **`targetRules`는 8.25.0 신설 — CI(`action@v3`)는 8.24.3이라 사용 불가** → 룰 재선언으로 스코프. **대조군으로 룰 생존 증명**(허용 경로에 진짜 RSA 키 삽입 → 발화 — 억제와 무력화는 겉으로 똑같이 "no leaks found"). controller `9d62d65` · [backend PR #8](https://github.com/ressKim-io/weDocs-backend/pull/8) squash 머지(`2290ce0`, **squash 후에도 green = 최종 증명**) · engine·frontend 무변경(원래 green). plan = `docs/plans/2026-07-17-gitleaks-false-positive-baseline.md`(done) · dev-log = `docs/dev-logs/2026-07-17-gitleaks-fingerprint-squash-trap.md` · 표준 = `secure-coding.md` §게이트 배선(자동 스캔 게이트 완료 조건 6항목).
- **M2 구현 진행 중 — Phase 1c PR② ✅ ([backend PR #9](https://github.com/ressKim-io/weDocs-backend/pull/9) 머지, squash `290bf69`, 2026-07-17)**: 리소스 REST 10 엔드포인트 — workspace 생성(생성자=owner 같은 tx)/목록/멤버 초대(owner 전용, 레이스=복합 PK 캐치) + 페이지 트리 CRUD/**move**(워크스페이스 행 `PESSIMISTIC_WRITE` 직렬화 + 사이클 fail-closed 64 + 교차 ws 409)/아카이브(가역 D-4) + 공유 PUT(UPSERT)/DELETE(멱등, owner 전용). 인가 가드 2종(no-read/비멤버=404 비노출, 권한 부족=403) — 1b `resolve()` 재사용. 전체 102건 green. **Phase 1c(1a·1b·1c①②) 완결.** ⚠️ 크래프트 게이트 findings **미반영 머지**(사용자 지시) — HIGH 2(아카이브 자손 목록 잔존·move 락 이전 L1 캐시 stale 추정)+MEDIUM 5+LOW 7 = 1c plan §PR② 게이트 findings.
- **표준 확장 + 리팩토링 트랙(에러 카탈로그·package-by-feature) ✅ 완료(2026-07-18)**: 사용자 요구(읽기 좋은 코드·enum 에러 관리·패키지 구조·모델 티어링)에 대한 표준 정립 + doc-service 4 PR 리팩토링.
  - **Step ① 표준(controller)**: error-handling.md **P7 에러 카탈로그**(서비스별 ErrorCode enum SSOT + 카테고리 예외 4~5종) + layering-readability.md **P7 package-by-feature**(`[B]` 통패키지 금지) + spring.md ProblemDetail 정합 + git.md move-only 산정 + **ADR-0018/0019/0020** + effort-guide·token-budget **현행화**(Claude 5/Opus 4.8 세대, stale 해소, 리뷰=sonnet 티어링 판단). dev-log = `2026-07-17-error-catalog-package-standards.md`.
  - **Step ②③ 백엔드 4 PR (전부 머지, 148건 green, 크래프트 6종 2-렌즈 게이트)**: [#10](https://github.com/ressKim-io/weDocs-backend/pull/10) `a40bae5` 1c 게이트 findings(아카이브 도달성 BFS·move 인가→락→clear·InOrder 결정적 가드) → [#11](https://github.com/ressKim-io/weDocs-backend/pull/11) `080cec7` 에러 카탈로그(DocErrorCode enum+카테고리 5종, HTTP/gRPC 매핑 isInternal 단일화, leaf 12 삭제, 불변식 비노출 회귀 가드) → [#12](https://github.com/ressKim-io/weDocs-backend/pull/12) `9c870a5` 중복 제거(공유 인가 통합 시 **IDOR 붕괴 보존** 위해 not-found 코드 오버로드·교차 feature repo 주입 제거·MAX_ANCESTOR_DEPTH→Page 도메인) → [#13](https://github.com/ressKim-io/weDocs-backend/pull/13) `3b51772` **package-by-feature**(auth/workspace/page/snapshot/common, move-only=로직 diff 비어있음 증명, base package 불변→스캔·JPA·Flyway 무영향). dev-log = `2026-07-18-m2-refactor-track-backend.md`.
- **secure-coding retrofit ✅ 완료(2026-07-18)** — 3-레포 관통 DoS 체인(무검증 room → 무한 문서 생성) 소급 차단. **crdt-engine**: `DocId` 검증 생성자(`TryFrom`, 길이 1..=128·`[A-Za-z0-9_-]`) + 문서 수 상한(`MAX_DOCUMENTS`)+`resource_exhausted` + `max_decoding_message_size` 명시 — [PR #9](https://github.com/ressKim-io/weDocs-crdt-engine/pull/9) 머지(`5854b72`). **backend/ws-gateway**: `RoomId`(엔진과 동일 규칙) + `RoomHandshakeInterceptor`(WS 업그레이드 전 검증) + 프레임/버퍼 상한 + Origin 화이트리스트 + gRPC keepalive — [PR #14](https://github.com/ressKim-io/weDocs-backend/pull/14) 머지(`1d94a9a`). **backend/doc-service**: dev DB 크리덴셜 fail-closed(env 주입 필수) + dead 쿼리 삭제 — [PR #15](https://github.com/ressKim-io/weDocs-backend/pull/15) 머지(`a74667b`). **frontend**: `sanitizeRoom` + `wss://` 강제 승격 — [PR #3](https://github.com/ressKim-io/weDocs-frontend/pull/3) 머지(`f7b5b92`). 4 PR 전부 크래프트 게이트 블로킹 0. plan = `docs/plans/2026-07-03-secure-coding-retrofit.md`(done) · dev-log = `docs/dev-logs/2026-07-18-secure-coding-retrofit-completion.md`. ⚠️ 이 4 PR은 controller와 별도 세션에서 진행돼 plan 상태 갱신이 하루 지연 — 2026-07-19 4레포 pull 동기화 중 드리프트 발견·정합.
- **다음 = Phase 2 인증** — M2 본류(`docs/plans/2026-06-30-m2-persistence-session.md` §재개지점: 3 엔진저장(build_client flip)·4 복원·5 outbox·6 E2E). 횡단(T4) 병행. 크래프트 6종(+P7) 게이트 계속 적용. 로컬 backend 테스트 = colima 필요(메모리 `backend-testcontainers-colima` 참조).

> **재개 SSOT(Phase 2 진입)**: retrofit 완결 → **다음 = Phase 2 인증**(M2 본류 = `docs/plans/2026-06-30-m2-persistence-session.md` §재개지점: 3 엔진저장·4 복원·5 outbox·6 E2E). retrofit 상세 = `docs/plans/2026-07-03-secure-coding-retrofit.md`(done) + `docs/dev-logs/2026-07-18-secure-coding-retrofit-completion.md`. 리팩토링 트랙 상세·교훈 = `docs/plans/2026-07-17-error-catalog-package-by-feature.md`(done) + `docs/dev-logs/2026-07-18-m2-refactor-track-backend.md`. ⚠️ **doc-service 구조 = package-by-feature**(ADR-0019): 신규 코드는 feature 패키지(auth/workspace/page/snapshot) 평면에, 공용은 common/(error·jpa·validation)에. 도메인 에러는 카탈로그(DocErrorCode enum + 카테고리 예외, ADR-0018)로만. Phase 1 분해·구현 패턴은 같은 plan 참조. **1c 상세·게이트 findings 목록 = `docs/plans/2026-07-12-m2-phase1c-rest-jwt.md`(done, §PR② 게이트 findings 이월)** · 1b 상세 = `docs/plans/2026-07-04-m2-phase1b-docservice-grpc.md`(done) · JWT 서명 결정 = `docs/adr/0017-jwt-rs256-jwks.md`. 게이트 트랙 = `docs/plans/2026-06-30-plan-audit-improvements.md`(T3 done·T4). M2 ADR = `docs/adr/0012`~`0015`. M2 readiness 후향 = `docs/dev-logs/2026-06-30-m2-readiness-gate.md` · 1a 빌드함정 = `docs/dev-logs/2026-06-30-m2-doc-service-1a-version-traps.md` · 1c Boot4 함정 = `docs/dev-logs/2026-07-13-m2-doc-service-1c-boot4-traps.md`. 크래프트 표준 정합 = `docs/plans/2026-07-01-craft-standards-alignment.md`(done) · **표준 v2+스캔 CI = `docs/plans/2026-07-03-security-quality-standards.md`(done)**. M1 회고 = `docs/retrospective/2026-06-30-m1-convergence.md`. ⚠️ 서비스 레포(backend/crdt-engine/frontend)는 branch+PR+건별 승인·push 승인. controller만 main 직접.
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
- `token-budget.md`·`effort-guide.md` — 모델 라인업·effort·캐시 수치 현행판(**Claude 5/Opus 4.8 세대, 2026-07-17 WebFetch 검증**) + 이 레포 21 agents 티어링 매핑·판단 기록. 모델/effort 관련 결정 시 참조 (⚠️ `/token-budget` 스킬 본문은 구버전일 수 있음 — rule이 우선)

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
