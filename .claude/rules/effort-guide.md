# Effort Level Guide — Claude 5 / Opus 4.8 세대 기준

이 레포의 21 agents / 198 skills 가 어떤 effort level 로 호출되어야 하는지의 카테고리별 매핑 표.
사용자가 새 작업 / 새 agent / 새 skill 을 작성할 때 "이거 effort 뭘 줘야 하지?" 의 답.

상세 룰(캐시·tokenizer·adaptive thinking)은 [`token-budget.md`](token-budget.md) 참조. 이 문서는 매핑에 집중.

> **출처**: [effort](https://platform.claude.com/docs/en/docs/build-with-claude/effort) · [models overview](https://platform.claude.com/docs/en/docs/about-claude/models/overview) (✅ verified 2026-07-17, WebFetch)

---

## 단계 정의 (Anthropic 공식, 2026-07-17)

| 레벨 | 정의 | 권장 사용 상황 |
|---|---|---|
| `low` | 최소 토큰, 속도·비용 우선 | 단순 조회 / 분류 / subagent 대량 fan-out / latency 민감 |
| `medium` | 균형 — 중간 절약 | 평균 워크플로우의 비용 절감 스텝다운 |
| `high` | **API·Claude Code 기본값** (파라미터 생략과 동일) | 복잡 추론 · 일반 코딩 · agentic 최소 기준 |
| `xhigh` | 장기 agentic/코딩 확장 (30분+ · 수백만 토큰 급) | **Opus 4.8 코딩/agentic 권장 시작점** · 반복 탐색 |
| `max` | 상한 없음 | frontier 문제만 — 비용 대비 품질 이득 작고 overthinking 위험 |

> 구버전 가이드의 레벨별 비용 %(~25%/~50%/~200% 등)는 공식 문서가 더 이상 제공하지 않음 → 수치 삭제(정성 서술만). "max는 상당한 비용 추가 대비 품질 이득이 작다"는 정성 가이드는 유지됨.

**모델별 지원 (2026-07-17)**:
- effort 파라미터 지원: Fable 5 · Opus 4.8 / 4.7 / 4.6 / 4.5 · Sonnet 5 / 4.6 (+Mythos 계열)
- **Haiku 4.5 는 effort 미지원** (구 가이드의 "Haiku 4.5: low~max" 는 폐기)
- `xhigh` 지원: Fable 5 · Opus 4.8 / 4.7 · Sonnet 5
- `max` 지원: 위 + Opus 4.6 · Sonnet 4.6

**기본값 — 구버전 가이드와 달라진 것**:
- **모든 surface 기본 = `high`** (API·Claude Code·claude.ai). "Claude Code 코딩 기본 xhigh" 는 Opus 4.7 시절 정보 — 폐기. 코딩/agentic 에서 xhigh 를 원하면 **명시 지정**.
- Opus 4.8: 코딩/agentic 은 xhigh 로 시작 권장(4.7 가이드 승계), 그 외 지능 민감 작업은 high.
- Fable 5: **high(기본)로 시작** — 낮은 effort 로도 이전 세대 xhigh 이상인 경우가 많음. capability-critical 만 xhigh.
- Sonnet 5: 기본 high. 스텝다운 medium ≈ Sonnet 4.6 high 수준.
- Claude Code "ultracode" = `xhigh` + 멀티에이전트 상시 허용 — 별도 API 레벨 아님.

## 모델 라인업 (2026-07-17)

| 모델 | API ID | 가격 (in/out MTok) | ctx | 비고 |
|---|---|---|---|---|
| Fable 5 | `claude-fable-5` | $10 / $50 | 1M | 최상위 · adaptive thinking 상시 on |
| Opus 4.8 | `claude-opus-4-8` | $5 / $25 | 1M | 복잡 agentic 코딩 기본 추천 |
| Sonnet 5 | `claude-sonnet-5` | $3 / $15 (~2026-08-31 인트로 $2/$10) | 1M | 속도·지능 균형 |
| Haiku 4.5 | `claude-haiku-4-5-20251001` | $1 / $5 | 200k | 최속 · effort 미지원 |

(Opus 4.1 은 deprecated — 2026-08-05 retire. Opus 4.7/4.6·Sonnet 4.6/4.5 = legacy.)

---

## Agents 매핑 (이 레포 21개)

| Effort | 대상 (model) | 정당화 |
|---|---|---|
| `low` | git-workflow (haiku — frontmatter 명시) | 커밋 메시지 / 단순 자동화 — 깊은 추론 불필요 |
| 기본(`high`) | sonnet 16개 — code-reviewer / java-expert / python-expert / cicd·dockerfile·gitops·k8s·observability-reviewer / database·messaging·otel·redis-expert / k8s-troubleshooter / platform-engineer / saga-agent / service-mesh-expert | 게이트 체크리스트 실행·단일 도메인 리뷰 — sonnet + 기본 effort 로 충분 |
| `max` | rust-expert / architect-agent / tech-lead / debugging-expert (opus — frontmatter 명시) | CRDT 정확성 · cascade · 아키텍처 트레이드오프 — frontier 추론 |

**Outlier note**: opus 4개 + haiku 1개만 frontmatter 에 `effort:` 명시. 나머지 16개는 기본(`high`). Claude Code 는 frontmatter 의 `effort` 필드를 직접 읽지 않으므로 본 표가 사람/스크립트/agent prompt 의 SOT.

## 모델 티어링 판단 기록 (2026-07-17)

- **리뷰·언어 expert = sonnet 유지.** 근거: 크래프트 게이트는 자유 리뷰가 아니라 **[B]/[A] 기계적 체크리스트 실행** — sonnet + 체크리스트로 일관성 충분("리뷰는 sonnet" 현업 패턴 정합). frontier 판단(cascade·트레이드오프·난해 디버깅)은 opus+max 에이전트(architect-agent / tech-lead / debugging-expert)로 에스컬레이션.
- **☕/🦀 게이트 비대칭 유지** (java-expert=sonnet vs rust-expert=opus/max): rust 는 CRDT 수렴 정확성이 걸린 엔진 코어라 상향 정당. Java 게이트에서 체크리스트 miss 가 반복 관측되면 재판단.

---

## Skills 매핑 (198개, 카테고리 default)

| Effort | 카테고리 | 정당화 |
|---|---|---|
| `low` | `dx/` 단순 템플릿류 (changelog·commit) / 단순 lookup | template 적용 / 산식 조회 — 추론 불필요 |
| 기본(`high`) | `rust/` / `spring/` / `kubernetes/` / `architecture/` 대다수 / `security/` / `cicd/` / `observability/` 등 | 일반 코딩 / 패턴 적용 / 설계 |
| `max` | `architecture/` 중 cascade·blast radius 큰 것 / `msa/` 분산 트랜잭션류 | 트레이드오프 cascade |

**예외**: `medium` skill 은 없음 — 카테고리 default 또는 invoker 의 명시 override 로 충분.

---

## 적용 방법

### 1. Agent / Skill 호출 시
- 본 매핑 표 default 사용 — 명시 없으면 기본(`high`)
- 사용자가 override 명시한 경우 (예: "low effort 로 빠르게 훑어줘") 그대로 적용
- Outlier agent (opus 4 + haiku 1) 는 frontmatter 의 `effort:` 우선

### 2. 새 agent / skill 추가 시
- 본 표의 카테고리에 매핑되면 해당 effort 사용 — frontmatter `effort:` 명시는 outlier 만
- 새 카테고리면 본 표에 한 줄 추가 (작성자가 책임)
- 기준 모호 시 기본(`high`) — 상향은 근거가 생길 때

### 3. 작업 복잡도별 직접 호출 (slash command / agent prompt)

```
단순 lookup / 1-2 파일 조회 / fan-out subagent   → low
평균 워크플로우 비용 절감 스텝다운               → medium
일반 코딩 / 단일 도메인 expert / review          → high    ← 기본
장기 agentic / 반복 탐색 / 고난도 코딩           → xhigh   (명시 지정)
cascade / cross-service / frontier 트레이드오프  → max     (드물게)
```

### 4. Subagent spawn 시
- token-budget.md §"Subagent 를 Context 절약 도구로" 참조
- **subagent 의 effort 는 main agent 와 독립** — 가벼운 fan-out 은 `low`, 깊은 분석은 `xhigh`/`max`
- 10+ 파일 탐색만 fan-out 으로 (단일 함수 리팩토링에 subagent 금지)

---

## Decision Tree

```
이 작업이 단순 조회 / template 적용 / 산식 인가?
├── YES ──────────────────────────────────────────→ low
└── NO
    │
    비용 절감이 품질보다 중요한 평균 워크플로우인가?
    ├── YES ──────────────────────────────────────→ medium
    └── NO
        │
        이 작업이 cross-service / cascade / frontier 트레이드오프인가?
        ├── YES ──────────────────────────────────→ max
        └── NO
            │
            30분+ 장기 agentic / 반복 탐색 / 고난도 코딩인가?
            ├── YES ──────────────────────────────→ xhigh  (명시 지정)
            └── NO (일반 코딩 / 단일 도메인 / review) → high   ← 기본
```

---

## 자기 점검 (작업 시작 전)

- [ ] 이 작업의 **blast radius** 가 큰가? (큼 → xhigh/max 상향)
- [ ] **단순 lookup** 인데 기본 effort 쓰고 있나? (low 로 하향)
- [ ] **subagent 에 max** 주고 있나? (대부분 low 로 충분, fan-out 합산 비용 고려)
- [ ] **effort 미지원 모델(Haiku 4.5)** 에 effort 요구하나? (model + effort 정합성)

---

## 참고 / cross-link

- Tokenizer / Prompt Cache / Adaptive thinking 상세: [`token-budget.md`](token-budget.md)
- Subagent spawn 가이드: [`token-budget.md`](token-budget.md) §"Subagent 를 Context 절약 도구로"
- 공식 출처: effort · models overview (✅ 2026-07-17 WebFetch, 상단 링크)
