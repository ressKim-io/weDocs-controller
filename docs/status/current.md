# 현재 상태 — 재개 SSOT

> **이 파일이 "지금 어디까지 왔고 다음에 뭘 하나"의 유일한 출처다.**
> CLAUDE.md는 이 파일을 가리키는 포인터만 갖는다(진척 이력을 CLAUDE.md에 두지 않는 이유 = 공식 가이드의 "자주 바뀌는 정보 제외" + 그 편집 지점이 곧 드리프트 지점이었다는 실증).
> 완료 이력 = [`history.md`](history.md) · 상세 실행 계획 = `docs/plans/`

**최종 갱신**: 2026-08-03

---

## 지금

**M2 Phase 6(E2E 복원·권한 검증) 완료(2026-08-03).** backend PR #25 머지(`ba0406c`). 181 테스트 전체 통과.
**M2 마일스톤 전체 완료.** proto-doc 파이프라인도 동시 완성(controller `7999aa6`).

> 2026-08-03 Phase 6 완료 — E2E 스냅샷 복원 + 권한 상속 gRPC 검증 테스트 17건 추가.
> 2026-08-03 proto-doc 완료 — Makefile + CI doc-freshness job + buf.gen.doc.yaml 보강.

M1(실시간 수렴) 완료. **M2 전 Phase 완료**:
doc-service 신설(Phase 1) → 인증/인가(Phase 2) → 스냅샷 영속화(Phase 3+4) → outbox 하드닝(Phase 5) → **E2E 검증(Phase 6)**.

