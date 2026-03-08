import os
import asyncio
import threading
from flask import Flask
import firebase_admin
from firebase_admin import credentials, db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

app = Flask(__name__)

# ---------------- WEB SERVER ----------------
@app.route('/')
def home():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "index.html not found"

@app.route('/ads')
def ads():
    try:
        with open("ads.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "ads.html not found"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

CHANNEL_USERNAME = "@viralmoviehubbd"

APP_URL = os.environ.get("APP_URL")  # Render URL

FIREBASE_DB_URL = "https://viralmoviehubbd-default-rtdb.firebaseio.com/"

ADS_URL = "/ads"

TASK_LINKS = {
    "task1": "https://singingfiles.com/show.php?l=0&u=2499908&id=54747",
    "task2": "https://singingfiles.com/show.php?l=0&u=2499908&id=36521",
    "task3": "https://singingfiles.com/show.php?l=0&u=2499908&id=54746"
}

# ---------------- FIREBASE ----------------
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': FIREBASE_DB_URL
    })

user_ref = db.reference('users')
movie_ref = db.reference('movies')

# ---------------- HELPER ----------------
async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def progress_bar(count, total=5):
    filled = "█" * min(count, total)
    empty = "░" * max(0, total - count)
    return f"[{filled}{empty}] {int((min(count,total)/total)*100)}%"

# ---------------- ADMIN ----------------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    users = user_ref.get()
    total = len(users) if users else 0

    await update.message.reply_text(
        f"📊 Total Users: {total}",
        parse_mode=ParseMode.HTML
    )

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.effective_user.id)

    if not user_ref.child(user_id).get():

        ref_by = context.args[0] if context.args else None

        user_ref.child(user_id).set({
            "referrals":0,
            "coins":0,
            "completed_tasks":[],
            "ref_by":ref_by
        })

        if ref_by and ref_by != user_id:

            r = user_ref.child(ref_by).get() or {"referrals":0,"coins":0}

            user_ref.child(ref_by).update({
                "referrals": r["referrals"] + 1,
                "coins": r["coins"] + 100
            })

    await show_menu(update, context)

# ---------------- MENU ----------------
async def show_menu(update, context):

    user_id = str(update.effective_user.id)

    if not await is_subscribed(context.bot, user_id):

        kb = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ Joined", callback_data="check")]
        ]

        msg = "❌ আগে চ্যানেলে জয়েন করুন"

    else:

        kb = [
            [InlineKeyboardButton("🎬 Open Movie App", callback_data="open_app")],
            [InlineKeyboardButton("🎁 Offers", callback_data="tasks")],
            [InlineKeyboardButton("🚀 Referral", callback_data="ref")],
            [InlineKeyboardButton("💰 Wallet", callback_data="wallet")]
        ]

        msg = "🎬 Viral Movie Hub"

    target = update.callback_query.message if update.callback_query else update.message

    await target.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

# ---------------- BUTTON ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)

    user = user_ref.child(user_id).get() or {}

    if query.data == "open_app":

        refs = user.get("referrals",0)

        if refs < 5:

            bot = await context.bot.get_me()

            ref_link = f"https://t.me/{bot.username}?start={user_id}"

            msg = f"🔒 Unlock করতে ৫ referral লাগবে\n\n{progress_bar(refs)}\n\n{ref_link}"

            await query.edit_message_text(msg)

        else:

            kb = [
                [InlineKeyboardButton("📺 Watch Ad", url=ADS_URL)],
                [InlineKeyboardButton("🎬 Open App", web_app={"url": APP_URL})]
            ]

            await query.edit_message_text(
                "Ad দেখে App খুলুন",
                reply_markup=InlineKeyboardMarkup(kb)
            )

# ---------------- RUN ----------------
async def main():

    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("stats", stats))
    app_bot.add_handler(CallbackQueryHandler(button_handler))

    print("Bot running...")

    await app_bot.run_polling()

# ---------------- MAIN ----------------
if __name__ == "__main__":

    threading.Thread(target=run_flask).start()

    asyncio.run(main())
