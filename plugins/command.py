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

        return {
            "name": name.strip(),
            "phone": phone,
            "twofa": twofa,
            "spam": spam
        }


@Client.on_message(filters.document & filters.private)
async def handle_zip(client, message):
    if not message.document.file_name.endswith(".zip"):
        return await message.reply("❌ Please send a valid .zip containing accounts.")

    # Temp dir
    temp_dir = tempfile.mkdtemp()
    zip_path = await message.download(file_name=os.path.join(temp_dir, message.document.file_name))

    # Extract all
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    results = []
    account_num = 1

    # Walk through all extracted dirs
    for root, dirs, files in os.walk(temp_dir):
        if "tdata" in dirs:
            tdata_path = os.path.join(root, "tdata")
            try:
                info = login_with_tdata(tdata_path)
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

    # Write to txt
    result_txt = os.path.join(temp_dir, "accounts_report.txt")
    with open(result_txt, "w", encoding="utf-8") as f:
        f.write("\n\n".join(results))

    # Send back
    await message.reply_document(result_txt, caption="📄 Accounts Report")

    shutil.rmtree(temp_dir)
