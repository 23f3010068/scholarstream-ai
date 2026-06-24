"""
base.py — Abstract base class for all ScholarStream agents.
Defines the AgentState enum and the BaseAgent interface every agent must implement.
"""
from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    IDLE       = "IDLE"
    EXECUTING  = "EXECUTING"
    STREAMING  = "STREAMING"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"


def exponential_backoff(max_retries: int = 4, base_delay: float = 1.0):
    """
    Decorator: retry the wrapped async function with exponential backoff + jitter.
    Handles transient API errors (rate-limits, network drops).
    """
    def decorator(fn):
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "[Retry %d/%d] %s — sleeping %.2fs",
                        attempt + 1, max_retries, exc, delay
                    )
                    await asyncio.sleep(delay)
        return wrapper
    return decorator


class BaseAgent(ABC):
    """All agents inherit from this class."""

    def __init__(self, name: str, llm_client: Any):
        self.name       = name
        self.llm_client = llm_client
        self.state      = AgentState.IDLE

    # ── public interface ───────────────────────────────────────────────────────

    async def run(self, instruction: str, context: dict | None = None) -> AsyncGenerator[str, None]:
        """Entry point: transitions state, delegates to _execute, handles failures."""
        self.state = AgentState.EXECUTING
        try:
            async for chunk in self._execute(instruction, context or {}):
                self.state = AgentState.STREAMING
                yield chunk
            self.state = AgentState.COMPLETED
        except Exception as exc:
            self.state = AgentState.FAILED
            logger.error("[%s] FAILED: %s", self.name, exc)
            raise

    # ── abstract ───────────────────────────────────────────────────────────────

    @abstractmethod
    async def _execute(
        self, instruction: str, context: dict
    ) -> AsyncGenerator[str, None]:
        """Subclasses implement actual work here."""
        ...
