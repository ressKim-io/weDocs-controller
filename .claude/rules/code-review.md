---
paths:
  - "**/.github/**"
  - "**/review*"
  - "**/docs/review*"
---

# Code Review Rules

PR 코드 리뷰 시 반드시 이 양식과 프로세스를 따른다.

---

## PR 루틴 (고정)

```
1. 브랜치 생성 + 파일 스테이징
2. 사용자 커밋/푸시
3. Claude가 PR 생성
4. Claude가 자동으로 /review-pr 실행 → 멀티 관점 코드 리뷰 → PR 코멘트 (직접 수정 X)
   ⚠️ 사용자가 요청하지 않아도 PR 생성 직후 반드시 실행한다
5. Gemini 리뷰 확인 (같이)
6. 리뷰 갭 기록 (MANDATORY) — Gemini가 잡고 Claude가 놓친 항목을 docs/review-gaps.md에 기록
7. 양쪽 피드백 기반으로 코드 수정
8. 사용자 커밋/푸시
9. 머지 → 다음 PR
```

**절대 금지**: 리뷰 후 바로 코드 수정하지 않는다. 반드시 코멘트만 남기고 사용자 판단을 기다린다.

---

## 멀티 관점 리뷰 (Multi-Perspective Review)

`/review-pr` 커맨드로 5개 관점의 에이전트를 **병렬 실행**하여 종합한다.

| 관점 | 태그 | 핵심 체크 |
|------|------|----------|
| 보안/권한 | 🔒 | securityContext, 시크릿 노출, RBAC, image tag 고정, TLS |
| 운영/성능 | ⚙️ | resource limits, health probe, 서비스 연동, 데이터 영속성 |
| 패턴/일관성 | 📐 | values↔template 정합성, DRY, 네이밍 컨벤션, deprecated API |
| Rust 크래프트 | 🦀 | `rust-expert` 실행 — `error-handling.md` 체크리스트(thiserror·no-unwrap·에러체인·경계매핑) |
| Java 크래프트 | ☕ | `java-expert` 실행 — `error-handling.md` 체크리스트(ControllerAdvice·ProblemDetail·Lombok) |

### 종합 규칙
- 중복 제거: 같은 파일/라인의 동일 이슈는 병합
- severity 상향: 2개 이상 관점에서 동시 지적 시 검토
- 코멘트 헤더: `## Code Review - Claude Code (Multi-Perspective)`

---

## 리뷰 갭 추적 (MANDATORY)

Gemini가 발견했지만 Claude가 놓친 항목은 **반드시** `docs/review-gaps.md`에 기록한다.

### 기록 시점
- 매 PR에서 양쪽 리뷰 결과 비교 후 즉시 기록

### 기록 형식
```markdown
### [PR #번호] 제목
**N. 이슈 요약**
- **카테고리**: (보안 | 일관성 | 성능 | 패턴 | 네이밍 | 기타)
- **Gemini 지적**: 요약
- **원인 분석**: Claude가 왜 놓쳤는지 추정
- **개선 방향**: 리뷰 룰/프롬프트에 어떤 체크를 추가해야 하는지
```

### 목적
- 누적 데이터 분석 → Claude Code 리뷰 agent/skill 개선
- 패턴 반복 시 리뷰 프롬프트 또는 룰에 체크 항목 추가

---

## 리뷰 본문 한국어 작성 (MANDATORY)

PR 코멘트, 리뷰 본문, 갭 기록 모두 **한국어**로 작성한다.

- 기술 용어/식별자는 원문 유지 (`p99`, `HikariCP`, `NetworkPolicy`, `kubectl`)
- 코드 스니펫, 변수명, 명령어는 영어 그대로
- 설명 문장, 권장 사항, 트레이드오프 분석은 한국어
- 표/체크리스트의 헤더와 항목 텍스트는 한국어

이유: 리뷰의 1차 독자는 한국어 사용자(본인+팀)이며, 영어 본문은 자동 번역 단계를 거치며 미묘한 뉘앙스 손실이 발생한다.

---

## 자주 놓치는 패턴 체크리스트

Gemini 리뷰 갭 학습 누적으로 도출된 Claude가 빈번히 놓치는 패턴. **리뷰 시 의식적으로 확인**한다:

| 카테고리 | 패턴 | 검증 방법 |
|---------|------|----------|
| 네이밍 일관성 | FQDN vs short name 혼용 (`service.namespace.svc.cluster.local` vs `service`) | manifest/config 전체에서 동일 host 표기 일치 |
| Shell 변수 인용 | `$VAR` vs `"$VAR"` 차이 (공백/특수문자 포함 시) | shell script 내 변수 사용 — quoting 누락 위치 |
| Helm template 이스케이프 | recording rule 안의 `{{ $labels.x }}` (Helm이 먼저 평가) | `{{ "{{" }} $labels.x {{ "}}" }}` 형태 |
| label/selector 일치 | Service selector vs Deployment label, NetworkPolicy podSelector vs Pod label | matchLabels 양방향 검증 |
| env 변수 expand | `${VAR}` 리터럴 (K8s manifest에서 expand 안 됨) | shell script 또는 init container에서 처리 여부 |
| API version | beta API 잔재 (`networking.k8s.io/v1beta1` 등) | manifest 전수 grep |
| Idempotency | 비멱등 메서드(POST)의 retry 설정 | Istio VirtualService / 클라이언트 retry policy |

매 PR에서 위 항목 통과 여부를 mental check 후 코멘트 작성.

---

## PR 코멘트 양식

코드 리뷰 결과는 아래 양식으로 PR에 코멘트를 남긴다.

```markdown
## Code Review - Claude Code

### Summary
| Severity | Count |
|----------|-------|
| Blocker  | 0     |
| Critical | 0     |
| Major    | 0     |
| Minor    | 0     |

> Confidence threshold: 50 | Avg confidence: --

### Blocker
<!-- 머지 차단 수준. 보안 취약점, 기능 장애, 컨벤션 위반 등 -->

**[CR-001] 🔒 제목** `confidence: 95`
- 파일: `path/to/file.yaml` (line X)
- 현재: 문제 설명
- 수정 제안: 구체적 해결 방안

### Critical
<!-- 심각한 문제. 성능, 데이터 무결성 등 -->

### Major
<!-- 중요하지만 즉시 장애는 아닌 문제 -->

### Minor
<!-- 개선 권장 사항. 선택적 반영 -->

### Good Practices
<!-- 잘 작성된 부분 칭찬 (선택) -->
```

### 심각도 기준

| 심각도 | 기준 | 예시 |
|--------|------|------|
| Blocker | 머지하면 안 되는 수준 | 보안 취약점, 빌드 깨짐, 컨벤션 위반 |
| Critical | 프로덕션 문제 가능 | 리소스 누수, 데이터 불일치 |
| Major | 유지보수/확장성 문제 | 패턴 미준수, 누락된 설정 |
| Minor | 개선 권장 | 네이밍, 주석, 사소한 개선 |

### 규칙

- 제목은 반드시 `## Code Review - Claude Code`로 시작
- 이슈 ID는 `[CR-001]`부터 순차 부여
- 빈 섹션(해당 심각도 이슈 없음)은 생략
- 수정 제안은 구체적으로 (코드 스니펫 포함 권장)
- Good Practices는 선택 사항
