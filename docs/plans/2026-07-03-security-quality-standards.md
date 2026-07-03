---
date: 2026-07-03
slug: security-quality-standards
status: in-progress
related:
  - plans/2026-07-01-craft-standards-alignment.md
  - plans/2026-06-30-m2-persistence-session.md
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0014-auth-authz-boundary.md
---

# 크래프트 표준 v2 (설계 패턴·시큐어 코딩) + 보안 스캔 CI — 실무급 품질 영구 상향

## Context

**문제**(사용자 제기): 실무 배포 가정 시 코드 품질(디자인 패턴·구조 판단 부재)과 보안이 부족 — 특히 Java·Rust. 크래프트 표준 4종이 있어도 모자람. 이를 PRD/SDD·rules로 **영구** 상향해야 함.

**탐색으로 확정한 갭의 본질** (2026-07-03, 3-agent 실측):

1. **"무엇으로 짜나" 게이트 부재** — 기존 4종(error-handling/concurrency/layering-readability/observability)은 "어떻게 짜나"만 강제. 추상화 도입 판단·타입 불변식 강제·생성 설계·분기 구조는 게이트 없음. 실증: 엔진 `ServerFrame` 수동 조립 4곳(상호배타 미강제), 레지스트리 구체 결합(ADR-0013 저장 백엔드 교체 예정인데 경계 trait 없음), 게이트웨이 room raw String 관통(엔진 `DocId` newtype과 비대칭) — 전부 리뷰 통과해 머지됨.
2. **앱 레벨 시큐어 코딩 게이트 실질 부재** — `security.md`(전역 룰)·`skills/security/` 5종은 지식일 뿐 [B]/[A] 미배선. code-review.md 🔒 렌즈는 인프라(K8s/RBAC/TLS) 편향 + 실행 에이전트 미바인딩. 실증: **3-레포 관통 DoS 체인**(frontend 무검증 room → gateway 무검증 전달 → engine 무한 문서 생성 + eviction 없음), WS Origin `*`, 프레임/메시지 크기 무상한(런타임 기본값 암묵 의존), GetSnapshot 무인증, gRPC deadline 부재.
3. **PRD/SDD에 품질·보안 표준 0줄** — PRD §6 NFR 보안 행 = "mTLS, JWT" 한 줄. SDD §14 불변 규칙 6개 중 보안·품질 0개.
4. **보안 도구 게이트 부재** — 서비스 레포에 CI 자체가 없음(시크릿·의존성 스캔 전무).

**해법** (사용자 확정 범위, AskUserQuestion 2026-07-03):
- 트랙 1: 크래프트 표준 2종 신설(`design-patterns.md`·`secure-coding.md`) + 게이트 배선 + PRD/SDD 승격 — controller main 직접
- 트랙 2: 보안 스캔 CI(시크릿+의존성) **지금 구축** — controller 직접 + 서비스 3레포 PR·건별 승인
- 트랙 3: 기존 코드 retrofit은 **plan 초안만**(실행 = 다음 세션)

**설계 원칙**:
- 포맷 = `error-handling.md` 복제(P원칙 → Java/Rust 실현 → ✅ [B]/[A] 체크리스트 → 게이트 배선 → 출처). Python 실현 없음(M4).
- 게이트 배선 = code-review.md 42–43행 **목록 확장만**(렌즈 행 추가 금지 — 게이트 활성화 원칙) + phase-workflow.md Gate 3 목록 + CLAUDE.md + README 카운트.
- SSOT(M1 회고 교훈) = 원칙·체크리스트 본문은 rules에만. PRD/SDD·CLAUDE.md는 선언+링크. "표준 4종" 하드코딩 전수 갱신.
- 신설 장치: **칼리브레이션 주석**("[B]는 diff가 생성·변경하는 코드 기준, diff 밖 기존 위반은 [A]+retrofit 이슈") + **escape hatch**("정당 사유는 근거 주석+이슈 링크로 [B] 통과") — 표준 도입이 개발 마비로 역전되는 것 방지.
- 중복 금지 역할 분담: design-patterns는 java.md/spring.md/layering-readability/clean-code와, secure-coding은 security.md(금지 목록 SSOT — 위임 집행 1줄)/concurrency P7(내부 채널)/observability P4(로그)와 경계 명시.
- deep-thinking: 룰에 기재하는 기술 수치(tonic 기본 한도·Tomcat WS 버퍼·Spring Origin 기본·gRPC deadline)는 공식 출처 WebFetch 확인 후 기재, 실패 시 수치 삭제 일반형 폴백. 스캔 도구(gitleaks·cargo-audit·Gradle SCA) 액션/설정도 스펙 검증 후 확정.

상세 설계(P원칙 전문·체크리스트 초안·편집 위치)는 승인된 harness plan 기준 — 실행하며 이 파일 체크리스트에 결과만 기록.

## 실행 체크리스트

