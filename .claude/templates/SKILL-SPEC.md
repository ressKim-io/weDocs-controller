# Skill 작성 표준 — SKILL-SPEC

이 레포의 모든 `.claude/skills/**/*.md` 가 따라야 할 frontmatter / 본문 / trigger 표준.
신규 skill 추가 시 본 spec 을 그대로 카피해 사용.

> **출처 (F1)**: https://code.claude.com/docs/en/skills (검증일 2026-05-15)
>
> 핵심: `description` 필드는 Claude Code 의 auto-invocation primary signal. 누락 시 skill 이 발견되지 않음.

---

## 1. 필수 Frontmatter

```yaml
---
name: skill-slug                                # kebab-case, 파일명과 동일
description: "[What it does in 1 sentence]. Use when the user asks [trigger phrases]."
effort: xhigh                                   # low | medium | xhigh | max — effort-guide.md 매핑
deprecated: false                               # 폐지 시 true + replaced_by 명시
---
```

### 필드 정의

| 필드 | 필수 | 길이 | 설명 |
|---|---|---|---|
| `name` | ✅ | ≤50 자 | kebab-case, 파일명 (확장자 제외) 과 동일. 슬래시 `category:name` 또는 폴더 매핑 |
| `description` | ✅ | 50-300 자 | F1 패턴 — `What. Use when X.` 형식. description + when_to_use 합산 1536 자 한도 |
| `effort` | 선택 | enum | 카테고리 default (`effort-guide.md`) 와 다른 경우만 명시. default 면 생략 가능 |
| `deprecated` | 선택 | bool | 폐지 시 `true` + `replaced_by:` 메타 |
| `replaced_by` | 조건부 | string | `deprecated: true` 일 때 필수 — 대체 skill 의 name |

### description 패턴 (의무)

✅ **Good**:
```
description: "Go 백엔드 LLM 통합 패턴, 프레임워크 선택 (Genkit/LangChainGo/Eino), Tool Calling, RAG. Use when Go 프로젝트에 AI 기능을 도입하거나 LLM 통합 패턴을 선택할 때."
```

❌ **Bad** (현재 273 중 ~227 의 패턴):
```
# Go AI Integration Patterns
```
(frontmatter 없음 — auto-discovery 불가)

---

## 2. 본문 구조 표준

### 권장 줄 수: 250-400 줄

> **이유**: `/compact` 후 skill content 는 첫 **5000 tokens/skill** 만 잔존, 25KB 총합 한도 (F1). 400 줄 초과 시 본문 후반이 compact 시 잘림.

| 길이 | 평가 |
|---|---|
| <100 줄 | 너무 짧음 — 단일 lookup 외 부적합 |
| 100-250 줄 | OK |
| **250-400 줄** | **Sweet spot** |
| 400-600 줄 | 압축 후보 — 본문에 `## 압축 후보` 마킹 |
| >600 줄 | 분할 / 압축 필수 |

### 표준 섹션 순서

```markdown
# Skill Title (한 줄)

[Skill 의 도메인 / 의도 1-2 문장]

## Quick Reference (결정 트리)

[ASCII 결정 트리 — "이 상황이면 이걸 써라"]

## [도메인 패턴 1]
## [도메인 패턴 2]
...

## Anti-Patterns

[해당 도메인의 안티패턴 3-5 개]

## Verification Criteria

[이 skill 을 적용한 결과의 성공 기준 — F7 "highest-leverage thing"]

## 참조 스킬

- `[[other-skill-name]]` — 한 줄 관계
- ...

## Sources / Verified

- [출처 1 URL] — 검증일 YYYY-MM-DD
- ...
```

---

## 3. Verification Criteria 섹션 (필수, F7)

Anthropic 공식: "providing verification criteria is the single highest-leverage thing you can do."

```markdown
## Verification Criteria

이 skill 을 적용한 결과가 다음 조건을 만족해야 한다:

1. **[기능 검증]** — [구체 테스트 / 산출물]
   예: 작성된 Go 함수가 `go test ./...` 통과
2. **[성능 / 안전성]** — [정량 기준]
   예: p95 latency 100ms 이하 또는 OWASP Top 10 위반 없음
3. **[일관성]** — [다른 skill / rule 과의 정합]
   예: clean-code.md §메서드 길이 (<50 줄) 준수
```

---

## 4. Deprecated 처리

폐지된 skill 은 삭제 대신 frontmatter 갱신:

```yaml
---
name: old-skill
description: "[기존 내용]. **DEPRECATED**: replaced by [[new-skill]]."
deprecated: true
replaced_by: new-skill
---

# [기존 제목] — DEPRECATED

> **이 skill 은 폐지되었습니다.** 대신 [[new-skill]] 을 사용하세요.
> 폐지일: YYYY-MM-DD / 사유: [한 줄]

[기존 내용 유지 — 점진 마이그레이션을 위해]
```

---

## 5. 검증 스크립트

```bash
# 전체 skill frontmatter 검증
scripts/validate-skill-frontmatter.sh

# 특정 skill 만
scripts/validate-skill-frontmatter.sh .claude/skills/go/effective-go.md
```

검증 항목:
- frontmatter 존재
- `name` 필드 + 파일명 일치
- `description` 존재 + 50-300 자 + "Use when" 패턴
- `effort` 가 enum (`low|medium|xhigh|max` 또는 미명시)
- `deprecated: true` 일 때 `replaced_by` 존재

---

## 6. Cross-link 패턴

다른 skill 참조 시 `[[skill-name]]` 사용 — 향후 dependency graph 빌드 자동화 대비.

```markdown
## 참조 스킬
- [[effective-go]] — Go idiom 결정 트리
- [[go-ai]] — LLM 통합 시 본 skill 의 패턴 적용
```

---

## 7. 예시 (완전한 skill)

```markdown
---
name: example-skill
description: "예시 도메인의 패턴 가이드. Use when 예시 작업을 수행하거나 패턴 결정이 필요할 때."
effort: xhigh
deprecated: false
---

# Example Skill

예시 도메인의 패턴 결정 가이드.

## Quick Reference

\`\`\`
상황 A → 패턴 X
상황 B → 패턴 Y
\`\`\`

## 패턴 X
...

## Anti-Patterns
...

## Verification Criteria
1. ...

## 참조 스킬
- [[other-skill]] — 관계

## Sources
- [URL] — 2026-05-15
```

---

## 관련 문서

- Effort 매핑: [`../rules/effort-guide.md`](../rules/effort-guide.md)
- Agent spec: [`AGENT-SPEC.md`](AGENT-SPEC.md)
- Token / context 룰: [`../rules/token-budget.md`](../rules/token-budget.md)
- 검증 의무: [`../rules/deep-thinking.md`](../rules/deep-thinking.md)
