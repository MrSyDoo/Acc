from pyrogram import Client
import time
import asyncio
from .command import db, ADMINS, check_valid_session, get_account_age, get_country_from_phone, check_2fa
from pyrogram import Client, filters, enums
from pyrogram.errors import (
    ApiIdInvalid,
    FloodWait,
    PasswordHashInvalid,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
    ListenerTimeout
)
from config import Config
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError
)
from telethon.sessions import StringSession
from telethon import TelegramClient


async def start_clone_bot(session: str) -> TelegramClient:
    """Create, start, and return a Telethon user client"""
    mrsyd = TelegramClient(
        StringSession(session),
        API_ID,
        API_HASH
    )
    await mrsyd.start()
    return mrsyd





async def cancelled(message):
    if "/cancel" in message.text:
        await message.reply_text(
            "** ᴄᴀɴᴄᴇʟʟᴇᴅ ᴛʜᴇ ᴏɴɢᴏɪɴɢ sᴛʀɪɴɢ ɢᴇɴᴇʀᴀᴛɪᴏɴ ᴩʀᴏᴄᴇss. **"
        )
        return True
    
    else:
        return False




async def generate_telethon_session(bot, message):
    user_id = message.from_user.id

    # 1. Ask phone number
    try:
        phone_number = await bot.ask(
            chat_id=user_id,
            text="Send your phone number with country code (ex: +13124562345)",
            filters=filters.text,
            timeout=300,
        )
    except ListenerTimeout:
        return await bot.send_message(
            user_id, "Timed out! Start again."
        )

    if await cancelled(phone_number):
        return

    phone_number = phone_number.text

    await bot.send_message(user_id, "Sending OTP to your Telegram app...")

    # Telethon client
    client = TelegramClient(
        session=StringSession(),
        api_id=Config.API_ID,
        api_hash=Config.API_HASH
    )

    await client.connect()

    # 2. Send OTP
    try:
        sent = await client.send_code_request(phone_number)
    except FloodWaitError as e:
        return await bot.send_message(user_id, f"Flood wait {e.seconds}s.")
    except PhoneNumberInvalidError:
        return await bot.send_message(user_id, "Invalid phone number!")

    # 3. Ask OTP
    try:
        otp = await bot.ask(
            chat_id=user_id,
            text=f"Enter the OTP in format `1 2 3 4 5`",
            filters=filters.text,
            timeout=600,
        )
        if await cancelled(otp):
            return
    except ListenerTimeout:
        return await bot.send_message(user_id, "OTP timeout. Start again.")

    otp = otp.text.replace(" ", "")

    # 4. Sign In
    try:
        await client.sign_in(phone_number, sent.phone_code_hash, otp)
    except PhoneCodeInvalidError:
        return await bot.send_message(user_id, "Wrong OTP!")
    except PhoneCodeExpiredError:
        return await bot.send_message(user_id, "OTP expired!")
    except SessionPasswordNeededError:
        # ask 2FA password
        pwd = await bot.ask(
            chat_id=user_id,
            text="Your account has 2FA. Please enter your password:",
            filters=filters.text,
            timeout=300,
        )
        if await cancelled(pwd):
            return

        try:
            await client.sign_in(password=pwd.text)
        except:
            return await bot.send_message(user_id, "Wrong 2FA password!")

    # 5. Export Telethon Session String
    session_string = client.session.save()

    await client.disconnect()
    return session_string


from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from plugins.utils import db, get_country_from_phone, get_account_age, check_2fa

@Client.on_message(filters.private & filters.command('addacc') & filters.user(Config.ADMIN))
async def add_userbot(bot: Client, message: Message):
    """Add a user bot (Pyrogram session)"""
    user_id = message.from_user.id
    session = await generate_telethon_session(bot, message)
    try:
        user_client = TelegramClient(
            session=StringSession(session),
            api_id=Config.API_ID,
            api_hash=Config.API_HASH
        )
        await user_client.start()
        me = await user_client.get_me()
        phone = getattr(me, "phone_number", "Unknown")
        syd = await check_2fa(user_client, False)
        info = {
            "_id": me.id,
            "account_num": await db.get_next_account_num(),
            "name": me.first_name or me.username or "N/A",
            "phone": phone,
            "country": get_country_from_phone(f"+{phone}") if phone != "Unknown" else "Unknown",
            "age": await get_account_age(user_client, False),
            "twofa": syd,
            "session_string": session,
            "by": f"{message.from_user.first_name}({message.from_user.id})"
        }
        acc_num = await db.save_account(me.id, info)
        await message.reply_text(
            f"✅ Account `#{acc_num}` (`{info['name']}`) added successfully!"
            f"Lᴏɢɢᴇᴅ ɪɴ ᴀs {me.first_name or '?'} ({me.id})\n"
            f"ID: {info.get('account_num', 'N/A')}\n"
            f"PH: +{me.phone_number if getattr(me, 'phone_number', None) else 'Unknown'}\n"
            f"AGE: {info.get('age', 'Unknown')}\n"
            f"CTRY: {info.get('country', 'Unknown')}\n"
            f"{syd}",
            quote=True
        )
    except Exception as e:
        return await message.reply_text(f"**⚠️ USER BOT ERROR:** `{e}`")

    finally:
        try:
            await user_client.stop()
        except:
            pass

    
