from __future__ import annotations
import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


class Batcher:
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run(self, items: list[Any], worker: Callable[[Any], Awaitable[T]]) -> list[T | Exception]:
        tasks = [self._guarded(worker, item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return list(results)

    async def _guarded(self, worker: Callable, item: Any) -> Any:
        async with self._semaphore:
            logger.debug("Batcher: processing item %r", item)
            return await worker(item)


def chunk_list(items: list, size: int) -> list[list]:
    return [items[i: i + size] for i in range(0, len(items), size)]
