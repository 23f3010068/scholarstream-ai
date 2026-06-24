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
