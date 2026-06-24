# Deep Thinking Rules — 얕은 고민 금지

모든 작업에서 **얕은 추측 / "이미 알고 있다는 자신감" / 검증 회피**로 명시·답변·구현하지 않는다.
이 규칙은 모든 도메인, 모든 작업에 적용된다.

> **배경 — 추정 사고 (2026-05-13)**: Ongilro Apple 스택 추정 사고 — knowledge cutoff 이후 출시된 Xcode 26 / Privacy Manifest / Approachable Concurrency 표시명을 검증 없이 추정으로 명시했고, 그 추정값을 다시 보강(G1-G7)에 자기 강화 인용. 사용자가 "왜 최신 기준으로 안 하는가" 지적. **얕은 고민은 기초 전체를 무너뜨린다.**

---

## 핵심 금지 (MANDATORY)

| 금지 행위 | 이유 |
|---|---|
| **knowledge cutoff 이후 출시·변경된 도구/버전/SDK 를 검증 없이 명시** | 추정 기록 → 추정값 강화 루프 → 도미노 오류. 한 번 들어간 추정이 다음 기록의 기초가 되면 검증 불가능한 모래탑 |
| **기록된 값을 검증 상태 확인 없이 받아 다음 기록 추가** | "추정값을 추정값으로 정당화" 자기 강화. 첫 기록이 틀리면 다 틀림. **인용 전 원본 verified 상태 확인 필수** |
| **추측 명시 후 caveat 박스 / "확인 필요" 노트로 면피** | caveat 는 검증 100% 불가 영역의 사후 보강이지, **검증 가능한 영역의 검증 대체가 아니다**. 검증 5분이면 끝나는 영역을 caveat 로 처리하는 것은 게으름 |
| **단일 출처 / 단일 패턴 기반으로 명시** | 공식 docs + WWDC 세션 + 신뢰성 있는 블로그 cross-check. 한 출처가 잘못되거나 outdated 일 때 catch 가능 |
| **"GUI 표시명 / API 명칭 / Build Setting key / Info.plist 키 / 파일 명명 규칙" 추정** | 이 영역은 spec 검증 5-10분이면 충분. 추정 명시 금지 영역 |
| **사용자가 "이거 검증된 거야?" 물어야 그제서야 검증 시작** | 검증 시점이 잘못됨. 기록 전 검증, 인용 전 검증, 답변 전 검증 — **사용자 의문 제기는 마지막 catch-net 이지 첫 trigger 가 아니다** |
| **"Xcode 15/16 패턴 기반 추정" 같은 fallback 명시 후 기록** | 신규 버전 검증 회피의 흔적. 신규 버전 검증을 먼저 한 후, 차이가 없으면 그제서야 fallback 으로 명시할 수 있음 |

---

## 의무 (MANDATORY)

### 1. Knowledge Cutoff 자각

매 작업에서 자신의 cutoff (예: 2026-01) 이후 출시/변경된 도구·버전·SDK·API·정책을 다룰 때:

- **즉시 자기 체크**: "이 정보는 cutoff 이후의 것인가?"
- 그렇다면 **WebFetch / WebSearch 로 공식 출처 확인 필수**
- 확인 안 한 상태로 명시·답변·구현 금지
- "추정해서 일단 진행" 패턴 금지 — 추정은 검증 후에만 fallback 으로 허용

### 2. 검증 가능한 모든 기록값은 검증

기록 전 확인:
- **공식 출처**: Apple Developer / 공식 docs / Release Notes / GitHub release / WWDC 세션 / 라이브러리 maintainer 공식 블로그
- **WebFetch 우선** — 정적 docs 는 직접 fetch 가능
- **WebSearch 보조** — 정확한 URL 모를 때 검색으로 찾기
- 단일 출처는 신뢰성 1단계 — 가능하면 2-3 출처 cross-check

### 3. verified / unverified 명시 마킹

기록 문서에:
- **출처 URL** 기록 (인용 가능한 URL)
- **검증일** 기록 (YYYY-MM-DD)
- **검증자** 기록 (subagent / Claude / ressKim 직접)
- **상태 마킹**: ✅ verified / ⚠️ unverified / ❌ mismatch
- 검증 못 한 영역은 명시적 `⚠️ unverified` 표기 + **왜 검증 못 했는가** 1줄 기록

### 4. 자기 강화 추정 루프 회피

기록값을 인용·확장할 때:
- **원본 기록의 verified 상태 확인**
- unverified → unverified 인용 금지 (도미노 오류 시작점)
- unverified 인용 필요 시 인용 자체에 ⚠️ 마킹 + 원본 검증 트리거 기록

