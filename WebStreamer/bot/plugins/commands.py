# WebStreamer/bot/plugins/commands.py

import logging
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from WebStreamer.bot import StreamBot
from WebStreamer.config import Var
from WebStreamer.utils.secure_link import generate_token
from WebStreamer.utils.file_info import get_media_info

logger = logging.getLogger(__name__)

SUPPORTED_MEDIA = (
    filters.document
    | filters.video
    | filters.audio
    | filters.voice
    | filters.video_note
    | filters.animation
    | filters.photo
)


# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────
@StreamBot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    await message.reply_text(
        f"👋 **Hello {message.from_user.mention}!**\n\n"
        f"📁 Send me any file and I'll generate a **fast direct download link** for you.\n\n"
        f"**Commands:**\n"
        f"`/getlink MSG_ID` — Single msg ID se link\n"
        f"`/getlink 101 102 103` — Multiple IDs se links\n"
        f"`/bulklink 101 150` — Range se bulk links\n"
        f"`/status` — Bot status\n"
        f"`/help` — Help\n\n"
        f"⚡ Powered by **FastStreamBot**",
    )


# ─────────────────────────────────────────────
#  /help
# ─────────────────────────────────────────────
@StreamBot.on_message(filters.command("help") & filters.private)
async def help_handler(client, message: Message):
    await message.reply_text(
        "**📖 How to use:**\n\n"
        "**Method 1 — File bhejo:**\n"
        "Bot ko directly file bhejo → link milega\n\n"
        "**Method 2 — Msg ID se link:**\n"
        "`/getlink 1234` — single file\n"
        "`/getlink 1234 5678 9012` — multiple files\n\n"
        "**Method 3 — Bulk range:**\n"
        "`/bulklink 1001 1050` — ID 1001 se 1050 tak (max 200)\n\n"
        f"⏳ Links expire: **{Var.LINK_EXPIRY_HOURS} hours**\n"
        f"📦 Max file size: **4GB**"
    )


# ─────────────────────────────────────────────
#  /status
# ─────────────────────────────────────────────
@StreamBot.on_message(filters.command("status") & filters.private)
async def status_handler(client, message: Message):
    from WebStreamer.bot import multi_clients
    await message.reply_text(
        f"✅ **Bot is running!**\n\n"
        f"🤖 Active clients: **{multi_clients.count}**\n"
        f"🌐 Server: `{Var.FQDN}`\n"
        f"📡 BIN_CHANNEL: `{Var.BIN_CHANNEL}`"
    )


# ─────────────────────────────────────────────
#  /getlink — Single ya multiple msg IDs se link
# ─────────────────────────────────────────────
@StreamBot.on_message(filters.command("getlink") & filters.private)
async def getlink_handler(client, message: Message):
    args = message.text.strip().split()[1:]

    if not args:
        await message.reply_text(
            "❌ **MSG ID daao!**\n\n"
            "**Usage:**\n"
            "`/getlink 1234` — single\n"
            "`/getlink 1234 5678 9012` — multiple"
        )
        return

    valid_ids = []
    for arg in args:
        try:
            valid_ids.append(int(arg.strip()))
        except ValueError:
            await message.reply_text(f"❌ `{arg}` valid number nahi hai.")
            return

    processing = await message.reply_text(
        f"⏳ `{len(valid_ids)}` file(s) ka link bana raha hoon..."
    )

    results = await _generate_links_for_ids(client, valid_ids, message.from_user.id)
    await _send_results(message, processing, results)


# ─────────────────────────────────────────────
#  /bulklink — Range of msg IDs se bulk links
# ─────────────────────────────────────────────
@StreamBot.on_message(filters.command("bulklink") & filters.private)
async def bulklink_handler(client, message: Message):
    args = message.text.strip().split()[1:]

    if len(args) != 2:
        await message.reply_text(
            "❌ **2 IDs daao — start aur end!**\n\n"
            "**Usage:** `/bulklink 1001 1050`\n"
            "Max range: 200 messages"
        )
        return

    try:
        start_id = int(args[0])
        end_id = int(args[1])
    except ValueError:
        await message.reply_text("❌ Valid numbers daao.")
        return

    if start_id > end_id:
        start_id, end_id = end_id, start_id

    total = end_id - start_id + 1
    if total > 200:
        await message.reply_text(
            f"❌ Range bahut bada hai ({total} messages).\n"
            f"Max **200** messages ek baar mein.\n"
            f"Example: `/bulklink {start_id} {start_id + 199}`"
        )
        return

    processing = await message.reply_text(
        f"⏳ ID `{start_id}` se `{end_id}` tak **{total}** messages check kar raha hoon..."
    )

    msg_ids = list(range(start_id, end_id + 1))
    results = await _generate_links_for_ids(
        client, msg_ids, message.from_user.id, is_bulk=True
    )
    await _send_results(message, processing, results, is_bulk=True)


