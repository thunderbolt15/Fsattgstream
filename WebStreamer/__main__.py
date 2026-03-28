# WebStreamer/__main__.py
# ─────────────────────────────────────────────
#  Entry point — Bot + Web server
#  All handlers registered HERE directly
# ─────────────────────────────────────────────

import asyncio
import logging
import sys

import uvicorn
from pyrogram import filters

from WebStreamer.config import Var
from WebStreamer.bot import StreamBot, multi_clients, stop_clients
from WebStreamer.server.app import create_app

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ── Import handler functions ──────────────────────────────
from WebStreamer.bot.plugins.commands import (
    start_handler,
    help_handler,
    status_handler,
    getlink_handler,
    bulklink_handler,
    media_handler,
)

# ── REGISTER ALL HANDLERS DIRECTLY ───────────────────────
SUPPORTED_MEDIA = (
    filters.document
    | filters.video
    | filters.audio
    | filters.voice
    | filters.video_note
    | filters.animation
    | filters.photo
)

StreamBot.on_message(filters.command("start") & filters.private)(start_handler)
StreamBot.on_message(filters.command("help") & filters.private)(help_handler)
StreamBot.on_message(filters.command("status") & filters.private)(status_handler)
StreamBot.on_message(filters.command("getlink") & filters.private)(getlink_handler)
StreamBot.on_message(filters.command("bulklink") & filters.private)(bulklink_handler)
StreamBot.on_message(filters.private & SUPPORTED_MEDIA)(media_handler)

logger.info("All handlers registered successfully")


# ── Main ──────────────────────────────────────────────────
async def main():
    logger.info("=" * 50)
    logger.info("  FastStreamBot Starting...")
    logger.info("=" * 50)

    # 🛑 Ensure Webhook is deleted because Pyrogram uses MTProto
    # If a previous webhook was stuck, Telegram drops MTProto updates silently!
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{Var.BOT_TOKEN}/deleteWebhook?drop_pending_updates=True") as resp:
                logger.info(f"Webhook Clear Response: {await resp.text()}")
    except Exception as e:
        logger.warning(f"Failed to clear webhook: {e}")

    # Start bot
    await StreamBot.start()
    me = await StreamBot.get_me()
    logger.info(f"Main bot started: @{me.username}")
    multi_clients.add(StreamBot)

    # Start worker bots (optional)
    from pyrogram import Client
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
            logger.info(f"Worker {i} started: @{worker_me.username}")
        except Exception as e:
            logger.error(f"Worker {i} failed: {e}")

    logger.info(f"Total clients ready: {multi_clients.count}")

    # Start web server
    app = create_app()
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=Var.PORT,
        loop="asyncio",
        log_level="warning",
        timeout_keep_alive=30,
        limit_concurrency=200,
    )
    server = uvicorn.Server(config)

    logger.info(f"Server starting on port {Var.PORT}")
    logger.info(f"Public URL: {Var.FQDN}")

    try:
        await server.serve()
    finally:
        logger.info("Shutting down...")
        await stop_clients()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped.")
        sys.exit(0)
