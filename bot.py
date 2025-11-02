
import warnings
from pyrogram import Client, idle, filters
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from config import Config
from aiohttp import web
from plugins.web_support import web_server
from pytz import timezone

from datetime import datetime
import asyncio
import os
from threading import Thread
from time import sleep
from pyromod import listen



class Bot(Client):

    def __init__(self):
        super().__init__(
            "AddBot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        
        
        if Config.WEBHOOK:
            app = web.AppRunner(await web_server())
            await app.setup()
            bind_address = "0.0.0.0"
            await web.TCPSite(app, bind_address, Config.PORT).start()
        print(f"{me.first_name} ✅✅ BOT started successfully ✅✅")

        for id in Config.ADMIN:
            try:
                await self.send_message(id, f"**__{me.first_name}  Iꜱ Sᴛᴀʀᴛᴇᴅ.....✨️__**")
            except:
                pass

        
        
    async def stop(self, *args):
        await super().stop()
        print("Bot Stopped 🙄")
        
    
bot = Bot()
bot.run()