# ─────────────────────────────────────────────
#  Media handler — File bhejo → link milega
# ─────────────────────────────────────────────
@StreamBot.on_message(filters.private & SUPPORTED_MEDIA)
async def media_handler(client, message: Message):
    processing_msg = await message.reply_text("⏳ Link bana raha hoon...")

    try:
        log_msg = await message.forward(Var.BIN_CHANNEL)
    except Exception as e:
        logger.error(f"Forward failed: {e}")
        await processing_msg.edit_text(
            "❌ File process nahi hui.\n"
            "Bot ko BIN_CHANNEL ka Admin banao."
        )
        return

    file_id, file_name, file_size = get_media_info(log_msg)
    if not file_id:
        await processing_msg.edit_text("❌ Unsupported file type.")
        return

    token = generate_token(
        msg_id=log_msg.id,
        user_id=message.from_user.id if message.from_user else 0,
    )
    stream_url = f"{Var.FQDN}/{token}/{file_name}"
    size_str = _format_size(file_size)

    await processing_msg.edit_text(
        f"✅ **Link Ready!**\n\n"
        f"📁 **File:** `{file_name}`\n"
        f"💾 **Size:** `{size_str}`\n"
        f"⏳ **Expires:** {Var.LINK_EXPIRY_HOURS} hours\n\n"
        f"🔗 **Link:**\n`{stream_url}`",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬇️ Download / Stream", url=stream_url),
        ]]),
    )


# ─────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────

async def _generate_links_for_ids(
    client,
    msg_ids: list,
    user_id: int,
    is_bulk: bool = False,
) -> list:
    results = []
    BATCH_SIZE = 50

    for i in range(0, len(msg_ids), BATCH_SIZE):
        batch = msg_ids[i : i + BATCH_SIZE]

        try:
            messages = await client.get_messages(
                chat_id=Var.BIN_CHANNEL,
                message_ids=batch,
            )
        except Exception as e:
            logger.error(f"get_messages batch failed: {e}")
            for mid in batch:
                results.append(f"❌ ID `{mid}` — Fetch failed")
            continue

        if not isinstance(messages, list):
            messages = [messages]

        for msg in messages:
            if not msg or msg.empty:
                if not is_bulk:
                    results.append(f"❌ ID `{msg.id if msg else '?'}` — Not found")
                continue

            file_id, file_name, file_size = get_media_info(msg)

            if not file_id:
                if not is_bulk:
                    results.append(f"❌ ID `{msg.id}` — No media")
                continue

            token = generate_token(msg_id=msg.id, user_id=user_id)
            link = f"{Var.FQDN}/{token}/{file_name}"
            size_str = _format_size(file_size)

            results.append(
                f"✅ `{file_name}`\n"
                f"💾 {size_str}  |  📌 ID: `{msg.id}`\n"
                f"🔗 `{link}`"
            )

    return results


async def _send_results(
    message: Message,
    processing_msg: Message,
    results: list,
    is_bulk: bool = False,
):
    if not results:
        await processing_msg.edit_text(
            "❌ Koi bhi media nahi mila un IDs mein.\n"
            "Check karo ki BIN_CHANNEL sahi hai aur files hain."
        )
        return

    success_count = sum(1 for r in results if r.startswith("✅"))
    header = f"**✅ {success_count}/{len(results)} links ready!**\n\n"
    chunks = _split_into_chunks(results, header=header, limit=4000)

    await processing_msg.edit_text(chunks[0], disable_web_page_preview=True)

    for chunk in chunks[1:]:
        await message.reply_text(chunk, disable_web_page_preview=True)


def _split_into_chunks(results: list, header: str = "", limit: int = 4000) -> list:
    chunks = []
    current = header

    for r in results:
        entry = r + "\n\n"
        if len(current) + len(entry) > limit:
            chunks.append(current.strip())
            current = entry
        else:
            current += entry

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [header + "Koi result nahi."]


def _format_size(size_bytes) -> str:
    if not size_bytes:
        return "Unknown"
    size_bytes = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"
