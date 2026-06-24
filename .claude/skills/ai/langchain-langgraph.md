---
name: langchain-langgraph
description: "LangChain & LangGraph — LangChain v0.3 LCEL, LangGraph 에이전트, 멀티 에이전트 오케스트레이션 Use when working with ai 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# LangChain & LangGraph

LangChain v0.3 LCEL, LangGraph 에이전트, 멀티 에이전트 오케스트레이션

## Quick Reference (결정 트리)

```
LLM 앱 구축 방식?
    │
    ├─ 단순 체이닝 ────────> LangChain LCEL (Runnables)
    ├─ 상태 기반 에이전트 ─> LangGraph StateGraph
    ├─ 멀티 에이전트 ──────> LangGraph Multi-Agent
    └─ RAG 파이프라인 ────> LangChain Retrievers + LCEL

LangGraph 패턴?
    │
    ├─ 단일 에이전트 ──────> ReAct Agent (tool calling loop)
    ├─ 순차 파이프라인 ────> Linear Graph (node → node)
    ├─ 조건 분기 ──────────> Conditional Edges
    ├─ 감독자 패턴 ────────> Supervisor Agent
    └─ 계층적 팀 ──────────> Hierarchical Multi-Agent

메모리 전략?
    │
    ├─ 짧은 대화 ──────────> ConversationBufferMemory
    ├─ 긴 대화 ────────────> ConversationSummaryMemory
    ├─ 지속성 필요 ────────> LangGraph Checkpointer
    └─ 커스텀 ─────────────> Custom Memory class
```

---

## LangChain v0.3 LCEL

### LCEL (LangChain Expression Language)

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# LCEL: pipe(|) 연산자로 체이닝
prompt = ChatPromptTemplate.from_messages([
    ("system", "당신은 {role} 전문가입니다."),
    ("user", "{question}"),
])

model = ChatOpenAI(model="gpt-4o", temperature=0)
parser = StrOutputParser()

# 체인 구성: prompt → model → parser
chain = prompt | model | parser

# 실행
result = chain.invoke({"role": "Python", "question": "데코레이터란?"})

# 스트리밍
for chunk in chain.stream({"role": "Python", "question": "제너레이터란?"}):
    print(chunk, end="", flush=True)

# 배치
results = chain.batch([
    {"role": "Python", "question": "리스트 컴프리헨션이란?"},
    {"role": "Go", "question": "고루틴이란?"},
])
```

### Runnables

```python
from langchain_core.runnables import RunnablePassthrough, RunnableParallel, RunnableLambda

# RunnableParallel: 병렬 실행
parallel_chain = RunnableParallel(
    summary=prompt_summary | model | parser,
    keywords=prompt_keywords | model | parser,
)

# RAG 패턴: retriever → format → prompt → model
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

chain = (
    {"context": retriever | RunnableLambda(format_docs), "question": RunnablePassthrough()}
    | prompt | model | parser
)
```

---

## Core Components

### ChatModels

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

# OpenAI
gpt = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=1000)

# Anthropic
claude = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)

# 공통 인터페이스
response = gpt.invoke("안녕하세요")
response = claude.invoke("안녕하세요")
```

### Prompts

```python
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    MessagesPlaceholder,
)

# 기본 프롬프트
prompt = ChatPromptTemplate.from_messages([
    ("system", "당신은 {domain} 전문가입니다."),
    MessagesPlaceholder("history"),  # 대화 이력 삽입
    ("user", "{input}"),
])

# Few-shot 프롬프트
examples = [
    {"input": "좋은 제품이에요", "output": "긍정"},
    {"input": "실망스럽네요", "output": "부정"},
]

example_prompt = ChatPromptTemplate.from_messages([
    ("user", "{input}"),
    ("assistant", "{output}"),
])

few_shot = FewShotChatMessagePromptTemplate(
    example_prompt=example_prompt,
    examples=examples,
)

final_prompt = ChatPromptTemplate.from_messages([
    ("system", "감정 분석기입니다."),
    few_shot,
    ("user", "{input}"),
])
```

### Output Parsers

