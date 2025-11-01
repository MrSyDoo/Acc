import os
import re
import tempfile
import zipfile
import asyncio
from functools import wraps

# Config
from config import Config

# Pyrogram
from pyrogram.types import Message

# Telethon
from telethon import TelegramClient, functions
from telethon.sessions import StringSession
from telethon.errors import (
    RPCError,
    FloodWaitError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
)
from telethon.tl.functions.account import GetPasswordRequest
from telethon.tl.functions.auth import ResetAuthorizationsRequest

from telethon.tl.types import account

# OpenTele
from opentele.td import TDesktop
from opentele.api import UseCurrentSession
from opentele.exception import NoPasswordProvided

# Database
import motor.motor_asyncio

# Phone Lib
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException

# --- Constants ---
API_ID = Config.API_ID
API_HASH = Config.API_HASH
ADMINS = Config.ADMIN
USERPASS = Config.USERPASS
MAINPASS = Config.MAINPASS

# --- Database Class & Instance ---

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.accounts
        self.syd = self.db.ownership
        self.users = self.db.bot_users
        self.verified = self.db.verified_users
        self.stock = self.db.stock
        self.balances = self.db.balances
        self.locks = self.db.locks
        self.sections = self.db.sections

    # --- User & Verification Management ---
    async def add_user(self, user_id: int):
        await self.users.update_one({"_id": user_id}, {"$set": {}}, upsert=True)
        await self.balances.update_one({"_id": user_id}, {"$setOnInsert": {"balance": 0.0}}, upsert=True)

    async def get_all_users(self):
        return self.users.find({})

    async def total_users_count(self):
        return await self.users.count_documents({})

    async def delete_user(self, user_id: int):
        await self.users.delete_one({"_id": user_id})
        
    async def is_verified(self, user_id: int):
        has_account = await self.syd.find_one({"_id": user_id})
        return bool(has_account) or bool(await self.verified.find_one({"_id": user_id}))

    async def add_verified(self, user_id: int):
        await self.verified.update_one({"_id": user_id}, {"$set": {"verified": True}}, upsert=True)

    async def revoke_verified(self, user_id: int):
        await self.verified.delete_one({"_id": user_id})

    # --- Balance Management ---
    async def get_balance(self, user_id: int):
        bal = await self.balances.find_one({"_id": user_id})
        return bal['balance'] if bal else 0.0

    async def update_balance(self, user_id: int, amount: float):
        await self.balances.update_one({"_id": user_id}, {"$inc": {"balance": amount}}, upsert=True)

    # --- Transaction Locking ---
    async def lock_user(self, user_id: int):
        try:
            await self.locks.insert_one({"_id": user_id})
            return True
        except:
            return False

    async def unlock_user(self, user_id: int):
        await self.locks.delete_one({"_id": user_id})

    # --- Account & Ownership Management ---
    async def save_account(self, user_id, info):
        existing = await self.col.find_one({"_id": user_id})
        if existing:
            account_num = existing["account_num"]
        else:
            if info.get("phone"):
                phone_match = await self.col.find_one({"phone": info["phone"]})
                if phone_match:
                    account_num = phone_match["account_num"]
                    user_id = phone_match["_id"]
                else:
                    account_num = await self.get_next_account_num()
            else:
                account_num = await self.get_next_account_num()
        doc = {
            "_id": user_id,
            "account_num": account_num,
            "name": info.get("name", "?"),
            "phone": info.get("phone", "?"),
            "country": info.get("country", "N/A"),
            "age": info.get("age", "Unknown"),
            "twofa": info.get("twofa", "?"),
            "spam": info.get("spam", "?"),
            "by": info.get("by", "?"),
            "tdata": info.get("tdata", None),
            "session_string": info.get("session_string", None),
        }
        await self.col.update_one({"account_num": account_num}, {"$set": doc}, upsert=True)
        return account_num

    async def reset_field(self, user_id, field: str, value="?"):
        await self.col.update_one(
            {"_id": user_id},
            {"$set": {field: value}}
        )

    async def get_next_account_num(self):
        last = await self.col.find_one(sort=[("account_num", -1)])
        return (last["account_num"] + 1) if last else 1
    
    async def find_account_by_num(self, acc_num: int):
        return await self.col.find_one({"account_num": acc_num})

    async def grant_account(self, user_id: int, acc_num: int):
        acc = await self.col.find_one({"account_num": acc_num})
        if not acc:
            return False, f"Account #{acc_num} does not exist."
        
        await self.stock.delete_many({"account_num": acc_num})
        await self.syd.update_one(
            {"_id": user_id},
            {"$addToSet": {"accounts": acc_num}},
            upsert=True,
        )
        return True, f"Granted account #{acc_num} to user {user_id}"

    async def get_user_account_info(self, user_id: int):
        doc = await self.syd.find_one({"_id": user_id})
        if not doc or "accounts" not in doc:
            return []
        cursor = self.col.find({"account_num": {"$in": doc["accounts"]}})
        return [acc async for acc in cursor]

    async def validate_accounts_for_stock(self, acc_nums: list):
        owned_accounts_cursor = self.syd.find({}, {"accounts": 1})
        owned_set = set()
        async for doc in owned_accounts_cursor:
            owned_set.update(doc.get("accounts", []))
            
        valid_accs, invalid_accs = [], []
        for num in acc_nums:
            if num in owned_set:
                invalid_accs.append(num)
                continue
            acc_doc = await self.find_account_by_num(num)
            if not acc_doc:
                invalid_accs.append(num)
                continue
            valid_accs.append(num)
        return valid_accs, invalid_accs
        
    async def list_accounts(self):
        cursor = self.col.find({}, {"_id": 0, "account_num": 1, "name": 1, "phone": 1, "by": 1})
        return [doc async for doc in cursor]

    async def remove_stock_item(self, acc_num: int):
        result = await self.stock.delete_many({"account_num": acc_num})
        return result.deleted_count > 0

    # --- Stock & Section Management ---
    async def add_stock_item(self, price: float, acc_num: int, section: str):
        exists = await self.stock.find_one({"account_num": acc_num, "section": section})
        if exists: return False
        await self.stock.insert_one({"account_num": acc_num, "section": section.strip(), "price": price})
        return True

    async def get_stock_sections(self):
        return [s['name'] async for s in self.sections.find({}, {"_id": 0, "name": 1})]

    async def add_section(self, section_name: str):
        exists = await self.sections.find_one({"name": section_name})
        if exists: return False
        await self.sections.insert_one({"name": section_name})
        return True

    async def remove_section(self, section_name: str):
        await self.stock.delete_many({"section": section_name})
        await self.sections.delete_one({"name": section_name})

    async def rename_section(self, old_name: str, new_name: str):
        await self.stock.update_many({"section": old_name}, {"$set": {"section": new_name}})
        await self.sections.update_one({"name": old_name}, {"$set": {"name": new_name}})

    async def count_stock_in_section(self, section: str):
        return await self.stock.count_documents({"section": section})

    async def get_stock_in_section(self, section: str):
        return self.stock.find({"section": section})

    async def get_stock_item_by_acc_num(self, acc_num: int):
        return await self.stock.find_one({"account_num": acc_num})

