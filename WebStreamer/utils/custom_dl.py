# WebStreamer/utils/custom_dl.py
# ─────────────────────────────────────────────
#  Parallel MTProto chunk downloader
#  This is what makes downloads FAST
# ─────────────────────────────────────────────

import asyncio
import logging
from typing import AsyncGenerator, Optional, Union

from pyrogram import Client
from pyrogram.raw import functions, types
from pyrogram.raw.types import (
    InputDocumentFileLocation,
    InputPhotoFileLocation,
    InputPeerEmpty,
)
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)

# ── Tuning constants ──────────────────────────────────────
CHUNK_SIZE = 1024 * 1024        # 1MB per chunk (max allowed by Telegram)
PARALLEL_CHUNKS = 4             # Download 4 chunks simultaneously → 4x speed
MAX_RETRIES = 3                 # Retry failed chunks
RETRY_DELAY = 2                 # Seconds between retries


async def _get_file_location(client: Client, message) -> Optional[object]:
    """
    Message se Telegram file location object banao.
    """
    from WebStreamer.utils.file_info import get_media_object
    media = get_media_object(message)
    if not media:
        return None

    # Photo
    if hasattr(media, "sizes"):
        # Largest size lo
        size = max(media.sizes, key=lambda s: getattr(s, "size", 0))
        return InputPhotoFileLocation(
            id=media.id,
            access_hash=media.access_hash,
            file_reference=media.file_reference,
            thumb_size=size.type,
        )

    # Document/Video/Audio/etc.
    return InputDocumentFileLocation(
        id=media.id,
        access_hash=media.access_hash,
        file_reference=media.file_reference,
        thumb_size="",
    )


async def _download_chunk(
    client: Client,
    location,
    offset: int,
    limit: int,
    retries: int = MAX_RETRIES,
) -> bytes:
    """
    Single chunk download with retry logic.
    """
    for attempt in range(retries):
        try:
            r = await client.invoke(
                functions.upload.GetFile(
                    location=location,
                    offset=offset,
                    limit=limit,
                    precise=True,  # Exact offset — important for range requests
                )
            )
            if hasattr(r, "bytes"):
                return r.bytes
            return b""
        except FloodWait as e:
            logger.warning(f"FloodWait {e.value}s on chunk offset={offset}")
            await asyncio.sleep(e.value)
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"Chunk retry {attempt+1}/{retries} offset={offset}: {e}")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"Chunk failed after {retries} retries offset={offset}: {e}")
                return b""
    return b""


async def stream_file(
    client: Client,
    message,
    from_byte: int = 0,
    to_byte: Optional[int] = None,
) -> AsyncGenerator[bytes, None]:
    """
    Fast parallel streaming generator.
    
    Downloads PARALLEL_CHUNKS chunks simultaneously,
    delivers them in order to the HTTP response.
    
    This is 3-5x faster than sequential single-chunk download.
    """
    from WebStreamer.utils.file_info import get_media_object
    media = get_media_object(message)
    if not media:
        return

    file_size = getattr(media, "file_size", 0) or 0
    if to_byte is None or to_byte >= file_size:
        to_byte = file_size - 1

    # Align offset to chunk boundary (Telegram requirement)
    first_chunk_offset = from_byte - (from_byte % CHUNK_SIZE)
    skip_bytes = from_byte - first_chunk_offset  # Bytes to skip in first chunk

    location = await _get_file_location(client, message)
    if not location:
        logger.error("Could not get file location")
        return

    current_offset = first_chunk_offset
    first_chunk = True

    while current_offset <= to_byte:
        # Build parallel task list
        tasks = []
        offsets = []

        for i in range(PARALLEL_CHUNKS):
            chunk_offset = current_offset + (i * CHUNK_SIZE)
            if chunk_offset > to_byte:
                break
            # Last chunk mein sirf zaruri bytes lo
            remaining = to_byte - chunk_offset + 1
            limit = min(CHUNK_SIZE, remaining + (CHUNK_SIZE - remaining % CHUNK_SIZE))
            limit = min(limit, CHUNK_SIZE)  # Never exceed 1MB

            tasks.append(_download_chunk(client, location, chunk_offset, CHUNK_SIZE))
            offsets.append(chunk_offset)

        if not tasks:
            break

        # Parallel download!
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, (chunk_offset, chunk_data) in enumerate(zip(offsets, results)):
            if isinstance(chunk_data, Exception) or not chunk_data:
                logger.error(f"Empty chunk at offset={chunk_offset}")
                continue

            # First chunk: skip bytes before from_byte
            if first_chunk and skip_bytes > 0:
                chunk_data = chunk_data[skip_bytes:]
                first_chunk = False

            # Last relevant chunk: trim extra bytes
            bytes_served_so_far = chunk_offset + (skip_bytes if first_chunk else 0)
            if chunk_offset + len(chunk_data) > to_byte + 1:
                trim_to = to_byte + 1 - chunk_offset
                chunk_data = chunk_data[:trim_to]

            if chunk_data:
                yield chunk_data

        current_offset += CHUNK_SIZE * PARALLEL_CHUNKS
