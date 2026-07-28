#!/usr/bin/env python3
"""Claude Code 상시 로드 컨텍스트 예산 게이트.

매 세션 무조건 로드되는 것만 측정한다:
    CLAUDE.md
  + .claude/rules/**/*.md 중 frontmatter에 paths: 키가 없는 것
  + CLAUDE.md에서 실제 @import로 도달하는 파일 (재귀)
  − 절대경로 기준 중복 제거

표준·근거: docs/plans/2026-07-28-claude-context-budget.md
공식 출처: https://code.claude.com/docs/en/memory
  - "target under 200 lines per CLAUDE.md file"
  - paths: 없는 rule은 launch 시 무조건 로드
  - "@imports ... doesn't reduce context" (조직화 수단일 뿐 절감 아님)

의존성 없음(stdlib only) — 러너/맥 어디서나 그대로 실행된다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# @import 재귀 상한. 공식 문서상 최대 4 hop이라 5면 충분하다.
MAX_IMPORT_DEPTH = 5

# 이 코퍼스 실측 비율(한글 28% / ASCII 71%). 사람이 감각을 잡기 위한 참고치일 뿐,
# 게이트 판정은 항상 코드포인트로 한다 — 토크나이저는 모델 세대마다 바뀐다.
CHARS_PER_TOKEN = 1.99


# ─────────────────────────────────────────────────────────────
# 임계값
#
# STAGE를 올리는 것이 곧 "래칫"이다. 임계값 하향은 내용 변경과 섞지 말고
# 항상 별도 커밋으로 — 그래야 조인 것과 되돌릴 것을 따로 볼 수 있다.
# ─────────────────────────────────────────────────────────────
STAGE = "baseline"

TIER_A = {
    # baseline: 현재값+5%. 스크립트를 무수정 통과시켜 "측정이 맞는지"만 먼저 검증한다.
    "baseline": {
        "total_lines": 2074,
        "total_chars": 59988,
        "claude_md_lines": 82,
        "max_rule_lines": 205,
        "imports": 7,
        "noop_imports": 5,
    },
    "stage1": {
        "total_lines": 900,
        "total_chars": 26000,
        "claude_md_lines": 150,
        "max_rule_lines": 160,
        "imports": 2,
        "noop_imports": 0,
    },
    "stage2": {
        "total_lines": 300,
        "total_chars": 9000,
        "claude_md_lines": 80,
        "max_rule_lines": 60,
        "imports": 0,
        "noop_imports": 0,
    },
}

# Tier B — 참고 문서 길이 예산. 상시 로드가 아니라 "읽힐 때 비싼" 문서들.
# 오늘의 최댓값보다 살짝 위로 잡아, 진짜 회귀에만 발화하고 평소엔 조용하게 한다.
TIER_B = {
    "scoped_rule_lines": 200,      # 오늘 최대: debugging.md 195 (97% 소진)
    "skill_md_lines": 300,
    "skill_md_count": 12,
    "skill_desc_chars": 400,
    "flat_skill_lines": 700,       # 오늘 최대: dx/local-dev-makefile.md 636
    "agent_body_lines": 620,       # 오늘 최대: java-expert.md 605
    "agent_desc_chars": 600,
    "agent_desc_total": 5200,
}

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
IMPORT_RE = re.compile(r"(?:^|\s)@([^\s`]+)")


@dataclass
class Doc:
    path: Path
    lines: int
    chars: int
    bytes_: int
    reason: str  # "CLAUDE.md" | "no-paths" | "@import"


@dataclass
class Report:
    docs: list[Doc] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    noop_imports: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


def measure(p: Path) -> tuple[int, int, int]:
    """줄 / 코드포인트 / 바이트.

    FP-6: 한글은 바이트 ≠ 문자다(이 코퍼스 ~1.58 byte/codepoint). `wc -c`로 예산을
    잡으면 한글을 1.5~3배 계상해 임계값이 무의미해진다. 항상 코드포인트로 센다.
    """
    raw = p.read_bytes()
    text = raw.decode("utf-8")
    return text.count("\n") + (0 if text.endswith("\n") or not text else 1), len(text), len(raw)


def frontmatter_lines(text: str) -> list[str] | None:
    """frontmatter 블록의 본문 줄들. 없으면 None.

    FP-1: frontmatter가 아예 없는 룰이 있다(clean-code.md·token-budget.md는 `# `로 시작).
          1행이 정확히 `---`일 때만 frontmatter로 인정한다 — 그 외에는 없는 것.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return None  # 닫히지 않은 구분자 = frontmatter 아님


