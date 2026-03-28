# WebStreamer/bot/__init__.py

import asyncio
import itertools
import logging
from typing import List

from pyrogram import Client
from WebStreamer.config import Var

logger = logging.getLogger(__name__)

# Main bot — NO plugins parameter, handlers registered manually in __main__.py
StreamBot = Client(
    name="StreamBot",
    api_id=Var.API_ID,
    api_hash=Var.API_HASH,
    bot_token=Var.BOT_TOKEN,
    sleep_threshold=10,
    no_updates=False,
)


class MultiClientManager:
    def __init__(self):
        self._clients: List[Client] = []
        self._cycle = None
        self._lock = asyncio.Lock()

    def add(self, client: Client):
        self._clients.append(client)
        self._cycle = itertools.cycle(self._clients)

    async def get(self) -> Client:
        if not self._clients:
            return StreamBot
        async with self._lock:
            return next(self._cycle)

    @property
    def count(self) -> int:
        return len(self._clients)

    @property
    def all(self) -> List[Client]:
        return self._clients


multi_clients = MultiClientManager()


async def stop_clients():
    for client in multi_clients.all:
        try:
            await client.stop()
        except Exception:
            pass
