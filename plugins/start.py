import motor.motor_asyncio
from config import Config, Txt
import random, asyncio
from collections import defaultdict
import pytz
from datetime import datetime, timedelta
from telethon.tl.functions.account import UpdateProfileRequest
from pyrogram import Client, filters, enums
from telethon.tl.functions.channels import GetForumTopicsRequest
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
india = pytz.timezone("Asia/Kolkata")

sessions = {}
API_HASH = Config.API_HASH
API_ID = Config.API_ID

class temp(object):
    ME = None
    U_NAME = None
    B_NAME = None
    
class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.used

    async def save_account(self, user_id, info, tdata_bytes):
        """
        Save account info + tdata in MongoDB
        """
        doc = {
            "_id": user_id,   # unique by account id
            "name": info["name"],
            "phone": info["phone"],
            "twofa": info["twofa"],
            "spam": info["spam"],
            "tdata": base64.b64encode(tdata_bytes).decode("utf-8")
        }
        await self.col.update_one({"_id": user_id}, {"$set": doc}, upsert=True)

    async def total_users_count(self):
        return await self.col.count_documents({})

db = Database(Config.DB_URL, Config.DB_NAME)

async def start_forwarding_process(client: Client, user_id: int, user: dict):
    syd = await client.send_message(user_id, "Sᴛᴀʀɪɴɢ....")
    is_premium = user.get("is_premium", False)
    can_use_interval = user.get("can_use_interval", False)
    clients = []
    user_groups = []

    for acc in user["accounts"]:
        session = StringSession(acc["session"])
        tele_client = TelegramClient(session, Config.API_ID, Config.API_HASH)
        await tele_client.start()
        clients.append(tele_client)

        me = await tele_client.get_me()
        session_user_id = me.id

        group_data = await db.group.find_one({"_id": session_user_id}) or {"groups": []}
        groups = group_data["groups"]
        user_groups.append(groups)

    if not any(user_groups):
        await syd.delete()
        return await client.send_message(user_id, "Nᴏ ɢʀᴏᴜᴩꜱ ꜱᴇʟᴇᴄᴛᴇᴅ. Uꜱᴇ /groups ᴛᴏ ᴀᴅᴅ ꜱᴏᴍᴇ.")

    sessions[user_id] = clients
    await db.update_user(user_id, {"enabled": True})
    if index > 0:
        return
    syd = await client.send_message(user_id, "Sᴇɴᴅɪɴɢ ꜰᴏʀᴡᴀʀᴅ ᴅᴀᴛᴀ...")

    entries = await db.user_messages.find({"user_id": user_id}).to_list(None)
    if not entries:
        return await syd.edit("No forwarding data found for this user.")

    grouped = defaultdict(list)
    group_names = {}
    for entry in entries:
        group_id = entry.get("group_id")
        name = entry.get("name")
        timestamp = entry.get("time")

        if isinstance(timestamp, datetime):
            timestamp = timestamp.astimezone(india)
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S IST")
        else:
            timestamp_str = str(timestamp)

        grouped[group_id].append(timestamp_str)
        if group_id not in group_names:
            group_names[group_id] = name or "Unknown"

    for group_id in grouped:
        grouped[group_id].sort()

    out = f"User ID: {user_id}\n"
    for group_id, times in grouped.items():
        group_name = group_names.get(group_id, "Unknown")
        out += f"  => Group ID: {group_id} | Name: {group_name}\n"
        for t in times:
            out += f"    - {t}\n"

    with open("forward.txt", "w", encoding="utf-8") as f:
        f.write(out)
    await client.send_document(user_id, "forward.txt", caption=f"Fᴏʀᴡᴀʀᴅ ʟᴏɢꜱ")
    await db.user_messages.delete_many({"user_id": user_id})
    await syd.delete()



async def start_forwarding(client, user_id):
    #Don't Use Directly
    user = await db.get_user(user_id)
    usr = await client.get_users(user_id)
    user_nam = f"For @{usr.username}" if usr.username else ""
    if not user or not user.get("accounts"):
        await client.send_message(user_id, "No userbot account found. Use /add_account first.")
        return
        
    syd = await client.send_message(user_id, "Starting...")

    is_premium = user.get("is_premium", False)
    can_use_interval = user.get("can_use_interval", False)
    clients = []
    user_groups = []

    for acc in user["accounts"]:
        session = StringSession(acc["session"])
        tele_client = TelegramClient(session, Config.API_ID, Config.API_HASH)
        await tele_client.start()
        clients.append(tele_client)

        me = await tele_client.get_me()
        session_user_id = me.id
        
        group_data = await db.group.find_one({"_id": session_user_id}) or {"groups": []}
        groups = group_data["groups"]
        user_groups.append(groups)

    if not any(user_groups):
        await client.send_message(user_id, "No groups selected. Use /groups to add some.")
        return

    sessions[user_id] = clients
    await db.update_user(user_id, {"enabled": True})
    await syd.delete()
    await client.send_message(user_id, "Forwarding started.")

    for i, tele_client in enumerate(clients):
        groups = user_groups[i]
        mee = await tele_client.get_me()
        groupdata = await db.group.find_one({"_id": mee.id})
        if i != 0:
            wait_time = groupdata.get("interval", 300)
            await asyncio.sleep(wait_time)
        asyncio.create_task(
            start_forwarding_loop(tele_client, user_id, groups, is_premium, can_use_interval, client, i)
        )
        

