# 📚 ScholarStream AI
> Automated Research & Literature Review Engine — Agentic AI System (Task 1)

A native-Python async pipeline that accepts a complex research query, decomposes it into a
Directed Acyclic Graph (DAG) of tasks, runs three specialized agents concurrently, and streams
partial outputs to the terminal in real-time.

## Architecture

```
[ Complex User Prompt ]
        │
        ▼
 ┌─────────────────┐
 │  PlannerAgent   │  (JSON-mode LLM → Pydantic-validated Plan)
 └────────┬────────┘
          │  On bad JSON → FallbackCorrectionAgent
          ▼
 ┌──────────────────────┐
 │  Orchestrator (DAG)  │  topological_levels() + asyncio.gather()
 └──────┬───────────────┘
        │
   Level 0 (parallel)          Level 1
   ┌────┴────┐                     │
   ▼         ▼                     ▼
Retriever  Analyzer  ──────►  WriterAgent
   │         │
   └────┬────┘
        ▼
  asyncio.Queue (merged stream)
        │
        ▼
  [ Streamed Output → CLI ]
```

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/YOUR_USERNAME/scholarstream-ai.git
cd scholarstream-ai

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API key
cp .env.example .env
# Edit .env and paste your OPENAI_API_KEY

# 5. Run the pipeline
python -m src.main

# 6. Custom prompt
python -m src.main --prompt "Analyze transformers for time-series forecasting"

# 7. Demo failure handling (no valid key needed)
python -m src.main --demo-failure
```

## Run Tests

```bash
pytest tests/ -v
```

## File Structure

```
scholarstream/
├── .github/workflows/ci.yml   # GitHub Actions: lint + test
├── src/
│   ├── agents/
│   │   ├── base.py            # BaseAgent, AgentState, @exponential_backoff
│   │   ├── planner.py         # PlannerAgent + FallbackCorrectionAgent
│   │   └── specialists.py     # RetrieverAgent, AnalyzerAgent, WriterAgent
│   ├── pipeline/
│   │   ├── orchestrator.py    # Async DAG runner + stream merger
│   │   └── batcher.py         # Manual batching via asyncio.Semaphore
│   └── main.py                # CLI entrypoint (rich output)
├── docs/system_design.md
├── tests/test_pipeline.py
├── POST_MORTEM.md
├── requirements.txt
└── README.md
```

## Key Engineering Decisions

| Concern | Solution |
|---|---|
| No black-box frameworks | Native `openai` + `asyncio` only |
| Structured LLM output | `response_format={"type":"json_object"}` + Pydantic |
| Transient failures | `@exponential_backoff` decorator with jitter |
| Structural failures | `FallbackCorrectionAgent` repairs bad JSON |
| Concurrency | `asyncio.gather()` per DAG level |
| Rate-limit safety | `asyncio.Semaphore(3)` in `Batcher` |
| Streaming | `async for` generators + `asyncio.Queue` merge |

## Deliverables Checklist

- [x] GitHub repository with clean commits
- [x] `docs/system_design.md` — architecture + data flow
- [x] `POST_MORTEM.md` — scaling issue, design change, 2 trade-offs
- [ ] 3–5 minute demo video (record after running `python -m src.main --demo-failure`)