def paths_state(p: Path) -> str:
    """'scoped' | 'unscoped' | 'empty'.

    FP-2: 본문 산문과 YAML 예시에도 `paths:`가 등장한다(이 룰 문서들이 정확히 그렇다).
          절대 본문을 grep하지 않고 frontmatter 블록 안에서만 판정한다.
    FP-5: 키는 있는데 값이 비면(`paths:` / `paths: []`) Claude Code는 unscoped로 취급한다.
    """
    fm = frontmatter_lines(p.read_text(encoding="utf-8"))
    if fm is None:
        return "unscoped"

    for idx, line in enumerate(fm):
        m = re.match(r"^paths:\s*(.*)$", line)
        if not m:
            continue
        inline = m.group(1).strip()
        if inline and inline not in ("[]", "[ ]"):
            return "scoped"
        # 블록 시퀀스: 다음 줄부터 들여쓴 `- ...`가 있는지
        for nxt in fm[idx + 1:]:
            if not nxt.strip():
                continue
            if re.match(r"^\s+-\s*\S", nxt):
                return "scoped"
            break
        return "empty"
    return "unscoped"


def strip_code(text: str) -> list[str]:
    """코드펜스 안의 줄을 비우고, 남은 줄의 inline code span도 제거한다.

    FP-3: `^@`는 @import가 아니다. 이 트리의 룰 본문 코드펜스 안에는
          @Transactional(3) @Bean @Test @Entity @RestControllerAdvice @DisplayName
          @EqualsAndHashCode @NoArgsConstructor 등 **가짜 10건**이 있다.
          펜스 상태를 추적해 스킵하지 않으면 import가 7이 아니라 17로 잡힌다.
    """
    out: list[str] = []
    fence: str | None = None
    for line in text.split("\n"):
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            out.append("")
            continue
        out.append("" if fence else INLINE_CODE_RE.sub("", line))
    return out


def collect_imports(start: Path, report: Report) -> list[Path]:
    """start에서 실제 @import로 도달하는 파일들(재귀).

    FP-3(2): 펜스를 걷어낸 뒤에도 `@` 뒤 토큰이 **디스크에 실재하는 파일로 resolve될 때만**
             import로 인정한다. 이메일·데코레이터·멘션이 섞여도 안전하다.
    """
    found: list[Path] = []
    seen: set[Path] = {start.resolve()}
    queue: list[tuple[Path, int]] = [(start, 0)]

    while queue:
        current, depth = queue.pop(0)
        if depth >= MAX_IMPORT_DEPTH:
            report.warnings.append(f"@import 깊이 상한({MAX_IMPORT_DEPTH}) 도달: {rel(current)}")
            continue

        for line in strip_code(current.read_text(encoding="utf-8")):
            for token in IMPORT_RE.findall(line):
                target = token.rstrip(".,;:)")
                cand = (current.parent / target).resolve()
                if not cand.is_file():
                    cand = (REPO / target).resolve()
                if not cand.is_file():
                    continue  # 데코레이터/멘션/오타 — import 아님
                report.imports.append(rel(cand))
                if cand in seen:
                    continue
                seen.add(cand)
                found.append(cand)
                queue.append((cand, depth + 1))
    return found


