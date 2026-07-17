# Git Rules

Git 작업 시 반드시 준수해야 할 규칙. 위반 시 작업을 중단하고 올바른 방식으로 재시도한다.

---

## Commit Message

MUST follow the Conventional Commits specification for every commit.

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type       | 의미                          | SemVer  |
|------------|-------------------------------|---------|
| `feat`     | 새 기능 추가                  | MINOR   |
| `fix`      | 버그 수정                     | PATCH   |
| `feat!`    | Breaking change 포함 기능     | MAJOR   |
| `docs`     | 문서 변경 (코드 무관)         | -       |
| `style`    | 포맷, 공백 등 (로직 무관)     | -       |
| `refactor` | 기능 변경 없는 코드 개선      | -       |
| `perf`     | 성능 개선                     | PATCH   |
| `test`     | 테스트 추가/수정              | -       |
| `build`    | 빌드 시스템, 의존성 변경      | -       |
| `chore`    | 그 외 유지보수 작업           | -       |
| `ci`       | CI/CD 설정 변경               | -       |

### Rules

- `scope` = 영향받는 모듈명 (예: `auth`, `order`, `k8s`, `api`)
- `description` MUST start with lowercase, no period at end, 50 chars max
- Breaking changes MUST include `BREAKING CHANGE:` in footer or `!` after type
- NEVER use vague messages like `fix bug`, `update`, `wip`

---

## Branch Naming

MUST follow the branch naming convention before creating any branch.

```
feature/#<issue>-short-description
fix/#<issue>-short-description
hotfix/#<issue>-critical-fix
docs/update-<topic>
chore/<task-description>
release/v<major>.<minor>.<patch>
```

- 이슈 번호가 없으면 `#<issue>` 부분 생략 가능
- 단어 구분은 하이픈(`-`) 사용, 공백/언더스코어 금지
- 소문자만 사용

---

## Commit Discipline

- MUST commit in logical units: 하나의 목적 = 하나의 커밋
- **PREFER 4~5 파일 이내** — 단일 커밋이 그 이상이면 리뷰 부담이 급증한다. 성격이 다른 변경(코드/문서/설정)은 분리한다.
- NEVER commit WIP (work-in-progress) directly; squash before push
- NEVER commit `.env`, credentials, API keys, or any secret files
- NEVER include unrelated changes in a single commit
- `git add .` 대신 파일을 명시적으로 지정하여 스테이징
- 큰 변경은 PR 자체를 분할하거나, 의미 단위로 여러 커밋으로 쪼개 push

---

## Co-Authored-By Trailer 금지 (MANDATORY)

NEVER add `Co-Authored-By: Claude ...` (또는 다른 AI 어시스턴트) trailer to commit messages **unless the user has explicitly requested it.**

- 모든 경로에서 금지: `git commit`, slash command, amend, rebase, squash merge 시 commit message 재작성 포함
- Claude Code CLI / Codex / Cursor 기본 commit template 사용 시에도 동일
- 예외: 사용자가 명시적으로 "Co-Authored-By 넣어줘"라고 요청한 경우만

---

## Branch Protection

- NEVER push directly to `main` or `master`
- NEVER force push (`--force`, `-f`) to `main` or `master`
- ALWAYS create a feature/fix branch and open a PR
- 긴급 핫픽스도 `hotfix/` 브랜치 생성 후 PR로 머지

---

## Pull Request

PR 생성 시 아래 형식을 MUST 준수한다.

### Title

PR 제목은 Conventional Commits 형식과 동일하게 작성:

```
feat(auth): add OAuth2 social login support
fix(order): resolve race condition in payment processing
```

### Body Template

```markdown
## Summary
- 변경 내용 요약 (불릿 포인트, 1~3개)
- 왜 이 변경이 필요한가

## Test plan
- [ ] 단위 테스트 추가/수정 확인
- [ ] 로컬 실행 검증
- [ ] 엣지 케이스 확인

Closes #<issue>
```

### Size Limit

- 단일 PR MUST NOT exceed 400 lines of change
- 400줄 초과 시 기능 단위로 PR 분할
- 리뷰어가 맥락을 이해할 수 있도록 설명 충분히 작성
- **이동 전용(move-only) 리팩토링 PR 예외**: `git diff -M90%` 기준 rename으로 인식되는 변경은 산정에서 제외 — 비-rename 실질 diff(package/import 행·최소 가시성 승격)가 400줄 이내면 허용. 단 PR 본문에 move-only 선언 + rename 검증 명령 + 비-이동 diff 전수 열거 필수. 로직 변경 혼입 금지.

---

## Sensitive Files

NEVER stage or commit these files under any circumstances:

- `.env`, `.env.*`, `.env.local`
- `*credentials*`, `*secret*`, `*.pem`, `*.key`
- `application-prod.yml`, `application-production.properties`
- 클라우드 자격증명 파일 (AWS, GCP, Azure)

이미 커밋된 경우 즉시 히스토리에서 제거하고 시크릿을 rotate한다.
