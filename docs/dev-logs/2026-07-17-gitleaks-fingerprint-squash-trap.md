---
date: 2026-07-17
category: troubleshoot
tier: 2
importance: major
status: resolved
tags: [gitleaks, security-scan, ci, squash-merge, false-positive, gate-activation]
related:
  - plans/2026-07-17-gitleaks-false-positive-baseline.md
  - plans/2026-07-03-security-quality-standards.md
  - dev-logs/2026-07-03-craft-standards-v2-security-quality.md
  - plans/2026-07-12-m2-phase1c-rest-jwt.md
---

# gitleaks — fingerprint 커밋 핀이 squash 머지에 죽는다 + push green이 schedule red를 은폐한다

**한 줄**: 보안 스캔 게이트를 2026-07-03에 배선했지만 **오탐 베이스라인을 한 번도 green으로 만들지 않았다**. 그 결과 controller는 주간 스캔이 **최초 실행부터 red**였고(2주간 미발견), backend는 **머지 직후 red**가 됐다. 실제 유출은 0건 — 전부 오탐.

## 증상

| 레포 | push 스캔 | schedule 스캔(주간·전체 히스토리) |
|---|---|---|
| controller | ✅ green | ❌ **red — 최초 실행부터**(07-05·07-12) |
| backend | ❌ **red**(PR #7 머지 `a7e3a27` 이후) | ❌ red |
| crdt-engine · frontend | ✅ | ✅ |

## 근본 원인 2개

### ① fingerprint 커밋 핀 ↔ squash 머지 (backend)

gitleaks fingerprint는 **`<commit>:<path>:<rule>:<line>`** 구조다. PR #7은 오탐을 억제하려고 `.gitleaksignore`에 **브랜치 커밋 `eadaf38`로 핀**했다 → PR CI green → **squash 머지로 main 커밋이 `a7e3a27`이 되며 엔트리 즉사** → main red.

```
PR 브랜치: eadaf38:…/JwtKeysTest.java:private-key:61   ← 이 SHA로 핀
squash 머지 → main:  a7e3a27                            ← SHA 재작성 = 엔트리 무효
```

**= 게이트가 false pass를 준 것.** PR에서 green을 보고 머지했는데 main이 red. 머지마다 사후 fingerprint를 다시 박는 건 지속 불가능하고, `.gitleaksignore`는 공식 문서상 *experimental*. **커밋 SHA 핀은 squash 머지 레포에서 구조적으로 깨진다.**

### ② 트리거별 스캔 범위 차이 (controller)

gitleaks-action은 이벤트로 스캔 범위를 정한다 — 실행 로그의 `gitleaks cmd:` 줄로 확인:

```
event type: push              → gitleaks detect … --log-opts=-1   ← 마지막 커밋만
event type: schedule          → gitleaks detect …                 ← 전체 히스토리
event type: workflow_dispatch → gitleaks detect …                 ← 전체 히스토리(schedule 등가)
```

controller의 오탐은 **2026-06-25 커밋(`5ce132c`)**에 묻혀 있었다. push 스캔은 마지막 커밋만 보니 **영원히 green** → 주간 red를 아무도 안 봄. **push green ≠ 게이트 green.**

## 오탐 4건 판정 (실제 유출 0)

| 레포 | 룰 | 위치 | 추출된 "시크릿" | 실체 |
|---|---|---|---|---|
| controller | `generic-api-key` | `gitops-reviewer.md:242` | `cGFzc3dvcmQxMjM=` | base64("password123") — **"base64 ≠ 암호화" 교육 예시**(일부러 넣은 가짜) |
| controller | `generic-api-key` | `istio-core.md:243` | `ztunnel/waypoint` | 산문. `Access Log:`의 `access` 키워드 + 엔트로피 3.58(임계 3.5) 간신히 초과 |
| backend | `private-key` | `JwtKeys.java:60-75` | **Java 소스 코드** | PKCS#8 파서의 `.replace("-----BEGIN PRIVATE KEY-----", "")` |
| backend | `private-key` | `JwtKeysTest.java:61-77` | **Java 소스 코드** | fail-fast 더미(`"not-a-key"`), 키는 런타임 생성 |

**`private-key` 룰의 구조를 알아야 이해된다**: 정규식이 `-----BEGIN…PRIVATE KEY-----` + **64자 이상** + `KEY-----`다. 즉 **마커 리터럴 2개가 64자 이상 떨어져 있으면 그 사이의 코드/산문이 통째로 "키 본문"으로 잡힌다.**

> 🔁 이 트랩을 설명하는 **plan 문서 자신이 같은 이유로 걸렸다** — 표에 마커를 두 번 인용했더니 사이의 한국어 산문이 "키 본문"이 됐다. 룰의 작동 방식을 문서로 옮기는 순간 재현된 셈.

## 해결

**fingerprint → `.gitleaks.toml` allowlist(SHA 비의존)**. 커밋 SHA에 의존하지 않으니 squash·후속 커밋에 안 깨진다.

핵심 제약 3가지:

1. **`targetRules` 사용 불가** — allowlist를 룰에 스코프하는 이 필드는 **8.25.0 신설**인데 CI(`action@v3`)가 해소하는 건 **8.24.3**. → `[extend] useDefault=true` + `[[rules]] id=…` 재선언으로 스코프(미지정 속성 regex/entropy/keywords는 기본 룰에서 상속 — 실측 확인).
2. **경로 blanket 금지** — `condition="AND"`로 경로 + 값/모양까지 좁힌다. `JwtKeys.java`는 **오히려 진짜 키가 붙을 위험이 가장 큰 파일**이라 통째 허용은 금물.
3. **판별식으로 진짜/가짜를 가른다** — 실제 PEM 본문은 개행 뒤 **순수 base64**라 `"`·백틱·표 파이프가 올 수 없다:
   - backend: `-----BEGIN [A-Z ]*PRIVATE KEY-----[^\n]{0,80}"` (마커 직후 80자 내 `"` = 자바 리터럴)
   - controller: `-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]{0,200}?[`|]` (마커 직후 200자 내 백틱/파이프 = 문서 산문)

부수 조치: **`workflow_dispatch` 추가** — 전체 히스토리 스캔을 주 1회 기다리지 않고 즉시 검증.

## 검증 — 대조군이 핵심

"no leaks found"는 **룰을 죽여도 나온다**. 억제가 룰 자체를 무력화하지 않았음을 증명해야 한다. CI와 **동일 바이너리(8.24.3)**로 재현 → 수정 → 대조군:

| 대조군 | 기대 | 실측 |
|---|---|---|
| 오탐 4건 | 억제 | ✅ no leaks |
| **진짜 RSA 키를 `JwtKeys.java`(허용 경로)에 삽입** | **발화** | ✅ **발화** ← 핵심 안전 증명 |
| 진짜 키를 `docs/*.md` 펜스 블록에 | **발화** | ✅ 발화 |
| 진짜 `.pem` · 자바 리터럴 내 키 | **발화** | ✅ 발화 |
| `.claude/` 안의 진짜 generic key(`api_key:`/`db_password:`) | **발화** | ✅ 발화 — 룰 regex 상속 확인 |
| `.claude/` 안의 stripe 토큰 | **발화** | ✅ 발화 — 타 룰 영향 없음 |
| 같은 오탐 값이 허용 경로 **밖**에 | **발화** | ✅ 발화 — 경로 스코프 작동 |

**실 CI 확인**: controller `workflow_dispatch` 실행 → `gitleaks cmd`가 schedule과 **byte-identical**(`--log-opts` 없음) → **no leaks found**. 로컬 주장이 아니라 실제 러너에서 증명.

## 패턴 전수 스캔 (`workflow.md` SOP)

4레포 전부 확인 — engine·frontend는 push·schedule 양쪽 green(오탐 없음)이라 **설정 추가 안 함**(불필요한 표면). 선제 배포보다 "오탐이 실제로 난 곳만, 근거를 남기고" 억제.

## 교훈

- **게이트 배선의 완료 조건은 "워크플로 파일 존재"가 아니라 "모든 트리거가 green"이다.** red가 상시화되면 신호가 죽어 진짜 유출을 덮는다 — 배선 안 한 것보다 나쁘다.
- **push green ≠ 게이트 green.** 트리거마다 스캔 범위가 다르다는 걸 모르면 red가 은폐된다.
- **오탐 억제를 커밋 SHA에 핀하지 않는다.** squash 머지가 SHA를 재작성한다.
- **억제 후에는 대조군으로 "룰이 살아있음"을 증명한다.** 억제와 무력화는 겉으로 똑같이 "no leaks found"다.
- **버전 종속 기능을 추측하지 않는다** — `targetRules`(8.25.0)를 CI 버전(8.24.3)에 썼다면 조용히 오작동했다. `gitleaks version:` 로그로 확인 후 설계.

→ 표준 반영: `.claude/rules/secure-coding.md` §게이트 배선 — "자동 스캔 게이트 완료 조건" 6항목 추가.

## 산출

- controller `9d62d65`(allowlist) · `.github/workflows/security-scan.yml`(workflow_dispatch) — main 직접
- backend [PR #8](https://github.com/ressKim-io/weDocs-backend/pull/8) — `.gitleaks.toml` 신설 + `.gitleaksignore` 삭제 + workflow_dispatch. **머지 후 main green 확인 = squash에도 안 깨진다는 최종 증명**