def build_report() -> Report:
    r = Report()
    claude_md = REPO / "CLAUDE.md"
    if not claude_md.is_file():
        r.violations.append("CLAUDE.md 없음")
        return r

    seen: set[Path] = set()

    def add(p: Path, reason: str) -> None:
        rp = p.resolve()
        if rp in seen:
            return
        seen.add(rp)
        lines, chars, bytes_ = measure(rp)
        r.docs.append(Doc(rp, lines, chars, bytes_, reason))

    add(claude_md, "CLAUDE.md")

    imported = {p.resolve() for p in collect_imports(claude_md, r)}

    rules_dir = REPO / ".claude" / "rules"
    for rule in sorted(rules_dir.rglob("*.md")) if rules_dir.is_dir() else []:
        state = paths_state(rule)
        if state == "empty":
            r.warnings.append(f"{rel(rule)}: paths: 키가 비어 있음 → Claude Code는 unscoped로 취급")
        if state in ("unscoped", "empty"):
            add(rule, "no-paths")
            # FP-4: @import이면서 paths:도 없으면 그 import는 아무 일도 하지 않는다.
            #       중복 계상하지 않고(위 seen), 대신 제거 대상으로 보고한다.
            if rule.resolve() in imported:
                r.noop_imports.append(rel(rule))

    for p in sorted(imported):
        add(p, "@import")

    # FP-7: 사용자 스코프 메모리는 CI가 볼 수 없다. 측정 범위를 정직하게 밝힌다.
    if (REPO / "CLAUDE.local.md").is_file():
        r.warnings.append("CLAUDE.local.md 존재 — 이 파일도 로드되지만 gitignore라 CI 측정 범위 밖")
    return r


def totals(r: Report) -> dict:
    return {
        "files": len(r.docs),
        "lines": sum(d.lines for d in r.docs),
        "chars": sum(d.chars for d in r.docs),
        "bytes": sum(d.bytes_ for d in r.docs),
        "est_tokens": int(sum(d.chars for d in r.docs) / CHARS_PER_TOKEN),
    }


def check_tier_a(r: Report) -> None:
    t = TIER_A[STAGE]
    tot = totals(r)
    claude_md = next((d for d in r.docs if d.reason == "CLAUDE.md"), None)
    rules = [d for d in r.docs if d.reason != "CLAUDE.md"]

    def bad(label: str, actual: int, cap: int) -> None:
        if actual > cap:
            r.violations.append(f"[A] {label}: {actual:,} > {cap:,}")

    bad("상시 로드 총 줄수", tot["lines"], t["total_lines"])
    bad("상시 로드 총 코드포인트", tot["chars"], t["total_chars"])
    if claude_md:
        bad("CLAUDE.md 줄수", claude_md.lines, t["claude_md_lines"])
    if rules:
        worst = max(rules, key=lambda d: d.lines)
        bad(f"상시 로드 개별 룰 최대 줄수({rel(worst.path)})", worst.lines, t["max_rule_lines"])
    bad("CLAUDE.md 실제 @import 수", len(set(r.imports)), t["imports"])
    bad("no-op @import 수", len(r.noop_imports), t["noop_imports"])


def check_tier_b(r: Report) -> None:
    def bad(label: str, actual: int, cap: int) -> None:
        if actual > cap:
            r.violations.append(f"[B] {label}: {actual:,} > {cap:,}")

    rules_dir = REPO / ".claude" / "rules"
    for rule in sorted(rules_dir.rglob("*.md")) if rules_dir.is_dir() else []:
        if paths_state(rule) == "scoped":
            bad(f"스코프 룰 줄수({rel(rule)})", measure(rule)[0], TIER_B["scoped_rule_lines"])

    skills = REPO / ".claude" / "skills"
    if skills.is_dir():
        registered = sorted(skills.glob("*/SKILL.md"))
        bad("SKILL.md 개수", len(registered), TIER_B["skill_md_count"])
        for s in registered:
            bad(f"SKILL.md 줄수({rel(s)})", measure(s)[0], TIER_B["skill_md_lines"])
            desc = read_desc(s)
            if desc:
                bad(f"SKILL.md description 자수({rel(s)})", len(desc), TIER_B["skill_desc_chars"])
        for flat in sorted(skills.glob("*/*.md")):
            if flat.name == "SKILL.md":
                continue
            bad(f"레퍼런스 스킬 줄수({rel(flat)})", measure(flat)[0], TIER_B["flat_skill_lines"])

    agents = REPO / ".claude" / "agents"
    total_desc = 0
    for a in sorted(agents.glob("*.md")) if agents.is_dir() else []:
        bad(f"에이전트 본문 줄수({rel(a)})", measure(a)[0], TIER_B["agent_body_lines"])
        desc = read_desc(a)
        if desc:
            total_desc += len(desc)
            bad(f"에이전트 description 자수({rel(a)})", len(desc), TIER_B["agent_desc_chars"])
    bad("에이전트 description 합계", total_desc, TIER_B["agent_desc_total"])


