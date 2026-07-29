import os
import json
import asyncio
import re

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import (
    SessionPasswordNeeded, 
    PhoneCodeInvalid, 
    PhoneCodeExpired, 
    PasswordHashInvalid
)

# Latest PyTgCalls Imports
try:
    from pytgcalls import PyTgCalls
except ImportError:
    from pytgcalls.pytgcalls import PyTgCalls

from pytgcalls.types import MediaStream, StreamEnded

import config
import db
from downloader import resolve_track

# -------------------------------------------------------------
# 💾 Session Management (Save & Load sessions.json)
# -------------------------------------------------------------
SESSIONS_FILE = "sessions.json"

def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_session_string(session_str):
    sessions = load_sessions()
    if session_str not in sessions:
        sessions.append(session_str)
        with open(SESSIONS_FILE, "w") as f:
            json.dump(sessions, f, indent=4)

# Global instances & Queue / Vote Management
bot = None
userbot = None
call_py = None
pending_logins = {}

queues = {}          # { chat_id: [ {track_data}, {track_data} ] }
skip_votes = {}      # { chat_id: set([user_ids]) }

# Helper to clean special markdown chars
def clean_text(text: str) -> str:
    if not text:
        return "Unknown"
    return re.sub(r'[*_`\[\]()~>#+-=|{}.!]', '', str(text))

# Play next track in queue with file cleanup to prevent memory/bot kill
async def play_next(client_call, chat_id):
    global userbot
    if chat_id in queues and len(queues[chat_id]) > 0:
        # Peer cache ensure karne ke liye pehle get_chat call karein
        if userbot:
            try:
                await userbot.get_chat(chat_id)
            except Exception:
                pass

        # Purane gaane ko queue se hatane se pehle uska file path nikal kar delete karein
        finished_track = queues[chat_id][0]
        old_path = finished_track.get("local_path")
        if old_path and os.path.exists(old_path) and not old_path.startswith("http"):
            try:
                os.remove(old_path)
            except Exception:
                pass

        queues[chat_id].pop(0)
        
        # Clear skip votes for this chat when song changes
        if chat_id in skip_votes:
            skip_votes[chat_id].clear()
        
        if len(queues[chat_id]) > 0:
            next_track = queues[chat_id][0]
            try:
                is_video = next_track.get("is_video", False)
                stream = MediaStream(
                    next_track["local_path"],
                    video_flags=None if is_video else MediaStream.Flags.IGNORE
                )
                await client_call.play(chat_id, stream)
                
                title = clean_text(next_track.get('title', 'Unknown'))
                artist = clean_text(next_track.get('artist', 'YouTube Artist'))
                
                if bot:
                    await bot.send_message(
                        chat_id,
                        f"🎧 **NOW PLAYING FROM QUEUE**\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📌 Title: {title}\n"
                        f"👤 Artist: {artist}\n"
                        f"⏱ Duration: {next_track.get('duration', 0)}s\n"
                        f"━━━━━━━━━━━━━━━━━━━━"
                    )
                return
            except Exception as e:
                print(f"⚠️ Queue Play Error in {chat_id}: {e}")
                await play_next(client_call, chat_id)
        else:
            try:
                await client_call.leave_call(chat_id)
                print(f"⏹ Queue finished. Left VC in Chat: {chat_id}")
            except Exception:
                pass
    else:
        try:
            await client_call.leave_call(chat_id)
        except Exception:
            pass

# Robust Check for Group Owner, Creator, and Admins
async def is_admin(client, chat_id, user_id):
    if user_id == config.ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        status = str(getattr(member, "status", "")).lower()
        
        if any(role in status for role in ["creator", "owner", "administrator"]):
            return True
            
        if getattr(member, "privileges", None) is not None:
            return True
    except Exception as e:
        print(f"Admin check error: {e}")
    return False

# -------------------------------------------------------------
# 👤 Userbot Hot-Loader (used at boot AND right after /otp or /pass login)
# -------------------------------------------------------------
userbot_lock = asyncio.Lock()
_swap_counter = 0

async def start_userbot(session_str: str):
    global userbot, call_py, _swap_counter

    async with userbot_lock:
        old_userbot = userbot
        old_call_py = call_py

        userbot = None
        call_py = None

        if old_call_py is not None:
            try:
                await asyncio.wait_for(old_call_py.stop(), timeout=10)
            except Exception:
                pass
        if old_userbot is not None:
            try:
                await asyncio.wait_for(old_userbot.stop(), timeout=10)
            except Exception:
                pass
            await asyncio.sleep(1)

        try:
            _swap_counter += 1
            new_userbot = Client(
                f"DevNullUserbot_{_swap_counter}",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=session_str,
                in_memory=True,
            )
            await new_userbot.start()

            new_call_py = PyTgCalls(new_userbot)

            @new_call_py.on_update()
            async def stream_end_handler(client, update):
                if isinstance(update, StreamEnded):
                    chat_id = update.chat_id
                    await play_next(client, chat_id)

            await new_call_py.start()

            userbot = new_userbot
            call_py = new_call_py
            print("✅ Active Userbot & PyTgCalls Loaded Successfully!")
            return True, None
        except Exception as e:
            print(f"⚠️ Userbot start error: {e}")
            return False, str(e)

