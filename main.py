import os
import asyncio
import uuid
from typing import Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery
)

from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped, InputStream

import yt_dlp

# ENV VARIABLES (FROM RENDER)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SESSION_STRING = os.environ.get("SESSION_STRING")
API_ID = int(os.environ.get("API_ID") or 0)
API_HASH = os.environ.get("API_HASH")
OWNER_ID = int(os.environ.get("OWNER_ID") or 0)

if not BOT_TOKEN or not SESSION_STRING or not API_ID or not API_HASH:
    raise SystemExit("Missing required environment variables!")

# Pyrogram Clients
bot = Client("music_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)
user = Client("music_user", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)

pytgcalls = PyTgCalls(user)

# Queue System
class Track:
    def __init__(self, title, url, file, duration=None, requested_by=""):
        self.id = str(uuid.uuid4())
        self.title = title
        self.url = url
        self.file = file
        self.duration = duration
        self.requested_by = requested_by

class ChatQueue:
    def __init__(self):
        self.queue: List[Track] = []
        self.loop = False
        self.playing: Optional[Track] = None

chat_queues: Dict[int, ChatQueue] = {}

# yt-dlp download settings
YTDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "outtmpl": "downloads/%(id)s.%(ext)s",
}

os.makedirs("downloads", exist_ok=True)

def download_audio(query: str):
    ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)
    info = ytdl.extract_info(query, download=False)

    if "entries" in info:
        info = info["entries"][0]

    video_id = info.get("id")
    title = info.get("title")
    url = info.get("webpage_url")

    ext = info.get("ext", "mp3")
    path = f"downloads/{video_id}.{ext}"

    if not os.path.isfile(path):
        ytdl.params["outtmpl"] = path
        ytdl.download([url])

    return Track(title, url, path, info.get("duration"))

def control_keyboard(cid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏯ Pause/Resume", callback_data=f"pause|{cid}"),
         InlineKeyboardButton("⏭ Skip", callback_data=f"skip|{cid}")],
        [InlineKeyboardButton("🔁 Loop", callback_data=f"loop|{cid}"),
         InlineKeyboardButton("⛔ Stop", callback_data=f"stop|{cid}")]
    ])

async def ensure_queue(chat_id):
    if chat_id not in chat_queues:
        chat_queues[chat_id] = ChatQueue()
    return chat_queues[chat_id]

async def start_playback(chat_id):
    q = await ensure_queue(chat_id)

    if q.playing:
        return
    if not q.queue:
        return

    track = q.queue.pop(0)
    q.playing = track

    await pytgcalls.join_group_call(
        chat_id,
        AudioPiped(track.file),
        stream_type=StreamType().local_stream
    )

@pytgcalls.on_stream_end()
async def stream_end_handler(_, update):
    cid = update.chat_id
    q = chat_queues.get(cid)

    if not q:
        return

    last = q.playing
    q.playing = None

    if q.loop and last:
        q.queue.insert(0, last)

    if q.queue:
        nxt = q.queue.pop(0)
        q.playing = nxt
        await pytgcalls.change_stream(cid, AudioPiped(nxt.file))
    else:
        await pytgcalls.leave_group_call(cid)

@bot.on_message(filters.command("start"))
async def start_cmd(_, msg: Message):
    me = await bot.get_me()
    add = f"https://t.me/{me.username}?startgroup=true"

    await msg.reply_text(
        "🎵 **Welcome to VC Music Bot!**\nUse /play <song name>\n",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Me to Group", url=add)]
        ])
    )

@bot.on_message(filters.command("play") & ~filters.private)
async def play_cmd(_, msg: Message):
    chat_id = msg.chat.id

    if len(msg.command) < 2:
        return await msg.reply_text("Usage: /play song name or url")

    query = msg.text.split(" ", 1)[1]
    status = await msg.reply_text("Downloading...")

    loop = asyncio.get_event_loop()
    track = await loop.run_in_executor(None, download_audio, query)

    q = await ensure_queue(chat_id)
    q.queue.append(track)

    await status.edit_text(
        f"🎶 Added: {track.title}",
        reply_markup=control_keyboard(chat_id)
    )

    if not q.playing:
        await start_playback(chat_id)

@bot.on_callback_query()
async def cb_handler(_, cq: CallbackQuery):
    data = cq.data.split("|")
    action = data[0]
    chat_id = int(data[1])

    q = await ensure_queue(chat_id)

    if action == "pause":
        try:
            await pytgcalls.pause_stream(chat_id)
            await cq.answer("Paused")
        except:
            await pytgcalls.resume_stream(chat_id)
            await cq.answer("Resumed")

    elif action == "skip":
        if q.queue:
            nxt = q.queue.pop(0)
            await pytgcalls.change_stream(chat_id, AudioPiped(nxt.file))
            await cq.answer("Skipped!")
        else:
            await cq.answer("Nothing to skip")

    elif action == "loop":
        q.loop = not q.loop
        await cq.answer("Loop On" if q.loop else "Loop Off")

    elif action == "stop":
        q.queue.clear()
        q.playing = None
        await pytgcalls.leave_group_call(chat_id)
        await cq.answer("Stopped")

@bot.on_message(filters.command("search") & ~filters.private)
async def search_cmd(_, msg: Message):
    q = msg.text.split(" ", 1)
    if len(q) < 2:
        return await msg.reply_text("Usage: /search song name")

    query = q[1]
    ytdl = yt_dlp.YoutubeDL({"quiet": True, "default_search": "ytsearch5"})
    results = ytdl.extract_info(query, download=False)["entries"]

    text = "Search Results:\n\n"
    buttons = []
    for r in results:
        title = r["title"]
        url = r["webpage_url"]
        text += f"• {title}\n"
        buttons.append([InlineKeyboardButton(title[:30], callback_data=f"add|{msg.chat.id}|{url}")])

    await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@bot.on_callback_query(filters.regex("^add"))
async def add_result(_, cq: CallbackQuery):
    _, chatid, url = cq.data.split("|")
    chat_id = int(chatid)

    msg = await cq.message.reply_text("Downloading...")
    loop = asyncio.get_event_loop()
    track = await loop.run_in_executor(None, download_audio, url)

    q = await ensure_queue(chat_id)
    q.queue.append(track)

    await msg.edit_text(f"Added: {track.title}")
    if not q.playing:
        await start_playback(chat_id)

async def main():
    await bot.start()
    await user.start()
    await pytgcalls.start()
    print("Bot running...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
