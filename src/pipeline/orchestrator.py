"""
orchestrator.py — Async DAG runner.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from google import genai

from ..agents.planner import Plan, PlannerAgent, FallbackCorrectionAgent
from ..agents.specialists import RetrieverAgent, AnalyzerAgent, WriterAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, api_key: str):
        self._client   = genai.Client(api_key=api_key)
        self._planner  = PlannerAgent(self._client)
        self._fallback = FallbackCorrectionAgent(self._client)
        self._agents   = {
            "Retriever": RetrieverAgent(self._client),
            "Analyzer":  AnalyzerAgent(self._client),
            "Writer":    WriterAgent(self._client),
        }
        self._results: dict[int, str] = {}

    async def run(self, user_prompt: str) -> AsyncGenerator[str, None]:
        yield "⚙️  [Orchestrator] Planning tasks...\n"
        plan = await self._safe_plan(user_prompt)
        yield f"📋 Plan received: {len(plan.tasks)} task(s)\n\n"
        levels = self._topological_levels(plan)
        for level_idx, level_tasks in enumerate(levels):
            yield f"--- Level {level_idx + 1}: running {[t.id for t in level_tasks]} concurrently ---\n"
            coros = [self._run_task(task) for task in level_tasks]
            async for chunk in self._merge_streams(coros):
                yield chunk
        yield "\n✅ [Orchestrator] Pipeline complete.\n"

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

    async def _run_task(self, task) -> AsyncGenerator[str, None]:
        agent = self._agents.get(task.agent)
        if agent is None:
            yield f"[ERROR] Unknown agent: {task.agent}\n"
            return
        context = {
            "retriever_output": self._results.get(
                self._find_dep_id(task, "Retriever"), ""
            ),
            "analyzer_output": self._results.get(
                self._find_dep_id(task, "Analyzer"), ""
            ),
        }
        accumulated = []
        try:
            async for chunk in agent.run(task.instruction, context):
                accumulated.append(chunk)
                yield chunk
        except Exception as exc:
            yield f"\n[FAILURE] Task {task.id} ({task.agent}) failed: {exc}\n"
        self._results[task.id] = "".join(accumulated)

    def _find_dep_id(self, task, agent_name: str) -> int | None:
        return next(
            (k for k, v in self._results.items() if agent_name.lower() in str(v).lower()),
            0,
        )

    @staticmethod
    def _topological_levels(plan: Plan) -> list[list]:
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

    @staticmethod
    async def _merge_streams(generators: list) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        active = len(generators)

        async def drain(gen):
            nonlocal active
            async for chunk in gen:
                await queue.put(chunk)
            active -= 1
            await queue.put(None)

        tasks = [asyncio.create_task(drain(g)) for g in generators]
        finished = 0
        while finished < len(generators):
            item = await queue.get()
            if item is None:
                finished += 1
            else:
                yield item
        await asyncio.gather(*tasks, return_exceptions=True)