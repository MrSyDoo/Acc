from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from plugins.session import generate_session
from plugins.utils import start_clone_bot, user_client
from plugins.command import db

@Client.on_message(filters.private & filters.command('addacc') & filters.user(Config.ADMIN))
async def add_userbot(bot: Client, message: Message):
    """Add a user bot (Pyrogram session)"""
    try:
        # Check if userbot already exists
        bot_exist = await db.is_user_bot_exist(message.from_user.id)
        if bot_exist:
            return await message.reply_text(
                '**⚠️ User Bot Already Exists**',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton('User Bot', callback_data='userbot')
                ]])
            )
    except Exception:
        pass

    user_id = message.from_user.id

    # Request session string
    session = await generate_session(bot, message)
    try:
        # Start user bot
        user_account = await start_clone_bot(user_client(session))
    except Exception as e:
        await message.reply_text(f"**⚠️ USER BOT ERROR:** `{e}`")
        return

    user = user_account.me

    # Save user bot details
    details = {
        'id': user.id,
        'is_bot': False,
        'user_id': user_id,
        'name': user.first_name,
        'session': session,
        'username': user.username,
        'auto_listen_message': False
    }
    await db.add_user_bot(details)

    await message.reply_text(
        "**✅ User Bot Added Successfully**",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton('❮ Back', callback_data='userbot')
        ]])
    )


@Client.on_callback_query(filters.regex('^userbot$|^rmuserbot$|^close$'))
async def userbot_callback(client: Client, callback_query: CallbackQuery):
    """Handle userbot callback queries."""
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data == "userbot":
        userBot = await db.get_user_bot(user_id)
        text = f"Name: {userBot['name']}\nUserName: @{userBot['username']}\nUserId: `{userBot['user_id']}`"
        await callback_query.message.edit(
            text=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Remove", callback_data="rmuserbot")],
                [InlineKeyboardButton("✘ Close", callback_data="close")]
            ])
        )

    elif data == "rmuserbot":
        try:
            await db.remove_user_bot(user_id)
            await callback_query.message.edit("✅ **User Bot Removed Successfully!**", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✘ Close", callback_data="close")]
            ]))
        except:
            await callback_query.answer("You've already removed your userbot.", show_alert=True)

    elif data == "close":
        try:
            await callback_query.message.delete()
            await callback_query.message.reply_to_message.delete()
        except:
            pass
        await callback_query.message.continue_propagation()