def read_desc(p: Path) -> str:
    """frontmatter의 description 값. 다음 최상위 키 전까지가 값(멀티라인 허용)."""
    fm = frontmatter_lines(p.read_text(encoding="utf-8"))
    if fm is None:
        return ""
    out: list[str] = []
    capture = False
    for line in fm:
        if re.match(r"^description:\s*", line):
            capture = True
            out.append(re.sub(r"^description:\s*", "", line))
            continue
        if capture:
            if re.match(r"^[A-Za-z_][\w-]*:", line):
                break
            out.append(line)
    return "\n".join(out).strip().strip('"').strip("'").strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Claude Code 상시 로드 컨텍스트 예산 게이트")
    ap.add_argument("--json", action="store_true", help="기계 판독용 JSON 출력")
    ap.add_argument("--quiet-if-ok", action="store_true", help="통과 시 무출력 (훅 모드)")
    ap.add_argument("--tier", choices=["a", "b", "all"], default="all")
    args = ap.parse_args()

    r = build_report()
    if args.tier in ("a", "all"):
        check_tier_a(r)
    if args.tier in ("b", "all"):
        check_tier_b(r)

    tot = totals(r)
    ok = not r.violations

    if args.json:
        print(json.dumps({
            "stage": STAGE,
            "ok": ok,
            "totals": tot,
            "imports": sorted(set(r.imports)),
            "noop_imports": r.noop_imports,
            "files": [
                {"path": rel(d.path), "reason": d.reason, "lines": d.lines, "chars": d.chars}
                for d in sorted(r.docs, key=lambda d: -d.lines)
            ],
            "warnings": r.warnings,
            "violations": r.violations,
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    if ok and args.quiet_if_ok:
        return 0

    print(f"Claude 상시 로드 컨텍스트 예산 [stage={STAGE}]")
    print(f"  파일 {tot['files']} · {tot['lines']:,}줄 · {tot['chars']:,}자 "
          f"· {tot['bytes']:,}바이트 · ~{tot['est_tokens']:,}토큰")
    print(f"  실제 @import {len(set(r.imports))}건 (no-op {len(r.noop_imports)}건)")
    print("  범위: 프로젝트 메모리만 — ~/.claude/CLAUDE.md·rules는 CI가 볼 수 없음")

    if not args.quiet_if_ok:
        print("\n  상시 로드 파일:")
        for d in sorted(r.docs, key=lambda d: -d.lines):
            print(f"    {d.lines:>5}줄 {d.chars:>7,}자  {rel(d.path)}  [{d.reason}]")

    for w in r.warnings:
        print(f"  WARN: {w}")
    for n in r.noop_imports:
        print(f"  WARN: @import {n} 는 no-op — paths:가 없어 이미 자동 로드됨")

    if r.violations:
        print("\n예산 초과:")
        for v in r.violations:
            print(f"  ✗ {v}")
        print("\n  → docs/plans/2026-07-28-claude-context-budget.md 참조")
        return 1

    print("\n  ✓ 예산 내")
    return 0


if __name__ == "__main__":
    sys.exit(main())
