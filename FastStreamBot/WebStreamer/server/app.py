# WebStreamer/server/app.py
# ─────────────────────────────────────────────
#  FastAPI application factory
# ─────────────────────────────────────────────

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from WebStreamer.server.stream_routes import router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="FastStreamBot",
        description="High-speed Telegram file streaming server",
        version="2.0.0",
        docs_url=None,   # Disable Swagger (not needed in production)
        redoc_url=None,
    )

    # CORS — Allow all origins (files are meant to be publicly accessible)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "HEAD", "OPTIONS"],
        allow_headers=["Range", "Content-Type"],
        expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
    )

    # Include routes
    app.include_router(router)

    return app
