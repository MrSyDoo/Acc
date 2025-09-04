import motor.motor_asyncio
from config import Config, Txt
import random, asyncio
from collections import defaultdict
import pytz
from datetime import datetime, timedelta
from telethon.tl.functions.account import UpdateProfileRequest
from pyrogram import Client, filters, enums
from telethon.tl.functions.channels import GetForumTopicsRequest
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
india = pytz.timezone("Asia/Kolkata")
from .command import db, ADMINS
sessions = {}
API_HASH = Config.API_HASH
API_ID = Config.API_ID

class temp(object):
    ME = None
    U_NAME = None
    B_NAME = None
    
@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    used = message.from_user
    button=InlineKeyboardMarkup([[
                InlineKeyboardButton('Gᴜɪᴅᴇ', callback_data='guide')
          ]])
    if Config.PICS:
        await message.reply_photo(random.choice(Config.PICS), caption=Txt.START_TXT.format(used.mention), reply_markup=button, parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text(text=Txt.START_TXT.format(used.mention), reply_markup=button, disable_web_page_preview=True)



from pyrogram import Client, filters
from pyrogram.types import Message

@Client.on_message(filters.command("give") & filters.user([1821530401, 1733124290]))  
# ^ put your own admin IDs here
async def give_account(client: Client, message: Message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            return await message.reply("⚠️ Usage: /give {user_id} {acc_num}")

        user_id = int(parts[1])
        acc_num = int(parts[2])

        success, msg = await db.grant_account(user_id, acc_num)
        await message.reply(msg)

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("list") & filters.user([1821530401, 1733124290]))  
# ^ put your admin IDs here
async def list_user_accounts_cmd(client: Client, message: Message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            return await message.reply("⚠️ Usage: /list {user_id}")

        user_id = int(parts[1])
        accounts = await db.get_user_account_info(user_id)

        if not accounts:
            return await message.reply(f"❌ No accounts found for user {user_id}")

        text_lines = [f"📑 Accounts for user `{user_id}`:\n"]
        for acc in accounts:
            text_lines.append(
                f"🔹 #{acc['account_num']} | "
                f"{acc.get('name', '?')} | "
                f"{acc.get('phone', '?')} | "
                f"2FA: {acc.get('twofa', '?')} | "
                f"Spam: {acc.get('spam', '?')}"
            )

        await message.reply("\n".join(text_lines))

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("myaccounts"))
async def my_accounts_cmd(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        accounts = await db.get_user_account_info(user_id)

        if not accounts:
            return await message.reply("⚠️ You don’t own any accounts yet.")

        text_lines = ["📑 Your accounts:\n"]
        for acc in accounts:
            text_lines.append(
                f"🔹 #{acc['account_num']} | "
                f"{acc.get('name', '?')} | "
                f"{acc.get('phone', '?')} | "
                f"2FA: {acc.get('twofa', '?')} | "
                f"Spam: {acc.get('spam', '?')}"
            )

        await message.reply("\n".join(text_lines))

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("verify") & filters.user(ADMINS))
async def verify_user(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /verify {user_id}")
    try:
        uid = int(message.command[1])
        await db.add_verified(uid)
        await message.reply(f"✅ User `{uid}` verified.")
        await client.send_message(uid, "🎉 You have been verified by admin! You can now use the bot.")
    except Exception as e:
        await message.reply(f"Error: {e}")


@Client.on_message(filters.command("revoke") & filters.user(ADMINS))
async def revoke_user(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /revoke {user_id}")
    uid = int(message.command[1])
    await db.revoke_verified(uid)
    await message.reply(f"❌ User `{uid}` revoked.")
    await client.send_message(uid, "⚠️ Your verification has been revoked by admin.")

    