| Phase | 상태 | 산출 |
|---|---|---|
| 2a-1 gateway 인증 | ✅ 머지 | backend `583b065` |
| 2a-2 gateway 인가 + viewer write-drop | ✅ 머지 | backend `4cb750d` |
| 2b engine role 강제 | ✅ 머지 | engine `4d9c39e` |
| 2c-C1 doc-service effective role 노출 | ✅ 머지 | backend `4c1678e` (PR #19) |
| 2c-C2 frontend 인증 셸 | ✅ 머지 | frontend `de002f5` (PR #5) |
| 2c-C3 페이지 선택 + 에디터 + E2E | ✅ 머지 | frontend `9161fbc`·`336964f`·`b12e026` (PR #6·#7·#8) |
| 3+4 엔진 스냅샷 | ✅ 완료 | engine C3~C6 (PR #13·#14·#15·#16·#17), backend C7 (PR #20) |
| 5 outbox 하드닝 | ✅ 완료 | backend PR #24 (`5df4b3f`) |
| 6 E2E 복원·권한 검증 | ✅ 완료 | backend PR #25 (`ba0406c`) |

## 다음 액션

1. ~~**API 문서** — SpringDoc OpenAPI v3.0.3~~ ✅ 완료(2026-08-01)
2. ~~**에러 구조화 로깅** — logback 에러 전용 JSON appender~~ ✅ 완료(2026-08-01)
3. ~~**M2 Phase 5** — outbox 하드닝~~ ✅ 완료(2026-08-01, backend PR #24)
4. ~~**proto-doc** — buf/protoc-gen-doc으로 gRPC API 문서 자동 생성~~ ✅ 완료(2026-08-03, controller `7999aa6`)
5. ~~**M2 Phase 6** — E2E 복원·권한 검증~~ ✅ 완료(2026-08-03, backend PR #25)
6. **M3 진입 준비** — consistent-hash 멀티인스턴스 라우팅 · Redis 버퍼 복원 설계
7. ~~**plan-audit T4 잔여**~~ ✅ 완료(2026-08-03)

## 열린 트랙 (완료 시 여기부터 확인)

> **이 표가 "무엇이 나를 pending으로 주장하는가"의 답이다.** 어떤 작업을 끝냈으면 **먼저 이 표를 훑어** 그 항목을 pending으로 들고 있는 plan이 있는지 확인한다. 이 장치가 없어서 `plan-audit-improvements`의 T4-3(서비스 CI)이 한 달간 미체크로 남았다(2026-07-28 발견).

| plan | status | 실제 남은 것 |
|---|---|---|
| ~~[m2-persistence-session](../plans/2026-06-30-m2-persistence-session.md)~~ | **done** | Phase 6 완료(2026-08-03, backend PR #25). M2 전체 클리어 |
| ~~[plan-audit-improvements](../plans/2026-06-30-plan-audit-improvements.md)~~ | **done** | T4 전체 완료(2026-08-03). DoD 트래커·콜사이트·ADR 승격·완전성 보강 |


> **2026-07-31 역방향 점검**(Phase 3+4 완료 후): `m2-phase34-engine-persistence`를 `done`으로 클로징하고
> 이 표에서 제거했다. 본류 `m2-persistence-session`의 잔여를 Phase 5~6으로 갱신.
> 이월 findings 중 C7에서 소거된 항목(`listMine` 무상한 조회, `SaveSnapshot` 경계 검증 갭 2건) 표기 갱신.
> C5 게이트 이월 3건은 C6에서 소거 확인(engine PR #17).

## 이월된 findings (구현 시 소거)

- **2b 크래프트 게이트 Minor 4건** — `extract_role` 거절 로그에 `doc_id`·`trace_id` 없음 / `Cargo.toml` dev-dep 주석의 feature 주장이 사실과 다름 / `let _ = send` 근거 주석 / plan이 명시한 `INVALID_ROLE_MSG` 상수 미도입. 상세 = phase2 plan §2b.
- **1c PR② 게이트 findings** — 상세 = [`plans/2026-07-12-m2-phase1c-rest-jwt.md`](../plans/2026-07-12-m2-phase1c-rest-jwt.md) §PR② (HIGH 2건은 PR #10 `a40bae5`에서 해소됨).
- ~~**`WorkspaceService.listMine`에 조회 상한 없음**~~ → **C7에서 소거**(2026-07-31, backend PR #20). `MAX_WORKSPACE_LIST=100` + `Limit` 파라미터 + 상한 도달 WARN 로그.
- **crdt-engine 운영 기능 미도입 3건 → M5(클러스터 배포) 트랙** (2026-07-29 [ADR-0022](../adr/0022-module-structure-rust.md) §범위 밖에서 등록).
  Spring Boot Actuator 대응물이 Rust엔 프레임워크가 아니라 **개별 크레이트**로 존재하는데 아직 조립을 안 했다:
  ① **`tonic-health`**(0.14.6, tonic과 동일 버전 — K8s liveness/readiness probe에 필요)
  ② **metrics 노출**(`metrics` + exporter 또는 OTel metrics — 현재 trace만 있고 metric은 0)
  ③ `tonic-reflection`(grpcurl 개발 편의). 지금 넣으면 쓸 곳이 없어 YAGNI이고 M2 DoD에도 없다.
- ~~**`StoredSnapshot::Present`가 `from_wire` 없이 직접 조립 가능**~~ → **C5에서 소거**(2026-07-30).
- ~~**C5 게이트 이월 3건**~~ → **C6에서 소거**(2026-07-31, engine PR #17).
  워치독 오탐 차단(컴파일 타임 assert) · 경합 벤치 · `SweepStats` 반환값 — 전부 스위퍼 구현에 동승 완료.
- ~~**doc-service `SaveSnapshot`의 경계 검증 갭 2건**~~ → **C7에서 소거**(2026-07-31, backend PR #20).
  blob 크기 검증(`MAX_SNAPSHOT_BYTES=2MiB`) + FK/PK 구분(SQL state code `23505`/`23503`).
- **engine `ALREADY_EXISTS` 재시도 미구현** (2026-07-31, engine issue #18) — C7에서 PK conflict를
  `ALREADY_EXISTS`로 올바르게 반환하게 됐지만, 엔진 sweeper가 이 코드를 재시도로 분류하는 로직은 미구현.
  → **M2 Phase 5(outbox) 진입 시 sweeper 에러 분류 확장에 동승 예정**. 단독 소거 시점 = engine issue #18 클로즈.

---

## 알아둘 것 (자주 헷갈리는 사실)

- **2b의 방어 범위** = 게이트웨이 **회귀·계약 위반**이지 "엔진 직접 gRPC 우회" 차단이 **아니다**. `role`은 클라이언트 통제 메타라 악의적 직접 호출자는 `editor`를 자칭해 통과한다 — 그 차단은 M5(mTLS STRICT·NetworkPolicy) 몫.
- **proto 태그** = `proto-v0.2.0` **원격 push 완료**(`99213c3`). engine/backend CI가 이 ref를 핀한다 → proto 계약이 바뀌면 태그 bump + 양 레포 워크플로 `PROTO_REF` 갱신.
  ⚠️ **Phase 3+4는 bump가 불요하다**(실측 2026-07-29) — `proto-v0.2.0`에 `SaveSnapshot`·`LoadSnapshot`이
  이미 다 있고 `git diff proto-v0.2.0 -- proto/`가 비어 있다. engine `ci.yml:16`의 "Phase 3에서
  bump 필요" 주석은 **stale**(C4에서 정정).
- ~~**엔진에 아웃바운드 gRPC 클라이언트가 없다**~~ → **C4에서 생겼다**(2026-07-30, `1a14f13`).
  어댑터 = `snapshot/doc_service.rs`가 **tonic이 사는 유일한 곳**(포트 파일은 tonic을 모른다).
  채널은 `connect_lazy` · `concurrency_limit(8)` · `Request::set_timeout`(3s) · traceparent 주입.
  `DOC_SERVICE_ADDR` 설정 시 실제 어댑터가 활성화되고 저장·복원 모두 동작한다(C6 완료, 2026-07-31 실기동 확인).
- **`registry.open()`은 `crdt.sync` span 밖에서 호출된다** — span은 `tokio::spawn(...).instrument()`에만
  붙는다. 그래서 open 경로에서 나가는 RPC는 `.instrument(span.clone())`을 붙이지 않으면
  traceparent가 실리지 않는다(가드레일 4 구멍).
- **엔진 벤치 명령엔 `--bench convergence`가 필수다**(실측 2026-07-30) — `cargo bench`는 lib·bin·tests의
  libtest 하네스까지 벤치 타깃으로 돌리고 그것들은 criterion 플래그를 모른다. 그래서
  `make bench-baseline`/`bench-compare`가 **한 번도 동작한 적이 없었다**(인자 없는 `make bench`만
  우연히 통과) = 가드레일 5의 회귀 비교가 공회전. C5에서 수정 + `make bench-smoke`를 CI에 추가.
  ⚠️ **벤치 측정 위생**: 로드가 걸린 맥에서는 같은 코드의 A/B가 ±7% 흔들리고 손대지 않은 그룹도
  +33%가 나온다. 신뢰구간 폭이 좁은(±0.2% 수준) 쌍만 유효 측정으로 채택할 것.
- **CI** = 4레포 전부 빌드·테스트 게이트 보유(2026-07-28). PR 초록이 이제 실제 검증을 뜻한다. 단 **프론트 E2E는 제외**.
  ⚠️ **"게이트 보유"와 "게이트 초록"은 다르다** — frontend `security-scan/npm-audit`은 `ci.yml` 신설 시점부터
  main에서 계속 red였는데(vite 8.1.0 전이 의존 postcss) `ci.yml`이 초록이라 가려져 있었다(2026-07-29 발견·해소).
  **새 게이트를 붙였으면 기존 게이트의 main 상태도 함께 확인한다.**
- **doc-service 에러 계약** — 도메인 예외만 RFC 9457 확장 멤버 `code`를 갖는다. **Bean validation 400에는 없다**
  (프레임워크 경로). 실측 확인 2026-07-29 → 클라이언트는 `code` 부재를 전제한 폴백이 필요하고,
  분기는 `code`/`status`로만 한다(`detail` 파싱은 서버가 금지).
- **`POST /api/auth/signup`은 토큰을 주지 않는다** — 201 + `UserResponse`뿐. 세션이 필요하면 login을 이어 부른다.
- **편집 가능 여부는 `canEdit`이 단일 출처다** — `myRole`은 **표시용**(배지)이다. "editor 또는 owner가 편집 가능"은
  서버 정책이라 클라가 재유도하면 역할 추가 시 즉시 갈라진다. 목록 응답에는 역할이 **없다**(N+1 회피, 계약).
- **room = 페이지 UUID** — `parseRoom`이 UUID 형식을 요구한다. 게이트웨이는 비UUID `doc_id`를 `CheckPermission`
  왕복 **없이 403**으로 끊는다(실측 2026-07-29). 옛 기본값 `demo`는 그래서 **무조건 실패**였다.
- **브라우저는 WS 실패의 상태 코드를 볼 수 없다**(code 1006뿐) — 401/403은 Node `ws`에서만 관측된다.
  그래서 토큰 만료·room 형식은 **연결 전에** 클라가 판단하고, 어긋나면 provider를 아예 만들지 않는다.
  관측 불가능한 실패는 "알려주기"가 아니라 **발생시키지 않기**가 유일한 처방이다.
- **프론트 E2E 사전조건 = 4프로세스**(postgres·doc-service·gateway·engine). 테스트가 계정·워크스페이스·페이지를
  **스스로 만든다** — 토큰 주입 방식으로는 viewer 케이스를 검증할 수 없어서다. 여전히 **CI 밖**.
- **프론트엔드 파일 배치 = feature 평면** — `src/<feature>/…` + `src/common/<관심사>/…`.
  `src/api/`·`src/service/` 류 전역 계층 통패키지는 크래프트 게이트 layering P7이 **이름까지 지목해 금지**한다
  (C2에서 실제 반려됨). "Java 패키지 규칙"으로 읽히지만 프론트 관행에도 그대로 발화한다.
- **crdt-engine 모듈 구조 = 관심사 모듈**([ADR-0022](../adr/0022-module-structure-rust.md), 2026-07-29).
  `doc.rs`(도메인) · `snapshot/`(포트+어댑터 평면) · `sync/`(전송 경계) · `config.rs`(env 유일 지점) ·
  `sync/status.rs`(wire 실패 문구 유일 지점). **계층 폴더(`domain/`·`service/`) 금지** —
  프로덕션 Rust 서비스(linkerd2-proxy·vector) 실측과 hexagonal 가이드 자신의 제외 조건이 근거.
  **분할 트리거는 응집도이지 줄 수가 아니다**(yrs 중앙값 502줄 — Rust는 테스트 동거로 줄 수가 부푼다).
- **doc-service 구조** = package-by-feature(ADR-0019). 신규 코드는 feature 패키지(auth/workspace/page/snapshot) 평면에, 공용은 `common/`. 도메인 에러는 카탈로그(`DocErrorCode` enum + 카테고리 예외, ADR-0018)로만.
- **테스트 환경** — backend doc-service 테스트는 Docker 필요(OrbStack 또는 colima, `DOCKER_HOST`/`TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE`), ws-gateway는 불요(in-process fake).
- **승인 경계** — 서비스 레포(backend/crdt-engine/frontend)는 branch+PR+**건별 승인**(push·PR 생성·머지 각각). controller만 main 직접.
- **세션 기본 = Opus 5 + effort 기본(high)** (2026-07-29 저속 진단 후 교정 — 전역 `xhigh` 상시 고정과
  `fable-5[1m]`이 주범이었다). xhigh/max는 세션·작업 단위로만 명시 상향. opus 에이전트 effort는
  frontmatter가 **실구동값**이다(rust-expert만 max). 근거·수치 = `/context-and-effort` §판단 기록,
  회고 = [dev-log](../dev-logs/2026-07-29-context-speed-tuning.md).
- **크래프트 룰은 레포 경계를 안 넘는다**(실측 2026-07-28) — controller에서 `--add-dir`로 서비스 레포를 열어도 `paths:` 스코프 룰 10종(java·spring·error-handling·concurrency·secure-coding·design-patterns·layering-readability·observability·clean-code·security)은 **로드되지 않는다**. 상시 5개와 settings 권한/훅·에이전트는 따라온다. → 크래프트 `[B]` 게이트는 반드시 **에이전트로** 실행. 상세 = [dev-log](../dev-logs/2026-07-28-rules-do-not-cross-repo.md)

## 교훈 dev-log (같은 함정 재발 시)

| 주제 | dev-log |
|---|---|
| **Phase 3+4 완료·M2 DoD 실기동·교훈 5건** | [2026-07-31-m2-phase34-complete](../dev-logs/2026-07-31-m2-phase34-complete.md) |
| 엔진 스냅샷 복원·fork 방지·순서 역전 | [2026-07-29-m2-phase34-engine-restore](../dev-logs/2026-07-29-m2-phase34-engine-restore.md) |
| **keepalive가 꺼져 있었다 · 공허한 관측 테스트 · 지시문 stale** | [2026-07-30-m2-phase4-doc-service-adapter](../dev-logs/2026-07-30-m2-phase4-doc-service-adapter.md) |
| **표준이 Rust에서 덜 발화한 지점**(ADR 분석 대기) | [2026-07-29-rust-module-structure-and-standards-gap](../dev-logs/2026-07-29-rust-module-structure-and-standards-gap.md) |
| 프론트 인증 배선·폴백이 감춘 403 | [2026-07-29-m2-phase2c-frontend-auth](../dev-logs/2026-07-29-m2-phase2c-frontend-auth.md) |
| CI 갭·게이트 실효성 증명 | [2026-07-28-build-test-ci-gap](../dev-logs/2026-07-28-build-test-ci-gap.md) |
| 상시 컨텍스트 예산(−85%)·게이트 배선 | [2026-07-28-claude-context-budget](../dev-logs/2026-07-28-claude-context-budget.md) |
| 세션 저속 주범 = 전역 xhigh·fable[1m] | [2026-07-29-context-speed-tuning](../dev-logs/2026-07-29-context-speed-tuning.md) |
| 룰이 레포 경계를 안 넘음 | [2026-07-28-rules-do-not-cross-repo](../dev-logs/2026-07-28-rules-do-not-cross-repo.md) |
| gitleaks fingerprint ↔ squash 함정 | [2026-07-17](../dev-logs/2026-07-17-gitleaks-fingerprint-squash-trap.md) |
| VT pinning 측정(맞는 결론·틀린 근거) | [2026-07-20](../dev-logs/2026-07-20-vt-pinning-grpc-blocking-stub.md) |
| gateway 관측 계약·WIP 드리프트 | [2026-07-19](../dev-logs/2026-07-19-m2-gateway-authn-observability.md) |
| Spring Boot 4.x·Jackson 3 함정 | [2026-07-13](../dev-logs/2026-07-13-m2-doc-service-1c-boot4-traps.md) |
| 에러 카탈로그·package-by-feature | [2026-07-18](../dev-logs/2026-07-18-m2-refactor-track-backend.md) |
