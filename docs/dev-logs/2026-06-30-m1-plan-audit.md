---
date: 2026-06-30
category: decision
tier: 2
importance: major
status: resolved
tags: [plan-audit, m1, m2, roadmap, doc-debt, nfr, otel, workflow]
related:
  - plans/2026-06-30-plan-audit-improvements.md
  - plans/2026-06-25-m1-convergence-impl.md
  - dev-logs/2026-06-28-m1-convergence-phase1-3.md
  - dev-logs/2026-06-25-m1-engine-code-review.md
---

# weDocs 작업계획 다각도 감사 — M1 잔여·M2 로드맵·문서부채·NFR 갭 40건

새 Linux 머신에서 weDocs 폴리레포를 받아 도구 설치(rust/java/docker/buf/gh) 후, 사용자 요청으로
**"작업 plan이 충분한가, 모자란 게 무엇인가"**를 점검했다. M1 plan(`2026-06-25-m1-convergence-impl.md`)은
구현·검증이 견고하나 "무엇을"만 담고 "어떻게/이후"가 비어 "대략적"이라는 사용자 직관을 검증·구체화한 기록.

이 dev-log는 **찾은 것의 보존(후향)**, 실행은 plan(`2026-06-30-plan-audit-improvements.md`, 전향)으로 분리한다.

## 방법 (workflow 5차원 + 자체 적대검증)

`Workflow` 도구로 5개 차원 병렬 리뷰 → 각 발견을 "진짜 갭 vs 의도적 연기"로 적대 검증 → 완전성 비평.

| 차원 | 질문 | 발견 |
|---|---|---|
| m1-finish | Phase 4.2/4.3/5가 추측 없이 실행 가능한가 | 9 |
| plan-vs-reality | 문서가 실제 코드·infra·proto와 일치하나 | 6 |
| forward-roadmap | M2 착수 전 확정할 결정·선기록은 | 8 |
| cross-cutting-nfr | NFR/DoD/가드레일에 측정·검증 계획이 있나 | 10 |
| process-doc-debt | repo 자체 룰(documentation/devlog/plan-logging)이 지켜지나 | 7 |

> **정직 기록**: Review 단계(5 에이전트, 40 findings)는 완료됐으나 **Verify 단계가 토큰 세션 리밋으로 중단**(46 에이전트·1.37M 토큰 소진 후 `failed`). 리셋 후 Review 산출물을 트랜스크립트에서 회수하고, **적대 검증은 Claude가 직접 수행**(리뷰어들이 이미 `isIntentionallyDeferred`로 M5/M4 연기를 자체 표시 + 전체 문서 맥락 보유). 따라서 본 기록의 검증은 "독립 에이전트 다수결"이 아니라 "단일 검증자(전체 맥락)"임을 명시 — 추후 재검증 시 이 한계 고려.

## 총평

M1 수직 슬라이스(수렴 + thin 2-hop OTel) 구현·검증은 견고. 갭은 plan의 **범위·구체성**에 있다:

1. **M1 잔여(4.2/4.3/5)** — "무엇을"만 있고 javaagent 배선·Jaeger docker 명령·trace_id 대조 절차가 비어 다음 세션이 추측해야 함.
2. **M2~M6 전방 계획 0건** — doc-service는 신규 모듈인데 plan·ADR 미작성. 영속화 트리거 방향이 안 정해져 M2 첫 줄도 못 씀(blocker).
3. **NFR/DoD 선언만** — `p95<100ms·동시 50명·WS 수천`에 측정 계획 없음. DoD 9개 마일스톤 미매핑.
4. **문서 자기모순** — ADR-0010이 폐기한 "submodule"이 가드레일·SDD·PRD 6곳 잔존.

40건 중 거의 전부가 진짜 갭(리뷰어가 M5/M4 연기는 이미 걸러냄), 6건만 "지금 할 일"이 아니라 "연기 마커를 달 일".

## 핵심 캐치 3건 (blast radius 큼)

