# WebStreamer/__main__.py
# ─────────────────────────────────────────────
#  Main entry point — starts bot + web server
# ─────────────────────────────────────────────

import asyncio
import logging
import sys

import uvicorn
from WebStreamer.config import Var
from WebStreamer.bot import initialize_clients, stop_clients
from WebStreamer.server.app import create_app

# ── Logging setup ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Suppress noisy loggers
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main():
    logger.info("=" * 50)
    logger.info("  FastStreamBot Starting...")
    logger.info("=" * 50)

    # Start all bot clients
    await initialize_clients()

    # Create FastAPI app
    app = create_app()

    # Configure uvicorn server
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=Var.PORT,
        loop="asyncio",
        log_level="warning",
        timeout_keep_alive=30,
        limit_concurrency=200,     # Max simultaneous connections
        limit_max_requests=10000,  # Restart worker after N requests (memory)
        h11_max_incomplete_event_size=16384,
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
        logger.info("Bot stopped by user.")
        sys.exit(0)
