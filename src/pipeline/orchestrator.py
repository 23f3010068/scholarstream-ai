"""
orchestrator.py — Async DAG runner.
1. Calls PlannerAgent to get an ordered task list.
2. Resolves dependencies so independent tasks run concurrently via asyncio.gather().
3. Streams all agent outputs back to the caller in real-time.
4. Routes LLM/validation failures to FallbackCorrectionAgent before retrying.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

# from openai import AsyncOpenAI
from google import genai

from ..agents.planner import Plan, PlannerAgent, FallbackCorrectionAgent
from ..agents.specialists import RetrieverAgent, AnalyzerAgent, WriterAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordinates the full ScholarStream pipeline end-to-end.

    Usage:
        async for token in Orchestrator(api_key).run(user_prompt):
            print(token, end="", flush=True)
    """

    def __init__(self, api_key: str):
        self._client   = genai.Client(api_key=api_key)
        self._planner  = PlannerAgent(self._client)
        self._fallback = FallbackCorrectionAgent(self._client)
        self._agents   = {
            "Retriever": RetrieverAgent(self._client),
            "Analyzer":  AnalyzerAgent(self._client),
            "Writer":    WriterAgent(self._client),
        }
        # Shared state: task_id → accumulated output string
        self._results: dict[int, str] = {}

    # ── public entry point ─────────────────────────────────────────────────────

    async def run(self, user_prompt: str) -> AsyncGenerator[str, None]:
        yield "⚙️  [Orchestrator] Planning tasks...\n"

        plan = await self._safe_plan(user_prompt)
        yield f"📋 Plan received: {len(plan.tasks)} task(s)\n\n"

        # Group tasks into dependency levels (topological sort)
        levels = self._topological_levels(plan)

        for level_idx, level_tasks in enumerate(levels):
            yield f"--- Level {level_idx + 1}: running {[t.id for t in level_tasks]} concurrently ---\n"

            # Collect per-task async generators
            coros = [
                self._run_task(task) for task in level_tasks
            ]

            # Run this level concurrently; merge streams via asyncio.Queue
            async for chunk in self._merge_streams(coros):
                yield chunk

        yield "\n✅ [Orchestrator] Pipeline complete.\n"

    # ── planning with fallback ─────────────────────────────────────────────────

    async def _safe_plan(self, user_prompt: str) -> Plan:
        try:
            return await self._planner.plan(user_prompt)
        except ValueError as exc:
            logger.warning("Primary planner failed — invoking FallbackCorrectionAgent")
            schema_hint = (
                '{"tasks":[{"id":int,"agent":"Retriever|Analyzer|Writer",'
                '"instruction":str,"depends_on":[int]}]}'
            )
            return await self._fallback.fix(str(exc), schema_hint)

    # ── per-task execution ─────────────────────────────────────────────────────

    async def _run_task(self, task) -> AsyncGenerator[str, None]:
        agent = self._agents.get(task.agent)
        if agent is None:
            yield f"[ERROR] Unknown agent: {task.agent}\n"
            return

        # Build context from upstream dependency outputs
        context = {}
        if "Retriever" in task.agent or task.depends_on:
            context["retriever_output"] = self._results.get(
                self._find_dep_id(task, "Retriever"), ""
            )
            context["analyzer_output"] = self._results.get(
                self._find_dep_id(task, "Analyzer"), ""
            )

        accumulated = []
        try:
            async for chunk in agent.run(task.instruction, context):
                accumulated.append(chunk)
                yield chunk
        except Exception as exc:
            yield f"\n[FAILURE] Task {task.id} ({task.agent}) failed: {exc}\n"

        self._results[task.id] = "".join(accumulated)

    def _find_dep_id(self, task, agent_name: str) -> int | None:
        """Return the task-id of the nearest upstream dep matching agent_name."""
        # Placeholder: the orchestrator stores all results by id; return 0 fallback
        return next(
            (k for k, v in self._results.items() if agent_name.lower() in str(v).lower()),
            0,
        )

    # ── DAG helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _topological_levels(plan: Plan) -> list[list]:
        """
        Kahn's algorithm: returns tasks grouped by execution level.
        Tasks in the same level have no dependency on each other.
        """
        task_map   = {t.id: t for t in plan.tasks}
        in_degree  = {t.id: len(t.depends_on) for t in plan.tasks}
        dependents = {t.id: [] for t in plan.tasks}

        for task in plan.tasks:
            for dep in task.depends_on:
                dependents[dep].append(task.id)

        levels   = []
        frontier = [tid for tid, deg in in_degree.items() if deg == 0]

        while frontier:
            levels.append([task_map[tid] for tid in frontier])
            next_frontier = []
            for tid in frontier:
                for dep in dependents[tid]:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        next_frontier.append(dep)
            frontier = next_frontier

        return levels

    # ── concurrent stream merger ───────────────────────────────────────────────

    @staticmethod
    async def _merge_streams(
        generators: list,
    ) -> AsyncGenerator[str, None]:
        """
        Runs multiple async generators concurrently, forwarding each
        yielded chunk immediately via an asyncio.Queue.
        """
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        active = len(generators)

        async def drain(gen):
            nonlocal active
            async for chunk in gen:
                await queue.put(chunk)
            active -= 1
            await queue.put(None)  # sentinel

        tasks = [asyncio.create_task(drain(g)) for g in generators]

        finished = 0
        while finished < len(generators):
            item = await queue.get()
            if item is None:
                finished += 1
            else:
                yield item

        # Ensure tasks are awaited
        await asyncio.gather(*tasks, return_exceptions=True)
