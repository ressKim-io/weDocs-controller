---
date: 2026-06-30
category: decision
tier: 2
importance: major
status: resolved
tags: [m2, persistence, readiness, adr, proto, page-tree]
related:
  - plans/2026-06-30-m2-persistence-session.md
  - plans/2026-06-30-plan-audit-improvements.md
  - adr/0012-crdt-boundary-content-vs-tree.md
  - adr/0013-snapshot-persistence-lifecycle.md
  - adr/0014-auth-authz-boundary.md
  - adr/0015-outbox-app-level.md
---

# M2 readiness 게이트 — 4 ADR + proto-v0.2.0로 M2 unblock

## 무엇

M2(영속화·세션·권한, doc-service 신설) **착수 전 확정 게이트**(plan-audit T3)를 완료했다. M2의 "첫 코드 줄"을 막던 결정·계약·스키마를 controller에서 전부 잠갔다.

산출물(전부 controller main 직접):
- **ADR 0012~0015** — CRDT 경계(내용=CRDT/트리=관계형) · 스냅샷 영속화(엔진 push) · 인증/인가 경계 · outbox(앱레벨).
- **proto-v0.2.0** — `DocService.LoadSnapshot` 신설 + `DocMeta` page-tree 필드(workspace_id/parent_id). additive, buf breaking 통과, 로컬 태그.
- **PRD D-1~6 확정** — page-tree+workspace 모델 채택(SDD §5 평면 `documents` 대체).
- **SDD §5 스키마 page-tree·§15 미해결 M2 3건 해소·§3 outbox/스냅샷/인증 반영.**
- **M2 plan**(`plans/2026-06-30-m2-persistence-session.md`) — Phase 1~6 구현 분해.

## 왜 (blocker)

1. **M2F-02 (blocker)**: `crdt-engine/build.rs`가 `.build_client(false)` → 엔진에 아웃바운드 gRPC 클라이언트 stub이 없어 doc-service 호출 불가. 스냅샷 영속화의 트리거 방향(누가 저장을 주도하나)이 안 정해지면 엔진 스레드 모델·트랜잭션 경계·proto가 전부 미정.
2. **스키마 충돌**: SDD §5(평면 documents) vs PRD §4(workspace+page-tree). 어느 모델로 doc-service 스키마를 쓸지 미확정.

## 핵심 결정 (사용자 확정)

| 결정 | 채택 | ADR |
|---|---|---|
| 스냅샷 트리거 | **엔진 push**(`build_client(true)`, N=100/T=10s) | 0013 |
| 데이터 모델 | **page-tree + workspace** | 0012 |
| 인증/인가 | JWT 발급=doc-service·검증=gateway, `Sec-WebSocket-Protocol`, viewer write-block=gateway+엔진 | 0014 |
| outbox | 앱레벨 transactional(Debezium 기각=KinD 리소스), relay=M4 | 0015 |

## 교훈

- **"proto 변경 없이 완수"는 M1의 성공이었지만 M2엔 함정**(plan-audit M2F-04가 사전 경고). M1은 기존 `ClientFrame`/`ServerFrame`로 충분했으나, M2 복원은 엔진→doc-service 역방향 호출이 필요 → `LoadSnapshot` 신설이 불가피. proto-stable을 목표 자체로 삼지 않는다. additive(하위호환)면 태그 bump가 정답.
- **blocker는 코드가 아니라 결정이었다.** `build_client(false)` 한 줄이 M2 전체를 막았는데, 해소는 코드 수정이 아니라 "트리거 방향 ADR"이었다. 결정 게이트를 코드 착수 전에 두는 것(T3)이 재작업을 막는다.
- **plan 선기록 준수** — M2 plan을 코드(이 게이트 산출물) 착수 전 먼저 커밋(`ee0bbba`, plan-logging §2). 세션 초기화 대비.
- **page-tree 채택의 연쇄** — D-1(page-tree) 하나가 스키마·proto(DocMeta)·권한 알고리즘(상속)·ADR-0012 경계를 전부 결정. 베이스 결정부터 잠그고 파생을 따라가는 순서가 맞다.

## 검증

- `buf lint proto` + `buf breaking proto --against '.git#branch=main,subdir=proto'` green(additive).
- ADR 4종 documentation.md §ADR 검증규칙 충족(대안 비교표·트레이드오프·정량 근거).

## 다음

M2 구현 Phase 1(doc-service 스켈레톤 + page-tree 스키마, `weDocs-backend` branch+PR). 엔진 `build_client` flip = Phase 3. proto 태그 push·다운스트림 ref bump = 서비스 레포 착수 시 승인.