- **M1R-09 — telemetry.rs 실버그(코드 확인 완료)**: `src/telemetry.rs:67-73` — `OTEL_EXPORTER_OTLP_ENDPOINT`를
  `endpoint` 변수로 읽지만 `SpanExporter::builder().with_tonic().build()`에 **넘기지 않음**(`.with_endpoint()` 부재).
  그 변수는 `format!("otlp/grpc → {endpoint}")` **로그에만** 사용 → 4.3에서 Jaeger를 가리켜도 "로그는 Jaeger, 실제 전송은
  localhost:4317 기본값" silent drift 가능. **4.3 live 검증의 핵심 경로를 정확히 위협.** config-contract-audit "명시값 vs
  라이브러리 기본값" 함정의 교과서 사례. → engine PR로 `.with_endpoint(endpoint)` 1줄 + opentelemetry-otlp 0.32 env
  자동읽기 여부 docs.rs 재확인.
- **M2F-02 — M2 blocker**: `crdt-engine/build.rs`가 `.build_client(false)` → 엔진에 outbound gRPC 클라이언트 stub 자체가
  없음 → SDD가 말한 "엔진이 스냅샷을 PostgreSQL에 영속화"의 **저장 트리거 수단이 없음**. 누가 트리거하나(엔진 push[build_client(true)]
  vs doc-service pull vs 게이트웨이)가 미결정이라 proto·build.rs·스레드모델·트랜잭션 경계가 전부 미정 → M2 첫 줄도 못 씀.
- **M1D-01 — 가드레일 자기모순**: ADR-0010(Accepted)은 "submodule 아님, buf 원격 git input"으로 확정했으나
  CLAUDE.md:10 가드레일①·SDD.md:10·sdd/2:73·sdd/5:63·prd/2:64 **6곳에 "submodule" 잔존**. 매 세션 주입되는 가드레일이
  폐기된 메커니즘을 지시 → 재개 세션이 글자대로 따르면 ADR-0010과 정면 충돌. deep-thinking.md "자기강화 추정 루프"와 동형.

## 클러스터 요약 (실행은 plan 참조)

| 우선 | 클러스터 | 발견 ID |
|---|---|---|
| 🔴 즉시(M1마감) | javaagent 배선·Jaeger docker·trace_id 절차·E2E 회귀·endpoint 버그 | M1R-01,02,03,04,05,09 |
| 🟠 문서부채(저위험 quick win) | submodule 치환·ai-service 마커·ci/참조·ADR README·onboarding·M0 status | M1D-01,02,03,04 · PDD-06,07 |
| 🟡 M2 착수 전 확정 | 스냅샷 트리거(blocker)·복원절차·proto 영향·JWT/인가·outbox·plan 선기록 | M2F-01,02,03,04,05,06,08 · SEC-01 |
| 🟢 횡단 프로그램 | NFR 측정 매핑·DoD 트래커·관측 콜사이트·서비스 CI·ADR 승격·dev-log 규율 | NFR-01,02 · DOD-01,02 · OBS-01 · CI-01 · PDD-01,02,03,04 |
| ⚪ 완전성 보강 | 통합 로컬개발 compose·데모 산출물·의존성 보안 스캔·버전핀 매트릭스 | (비평 보강, plan T4) |

## 전체 발견 appendix (40건 — 세션 초기화 대비 보존)

> 형식: `ID · severity · category · isDeferred · 제목` / 근거 file:line / 권장. 근거는 실제 read/grep 결과(추측 아님).

### m1-finish (9)

- **M1R-01 · high · under-specified** — 4.2 javaagent jar 출처·버전핀·gitignore 미명세. 근거: plan:148,186이
  'v2.29.0'만, backend 전체 javaagent/OTEL_ grep 0건. 권장: jar 취득(URL+sha256)·배치경로(tools/)·gitignore 정책 3줄.
- **M1R-02 · high · missing-plan** — javaagent를 Makefile/run에 붙이는 배선 부재(현 Makefile run=bootRun, javaagent 진입점 없음).
  bootRun jvmArgs vs java -jar 미정. 권장: `make run-otel` target + 정확한 `java -javaagent:...` 커맨드 + env 3개 위치.
