# 📚 ScholarStream AI — LangGraph Edition
> Agentic Research & Literature Review Engine | Task 1

Built with **LangChain + LangGraph + Gemini**. A fully agentic pipeline that decomposes a complex
research query into a DAG of specialized agents, streams outputs in real-time, and handles failures gracefully.

## Architecture

```
[ User Prompt ]
      │
      ▼
┌─────────────┐     LangGraph StateGraph
│ PlannerNode │ ── ChatPromptTemplate + Gemini JSON mode
└──────┬──────┘
       │  state["tasks"] populated
       ▼
┌──────────────────┐
│ RetrieverNode    │ ── @tool: fetch_papers → PromptTemplate → llm.astream()
└──────┬───────────┘
       │  state["retriever_output"] populated
       ▼
┌──────────────────┐
│ AnalyzerNode     │ ── @tool: extract_constraints → PromptTemplate → llm.astream()
└──────┬───────────┘
       │  state["analyzer_output"] populated
       ▼
┌──────────────────┐
│ WriterNode       │ ── @tool: write_report → PromptTemplate → llm.astream()
└──────┬───────────┘
       │  state["writer_output"] populated
       ▼
    [ END ]
```

## LangChain Components Used

| Component | Where | Purpose |
|---|---|---|
| `ChatGoogleGenerativeAI` | All nodes | LLM interface |
| `ChatPromptTemplate` | All nodes | Structured prompts |
| `@tool` decorator | `tools.py` | Explicit tool definitions |
| `StateGraph` | `graph.py` | DAG orchestration |
| `langgraph` edges | `graph.py` | Node routing |
| `chain.astream()` | All nodes | Real-time token streaming |

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/scholarstream-ai.git
cd scholarstream-ai

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # Mac/Linux

pip install -r requirements.txt

cp .env.example .env
# paste your GOOGLE_API_KEY in .env

python -m src.main
python -m src.main --prompt "Analyze transformers for time-series forecasting"
python -m src.main --demo-failure    # failure handling demo
```

## Run Tests

```bash
pytest tests/ -v
```

## File Structure

```
scholarstream/
├── .github/workflows/ci.yml
├── src/
│   ├── agents/
│   │   ├── state.py        # ResearchState TypedDict (shared LangGraph state)
│   │   ├── tools.py        # LangChain @tool decorated tools
│   │   └── nodes.py        # LangGraph node functions (Planner, Retriever, Analyzer, Writer, Fallback)
│   ├── pipeline/
│   │   ├── graph.py        # LangGraph StateGraph — DAG definition
│   │   └── batcher.py      # Manual asyncio.Semaphore batching
│   └── main.py
├── docs/system_design.md
├── tests/test_pipeline.py
├── POST_MORTEM.md
└── requirements.txt
```
