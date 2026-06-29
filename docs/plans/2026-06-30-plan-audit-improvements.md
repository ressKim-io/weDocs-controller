---
date: 2026-06-30
slug: plan-audit-improvements
status: planned
related:
  - dev-logs/2026-06-30-m1-plan-audit.md
  - plans/2026-06-25-m1-convergence-impl.md
  - adr/0010-proto-distribution-buf-git-input.md
---

# weDocs 계획 감사 → 개선 실행 plan (4트랙)

[감사 dev-log](../dev-logs/2026-06-30-m1-plan-audit.md)에서 도출한 40건 갭을 실행 가능한 4트랙으로 재편.
발견 ID(M1R-/M1D-/M2F-/NFR-/DOD-/SEC-/OBS-/CI-/TEST-/DOC-/PDD-)는 dev-log appendix에 근거 file:line 보존.

## Context

- **왜**: M1 plan은 구현·검증 견고하나 "무엇을"만 담아 ①4.2/4.3/5 "어떻게" ②M2~M6 로드맵 ③NFR/DoD 측정·추적 ④문서 자기모순이 비어 "대략적".
- **방법**: `Workflow` 5차원 병렬 리뷰 + 자체 적대검증(Verify 토큰리밋 중단 → Claude 직접 검증, dev-log §방법 참조).
- **확정 사실**(추측 아님, 코드 확인):
  - `crdt-engine/src/telemetry.rs:67-73` — endpoint를 exporter에 명시 전달 안 함. ~~M1R-09 실버그~~ → **2026-06-30 검증 기각**: opentelemetry-otlp 0.32 `with_tonic().build()`가 `OTEL_EXPORTER_OTLP_ENDPOINT` 자동 읽음 → 기능 정상, 코드 변경 불요(`.with_endpoint()` 추가는 signal-specific override 덮어쓰는 회귀).
  - `crdt-engine/build.rs` `.build_client(false)` — 엔진 outbound gRPC 클라이언트 stub 부재 = M2F-02 blocker.
  - `submodule` 표현 6곳(CLAUDE.md:10·SDD.md:10·sdd/2:73·sdd/5:63·prd/2:64) vs ADR-0010 = M1D-01 자기모순.
  - infra/ = 스캐폴드 9파일(resources:[]), 서비스레포 Dockerfile/CI 0건. ai-service 레포 미생성(4 레포만).
- **워크플로 제약**: controller=main 직접(T1 plan갱신·T2 문서부채·T4 일부 controller 문서). **서비스레포(engine/backend/frontend)=branch+PR+건별 승인**(M1R-09 engine 수정·서비스 CI).

---

## 실행 체크리스트

### Phase 0 — 기록 (controller, main 직접) ✅
- [x] 감사 dev-log 작성 (`docs/dev-logs/2026-06-30-m1-plan-audit.md`, 40건 보존)
- [x] 이 plan 작성 ← 코드/문서 변경 전 게이트
- [x] 두 문서 commit (dev-log 1344fc6 · plan fb7060f)

### T1 — M1 마감 구체화 🔴 — ✅ 계획 구체화 완료(2026-06-30), 실제 4.2/4.3/5 실행은 convergence plan으로

> 산출물 = `2026-06-25-m1-convergence-impl.md`의 Phase 4.2/4.3/5를 "어떻게"로 재작성(완료) + spec 검증 + Jaeger compose 생성.
> 이 트랙은 **계획 구체화**가 목표 — 실제 backend javaagent 부착(4.2 PR)·live 검증 실행(4.3)·마감 문서(5)는 이제 구체화된 convergence plan을 따라 진행.

- [x] **T1-1 (M1R-09)** ✅ **검증 완료 — engine 코드 변경 불필요**. docs.rs opentelemetry-otlp 0.32: `with_tonic().build()`가
      `OTEL_EXPORTER_OTLP_ENDPOINT`(+signal-specific `_TRACES_ENDPOINT` 우선) **자동 읽음** → 현 telemetry.rs 기능 정상.
      리뷰어 원권장 `.with_endpoint()` 추가는 **회귀**(env override 덮어씀)라 기각. engine PR 불요(사이클 절약). convergence plan §4.3·재개지점에 기록.