def _loop_exception_handler(loop, context):
    exc = context.get("exception")
    msg = str(exc) if exc else context.get("message", "")
    if "closed database" in msg.lower():
        print(f"ℹ️ Ignored harmless stale-session cleanup error: {msg}")
        return
    loop.default_exception_handler(context)

# -------------------------------------------------------------
# 🌐 Tiny web server
# -------------------------------------------------------------
async def run_web_server():
    from aiohttp import web

    async def health(request):
        return web.Response(text="OK - Bot is alive")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 3000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Web server listening on port {port}")

# -------------------------------------------------------------
# 🚀 MAIN ENGINE RUNNER
# -------------------------------------------------------------
async def main():
    global bot

    asyncio.get_event_loop().set_exception_handler(_loop_exception_handler)

    bot = Client(
        "DevNullBot", 
        api_id=config.API_ID, 
        api_hash=config.API_HASH, 
        bot_token=config.BOT_TOKEN
    )

    register_handlers(bot)
    await bot.start()

    await run_web_server()

    saved = load_sessions()
    session_to_use = saved[0] if saved else getattr(config, "STRING_SESSION", None)

    if session_to_use:
        await start_userbot(session_to_use)
    else:
        print("⚠️ No Userbot Session found. Use /login in Bot DM to add one!")

    print(f"🚀 Python PyTgCalls Engine Online! Credit: {config.DEVELOPED_BY}")
    await asyncio.Event().wait()

