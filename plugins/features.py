# =====================================================================================
# This is the final, complete features.py file.
# It contains all new commands and fixes, with the trial account feature removed.
# =====================================================================================

import re
import os
import json
import base64
import shutil
import tempfile
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyromod.exceptions import ListenerTimeout
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# Import necessary items from your original command.py
from .command import db, ADMINS, check_valid_session, get_account_age, get_country_from_phone, check_2fa
from config import Config

# Helper function to create paginated keyboards
def paginate_buttons(buttons, page, callback_prefix):
    items_per_page = 10
    rows = [[btn] for btn in buttons]
    pages = [rows[i:i + items_per_page] for i in range(0, len(rows), items_per_page)]
    
    keyboard = pages[page] if page < len(pages) else []
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"{callback_prefix}_{page-1}"))
    if page < len(pages) - 1:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"{callback_prefix}_{page+1}"))
        
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    return keyboard

# =====================================================================================
# NEW UTILITY & BALANCE COMMANDS
# =====================================================================================

@Client.on_message(filters.command("check_age") & filters.user(ADMINS))
async def check_age_command(client, message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply("Usage: `/check_age <account_id>`", parse_mode=ParseMode.MARKDOWN)
    
    acc_num = int(message.command[1])
    doc = await db.find_account_by_num(acc_num)
    if not doc:
        return await message.reply(f"❌ Account #{acc_num} not found.")

    status_msg = await message.reply(f"⏳ Checking age for account `#{acc_num}`...")
    tele_client = None
    try:
        tele_client, status = await check_valid_session(doc)
        if not tele_client:
            return await status_msg.edit(f"Could not start session for `#{acc_num}`: {status}")

        age = await get_account_age(tele_client)
        
        await db.reset_field(doc["_id"], "age", age)
        
        await status_msg.edit(f"✅ Account `#{acc_num}` Age: **{age}**\n\n(Database has been updated).")
    
    except Exception as e:
        await status_msg.edit(f"An error occurred: {e}")
    finally:
        if tele_client and tele_client.is_connected():
            await tele_client.disconnect()

@Client.on_message(filters.command("stats"))
async def stats_command(client, message):
    user_id = message.from_user.id
    balance = await db.get_balance(user_id)
    owned_accounts = await db.get_user_account_info(user_id)
    
    text = f"📊 **Your Stats**\n\n"
    text += f"**Balance:** `${balance:.2f}`\n\n"
    
    if owned_accounts:
        text += "**Owned Accounts:**\n"
        for acc in owned_accounts:
            text += f"• ID: `{acc['account_num']}` - {acc.get('name', '?')} ({acc.get('phone', '?')})\n"
    else:
        text += "**Owned Accounts:** None"
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Tᴏᴩ-Uᴩ", callback_data="topup")]
    ])

    await message.reply(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    
@Client.on_message(filters.command("pay") & filters.user(ADMINS))
async def pay_command(client, message):
    try:
        parts = message.command
        if len(parts) != 3:
            return await message.reply("Usage: `/pay <user_id> <amount>`", parse_mode=ParseMode.MARKDOWN)
        
        user_id = int(parts[1])
        amount_str = parts[2].replace('$', '')
        amount = float(amount_str)
        
        await db.update_balance(user_id, amount)
        new_balance = await db.get_balance(user_id)
        
        await message.reply(f"✅ Success! Gave `${amount:.2f}` to user `{user_id}`.\nTheir new balance is `${new_balance:.2f}`.", parse_mode=ParseMode.MARKDOWN)
        
        try:
            await client.send_message(user_id, f"💰 An admin has credited your account with **${amount:.2f}**!\nYour new balance is `${new_balance:.2f}`.", parse_mode=ParseMode.MARKDOWN)
        except:
            await message.reply("⚠️ Could not notify the user (they may have blocked the bot).")

    except (ValueError, IndexError):
        await message.reply("Usage: `/pay <user_id> <amount>`\nExample: `/pay 123456 10.50`", parse_mode=ParseMode.MARKDOWN)

# =====================================================================================
# NEW ACQUISITION & REPORTING COMMANDS
# =====================================================================================

from pyrogram import Client, filters
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    AuthKeyUnregisteredError,
)


