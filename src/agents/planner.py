"""
planner.py — Planner / Decomposer Agent.
Uses JSON-mode Structured Outputs to convert a complex user prompt
into an ordered DAG of tasks (array of {id, agent, instruction, depends_on}).
Also contains the FallbackCorrectionAgent that fixes malformed JSON payloads.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from pydantic import BaseModel, ValidationError

from .base import BaseAgent, exponential_backoff

logger = logging.getLogger(__name__)

# ── Pydantic schema for planner output ────────────────────────────────────────

class Task(BaseModel):
    id:          int
    agent:       str          # "Retriever" | "Analyzer" | "Writer"
    instruction: str
    depends_on:  list[int] = []

class Plan(BaseModel):
    tasks: list[Task]


# ── Planner Agent ──────────────────────────────────────────────────────────────

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
    """Breaks a user prompt into an ordered task graph."""

    def __init__(self, llm_client: Any):
        super().__init__("PlannerAgent", llm_client)

    async def plan(self, user_prompt: str) -> Plan:
        """Returns a validated Plan. Raises on unrecoverable failure."""
        raw = await self._call_llm(user_prompt)
        return self._parse_plan(raw)

    @exponential_backoff(max_retries=4, base_delay=1.0)
    async def _call_llm(self, user_prompt: str) -> str:
        response = await self.llm_client.chat.completions.create(
            model="gemini-2.0-flash",
            contents=f"{PLANNER_SYSTEM}\n\nUser query: {user_prompt}",
            config={"response_mime_type": "application/json"},
        )
        return response.choices[0].message.content

    def _parse_plan(self, raw: str) -> Plan:
        try:
            data = json.loads(raw)
            return Plan(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Planner returned bad JSON — routing to FallbackAgent: %s", exc)
            raise ValueError(f"Malformed planner output: {exc}") from exc

    # _execute is only used if you want streaming status lines
    async def _execute(self, instruction: str, context: dict) -> AsyncGenerator[str, None]:
        plan = await self.plan(instruction)
        yield json.dumps(plan.model_dump(), indent=2)


# ── Fallback / Correction Agent ────────────────────────────────────────────────

FALLBACK_SYSTEM = """You are a JSON repair assistant.
You will receive a broken JSON string and the schema it must match.
Return ONLY the corrected, valid JSON. No prose."""

class FallbackCorrectionAgent(BaseAgent):
    """Receives a bad JSON payload and returns a corrected version."""

    def __init__(self, llm_client: Any):
        super().__init__("FallbackCorrectionAgent", llm_client)

    async def fix(self, bad_payload: str, schema_hint: str) -> Plan:
        corrected = await self._repair(bad_payload, schema_hint)
        data = json.loads(corrected)
        return Plan(**data)

    # NEW
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
