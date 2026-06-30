# PRD — 데이터 모델 · 권한/공유 모델 (제품 관점)
> [← 인덱스](../PRD.md) · 선행: [3. 정보구조·UX](3-information-architecture-ux.md)

> 이 문서는 **제품 관점의 모델**이다(무엇을·왜). 테이블 DDL·인덱스·트랜잭션 경계 같은 "어떻게"는 SDD §5 / M2 doc-service 설계에서 확정한다.
> ⚠️ **현 SDD §5는 평면 `documents` 구조**(workspace·트리 없음)다. 본 문서가 정의하는 모델은 SDD §5를 **확장·대체**한다 → SDD 갱신은 [결정 필요 D-1](#결정-필요) 참조.

---

## 1. 제품을 한 문장으로

> 팀이 **워크스페이스** 안에서 **페이지 트리**로 지식을 쌓고, 각 페이지를 **실시간 동시 편집**하며, **워크스페이스 멤버십 + 페이지별 공유**로 접근을 통제하는 사내 위키.

이 한 문장이 데이터 모델의 4개 축을 결정한다: **워크스페이스 / 페이지(트리) / 멤버십 / 권한(공유)**.

---

## 2. 핵심 엔티티 (제품 관점)

```
User ──┬─< WorkspaceMember >── Workspace ──< Page (self-tree: parent_id) >── PagePermission
       │         (role)                          │                              (level)
       └─────────────────── (principal) ─────────┴──────────────────────────────┘
```

| 엔티티 | 의미 | 핵심 속성 (제품 관점) |
|---|---|---|
| **User** | 계정 주체 | email, 표시이름 |
| **Workspace** | 팀 지식의 경계. 모든 페이지의 최상위 컨테이너 | name, owner |
| **WorkspaceMember** | User가 Workspace에 속한 관계 | `role`: `owner` \| `member` |
| **Page** | 위키의 한 페이지 = 한 CRDT 문서. **자기참조 트리**(`parent_id`) | title, parent_id, position(형제 정렬), archived |
| **PagePermission** | 특정 페이지에 대한 명시적 공유 (선택적 오버라이드) | principal(=User), `level`: `editor` \| `viewer` |
| **PageSnapshot** | 영속화된 CRDT 상태 (복원용) | page_id, snapshot(bytea), version |

> **명명 변경 제안**: 기존 SDD의 `documents`/`document_members` → 위키 맥락에 맞춰 `pages`/`page_permissions`. "문서"보다 "페이지"가 트리·중첩을 더 잘 표현한다. (D-1)

---

## 3. ⭐ 가장 중요한 경계 — CRDT는 어디까지인가

이 프로젝트의 핵심 증명(분산 동시성)과 직결되는 결정. **두 종류의 "동시성"을 분리한다.**

```
┌──────────────────────────────────────────────────────────────┐
│  ① 페이지 "내용"의 동시성       →  CRDT (yrs/Yjs)              │
│     같은 페이지를 여러 명이 동시에 타이핑·블록 이동·분할        │
│     = M1에서 증명한 경로. 머지 순서 무관 수렴 보장.            │
│     소유: CRDT Engine(Rust). 영속: PageSnapshot.              │
├──────────────────────────────────────────────────────────────┤
│  ② 페이지 "트리"의 동시성       →  CRDT 아님 (관계형 + 직렬화) │
│     두 명이 동시에 페이지를 다른 위치로 이동(reparent)         │
│     = 트리 사이클·고아 위험. doc-service가 트랜잭션으로 처리.   │
│     소유: doc-service(Postgres). 이동 시 사이클 검사.         │
└──────────────────────────────────────────────────────────────┘
```

**왜 트리를 CRDT로 안 하나 (MLP 판단):**
페이지 이동은 (a) 내용 편집보다 **압도적으로 드물고**, (b) 충돌 시 "마지막 이동 우선 + 사이클 방지"로 충분하며, (c) 트리 CRDT(Kleppmann의 *highly-available move operation for replicated trees*)는 구현 난이도가 높다. → **트리는 doc-service에서 직렬화**, 트리 CRDT는 명시적 **확장(2차)** 으로 미룬다.

> 이 경계는 기존 가드레일("엔진은 한 문서 내용 스트림만 담당")과 정확히 일치한다. **ADR 후보**: `0012-crdt-boundary-content-vs-tree`. (D-2)

**트리 이동 충돌 처리 (doc-service):**
```
move(page P, new_parent N):
  1. N이 P 자신 또는 P의 자손이면 거부 (사이클 방지)
  2. 단일 트랜잭션으로 parent_id·position 갱신
  3. 동시 이동은 row lock으로 직렬화 (마지막 커밋 우선)
```

---

## 4. 권한/공유 모델 — "둘 다 가능" 풀어내기

사용자 요구: *워크스페이스 단위로도, 노션처럼 문서(페이지) 단위로도 권한이 가능하고, 레벨은 편집/읽기로 갈린다.* → **2계층 + 상속** 모델로 정식화한다.

### 4.1 두 개의 권한 출처

```
출처 A) 워크스페이스 멤버십 (baseline)
        owner  → 워크스페이스 내 모든 페이지 editor + 멤버/공유 관리
        member → 기본 접근 레벨(D-3에서 확정: editor 또는 viewer)

출처 B) 페이지별 공유 (override, 선택적)
        특정 페이지에 User를 editor/viewer로 명시 → baseline을 덮어씀
        트리 하위로 상속됨(아래 4.2)
```

### 4.2 유효 권한 해석 (effective permission)

한 사용자가 한 페이지에 대해 갖는 **최종 권한**은 다음 순서로 결정한다 — 노션과 동일한 "가장 가까운 명시 권한 우선 + 상속" 규칙:

```
effective(user, page):
  1. page에 user의 명시적 PagePermission 있으면          → 그 level
  2. 없으면 조상 페이지를 위로 탐색,
     가장 가까운 조상의 명시 권한 있으면                  → 그 level (상속)
  3. 그래도 없으면 워크스페이스 role의 기본 레벨           → baseline
  4. 워크스페이스 멤버도 아니면                            → 접근 불가
```

ASCII로 본 상속 예시:
```
Workspace (member 기본 = viewer 라고 가정)
└─ 📄 엔지니어링            (Alice를 editor로 공유)
   ├─ 📄 백엔드 가이드        → Alice: editor (상속)
   │  └─ 📄 DB 스키마         → Alice: editor (상속)
   └─ 📄 보안 정책 (Alice를 viewer로 오버라이드) → Alice: viewer (가장 가까운 명시 우선)
```

### 4.3 권한 레벨 정의

| level | 읽기 | 편집(CRDT write) | 공유/멤버 관리 | 페이지 삭제·이동 |
|---|---|---|---|---|
| **viewer** | ✅ | ❌ | ❌ | ❌ |
| **editor** | ✅ | ✅ | ❌ | ✅(편집의 일부로 볼지 D-4) |
| **workspace owner** | ✅ | ✅ | ✅ | ✅ |

> MLP는 3단계로 충분(viewer/editor/owner). 페이지별 "owner" 같은 4번째 레벨은 복잡도 대비 효용이 낮아 **비범위**.

### 4.4 게이트웨이 연동 (기존 SDD §6.2/§8과 정합)

권한은 **연결 시점에 1회 + 변경 시 무효화**로 검사한다. 기존 시퀀스에 자연스럽게 끼워진다:
```
client → gateway: connect(pageId, JWT)
gateway → doc-service: CheckPermission(user, pageId)
        ⇒ effective level (viewer/editor)
  viewer  → CRDT Sync 스트림을 read-only로 open (서버가 client→server update drop)
  editor  → 양방향 Sync 스트림 open
  none    → 연결 거부(403)
```
> ⚠️ **viewer의 write 차단은 게이트웨이/엔진에서 강제**해야 한다. 클라이언트 read-only 플래그만 믿으면 안 됨(보안). (D-5)

---

## 5. MLP에 포함 / 제외 (이 모델 기준)

**포함 (실제 써지려면 필수):**
- 워크스페이스 1개 + 멤버 초대(email)
- 페이지 트리: 생성 / 이름변경 / 이동 / 삭제(아카이브)
- 페이지 내용: 블록 에디터 + 실시간 수렴(M1 확장) + 영속화(M2)
- 권한: 워크스페이스 멤버십(owner/member) + 페이지별 editor/viewer 오버라이드 + 상속
- JWT 인증

**제외 → 확장 로드맵(2차):**
- 트리 자체의 CRDT(동시 이동 자동 머지) — 직렬화로 대체
- 페이지별 세분화된 role(owner/commenter 등)
- 공개 링크 공유 / 외부 게스트
- 권한 변경의 실시간 즉시 반영(연결 중 강등) — MLP는 재연결 시 반영
- 버전 히스토리 / 페이지 복원 UI(스냅샷은 저장하되 UI는 후속)

---

## 6. 결정 필요 (Decisions)

기획 확정 전에 너의 선택이 필요한 항목. 각각 M2 doc-service 스키마에 직접 영향을 준다.

| ID | 결정 | 옵션 / 기본 제안 |
|---|---|---|
| **D-1** | SDD §5 갱신 범위 | `documents`→`pages` 개명 + workspace/parent_id/page_permissions 추가. **제안: 채택** |
| **D-2** | CRDT 경계 ADR 작성 | `0012-crdt-boundary-content-vs-tree`. **제안: 작성** |
| **D-3** | 워크스페이스 `member`의 기본 레벨 | editor(개방·위키스럽다) vs viewer(보수적). **제안: editor** — 사내 위키는 "누구나 고침"이 자연 |
| **D-4** | editor가 페이지 삭제·이동 가능? | 편집의 일부로 허용 vs owner만. **제안: 허용**(아카이브는 되돌릴 수 있으니) |
| **D-5** | viewer write 차단 위치 | 게이트웨이 강제(권장) vs 엔진 강제. **제안: 게이트웨이 1차 차단 + 엔진 방어** |
| **D-6** | 멀티 워크스페이스 | MLP는 1워크스페이스 고정 vs N개. **제안: 데이터는 N 지원, UI는 1개로 시작** |
