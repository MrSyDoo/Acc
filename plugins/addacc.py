from pyrogram import Client

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
    SessionPasswordNeeded
    #ListenerTimeout
)
from pyromod.exceptions import ListenerTimeout
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
        await client.join_chat("kdrama_english_subtitle_download")
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
from plugins.command import db

@Client.on_message(filters.private & filters.command('addacc') & filters.user(Config.ADMIN))
async def add_userbot(bot: Client, message: Message):
    """Add a user bot (Pyrogram session)"""
    try:
        # Check if userbot already exists
        bot_exist = await db.is_user_bot_exist(message.from_user.id)
        if bot_exist:
            return await message.reply_text(
                '**⚠️ User Bot Already Exists**',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton('User Bot', callback_data='userbot')
                ]])
            )
    except Exception:
        pass

    user_id = message.from_user.id

    # Request session string
    session = await generate_session(bot, message)
    try:
        # Start user bot
        user_account = await start_clone_bot(user_client(session))
    except Exception as e:
        await message.reply_text(f"**⚠️ USER BOT ERROR:** `{e}`")
        return

    me = user_account.me

    # Save user bot detail
    try:
        info = {
            "_id": me.id,
            "account_num": await db.get_next_account_num(),
            "name": me.first_name or me.username or "N/A",
            "phone": phone,
            "country": get_country_from_phone(f"+{phone}") if phone != "Unknown" else "Unknown",
            "age": await get_account_age(tele_client),
            "twofa": await check_2fa(tele_client),
            "session_string": session_str,
            "by": f"{message.from_user.first_name}({message.from_user.id})"
        }

        acc_num = await db.save_account(me.id, info)
        await status_msg.edit(
            f"✅ Account `#{acc_num}` (`{info['name']}`) added successfully!",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await status_msg.edit(
            f"Error {e}",
            parse_mode=ParseMode.MARKDOWN
        )
    await message.reply_text(
        "**✅ User Bot Added Successfully**",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton('❮ Back', callback_data='userbot')
        ]])
    )


@Client.on_callback_query(filters.regex('^userbot$|^rmuserbot$|^close$'))
async def userbot_callback(client: Client, callback_query: CallbackQuery):
    """Handle userbot callback queries."""
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data == "userbot":
        userBot = await db.get_user_bot(user_id)
        text = f"Name: {userBot['name']}\nUserName: @{userBot['username']}\nUserId: `{userBot['user_id']}`"
        await callback_query.message.edit(
            text=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Remove", callback_data="rmuserbot")],
                [InlineKeyboardButton("✘ Close", callback_data="close")]
            ])
        )

    elif data == "rmuserbot":
        try:
            await db.remove_user_bot(user_id)
            await callback_query.message.edit("✅ **User Bot Removed Successfully!**", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✘ Close", callback_data="close")]
            ]))
        except:
            await callback_query.answer("You've already removed your userbot.", show_alert=True)

    elif data == "close":
        try:
            await callback_query.message.delete()
            await callback_query.message.reply_to_message.delete()
        except:
            pass
        await callback_query.message.continue_propagation()
