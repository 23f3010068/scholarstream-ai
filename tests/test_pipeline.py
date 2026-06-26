"""
<<<<<<< HEAD
tests/test_pipeline.py — Unit tests for ScholarStream AI (LangGraph version).
Run: pytest tests/ -v
=======
tests/test_pipeline.py — Unit tests for ScholarStream AI.
Run with: pytest tests/ -v
>>>>>>> c0cf0277212e1d38ee2e1d0ac67f0932695279e1
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
<<<<<<< HEAD

from src.agents.state import ResearchState
from src.agents.nodes import _find_task, fallback_node
from src.agents.tools import fetch_papers, extract_constraints, write_report
from src.pipeline.batcher import Batcher, chunk_list


# ── Tool tests ─────────────────────────────────────────────────────────────────

def test_fetch_papers_tool():
    result = fetch_papers.invoke({"query": "contrastive learning GNN"})
    assert "fetch_papers" in result
    assert "contrastive learning GNN" in result


def test_extract_constraints_tool():
    result = extract_constraints.invoke({"papers_text": "some paper text"})
    assert "extract_constraints" in result


def test_write_report_tool():
    result = write_report.invoke({"analysis_text": "analysis here"})
    assert "write_report" in result


# ── Helper tests ───────────────────────────────────────────────────────────────

def test_find_task_found():
    tasks = [
        {"id": 1, "agent": "Retriever", "instruction": "fetch papers", "depends_on": []},
        {"id": 2, "agent": "Analyzer",  "instruction": "analyze",      "depends_on": [1]},
    ]
    result = _find_task(tasks, "Retriever")
    assert result["id"] == 1


def test_find_task_not_found():
    result = _find_task([], "Writer")
    assert result is None


# ── Batcher tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batcher_runs_all_items():
    async def worker(item):
=======
from pydantic import ValidationError

from src.agents.base import AgentState, exponential_backoff
from src.agents.planner import FallbackCorrectionAgent, Plan, PlannerAgent, Task
from src.pipeline.batcher import Batcher, chunk_list
from src.pipeline.orchestrator import Orchestrator


# ── Fixtures ───────────────────────────────────────────────────────────────────

VALID_PLAN_JSON = json.dumps({
    "tasks": [
        {"id": 1, "agent": "Retriever", "instruction": "Fetch papers on GNNs", "depends_on": []},
        {"id": 2, "agent": "Analyzer",  "instruction": "Extract constraints",   "depends_on": [1]},
        {"id": 3, "agent": "Writer",    "instruction": "Write abstract",         "depends_on": [2]},
    ]
})

INVALID_PLAN_JSON = "{'tasks': [broken json}"


# ── PlannerAgent ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_planner_returns_valid_plan():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=VALID_PLAN_JSON))])
    )
    agent = PlannerAgent(mock_client)
    plan = await agent.plan("Test research query")
    assert isinstance(plan, Plan)
    assert len(plan.tasks) == 3
    assert plan.tasks[0].agent == "Retriever"


@pytest.mark.asyncio
async def test_planner_raises_on_bad_json():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=INVALID_PLAN_JSON))])
    )
    agent = PlannerAgent(mock_client)
    with pytest.raises(ValueError, match="Malformed planner output"):
        await agent.plan("Test")


# ── Batcher ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batcher_runs_all_items():
    results = []

    async def worker(item):
        results.append(item)
>>>>>>> c0cf0277212e1d38ee2e1d0ac67f0932695279e1
        return item * 2

    batcher = Batcher(max_concurrent=2)
    out = await batcher.run([1, 2, 3, 4, 5], worker)
    assert out == [2, 4, 6, 8, 10]
<<<<<<< HEAD
=======
    assert sorted(results) == [1, 2, 3, 4, 5]
>>>>>>> c0cf0277212e1d38ee2e1d0ac67f0932695279e1


@pytest.mark.asyncio
async def test_batcher_captures_exceptions():
<<<<<<< HEAD
    async def flaky(item):
=======
    async def flaky_worker(item):
>>>>>>> c0cf0277212e1d38ee2e1d0ac67f0932695279e1
        if item == 3:
            raise RuntimeError("deliberate failure")
        return item

    batcher = Batcher(max_concurrent=3)
<<<<<<< HEAD
    out = await batcher.run([1, 2, 3, 4], flaky)
=======
    out = await batcher.run([1, 2, 3, 4], flaky_worker)
>>>>>>> c0cf0277212e1d38ee2e1d0ac67f0932695279e1
    assert out[0] == 1
    assert isinstance(out[2], RuntimeError)


def test_chunk_list():
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert chunk_list([], 3) == []


<<<<<<< HEAD
# ── State schema test ──────────────────────────────────────────────────────────

def test_research_state_keys():
    state: ResearchState = {
        "user_prompt": "test",
        "tasks": [],
        "retriever_output": "",
        "analyzer_output": "",
        "writer_output": "",
        "errors": [],
        "stream_log": [],
    }
    assert state["user_prompt"] == "test"
    assert isinstance(state["tasks"], list)


# ── Fallback node test (mocked LLM) ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_node_repairs_json():
    valid_json = json.dumps({
        "tasks": [{"id": 1, "agent": "Retriever", "instruction": "fetch", "depends_on": []}]
    })
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = valid_json

    async def mock_astream(inputs):
        yield mock_response

    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_response)

    with patch("src.agents.nodes.FALLBACK_PROMPT") as mock_prompt:
        mock_prompt.__or__ = MagicMock(return_value=mock_chain)
        result = await fallback_node({"bad_payload": "{broken"}, mock_chain)
        # fallback returns parsed dict or empty
        assert isinstance(result, dict)
=======
# ── Orchestrator — topological levels ─────────────────────────────────────────

def test_topological_levels_sequential():
    plan = Plan(tasks=[
        Task(id=1, agent="Retriever", instruction="A", depends_on=[]),
        Task(id=2, agent="Analyzer",  instruction="B", depends_on=[1]),
        Task(id=3, agent="Writer",    instruction="C", depends_on=[2]),
    ])
    levels = Orchestrator._topological_levels(plan)
    assert len(levels) == 3
    assert levels[0][0].id == 1
    assert levels[1][0].id == 2
    assert levels[2][0].id == 3


def test_topological_levels_parallel():
    plan = Plan(tasks=[
        Task(id=1, agent="Retriever", instruction="A", depends_on=[]),
        Task(id=2, agent="Analyzer",  instruction="B", depends_on=[]),
        Task(id=3, agent="Writer",    instruction="C", depends_on=[1, 2]),
    ])
    levels = Orchestrator._topological_levels(plan)
    assert len(levels) == 2
    assert {t.id for t in levels[0]} == {1, 2}
    assert levels[1][0].id == 3


# ── exponential_backoff decorator ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backoff_retries_then_succeeds():
    call_count = 0

    @exponential_backoff(max_retries=3, base_delay=0.01)
    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("transient")
        return "ok"

    result = await flaky()
    assert result == "ok"
    assert call_count == 3
>>>>>>> c0cf0277212e1d38ee2e1d0ac67f0932695279e1
