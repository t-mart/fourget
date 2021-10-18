"""Here's the docstring."""
# notions
# queue
# item
# worker_task
# terminating vs non-terminating
from __future__ import annotations

import asyncio
from abc import ABCMeta, abstractmethod
from typing import Any, Callable, Iterable, Optional

import attr


async def worker_task(queue: Queue) -> StopReason:
    """Process items in queue until one of them requests termination."""
    while True:
        item = await queue.get()

        stop_reason = await item.process(queue=queue)

        queue.task_done()

        if stop_reason is not None:
            return stop_reason


class Item(metaclass=ABCMeta):
    """Abstract class for enqueue-able item of work that's processed by worker tasks."""

    @abstractmethod
    async def process(self, queue: Queue) -> Optional[StopReason]:
        """
        Do the "work" of the item.

        Return True if the completion of this item should terminate the queue.
        """
        raise NotImplementedError("Can't process on abstract Item class.")


@attr.s(frozen=True, kw_only=True, auto_attribs=True, order=False)
class StopReason:
    """A data class that holds a str reason message for stopping the queue."""

    reason: str

    def __str__(self) -> str:
        """Return the reason."""
        return self.reason


@attr.s(frozen=True, kw_only=True, auto_attribs=True, order=False)
class Queue:
    """An asyncio.Queue with some additional stuff."""

    _queue: asyncio.Queue[Item]
    stop_reason_callback: Callable[[StopReason], None]

    @classmethod
    def create(
        cls,
        queue_maxsize: int = 0,
        stop_reason_callback: Callable[[StopReason], Any] = lambda sr: ...,
    ) -> Queue:
        """Create a Queue object with a specified maximum size."""
        return cls(
            queue=asyncio.Queue[Item](maxsize=queue_maxsize),
            stop_reason_callback=stop_reason_callback,
        )

    async def complete(self, initial_items: Iterable[Item], worker_count: int) -> None:
        """Put items from initial_items in queue and return a join task."""
        for item in initial_items:
            try:
                self._queue.put_nowait(item)
            except asyncio.QueueFull as qf_exc:
                raise ValueError(
                    "Queue must be sized at least as large as initial_items"
                ) from qf_exc

        tasks: set[asyncio.Task[Optional[StopReason]]] = set()

        async def all_items_processed() -> StopReason:
            await self._queue.join()

            return StopReason(reason="All items processed")

        tasks.add(asyncio.create_task(all_items_processed(), name="joiner"))

        for _ in range(worker_count):
            tasks.add(asyncio.create_task(worker_task(self)))

        done, pending = await asyncio.wait(tasks, return_when="FIRST_COMPLETED")

        # we want exceptions to be raised if they've occured in a task. calling
        # Task.result() will do that (or just return the value of the coro if none was
        # raised).
        for task in done:
            if (stop_reason := task.result()) is not None:
                self.stop_reason_callback(stop_reason)

        for task in pending:
            if not task.done():
                task.cancel()

        await asyncio.gather(*pending, return_exceptions=True)

    async def get(self) -> Item:
        """Remove and return an item from the queue."""
        return await self._queue.get()

    async def put(self, item: Item) -> None:
        """Remove and return an item from the queue."""
        return await self._queue.put(item=item)

    def task_done(self) -> None:
        """Indicate that a formerly enqueued task is complete."""
        return self._queue.task_done()