@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    if message.from_user.id in Config.BANNED_USERS:
        await message.reply_text("Sorry, You are banned.")
        return

    used = message.from_user
    user = await db.col.find_one({"_id": used.id})

    if not user:
        user_data = {
            "_id": used.id,
            "is_premium": False,
            "name": used.first_name,
            "accounts": [],
            "enabled": False,
            "intervals": {},
        }
        await db.col.insert_one(user_data)
        try:
            await client.send_message(
                Config.LOG_CHANNEL,
                f"#New_User \nUser: <a href='tg://user?id={user_id}'>{used.first_name}</a> \n(User ID: <code>{user_id}</code>)",
                parse_mode=enums.ParseMode.HTML
            )
        except:
            pass
    button=InlineKeyboardMarkup([[
                InlineKeyboardButton('Gᴜɪᴅᴇ', callback_data='guide'),
                InlineKeyboardButton('Tɪᴇʀ', callback_data='tier')
            ], [
                InlineKeyboardButton('Iɴᴄʀᴇᴀꜱᴇ Lɪᴍɪᴛ', url='https://t.me/vizean'),
                InlineKeyboardButton('Gᴇɴᴇʀᴀᴛᴇ Sᴛʀɪɴɢ', url='https://t.me/snowstringgenbot')
            ], [
                InlineKeyboardButton('Aᴅᴅ Aᴄᴄᴏᴜɴᴛ', callback_data='add_account')
          ]])
    if Config.PICS:
        await message.reply_photo(random.choice(Config.PICS), caption=Txt.START_TXT.format(used.mention, temp.U_NAME, temp.B_NAME), reply_markup=button, parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text(text=Txt.START_TXT.format(used.mention, temp.U_NAME, temp.B_NAME), reply_markup=button, disable_web_page_preview=True)




@Client.on_message(filters.command("stop") & filters.private)
async def stop_forwarding(client, message):
    user_id = message.from_user.id
    await db.update_user(user_id, {"enabled": False})
    if user_id in sessions:
        for tele_client in sessions[user_id]:
            await tele_client.disconnect()
        sessions.pop(user_id)
    await message.reply("Trying To Stop.")
    
@Client.on_message(filters.command("run") & filters.private)
async def run_forwarding(client: Client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    usr = await client.get_users(user_id)
    user_nam = f"For @{usr.username}" if usr.username else ""
    if not user or not user.get("accounts"):
        return await message.reply("No userbot account found. Use /add_account first.")

    if user.get("enabled", False):
        return await message.reply("Fᴏʀᴡᴀʀᴅɪɴɢ ᴀʟʀᴇᴀᴅʏ ʀᴜɴɴɪɴɢ. Uꜱᴇ /stop ᴛᴏ ᴇɴᴅ ɪᴛ ʙᴇꜰᴏʀᴇ ꜱᴛᴀʀᴛɪɴɢ ᴀɢᴀɪɴ.")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Fᴏʀᴡᴀʀᴅ : Sᴀᴠᴇᴅ Mᴇꜱꜱᴀɢᴇ", callback_data="normal")
        ], [
            InlineKeyboardButton("Fᴏʀᴡᴀʀᴅ : Wɪᴛʜ Tᴀɢ", callback_data="forward")
        ]
    ])
    choose = await message.reply(
        "Hᴏᴡ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ꜱᴇɴᴅ ᴛʜᴇ ᴍᴇꜱꜱᴀɢᴇ?\nCʟɪᴄᴋ ᴏɴ ꜱᴀᴠᴇᴅ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ꜱᴇɴᴅ ʟᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ ꜱᴀᴠᴇᴅ ʙʏ ᴛʜᴇ ᴜꜱᴇʀ ʙᴏᴛ\nCʟɪᴄᴋ ᴏɴ ᴡɪᴛʜ ᴛᴀɢ ɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ꜱᴇɴᴅ ᴍᴇꜱꜱᴀɢᴇ ᴡɪᴛʜ ᴛʜᴇ ꜰᴏʀᴡᴀʀᴅ ᴛᴀɢ [ʏᴏᴜ ʜᴀᴠᴇ ᴛᴏ ɢɪᴠᴇ ᴛʜᴇ ɪɴᴩᴜᴛ ꜰᴏʀ ᴛʜᴀᴛ] \nCʜᴏᴏꜱᴇ ᴀɴ ᴏᴩᴛɪᴏɴ ʙᴇʟᴏᴡ (timeout 60s):",
        reply_markup=keyboard
    )
    await asyncio.sleep(60)
    try:
        await choose.delete()
    except:
        pass
    return
   
