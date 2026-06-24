---
name: prompt-engineering
description: "Prompt Engineering — 프롬프트 설계 기법, 시스템 프롬프트, 가드레일, 평가 방법론 Use when working with ai 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Prompt Engineering

프롬프트 설계 기법, 시스템 프롬프트, 가드레일, 평가 방법론

## Quick Reference (기법 선택)

```
작업 유형별 프롬프트 기법?
    │
    ├─ 단순 분류/추출 ────> Zero-shot + 출력 형식 지정
    ├─ 패턴 학습 필요 ────> Few-shot (3-5 예시)
    ├─ 복잡한 추론 ────────> Chain-of-Thought (CoT)
    ├─ 다단계 의사결정 ───> Tree-of-Thought
    ├─ 도구 사용 필요 ────> ReAct (Reasoning + Acting)
    └─ 정확도 극대화 ─────> Self-consistency + CoT

출력 형식?
    │
    ├─ 구조화 데이터 ─────> JSON Mode / Function Calling
    ├─ 자유 형식 ──────────> System prompt + 예시
    └─ 코드 생성 ──────────> Few-shot + 테스트 케이스 포함

안전성?
    │
    ├─ 입력 검증 ──────────> Content filtering + 길이 제한
    ├─ 출력 검증 ──────────> Output parsing + Schema validation
    └─ 탈옥 방지 ──────────> System prompt guardrails + Constitutional AI
```

---

## Opus 4.7 프롬프팅 주의사항 (2026-04)

Claude Opus 4.7은 이전 버전과 몇 가지 중요한 해석 차이가 있다.

- **Literal interpretation** — 느슨한 해석을 하지 않음. 의도·제약·수락 기준을 첫 턴에 완전 명세
- **Positive framing 선호** — `"Don't do X"`보다 `"Do Y"`가 더 효과적. 부정형 지시는 예시와 함께 사용
- **Scaffolding 제거** — `"double-check before returning"`, `"N회마다 진행 보고"` 같은 강제 지시는 제거. 4.7은 자체 검증과 progress update를 내장
- **응답 길이 자동 calibration** — 고정 verbosity 지시 대신 예시로 원하는 톤 제시
- **더 direct한 tone** — emoji/validation phrasing 감소. 따뜻한 스타일이 필요하면 명시적 예시 제공

세부: `rules/token-budget.md` · Anthropic Migration Guide 참조

---

## Core Techniques

### Zero-shot

```python
from openai import OpenAI
client = OpenAI()

# Zero-shot: 예시 없이 지시만으로 수행
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "감정 분석기입니다. positive, negative, neutral 중 하나만 답하세요."},
        {"role": "user", "content": "이 제품 정말 실망스럽네요. 환불 받고 싶어요."}
    ]
)
# → "negative"
```

### Few-shot

```python
# Few-shot: 예시를 통해 패턴 학습
messages = [
    {"role": "system", "content": "고객 문의를 카테고리로 분류합니다."},
    {"role": "user", "content": "배송이 너무 늦어요"},
    {"role": "assistant", "content": "카테고리: 배송"},
    {"role": "user", "content": "결제가 두 번 됐어요"},
    {"role": "assistant", "content": "카테고리: 결제"},
    {"role": "user", "content": "사이즈가 안 맞는데 교환 가능한가요?"},
    {"role": "assistant", "content": "카테고리: 교환/반품"},
    # 실제 쿼리
    {"role": "user", "content": "포인트 적립이 안 되었어요"},
]
```

### Chain-of-Thought (CoT)

```python
# CoT: 단계별 추론 유도
cot_prompt = """
문제를 단계별로 풀어보세요.

문제: 한 가게에서 사과 3개를 800원에, 배 2개를 1200원에 샀습니다.
총 과일 수와 총 금액을 구하세요.

풀이:
1단계: 사과 비용 = 3 x 800 = 2,400원
2단계: 배 비용 = 2 x 1,200 = 2,400원
3단계: 총 과일 수 = 3 + 2 = 5개
4단계: 총 금액 = 2,400 + 2,400 = 4,800원

답: 총 5개, 4,800원
"""
```