- [x] **T1-2 (M1R-01/02)** ✅ convergence plan §4.2에 javaagent 배선 전부 명세 — jar URL(v2.29.0, 다운로드 구문 검증)+sha256·`tools/` 배치·`tools/*.jar` gitignore·`make run-otel`(java -jar 직접) target+env 3개. (실제 backend 파일 변경=4.2 실행 PR)
- [x] **T1-3 (M1R-03/04)** ✅ `infra/local/docker-compose.jaeger.yml` 생성(Jaeger v2 2.19.0, 4317/4318/16686, v2 OTLP 기본활성 검증). convergence plan §4.3에 기동순서·단일trace 검증·docker-free grep 절차 명세.
- [x] **T1-4 (M1R-05)** ✅ convergence plan §4.3에 '4.3-회귀' 체크박스 추가(`npm run test:e2e` 2회 green) + 'done 게이트=단일trace+수렴 둘 다' 명시.
- [x] **T1-5 (M1R-06, DOC-01, PDD-01/03)** ✅ convergence plan Phase 5 재작성 — ADR 0011+대안 3축·Phase4 후향 dev-log·M1 retrospective·SDD §15 정리.
- [x] **T1-VERIFY** ✅ convergence plan 재개지점·환경표기(node 24·docker 추가) 갱신. **남은 실행**: 4.2(backend PR)·4.3(live 실측)·5(마감) = convergence plan 따라 진행.

### T2 — 문서 부채 quick win 🟠 (controller, main 직접 — 저위험)

- [ ] **T2-1 (M1D-01)** `submodule` 6곳 → `buf 원격 git input(ADR-0010)` 일괄 치환. 특히 CLAUDE.md:10 가드레일① = '다운스트림 buf git-input ref bump → 3언어 재생성'. `grep -rn submodule docs/ CLAUDE.md` 잔존0 확인.
- [ ] **T2-2 (M1D-02)** CLAUDE.md:4 = '현재 존재: backend/crdt-engine/frontend(+controller). ai-service=M4·doc-service=M2 신설 예정'. SDD §12 트리에 '(M2/M4 신설)' 마커.
- [ ] **T2-3 (M1D-03/04)** SDD §12 'ci/' → '.github/workflows/(buf 게이트; 다운스트림 트리거=M5 TODO)' 정정. ADR README 0002~0009에 'M6 분리, SDD §15 권위' 마커 + 미해결5 중복 제거(SDD §15 단일권위).
- [ ] **T2-4 (PDD-06/07)** M0 dev-log `status: open→resolved` + tier 재산출 + self-loop 제거. onboarding guide:6 '현재 plan' → convergence plan §재개지점.
- [ ] **T2-5 (M1D-05/06, TEST-01)** PRD §7 DoD 9개에 마일스톤 태그(수렴→M1 / 복원→M2 / 커서→M3 / AI→M4 / GitOps→M5). SDD §9/§11에 '(M5)/(M2)/(M4)' 마커.
- [ ] **T2-VERIFY** `grep -rn submodule` 0건, 문서 상호참조 모순 없음.

### T3 — M2 readiness 🟡 (M2 착수 전 확정 — plan·ADR 선기록)

> blocker(M2F-02) 미해결 시 M2 첫 줄 불가. 이 트랙 완료 = M2 plan 작성 가능 상태.

- [ ] **T3-1 (M2F-02, blocker)** ADR 'CRDT 스냅샷 영속화 트리거 방향' — 대안 A(엔진 push, build_client(true)) / B(doc-service pull) / C(게이트웨이) 비교표(가드레일5 정합·멀티인스턴스 중복저장·트랜잭션경계). 권장 A + 트리거 임계(N updates/T초) 수치.
- [ ] **T3-2 (M2F-05, SEC-01)** ADR '인증/인가 경계' — JWT 발급(doc-service)·검증(게이트웨이) 위치, WS 토큰 전달방식(Sec-WebSocket-Protocol vs 쿼리 vs 첫메시지, write-time 검증), VIEWER 쓰기차단 게이트 위치, 실패 close code.
- [ ] **T3-3 (M2F-06)** ADR 'outbox 방식' — Debezium vs 앱레벨 transactional outbox 비교(홈랩 KinD 리소스). 권장 앱레벨, 테이블/트랜잭션은 M2 선반영·릴레이는 M4.
- [ ] **T3-4 (M2F-03/04)** M2 복원 시퀀스 설계(엔진 ensure→스냅샷 로드→decode_v1→apply→SyncStep2) + 'M2 보장경계=마지막 스냅샷, in-flight 유실허용(Redis=M5)' + proto 영향분석(LoadSnapshot 신설 vs GetSnapshot 재사용 / CheckPermission 토큰필드). 변경시 proto Phase0 분리 + proto-v0.2.0.
- [ ] **T3-5 (M2F-01)** `docs/plans/2026-..-m2-persistence-session.md` 선기록(Context=T3-1~4 확정결과, Phase분해, Blast Radius, 재개지점). 커밋 후 코드 착수.
- [ ] **T3-6 (M2F-08, DOC-01)** SDD §15 미해결5 소유 마일스톤 재배정(복원·outbox·인증=M2 / consistent-hash=M3 / AI SLO=M4) + 경량 로드맵 결정소유권 맵.