@Client.on_message(filters.command(["interval", "group_limit", "account_limit"]) & filters.user(Config.ADMIN))
async def admin_command(client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text(
            "Usage:\n"
            "/interval y/n user_id\n"
            "/group_limit <number> user_id\n"
            "/account_limit <number> user_id"
        )

    command = message.command[0].lower()
    value = message.command[1]
    try:
        user_id = int(message.command[2])
    except ValueError:
        return await message.reply_text("Invalid user_id. Please provide a valid number.")

    user = await db.col.find_one({"_id": user_id})
    if not user:
        return await message.reply_text("User not found in database.")

    update = {}

    if command == "interval":
        if value.lower() not in ["y", "n"]:
            return await message.reply_text("Value must be 'y' or 'n'.")
        update["can_use_interval"] = value.lower() == "y"

    elif command == "group_limit":
        if not value.isdigit():
            return await message.reply_text("Group limit must be a digit.")
        update["group_limit"] = int(value)

    elif command == "account_limit":
        if not value.isdigit():
            return await message.reply_text("Account limit must be a digit.")
        update["account_limit"] = int(value)

    await db.col.update_one({"_id": user_id}, {"$set": update})
    await message.reply_text(f"Updated `{command}` settings for user `{user_id}`.")


@Client.on_message(filters.command("account") & filters.private)
async def show_accounts_interval(client: Client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or not user.get("accounts"):
        return await message.reply("❗ Please add an account first using /add_account")

    accounts = user["accounts"]

    if len(accounts) == 1:
        return await message.reply("⚠️ You only have one account. Interval applies only when multiple accounts are used.")

    buttons = []
    for i, acc in enumerate(accounts):
        try:
            async with TelegramClient(StringSession(acc["session"]), Config.API_ID, Config.API_HASH) as userbot:
                me = await userbot.get_me()
                acc_name = me.first_name or me.username or f"Account {i+1}"
        except Exception:
            acc_name = f"Account {i+1} (invalid)"
        buttons.append([
            InlineKeyboardButton(f"{acc_name}", callback_data=f"set_interval_account_{i}")
        ])

    await message.reply(
        "🕒 Choose an account to set the default interval:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_message(filters.command("groups") & filters.private)
async def show_accounts(client: Client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or not user.get("accounts"):
        return await message.reply("Please add an account first using /add_account")
    accounts = user["accounts"]
    buttons = []
    for i, acc in enumerate(accounts):
        try:
            async with TelegramClient(StringSession(acc["session"]), Config.API_ID, Config.API_HASH) as userbot:
                me = await userbot.get_me()
                acc_name = me.first_name or me.username or f"Account {i+1}"
        except Exception:
            acc_name = f"Account {i+1} (invalid)"
        buttons.append([
            InlineKeyboardButton(acc_name, callback_data=f"choose_account_{i}")
        ])
    await message.reply(
        "Choose an account to manage groups:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_message(filters.command("remove_premium") & filters.user(Config.ADMIN))
async def remove_premium(client, message):
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("Usage: /remove_premium user_id")
    try:
        user_id = int(parts[1])
    except:
        return await message.reply("Invalid user ID.")

    await db.col.update_one({"_id": user_id}, {"$set": {"is_premium": False}})
    await message.reply(f"Premium removed from user `{user_id}`", parse_mode=enums.ParseMode.HTML)



@Client.on_message(filters.command("delete_account") & filters.private)
async def delete_account_handler(client, message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or not user.get("accounts"):
        return await message.reply("Please add an account first using /add_account")
    accounts = user["accounts"]
    buttons = []
    for i, acc in enumerate(accounts):
        try:
            async with TelegramClient(StringSession(acc["session"]), Config.API_ID, Config.API_HASH) as userbot:
                me = await userbot.get_me()
                acc_name = me.first_name or me.username or f"Account {i+1}"
        except Exception:
            acc_name = f"Account {i+1} (invalid)"

        buttons.append([
            InlineKeyboardButton(f"Delete {acc_name}", callback_data=f"choose_delete_{i}")
        ])

    await message.reply(
        "Select the account you want to delete:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )



