---
name: conventional-commits
description: "Conventional Commits — 커밋 메시지 규칙 및 자동화 패턴 Use when working with dx 도메인의 패턴 / 구현 선택."
effort: low
deprecated: false
---

# Conventional Commits

커밋 메시지 규칙 및 자동화 패턴

## Quick Reference

```
Conventional Commits
    │
    ├─ 포맷 ─────────> <type>(<scope>): <description>
    │
    ├─ 검증 ─────────> commitlint + husky
    │
    ├─ 릴리즈 자동화
    │   ├─ 완전 자동 ──> semantic-release
    │   └─ 반자동 ────> release-please
    │
    └─ Breaking ────> feat!: 또는 BREAKING CHANGE: footer
```

---

## 기본 포맷

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### 예시
```
feat(auth): add JWT refresh token support

Implement automatic token refresh when access token expires.
Includes retry logic for failed refresh attempts.

Closes #123
BREAKING CHANGE: Auth header format changed from 'Token' to 'Bearer'
```

---

## Type 종류

| Type | 설명 | SemVer |
|------|------|--------|
| `feat` | 새로운 기능 | MINOR |
| `fix` | 버그 수정 | PATCH |
| `docs` | 문서 변경 | - |
| `style` | 코드 스타일 (포맷팅) | - |
| `refactor` | 리팩토링 (기능 변화 없음) | - |
| `perf` | 성능 개선 | PATCH |
| `test` | 테스트 추가/수정 | - |
| `build` | 빌드 설정 변경 | - |
| `ci` | CI 설정 변경 | - |
| `chore` | 기타 변경 | - |

### Breaking Change
```
feat!: remove deprecated API endpoints

BREAKING CHANGE: /api/v1/* endpoints are removed.
Use /api/v2/* instead.
```

`!` 또는 `BREAKING CHANGE:` footer → **MAJOR** 버전

---

## Scope 예시

```
feat(api): add user search endpoint
fix(ui): resolve button alignment issue
docs(readme): update installation guide
refactor(auth): extract token validation logic
```

프로젝트에 맞게 정의:
- 모듈별: `api`, `ui`, `core`, `db`
- 기능별: `auth`, `payment`, `user`
- 레이어별: `controller`, `service`, `repository`

---

## 자동화 도구

### 1. commitlint (검증)

```bash
npm install -D @commitlint/{cli,config-conventional}
```

```js
// commitlint.config.js
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [2, 'always', ['api', 'ui', 'core', 'auth']],
  },
};
```

```bash
# .husky/commit-msg
npx --no -- commitlint --edit $1
```

### 2. semantic-release (자동 릴리즈)

```bash
npm install -D semantic-release
```

```json
// package.json
{
  "release": {
    "branches": ["main"],
    "plugins": [
      "@semantic-release/commit-analyzer",
      "@semantic-release/release-notes-generator",
      "@semantic-release/changelog",
      "@semantic-release/npm",
      "@semantic-release/github"
    ]
  }
}
```

**동작:**
- `fix:` → v1.0.0 → v1.0.1 (PATCH)
- `feat:` → v1.0.1 → v1.1.0 (MINOR)
- `feat!:` → v1.1.0 → v2.0.0 (MAJOR)
- CHANGELOG.md 자동 생성
- GitHub Release 자동 생성

### 3. release-please (Google 권장)

```bash
# GitHub Action으로 사용 (권장)
# .github/workflows/release-please.yml
name: Release Please
on:
  push:
    branches: [main]
jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        with:
          release-type: node  # 또는 go, python, java 등
```

**동작:**
- PR 자동 생성 (릴리즈 준비)
- 머지 시 태그 + GitHub Release 생성
- CHANGELOG.md 자동 업데이트

> **Note**: `standard-version`은 2023년부터 maintenance 모드. 신규 프로젝트는 `semantic-release` 또는 `release-please` 권장

### 4. commitizen (대화형 커밋)

```bash
npm install -D commitizen cz-conventional-changelog

# package.json
{
  "config": {
    "commitizen": {
      "path": "cz-conventional-changelog"
    }
  }
}

# 사용
npx cz
# 또는
git cz
```

---

## Go 프로젝트

### go-semantic-release

```yaml
# .github/workflows/release.yml
name: Release
on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: go-semantic-release/action@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### goreleaser + conventional commits

```yaml
# .goreleaser.yml
version: 2
builds:
  - env: [CGO_ENABLED=0]
    goos: [linux, darwin]
    goarch: [amd64, arm64]

changelog:
  use: github
  groups:
    - title: Features
      regexp: '^feat'
    - title: Bug Fixes
      regexp: '^fix'
    - title: Others
      regexp: '^(docs|style|refactor|perf|test|build|ci|chore)'
```

---

## PR 전략

### Squash Merge (권장)

```
PR Title: feat(auth): implement OAuth2 login

# PR 내 커밋들 (스쿼시됨)
- wip: initial oauth setup
- fix: token parsing
- add tests
```

→ 머지 시 PR 제목이 커밋 메시지가 됨

### GitHub 설정

```
Settings > General > Pull Requests
☑ Allow squash merging
  Default commit message: Pull request title
```

---

## 체크리스트

### 커밋 작성 시
- [ ] type이 올바른가? (feat/fix/docs 등)
- [ ] scope가 일관성 있는가?
- [ ] description이 명확한가?
- [ ] breaking change면 `!` 또는 footer 추가했는가?
- [ ] 관련 이슈 참조했는가? (Closes #123)

### 프로젝트 설정
- [ ] commitlint 설정됨
- [ ] husky commit-msg hook 설정됨
- [ ] PR squash merge 활성화
- [ ] semantic-release 또는 standard-version 설정됨
- [ ] CI에서 자동 릴리즈 설정됨

---

## Anti-Patterns

| 실수 | 올바른 예 |
|------|----------|
| `fix bug` | `fix(auth): resolve login timeout issue` |
| `update` | `refactor(api): simplify error handling` |
| `WIP` | 작업 완료 후 rebase로 정리 |
| `feat + fix` 섞음 | PR 분리 또는 squash |
| 본문 없이 복잡한 변경 | body에 상세 설명 추가 |

---

## 선택 가이드

```
OSS / NPM 배포? ──────────> semantic-release (완전 자동)
     │
     └─ 앱 / 수동 제어? ───> standard-version (반자동)
           │
           └─ Go 프로젝트? ─> goreleaser + go-semantic-release
```
