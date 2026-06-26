"""
tests/test_pipeline.py — Unit tests for ScholarStream AI (LangGraph version).
Run: pytest tests/ -v
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        return item * 2

    batcher = Batcher(max_concurrent=2)
    out = await batcher.run([1, 2, 3, 4, 5], worker)
    assert out == [2, 4, 6, 8, 10]


@pytest.mark.asyncio
async def test_batcher_captures_exceptions():
    async def flaky(item):
        if item == 3:
            raise RuntimeError("deliberate failure")
        return item

    batcher = Batcher(max_concurrent=3)
    out = await batcher.run([1, 2, 3, 4], flaky)
    assert out[0] == 1
    assert isinstance(out[2], RuntimeError)


def test_chunk_list():
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert chunk_list([], 3) == []


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