```python
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

class ReviewAnalysis(BaseModel):
    sentiment: str = Field(description="감정: positive/negative/neutral")
    score: float = Field(description="점수 (0.0 ~ 1.0)")
    summary: str = Field(description="한 줄 요약")

parser = JsonOutputParser(pydantic_object=ReviewAnalysis)

prompt = ChatPromptTemplate.from_messages([
    ("system", "리뷰를 분석하세요.\n{format_instructions}"),
    ("user", "{review}"),
]).partial(format_instructions=parser.get_format_instructions())

chain = prompt | model | parser
result = chain.invoke({"review": "배송은 빨랐지만 포장이 좀..."})
# {'sentiment': 'negative', 'score': 0.35, 'summary': '포장 불만족'}
```

---

## Tool Calling

```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

@tool
def search_database(query: str, limit: int = 5) -> str:
    """데이터베이스에서 정보를 검색합니다."""
    # 실제 DB 검색 로직
    return f"'{query}' 검색 결과 {limit}건"

@tool
def calculate(expression: str) -> str:
    """수학 계산을 수행합니다."""
    return str(eval(expression))  # 프로덕션에서는 안전한 평가기 사용

# 모델에 도구 바인딩
llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools([search_database, calculate])

# 도구 호출 실행
response = llm_with_tools.invoke("2024년 매출을 검색하고 10% 증가율을 계산해줘")

# tool_calls 처리
for tool_call in response.tool_calls:
    print(f"Tool: {tool_call['name']}, Args: {tool_call['args']}")
```

---

## LangGraph Agents

### StateGraph 기본

```python
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# 1. State 정의
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    next_action: str

# 2. Node 함수 정의
def chatbot(state: AgentState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def tool_executor(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    results = []
    for tool_call in last_message.tool_calls:
        result = tool_map[tool_call["name"]].invoke(tool_call["args"])
        results.append({"role": "tool", "content": str(result), "tool_call_id": tool_call["id"]})
    return {"messages": results}

# 3. 조건부 엣지
def should_use_tools(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "end"

# 4. 그래프 구성
graph = StateGraph(AgentState)
graph.add_node("chatbot", chatbot)
graph.add_node("tools", tool_executor)

graph.add_edge(START, "chatbot")
graph.add_conditional_edges("chatbot", should_use_tools, {"tools": "tools", "end": END})
graph.add_edge("tools", "chatbot")  # 도구 결과 → 다시 chatbot

agent = graph.compile()
```

### ReAct Agent (간편 생성)

```python
from langgraph.prebuilt import create_react_agent

# 한 줄로 ReAct 에이전트 생성
agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o"),
    tools=[search_database, calculate],
    prompt="당신은 데이터 분석 어시스턴트입니다.",
)

# 실행
result = agent.invoke({
    "messages": [{"role": "user", "content": "최근 매출 트렌드를 분석해줘"}]
})
```

### Persistence (Checkpointer)

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

# 인메모리 (개발용)
memory = MemorySaver()
agent = graph.compile(checkpointer=memory)

# PostgreSQL (프로덕션)
pg_saver = PostgresSaver.from_conn_string("postgresql://user:pass@localhost/langgraph")
agent = graph.compile(checkpointer=pg_saver)

# thread_id로 대화 이력 관리
config = {"configurable": {"thread_id": "user_123_session_1"}}

# 첫 번째 대화
result1 = agent.invoke(
    {"messages": [{"role": "user", "content": "안녕, 나는 김철수야"}]},
    config=config
)

# 이전 대화 이어서 (같은 thread_id)
result2 = agent.invoke(
    {"messages": [{"role": "user", "content": "내 이름이 뭐라고 했지?"}]},
    config=config
)
# → "김철수라고 하셨습니다."
```

---

## Multi-Agent Patterns

### Supervisor Pattern

```python
from langgraph.graph import StateGraph, START, END

class TeamState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: str

# Supervisor: 다음 에이전트 결정
def supervisor(state: TeamState) -> dict:
    response = llm.invoke([
        {"role": "system", "content": """
팀 감독자입니다. 다음 중 적절한 에이전트를 선택하세요:
- researcher: 정보 검색 및 조사
- coder: 코드 작성 및 리뷰
- writer: 문서 작성 및 편집
- FINISH: 작업 완료
"""},
        *state["messages"]
    ])
    return {"next_agent": parse_agent_name(response.content)}

# 각 에이전트 노드
def researcher(state: TeamState) -> dict:
    result = research_agent.invoke(state["messages"])
    return {"messages": [{"role": "assistant", "content": f"[Researcher] {result}"}]}

