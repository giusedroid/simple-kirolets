import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager


SendMessage = Callable[[str], Awaitable[None]]


@asynccontextmanager
async def progress_updates(send_message: SendMessage, message: str, every_seconds: int):
    stop_event = asyncio.Event()

    async def heartbeat() -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=every_seconds)
            except TimeoutError:
                await send_message(message)

    task = asyncio.create_task(heartbeat())
    try:
        yield
    finally:
        stop_event.set()
        await task