@Client.on_message(filters.command("addacc") & filters.user(ADMINS))
async def add_account_interactive(client, message):
    tele_client = None
    try:
        # Ask for session string
        ask_sess = await message.reply(
            "Please send the **Telethon session string** for the account.",
            parse_mode=ParseMode.MARKDOWN
        )
        sess_msg = await client.listen(message.chat.id, timeout=300)
        session_str = sess_msg.text.strip()
        await ask_sess.delete()

        status_msg = await message.reply("⏳ Connecting to the account...", parse_mode=ParseMode.MARKDOWN)

        # Try connecting
        tele_client = TelegramClient(StringSession(session_str), 6, "eb06d4abfb49dc3eeb1aeb98ae0f581e")  # Default values for checking
        try:
            await tele_client.connect()
        except Exception as e:
            await status_msg.edit(f"❌ Failed to connect: `{e}`", parse_mode=ParseMode.MARKDOWN)
            return

        # Validate session
        try:
            me = await tele_client.get_me()
        except AuthKeyUnregisteredError:
            await status_msg.edit("❌ Invalid session string. It seems expired or incorrect.")
            return

        # Gather info
        phone = me.phone or "Unknown"
        info = {
            "_id": me.id,
            "account_num": await db.get_next_account_num(),
            "name": me.first_name or me.username or "N/A",
            "phone": phone,
            "country": get_country_from_phone(f"+{phone}) if phone != "Unknown" else "Unknown",
            "age": await get_account_age(tele_client),
            "twofa": await check_2fa(tele_client),
            "session_string": session_str,
            "by": f"{message.from_user.first_name}({message.from_user.id})"
        }

        acc_num = await db.save_account(me.id, info)
        await status_msg.edit(
            f"✅ Account `#{acc_num}` (`{info['name']}`) added successfully!",
            parse_mode=ParseMode.MARKDOWN
        )

    except ListenerTimeout:
        await message.reply("⏰ Timeout. Process cancelled.")
    except Exception as e:
        await message.reply(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)
    finally:
        if tele_client and tele_client.is_connected():
            await tele_client.disconnect()

@Client.on_message(filters.command("show") & filters.user(ADMINS))
async def show_report_command(client, message):
    status_msg = await message.reply("⏳ Generating report...")
    report_lines = ["--- Users, Balances, and Owned Accounts ---"]
    all_users = await db.users.find({}).to_list(length=None)
    for user in all_users:
        user_id = user['_id']
        try:
            tg_user = await client.get_users(user_id)
            name = tg_user.first_name or "Unknown"
            if tg_user.last_name:
                name += f" {tg_user.last_name}"
        except Exception:
            name = "Unknown"
        balance = await db.get_balance(user_id)
        owned_doc = await db.syd.find_one({"_id": user_id})
        owned_ids = owned_doc.get("accounts", []) if owned_doc else []
        report_lines.append(f"User: {user_id} ({name}) | Balance: ${balance:.2f} | Owns: {owned_ids or 'None'}")

    report_lines.append("\n--- Unassigned Accounts in Database ---")
    all_accounts = await db.col.find({}).to_list(length=None)
    all_owned_ids = set()
    async for doc in db.syd.find({}, {"accounts": 1}):
        all_owned_ids.update(doc.get("accounts", []))

    for acc in all_accounts:
        if 'account_num' in acc and acc['account_num'] not in all_owned_ids:
            report_lines.append(f"ID: {acc['account_num']} | Name: {acc['name']} | Phone: {acc['phone']}")

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tmp:
        tmp.write("\n".join(report_lines))
        tmp_path = tmp.name
        
    await message.reply_document(tmp_path, caption=f"📊 Bot Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    await status_msg.delete()
    os.remove(tmp_path)

@Client.on_message(filters.command("backup_db") & filters.user(ADMINS))
async def backup_db_command(client, message):
    status_msg = await message.reply("⏳ Creating database backup...")
    collections = {"accounts": db.col, "ownership": db.syd, "bot_users": db.users, "balances": db.balances, "stock": db.stock, "sections": db.sections}
    backup_data = {}
    for name, col in collections.items():
        backup_data[name] = [doc async for doc in col.find({})]
    
    def serializer(o): return str(o)
    backup_json = json.dumps(backup_data, indent=2, default=serializer)
    
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
        tmp.write(backup_json)
        tmp_path = tmp.name

    await message.reply_document(tmp_path, caption=f"📦 Database Backup - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    await status_msg.delete()
    os.remove(tmp_path)

# =====================================================================================
# USER-FACING STOCK COMMANDS
# =====================================================================================





active_stock_messages = {}

@Client.on_message(filters.command("stock"))
async def stock_command(client, message):
    user_id = message.from_user.id

    if user_id in active_stock_messages:
        try: await active_stock_messages[user_id]["msg"].delete()
        except: pass
        del active_stock_messages[user_id]

    sections = await db.get_stock_sections()
    if not sections:
        return await message.reply("😔 Sorry, there are no stock sections created yet.")

    buttons = [
        InlineKeyboardButton(f"{s} ({await db.count_stock_in_section(s)} IDs)", callback_data=f"view_stock_0_{s}")
        for s in sections
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    stock_msg = await message.reply("**🛒 Account Stock**\n\nPlease choose a category:", reply_markup=InlineKeyboardMarkup(keyboard))
    active_stock_messages[user_id] = {"msg": stock_msg, "task": None}

    async def auto_delete():
        await asyncio.sleep(300)
        if user_id in active_stock_messages and active_stock_messages[user_id]["msg"].id == stock_msg.id:
            try: await stock_msg.delete()
            except: pass
            active_stock_messages.pop(user_id, None)

    active_stock_messages[user_id]["task"] = asyncio.create_task(auto_delete())



@Client.on_callback_query(filters.regex(r"^view_stock_(\d+)_(.+)"))
async def view_stock_section_cb(client, cb):
    
    uid, mid = cb.from_user.id, cb.message.id
    if uid not in active_stock_messages or active_stock_messages[uid]["msg"].id != mid:
        return await cb.answer("Old Message, Start New One!.", show_alert=True)
    try:
        await cb.answer() 
    except:
        pass # Ignore errors if we can't answer the query (e.g., already answered)

    try:
        # Extract data from callback query
        page = int(cb.matches[0].group(1))
        section = cb.matches[0].group(2)
        
        # 1. Fetch items in the specific section
        items = [item async for item in await db.get_stock_in_section(section)]
        
        if not items:
            await cb.message.edit("This section is currently empty.")
            return
            
        # 2. Compile full item details
        full_items = []
        for item in items:
            acc_doc = await db.find_account_by_num(item['account_num'])
            if acc_doc:
                full_items.append({
                    "price": item.get('price', "Don't Selling"), 
                    "acc_num": acc_doc['account_num'], 
                    "country": acc_doc.get('country', 'N/A'), 
                    "age": acc_doc.get('age', 'Unknown')
                })
        
        # If all accounts are missing from the main DB, handle it
        if not full_items:
            await cb.message.edit(f"**Available in `{section}`**: ⚠️ No valid accounts found for the stock items.", 
                                  parse_mode=ParseMode.MARKDOWN)
            return

        # 3. Sort and create buttons
        full_items.sort(key=lambda x: x['price'])
        
        buttons = [InlineKeyboardButton(
            f"${i['price']:.2f} - {i['country']} Account - {i['age']}", 
            callback_data=f"confirm_buy_{i['acc_num']}"
        ) for i in full_items]
        
        kbd_rows = paginate_buttons(buttons, page, f"view_stock_{section}")
        
        # 4. Add the 'Back' button
        kbd_rows.append([InlineKeyboardButton("◀️ Back to Categories", callback_data="back_to_stock_main")])
        
        
        await cb.message.edit(
            f"**Available in `{section}`** ({len(full_items)} total):", 
            reply_markup=InlineKeyboardMarkup(kbd_rows), 
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        # Use cb.message.reply to send the error
        await cb.message.reply(
            f"❌ **An unexpected error occurred while loading stock.**\n\n"
            f"Error details: `{e}`", 
            quote=True, # Reply to the original message for context
            parse_mode=ParseMode.MARKDOWN
        )


@Client.on_callback_query(filters.regex(r"^confirm_buy_(\d+)"))
async def confirm_buy_cb(client, cb):
    uid, mid = cb.from_user.id, cb.message.id
    if uid not in active_stock_messages or active_stock_messages[uid]["msg"].id != mid:
        return await cb.answer("Old Message, Start New One..!", show_alert=True)
    
    acc_num = int(cb.matches[0].group(1))
    user_id = cb.from_user.id
    stock_item = await db.get_stock_item_by_acc_num(acc_num)
    if not stock_item:
        await cb.answer("❌ This account is no longer available.", show_alert=True)
        return await back_to_stock_main_cb(client, cb)
    user_balance, price = await db.get_balance(user_id), stock_item['price']
    if user_balance < price:
        return await cb.answer(f"⚠️ Insufficient balance! Your: ${user_balance:.2f}, Required: ${price:.2f}", show_alert=True)
    
    text = (f"**Confirm Purchase**\n\nBuy account `#{acc_num}` for **${price:.2f}**?\n\n"
            f"Your balance: `${user_balance:.2f}`\nAfter purchase: `${user_balance - price:.2f}`")
    keyboard = [[InlineKeyboardButton("✅ Proceed", callback_data=f"proceed_buy_{acc_num}"), InlineKeyboardButton("◀️ Go Back", callback_data="back_to_stock_main")]]
    await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

@Client.on_callback_query(filters.regex(r"^proceed_buy_(\d+)"))
async def proceed_buy_cb(client, cb):
    uid, mid = cb.from_user.id, cb.message.id
    if uid not in active_stock_messages or active_stock_messages[uid]["msg"].id != mid:
        return await cb.answer("Old Message, Start New One..!", show_alert=True)
    
    acc_num = int(cb.matches[0].group(1))
    user_id = cb.from_user.id
    if not await db.lock_user(user_id):
        return await cb.answer("⏳ Your previous transaction is processing.", show_alert=True)

    try:
        stock_item = await db.get_stock_item_by_acc_num(acc_num)
        if not stock_item: return await cb.message.edit("❌ Sorry, this account was just sold.")
        
        price, user_balance = stock_item['price'], await db.get_balance(user_id)
        if user_balance < price: return await cb.message.edit("❌ Your balance is no longer sufficient.")
        
        doc = await db.col.find_one({"account_num": acc_num})
        if not doc:
            return await callback_query.message.edit("❌ Account not found.")
            
        session, valid = await check_valid_session(
            doc
        )
        if not session: 
            await callback_query.answer("This account is invalid, sorry for the inconvenience, please purchase a different account, this one will be removed from stocks.", show_alert=True)
            syd = await db.remove_stock_item(acc_num)
            if syd:
                ext = "and removed from stocks"
            else:
                ext = "and tried to remove from stock but failed"
            for admin in ADMINS:
                await client.send_message(admin, f"The account: ID {acc_num} \nUser ID: {user_id} \nNumber: {doc['phone']} \nIs invalid {ext}", parse_mode=ParseMode.MARKDOWN)
            return
        await db.update_balance(user_id, -price)
        success, msg = await db.grant_account(user_id, acc_num)
        
        if not success:
            await db.update_balance(user_id, price) # Refund
            return await cb.message.edit(f"❌ Critical error. You have been refunded. Error: {msg}")

        await cb.message.edit(f"✅ **Purchase Successful!**\nYou now own account `#{acc_num}`.\nUse `/retrieve {acc_num}` to access it.", parse_mode=ParseMode.MARKDOWN)
        new_balance = await db.get_balance(user_id)
        for admin in ADMINS:
            await client.send_message(admin, f"🚨 <b>New Sale!</b> 🚨\nUser: {cb.from_user.mention} (<code>{user_id}</code>)\nAccount: <code>#{acc_num}</code>\nPrice: <code>${price:.2f}</code>\nUser's New Balance: <code>${new_balance:.2f}</code>", parse_mode=ParseMode.HTML)
    finally:
        await db.unlock_user(user_id)

@Client.on_callback_query(filters.regex(r"^back_to_stock_main"))
async def back_to_stock_main_cb(client, cb):
    uid, mid = cb.from_user.id, cb.message.id
    if uid not in active_stock_messages or active_stock_messages[uid]["msg"].id != mid:
        return await cb.answer("Old Message, Start New One..!", show_alert=True)
    
    await cb.answer()
    sections = await db.get_stock_sections()
    if not sections:
        return await cb.message.edit("😔 Sorry, there are no stock sections created yet.")

    buttons = [
        InlineKeyboardButton(f"{s} ({await db.count_stock_in_section(s)} IDs)", callback_data=f"view_stock_0_{s}")
        for s in sections
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    stock_msg = await cb.message.edit("**🛒 Account Stock**\n\nPlease choose a category:", reply_markup=InlineKeyboardMarkup(keyboard))
    


# =====================================================================================
# ADMIN STOCK MANAGEMENT
# =====================================================================================
    
@Client.on_message(filters.command("managestock") & filters.user(ADMINS))
async def manage_stock_command(client, message):
    kbd = [[InlineKeyboardButton("➕ Add New Section", callback_data="stockadmin_add_sec"), InlineKeyboardButton("🗑️ Remove a Section", callback_data="stockadmin_rem_sec")],
           [InlineKeyboardButton("✏️ Rename a Section", callback_data="stockadmin_ren_sec")]]
    await message.reply("**🛠️ Stock Management**", reply_markup=InlineKeyboardMarkup(kbd))

@Client.on_message(filters.command("add") & filters.user(ADMINS))
async def add_to_stock_command(client, message):
    try:
        parts = message.command
        if len(parts) < 3: 
            return await message.reply("Usage: `/add <price> <ID1> <ID2>...`", parse_mode=ParseMode.MARKDOWN)
        
        price = float(parts[1])
        acc_nums = []
        
        for p in parts[2:]:
            if "-" in p:
                start, end = map(int, p.split("-", 1))
                acc_nums.extend(range(start, end + 1))
            else:
                acc_nums.append(int(p))

        
        acc_nums = list(set(acc_nums))
        
        valid_accs, invalid_accs = await db.validate_accounts_for_stock(acc_nums)
        if invalid_accs: await message.reply(f"⚠️ Cannot add: `{', '.join(map(str, invalid_accs))}` (non-existent or owned).", parse_mode=ParseMode.MARKDOWN)
        if not valid_accs: return await message.reply("❌ No valid accounts to add.")
        for acc in valid_accs:
            await db.col.update_one({"account_num": acc}, {"$set": {"price": price}}, upsert=True)

        sections = await db.get_stock_sections()
        buttons = [[InlineKeyboardButton(s, callback_data=f"add_to_sec_{s}")] for s in sections]
        buttons.append([InlineKeyboardButton("➕ Create New Section", callback_data="add_to_sec_new")])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="stockadmin_cancel")])

        client.pending_stock_add = {"price": price, "accounts": valid_accs}
        await message.reply(f"Adding `{', '.join(map(str, valid_accs))}` for `${price:.2f}`.\nSelect a section:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await message.reply("Usage: `/add <price> <ID1> <ID2>...`", parse_mode=ParseMode.MARKDOWN)

@Client.on_callback_query(filters.regex(r"^add_to_sec_") & filters.user(ADMINS))
async def add_to_section_cb(client, cb):
    action = cb.data.split("_")[-1]
    pending = getattr(client, 'pending_stock_add', None)
    if not pending: return await cb.message.edit("❌ Error: Timed out. Start `/add` again.")

    price, accounts = pending['price'], pending['accounts']
    section_name = ""
    if action == "new":
        try:
            ask = await cb.message.edit("Send the name for the new section.")
            resp = await client.listen(cb.from_user.id, timeout=300)
            section_name = resp.text.strip()
            await db.add_section(section_name)
        except ListenerTimeout: return await cb.message.edit("⏰ Timeout.")
    else:
        section_name = cb.data.replace("add_to_sec_", "")
    
    added, skipped = 0, 0
    for acc in accounts:
        if await db.add_stock_item(price, acc, section_name): added += 1
        else: skipped += 1
            
    text = f"✅ Added **{added}** accounts to `{section_name}` for `${price:.2f}`."
    if skipped: text += f"\nSkipped **{skipped}** (already in section)."
    await cb.message.edit(text, parse_mode=ParseMode.MARKDOWN)
    client.pending_stock_add = None


@Client.on_callback_query(filters.regex(r"^topup"))
async def handle_guide_cb(client, cb):
   
    text = (
        "💰 **Top-up Guide**\n\n"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴩᴀʏ", url="t.me/vizean")]
    ])

    await cb.message.edit_text(text, reply_markup=keyboard)
    await cb.answer()
    
@Client.on_callback_query(filters.regex(r"^stockadmin_") & filters.user(ADMINS))
async def stock_admin_handler(client, cb):
    action = cb.data.split("_", 1)[1]
    
    if action == "add_sec":
        try:
            ask = await cb.message.edit("Please send the name for the new section.")
            resp = await client.listen(cb.from_user.id, timeout=300)
            if await db.add_section(resp.text.strip()):
                await cb.message.edit(f"✅ Section `{resp.text.strip()}` created.", parse_mode=ParseMode.MARKDOWN)
            else:
                await cb.message.edit(f"⚠️ Section `{resp.text.strip()}` already exists.", parse_mode=ParseMode.MARKDOWN)
        except ListenerTimeout: await cb.message.edit("⏰ Timeout.")
    
    elif action == "rem_sec":
        sections = await db.get_stock_sections()
        if not sections: return await cb.answer("No sections to remove.", show_alert=True)
        btns = [[InlineKeyboardButton(s, callback_data=f"stockadmin_del_{s}")] for s in sections]
        btns.append([InlineKeyboardButton("◀️ Back", callback_data="stockadmin_back")])
        await cb.message.edit("🗑️ Select a section to remove:", reply_markup=InlineKeyboardMarkup(btns))

    elif action.startswith("del_"):
        section = action.replace("del_", "")
        await db.remove_section(section)
        await cb.message.edit(f"✅ Section `{section}` and its stock items have been deleted.", parse_mode=ParseMode.MARKDOWN)

    elif action == "ren_sec":
        sections = await db.get_stock_sections()
        if not sections: return await cb.answer("No sections to rename.", show_alert=True)
        btns = [[InlineKeyboardButton(s, callback_data=f"stockadmin_ren_start_{s}")] for s in sections]
        btns.append([InlineKeyboardButton("◀️ Back", callback_data="stockadmin_back")])
        await cb.message.edit("✏️ Select a section to rename:", reply_markup=InlineKeyboardMarkup(btns))

    elif action.startswith("ren_start_"):
        old_name = action.replace("ren_start_", "")
        try:
            ask = await cb.message.edit(f"Renaming `{old_name}`. Send the new name.", parse_mode=ParseMode.MARKDOWN)
            resp = await client.listen(cb.from_user.id, timeout=300)
            await db.rename_section(old_name, resp.text.strip())
            await cb.message.edit(f"✅ Renamed to `{resp.text.strip()}`.", parse_mode=ParseMode.MARKDOWN)
        except ListenerTimeout: await cb.message.edit("⏰ Timeout.")

    elif action == "back":
        await manage_stock_command(client, cb.message)
    
    elif action == "cancel":
        await cb.message.delete()




    from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.command("fetch") & filters.user(ADMINS))
async def fetch_account(client, message):
    parts = message.command
    if len(parts) < 2:
        return await message.reply("Usage: `/fetch <account_id>`", parse_mode=ParseMode.MARKDOWN)

    try:
        acc_num = int(parts[1])
    except ValueError:
        return await message.reply("❌ Invalid account ID.")

    # Find who owns this account
    owned = await db.syd.find_one({"accounts": acc_num})
    if not owned:
        return await message.reply("❌ This account isn’t owned by anyone.")

    user_id = owned["_id"]
    user_name = owned.get("name", "Unknown")

    # Ask for confirmation
    text = (
        f"⚠️ Are you sure you want to take back account **{acc_num}** "
        f"from **{user_name}** (`{user_id}`)?"
    )
    buttons = [
        [
            InlineKeyboardButton("📦 Retrieve", callback_data=f"fetch_retrieve_{acc_num}_{user_id}"),
            InlineKeyboardButton("💸 Retrieve + Cashback", callback_data=f"fetch_cashback_{acc_num}_{user_id}")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="fetch_cancel")]
    ]
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)


