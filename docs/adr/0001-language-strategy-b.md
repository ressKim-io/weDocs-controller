# ADR-0001 — 언어 전략 B (지배적 제약 기반 언어 배치)

- 상태: **Accepted**
- 날짜: 2026-06-24
- 관련: PRD §2.2 · SDD §0·§2·§15.1

## 맥락
폴리글랏 MSA에서 "왜 이 언어?"를 일관 논리로 방어해야 한다. 초기 후보에 **Go**가 있었다(WS 게이트웨이).
"다양하게 써봄"이 아니라 "각 서비스의 필연적 분리"로 설명 가능해야 한다(PRD §2.2).

## 결정
각 서비스의 **지배적 제약**에 언어를 배치한다.

| 지배적 제약 | 언어 | 서비스 |
|---|---|---|
| I/O 바운드 | **Java 25 / Virtual Thread** | WS Gateway, Doc/Session |
| AI 생태계 | **Python / FastAPI + LlamaIndex** | AI Service, Indexing Consumer |
| CPU 바운드 + 정확성 critical | **Rust / yrs** | CRDT Engine |

**Go 제외 근거**: JEP 491(JDK 24/25)로 Virtual Thread의 `synchronized` pinning이 해소되어,
blocking 코드로 수만 커넥션을 단순하게 처리할 수 있다 → goroutine 대비 동시성 우위가 상쇄되어
"왜 Go?"를 방어하기 어렵다.

## 결과
- 폴리글랏 trace 체인이 **Java → Rust → Python** (단일 OTel trace가 핵심 showcase).
- AI Service는 stateless(텍스트 in/out), CRDT 미인지(가드레일).
- 게이트웨이는 native call(JNI) 도입 금지 — 남은 VT pinning 원인 제거.
- 면접 한 줄: "I/O는 Java VT, AI는 Python, CPU+정확성(CRDT)은 Rust — 지배적 제약에 언어를 배치."

## 대안 / 기각
- **Go 게이트웨이**: VT가 동시성 우위를 상쇄 → 기각.
- **AI를 Spring AI(Java)로**: "모델 통합"엔 충분하나 RAG "생태계 깊이"(고급 청킹·쿼리 분해)는
  Python/LlamaIndex 우위 → 기각.
- **CRDT를 Java 래퍼로**: 머지는 CPU 바운드 + 수렴 정확성이 생명 → Rust 독립 엔진(ADR-0004).
