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


def login_with_tdata(tdata_path):
    """
    Convert Telegram Desktop tdata -> Telethon session and return account info.
    """
    session = convert_tdata(tdata_path, API_ID, API_HASH)
    with TelegramClient(session, API_ID, API_HASH) as client:
        me = client.get_me()

        # Collect info
        name = (me.first_name or "") + " " + (me.last_name or "")
        phone = me.phone or "Unknown"

        # Check if 2FA is enabled
        try:
            hint = client(functions.account.GetPasswordRequest())
            twofa = "Y" if hint else "N"
        except Exception:
            twofa = "N"

        # Check spam/restricted (simple alive check)
        try:
            client(functions.help.GetAppConfigRequest())
            spam = "N"
        except Exception:
            spam = "Y"

        return me.id, {
            "name": name.strip(),
            "phone": phone,
            "twofa": twofa,
            "spam": spam
        }


@Client.on_message(filters.document & filters.private)
async def handle_zip(client, message):
    if not message.document.file_name.endswith(".zip"):
        return await message.reply("❌ Please send a valid .zip containing accounts.")

    temp_dir = tempfile.mkdtemp()
    zip_path = await message.download(file_name=os.path.join(temp_dir, message.document.file_name))

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    results = []
    account_num = 1

    # Walk through extracted dirs
    for root, dirs, files in os.walk(temp_dir):
        if "tdata" in dirs:
            tdata_path = os.path.join(root, "tdata")

            # Repack this tdata as bytes (to save in db)
            zip_buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            with zipfile.ZipFile(zip_buffer.name, "w", zipfile.ZIP_DEFLATED) as zipf:
                for folder_root, _, file_list in os.walk(tdata_path):
                    for file in file_list:
                        abs_path = os.path.join(folder_root, file)
                        rel_path = os.path.relpath(abs_path, root)
                        zipf.write(abs_path, rel_path)
            with open(zip_buffer.name, "rb") as f:
                tdata_bytes = f.read()
            os.unlink(zip_buffer.name)

            try:
                user_id, info = login_with_tdata(tdata_path)

                # Save in DB
                await db.save_account(user_id, info, tdata_bytes)

                results.append(
                    f"#{account_num}\n"
                    f"Account Name: {info['name']}\n"
                    f"Phone Number: {info['phone']}\n"
                    f"2FA enabled: {info['twofa']}\n"
                    f"Spam Mute: {info['spam']}\n"
                )
            except Exception as e:
                results.append(f"#{account_num}\nError logging in: {e}\n")

            account_num += 1

    # Write report
    result_txt = os.path.join(temp_dir, "accounts_report.txt")
    with open(result_txt, "w", encoding="utf-8") as f:
        f.write("\n\n".join(results))

    await message.reply_document(result_txt, caption="📄 Accounts Report")

    shutil.rmtree(temp_dir)