- [x] **C1**: 이 plan 커밋 (작업 시작 전) — `a051fd4`
- [x] 기술 사실 WebFetch 검증 — 전 항목 공식 출처 확인(tonic 4MB·Tomcat 8192B·Spring same-origin·gRPC deadline 없음). 도구 확정: gitleaks-action **v3**(User 계정=라이선스 불요, 실측)·rustsec/audit-check v2·Gradle SCA=**dependency-submission@v6 + dependency-review-action@v5**(lockfile 불요 — osv-scanner 기각)
- [x] `.claude/rules/design-patterns.md` 작성 (P1~P7 + Java/Rust 실현 + 체크리스트)
- [x] `.claude/rules/secure-coding.md` 작성 (P1~P5 + Java/Rust 실현 + 체크리스트 + 적용 시연 부록)
- [x] **게이트 시뮬레이션**: 기대 [B] 6종 전부 fire + 오탐 0 (rust-expert, HEAD `0355a58`). 문구 개정 5건 — **A2 오지목 교정**(ADR-0013 seam=아웃바운드 클라이언트, 레지스트리 trait는 과설계)·A10 트리거 재정의(실패 가능→검증 필요)·A8 불변식 한정·A3 조립 포함·B5 출처 무관 에코백
- [x] **C2**: design-patterns.md 커밋 — `8853164`
- [x] **C3**: secure-coding.md 커밋 — `f710058`
- [x] **C4**: 게이트 배선 4파일 — `4301030` (README 카운트 24(stale)→31 실측 정정 포함)
- [x] **C5**: PRD/SDD 승격 — prd/2 §6·sdd/5 §14 ⑦⑧+§15 하드닝 등록·CLAUDE.md 가드레일 7·8 미러 (이 커밋)
- [ ] **C6**: controller `.github/workflows/security-scan.yml`(gitleaks) + `ci/README.md` 스캔 표준 문서화
- [x] **C7**: `docs/plans/2026-07-03-secure-coding-retrofit.md` 초안 — `d94c737` (§15 링크 무결성 위해 C5보다 먼저 커밋, 순서 교환)
- [ ] 서비스 레포 스캔 CI — crdt-engine (gitleaks+cargo-audit, branch+PR+건별 승인)
- [ ] 서비스 레포 스캔 CI — backend (gitleaks+Gradle SCA, branch+PR+건별 승인)
- [ ] 서비스 레포 스캔 CI — frontend (gitleaks+npm/osv, branch+PR+건별 승인)
- [ ] **C8**: 마감 — dev-log(시뮬레이션 매트릭스)·plan status done·CLAUDE.md 현재 상태·메모리(표준 4종→6종)

## 검증

1. **게이트 시뮬레이션** (룰 커밋 전): 기대 fire = 레지스트리 구체결합(DP-P2)·ServerFrame 상호배타(DP-P4)·DocId 무검증(SC-P1)·open() 삽입-only(SC-P2)·max_decoding 미설정(SC-P2). **오탐 0**: thiserror·바운디드 채널·DashMap 샤딩 미발화. 판정 불가 항목 → 문구 개정 후 재실행.
2. **배선 완전성 grep** (C5 후):
   ```sh
   grep -rn "design-patterns\|secure-coding" CLAUDE.md .claude/rules/code-review.md \
     .claude/rules/phase-workflow.md .claude/README.md \
     docs/prd/2-scope-nfr-dod.md docs/sdd/5-project-milestones-guardrails.md
   ```
   역방향: 크래프트 표준을 "4종"으로 하드코딩한 잔존 0 (plans/dev-logs 역사 기록 제외).
3. **링크 유효성**: 신규 상대 링크 대상 파일 존재를 각 문서 디렉토리 기준으로 확인.
4. **CI 실검증**: 각 워크플로 PR에서 실제 run green + gitleaks 전체 히스토리 스캔(fetch-depth: 0) 동작 확인.

## 재개 지점 (Resume)

- 마지막 완료 = C5 (PRD/SDD 승격) — 트랙 1 완료, 트랙 3(retrofit plan) 완료
- 다음 = C6 controller 스캔 CI → 서비스 3레포 CI PR(건별 승인) → C8 마감
- 주의 = 서비스 레포 push·PR 생성·머지는 **건별 승인 STOP**. backend 로컬 클론 stale(main=30e0aca, PR #3/#4 미반영) — fetch 후 작업. controller만 main 직접.

## 범위 밖

- **retrofit 실행**(기존 코드 수정 PR) — `2026-07-03-secure-coding-retrofit.md`(트랙 3 산출물)의 다음 세션 몫. P0 = 3-레포 DoS 체인.
- 빌드/테스트 CI 전체(T4 횡단) — 이번은 보안 스캔 레인만.
- SAST 확장(semgrep/CodeQL) → M5, 인프라 하드닝(mTLS/NetworkPolicy) → M5, 레이트리밋 정량 → M3 — SDD §15 등록으로 추적.
- rust 일반 패턴 스킬 신설 — 보류. 트리거 = 신규 게이트 2~3회 실행 후 rust-expert [A] 코멘트의 처방 구체성 부족 확인 시(retrofit plan에 기록).
- ai-service Python 실현 섹션 — M4 신설 시.
