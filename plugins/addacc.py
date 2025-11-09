from pyrogram import Client
import time
import asyncio
from .command import db, ADMINS, check_valid_session, get_account_age, get_country_from_phone, check_2fa
from pyrogram import Client, filters
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

async def start_clone_bot(user_client: Client) -> Client:
    """Start and return clone bot client"""
    await user_client.start()
    return user_client

def user_client(session: str) -> Client:
        """Create user client with session"""
        return Client("USERclient", Config.API_ID, Config.API_HASH, session_string=session)




async def cancelled(message):
    if "/cancel" in message.text:
        await message.reply_text(
            "** ᴄᴀɴᴄᴇʟʟᴇᴅ ᴛʜᴇ ᴏɴɢᴏɪɴɢ sᴛʀɪɴɢ ɢᴇɴᴇʀᴀᴛɪᴏɴ ᴩʀᴏᴄᴇss. **"
        )
        return True
    
    else:
        return False

async def generate_session(bot, message):
    user_id = message.from_user.id

    try:
        phone_number = await bot.ask(
            chat_id=message.from_user.id,
            text="Please send your phone number which includes country code\n\nExample: `+13124562345`",
            filters=filters.text,
            timeout=300,
        )
    except ListenerTimeout:
        return await bot.send_message(
            user_id,
            "» ᴛɪᴍᴇᴅ ʟɪᴍɪᴛ ʀᴇᴀᴄʜᴇᴅ ᴏғ 5 ᴍɪɴᴜᴛᴇs.\n\nᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ɢᴇɴᴇʀᴀᴛɪɴɢ sᴇssɪᴏɴ ᴀɢᴀɪɴ."
        )

    if await cancelled(phone_number):
        return
    phone_number = phone_number.text

    await bot.send_message(user_id, "» ᴛʀʏɪɴɢ ᴛᴏ sᴇɴᴅ ᴏᴛᴩ ᴀᴛ ᴛʜᴇ ɢɪᴠᴇɴ ɴᴜᴍʙᴇʀ...")

    client = Client(name="bot", api_id=Config.API_ID, api_hash=Config.API_HASH, in_memory=True)
    await client.connect()
    
    
    try:
        
        code = await client.send_code(phone_number)
        await asyncio.sleep(1)

    except FloodWait as f:
        return await bot.send_message(
            user_id,
            f"» ғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ᴄᴏᴅᴇ ғᴏʀ ʟᴏɢɪɴ.\n\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ {f.value or f.x} sᴇᴄᴏɴᴅs ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ."
        )
    except (ApiIdInvalid):
        return await bot.send_message(
            user_id,
            "» ᴀᴘɪ ɪᴅ ᴏʀ ᴀᴘɪ ʜᴀsʜ ɪs ɪɴᴠᴀʟɪᴅ.\n\nᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ɢᴇɴᴇʀᴀᴛɪɴɢ ʏᴏᴜʀ sᴇssɪᴏɴ ᴀɢᴀɪɴ."
        )
    except (PhoneNumberInvalid):
        return await bot.send_message(
            user_id,
            "» ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ ɪɴᴠᴀʟɪᴅ.\n\nᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ɢᴇɴᴇʀᴀᴛɪɴɢ ʏᴏᴜʀ sᴇssɪᴏɴ ᴀɢᴀɪɴ."
        )
    
    
    try:
        otp = await bot.ask(
            chat_id=message.from_user.id,
            text=f"I had sent an OTP to the number {phone_number} through Telegram App  💌\n\nPlease enter the OTP in the format `1 2 3 4 5` (provied white space between numbers)",
            filters=filters.text,
            timeout=600,
        )
        if await cancelled(otp):
            return
    except ListenerTimeout:
        return await bot.send_message(
            user_id,
            "» ᴛɪᴍᴇ ʟɪᴍɪᴛ ʀᴇᴀᴄʜᴇᴅ ᴏғ 10 ᴍɪɴᴜᴛᴇs.\n\nᴩʟᴇᴀsᴇ sᴛᴀʀᴛ ɢᴇɴᴇʀᴀᴛɪɴɢ ʏᴏᴜʀ sᴇssɪᴏɴ ᴀɢᴀɪɴ."
        )

    otp = otp.text.replace(" ", "")
    try:
        await client.sign_in(phone_number, code.phone_code_hash, otp)
    except (PhoneCodeInvalid):
        return await bot.send_message(
            user_id,
            "» ᴛʜᴇ ᴏᴛᴩ ʏᴏᴜ'ᴠᴇ sᴇɴᴛ ɪs <b>ᴡʀᴏɴɢ.</b>\n\nᴩʟᴇᴀsᴇ sᴛᴀʀᴛ ɢᴇɴᴇʀᴀᴛɪɴɢ ʏᴏᴜʀ sᴇssɪᴏɴ ᴀɢᴀɪɴ."
        )
    except (PhoneCodeExpired):
        return await bot.send_message(
            user_id,
            "» ᴛʜᴇ ᴏᴛᴩ ʏᴏᴜ'ᴠᴇ sᴇɴᴛ ɪs <b>ᴇxᴩɪʀᴇᴅ.</b>\n\nᴩʟᴇᴀsᴇ sᴛᴀʀᴛ ɢᴇɴᴇʀᴀᴛɪɴɢ ʏᴏᴜʀ sᴇssɪᴏɴ ᴀɢᴀɪɴ."
        )
    except (SessionPasswordNeeded):
        try:
            pwd = await bot.ask(
                chat_id=message.from_user.id,
                text="🔐 This account have two-step verification code.\nPlease enter your second factor authentication code.",
                filters=filters.text,
                timeout=300,
            )
        except ListenerTimeout:
            return bot.send_message(
                user_id,
                "» ᴛɪᴍᴇᴅ ʟɪᴍɪᴛ ʀᴇᴀᴄʜᴇᴅ ᴏғ 5 ᴍɪɴᴜᴛᴇs.\n\nᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ɢᴇɴᴇʀᴀᴛɪɴɢ sᴇssɪᴏɴ ᴀɢᴀɪɴ."
            )

        if await cancelled(pwd):
            return
        pwd = pwd.text

        try:
            
            await client.check_password(password=pwd)
        except (PasswordHashInvalid):
            return await bot.send_message(
                user_id,
                "» ᴛʜᴇ ᴩᴀssᴡᴏʀᴅ ʏᴏᴜ'ᴠᴇ sᴇɴᴛ ɪs ᴡʀᴏɴɢ.\n\nᴩʟᴇᴀsᴇ sᴛᴀʀᴛ ɢᴇɴᴇʀᴀᴛɪɴɢ ʏᴏᴜʀ sᴇssɪᴏɴ ᴀɢᴀɪɴ."
            )

    except Exception as ex:
        return await bot.send_message(user_id, f"ᴇʀʀᴏʀ : <code>{str(ex)}</code>")

    try:
        string_session = await client.export_session_string()
        try:
            await client.disconnect()
        except:
            pass
        return string_session
    except KeyError:
        pass


