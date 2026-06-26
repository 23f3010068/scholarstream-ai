# ScholarStream AI — System Design Document

## 1. Overview

ScholarStream AI is a LangGraph-based agentic pipeline that accepts a complex research query,
decomposes it into tasks via a Planner node, and routes state through Retriever → Analyzer → Writer
nodes using an explicit directed acyclic graph (DAG). Every LLM call is made through LangChain's
`ChatPromptTemplate | ChatGoogleGenerativeAI` chain pattern with async streaming.

---

## 2. LangChain Components & Why Each Was Chosen

| Component | File | Reason |
|---|---|---|
| `ChatGoogleGenerativeAI` | nodes.py, graph.py | Standardized LLM interface with streaming support |
| `ChatPromptTemplate` | nodes.py | Explicit, inspectable prompt construction |
| `@tool` decorator | tools.py | Declares agent capabilities as first-class LangChain tools |
| `StateGraph` | graph.py | Native DAG — nodes + edges define execution topology |
| `chain.astream()` | nodes.py | True token-level streaming without buffering |

**Not used (intentionally):** `AgentExecutor`, `create_react_agent`, `LangGraph ToolNode`,
built-in memory/checkpointing. These were avoided to keep full visibility into execution flow.

---

## 3. Data Flow

```
User Prompt (CLI)
      │
      ▼
ResearchState initialized (TypedDict)
      │
      ▼
[PlannerNode] — PLANNER_PROMPT | llm.ainvoke() → JSON tasks list
      │  state["tasks"] = [{id, agent, instruction, depends_on}, ...]
      │  On bad JSON → fallback_node() repairs payload
      ▼
[RetrieverNode] — fetch_papers @tool → RETRIEVER_PROMPT | llm.astream()
      │  state["retriever_output"] = streamed paper concepts
      ▼
[AnalyzerNode] — extract_constraints @tool → ANALYZER_PROMPT | llm.astream()
      │  state["analyzer_output"] = streamed analysis bullets
      ▼
[WriterNode] — write_report @tool → WRITER_PROMPT | llm.astream()
      │  state["writer_output"] = streamed academic report
      ▼
END — graph.astream() yields state delta after each node
```

---

## 4. Agent State Machine

```
IDLE → EXECUTING → STREAMING → COMPLETED
              └──→ FAILED (exponential_backoff retries → FallbackNode)
```

---

## 5. Failure Handling

- **Transient** (rate limits/network): `@exponential_backoff` on every `_call_with_retry()` call
- **Structural** (bad JSON from Planner): `fallback_node()` sends repair prompt to Gemini
- **Unknown agent**: Logged and skipped, pipeline continues
