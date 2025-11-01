import re
import os
import time

id_pattern = re.compile(r'^.\d+$')


class Config(object):
    # pyro client config
    API_ID = os.environ.get("API_ID", "")  # ⚠️ Required
    API_HASH = os.environ.get("API_HASH", "")  # ⚠️ Required
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")  # ⚠️ Required

    #2fa
    USERPASS = "YoWaKeUp" #for other user or set = MAINPASS , if don't need
    MAINPASS = "AnYtHing Huh?"

    #purchase
    USETXT = """ Text
    Goes 
    Here
    """
    # database config
    DB_NAME = os.environ.get("DB_NAME", "cluster0")
    DB_URL = os.environ.get("DB_URL", "")  # ⚠️ Required

    # other configs
    BOT_UPTIME = time.time()
    PICS = os.environ.get("PICS", 'https://envs.sh/s3r.jpg https://envs.sh/s33.jpg').split()
    ADMIN = [int(admin) if id_pattern.search(
        admin) else admin for admin in os.environ.get('ADMIN', '').split()]  # ⚠️ Required

    # wes response configuration
    WEBHOOK = bool(os.environ.get("WEBHOOK", True))
    PORT = int(os.environ.get("PORT", "8080"))


class Txt(object):
    # part of text configuration
    START_TXT = """<b>ʜᴇʏ {} 👋, ɪ'ᴍ ᴀ ᴩᴇʀꜱᴏɴᴀʟɪꜱᴇᴅ ʙᴏᴛ.... ᴍᴀᴅᴇ ꜰᴏʀ ᴩʀɪᴠᴀᴛᴇ ᴜꜱᴇ.</b>"""


    
    
    
