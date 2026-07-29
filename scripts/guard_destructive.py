#!/usr/bin/env python3
"""PreToolUse(Bash) 가드 — 플래그 순서에 의존하는 파괴적 명령을 차단한다.

**왜 permissions.deny로 안 되나**: `Bash(...)` deny 규칙은 **접두사 매칭**이다.
`kubectl apply …`처럼 동사가 앞에 오는 건 확실히 잡지만, 아래는 못 잡는다.

    argocd app sync myapp --force      ← --force가 뒤에 온다
    git push origin main --force       ← 동일
    kubectl --namespace x delete pod   ← 전역 플래그가 동사보다 앞에 온다

Anthropic 공식 가이드도 "절대 금지는 hook으로"라고 말한다(deny는 접두사, hook은 전체 문자열).
그래서 접두사로 안정적인 금지는 settings.json의 permissions.deny에, **순서 의존 금지는 여기에** 둔다.
deny 리스트가 완전하다고 착각하지 않는 것이 이 파일의 존재 이유다.

근거 룰:
  .claude/rules/user-approval.md §ArgoCD Force Sync 금지 (실제 사고 2026-03-28)
  .claude/rules/user-approval.md §kubectl 변경 금지 (실제 사고 2026-03-22)
  .claude/rules/git.md §Branch Protection (force push 금지)

⚠️ settings.json의 훅이 shell case 프리필터(`*kubectl*|*argocd*|*git*push*`)로 이 스크립트를
감싼다 — python 기동 비용을 무해한 Bash 호출에서 생략하기 위해서다(2026-07-29). RULES에
새 명령어를 추가하면 **프리필터 패턴에도 그 리터럴을 추가**해야 한다. 안 하면 가드가 조용히
뚫린다(프리필터가 python을 아예 안 부름).
"""

from __future__ import annotations

import json
import re
import sys

# heredoc 본문은 **명령이 아니라 데이터**다(커밋 메시지·문서·JSON 페이로드).
# 줄 단위로 세그먼트를 나누면 `git commit -F - <<EOF` 안의 "argocd app sync --force" 같은
# 인용문이 명령으로 오인된다 — 이 가드를 켠 직후 자기 커밋 메시지를 두 번 막았다(2026-07-28).
HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

# 세그먼트 분리자 — 파이프라인/체이닝/개행. 인용부호 안의 텍스트는 자체 세그먼트가 되지 않는다.
SEGMENT_SPLIT = re.compile(r"(?:\|\||&&|[;\n|])")
# 세그먼트 앞머리의 잡음(서브셸 여는 괄호, VAR=값 형태의 환경변수 프리픽스).
SEGMENT_PREFIX = re.compile(r"^[\s(){]*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*")

# (정규식, 사유). 정규식은 **세그먼트 앞머리에 앵커**된다(`^`).
# 전체 문자열 검색으로 하면 `echo '... argocd app sync --force ...'`처럼 인용부호 안의
# 텍스트에도 걸린다 — 실제로 이 가드를 처음 켠 직후 자기 테스트 문자열을 물었다(2026-07-28).
# 문서·dev-log에 사고 명령을 인용하는 것까지 막으면 가드가 일을 방해한다.
RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"^argocd\b.*\bsync\b.*(--force|--replace)\b"),
        "ArgoCD Force Sync 금지 — ServerSideApply=true 앱에서 --force와 --server-side는 "
        "동시 사용 불가라 sync operation이 stuck된다(user-approval.md, 실제 사고 2026-03-28). "
        "force 없는 sync로 다시 시도하라.",
    ),
    (
        re.compile(r"^git\s+push\b.*(--force\b(?!-with-lease)|(?<![\w-])-f\b)"),
        "force push 금지 — 히스토리 파괴는 되돌릴 수 없다(git.md §Branch Protection). "
        "정말 필요하면 사용자에게 먼저 확인받아라.",
    ),
    (
        re.compile(r"^kubectl\b.*\b(apply|delete|patch|edit|scale|rollout|replace|create)\b"),
        "kubectl로 K8s 리소스를 직접 바꾸지 않는다 — ArgoCD OutOfSync·drift 추적 불가·"
        "의도치 않은 rollout을 유발한다(user-approval.md, 실제 사고 2026-03-22). "
        "올바른 경로: 소스 수정 → commit/push → ArgoCD sync.",
    ),
]


def strip_heredocs(command: str) -> str:
    """heredoc 본문을 걷어낸다. 리다이렉트를 여는 줄 자체는 명령이므로 남긴다."""
    lines = command.split("\n")
    kept: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        m = HEREDOC_START.search(line)
        if m:
            delimiter = m.group(2)
            i += 1
            while i < len(lines) and lines[i].strip() != delimiter:
                i += 1  # 본문 — 데이터이므로 버린다
        i += 1
    return "\n".join(kept)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # 입력을 못 읽으면 조용히 통과 — 가드가 작업을 막는 버그가 되면 안 된다

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    segments = [
        SEGMENT_PREFIX.sub("", seg).strip()
        for seg in SEGMENT_SPLIT.split(strip_heredocs(command))
    ]

    for pattern, reason in RULES:
        if any(pattern.search(seg) for seg in segments):
            json.dump({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }, sys.stdout, ensure_ascii=False)
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
