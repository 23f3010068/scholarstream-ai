"""
planner.py — Planner / Decomposer Agent (Gemini version).
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from pydantic import BaseModel, ValidationError

from .base import BaseAgent, exponential_backoff

logger = logging.getLogger(__name__)


class Task(BaseModel):
    id:          int
    agent:       str
    instruction: str
    depends_on:  list[int] = []

class Plan(BaseModel):
    tasks: list[Task]


PLANNER_SYSTEM = """You are a research planning assistant.
Given a complex research query, decompose it into an ordered list of tasks.
Each task must be assigned to one of three agents: Retriever, Analyzer, or Writer.
Return ONLY valid JSON matching this schema:
{
  "tasks": [
    {"id": 1, "agent": "Retriever", "instruction": "...", "depends_on": []},
    ...
  ]
}
Never add prose outside the JSON block."""


class PlannerAgent(BaseAgent):
    def __init__(self, llm_client: Any):
        super().__init__("PlannerAgent", llm_client)

    async def plan(self, user_prompt: str) -> Plan:
        raw = await self._call_llm(user_prompt)
        return self._parse_plan(raw)

    @exponential_backoff(max_retries=4, base_delay=1.0)
    async def _call_llm(self, user_prompt: str) -> str:
        response = await self.llm_client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"{PLANNER_SYSTEM}\n\nUser query: {user_prompt}",
            config={"response_mime_type": "application/json"},
        )
        return response.text

    def _parse_plan(self, raw: str) -> Plan:
        try:
            data = json.loads(raw)
            return Plan(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Planner returned bad JSON — routing to FallbackAgent: %s", exc)
            raise ValueError(f"Malformed planner output: {exc}") from exc

    async def _execute(self, instruction: str, context: dict) -> AsyncGenerator[str, None]:
        plan = await self.plan(instruction)
        yield json.dumps(plan.model_dump(), indent=2)


FALLBACK_SYSTEM = """You are a JSON repair assistant.
You will receive a broken JSON string and the schema it must match.
Return ONLY the corrected, valid JSON. No prose."""

class FallbackCorrectionAgent(BaseAgent):
    def __init__(self, llm_client: Any):
        super().__init__("FallbackCorrectionAgent", llm_client)

    async def fix(self, bad_payload: str, schema_hint: str) -> Plan:
        corrected = await self._repair(bad_payload, schema_hint)
        data = json.loads(corrected)
        return Plan(**data)

    @exponential_backoff(max_retries=3, base_delay=0.5)
    async def _repair(self, bad_payload: str, schema_hint: str) -> str:
        response = await self.llm_client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"{FALLBACK_SYSTEM}\n\nSchema: {schema_hint}\n\nBroken payload:\n{bad_payload}",
            config={"response_mime_type": "application/json"},
        )
        return response.text

    async def _execute(self, instruction: str, context: dict) -> AsyncGenerator[str, None]:
        yield await self._repair(instruction, context.get("schema", ""))