### T4 — 횡단 프로그램 🟢 (마일스톤 관통 — 한 번에 안 끝남, 선등록)

- [ ] **T4-1 (NFR-01/02, DOD-01/02)** `docs/status/dod-tracker.md`(DoD 9개 × 마일스톤 × 검증증거) + NFR별 측정수단·소유 마일스톤 매핑(p95→M3 부하 k6/Gatling, AI→M4). 벤치≠SLI caveat. M1 완료분(#1/#6부분/#8) 마킹.
- [ ] **T4-2 (OBS-01)** 관측 콜사이트 정의(engine merge_duration 히스토그램·active_streams 게이지·lagged_total 카운터 / gateway active connection 게이지). M5 백엔드 전이라도 콜사이트 목록을 M5 plan에 선고정(가능하면 no-op exporter로 콜사이트 선삽입).
- [ ] **T4-3 (CI-01)** 서비스레포 최소 PR CI를 M2 전 도입(engine: cargo test+clippy+bench --no-run / gateway: gradle test / frontend: vitest+build). 이미지빌드(cargo-chef/distroless)·소비자 buf 정합·다운스트림 트리거는 M5. 각 서비스레포 branch+PR+승인.
- [ ] **T4-4 (PDD-02)** ADR 승격 프로그램 — blast radius 큰 것부터(0004 Rust bidi 엔진·0005 yrs·0007 Istio Ambient) 대안비교표 포함 정식 ADR. M6 마감 전 완성.
- [ ] **T4-5 (PDD-04, SEC-02, 완전성보강)** ①overview.md 결정(생성 또는 룰 현실화) ②M5 plan stub에 mTLS STRICT+평문거부 검증 시나리오·입력검증 규칙 ③통합 로컬개발 compose(engine+gateway+jaeger 일괄) ④의존성 보안 스캔(cargo audit/npm audit) CI 항목 ⑤버전핀 매트릭스 문서.

---

## 검증

| 트랙 | 검증 | 게이트 |
|---|---|---|
| T1 | engine PR green(test/clippy/fmt) · plan 4.2/4.3/5 "추측 없이 실행가능" 셀프리뷰 · 4.3 done=수렴 E2E+단일trace | M1 마감 |
| T2 | `grep -rn submodule docs/ CLAUDE.md`=0 · 문서 상호참조 모순0 | 문서 정합 |
| T3 | ADR 3건 대안비교표(documentation.md 검증규칙) · M2 plan 재개지점 완비 · proto 영향 결론 명시 | M2 착수 가능 |
| T4 | DoD 트래커 존재 · 서비스 CI green · ADR 번호 연속 | 횡단 추적성 |

## 범위 밖 (이 plan에서 안 함)

- 실제 M2 doc-service 구현(T3은 plan·ADR 선기록까지) / M3~M6 상세 plan(각 착수 시 작성, T3-6은 소유권 맵만).
- M5 인프라 실구현(Istio Ambient·ArgoCD·이미지빌드) — 마커·검증시나리오 stub만.
- 관측 백엔드(LGTM) 실배포 — 콜사이트 정의만(T4-2).

---

## 재개 지점 (Resume)

> **마지막 완료**: **T1 계획 구체화 완료**(2026-06-30) — Phase 0 기록 커밋(dev-log 1344fc6·plan fb7060f) + T1 전체: spec 검증(opentelemetry-otlp 0.32·Jaeger v2·javaagent 2.29), convergence plan §4.2/4.3/5 구체화, `infra/local/docker-compose.jaeger.yml` 생성, M1R-09 검증(engine 변경 불요).
> **다음 작업**: T1 커밋(controller main 직접) → **4.2/4.3/5 실제 실행**은 구체화된 [convergence plan](2026-06-25-m1-convergence-impl.md) 따라 — 4.2(backend javaagent, branch+PR+승인) → 4.3(이 Linux서 `docker compose ... jaeger` live 검증) → Phase 5 마감. 또는 **T2(문서 부채 quick win, controller main 직접)** 먼저 처리 가능.
> **주의(검증된 사실, 변경 금지 전제)**: ~~telemetry.rs endpoint 미전달~~ → **M1R-09 기각**(0.32 env 자동읽기 검증, 코드 정상·`.with_endpoint` 추가 금지). build_client(false)로 엔진→doc-service 호출불가(T3-1 blocker, 유효) · submodule 6곳(T2-1, 유효) — grep 확인됨. engine·backend·frontend 변경은 branch+PR+건별 승인. controller는 main 직접.
> **환경**: rust 1.96 · java 25.0.3 · node 24 · docker 29.6 · buf 1.71 · gh 2.95 (전부 Linux 설치 완료). 전체 40건 근거는 dev-log appendix.
