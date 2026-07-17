---
date: 2026-07-17
slug: gitleaks-false-positive-baseline
status: done
related:
  - plans/2026-07-12-m2-phase1c-rest-jwt.md
  - plans/2026-07-03-security-quality-standards.md
  - dev-logs/2026-07-03-craft-standards-v2-security-quality.md
  - dev-logs/2026-07-17-gitleaks-fingerprint-squash-trap.md
---

# gitleaks 오탐 베이스라인 정리 — 4레포 전 트리거 green

> M2 Phase 1c PR② 착수 **선행 작업**. 진입점 = [1c plan §머지 후 발견](2026-07-12-m2-phase1c-rest-jwt.md).
> controller = main 직접. **backend = branch+PR+건별 승인**.

## Context

`2026-07-03` 보안 스캔 CI 신설([plan](2026-07-03-security-quality-standards.md)) 이후 **오탐 베이스라인을 한 번도 green으로 만들지 않았다**. 그 결과 2026-07-17 현재:

| 레포 | push 스캔 | schedule 스캔(주간·전체 히스토리) | 실제 유출 |
|---|---|---|---|
| controller | ✅ green | ❌ **red — 최초 실행부터**(07-05·07-12) | 없음(오탐 2) |
| backend | ❌ **red**(PR #7 머지 `a7e3a27` 이후) | ❌ red | 없음(오탐 2) |
| crdt-engine | ✅ | ✅ | — |
| frontend | ✅ | ✅ | — |

**왜 여태 못 봤나**: gitleaks-action은 트리거별로 스캔 범위가 다르다 — `push`=마지막 커밋만(`--log-opts=-1`), `schedule`=전체 히스토리. controller는 push만 보면 계속 green이라 **주간 red가 은폐**됐다. 게이트를 배선했지만 "모든 트리거 green"을 확인하지 않은 갭.

### 오탐 4건 판정 (2026-07-17, gitleaks 8.24.3 실측 — CI와 동일 바이너리)

| 레포 | 룰 | 위치 | 추출된 "시크릿" | 판정 |
|---|---|---|---|---|
| controller | `generic-api-key` | `.claude/agents/gitops-reviewer.md:242` | `cGFzc3dvcmQxMjM=` = base64("password123") | 오탐 — **"base64 ≠ 암호화" 교육 예시**(일부러 넣은 가짜) |
| controller | `generic-api-key` | `.claude/skills/service-mesh/istio-core.md:243` | `ztunnel/waypoint` | 오탐 — 산문. `Access Log:`의 `access` 키워드 + 엔트로피 3.58(임계 3.5) 간신히 초과 |
| backend | `private-key` | `JwtKeys.java:60-75` | **Java 소스 코드** | 오탐 — PKCS#8 파서의 `.replace("-----BEGIN PRIVATE KEY-----", "")` 마커 리터럴 |
| backend | `private-key` | `JwtKeysTest.java:61-77` | **Java 소스 코드** | 오탐 — fail-fast 테스트 더미(`"not-a-key"`), 키는 런타임 생성 |

**커밋된 키 자료 0건.** `private-key` 룰 정규식이 `-----BEGIN…PRIVATE KEY-----[\s\S-]{64,}?KEY(?: BLOCK)?-----` 구조라, **마커 리터럴 2개가 64자 이상 떨어져 있으면 그 사이의 Java 코드가 통째로 "키 본문"으로 잡힌다**.

### 근본 원인 — fingerprint 커밋 핀은 squash 머지에서 구조적으로 깨진다

backend는 PR 중 `.gitleaksignore`에 fingerprint를 넣어 green을 만들었다. fingerprint = `<commit>:<path>:<rule>:<line>`인데 **브랜치 커밋 `eadaf38`에 핀** → squash 머지로 main 커밋이 `a7e3a27`이 되며 **엔트리 즉사** → PR green / main red = **게이트 false pass**. 머지마다 사후 fingerprint를 다시 박는 건 지속 불가능. 게다가 `.gitleaksignore`는 공식 문서상 *experimental*.

→ **결론: 오탐 억제는 SHA 비의존(경로/룰/값 기반 `.gitleaks.toml` allowlist)으로 간다.**

### 검증된 결정 (실측 근거 — 추측 아님)

| 결정 | 채택 | 근거 |
|---|---|---|
| 억제 수단 | `.gitleaks.toml` allowlist (**`.gitleaksignore` 폐기**) | SHA 비의존 → squash 머지·후속 커밋에 안 깨짐 |
| 룰 스코프 방법 | `[extend] useDefault=true` + `[[rules]] id=…` + `[[rules.allowlists]]` | **`targetRules`는 8.25.0 신설 — CI는 8.24.3이라 사용 불가**([release notes](https://github.com/gitleaks/gitleaks/releases) 확인). 룰 재선언 시 미지정 속성은 상속(regex/entropy/keywords 보존) — **실측으로 확인** |
| 정밀도 | `condition = "AND"` + `paths` + `regexes` | 경로 통째 허용(blanket) 금지 — 그 파일에 **진짜** 키가 들어오면 반드시 잡혀야 함 |
| backend 판별식 | `-----BEGIN [A-Z ]*PRIVATE KEY-----[^\n]{0,80}"` | 실제 PEM 본문은 개행 뒤 순수 base64 → 매칭 안 됨. Java 리터럴은 마커 직후 `"` 등장 → 매칭. **둘을 구분하는 판별식** |

### 실측 검증 매트릭스 (positive/negative control, 2026-07-17)

CI와 동일한 gitleaks 8.24.3 바이너리로 재현 → 수정 → 대조군 검증까지 완료.

| 대조군 | 기대 | 실측 |
|---|---|---|
| controller 오탐 2건 | 억제 | ✅ no leaks |
| `.claude/` 안의 **진짜** generic key(`api_key:`/`db_password:`) | **발화** | ✅ 발화 — 룰 regex 상속 확인(=룰이 죽지 않음) |
| `.claude/` 안의 stripe 토큰 | **발화** | ✅ 발화 — 타 룰 영향 없음(경로 blanket 아님) |
| 같은 오탐 값이 `.claude/` **밖**에 | **발화** | ✅ 발화 — 경로 스코프 작동 |
| backend 오탐 2건 | 억제 | ✅ no leaks |
| **진짜 RSA 키를 `JwtKeys.java`(허용 경로)에 삽입** | **발화** | ✅ **발화** — 핵심 안전 증명 |
| 진짜 키를 Java 문자열 리터럴로 | **발화** | ✅ 발화 |
| 진짜 `.pem` 파일 | **발화** | ✅ 발화 |

## Blast Radius

| 항목 | 내용 |
|---|---|
| **직접 변경** | controller `.gitleaks.toml`(신규) / backend `.gitleaks.toml`(신규)+`.gitleaksignore`(삭제) |
| **간접 영향** | 4레포 보안 게이트 신호. 오탐 억제 범위를 과도하게 잡으면 **진짜 유출을 놓친다** → 위 대조군으로 방어 |
| **롤백** | controller = git revert. backend = PR revert. 설정 파일 2개뿐이라 즉시 |
| **검증** | 로컬 gitleaks 8.24.3(CI 동일 버전) 재현 → 수정 → 대조군 → 머지 후 실제 CI green 확인 |
| **다운타임** | 없음(CI 설정) |

## 실행 체크리스트

- [x] controller: 이 plan 커밋(planned, `ff01986`)
- [x] controller `.gitleaks.toml` 추가 → 로컬 8.24.3 재현/대조군 green → 커밋·push(`9d62d65`) → **실 CI green 확인**
      — 작업 중 **plan 문서 자신이 `private-key` 오탐 유발**(마커 2회 인용 → 사이의 산문이 "키 본문") → `docs|.claude/*.md` 판별식 엔트리 추가로 해소. 신규 dev-log도 무발화 확인.
- [x] controller `workflow_dispatch` 추가 → **실 CI 실행**: `event type: workflow_dispatch` + `gitleaks cmd`가 schedule과 byte-identical(`--log-opts` 없음 = 전체 히스토리) → **no leaks found**(run `29554972686`)
- [x] backend: 브랜치 `chore/gitleaks-fp-baseline` 분기 → `.gitleaks.toml` 추가 + `.gitleaksignore` 삭제 → 로컬 대조군 green(`b48a153`·`1bd9b30`)
- [x] backend: 사용자 승인 후 push·[PR #8](https://github.com/ressKim-io/weDocs-backend/pull/8) 오픈 → **PR CI 3종 green**(gitleaks/dependency-review/submission)
- [x] 표준 반영: `.claude/rules/secure-coding.md` §게이트 배선 — "자동 스캔 게이트 완료 조건" 6항목 + dev-log [2026-07-17](../dev-logs/2026-07-17-gitleaks-fingerprint-squash-trap.md)
- [x] **PR #8 squash 머지(`2290ce0`) → main CI green** ← **최종 증명 완료**: fingerprint를 죽였던 바로 그 squash 연산에서 allowlist는 살아남았다. push CI green + `workflow_dispatch`(전체 히스토리, schedule과 byte-identical cmd) → **no leaks found**
- [x] 마감: plan done + 1c plan/CLAUDE.md 재개지점 갱신(다음=PR②)

## 결과 (2026-07-17 완료)

**4레포 전 트리거 green.** 실제 유출 0 — 오탐 4건 전부 근거 남기고 억제.

| 레포 | 조치 | 검증 |
|---|---|---|
| controller | `.gitleaks.toml`(`9d62d65`) + `workflow_dispatch` | 실 CI 전체 히스토리 **no leaks**(run `29557073740`) — **최초 실행부터 2주 묵은 red 해소** |
| backend | [PR #8](https://github.com/ressKim-io/weDocs-backend/pull/8) squash 머지 `2290ce0` | main push green + 전체 히스토리 **no leaks**(run `29557159020`) |
| crdt-engine · frontend | 무변경 | 원래 양쪽 green(오탐 없음) — 불필요한 표면 안 늘림 |

> ⚠️ `gh run list`의 `schedule=failure`는 **수정 전 07-12 이력**이다. 다음 실제 cron = 일 20:00 UTC. `workflow_dispatch`가 schedule과 **byte-identical cmd**(`--log-opts` 없는 full scan)로 green이므로 통과 예정.

**부수 성과**: 작업 중 plan 문서 자신이 같은 오탐에 걸려(마커 2회 인용 → 사이 산문이 "키 본문") 판별식 엔트리를 추가 — 이후 작성한 dev-log도 무발화 확인. 이 트랩을 다루는 문서가 앞으로 늘어도 안 깨진다.

**교훈 승격**: `.claude/rules/secure-coding.md` §게이트 배선 — "자동 스캔 게이트 완료 조건" 6항목. 후향 = [dev-log](../dev-logs/2026-07-17-gitleaks-fingerprint-squash-trap.md).

## 검증

```bash
# CI와 동일 버전으로 재현 (8.24.3 — action@v3가 해소하는 버전)
gitleaks detect --redact -v --exit-code=2            # 전체 히스토리 = schedule 등가
gitleaks detect --config=.gitleaks.toml --redact     # 수정 후 no leaks 기대

# 대조군(필수) — 룰이 죽지 않았는지 증명
#  진짜 키를 허용 경로에 심고 발화하는지 확인 후 반드시 제거
```

머지 후 **실제 CI에서 push·schedule 양쪽 green 확인**까지가 완료 조건. 워크플로 파일 존재 ≠ 배선 완료.

## 범위 밖

- engine·frontend 설정 추가(양쪽 다 green — 오탐 없음. 선제 설정은 불필요한 표면)
- push 스캔을 전체 히스토리로 전환(베이스라인 green 이후 검토 — 별건)
- gitleaks 8.25+ 업그레이드 후 `targetRules`로 단순화(현 action@v3 해소 버전에 종속 — 별건)
- 오탐 유발 문서/코드 자체를 스캐너에 맞춰 수정(스캐너 때문에 프로덕션 코드·문서를 비트는 것은 반려 — `clean-code.md`)

## 재개 지점 (Resume)

> **마지막 완료**: **이 plan 전 단계 done**(2026-07-17). 4레포 전 트리거 green — controller `9d62d65`·backend squash 머지 `2290ce0` 양쪽 다 실 CI 전체 히스토리 스캔 **no leaks** 확인. 표준(`secure-coding.md` 6항목)·dev-log 반영 완료.
> **다음**: **M2 Phase 1c PR② 착수** — `feature/m2-doc-service-rest-pages` 분기(가드/도메인 행위→workspace→page tree/move→sharing). 설계 확정본 = [1c plan §PR②](2026-07-12-m2-phase1c-rest-jwt.md).
> **주의**: `targetRules` 금지(8.25+ 전용, CI는 8.24.3 — `gitleaks version:` 로그로 확인). 경로 blanket 금지 — 반드시 `condition="AND"`로 값/모양까지 좁힌다. 신규 억제 엔트리는 **대조군(허용 경로에 진짜 키 삽입 → 발화)으로 룰 생존 증명 필수** — 억제와 무력화는 겉으로 똑같이 "no leaks found"다. backend는 건별 승인.
