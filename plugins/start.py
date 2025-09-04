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
from .commands import db
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

@Client.on_message(filters.command("give") & filters.user([123456789]))  
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


    