# --- Database Instance ---
db = Database(Config.DB_URL, Config.DB_NAME)

# --- Decorators ---

def require_verified(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        user_id = message.from_user.id
        if await db.is_verified(user_id) or user_id in ADMINS:
            return await func(client, message, *args, **kwargs)
        else:
            # ɴᴏᴛɪꜰʏ ᴀᴅᴍɪɴꜱ
            try:
                tg_user = await client.get_users(user_id)
                name = tg_user.first_name or "Unknown"
                if tg_user.last_name:
                    name += f" {tg_user.last_name}"
            except Exception:
                name = "Unknown"
            for admin_id in ADMINS:
                await client.send_message(
                    admin_id,
                    f"🚨 Uɴᴠᴇʀɪꜰɪᴇᴅ ᴜꜱᴇʀ ᴛʀɪᴇᴅ ᴛᴏ ᴀᴄᴄᴇꜱꜱ:\n"
                    f"👤 {user_id} ({name} : @{message.from_user.username})\n\n"
                    f"✅ Tᴏ ᴠᴇʀɪꜰʏ:\n<code>/verify {user_id}</code>"
                )
            return await message.reply(
                "⛔ Yᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴠᴇʀɪꜰɪᴇᴅ ʏᴇᴛ.\n"
                "⏳ Pʟᴇᴀꜱᴇ ᴡᴀɪᴛ ꜰᴏʀ ᴀᴅᴍɪɴ ᴀᴘᴘʀᴏᴠᴀʟ."
            )
    return wrapper

# --- Helper Functions ---

async def check_2fa(client):
    try:
        pw = await client(GetPasswordRequest())
        if pw.has_password:   # True if 2FA is enabled
            return "2FA: Enabled"
        else:
            return "2FA: Disabled"
    except PasswordHashInvalidError:
        return "2FA: Disabled"
    except Exception as e:
        return f"2FA: Unknown ({e})"

async def set_or_change_2fa(tele_client, new_password: str, old_password: str = None):
    try:
        success = await tele_client.edit_2fa(
            current_password=old_password,   # None if first time, else provide old
            new_password=new_password,       # new 2FA password
            hint="Set via bot"
        )
        if success:
            return True, f"✅ 2FA updated to: `{new_password}`"
        else:
            return False, "❌ Failed to update 2FA."
    except PasswordHashInvalidError:
        return False, "❌ Wrong old password, could not change 2FA."
    except Exception as e:
        return False, f"❌ Error in 2FA update: {e}"

async def terminate_all_other_sessions(client):
    try:
        await client(ResetAuthorizationsRequest())
        return "✅ All other sessions terminated (except this one)."
    except Exception as e:
        return f"❌ Failed to terminate sessions: {e}"

def get_country_from_phone(phone_number: str) -> str:
    try:
        parsed = phonenumbers.parse(phone_number)
        region = phonenumbers.region_code_for_number(parsed)
        if not region:
            return "N/A"

        flag = "".join(chr(127397 + ord(c)) for c in region.upper())
        return f"{flag} {region}"
    except NumberParseException:
        return "N/A"

async def get_account_age(tele_client):
    try:
        await tele_client.send_message('@tgdnabot', '/start')
        await asyncio.sleep(4)

        # Fetch the last 2 messages to be safer
        messages = await tele_client.get_messages('@tgdnabot', limit=2)
        if not messages:
            return "Unknown (No reply)"

        # Check both recent messages
        for msg in messages:
            reply_text = msg.text or ""
            
            # Remove markdown decorations like ** or __
            clean_text = re.sub(r"[*_`]+", "", reply_text)

            # Look for known patterns
            age_match = re.search(r"Account Age:\s*(.+)", clean_text, re.IGNORECASE)
            if age_match:
                return age_match.group(1).strip()

            created_match = re.search(r"Created:\s*(.+)", clean_text, re.IGNORECASE)
            if created_match:
                return f"Since {created_match.group(1).strip()}"

        # If no match in both messages
        return f"Unknown (Format changed)\n<code>{clean_text}</code>"

    except Exception as e:
        return f"Unknown (Error {e})"



async def check_existing_session(account_num, bot): #removed
    try:
        doc = await db.find_account_by_num(account_num)
        if not doc:
            return True, f"❌ Account {account_num} not found in DB."

        if doc.get("session_string"):
            tele_client = TelegramClient(StringSession(doc["session_string"]), API_ID, API_HASH)

        elif doc.get("tdata"):
            with tempfile.TemporaryDirectory() as tempdir:
                zip_path = os.path.join(tempdir, "tdata.zip")
                with open(zip_path, "wb") as f:
                    f.write(doc["tdata"])
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(tempdir)

                from telethon.sessions import TDesktop
                tdesk = TDesktop(tempdir)
                if not tdesk.isLoaded():
                    return True, f"⚠️ Corrupted tdata for {account_num}"

                tele_client = await tdesk.ToTelethon(session=None)

        else:
            return True, f"❌ No session found for {account_num}"

        await tele_client.connect()

        # handle 2FA if required
        if not await tele_client.is_user_authorized():
            try:
                await tele_client.start(password=USERPASS)
            except PasswordHashInvalidError:
                return True, f"⚠️ Wrong 2FA password for {account_num}"
            except Exception as e:
                return True, f"⚠️ 2FA login failed for {account_num}: {e}"

        # now authorized, test send
        try:
            await tele_client.send_message("me", "✅ Session check OK")
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except RPCError as e:
            await bot.send_message(ADMINS, f"🚫 Account {account_num} frozen: {e}")
            return True, f"🚫 Frozen account"

        return False, "✅ Valid session (working, authorized)"

    except Exception as e:
        await bot.send_message(ADMINS, f"⚠️ Error checking {account_num}: {e}")
        return True, f"❌ Error: {e}"

    finally:
        if 'tele_client' in locals() and tele_client.is_connected():
            await tele_client.disconnect()


async def check_valid_session(doc):
    tele_client = None
    try:
        if doc.get("session_string"):
            tele_client = TelegramClient(StringSession(doc["session_string"]), API_ID, API_HASH)
        elif doc.get("tdata"):
            with tempfile.TemporaryDirectory() as tempdir:
                tdata_bytes = doc['tdata']
                zip_path = os.path.join(tempdir, "tdata.zip")
                with open(zip_path, "wb") as f: f.write(tdata_bytes)
                extract_path = os.path.join(tempdir, "tdata")
                with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(extract_path)
                
                tdesk = TDesktop(extract_path)
                if not tdesk.isLoaded(): return None, "Corrupted TData"
                
                # --- FIX FOR 2FA in check_valid_session ---
                # Added password=USERPASS here as well
                try:
                    tele_client = await tdesk.ToTelethon(session=None, flag=UseCurrentSession, password=USERPASS)
                except (NoPasswordProvided, PasswordHashInvalidError):
                    # If 2FA is on and password is wrong, we can't validate
                    return None, "2FA Enabled/Wrong Password"
                # --- END FIX ---
        else:
            return None, "No session data found"

        await tele_client.connect()
        if await tele_client.is_user_authorized():
            return tele_client, "OK"
        else:
            await tele_client.disconnect()
            return None, "Not Authorized"
            
    except Exception as e:
        if tele_client and tele_client.is_connected(): await tele_client.disconnect()
        return None, str(e)
