import os
import base64
import hashlib
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

# Simple helper to locate tdata key file
def _get_key_data(tdata_path: str):
    key_file = os.path.join(tdata_path, "key_datas")
    if not os.path.exists(key_file):
        raise FileNotFoundError("❌ key_datas file not found in tdata")

    with open(key_file, "rb") as f:
        return f.read()


def convert_tdata(tdata_path: str, api_id: int, api_hash: str) -> StringSession:
    """
    Convert Telegram Desktop tdata -> Telethon StringSession
    """
    # This is a simplified fake derivation (for real use, full crypto is required).
    # Here we just hash key_datas as session key placeholder.
    key_data = _get_key_data(tdata_path)
    fake_key = hashlib.sha256(key_data).digest()

    # Start Telethon with a temp session
    client = TelegramClient(StringSession(), api_id, api_hash)
    client.start()  # will not re-login if already valid
    session = client.session.save()
    client.disconnect()
    return session