### ReAct (Reasoning + Acting)

```python
react_system_prompt = """
당신은 도구를 사용해 문제를 해결하는 AI 어시스턴트입니다.

사용 가능한 도구:
- search(query): 웹 검색
- calculator(expression): 수학 계산
- lookup(term): 위키피디아 조회

반드시 다음 형식을 사용하세요:
Thought: 현재 상황 분석과 다음 행동 계획
Action: tool_name(argument)
Observation: 도구 실행 결과
... (반복)
Thought: 최종 결론
Answer: 최종 답변
"""
```

---

## System Prompts

### 효과적인 시스템 프롬프트 구조

```python
system_prompt = """
## 역할
당신은 {domain} 전문가입니다. {specific_capability}을 수행합니다.

## 규칙
1. {constraint_1}
2. {constraint_2}
3. 확실하지 않은 정보는 "확인이 필요합니다"라고 답하세요.

## 출력 형식
{output_format_specification}

## 예시
입력: {example_input}
출력: {example_output}
"""
```

### 실전 예시: 코드 리뷰어

```python
code_reviewer_prompt = """
## 역할
시니어 소프트웨어 엔지니어로서 코드 리뷰를 수행합니다.

## 리뷰 기준
1. 버그 가능성 (severity: critical/warning/info)
2. 보안 취약점 (OWASP Top 10 기준)
3. 성능 이슈
4. 가독성 및 유지보수성

## 출력 형식
각 이슈를 다음 형식으로 보고하세요:
- [severity] 파일:라인 - 설명
- 수정 제안: 코드 또는 설명

## 제약
- 스타일/포매팅 이슈는 무시하세요 (린터가 처리)
- 최대 10개 이슈만 보고하세요 (중요도 순)
- 코드에 문제가 없으면 "LGTM" 으로 답하세요
"""
```

---

## Structured Output

### JSON Mode

```python
response = client.chat.completions.create(
    model="gpt-4o",
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": "JSON 형식으로 응답하세요."},
        {"role": "user", "content": "서울의 날씨 정보를 생성해줘"}
    ]
)
import json
data = json.loads(response.choices[0].message.content)
```

### Structured Output with Pydantic

```python
from pydantic import BaseModel

class ReviewResult(BaseModel):
    sentiment: str  # positive, negative, neutral
    confidence: float
    key_phrases: list[str]
    summary: str

response = client.beta.chat.completions.parse(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "리뷰를 분석하세요."},
        {"role": "user", "content": "배송은 빨랐지만 포장이 엉성했어요."}
    ],
    response_format=ReviewResult,
)

result: ReviewResult = response.choices[0].message.parsed
# ReviewResult(sentiment='negative', confidence=0.72, ...)
```

### Tool / Function Calling

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "특정 도시의 현재 날씨를 조회합니다",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "도시명"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
        }
    }
}]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "서울 날씨 알려줘"}],
    tools=tools,
    tool_choice="auto",
)

tool_call = response.choices[0].message.tool_calls[0]
# Function: get_weather, Args: {"city": "서울", "unit": "celsius"}
```

---

## Advanced Patterns

### Self-Consistency

```python
import collections

def self_consistency(query: str, n_samples: int = 5) -> str:
    """여러 번 추론 후 다수결로 최종 답변 선택"""
    answers = []
    for _ in range(n_samples):
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.7,  # 다양한 추론 경로
            messages=[
                {"role": "system", "content": "단계별로 추론한 후 최종 답변을 [답변: ...]으로 표시하세요."},
                {"role": "user", "content": query}
            ]
        )
        answer = extract_final_answer(response.choices[0].message.content)
        answers.append(answer)

    # 가장 빈번한 답변 선택
    counter = collections.Counter(answers)
    return counter.most_common(1)[0][0]
