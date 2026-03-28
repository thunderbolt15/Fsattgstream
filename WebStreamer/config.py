# WebStreamer/config.py
# ─────────────────────────────────────────────
#  All config variables from environment (Railway compatible)
# ─────────────────────────────────────────────

import os
import sys


def _require(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"[ERROR] Required variable '{key}' is missing in environment")
        sys.exit(1)
    return val


class Var:
    # ── Required ──────────────────────────────
    API_ID: int = int(_require("API_ID"))
    API_HASH: str = _require("API_HASH")
    BOT_TOKEN: str = _require("BOT_TOKEN")
    BIN_CHANNEL: int = int(_require("BIN_CHANNEL"))
    FQDN: str = _require("FQDN").rstrip("/")
    SECRET_KEY: str = _require("SECRET_KEY")

    # ── Optional ──────────────────────────────
    PORT: int = int(os.environ.get("PORT", "8080"))
    HAS_SSL: bool = os.environ.get("HAS_SSL", "True").lower() == "true"
    LINK_EXPIRY_HOURS: int = int(os.environ.get("LINK_EXPIRY_HOURS", "24"))

    # ── Multi-bot worker tokens ───────────────
    MULTI_TOKENS: list[str] = []

    @classmethod
    def load_multi_tokens(cls):
        i = 1
        while True:
            token = os.environ.get(f"MULTI_TOKEN{i}", "").strip()
            if not token:
                break
            cls.MULTI_TOKENS.append(token)
            i += 1


Var.load_multi_tokens()