- **M1R-03 · high · under-specified** — Jaeger all-in-one docker 명령·포트(4317/16686)·OTLP enable env·양 서비스 endpoint
  문자열 전무(repo에 jaeger/compose 0건). 권장: docker-compose 태그핀 + env 세트 + docker-free stdout 경로. WebFetch로 Jaeger 현행 검증.
- **M1R-04 · medium · under-specified** — trace_id "일치 확인"이 결과만 있고 절차 없음(javaagent vs opentelemetry-stdout 포맷 상이).
  권장: 동일 room 1회 접속→양쪽 trace_id grep→string equal, grep 패턴 예시 박기.
- **M1R-05 · medium · nfr-dod-gap** — javaagent는 바이트코드 계측이라 VT·WS 영향 가능한데 E2E 수렴 회귀가 4.x 체크박스에 없음(Blast Radius에만).
  권장: 4.2 끝에 'javaagent 부착 후 npm run test:e2e 2회 green' 추가.
- **M1R-06 · medium · doc-debt** — Phase5 ADR 번호 미할당·대안비교표 요건 미명세. 권장: §D 8결정에서 대안 3개 끌어와 번호 확정(0011 vs 0004 슬롯).
- **M1R-07 · low · process-gap** — 마일스톤 완료 retrospective(documentation.md 트리거)가 Phase5에 없음. 권장: §5에 retrospective 작성 제안 1줄.
- **M1R-08 · low · process-gap** — 4.2에 phase-workflow Gate 적용 여부 모호('코드0이니 리뷰 불필요' 위험). 권장: config-contract-audit 셀프체크 + 1-lens.
- **M1R-09 · medium · plan-vs-reality-drift** — ★telemetry.rs endpoint가 exporter에 안 넘어감(코드 확인). 권장: `.with_endpoint()` + 0.32 env 자동읽기 검증.

### plan-vs-reality (6)

- **M1D-01 · high · doc-debt** — ★submodule 표현 6곳 잔존(가드레일① 자기모순). 근거: CLAUDE.md:10·SDD.md:10·sdd/2:73·sdd/5:63·prd/2:64 vs ADR-0010.
  권장: 'buf 원격 git input(ADR-0010)'으로 일괄 치환, grep 잔존0 확인.
- **M1D-02 · high · plan-vs-reality-drift** — ai-service 레포 부재가 미명시(ls=backend/crdt-engine/frontend/controller 4개)인데 CLAUDE.md:4는 "있다" 단정.
  isDeferred=true(M4). 권장: CLAUDE.md:4·SDD §12 트리에 '(M2/M4 신설 예정)' 마커.
- **M1D-03 · medium · plan-vs-reality-drift** — SDD §12가 가리킨 ci/는 README만, 실제 CI는 .github/workflows/proto-ci.yml. 권장: SDD §12 정정 또는 ci/README 포인터.
- **M1D-04 · medium · doc-debt** — ADR 0002~0009 공백 + 미해결5가 ADR README와 SDD §15 두 곳 중복. isDeferred=true. 권장: README에 'M6 분리, SDD §15 권위' 마커 + 중복 제거.
- **M1D-05 · low · nfr-dod-gap** — infra 스캐폴드(resources:[]) + Dockerfile/cargo-chef/distroless 0건, DoD 미매핑. isDeferred=true(M5 마커로 보호됨). 권장: DoD에 마일스톤 태그.
- **M1D-06 · low · process-gap** — 서비스레포 Dockerfile/CI 부재가 'M5' 마커 없이 평문. isDeferred=true. 권장: SDD §9/§11에 '(M5)' 마커.

### forward-roadmap (8)