### 5. PLAN 단계에서 추정 영역 식별

작업 시작 전:
- 변경 전 **"검증된 영역 vs 추정 영역"** 분리
- 추정 영역에 **검증 단계 추가**
- 검증 우선순위는 **변경 blast radius 가 큰 기록부터** (예: ADR / 베이스 기록 > 보강 / 인용)

### 6. 3회 룰 — 자기 의문 강제

추정 / 명시 / 인용을 3번째 작성할 때 1회 자기 의문 강제:

```
이거 정말 맞나? 출처 어디지?
- 공식 출처 확인 했나?
- knowledge cutoff 이후 변경됐을 가능성?
- 사용자가 의심하면 즉답 가능한가?
```

답이 "확신 없음"이면 즉시 검증 단계 추가.

---

## 위반 시그널 (Self-Check)

답변·명시·구현에서 다음 패턴 보이면 **얕은 고민 위반**:

| 시그널 | 의미 |
|---|---|
| "추정" / "표시명 다를 수 있음" / "Apple 공식 docs 확인 필요" 가 caveat 로 답변에 등장 | 검증 먼저 했어야 함 |
| "Xcode 15/16 패턴 기반 추정" 같은 fallback 명시 | 신규 버전 검증 회피 흔적 |
| 명시 후 사용자가 "이거 검증된 거야?" 묻고 그제서야 WebFetch 시작 | 검증 시점 잘못 — 기록 전 검증이 맞음 |
| 같은 기록값을 여러 곳에 자기 강화 인용 (PRD → ADR → onboarding → skill → agent) | 도미노 오류 위험. 원본 검증 안 됐으면 전수 검증 필요 |
| "knowledge cutoff 한계로 검증 어려움" 면피성 표현 | WebFetch 가능한 영역인데 회피. cutoff 가 절대적 핑계 아님 |
| 사용자 의문에 "맞는 지적입니다" 사후 인정 후 검증 시작 | 잘못된 시점 — 의문 전 검증이 맞음 |

---

## caveat 표기 — 그래도 명시할 때

검증 100% 불가 영역 (NDA / 비공개 베타 / Apple 미공개 / 라이센스 제약 / 출처 부재):

- **명시적 마킹**: `⚠️ unverified — [출처 시도 + 실패 이유]`
- **갱신 트리거**: "ressKim 실측 후 갱신" / "공식 docs 공개 시 재검증" 같은 구체 액션
- **caveat ≠ 면피**: caveat 는 "이 영역은 검증 불가" 입증 책임 보유. "그냥 안 했음" 의 핑계 아님
- **caveat 작성 시 1줄 기록**: "왜 검증 못 했는가" 명시. 단순 "확인 필요" 만으로 부족

---

## 적용 예 (학습 사례)

### 2026-05-13 — Ongilro Apple 스택 추정 사고

**위반 패턴**:
- 추정값: iOS 26 / Xcode 26 / Liquid Glass / Swift 6.2 Approachable Concurrency / Privacy Manifest 키 / Multiplatform App 템플릿
- WebFetch 검증 없이 controller 전체 기초로 사용
- 기록 후 보강(G1-G7) 도 검증 없이 추가 — **자기 강화 추정 루프**
- 사용자 "왜 최신 기준으로 안 하는가" 지적 후 그제서야 전수 검증 시작

**복구**:
- subagent 3개 병렬 spawn → Apple Developer 공식 docs 전수 검증
- `docs/research/apple-stack-verification-2026-05.md` 작성 (출처 URL + 검증일 + 상태 마킹)
- Layer 1-5 기록값 갱신 (verified ✅ / unverified ⚠️ 마킹)

**학습**:
- 기록 전 검증, 인용 전 검증, 답변 전 검증
- 기록값을 받는 모든 후속 작업도 검증 의무 (자기 강화 회피)
- 사용자 의문 제기는 마지막 catch-net 이지 검증 trigger 가 아니다

---

## 다른 rules 와의 관계

- `workflow.md` §"신규 도구/버전 도입 시 spec 사전 검증" — 이 rule 이 그 정신의 일반화·강화
- `debugging.md` — 가설-검증 루프 — 동일 사고방식 (검증 우선)
- `documentation.md` — 작성 검증 규칙 — 본 rule 의 문서 도메인 적용
- `user-approval.md` — 외부 영향 작업 사전 승인 — 본 rule 은 사고 깊이의 일반 원칙

이 rule 은 다른 모든 rules 의 메타 원칙. 다른 rules 가 "무엇을 어떻게 할지" 라면, 본 rule 은 "얼마나 깊게 생각하고 검증할지" 의 강제 기준.
