# WebStreamer/server/stream_routes.py
# ─────────────────────────────────────────────
#  FastAPI streaming routes
#  Smart: CDN redirect ≤20MB, parallel stream >20MB
# ─────────────────────────────────────────────

import logging
import time
from collections import defaultdict
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import (
    RedirectResponse,
    StreamingResponse,
    JSONResponse,
    HTMLResponse,
)

from WebStreamer.config import Var
from WebStreamer.bot import StreamBot, multi_clients
from WebStreamer.utils.secure_link import verify_token
from WebStreamer.utils.file_info import get_media_info, get_media_object
from WebStreamer.utils.custom_dl import stream_file

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Constants ─────────────────────────────────────────────
BOT_API_LIMIT = 20 * 1024 * 1024   # 20MB — Telegram Bot API get_file() limit
RATE_LIMIT_REQUESTS = 30            # per window per IP
RATE_LIMIT_WINDOW = 60              # seconds

# ── Rate limiter storage (in-memory) ──────────────────────
_rate_store: dict = defaultdict(list)


def _is_rate_limited(ip: str) -> bool:
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW
    _rate_store[ip] = [t for t in _rate_store[ip] if t > cutoff]
    if len(_rate_store[ip]) >= RATE_LIMIT_REQUESTS:
        return True
    _rate_store[ip].append(now)
    return False


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


# ── CDN URL cache (in-memory, TTL ~55 min) ────────────────
_cdn_cache: dict = {}
_cdn_cache_ttl: dict = {}
CDN_CACHE_DURATION = 3300  # 55 minutes


def _get_cached_cdn(file_id: str):
    if file_id in _cdn_cache:
        if time.time() < _cdn_cache_ttl.get(file_id, 0):
            return _cdn_cache[file_id]
        else:
            del _cdn_cache[file_id]
            del _cdn_cache_ttl[file_id]
    return None


def _set_cdn_cache(file_id: str, url: str):
    _cdn_cache[file_id] = url
    _cdn_cache_ttl[file_id] = time.time() + CDN_CACHE_DURATION


# ── Homepage ──────────────────────────────────────────────
@router.get("/")
async def homepage():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FastStreamBot</title>
        <style>
            body { font-family: sans-serif; text-align: center; padding: 50px; background: #0f0f0f; color: #fff; }
            h1 { color: #00d4ff; }
            p { color: #aaa; }
            a { color: #00d4ff; text-decoration: none; }
        </style>
    </head>
    <body>
        <h1>⚡ FastStreamBot</h1>
        <p>Telegram File Streaming Server is running.</p>
        <p>Send files to the bot on Telegram to get download links.</p>
    </body>
    </html>
    """)


# ── Main download endpoint ─────────────────────────────────
@router.get("/{token}/{filename:path}")
@router.get("/{token}")
async def download_handler(
    request: Request,
    token: str,
    filename: str = "",
):
    """
    Smart download handler:
    - Token verify karo (expiry + HMAC)
    - File ≤ 20MB → Telegram CDN redirect (zero server bandwidth)
    - File > 20MB → Parallel multi-bot server stream (fast)
    """

    # ── Rate limiting ──────────────────────────────────────
    ip = _get_ip(request)
    if _is_rate_limited(ip):
        return JSONResponse(
            {"error": "Too many requests. Please wait 60 seconds."},
            status_code=429,
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    # ── Token verify ───────────────────────────────────────
    msg_id, err = verify_token(token)
    if err:
        messages = {
            "expired": "⏰ This link has expired. Please send the file again to the bot.",
            "invalid_sig": "🔒 Invalid link. Tampering detected.",
            "bad_format": "❌ Malformed link.",
        }
        return JSONResponse(
            {"error": messages.get(err, "Invalid link.")},
            status_code=410 if err == "expired" else 403,
        )

    # ── Fetch message from BIN_CHANNEL ────────────────────
    try:
        message = await StreamBot.get_messages(
            chat_id=Var.BIN_CHANNEL,
            message_ids=msg_id,
        )
    except Exception as e:
        logger.error(f"get_messages failed msg_id={msg_id}: {e}")
        return JSONResponse({"error": "Failed to fetch file from Telegram."}, status_code=500)

    if not message or message.empty:
        return JSONResponse({"error": "File not found or deleted."}, status_code=404)

    # ── Get file info ─────────────────────────────────────
    file_id, file_name, file_size = get_media_info(message)
    if not file_id:
        return JSONResponse({"error": "No media in this message."}, status_code=404)

    file_size = file_size or 0

    # Use filename from URL if provided
    if filename:
        display_name = filename.split("/")[-1]
    else:
        display_name = file_name

    # ── Try CDN redirect for small files (≤ 20MB) ────────
    if file_size <= BOT_API_LIMIT and file_size > 0:
        # Check cache first
        cdn_url = _get_cached_cdn(file_id)

        if not cdn_url:
            try:
                tg_file = await StreamBot.get_file(file_id)
                cdn_url = f"https://api.telegram.org/file/bot{Var.BOT_TOKEN}/{tg_file.file_path}"
                _set_cdn_cache(file_id, cdn_url)
            except Exception as e:
                logger.warning(f"get_file() failed, falling back to stream: {e}")
                cdn_url = None

        if cdn_url:
            logger.info(f"[CDN-REDIRECT] msg={msg_id} size={file_size} ip={ip}")
            return RedirectResponse(url=cdn_url, status_code=302)

    # ── Server streaming for large files (> 20MB) ─────────
    logger.info(f"[SERVER-STREAM] msg={msg_id} size={file_size} ip={ip}")
    return await _serve_stream(request, message, display_name, file_size)


async def _serve_stream(
    request: Request,
    message,
    file_name: str,
    file_size: int,
) -> StreamingResponse:
    """
    Optimized parallel chunk streaming with HTTP Range support.
    Enables video seeking, resumable downloads, parallel chunks.
    """
    media = get_media_object(message)
    mime_type = (
        getattr(media, "mime_type", None) or "application/octet-stream"
    ) if media else "application/octet-stream"

    # ── Parse Range header ────────────────────────────────
    from_byte = 0
    to_byte = max(0, file_size - 1)
    status_code = 200

    range_header = request.headers.get("Range", "")
    if range_header.startswith("bytes="):
        try:
            parts = range_header[6:].split("-")
            from_byte = int(parts[0]) if parts[0] else 0
            to_byte = int(parts[1]) if (len(parts) > 1 and parts[1]) else file_size - 1
            to_byte = min(to_byte, file_size - 1)
            status_code = 206
        except (ValueError, IndexError):
            from_byte, to_byte = 0, file_size - 1

    content_length = max(0, to_byte - from_byte + 1)

    # ── Select fastest available client (round-robin) ────
    client = await multi_clients.get()

    # ── Response headers ──────────────────────────────────
    headers = {
        "Content-Type": mime_type,
        "Content-Length": str(content_length),
        "Content-Range": f"bytes {from_byte}-{to_byte}/{file_size}",
        "Content-Disposition": f'attachment; filename="{quote(file_name)}"',
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
        "X-Client": f"worker/{multi_clients.count}",
    }

    return StreamingResponse(
        content=stream_file(client, message, from_byte, to_byte),
        status_code=status_code,
        headers=headers,
        media_type=mime_type,
    )
