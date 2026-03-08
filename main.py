import os
import json
import asyncio
import threading
from flask import Flask
import firebase_admin
from firebase_admin import credentials, db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

app = Flask(__name__)

# ---------------- WEB SERVER (Render Port Binding) ----------------
@app.route('/')
def home():
    return "Bot is Active and Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # debug=False এবং use_reloader=False রাখা জরুরি
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ---------------- CONFIG & FIREBASE ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
CHANNEL_USERNAME = "@viralmoviehubbd"
APP_URL = os.environ.get("APP_URL")
FIREBASE_DB_URL = "https://viralmoviehubbd-default-rtdb.firebaseio.com/"
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS")

if not firebase_admin._apps:
    try:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
    except Exception as e:
        print(f"Firebase Init Error: {e}")

user_ref = db.reference('users')

# ---------------- HELPERS ----------------
async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def progress_bar(count, total=5):
    filled = "█" * min(count, total)
    empty = "░" * max(0, total - count)
    return f"[{filled}{empty}] {int((min(count, total)/total)*100)}%"

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not user_ref.child(user_id).get():
        ref_by = context.args[0] if context.args else None
        user_ref.child(user_id).set({"referrals": 0, "coins": 0, "ref_by": ref_by})
        if ref_by and ref_by != user_id:
            r = user_ref.child(ref_by).get() or {"referrals": 0, "coins": 0}
            user_ref.child(ref_by).update({"referrals": r.get("referrals", 0) + 1, "coins": r.get("coins", 0) + 100})
    await show_menu(update, context)

async def show_menu(update, context):
    user_id = str(update.effective_user.id)
    is_joined = await is_subscribed(context.bot, user_id)
    if not is_joined:
        kb = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
              [InlineKeyboardButton("✅ Joined", callback_data="check_join")]]
        msg = "❌ আগে জয়েন করুন!"
    else:
        kb = [[InlineKeyboardButton("🎬 Open Movie App", callback_data="open_app")],
              [InlineKeyboardButton("🚀 Referral", callback_data="get_ref")]]
        msg = "🎬 **Viral Movie Hub**"
    
    if update.callback_query: await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else: await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    if query.data == "check_join": await show_menu(update, context)
    elif query.data == "open_app":
        user = user_ref.child(user_id).get() or {}
        refs = user.get("referrals", 0)
        if refs < 5:
            bot_me = await context.bot.get_me()
            await query.edit_message_text(f"🔒 ৫ রেফারেল লাগবে।\n{progress_bar(refs)}\nলিংক: `https://t.me/{bot_me.username}?start={user_id}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("✅ আনলকড!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Open App", web_app={"url": APP_URL})]]))

# ---------------- MAIN RUNNER ----------------
def main():
    # ১. প্রথমে Flask থ্রেড চালু করুন যাতে Render পোর্ট খুঁজে পায়
    threading.Thread(target=run_flask, daemon=True).start()

    # ২. টেলিগ্রাম বট সেটআপ
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is starting...")
    # ৩. run_polling সরাসরি ব্যবহার করুন, এটি Render-এর জন্য সবচেয়ে ভালো কাজ করে
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
