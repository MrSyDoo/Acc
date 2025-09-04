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





    