def coder(state: TeamState) -> dict:
    result = coding_agent.invoke(state["messages"])
    return {"messages": [{"role": "assistant", "content": f"[Coder] {result}"}]}

def writer(state: TeamState) -> dict:
    result = writing_agent.invoke(state["messages"])
    return {"messages": [{"role": "assistant", "content": f"[Writer] {result}"}]}

# 그래프 구성
graph = StateGraph(TeamState)
graph.add_node("supervisor", supervisor)
graph.add_node("researcher", researcher)
graph.add_node("coder", coder)
graph.add_node("writer", writer)

graph.add_edge(START, "supervisor")
graph.add_conditional_edges("supervisor", lambda s: s["next_agent"], {
    "researcher": "researcher",
    "coder": "coder",
    "writer": "writer",
    "FINISH": END,
})
# 각 에이전트 → supervisor 복귀
for agent_name in ["researcher", "coder", "writer"]:
    graph.add_edge(agent_name, "supervisor")

team = graph.compile()
```

### Hierarchical Pattern

```
┌──────────────────────────────────────┐
│           Top Supervisor              │
│    (전체 프로젝트 관리)                 │
│         │          │                  │
│    ┌────┴────┐ ┌───┴─────┐           │
│    │Research │ │Dev Team │           │
│    │  Team   │ │Supervisor│           │
│    │         │ │  │   │   │           │
│    │ ┌─┐┌─┐ │ │ ┌┴┐ ┌┴┐  │           │
│    │ │R││R│ │ │ │C│ │T│  │           │
│    │ └─┘└─┘ │ │ └─┘ └─┘  │           │
│    └────────┘ └──────────┘           │
└──────────────────────────────────────┘
```

---

## RAG with LangChain

### RAG Chain (LCEL)

```python
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 벡터 스토어 구성
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = FAISS.from_documents(documents, embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# RAG 프롬프트
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", """다음 컨텍스트를 기반으로 질문에 답변하세요.
컨텍스트에 없는 내용은 '해당 정보를 찾을 수 없습니다'라고 답하세요.

컨텍스트:
{context}"""),
    ("user", "{question}"),
])

# RAG 체인
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | rag_prompt
    | ChatOpenAI(model="gpt-4o")
    | StrOutputParser()
)

answer = rag_chain.invoke("프로젝트 일정이 어떻게 되나요?")
```

---

## Streaming

```python
# LCEL 체인 스트리밍
for chunk in chain.stream({"question": "Python이란?"}):
    print(chunk, end="", flush=True)

# 비동기 스트리밍
async for chunk in chain.astream({"question": "Python이란?"}):
    print(chunk, end="", flush=True)

# LangGraph 이벤트 스트리밍 (도구 호출 과정 포함)
async for event in agent.astream_events(
    {"messages": [{"role": "user", "content": "매출 분석해줘"}]},
    version="v2",
):
    if event["event"] == "on_chat_model_stream":
        print(event["data"]["chunk"].content, end="")
```

---

## Production Deployment

```python
# 재시도 + Fallback
robust_chain = chain.with_retry(
    retry_if_exception_type=(TimeoutError, ConnectionError),
    stop_after_attempt=3,
    wait_exponential_jitter=True,
)

reliable_llm = ChatOpenAI(model="gpt-4o").with_fallbacks(
    [ChatOpenAI(model="gpt-4o-mini")]
)

# LangServe: 체인을 REST API로 배포
from langserve import add_routes
add_routes(app, rag_chain, path="/rag")
# → /rag/invoke, /rag/stream, /rag/batch 자동 생성

# LangSmith: 평가 및 모니터링
from langsmith.evaluation import evaluate
results = evaluate(
    lambda inputs: rag_chain.invoke(inputs["question"]),
    data="eval-dataset",
    evaluators=[correctness_evaluator],
)
```

---

## Common Patterns

```python
from langchain_core.runnables import RunnableBranch

# Routing: 쿼리 유형에 따라 다른 체인 실행
route_chain = RunnableBranch(
    (lambda x: "코드" in x["question"], code_chain),
    (lambda x: "검색" in x["question"], search_chain),
    default_chain,
)

# Map-Reduce: 긴 문서 분할 요약
chunk_summaries = map_chain.batch([{"context": c.page_content} for c in chunks])
final = reduce_chain.invoke({"summaries": "\n\n".join(chunk_summaries)})
```
