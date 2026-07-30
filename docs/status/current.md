# 현재 상태 — 재개 SSOT

> **이 파일이 "지금 어디까지 왔고 다음에 뭘 하나"의 유일한 출처다.**
> CLAUDE.md는 이 파일을 가리키는 포인터만 갖는다(진척 이력을 CLAUDE.md에 두지 않는 이유 = 공식 가이드의 "자주 바뀌는 정보 제외" + 그 편집 지점이 곧 드리프트 지점이었다는 실증).
> 완료 이력 = [`history.md`](history.md) · 상세 실행 계획 = `docs/plans/`

**최종 갱신**: 2026-07-30

---

## 지금

**M2 Phase 2 완료. Phase 3+4(엔진 스냅샷) 진행 중 — 복원은 와이어 끝까지 붙었고, 저장 회계(C5)는
코드·게이트까지 끝났다. 다음 = C5 push·PR(승인 필요) → C6 스위퍼.**

> 2026-07-30 C4 종료 — 엔진이 doc-service에서 스냅샷을 **복원**한다(fail-closed).
> 회고 = [dev-logs/2026-07-30-m2-phase4-doc-service-adapter.md](../dev-logs/2026-07-30-m2-phase4-doc-service-adapter.md)
>
> 2026-07-30 C5 코드 완료 — **로컬 브랜치만 있다**. engine `feat/m2-phase3-save-accounting`
> 커밋 4건, lib 테스트 43 → 60, 크래프트 게이트 반려 → 반영 완료. **push·PR 미착수**(건별 승인).
> 실제 저장 RPC는 아직 없다 — 이번 것은 "무엇을 언제 저장할지"의 회계까지다.

M1(실시간 수렴) 완료. M2는 doc-service 신설(Phase 1) → 인증/인가(Phase 2) **여기까지 완료** →
엔진 저장·복원·outbox·E2E(Phase 3~6)가 남았다.

