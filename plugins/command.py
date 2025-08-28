
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
from tdata_converter import convert_tdata   # external helper (see note)


API_ID = Config.API_ID       # from my.telegram.org
API_HASH = Config.API_HASH

def login_with_tdata(tdata_path):
    """
    Convert Telegram Desktop tdata -> Telethon session.
    """
    session = convert_tdata(tdata_path, API_ID, API_HASH)
    with TelegramClient(session, API_ID, API_HASH) as client:
        me = client.get_me()
        return me, client.session.save()


@bot.on_message(filters.document & filters.private)
async def handle_zip(client, message):
    if not message.document.file_name.endswith(".zip"):
        return await message.reply("❌ Please send a valid .zip containing tdata.")

    # Create temp dir
    temp_dir = tempfile.mkdtemp()
    zip_path = await message.download(file_name=os.path.join(temp_dir, message.document.file_name))

    # Extract
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    # Find tdata inside structure
    tdata_path = None
    for root, dirs, files in os.walk(temp_dir):
        if "tdata" in dirs:
            tdata_path = os.path.join(root, "tdata")
            break

    if not tdata_path:
        shutil.rmtree(temp_dir)
        return await message.reply("❌ No tdata folder found inside the .zip")

    try:
        me, session_string = login_with_tdata(tdata_path)
        await message.reply(
            f"✅ Logged in as {me.first_name} (@{me.username or me.id})\n\n"
            f"🔑 Session String (Telethon):\n`{session_string}`"
        )
    except Exception as e:
        await message.reply(f"⚠️ Error: {e}")
    finally:
        shutil.rmtree(temp_dir)