```

### Prompt Chaining

```python
def analyze_and_recommend(text: str) -> dict:
    """다단계 프롬프트 체이닝: 분석 → 요약 → 추천"""
    # Step 1: 분석
    analysis = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "텍스트의 핵심 주제와 감정을 분석하세요."},
            {"role": "user", "content": text}
        ]
    ).choices[0].message.content

    # Step 2: 분석 결과 기반 요약
    summary = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "분석 결과를 3줄로 요약하세요."},
            {"role": "user", "content": analysis}
        ]
    ).choices[0].message.content

    # Step 3: 요약 기반 행동 추천
    recommendation = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "요약을 바탕으로 구체적인 행동 3가지를 추천하세요."},
            {"role": "user", "content": summary}
        ]
    ).choices[0].message.content

    return {"analysis": analysis, "summary": summary, "recommendation": recommendation}
```

---

## Guardrails

### 입력 검증

```python
import re

def validate_input(user_input: str) -> tuple[bool, str]:
    """사용자 입력 검증"""
    # 길이 제한
    if len(user_input) > 10000:
        return False, "입력이 너무 깁니다 (최대 10,000자)"

    # 프롬프트 인젝션 패턴 탐지
    injection_patterns = [
        r"ignore\s+(previous|above|all)\s+instructions",
        r"you\s+are\s+now\s+",
        r"system\s*:\s*",
        r"<\|im_start\|>",
        r"###\s*(system|instruction)",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            return False, "허용되지 않는 입력 패턴이 감지되었습니다"

    return True, "OK"
```

### 출력 필터링

```python
def filter_output(response: str) -> str:
    """LLM 출력 후처리 필터링"""
    # PII 마스킹
    response = re.sub(
        r'\b\d{3}-\d{4}-\d{4}\b',
        '[전화번호 마스킹]',
        response
    )
    response = re.sub(
        r'\b[\w.-]+@[\w.-]+\.\w+\b',
        '[이메일 마스킹]',
        response
    )

    # URL 필터링 (허용 도메인 외)
    allowed_domains = {"example.com", "docs.python.org"}
    urls = re.findall(r'https?://([^\s/]+)', response)
    for domain in urls:
        if domain not in allowed_domains:
            response = response.replace(domain, "[URL 제거됨]")

    return response
```

---

## Evaluation

### LLM-as-Judge

```python
def llm_judge(question: str, answer: str, reference: str) -> dict:
    """LLM을 평가자로 사용"""
    eval_prompt = f"""
다음 답변을 1-5점으로 평가하세요.

## 평가 기준
- 정확성 (1-5): 참조 답변과 일치하는 정도
- 완전성 (1-5): 질문에 대해 충분히 답변하는 정도
- 명확성 (1-5): 이해하기 쉬운 정도

## 입력
질문: {question}
참조 답변: {reference}
평가 대상: {answer}

JSON 형식으로 답하세요:
{{"accuracy": N, "completeness": N, "clarity": N, "reasoning": "..."}}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": eval_prompt}]
    )
    return json.loads(response.choices[0].message.content)
```

---

## Multi-turn & Memory

### 컨텍스트 관리 전략

| 전략 | 적합한 경우 | 구현 |
|------|-----------|------|
| Sliding Window | 짧은 대화 (< 10턴) | 최근 N턴만 유지 |
| Summary Memory | 긴 대화 | 오래된 대화 LLM 요약 |
| Token Budget | 비용 제한 | 토큰 수 기준 자르기 |
| Hybrid | 프로덕션 | Window + 주기적 요약 |

---

## Cost Optimization

```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """텍스트의 토큰 수 계산"""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))
```

| 전략 | 절감 효과 |
|------|----------|
| 토큰 카운팅으로 사전 비용 예측 | 예산 초과 방지 |
| Prompt compression (LLM으로 압축) | 30-50% 토큰 절감 |
| 캐싱 (동일 쿼리 재사용) | API 호출 50%+ 감소 |
| 작은 모델로 분류 → 큰 모델로 처리 | 80%+ 비용 절감 |

---

## Production Patterns

### 핵심 운영 패턴

```
프롬프트 버전 관리
  - Registry에 version + status(active/canary/deprecated) 관리
  - A/B 테스트: user_id 기반 일관된 variant 할당

에러 처리
  - RateLimitError: exponential backoff 재시도
  - Timeout: 최대 3회 재시도 후 fallback 모델 전환
  - 응답 검증: schema validation으로 출력 형식 보장
```
