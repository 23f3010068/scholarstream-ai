<<<<<<< HEAD
# ScholarStream AI — System Design Document (LangGraph Edition)

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
=======
# ScholarStream AI — System Design Document

## 1. Overview

ScholarStream AI is an agentic research pipeline that accepts a complex research hypothesis,
decomposes it into a Directed Acyclic Graph (DAG) of tasks, runs specialized agents
concurrently via Python's native `asyncio`, and streams partial outputs to the user in real-time.

---

## 2. Data Flow

```
User Prompt (CLI)
       │
       ▼
 ┌─────────────────┐
 │  PlannerAgent   │  → JSON-mode LLM call → Pydantic-validated Plan (list of Tasks)
 └────────┬────────┘
          │ On bad JSON → FallbackCorrectionAgent repairs payload
          ▼
 ┌──────────────────────┐
 │  Orchestrator (DAG)  │  topological_levels() groups tasks by dependency depth
 └──────┬───────────────┘
        │
   Level 0 (no deps)              Level 1 (deps satisfied)
        ├──────────────────┐             │
        ▼                  ▼             ▼
 RetrieverAgent    AnalyzerAgent    WriterAgent
        │                  │             │
        └──────┬────────────┘             │
               ▼                          │
          asyncio.Queue  ◄────────────────┘
               │
               ▼
      Streamed token chunks → CLI (rich console)
```

### Token journey

1. **User prompt** → string passed to `Orchestrator.run()`
2. **Planner** → LLM call with `response_format={"type":"json_object"}` → parsed into `Plan`
3. **Task Queue** → `_topological_levels()` (Kahn's algorithm) groups tasks into levels
4. **Level execution** → `asyncio.gather()` per level; each task is an async generator
5. **Merge** → `_merge_streams()` drains all generators into a shared `asyncio.Queue`
6. **Output** → chunks yielded to CLI as they arrive (true streaming, no buffering)

---

## 3. Agent State Machine

Each agent transitions through the following states:

```
IDLE ──► EXECUTING ──► STREAMING ──► COMPLETED
                  │
                  └──► FAILED (caught by Orchestrator, logged, stream annotated)
```

| State      | Description                                        |
|------------|----------------------------------------------------|
| IDLE       | Agent instantiated, awaiting a task                |
| EXECUTING  | `run()` called; LLM call in progress               |
| STREAMING  | First token received; chunks being yielded         |
| COMPLETED  | Generator exhausted; result stored in `_results`   |
| FAILED     | Exception raised; error message yielded to stream  |

---

## 4. Failure Handling Strategy

### Transient Failures (API Rate Limits / Network Drops)
Handled by the `@exponential_backoff` decorator on every LLM call:
- Retries up to 4 times with `delay = base * 2^attempt + random(0,1)` seconds
- Jitter prevents thundering-herd when multiple agents hit limits simultaneously

### Structural Failures (Malformed LLM Output)
- `PlannerAgent._parse_plan()` catches `json.JSONDecodeError` and `pydantic.ValidationError`
- Routes payload to `FallbackCorrectionAgent` which sends a repair prompt to the LLM
- If the fallback also fails, the exception propagates up and the Orchestrator annotates the stream

---

## 5. Concurrency Model

```
asyncio event loop
│
├── Orchestrator._run_task(task_A) ──► RetrieverAgent._stream_llm()  (Level 0)
├── Orchestrator._run_task(task_B) ──► AnalyzerAgent._stream_llm()   (Level 0)
│         both drained into asyncio.Queue by _merge_streams()
│
└── Orchestrator._run_task(task_C) ──► WriterAgent._stream_llm()     (Level 1)
```

Independent tasks at the same dependency level run inside `asyncio.gather()`,
which interleaves I/O waits without OS threads. Batching (max 3 concurrent workers)
is enforced in `Batcher` via `asyncio.Semaphore(3)`.

---

## 6. Repository Structure

```
scholarstream/
├── .github/workflows/ci.yml   # Lint + test on every push
├── src/
│   ├── agents/
│   │   ├── base.py            # BaseAgent, AgentState, exponential_backoff
│   │   ├── planner.py         # PlannerAgent, FallbackCorrectionAgent
│   │   └── specialists.py     # RetrieverAgent, AnalyzerAgent, WriterAgent
│   ├── pipeline/
│   │   ├── orchestrator.py    # DAG runner, stream merger
│   │   └── batcher.py         # Manual batching with Semaphore
│   └── main.py                # CLI entrypoint
├── docs/
│   └── system_design.md       # ← this file
├── tests/
│   └── test_pipeline.py
├── POST_MORTEM.md
├── requirements.txt
└── README.md
```
>>>>>>> c0cf0277212e1d38ee2e1d0ac67f0932695279e1
