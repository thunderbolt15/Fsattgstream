# WebStreamer/bot/__init__.py

import asyncio
import logging
import itertools
from typing import List

from pyrogram import Client
from WebStreamer.config import Var

logger = logging.getLogger(__name__)

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


async def initialize_clients():
    from WebStreamer.bot.plugins import commands  # noqa
    await StreamBot.start()
    me = await StreamBot.get_me()
    logger.info(f"Main bot started: @{me.username}")
    multi_clients.add(StreamBot)
    for i, token in enumerate(Var.MULTI_TOKENS, start=1):
        try:
            worker = Client(
                name=f"Worker_{i}",
                api_id=Var.API_ID,
                api_hash=Var.API_HASH,
                bot_token=token,
                sleep_threshold=10,
                no_updates=True,
            )
            await worker.start()
            worker_me = await worker.get_me()
            multi_clients.add(worker)
            logger.info(f"Worker bot {i} started: @{worker_me.username}")
        except Exception as e:
            logger.error(f"Failed to start worker bot {i}: {e}")
    logger.info(f"Total clients ready: {multi_clients.count}")


async def stop_clients():
    for client in multi_clients.all:
        try:
            await client.stop()
        except Exception:
            pass