- **M2F-01 · high · missing-plan** — M2 doc-service plan 선기록 부재(plan-logging.md 신규모듈 의무). 권장: M2 착수 전 plan 작성 후 커밋(라이프사이클 2번 게이트).
- **M2F-02 · blocker · under-specified** — ★스냅샷 저장 트리거·방향 미결정(build_client(false)라 엔진→doc-service 호출 불가). 권장: ADR(push/pull/gateway 비교) 먼저, 권장=엔진 push+벤치.
- **M2F-03 · high · under-specified** — 엔진 장애 복원 절차 미상세(SDD §15 미해결, M2 검증기준='재접속 복원'과 직결). 권장: 복원 시퀀스 + 'M2 보장경계=마지막 스냅샷, in-flight 유실 허용(Redis=M5)'.
- **M2F-04 · medium · plan-vs-reality-drift** — M2 proto 변경 필요성 사전식별 부재(LoadSnapshot 부재, CheckPermission에 토큰필드 없음). 권장: proto 영향분석 1절, 변경시 Phase0 분리 + proto-v0.2.0.
- **M2F-05 · high · under-specified** — JWT 핸드셰이크·CheckPermission 연동 미설계(현 게이트웨이 auth drop). 권장: 검증지점·실패 close code·VIEWER 쓰기차단 게이트 위치 + ADR.
- **M2F-06 · medium · under-specified** — outbox 방식 미결정(Kafka는 M4지만 outbox 테이블/트랜잭션 경계는 M2 스키마). 권장: ADR(Debezium vs 앱레벨), 권장=앱레벨, 테이블만 M2 선반영.
- **M2F-07 · low · process-gap** — M2'세션' vs M3'presence/멀티인스턴스' 경계 모호. isDeferred=true. 권장: 'Redis/멀티인스턴스=M3' 명시, M2는 단일인스턴스 가정.
- **M2F-08 · low · process-gap** — M3~M6 plan 0건 + SDD 미해결5 소유 마일스톤 불명(AI SLO·consistent-hash가 'M1~M2 확정' 오라벨). 권장: 결정 소유권 맵(복원/outbox/인증=M2, hash=M3, SLO=M4).

### cross-cutting-nfr (10)

- **NFR-01 · high · nfr-dod-gap** — NFR 정량목표(p95<100ms·50명·WS수천)에 측정/부하 계획 어느 마일스톤에도 미매핑(load-test 디렉토리 부재). 권장: 마일스톤별 측정수단 고정(k6/Gatling, OTel span 히스토그램).
- **NFR-02 · medium · nfr-dod-gap** — criterion 벤치(머지 1.166ms)는 NFR 'sync p95<100ms 왕복'과 다른 지표. 권장: 벤치≠SLI 명시 분리 caveat, end-to-end는 OTel span.
- **DOD-01 · medium · nfr-dod-gap** — DoD 9개 마일스톤 매핑·추적 문서 부재. 권장: docs/status/dod-tracker.md(항목×마일스톤×증거 컬럼), M1 완료분 마킹.
- **DOD-02 · medium · plan-vs-reality-drift** — DoD#6 'Java→Rust→Python 단일 trace'는 3-hop인데 M1은 2-hop만, 4-hop 계획 부재. 권장: M2/M4 plan에 전파검증 선등록, Kafka 페이로드 trace 주입.
- **SEC-01 · high · guardrail-risk** — JWT 인증 owner 마일스톤 없이 SDD 산문에만, 현 게이트웨이 auth 무인증 drop(누구나 임의 room 편집). 권장: M2 1급 체크박스 + '현 무인증=M1 로컬한정' 경고.
- **SEC-02 · medium · guardrail-risk** — mTLS(Istio)·입력검증 선언만, M5 검증 시나리오 부재. isDeferred=true. 권장: M5 plan에 PeerAuthentication STRICT+평문거부 실증, room/doc-id 입력검증 규칙.
- **OBS-01 · medium · nfr-dod-gap** — 메트릭 계측 콜사이트가 TODO 주석만(M5 연기). isDeferred=true(백엔드만). 권장: 콜사이트는 지금(merge_duration/active_streams/lagged_total), no-op exporter라도. monitoring.md '사후추가 아닌 기본'.
- **CI-01 · high · process-gap** — 서비스레포 CI·이미지빌드·소비자 buf-breaking 게이트 전무(proto-ci.yml 1개뿐, 머지PR 4건 CI없이). isDeferred=true. 권장: M2 전 최소 PR CI(cargo test+clippy / gradle test / vitest).
- **TEST-01 · low · missing-plan** — SDD §11 Testcontainers(PG/Redis/Kafka)·RAG정확도·폴백트리거가 어느 plan에도 미진입. isDeferred=true. 권장: M2/M4 plan에 체크박스 매핑, SDD §11에 마일스톤 태그.
- **DOC-01 · low · doc-debt** — SDD §15 미해결5가 'M1~M2 확정' 마킹 채 방치(M1 마감인데 미확정). 권장: Phase5에 확정/이월 갱신, AI SLO→M4, hash→M3.

