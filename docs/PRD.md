# PRD — Synapse (코드네임, 변경 가능)

> 실시간 협업 텍스트 문서 편집 + 문서 맥락을 이해하는 AI co-pilot.
> Polyglot MSA(Java / Python / Rust), 로컬 LLM(Ollama) 우선·클라우드 폴백.

문서 버전: M0 (SDD v2 정렬) / 작성: 기획 단계
> **변경 노트 (SDD v2 정렬, 2026-06-24)**: 언어 전략 B 반영 — 게이트웨이 Go → **Java Virtual Thread**, AI Service 언어 = **Python**, 모노레포 → **5-repo 폴리레포(buf + submodule)**, 폴리글랏 trace 체인 `Go→Rust→Java` → **`Java→Rust→Python`**. 근거·상세는 `SDD.md` §0·§2·§12 및 `docs/adr/0001-language-strategy-b.md`.

이 문서의 목적: **Claude Code 및 협업자가 "무엇을, 왜" 만드는지 합의**하는 기준점. "어떻게"는 `SDD.md` 참조.

---

## 구성 (분할 문서)
- [만드는 이유 · 타겟 사용자](prd/1-why-and-users.md) — §2–3
- [기능 범위 · NFR · DoD · 리스크](prd/2-scope-nfr-dod.md) — §4–8

## 1. 한 줄 정의

여러 사용자가 **동시에 같은 문서를 편집**(CRDT 기반)하고, **AI가 문서 내용을 근거로 질문에 답하고 요약·리라이트를 제안**하는 협업 에디터. AI 추론은 로컬 GPU(Ollama)에서 우선 수행하고, 과부하·장애 시 클라우드 LLM으로 폴백한다.
