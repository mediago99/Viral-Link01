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

# ---------------- WEB SERVER (For Render) ----------------
@app.route('/')
def home():
    return "Bot is Running! Build by Gemini"

def run_flask():
    # Render সাধারণত ১০০০০ পোর্টে রান করে
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ---------------- CONFIG & ENV ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
CHANNEL_USERNAME = "@viralmoviehubbd" # আপনার চ্যানেলের ইউজারনেম
APP_URL = os.environ.get("APP_URL")   # আপনার মুভি অ্যাপের লিংক

FIREBASE_DB_URL = "https://viralmoviehubbd-default-rtdb.firebaseio.com/"
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS") # JSON string from env

# ---------------- FIREBASE INITIALIZE ----------------
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
    """ইউজার চ্যানেলে জয়েন করেছে কি না তা চেক করে"""
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        # member, administrator অথবা creator হলে ট্রু রিটার্ন করবে
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def progress_bar(count, total=5):
    """রেফারেল প্রগ্রেস দেখানোর জন্য বার তৈরি করে"""
    filled = "█" * min(count, total)
    empty = "░" * max(0, total - count)
    percent = int((min(count, total) / total) * 100)
    return f"[{filled}{empty}] {percent}%"

# ---------------- COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # নতুন ইউজার হলে ডাটাবেসে সেভ করা এবং রেফারেল চেক করা
    if not user_ref.child(user_id).get():
        ref_by = context.args[0] if context.args else None
        user_ref.child(user_id).set({
            "referrals": 0,
            "coins": 0,
            "ref_by": ref_by
        })
        # যদি কেউ কারো লিংকে জয়েন করে তাকে ১০০ কয়েন এবং ১টি রেফারেল দেওয়া
        if ref_by and ref_by != user_id:
            r = user_ref.child(ref_by).get() or {"referrals": 0, "coins": 0}
            user_ref.child(ref_by).update({
                "referrals": r.get("referrals", 0) + 1,
                "coins": r.get("coins", 0) + 100
            })
    
    await show_menu(update, context)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """অ্যাডমিন এই কমান্ড দিলে টোটাল ইউজার দেখতে পাবে"""
    if update.effective_user.id != ADMIN_ID:
        return # আপনি ছাড়া অন্য কেউ চাইলে কাজ করবে না
        
    users = user_ref.get()
    total = len(users) if users else 0
    await update.message.reply_text(f"📊 **বট স্ট্যাটাস:**\n\n👥 মোট ইউজার: {total} জন")

# ---------------- MENU LOGIC ----------------
async def show_menu(update, context):
    user_id = str(update.effective_user.id)
    is_joined = await is_subscribed(context.bot, user_id)

    if not is_joined:
        # ফোর্স জয়েন বাটন
        kb = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ Joined (চেক করুন)", callback_data="check_join")]
        ]
        msg = "❌ **অ্যাক্সেস ডিনাইড!**\n\nবটটি ব্যবহার করতে আপনাকে অবশ্যই আমাদের চ্যানেলে জয়েন থাকতে হবে।"
    else:
        # মেইন মেনু
        kb = [
            [InlineKeyboardButton("🎬 Open Movie App", callback_data="open_app")],
            [InlineKeyboardButton("🚀 Referral Link", callback_data="get_ref")],
            [InlineKeyboardButton("💰 Wallet / Balance", callback_data="wallet")]
        ]
        msg = "🎬 **Viral Movie Hub**\n\nনিচের বাটনগুলো ব্যবহার করে আপনার কাঙ্ক্ষিত অপশনটি বেছে নিন।"

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

# ---------------- CALLBACK HANDLER ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(update.effective_user.id)
    await query.answer()

    if query.data == "check_join":
        await show_menu(update, context)
    
    elif query.data == "open_app":
        user = user_ref.child(user_id).get() or {}
        refs = user.get("referrals", 0)
        
        # ৫ জন রেফারেল না হলে লক রাখা
        if refs < 5:
            bot_me = await context.bot.get_me()
            ref_link = f"https://t.me/{bot_me.username}?start={user_id}"
            msg = (
                f"🔒 **অ্যাপটি এখনো লক করা আছে!**\n\n"
                f"এটি আনলক করতে আপনার কমপক্ষে ৫ জন রেফারেল লাগবে।\n\n"
                f"📊 প্রগ্রেস: {progress_bar(refs)}\n"
                f"📢 আপনার ইনভাইট লিংক:\n`{ref_link}`"
            )
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            # ৫ জন পূর্ণ হলে ওয়েব অ্যাপ বাটন দেওয়া
            kb = [[InlineKeyboardButton("🚀 Open Movie WebApp", web_app={"url": APP_URL})]]
            await query.edit_message_text("✅ অভিনন্দন! আপনার ৫টি রেফারেল পূর্ণ হয়েছে। অ্যাপটি এখন আনলকড।", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == "get_ref":
        bot_me = await context.bot.get_me()
        user = user_ref.child(user_id).get() or {}
        ref_link = f"https://t.me/{bot_me.username}?start={user_id}"
        msg = f"🚀 **আপনার রেফারেল ইনফো:**\n\n🔗 লিংক: `{ref_link}`\n👥 মোট রেফার: {user.get('referrals', 0)} জন"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)

    elif query.data == "wallet":
        user = user_ref.child(user_id).get() or {}
        coins = user.get("coins", 0)
        await query.edit_message_text(f"💰 **আপনার ওয়ালেট:**\n\nবর্তমান ব্যালেন্স: {coins} Coins", parse_mode=ParseMode.MARKDOWN)

# ---------------- MAIN ----------------
async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # হ্যান্ডলার রেজিস্ট্রেশন
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Flask থ্রেড শুরু করা (Render এর জন্য জরুরি)
    threading.Thread(target=run_flask, daemon=True).start()

    print("Gemini: Bot starting polling...")

    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        # লুপ সচল রাখতে
        while True:
            await asyncio.sleep(20)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    