### process-doc-debt (7)

- **PDD-01 · high · doc-debt** — Phase 4.1 engine OTel dev-log 미생성(1~3은 작성, 4.1만 누락 — documentation.md Phase-gate 트리거 위반). 권장: 후향 dev-log 즉시 작성.
- **PDD-02 · high · doc-debt** — SDD §15 9결정 ADR 미승격(0002~0009 공백). 포트폴리오 '의사결정 깊이' 산출물 8개 비어있음. 권장: blast radius 큰 것부터(0004 Rust bidi·0005 yrs·0007 Istio Ambient).
- **PDD-03 · medium · doc-debt** — M1 거의 완료인데 retrospective 부재(documentation.md 제안 트리거). 권장: Phase5에 docs/retrospective/2026-..-m1-convergence.md.
- **PDD-04 · medium · process-gap** — docs/project/overview.md 부재('매 세션 확인' 주기 트리거 한번도 미실행=죽은 룰). 권장: overview 1회 생성 또는 룰을 'PRD.md 확인'으로 현실화.
- **PDD-05 · medium · process-gap** — M2 doc-service phase-workflow Gate 계획·review-gaps.md 부재. isDeferred=true. 권장: M2 착수 시 /phase-start, SDD 위치·Gate5 산출물 위치 사전결정.
- **PDD-06 · low · doc-debt** — M0 scaffold dev-log status:open 방치(완료인데 Tier1) + self-loop related. 권장: resolved 갱신·tier 재산출·self-loop 제거.
- **PDD-07 · low · doc-debt** — onboarding guide:6이 완료된 scaffold plan을 '현재 plan'으로(같은 파일 :95는 올바름, 문서내 모순). 권장: convergence plan §재개지점으로 교체.

## 교훈

1. **plan-logging은 모범, documentation.md ADR/dev-log 트리거는 반복 미이행** — plan(전향)은 6회 갱신·Resume 최신으로 견고하나,
   ADR 승격(8개 공백)·Phase별 dev-log(4.1 누락)·retrospective는 룰이 MANDATORY로 규정함에도 누락. **전향 규율 ≠ 후향 규율.**
2. **"proto 변경 없이 완수"의 성공이 M2에선 함정** — M1은 기존 proto로 완수했으나, M2는 build_client(false)·LoadSnapshot 부재·토큰필드
   부재로 proto/빌드 변경을 요구할 수 있다. M1의 무변경 자랑이 M2 사전식별을 가림.
3. **선언 NFR은 검증계획 없으면 부채** — professional-writing.md '검증 안 된 수치 나열 금지'가 코드에도 적용. p95<100ms를 PRD에 박으면 측정수단을 마일스톤에 매핑해야.
4. **워크플로 토큰 리밋 대비** — 대규모 fan-out(46 에이전트·1.37M)은 세션 리밋에 걸릴 수 있음. Review/Verify 분리 시 Review 산출물은
   트랜스크립트에서 회수 가능(journal.jsonl + agent-*.jsonl). 차후 대형 감사는 단계별 결과를 중간 커밋하거나 배치 축소.

## 다음

실행 계획은 [plan 2026-06-30-plan-audit-improvements.md](../plans/2026-06-30-plan-audit-improvements.md) 4트랙 참조.
즉시 실행 후보 = T1(M1 마감 구체화, M1R-09 engine 수정 포함).
