"""
tests/test_pipeline.py — Unit tests for ScholarStream AI.
Run with: pytest tests/ -v
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
        return item * 2

    batcher = Batcher(max_concurrent=2)
    out = await batcher.run([1, 2, 3, 4, 5], worker)
    assert out == [2, 4, 6, 8, 10]
    assert sorted(results) == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_batcher_captures_exceptions():
    async def flaky_worker(item):
        if item == 3:
            raise RuntimeError("deliberate failure")
        return item

    batcher = Batcher(max_concurrent=3)
    out = await batcher.run([1, 2, 3, 4], flaky_worker)
    assert out[0] == 1
    assert isinstance(out[2], RuntimeError)


def test_chunk_list():
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert chunk_list([], 3) == []


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