# -------------------------------------------------------------
# 🤖 BOT COMMAND & CALLBACK HANDLERS
# -------------------------------------------------------------
def register_handlers(app: Client):

    @app.on_message(filters.command("login") & filters.private)
    async def login_cmd(client, message: Message):
        if message.from_user.id != config.ADMIN_ID:
            return await message.reply_text("⛔ Sirf Admin hi new Userbot login kar sakta hai.")

        if len(message.command) < 2:
            return await message.reply_text("⚠️ Usage: /login +91xxxxxxx", parse_mode=None)

        phone = message.command[1].strip()
        user_id = message.from_user.id

        if user_id in pending_logins:
            return await message.reply_text("⚠️ Login pehle se process mein hai! Reset karne ke liye /cancel bhejein.", parse_mode=None)

        msg = await message.reply_text("📡 Connecting to Telegram...")

        try:
            temp_client = Client(
                f"temp_{user_id}",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                in_memory=True
            )
            await temp_client.connect()
            sent_code = await temp_client.send_code(phone)

            pending_logins[user_id] = {
                "client": temp_client,
                "phone": phone,
                "hash": sent_code.phone_code_hash
            }

            await msg.edit_text(f"📩 OTP Sent to {phone}.\n\nReply karein: /otp 12345", parse_mode=None)
        except Exception as e:
            await msg.edit_text(f"❌ Login Failed: {e}", parse_mode=None)

    @app.on_message(filters.command("otp") & filters.private)
    async def otp_cmd(client, message: Message):
        user_id = message.from_user.id
        if user_id not in pending_logins:
            return await message.reply_text("❌ Pehle /login +91xxxx command bhejein.", parse_mode=None)

        if len(message.command) < 2:
            return await message.reply_text("⚠️ Usage: /otp 12345", parse_mode=None)

        otp = "".join(message.command[1:]).replace(" ", "")
        data = pending_logins[user_id]
        temp_client = data["client"]

        msg = await message.reply_text("⏳ OTP Verify ho raha hai...")

        try:
            await temp_client.sign_in(data["phone"], data["hash"], otp)
            session_str = await temp_client.export_session_string()
            save_session_string(session_str)
            
            await temp_client.disconnect()
            del pending_logins[user_id]

            await msg.edit_text("✅ Login Successful! Userbot ko activate kar raha hoon...")
            ok, err = await start_userbot(session_str)
            if ok:
                await msg.edit_text("✅ Login Successful! Userbot ab LIVE hai — /play try karein.")
            else:
                await msg.edit_text(f"⚠️ Login save ho gaya, par Userbot start karte waqt error aaya: {err}")

        except SessionPasswordNeeded:
            await msg.edit_text("🔐 2FA Password Detected!\n\nReply karein: /pass your_password", parse_mode=None)
        except (PhoneCodeInvalid, PhoneCodeExpired) as e:
            await msg.edit_text(f"❌ Galat ya expired OTP: {e}", parse_mode=None)
        except Exception as e:
            await msg.edit_text(f"❌ Error: {e}", parse_mode=None)

    @app.on_message(filters.command("pass") & filters.private)
    async def pass_cmd(client, message: Message):
        user_id = message.from_user.id
        if user_id not in pending_logins:
            return await message.reply_text("❌ Koi active login attempt nahi mila.")

        if len(message.command) < 2:
            return await message.reply_text("⚠️ Usage: /pass your_password", parse_mode=None)

        password = message.command[1]
        data = pending_logins[user_id]
        temp_client = data["client"]

        msg = await message.reply_text("⏳ 2FA Password verify ho raha hai...")

        try:
            await temp_client.check_password(password)
            session_str = await temp_client.export_session_string()
            save_session_string(session_str)

            await temp_client.disconnect()
            del pending_logins[user_id]

            await msg.edit_text("✅ Login Successful with 2FA! Userbot ko activate kar raha hoon...")
            ok, err = await start_userbot(session_str)
            if ok:
                await msg.edit_text("✅ Login Successful with 2FA! Userbot ab LIVE hai — /play try karein.")
            else:
                await msg.edit_text(f"⚠️ Login save ho gaya, par Userbot start karte waqt error aaya: {err}")
        except PasswordHashInvalid:
            await msg.edit_text("❌ Galat password! /pass your_password firse try karein.", parse_mode=None)
        except Exception as e:
            await msg.edit_text(f"❌ Error: {e}", parse_mode=None)

    @app.on_message(filters.command("cancel") & filters.private)
    async def cancel_cmd(client, message: Message):
        user_id = message.from_user.id
        if user_id in pending_logins:
            try:
                await pending_logins[user_id]["client"].disconnect()
            except Exception:
                pass
            del pending_logins[user_id]
            await message.reply_text("✅ Login session cancel kar diya gaya!")
        else:
            await message.reply_text("ℹ️ Koi active login process nahi tha.")

    @app.on_message(filters.command("start"))
    async def start_cmd(client, message: Message):
        text = (
            f"👋 Welcome to {config.DEVELOPED_BY} Enterprise Music Bot!\n\n"
            "🎵 Music Commands:\n"
            "🔹 /play <name/url> - Play Audio in VC (Queued)\n"
            "🔹 /vplay <name/url> - Play Video in VC (Queued)\n"
            "🔹 /skip - Skip current song\n"
            "🔹 /pause | /resume | /stop\n\n"
            f"🇮🇳 Developed by {config.DEVELOPED_BY}"
        )
        await message.reply_text(text, parse_mode=None)

    @app.on_message(filters.command(["play", "vplay"]) & filters.group)
    async def play_cmd(client, message: Message):
        global call_py, userbot
        if not call_py or not userbot:
            return await message.reply_text("❌ No active Userbot session! Pehle PM mein /login +91xxxx karein.", parse_mode=None)

        if len(message.command) < 2:
            return await message.reply_text("⚠️ Usage: /play <song name or URL>", parse_mode=None)

        chat_id = message.chat.id
        msg = await message.reply_text("⚡ Fetching & Processing Track...")

        # Peer cache ensure karne ke liye userbot se pehle chat fetch karein
        try:
            await userbot.get_chat(chat_id)
        except Exception:
            pass

        try:
            await userbot.get_chat_member(chat_id, "me")
        except Exception:
            try:
                if message.chat.username:
                    await userbot.join_chat(message.chat.username)
                else:
                    link = await client.export_chat_invite_link(chat_id)
                    await userbot.join_chat(link)
                await asyncio.sleep(2)
            except Exception as e:
                return await msg.edit_text(f"❌ Userbot group join nahi kar paaya! Bot ko Group Admin banayein.\nError: {e}", parse_mode=None)

        is_video = message.command[0].lower() == "vplay"
        query = " ".join(message.command[1:])

        try:
            track = await asyncio.to_thread(resolve_track, query, is_video)
            track["is_video"] = is_video
            db.increment_play_count(track["id"])

            if chat_id not in queues:
                queues[chat_id] = []

            queues[chat_id].append(track)

            title = clean_text(track.get('title', 'Unknown'))
            artist = clean_text(track.get('artist', 'YouTube Artist'))

            if len(queues[chat_id]) == 1:
                stream = MediaStream(
                    track["local_path"],
                    video_flags=None if is_video else MediaStream.Flags.IGNORE
                )
                await call_py.play(chat_id, stream)

                ui_text = (
                    f"🎧 **NOW PLAYING**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 Title: {title}\n"
                    f"👤 Artist: {artist}\n"
                    f"⏱ Duration: {track.get('duration', 0)}s\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🛡️ Powered by {config.DEVELOPED_BY}"
                )
                await msg.edit_text(ui_text, parse_mode=None)
            else:
                position = len(queues[chat_id]) - 1
                ui_text = (
                    f"➕ **ADDED TO QUEUE**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 Title: {title}\n"
                    f"👤 Artist: {artist}\n"
                    f"🔢 Position in Queue: #{position}\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                await msg.edit_text(ui_text, parse_mode=None)

        except Exception as e:
            err_str = str(e)
            if "Transport not found" in err_str:
                await msg.edit_text("❌ Error: Pehle Group ki Voice Chat Start karein, fir /play chalayein!", parse_mode=None)
            else:
                await msg.edit_text(f"❌ Playback Error: {err_str}", parse_mode=None)

    @app.on_message(filters.command("skip") & filters.group)
    async def skip_cmd(client, message: Message):
        global call_py, userbot
        if not call_py:
            return

        chat_id = message.chat.id
        user_id = message.from_user.id

        if chat_id not in queues or len(queues[chat_id]) == 0:
            return await message.reply_text("❌ Queue mein koi gaana nahi hai skip karne ke liye!", parse_mode=None)

        user_is_admin = await is_admin(client, chat_id, user_id)
        if not user_is_admin and userbot:
            user_is_admin = await is_admin(userbot, chat_id, user_id)

        if user_is_admin:
            if chat_id in skip_votes:
                skip_votes[chat_id].clear()
            await message.reply_text("⏭️ Group Owner/Admin ne gaana skip kar diya!", parse_mode=None)
            await play_next(call_py, chat_id)
        else:
            if chat_id not in skip_votes:
                skip_votes[chat_id] = set()

            current_votes = len(skip_votes[chat_id])
            required_votes = 4

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🗳️ Vote to Skip ({current_votes}/{required_votes})", callback_data="vote_skip")]
            ])

            await message.reply_text(
                "⚠️ Sirf Group Owner aur Admins direct skip kar sakte hain.\nNormal users niche button par click karke vote de sakte hain!",
                reply_markup=keyboard,
                parse_mode=None
            )

    @app.on_callback_query(filters.regex("vote_skip"))
    async def vote_skip_callback(client, callback_query: CallbackQuery):
        global call_py
        message = callback_query.message
        chat_id = message.chat.id
        user_id = callback_query.from_user.id

        if chat_id not in queues or len(queues[chat_id]) == 0:
            return await callback_query.answer("❌ Koi gaana play nahi ho raha hai!", show_alert=True)

        if chat_id not in skip_votes:
            skip_votes[chat_id] = set()

        if user_id in skip_votes[chat_id]:
            return await callback_query.answer("⚠️ Aapne pehle hi skip vote de diya hai!", show_alert=True)

        skip_votes[chat_id].add(user_id)
        current_votes = len(skip_votes[chat_id])
        required_votes = 4

        if current_votes >= required_votes:
            skip_votes[chat_id].clear()
            try:
                await message.edit_text("🗳️ Skip votes target complete ho gaya! Gaana skip kiya ja raha hai...")
            except Exception:
                pass
            await play_next(call_py, chat_id)
            await callback_query.answer("✅ Vote counted! Song skipped.")
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🗳️ Vote to Skip ({current_votes}/{required_votes})", callback_data="vote_skip")]
            ])
            try:
                await message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
            await callback_query.answer(f"✅ Vote added! ({current_votes}/{required_votes})")

    @app.on_message(filters.command("pause") & filters.group)
    async def pause_cmd(client, message: Message):
        if call_py:
            await call_py.pause_stream(message.chat.id)
            await message.reply_text("⏸ Playback Paused.", parse_mode=None)

    @app.on_message(filters.command("resume") & filters.group)
    async def resume_cmd(client, message: Message):
        if call_py:
            await call_py.resume_stream(message.chat.id)
            await message.reply_text("▶️ Playback Resumed.", parse_mode=None)

    @app.on_message(filters.command("stop") & filters.group)
    async def stop_cmd(client, message: Message):
        if call_py:
            try:
                chat_id = message.chat.id
                if chat_id in queues:
                    for track in queues[chat_id]:
                        p = track.get("local_path")
                        if p and os.path.exists(p) and not p.startswith("http"):
                            try:
                                os.remove(p)
                            except Exception:
                                pass
                    queues[chat_id].clear()
                if chat_id in skip_votes:
                    skip_votes[chat_id].clear()
                await call_py.leave_call(chat_id)
                await message.reply_text("⏹ Playback stopped, Queue cleared & Left Voice Chat.", parse_mode=None)
            except Exception:
                await message.reply_text("❌ Bot VC mein nahi hai.", parse_mode=None)

if __name__ == "__main__":
    asyncio.run(main())
