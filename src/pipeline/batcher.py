"""
batcher.py — Manual batching with explicit concurrency control.
Uses asyncio.Semaphore to cap concurrent workers; never a black-box abstraction.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


class Batcher:
    """
    Splits an iterable of items into explicit batches and runs them with a
    capped concurrency (default 3 concurrent workers at a time).
    """

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run(
        self,
        items: list[Any],
        worker: Callable[[Any], Awaitable[T]],
    ) -> list[T | Exception]:
        """
        Runs `worker` on every item.  Results preserve input order.
        Exceptions are captured per-item (not raised), so one failure
        never aborts the entire batch.
        """
        tasks = [self._guarded(worker, item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return list(results)

    async def _guarded(self, worker: Callable, item: Any) -> Any:
        async with self._semaphore:
            logger.debug("Batcher: processing item %r", item)
            return await worker(item)


# ── Convenience: chunk a flat list into sub-lists of `size` ───────────────────

def chunk_list(items: list, size: int) -> list[list]:
    """Split items into consecutive sub-lists of at most `size` elements."""
    return [items[i : i + size] for i in range(0, len(items), size)]
