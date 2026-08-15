import asyncio
from collections import defaultdict
from typing import AsyncIterator, Dict, List


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[job_id].append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(job_id, [])
        if queue in subscribers:
            subscribers.remove(queue)
        if not subscribers and job_id in self._subscribers:
            self._subscribers.pop(job_id, None)

    async def publish(self, job_id: str, event: dict) -> None:
        for queue in list(self._subscribers.get(job_id, [])):
            await queue.put(event)

    async def stream(self, job_id: str) -> AsyncIterator[dict]:
        queue = self.subscribe(job_id)
        try:
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(job_id, queue)
