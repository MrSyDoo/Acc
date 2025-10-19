
from config import Config, Txt
import random, asyncio, time
import pytz
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from .command import db, ADMINS
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid



class temp(object):
    ME = None
    U_NAME = None
    B_NAME = None
    
@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    used = message.from_user
    button = InlineKeyboardMarkup([[
        InlineKeyboardButton('Gᴜɪᴅᴇ', callback_data='guide'),
        InlineKeyboardButton('Vᴇʀɪꜰʏ', url="t.me/vizean")
    ]])

    
    await db.add_user(used.id)

    if Config.PICS:
        await message.reply_photo(
            random.choice(Config.PICS),
            caption=Txt.START_TXT.format(used.mention),
            reply_markup=button,
            parse_mode=enums.ParseMode.HTML
        )
    else:
        await message.reply_text(
            text=Txt.START_TXT.format(used.mention),
            reply_markup=button,
            disable_web_page_preview=True
        )




@Client.on_message(filters.command("give") & filters.user(Config.ADMIN))  
# ^ put your own admin IDs here
async def give_account(client: Client, message: Message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            return await message.reply("⚠️ Usage: /give {user_id} {acc_num}")

        user_id = int(parts[1])
        acc_num = int(parts[2])

        success, msg = await db.grant_account(user_id, acc_num)
        await message.reply(msg)
        await client.send_message(user_id, f"ᴀᴅᴍɪɴ ɢᴀᴠᴇ ʏᴏᴜ ᴀɴ ᴀᴄᴄᴏᴜɴᴛ ᴡɪᴛʜ ɪᴅ : {acc_num}\nᴜꜱᴇ <code>/retrieve {acc_num}</code> ᴛᴏ ʟᴏɢɪɴ ᴛʜᴀᴛ ᴀᴄᴄᴏᴜɴᴛ 🎉.")

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("list") & filters.user(Config.ADMIN))  
# ^ put your admin IDs here
async def list_user_accounts_cmd(client: Client, message: Message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            return await message.reply("⚠️ Usage: /list {user_id}")

        user_id = int(parts[1])
        accounts = await db.get_user_account_info(user_id)

        if not accounts:
            return await message.reply(f"❌ No accounts found for user {user_id}")

        text_lines = [f"📑 Accounts for user `{user_id}`:\n"]
        for acc in accounts:
            text_lines.append(
                f"🔹 #{acc['account_num']} | "
                f"{acc.get('name', '?')} | "
                f"{acc.get('phone', '?')} | "
                f"{acc.get('twofa', '?')} | "
                f"Spam: {acc.get('spam', '?')}"
            )

        await message.reply("\n".join(text_lines))

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("myaccounts"))
async def my_accounts_cmd(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        accounts = await db.get_user_account_info(user_id)

        if not accounts:
            return await message.reply("⚠️ You don’t own any accounts yet. \nꜱᴇɴᴅ ᴛᴅᴀᴛᴀ ᴏꜰ ᴀᴄᴄᴏᴜɴᴛ ᴏʀ ʀᴇqᴜᴇꜱᴛ ᴏᴡɴᴇʀ.")

        text_lines = ["📑 Your accounts:\n"]
        for acc in accounts:
            text_lines.append(
                f"🔹 #{acc['account_num']} | "
                f"{acc.get('name', '?')} | "
                f"{acc.get('phone', '?')} | "
                f"{acc.get('twofa', '?')} | "
                f"Spam: {acc.get('spam', '?')}"
            )

        await message.reply("\n".join(text_lines))

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("verify") & filters.user(Config.ADMIN))
async def verify_user(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /verify {user_id}")
    try:
        uid = int(message.command[1])
        await db.add_verified(uid)
        await message.reply(f"✅ User `{uid}` verified.")
        await client.send_message(uid, "🎉 You have been verified by admin! You can now use the bot.")
    except Exception as e:
        await message.reply(f"Error: {e}")


@Client.on_message(filters.command("revoke") & filters.user(Config.ADMIN))
async def revoke_user(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /revoke {user_id}")
    uid = int(message.command[1])
    await db.revoke_verified(uid)
    await message.reply(f"❌ User `{uid}` revoked.")
    await client.send_message(uid, "⚠️ Your verification has been revoked by admin.")

    

@Client.on_message(filters.command("broadcast") & filters.user(Config.ADMIN) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    all_users = await db.get_all_users()
    broadcast_msg = m.reply_to_message
    sts_msg = await m.reply_text("Bʀᴏᴀᴅᴄᴀꜱᴛ Sᴛᴀʀᴛᴇᴅ..!")

    done = success = failed = 0
    start_time = time.time()
    total_users = await db.total_users_count()

    async for user in all_users:
        sts = await send_msg(user["_id"], broadcast_msg)
        if sts == 200:
            success += 1
        else:
            failed += 1
        if sts == 400:
            await db.delete_user(user["_id"])
        done += 1

        if not done % 20:
            await sts_msg.edit(
                f"📢 Bʀᴏᴀᴅᴄᴀꜱᴛ Iɴ Pʀᴏɢʀᴇꜱꜱ\n"
                f"Tᴏᴛᴀʟ: {total_users}\n"
                f"Cᴏᴍᴘʟᴇᴛᴇᴅ: {done}\n"
                f"Sᴜᴄᴄᴇꜱꜱ: {success}\n"
                f"Fᴀɪʟᴇᴅ: {failed}"
            )

    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts_msg.edit(
        f"✅ Bʀᴏᴀᴅᴄᴀꜱᴛ Cᴏᴍᴘʟᴇᴛᴇᴅ\n"
        f"Tɪᴍᴇ: `{completed_in}`\n\n"
        f"Tᴏᴛᴀʟ: {total_users}\n"
        f"Sᴜᴄᴄᴇꜱꜱ: {success}\n"
        f"Fᴀɪʟᴇᴅ: {failed}"
    )

@Client.on_callback_query(filters.regex("guide"))
async def guide_callback(client, callback_query):
    guide_text = (
        "📖 <b>Hᴏᴡ Tᴏ Uꜱᴇ Tʜᴇ Bᴏᴛ</b>\n\n"
        "Tʜɪꜱ ʙᴏᴛ ʜᴇʟᴘꜱ ᴍᴀɴᴀɢᴇ ᴀᴄᴄᴏᴜɴᴛꜱ ꜱᴀꜰᴇʟʏ.\n\n"
        
        "🔑 <b>Aᴅᴍɪɴ Cᴏᴍᴍᴀɴᴅꜱ</b>\n"
        "• <code>/verify {user_id}</code> – ✅ Vᴇʀɪꜰʏ ᴀ ᴜꜱᴇʀ ꜱᴏ ᴛʜᴇʏ ᴄᴀɴ ᴀᴄᴄᴇꜱꜱ ʙᴏᴛ ꜰᴇᴀᴛᴜʀᴇꜱ.\n"
        "• <code>/revoke {user_id}</code> – ⛔ Rᴇᴍᴏᴠᴇ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ꜰʀᴏᴍ ᴀ ᴜꜱᴇʀ.\n"
        "• <code>/list</code> – 📂 Lɪꜱᴛ ᴀʟʟ ᴜꜱᴇʀꜱ ᴀɴᴅ ᴛʜᴇɪʀ ᴀᴄᴄᴏᴜɴᴛꜱ.\n"
        "• <code>/give {user_id} {acc_num}</code> – 🎁 Aꜱꜱɪɢɴ ᴀɴ ᴀᴄᴄᴏᴜɴᴛ ɴᴜᴍʙᴇʀ ᴛᴏ ᴀ ᴜꜱᴇʀ.\n"
        "• <code>/clean_db</code> – 🧹 Cʟᴇᴀʀ ᴛʜᴇ ᴅᴀᴛᴀʙᴀꜱᴇ (ʙᴇ ᴄᴀʀᴇꜰᴜʟ!).\n"
        "• <code>/show_db</code> – 📋 Sʜᴏᴡ ᴀʟʟ ᴀᴄᴄᴏᴜɴᴛꜱ ꜱᴀᴠᴇᴅ ɪɴ DB.\n"
        "• <code>/retrieve {acc_num}</code> – 📥 Rᴇᴛʀɪᴇᴠᴇ ꜰᴜʟʟ ᴀᴄᴄᴏᴜɴᴛ ᴅᴀᴛᴀ.\n\n"
        
        "👤 <b>Uꜱᴇʀ Cᴏᴍᴍᴀɴᴅꜱ</b>\n"
        "• <code>/myaccounts</code> – 🗂 Sᴇᴇ ᴀʟʟ ᴀᴄᴄᴏᴜɴᴛꜱ ʏᴏᴜ ᴏᴡɴ.\n\n"
        
        "⚠️ Oɴʟʏ ᴠᴇʀɪꜰɪᴇᴅ ᴜꜱᴇʀꜱ ᴏʀ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴀᴄᴄᴇꜱꜱ ꜰᴇᴀᴛᴜʀᴇꜱ."
    )
    await callback_query.message.edit_text(
        guide_text,
        disable_web_page_preview=True
    )

async def send_msg(user_id, message):
    try:
        await message.forward(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return send_msg(user_id, message)
    except InputUserDeactivated:
        print(f"{user_id} : Dᴇᴀᴄᴛɪᴠᴀᴛᴇᴅ")
        return 400
    except UserIsBlocked:
        print(f"{user_id} : Bʟᴏᴄᴋᴇᴅ Tʜᴇ Bᴏᴛ")
        return 400
    except PeerIdInvalid:
        print(f"{user_id} : Uꜱᴇʀ Iᴅ Iɴᴠᴀʟɪᴅ")
        return 400
    except Exception as e:
        print(f"{user_id} : {e}")
        return 500


