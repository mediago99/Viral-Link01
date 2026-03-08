import os
import json
import asyncio
import threading
from flask import Flask
import firebase_admin
from firebase_admin import credentials, db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from flask import Flask, send_from_directory

app = Flask(__name__)

# ---------------- WEB SERVER ----------------
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
CHANNEL_USERNAME = "@viralmoviehubbd"
APP_URL = os.environ.get("APP_URL")

FIREBASE_DB_URL = "https://viralmoviehubbd-default-rtdb.firebaseio.com/"
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS")

# ---------------- FIREBASE ----------------
if not firebase_admin._apps:
    cred_dict = json.loads(FIREBASE_CREDS)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': FIREBASE_DB_URL
    })

user_ref = db.reference("users")

# ---------------- HELPERS ----------------
async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def progress_bar(count, total=5):
    filled = "█" * min(count, total)
    empty = "░" * max(0, total - count)
    percent = int((min(count, total) / total) * 100)
    return f"[{filled}{empty}] {percent}%"

# ---------------- START COMMAND ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.effective_user.id)

    if not user_ref.child(user_id).get():

        ref_by = context.args[0] if context.args else None

        user_ref.child(user_id).set({
            "referrals": 0,
            "coins": 0,
            "ref_by": ref_by
        })

        if ref_by and ref_by != user_id:

            r = user_ref.child(ref_by).get() or {"referrals":0,"coins":0}

            user_ref.child(ref_by).update({
                "referrals": r.get("referrals",0)+1,
                "coins": r.get("coins",0)+100
            })

    is_joined = await is_subscribed(context.bot, user_id)

    if not is_joined:

        kb = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ Joined", callback_data="check_join")]
        ]

        await update.message.reply_text(
            "❌ আগে চ্যানেলে জয়েন করুন",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    else:

        kb = [
            [InlineKeyboardButton("🎬 Open Movie App", callback_data="open_app")]
        ]

        await update.message.reply_text(
            "🎬 Viral Movie Hub এ স্বাগতম",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ---------------- BUTTON HANDLER ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)

    if query.data == "check_join":

        is_joined = await is_subscribed(context.bot, user_id)

        if is_joined:

            kb = [[InlineKeyboardButton("🎬 Open App", callback_data="open_app")]]

            await query.edit_message_text(
                "✅ ধন্যবাদ জয়েন করার জন্য!",
                reply_markup=InlineKeyboardMarkup(kb)
            )

        else:

            await query.answer(
                "❌ এখনো জয়েন করেননি!",
                show_alert=True
            )

    elif query.data == "open_app":

        user = user_ref.child(user_id).get() or {}

        refs = user.get("referrals", 0)

        if refs < 5:

            bot_me = await context.bot.get_me()

            await query.edit_message_text(
                f"🔒 ৫ রেফারেল লাগবে\n\n"
                f"{progress_bar(refs)}\n\n"
                f"Invite Link:\n"
                f"`https://t.me/{bot_me.username}?start={user_id}`",
                parse_mode=ParseMode.MARKDOWN
            )

        else:

            kb = [[
                InlineKeyboardButton(
                    "🎬 Open WebApp",
                    web_app=WebAppInfo(url=APP_URL)
                )
            ]]

            await query.edit_message_text(
                "✅ App Unlock হয়েছে!",
                reply_markup=InlineKeyboardMarkup(kb)
            )

# ---------------- MAIN ----------------
async def main():
    # Flask আলাদা thread এ চালানো
    threading.Thread(target=run_flask, daemon=True).start()

    # Telegram Bot তৈরি
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("Bot Started Successfully!")

    # Polling চালানো
    application.run_polling()

# ---------------- RUN ----------------
if __name__ == "__main__":
    # asyncio.run(main()) ব্যবহার করা হবে না
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
