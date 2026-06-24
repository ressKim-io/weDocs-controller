---
paths:
  - "**/dev-logs/**"
  - "**/docs/dev-logs/**"
  - "**/2026-*-*.md"
  - "**/2027-*-*.md"
---

# dev-logs Lifecycle Rules

dev-logs (`docs/dev-logs/*.md`) 작성·갱신·정리 시 반드시 따라야 할 4-Tier 정책 + frontmatter 표준.
근거: `docs/dev-logs/2026-04-29-devlog-tier-policy.md` (SDD).

---

## 4-Tier 정책

| Tier | 이름 | 조건 | 위치 | 검색 우선순위 |
|------|------|------|------|---------------|
| **1** | Active | `status: open` OR active 메모리/카드와 연결 | `docs/dev-logs/` | 최상위 (`/where`, `/related`) |
| **2** | Reference | `status: resolved` + (`importance: critical\|major` OR ADR/카드/메모리에서 인용) | `docs/dev-logs/` | 2순위 |
| **3** | Historical | `status: resolved` + 60일+ 미참조 + `importance: minor` | `docs/dev-logs/` | grep으로만 발견 |
| **4** | Superseded | `status: superseded` + `replaced_by` 명시 | `docs/dev-logs/_archive/` | 인덱스 제거, forward link만 보존 |

### Tier 산출 우선순위

1. `status: superseded` → **Tier 4** (다른 조건 무관)
2. `status: open` → **Tier 1**
3. `status: resolved` + `importance: critical|major` → **Tier 2**
4. `status: resolved` + 인용됨(ADR/repo-card/memory) → **Tier 2**
5. `status: resolved` + 60일+ 미참조 + `importance: minor` → **Tier 3**
6. 그 외 `resolved` → **Tier 2** (보수적 보존)

---

## Frontmatter 표준 (MANDATORY)

신규 dev-log 작성 시 반드시 아래 frontmatter를 포함한다. 기존 dev-logs는 점진 backfill (수정 시 보강).

```yaml
---
date: YYYY-MM-DD
category: troubleshoot | decision | migration | meta
tier: 1 | 2 | 3 | 4
importance: critical | major | minor
status: open | resolved | superseded
tags: [tag1, tag2]
related:
  - dev-logs/YYYY-MM-DD-...md
  - adr/NNNN-...md
  - memory/...md
replaced_by: dev-logs/YYYY-MM-DD-...md   # superseded 만
---
```

### 필수 필드

- `date`: 파일명 날짜와 일치 (YYYY-MM-DD ISO 8601)
- `category`: 4종 (troubleshoot/decision/migration/meta)
- `tier`: 작성 시점 산출값. 자동 산출은 `/consolidate-devlogs` 사용
- `importance`: 영향도 (critical: 프로덕션 장애·아키텍처 결정 / major: 의미 있는 패턴·교훈 / minor: 단순 작업 기록)
- `status`: open(진행 중) / resolved(완료) / superseded(대체됨)

### 선택 필드

- `tags`: 검색용 키워드. `/where`, `/related`에서 매칭 우선순위 +5점
- `related`: 다른 dev-log/ADR/메모리 forward link
- `replaced_by`: `status: superseded` 일 때만 필수

---

## category 가이드

| category | 의미 | 예시 |
|----------|------|------|
| `troubleshoot` | 장애·버그 디버깅 기록 | CrashLoopBackOff, DB connection timeout |
| `decision` | 기술/아키텍처 결정 (ADR보다 가벼움) | Tier 정책, 도구 선택 |
| `migration` | 환경/버전/아키텍처 전환 | AWS→GCP, K8s 1.33→1.34 |
| `meta` | AI 워크플로우·rules·commands 변경 | rule 추가, skill 보강 |

---

## importance 가이드

| importance | 기준 | 보존 |
|------------|------|------|
| `critical` | 프로덕션 장애 / 시스템 핵심 결정 / 비용 영향 큰 사고 | 영구 (Tier 2 이상) |
| `major` | 의미 있는 교훈 / 재발 가능 패턴 / ADR 후보 | 영구 (Tier 2 이상) |
| `minor` | 단순 작업 기록 / 일회성 트러블 / 컨텍스트 메모 | 60일+ 미참조 시 Tier 3 |

---

## 작성 시점 트리거 (MANDATORY)

dev-log 작성이 의무인 상황:

- 30분 이상 디버깅한 트러블 → `category: troubleshoot`
- A vs B 선택 (ADR 수준 아닌) → `category: decision`
- 환경 전환 / 마이그레이션 완료 → `category: migration`
- rules/skills/commands/agents 추가·변경 → `category: meta`

각 트리거의 상세 양식:
- `/log-trouble`, `/log-decision`, `/log-meta` 슬래시 커맨드 사용

---

## 갱신·archive 규칙

### Tier 1 → Tier 2 (resolved 시점)

진행 중 dev-log가 완료되면:
1. frontmatter `status: open` → `resolved`
2. tier 재산출 (대부분 1 → 2)
3. 후속 학습 / 결과 섹션 추가

### Tier 2 → ADR/skill 승격

같은 주제 dev-log 3건+ 누적 시 패턴 정착 신호. **`/promote-devlog <slug>`** 사용:
- ADR 생성 (decision 패턴) 또는 skill 보강 (반복 절차)
- 원본 dev-logs는 `replaced_by: adr/NNNN-...md` 메타 추가

### Tier 4 archive

대체 결정이 명확한 경우:
1. `status: superseded` + `replaced_by: dev-logs/...` 또는 `adr/...`
2. **`/archive-devlog <slug>`** 사용 → `_archive/` 이동
3. forward link는 신규 자료에 보존, INDEX 제거

---

## 절대 금지

| 금지 행위 | 이유 |
|---|---|
| frontmatter 없이 신규 dev-log 작성 | tier 자동 산출 불가 |
| Tier 4 파일을 단순 삭제 | forward link 끊김, 추적 불가 |
| `status: superseded` 인데 `replaced_by` 누락 | 대체 자료 추적 불가 |
| `importance` 자체 판단 없이 디폴트 `major` 남발 | Tier 정책 무력화 |
| 자동 일괄 archive (사용자 승인 없이) | 영구 자료 손실 위험 |

---

## 자동화 커맨드

| 커맨드 | 효과 | 빈도 |
|--------|------|------|
| `/consolidate-devlogs` | frontmatter 기반 tier 자동 산출, 클러스터 발견, superseded 식별 (dry-run) | 주 1회 |
| `/promote-devlog <slug>` | Tier 2 → ADR/skill 승격 (semantic 정착) | 패턴 발견 시 |
| `/archive-devlog <slug>` | Tier 4 이동, replaced_by 링크 보존 | superseded 발견 시 |

---

## 학계 근거 (요약)

- **FadeMem (LML/SML)**: Tier 1+2 (보존) / Tier 3+4 (빠른 demote) 매핑
- **Importance Score**: frontmatter `importance` 필드와 동형
- **Sleep-time computation**: `/consolidate-devlogs` 패턴
- **Episodic → Semantic**: `/promote-devlog` (dev-log → ADR/skill)
- **OS memory hierarchy**: Tier 1 (RAM) / Tier 2-3 (disk) / Tier 4 (cold storage)

상세: `docs/dev-logs/2026-04-29-devlog-tier-policy.md` 끝 섹션.