@Client.on_callback_query(filters.regex(r"^fetch_"))
async def handle_fetch_cb(client, cb):
    data = cb.data.split("_")
    action = data[1]

    if action == "cancel":
        return await cb.message.edit_text("❌ Operation cancelled.")

    acc_num = int(data[2])
    user_id = int(data[3])

    owned = await db.syd.find_one({"_id": user_id, "accounts": acc_num})
    if not owned:
        return await cb.message.edit_text("❌ This user doesn’t own that account anymore.")

    await db.syd.update_one({"_id": user_id}, {"$pull": {"accounts": acc_num}})

    acc_doc = await db.col.find_one({"account_num": acc_num})
    if not acc_doc:
        return await cb.message.edit_text("⚠️ Account data not found in records.")

    if action == "cashback":
        price = acc_doc.get("price", 0)
        await db.update_balance(user_id, price)
        await cb.message.edit_text(
            f"Retrieved account `{acc_num}` from user `{user_id}` and refunded **${price:.2f}**. ✅",
            parse_mode=ParseMode.MARKDOWN
        )
        try:
            await client.send_message(
                user_id,
                f"💸 Your account **({acc_num})** has been retrieved by admin.\n"
                f"The amount you spent (**${price:.2f}**) has been credited back to your balance.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass
    else:
        await cb.message.edit_text(
            f"Retrieved account `{acc_num}` from user `{user_id}`. ✅",
            parse_mode="markdown"
        )
