# WebStreamer/utils/file_info.py
# ─────────────────────────────────────────────
#  Media object + file info extraction helpers
# ─────────────────────────────────────────────

from typing import Optional, Tuple

MEDIA_ATTRS = (
    "document", "video", "audio", "voice",
    "video_note", "animation", "sticker",
)

MIME_TO_FILENAME = {
    "video/mp4": "video.mp4",
    "video/x-matroska": "video.mkv",
    "video/webm": "video.webm",
    "video/avi": "video.avi",
    "video/quicktime": "video.mov",
    "audio/mpeg": "audio.mp3",
    "audio/ogg": "audio.ogg",
    "audio/flac": "audio.flac",
    "audio/x-wav": "audio.wav",
    "image/jpeg": "image.jpg",
    "image/png": "image.png",
    "image/gif": "image.gif",
    "image/webp": "image.webp",
    "application/zip": "archive.zip",
    "application/pdf": "document.pdf",
    "application/x-rar-compressed": "archive.rar",
    "application/octet-stream": "file.bin",
}


def get_media_object(message) -> Optional[object]:
    """Message se media object return karo."""
    for attr in MEDIA_ATTRS:
        media = getattr(message, attr, None)
        if media:
            return media
    # Photo (largest size)
    if getattr(message, "photo", None):
        return message.photo
    return None


def get_media_info(message) -> Tuple[Optional[str], str, Optional[int]]:
    """
    Returns: (file_id, file_name, file_size)
    file_name is always a non-empty string.
    """
    media = get_media_object(message)
    if not media:
        return None, "file", None

    file_id = getattr(media, "file_id", None)
    file_size = getattr(media, "file_size", None)

    # Try to get original filename
    file_name = getattr(media, "file_name", None)

    if not file_name:
        mime = getattr(media, "mime_type", None) or "application/octet-stream"
        file_name = MIME_TO_FILENAME.get(mime, "file.bin")

    # Sanitize filename (remove special chars that break URLs)
    file_name = "".join(
        c if c.isalnum() or c in "._- " else "_"
        for c in file_name
    ).strip()

    if not file_name:
        file_name = "file"

    return file_id, file_name, file_size
