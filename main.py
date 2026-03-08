import os
import json
import threading
import asyncio
from flask import Flask
import firebase_admin
from firebase_admin import credentials, db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode 
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- WEB SERVER (For Render) ----------------
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running Perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 6311806060 # আপনার আইডি
CHANNEL_USERNAME = "@viralmoviehubbd" # আপনার চ্যানেল
APP_URL = os.environ.get("APP_URL") # আপনার মিনি অ্যাপের লিঙ্ক
FIREBASE_DB_URL = "https://viralmoviehubbd-default-rtdb.firebaseio.com/"
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS")

# ---------------- FIREBASE SETUP ----------------
if not firebase_admin._apps:
    try:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
    except Exception as e: print(f"Firebase Error: {e}")

user_ref = db.reference('users')
movie_ref = db.reference('movies')

# ---------------- HELPERS ----------------
async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    # ইউজার ডাটাবেজ চেক
    if not user_ref.child(user_id).get():
        user_ref.child(user_id).set({"referrals": 0, "coins": 0})
    
    # জয়েন চেক
    if not await is_subscribed(context.bot, user_id):
        kb = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
              [InlineKeyboardButton("✅ Joined", callback_data="check_join")]]
        await update.message.reply_text("❌ আগে চ্যানেলে জয়েন করুন", reply_markup=InlineKeyboardMarkup(kb))
    else:
        # মিনি অ্যাপ বাটন
        kb = [[InlineKeyboardButton("🎬 Open Movie App", web_app=WebAppInfo(url=APP_URL))]]
        await update.message.reply_text("🎬 Viral Movie Hub এ স্বাগতম", reply_markup=InlineKeyboardMarkup(kb))

# অ্যাডমিন পোস্ট সিস্টেম
async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        data = " ".join(context.args).split("|")
        movie_name, image_url, movie_link = [i.strip() for i in data]
        
        # ১. ডাটাবেজে মুভি সেভ করা (যাতে অ্যাপে শো করে)
        new_movie = movie_ref.push({
            "title": movie_name,
            "image_url": image_url,
            "video_url": movie_link
        })
        
        # ২. চ্যানেলে পোস্ট পাঠানো (বাটনটি মিনি অ্যাপ ওপেন করবে)
        kb = [[InlineKeyboardButton("🎬 Watch Movie (Open App)", web_app=WebAppInfo(url=APP_URL))]]
        await context.bot.send_photo(chat_id=CHANNEL_USERNAME, photo=image_url, 
                                     caption=f"🎬 {movie_name}\n\nনিচের বাটনে ক্লিক করে মুভিটি আনলক করুন।", 
                                     reply_markup=InlineKeyboardMarkup(kb))
        await update.message.reply_text("✅ মুভিটি অ্যাপ এবং চ্যানেলে পোস্ট হয়েছে!")
    except:
        await update.message.reply_text("❌ ফরম্যাট: /post নাম | ইমেজ URL | মুভি লিঙ্ক")

# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("post", post))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application.run_polling(drop_pending_updates=True)
