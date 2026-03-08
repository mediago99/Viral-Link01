import os
import json
import threading
import asyncio
from flask import Flask
import firebase_admin
from firebase_admin import credentials, db
from telegram import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    Update, 
    WebAppInfo, 
    MenuButtonWebApp  # এটি এরর সমাধানের জন্য যুক্ত করা হয়েছে
)
from telegram.constants import ParseMode 
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- WEB SERVER (For Render) ----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running Perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 6311806060  
CHANNEL_USERNAME = "@viralmoviehubbd"
APP_URL = os.environ.get("APP_URL") 
FIREBASE_DB_URL = "https://viralmoviehubbd-default-rtdb.firebaseio.com/"
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS")

# ---------------- FIREBASE SETUP ----------------
if not firebase_admin._apps:
    try:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
    except Exception as e:
        print(f"Firebase Initialization Error: {e}")

user_ref = db.reference('users')
movie_ref = db.reference('movies')

# ---------------- HELPERS ----------------
async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

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
            user_ref.child(ref_by).update({
                "referrals": r.get("referrals", 0) + 1,
                "coins": r.get("coins", 0) + 100
            })
    
    if not await is_subscribed(context.bot, user_id):
        kb = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
              [InlineKeyboardButton("✅ Joined", callback_data="check_join")]]
        await update.message.reply_text("❌ আগে আমাদের চ্যানেলে জয়েন করুন।", reply_markup=InlineKeyboardMarkup(kb))
    else:
        kb = [[InlineKeyboardButton("🎬 Open Movie App", callback_data="open_app")]]
        await update.message.reply_text("🎬 Viral Movie Hub এ স্বাগতম!", reply_markup=InlineKeyboardMarkup(kb))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = user_ref.child(user_id).get() or {"referrals": 0, "coins": 0}
    refs = user.get("referrals", 0)
    bot_me = await context.bot.get_me()
    text = f"📊 **আপনার স্ট্যাটাস**\n\n👥 মোট রেফার: {refs}/5\n📈 অগ্রগতি: {progress_bar(refs)}\n\n🔗 লিংক: `https://t.me/{bot_me.username}?start={user_id}`"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    
    if query.data == "check_join":
        if await is_subscribed(context.bot, user_id):
            await query.edit_message_text("✅ ধন্যবাদ! এখন মুভি অ্যাপ ওপেন করতে পারবেন।", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Open App", callback_data="open_app")]]))
        else:
            await query.answer("❌ আপনি এখনো জয়েন করেননি!", show_alert=True)
            
    elif query.data == "open_app":
        user = user_ref.child(user_id).get() or {}
        refs = user.get("referrals", 0)
        if refs < 5:
            bot_me = await context.bot.get_me()
            await query.edit_message_text(f"🔒 ৫ জন রেফার লাগবে। আপনার আছে: {refs}/5\n{progress_bar(refs)}", parse_mode=ParseMode.MARKDOWN)
        else:
            kb = [[InlineKeyboardButton("🚀 Launch Mini App", web_app=WebAppInfo(url=APP_URL))]]
            await query.edit_message_text("✅ ৫ রেফার পূর্ণ হয়েছে! নিচের বাটনে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(kb))

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        data = " ".join(context.args).split("|")
        movie_name, image_url, movie_link = [i.strip() for i in data]
        movie_ref.push({"title": movie_name, "image_url": image_url, "video_url": movie_link})
        kb = [[InlineKeyboardButton("🎬 Watch Movie (Open App)", web_app=WebAppInfo(url=APP_URL))]]
        await context.bot.send_photo(chat_id=CHANNEL_USERNAME, photo=image_url, 
                                     caption=f"🎬 **{movie_name}**\n\nঅ্যাপ থেকে আনলক করুন।", 
                                     reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("✅ মুভিটি পোস্ট হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ ভুল হয়েছে: /post নাম | ইমেজ URL | মুভি লিঙ্ক")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    all_users = user_ref.get()
    all_movies = movie_ref.get()
    user_count = len(all_users) if all_users else 0
    movie_count = len(all_movies) if all_movies else 0
    text = (f"📊 **বট রিপোর্ট (অ্যাডমিন)**\n\n"
            f"👤 মোট ইউজার: {user_count} জন\n"
            f"🎬 মোট মুভি: {movie_count} টি")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# --- এরর সমাধান করা মেনু বাটন ফাংশন ---
async def post_init(application):
    # আপনার গিটহাব পেজ লিঙ্ক
    MOVIE_APP_URL = "https://mediago99.github.io/Viral-Link01/" 
    
    # এখানে MenuButtonWebApp ব্যবহার করা হয়েছে যা 'type' ফিল্ড এরর সমাধান করবে
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="ভিডিও দেখুন", 
                web_app=WebAppInfo(url=MOVIE_APP_URL)
            )
        )
        print("Menu Button Configured Successfully!")
    except Exception as e:
        print(f"Failed to set Menu Button: {e}")

# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # application তৈরি করার সময় post_init এর মাধ্যমে মেনু বাটন সেট করা হবে
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("post", post))
    application.add_handler(CommandHandler("users", admin_stats))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is starting...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application.run_polling(drop_pending_updates=True)
    
