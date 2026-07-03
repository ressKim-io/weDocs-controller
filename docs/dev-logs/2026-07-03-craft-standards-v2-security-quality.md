---
date: 2026-07-03
category: meta
tier: 2
importance: major
status: resolved
tags: [craft-standards, design-patterns, secure-coding, security-scan-ci, gate-simulation, gitleaks, cargo-audit, dependency-graph, config-contract]
related:
  - plans/2026-07-03-security-quality-standards.md
  - plans/2026-07-03-secure-coding-retrofit.md
  - plans/2026-07-01-craft-standards-alignment.md
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0014-auth-authz-boundary.md
---

# 크래프트 표준 v2 (design-patterns·secure-coding) + 4레포 보안 스캔 CI

## 무엇

"실무 배포 가정 시 코드 품질(디자인 패턴)·보안이 부족하고 특히 Java·Rust가 심하다"(사용자, 2026-07-03)에 대한 영구 상향 패키지. 갭 실측(3-agent) 결과 **표준 지식이 없는 게 아니라 게이트가 없었다**: 기존 4종은 "어떻게 짜나"만 강제, 구조 판단·앱 보안은 [B]/[A] 미배선(🔒 렌즈는 인프라 편향), PRD/SDD엔 품질·보안 0줄, 서비스 레포 CI 전무.

산출: ① 크래프트 표준 6종 체제(`design-patterns.md` P1~7 · `secure-coding.md` P1~5 신설 + 렌즈/Gate 3/CLAUDE.md 배선) ② PRD §6 NFR 보안 확장+코드 품질 행 신설, SDD §14 불변 규칙 ⑦⑧, §15 하드닝 마일스톤 5건 등록 ③ 4레포 보안 스캔 CI(아래) ④ retrofit plan(`2026-07-03-secure-coding-retrofit.md`, P0=3-레포 DoS 체인 — 실행은 M2 Phase 2 분기 전).

신설 장치 2건: **칼리브레이션 주석**("[B]는 diff가 생성·변경하는 코드 기준 — 기존 위반은 [A]+retrofit") + **escape hatch**("근거 주석+이슈 링크로 [B] 통과") — 표준이 개발 마비로 역전되는 것 방지.

## 게이트 시뮬레이션 — "커밋 전에 표준을 실코드에 1회 실행"의 가치 (핵심 교훈)

신규 체크리스트 22항목을 crdt-engine HEAD `0355a58` src 3파일에 rust-expert로 실행(커밋 전):

| 결과 | 내용 |
|---|---|
| 기대 [B] fire 6/6 | DocId 무검증(engine.rs:39-49) · open() 삽입-only(engine.rs:109-123) · 크기 상한 미설정(main.rs:23-24) · 무인가 RPC(service.rs:71,107) · doc-id 에코백(service.rs:193) · ServerFrame 수동 조립 4곳(service.rs:149·204·235·246) |
| **오탐 0/5** | thiserror·DashMap 샤딩·바운디드 채널·DocId newtype 존재·unwrap 0건 — 전부 미발화 (양호 사례와 결함을 정확히 분리) |
| **문구 교정 2건** | 아래 |

**교정 ① (최중요) — A2가 ADR-0013을 오지목**: 초안은 "레지스트리 = 저장 백엔드 교체 예정 경계 → trait 필요"를 [B]로 강제할 뻔했으나, ADR-0013 원문의 실제 seam은 **엔진→doc-service 아웃바운드 호출**(SaveSnapshot/LoadSnapshot)이지 레지스트리가 아님. 레지스트리 trait는 오히려 추측성 추상화(과설계 가드 위반). → 체크리스트에 "교체점 위치는 **ADR/plan이 명시한 seam**으로 특정(해석·추측 금지)" 단서 추가, Rust 실현부를 양방향 가드 실례(SnapshotStore ⭕ / DocRegistry trait ❌)로 재서술. **[B] 게이트에 특정 아키텍처 '해석'을 박으면 게이트가 오설계를 강제한다** — deep-thinking(기록 전 검증)의 표준 문서판.

교정 ②: "실패 가능 변환은 TryFrom" → **"검증이 필요한 값의 변환에 무검증 From 금지"** — `DocId::from`은 infallible이라 전자의 트리거가 안 걸리는데 결함 실체는 검증 부재. 트리거를 "실패 가능성"이 아니라 "검증 필요성"에 건다. (+ A8 "타입이 강제 가능한 필드 불변식" 한정, A3 "선언·조립 무관", B5 "출처 무관 에코백" 정밀화)

escape hatch 실효도 검증됨: `DocId` 기존 주석은 근거는 있으나 이슈 링크가 없어 정발화 — "주석만으로는 통과 불가" 요건이 실제로 일함.

## 보안 스캔 CI (트랙 2) — 4레포

| 레포 | 시크릿 | SCA | 머지 |
|---|---|---|---|
| controller | gitleaks-action v3 | — | main 직접 `2b37069` |
| crdt-engine | gitleaks v3 | rustsec/audit-check v2 | PR #6 → `e925078` |
| backend | gitleaks v3 | dependency-submission v6 + dependency-review v5(high+) | PR #5 → `0992f70` |
| frontend | gitleaks v3 | npm audit --audit-level=high | PR #2 → `1d4dad5` |

공통: PR + push(main) + 주간 schedule, gitleaks `fetch-depth: 0`(전 히스토리). 전 레포 CI green 실측 후 머지.

**함정 — backend Dependency graph 기본 비활성**: dependency-review 문서는 "public 레포 지원"이라 기본 활성을 가정했으나, 실제 레포는 `security_and_analysis.dependency_graph` 꺼져 있어 submission(BUILD SUCCESSFUL인데 제출 API 거부)·review 둘 다 실패. `gh api -X PUT repos/<o>/<r>/vulnerability-alerts`로 활성화(의존성 그래프 동반) 후 재실행 → green. **"플랫폼 기능은 문서상 지원 ≠ 레포에 켜짐"** — config-contract-audit 3단계(명시값/기본값/환경별)의 GitHub 설정판. 새 레포에 dependency-review 도입 시 그래프 활성화를 선행 체크리스트로.

## 기술 사실 검증 (deep-thinking — 전부 기록 전 WebFetch, 2026-07-03)

tonic 디코딩 기본 4MB(docs.rs) · Tomcat WS 버퍼 기본 8192B(Tomcat 11 How-To) · Spring WS 기본 same-origin(공식 레퍼런스) · gRPC 기본 deadline 없음(grpc.io) · gitleaks-action **v3**·User 계정 라이선스 불요(README+`gh api`로 계정 타입 실측) · gradle dependency-submission **v6**(lockfile 불요)+dependency-review **v5** 조합(공식 docs) — osv-scanner는 lockfile 요구로 기각.

## 남긴 것

retrofit 실행(P0 DoS 체인)=별도 plan(planned) · SAST 확장(semgrep/CodeQL)=M5 · eviction=ADR-0013 선행 · 정량 캡=M3 — SDD §15 등록. rust 패턴 스킬은 게이트 2~3회 실행 후 [A] 처방 빈약 시 신설.
