"""
specialists.py — Retriever, Analyzer, and Writer agents.
Each agent calls the LLM with a specific system prompt, streams token chunks,
and yields them back through the async generator interface defined in BaseAgent.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from .base import BaseAgent, exponential_backoff

logger = logging.getLogger(__name__)

# ── Retriever Agent ────────────────────────────────────────────────────────────

RETRIEVER_SYSTEM = """You are a research retriever.
Given a query, simulate fetching the top 3 relevant academic paper concepts.
For each paper return: title, authors (fictional but realistic), year, and a 2-sentence abstract.
Format your output clearly."""


class RetrieverAgent(BaseAgent):
    """Fetches/simulates paper metadata from external sources."""

    def __init__(self, llm_client: Any):
        super().__init__("RetrieverAgent", llm_client)

    async def _execute(self, instruction: str, context: dict) -> AsyncGenerator[str, None]:
        yield "📡 [Retriever] Querying knowledge base...\n"
        async for chunk in self._stream_llm(instruction):
            yield chunk

    # NEW
    @exponential_backoff(max_retries=4, base_delay=1.0)
    async def _stream_llm(self, instruction: str) -> AsyncGenerator[str, None]:
        async for chunk in await self.llm_client.aio.models.generate_content_stream(
            model="gemini-2.0-flash",
            contents=f"{RETRIEVER_SYSTEM}\n\n{instruction}",
        ):
            if chunk.text:
                yield chunk.text


# ── Analyzer Agent ─────────────────────────────────────────────────────────────

ANALYZER_SYSTEM = """You are a research analyst.
Given retrieved paper summaries, extract:
1. Core architectural constraints or innovations.
2. Shared theoretical assumptions.
3. Identified research gaps.
Be concise and use bullet points."""


class AnalyzerAgent(BaseAgent):
    """Analyzes retrieved papers and extracts structured insights."""

    def __init__(self, llm_client: Any):
        super().__init__("AnalyzerAgent", llm_client)

    async def _execute(self, instruction: str, context: dict) -> AsyncGenerator[str, None]:
        retriever_output = context.get("retriever_output", "")
        prompt = f"Papers:\n{retriever_output}\n\nTask:\n{instruction}"
        yield "🔬 [Analyzer] Extracting architectural constraints...\n"
        async for chunk in self._stream_llm(prompt):
            yield chunk

    # NEW
    @exponential_backoff(max_retries=4, base_delay=1.0)
    async def _stream_llm(self, prompt: str) -> AsyncGenerator[str, None]:
        async for chunk in await self.llm_client.aio.models.generate_content_stream(
            model="gemini-2.0-flash",
            contents=f"{ANALYZER_SYSTEM}\n\n{prompt}",
        ):
            if chunk.text:
                yield chunk.text


# ── Writer Agent ───────────────────────────────────────────────────────────────

WRITER_SYSTEM = """You are a scientific writer.
Given research analysis, write a publication-ready report section that includes:
- A titled abstract (150–200 words)
- A proposed novel architecture description (2–3 paragraphs)
- A future work section (3 bullet points)
Use formal academic language."""


class WriterAgent(BaseAgent):
    """Synthesizes analysis into a publication-ready report section."""

    def __init__(self, llm_client: Any):
        super().__init__("WriterAgent", llm_client)

    async def _execute(self, instruction: str, context: dict) -> AsyncGenerator[str, None]:
        analyzer_output = context.get("analyzer_output", "")
        prompt = f"Analysis:\n{analyzer_output}\n\nTask:\n{instruction}"
        yield "✍️  [Writer] Drafting publication-ready output...\n"
        async for chunk in self._stream_llm(prompt):
            yield chunk

    # NEW
    @exponential_backoff(max_retries=4, base_delay=1.0)
    async def _stream_llm(self, prompt: str) -> AsyncGenerator[str, None]:
        async for chunk in await self.llm_client.aio.models.generate_content_stream(
            model="gemini-2.0-flash",
            contents=f"{WRITER_SYSTEM}\n\n{prompt}",
        ):
            if chunk.text:
                yield chunk.text