from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from plugins.utils import db, get_country_from_phone, get_account_age, check_2fa
@Client.on_message(filters.private & filters.command('addacc') & filters.user(Config.ADMIN))
async def add_userbot(bot: Client, message: Message):
    """Add a user bot (Pyrogram session)"""
    user_id = message.from_user.id
    session = await generate_session(bot, message)
    try:
        user_client = Client(
            name=f"user_{user_id}_{int(time.time())}",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            session_string=session
        )
        await user_client.start()
        me = await user_client.get_me()
        phone = getattr(me, "phone_number", "Unknown")
        info = {
            "_id": me.id,
            "account_num": await db.get_next_account_num(),
            "name": me.first_name or me.username or "N/A",
            "phone": phone,
            "country": get_country_from_phone(f"+{phone}") if phone != "Unknown" else "Unknown",
            "age": await get_account_age(user_client),
            "twofa": await check_2fa(user_client),
            "session_string": session,
            "by": f"{message.from_user.first_name}({message.from_user.id})"
        }
        acc_num = await db.save_account(me.id, info)
        await message.reply_text(
            f"✅ Account `#{acc_num}` (`{info['name']}`) added successfully!",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        return await message.reply_text(f"**⚠️ USER BOT ERROR:** `{e}`")

    finally:
        try:
            await user_client.stop()
        except:
            pass

    
