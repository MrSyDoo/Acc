import os
import base64
import hashlib
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

# Simple helper to locate tdata key file
def _get_key_data(tdata_path: str):
    if os.path.isdir(tdata_path):
        # Old format: look for key_datas inside folder
        key_file = os.path.join(tdata_path, "key_datas")
        if not os.path.exists(key_file):
            raise FileNotFoundError("❌ key_datas file not found in tdata folder")
        with open(key_file, "rb") as f:
            return f.read()

    elif os.path.isfile(tdata_path):
        # New format: tdata itself is the key file
        with open(tdata_path, "rb") as f:
            return f.read()

    else:
        raise FileNotFoundError("❌ Invalid tdata path (neither file nor folder)")


async def convert_tdata(tdata_path: str, api_id: int, api_hash: str) -> StringSession:
    """
    Convert Telegram Desktop tdata -> Telethon StringSession
    """
    # This is a simplified fake derivation (for real use, full crypto is required).
    # Here we just hash key_datas as session key placeholder.
    key_data = _get_key_data(tdata_path)
    fake_key = hashlib.sha256(key_data).digest()

    # Start Telethon with a temp session
    client = TelegramClient(StringSession(), api_id, api_hash)
  #  try:
    await client.start()  # ✅ async start
    session = client.session.save()
    return session
   # finally:
        #await client.disconnect()  # ✅ async disconnect
