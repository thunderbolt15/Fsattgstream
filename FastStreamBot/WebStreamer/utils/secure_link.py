# WebStreamer/utils/secure_link.py
# ─────────────────────────────────────────────
#  Expiry-based HMAC secure token system
# ─────────────────────────────────────────────

import time
import hmac
import hashlib
import base64
from typing import Tuple, Optional

from WebStreamer.config import Var


def generate_token(msg_id: int, user_id: int = 0) -> str:
    """
    Secure expiry token generate karo.
    Format (base64url): msg_id:expires_at:user_id:hmac_sig
    """
    expires_at = int(time.time()) + (Var.LINK_EXPIRY_HOURS * 3600)
    payload = f"{msg_id}:{expires_at}:{user_id}"

    sig = hmac.new(
        Var.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]  # 16 char signature — enough for security

    raw = f"{payload}:{sig}"
    token = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return token


def verify_token(token: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Token verify karo.
    Returns: (msg_id, error_string)
    error is None if token is valid.
    """
    try:
        # Restore base64 padding
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded).decode("utf-8")

        parts = raw.split(":")
        if len(parts) != 4:
            return None, "bad_format"

        msg_id_str, expires_str, user_id_str, received_sig = parts
        msg_id = int(msg_id_str)
        expires_at = int(expires_str)
        user_id = int(user_id_str)

        # Expiry check
        if time.time() > expires_at:
            return None, "expired"

        # HMAC verify karo
        payload = f"{msg_id}:{expires_at}:{user_id}"
        expected_sig = hmac.new(
            Var.SECRET_KEY.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:16]

        if not hmac.compare_digest(received_sig, expected_sig):
            return None, "invalid_sig"

        return msg_id, None

    except (ValueError, UnicodeDecodeError):
        return None, "decode_error"
    except Exception:
        return None, "unknown_error"