| Phase | 상태 | 산출 |
|---|---|---|
| 2a-1 gateway 인증 | ✅ 머지 | backend `583b065` |
| 2a-2 gateway 인가 + viewer write-drop | ✅ 머지 | backend `4cb750d` |
| 2b engine role 강제 | ✅ 머지 | engine `4d9c39e` |
| 2c-C1 doc-service effective role 노출 | ✅ 머지 | backend `4c1678e` (PR #19) |
| 2c-C2 frontend 인증 셸 | ✅ 머지 | frontend `de002f5` (PR #5) |
| 2c-C3 페이지 선택 + 에디터 + E2E | ✅ 머지 | frontend `9161fbc`·`336964f`·`b12e026` (PR #6·#7·#8) |
| **3+4 엔진 스냅샷** | **← 진행 중** | C3 `2ab925e` · C3.5 `28e1b9c` · C4 `1a14f13` 머지 · **C5 로컬 브랜치**(미머지) |

## 다음 액션 — Phase 3+4 (엔진 스냅샷 복원·저장)

**상세 SSOT = [`plans/2026-07-29-m2-phase34-engine-persistence.md`](../plans/2026-07-29-m2-phase34-engine-persistence.md) §재개 지점.**
다음 = **C5 push + PR**(승인 후) → **C6**(스위퍼 + graceful flush). C7(backend 하드닝)은 병렬 가능.

⚠️ **C6 착수 전에 plan §C5 "실제 착지한 API"를 반드시 읽어라** — C5가 게이트 반영으로 원문
스케치와 다르게 착지했다(`SaveTrigger` enum · `max_batch` 필수 · `settle_save`에 `doc_id` 없음).
원문대로 쓰면 컴파일 실패한다. C4에서 이미 한 번 겪은 함정이다.

⚠️ **실행 순서가 plan 번호와 반대다** — **복원(Phase 4) 먼저, 저장(Phase 3) 나중**.
저장을 먼저 넣으면 엔진 재시작 후 빈 Doc에 stale 클라가 붙어 **정상 DB 스냅샷을 열화된 상태로
덮어쓰는** 구간이 생기고 version 카운터도 0으로 리셋된다. 복원이 먼저면 그 구간이 없다.

## 열린 트랙 (완료 시 여기부터 확인)

> **이 표가 "무엇이 나를 pending으로 주장하는가"의 답이다.** 어떤 작업을 끝냈으면 **먼저 이 표를 훑어** 그 항목을 pending으로 들고 있는 plan이 있는지 확인한다. 이 장치가 없어서 `plan-audit-improvements`의 T4-3(서비스 CI)이 한 달간 미체크로 남았다(2026-07-28 발견).

| plan | status | 실제 남은 것 |
|---|---|---|
| [m2-persistence-session](../plans/2026-06-30-m2-persistence-session.md) | in-progress | **M2 Phase 5~6** (Phase 1·2 완료, 3+4는 아래 하위 트랙이 소유) |
| [m2-phase34-engine-persistence](../plans/2026-07-29-m2-phase34-engine-persistence.md) | in-progress | **C3~C8** — engine PR1a/1b/2a/2b + backend PR3 + 완료 처리 |
| [plan-audit-improvements](../plans/2026-06-30-plan-audit-improvements.md) | in-progress | T4 잔여 4건(T4-1 NFR/DoD 트래커 · T4-2 관측 콜사이트 · T4-4 ADR 0002~0009 승격 · T4-5 ①②③⑤). **T4-3 서비스 CI는 2026-07-28 완료** |


> **2026-07-29 역방향 점검**(Phase 2c 완료 후): `m2-phase2-auth-authz`·`m2-phase2c-frontend-auth` 둘 다
> `done`으로 클로징하고 이 표에서 제거했다. 본류 `m2-persistence-session`의 §재개 지점도 Phase 3으로 옮겼다
> — 하위 트랙 완료로 부모 재개 조건이 바뀌었는데 부모를 안 고치면, 부모만 여는 세션이 끝난 트랙을 재실행한다.
> `plan-audit-improvements`는 M2와 무관한 별개 트랙. 그 외 plan은 전부 `done`.

## 이월된 findings (구현 시 소거)

- **2b 크래프트 게이트 Minor 4건** — `extract_role` 거절 로그에 `doc_id`·`trace_id` 없음 / `Cargo.toml` dev-dep 주석의 feature 주장이 사실과 다름 / `let _ = send` 근거 주석 / plan이 명시한 `INVALID_ROLE_MSG` 상수 미도입. 상세 = phase2 plan §2b.
- **1c PR② 게이트 findings** — 상세 = [`plans/2026-07-12-m2-phase1c-rest-jwt.md`](../plans/2026-07-12-m2-phase1c-rest-jwt.md) §PR② (HIGH 2건은 PR #10 `a40bae5`에서 해소됨).
- **`WorkspaceService.listMine`에 조회 상한 없음** (backend, secure-coding P2) — 2026-07-29 C3-1 게이트에서 발견.
  같은 서비스의 `PageTreeService.list`는 `MAX_PAGE_LIST`(1,000)로 자르는데 워크스페이스 목록만 무상한이다.
  **클라에서 자르지 않는다** — 자르면 "내 워크스페이스가 안 보인다"는 무증상 버그가 되고 서버의 무상한
  조회는 그대로 남는다. 상한은 조회가 있는 곳에 둔다.
  → **소거 예정 = Phase 3+4의 C7**(backend PR3)에 동승 확정.
- **crdt-engine 운영 기능 미도입 3건 → M5(클러스터 배포) 트랙** (2026-07-29 [ADR-0022](../adr/0022-module-structure-rust.md) §범위 밖에서 등록).
  Spring Boot Actuator 대응물이 Rust엔 프레임워크가 아니라 **개별 크레이트**로 존재하는데 아직 조립을 안 했다:
  ① **`tonic-health`**(0.14.6, tonic과 동일 버전 — K8s liveness/readiness probe에 필요)
  ② **metrics 노출**(`metrics` + exporter 또는 OTel metrics — 현재 trace만 있고 metric은 0)
  ③ `tonic-reflection`(grpcurl 개발 편의). 지금 넣으면 쓸 곳이 없어 YAGNI이고 M2 DoD에도 없다.
- ~~**`StoredSnapshot::Present`가 `from_wire` 없이 직접 조립 가능**~~ → **C5에서 소거**(2026-07-30).
  newtype + private 필드 + **형제 모듈**(`snapshot/stored.rs`) 배치. 형제 배치가 핵심이다 —
  private 필드는 정의 모듈 *과 그 하위*에서 보이므로 부모(`snapshot/mod.rs`)에 두면 자식인
  어댑터가 여전히 우회 조립할 수 있다(에이전트가 `E0451`로 실증).
- **C5 게이트 이월 2건 → C6에 동승** (2026-07-30, 상세 = plan §C6):
  ① **경합 벤치** — `due_save`가 문서별 락을 쥔 채 전체 상태를 인코딩해 그 doc의 머지가 멈춘다
  (4MiB면 ms 단위). `bench-compare`는 스위퍼를 안 돌려 이 비용을 못 본다. C5에서 못 한 이유 =
  스위퍼가 없으면 main baseline이 성립하지 않는다. ② **`SweepStats`** — in-flight·disabled·
  contended skip이 반환값에 안 남는다(절단만 WARN). 소비자가 C6에 생긴다.
- **doc-service `SaveSnapshot`의 경계 검증 갭 2건**(2026-07-29 Phase 3+4 착수 조사에서 발견) —
  ① blob 크기 무검증(4MiB gRPC 한도가 유일한 방어) ② `DataIntegrityViolationException`을 전부
  `PAGE_NOT_FOUND`로 접어 **FK 위반과 PK 경합을 구분 못 한다**. 엔진은 `NotFound`를 영구 실패로
  보고 그 문서의 영속화를 끄므로, PK 경합이 조용한 데이터 유실이 된다. → 같은 C7에서 소거.

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
  `DOC_SERVICE_ADDR` **미설정이 기본**이라 현재 기동은 여전히 `NoopSnapshotStore`다 → Phase 6에서 켠다.
  ⚠️ 저장(`SaveSnapshot`)은 **아직 없다** — 포트에 `load`만 있다(C5·C6에서 추가).
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
- **테스트 환경** — backend doc-service 테스트는 colima 필요(`DOCKER_HOST`/`TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE`), ws-gateway는 불요(in-process fake).
- **승인 경계** — 서비스 레포(backend/crdt-engine/frontend)는 branch+PR+**건별 승인**(push·PR 생성·머지 각각). controller만 main 직접.
- **세션 기본 = Opus 5 + effort 기본(high)** (2026-07-29 저속 진단 후 교정 — 전역 `xhigh` 상시 고정과
  `fable-5[1m]`이 주범이었다). xhigh/max는 세션·작업 단위로만 명시 상향. opus 에이전트 effort는
  frontmatter가 **실구동값**이다(rust-expert만 max). 근거·수치 = `/context-and-effort` §판단 기록,
  회고 = [dev-log](../dev-logs/2026-07-29-context-speed-tuning.md).
- **크래프트 룰은 레포 경계를 안 넘는다**(실측 2026-07-28) — controller에서 `--add-dir`로 서비스 레포를 열어도 `paths:` 스코프 룰 10종(java·spring·error-handling·concurrency·secure-coding·design-patterns·layering-readability·observability·clean-code·security)은 **로드되지 않는다**. 상시 5개와 settings 권한/훅·에이전트는 따라온다. → 크래프트 `[B]` 게이트는 반드시 **에이전트로** 실행. 상세 = [dev-log](../dev-logs/2026-07-28-rules-do-not-cross-repo.md)

## 교훈 dev-log (같은 함정 재발 시)

| 주제 | dev-log |
|---|---|
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
