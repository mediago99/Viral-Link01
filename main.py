import os
import json
import threading
from flask import Flask
import firebase_admin
from firebase_admin import credentials, db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ---------------- WEB SERVER ----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running Perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
CHANNEL_USERNAME = "@viralmoviehubbd"
APP_URL = os.environ.get("APP_URL")
FIREBASE_DB_URL = "https://viralmoviehubbd-default-rtdb.firebaseio.com/"
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS")

# ---------------- FIREBASE ----------------
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
    except:
        return False

def progress_bar(count, total=5):
    filled = "█" * min(count, total)
    empty = "░" * max(0, total - count)
    return f"[{filled}{empty}] {int((min(count, total)/total)*100)}%"

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # ইউজার Firebase এ থাকছে কি না চেক
    if not user_ref.child(user_id).get():
        ref_by = context.args[0] if context.args else None
        user_ref.child(user_id).set({"referrals": 0, "coins": 0, "ref_by": ref_by})
        if ref_by and ref_by != user_id:
            r = user_ref.child(ref_by).get() or {"referrals": 0, "coins": 0}
            user_ref.child(ref_by).update({
                "referrals": r.get("referrals", 0) + 1,
                "coins": r.get("coins", 0) + 100
            })
    
    # চ্যানেল সাবস্ক্রিপশন চেক
    is_joined = await is_subscribed(context.bot, user_id)
    if not is_joined:
        kb = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ Joined", callback_data="check_join")]
        ]
        await update.message.reply_text("❌ আগে চ্যানেলে জয়েন করুন", reply_markup=InlineKeyboardMarkup(kb))
    else:
        kb = [[InlineKeyboardButton("🎬 Open Movie App", callback_data="open_app")]]
        await update.message.reply_text("🎬 Viral Movie Hub এ স্বাগতম", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    
    if query.data == "check_join":
        is_joined = await is_subscribed(context.bot, user_id)
        if is_joined:
            await query.edit_message_text(
                "✅ ধন্যবাদ জয়েন করার জন্য!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Open App", callback_data="open_app")]])
            )
        else:
            await query.answer("❌ এখনো জয়েন করেননি!", show_alert=True)
            
    elif query.data == "open_app":
        user = user_ref.child(user_id).get() or {}
        refs = user.get("referrals", 0)
        if refs < 5:
            bot_me = await context.bot.get_me()
            await query.edit_message_text(
                f"🔒 ৫ রেফারেল লাগবে।\n{progress_bar(refs)}\nলিংক: `https://t.me/{bot_me.username}?start={user_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                "✅ আনলকড!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Open WebApp", web_app={"url": APP_URL})]])
            )

# ---------------- POST COMMAND ----------------
async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to post.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Format: /post মুভি নাম | ইমেজ URL | মুভি লিংক")
        return
    
    try:
        data = " ".join(context.args).split("|")
        movie_name = data[0].strip()
        image_url = data[1].strip()
        movie_link = data[2].strip()
        
        # চ্যানেলে পোস্ট
        kb = [[InlineKeyboardButton("🎬 Watch Movie", url=movie_link)]]
        await context.bot.send_photo(
            chat_id=CHANNEL_USERNAME,
            photo=image_url,
            caption=f"🎬 {movie_name}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        
        await update.message.reply_text("✅ Posted Successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ---------------- MAIN ----------------
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("post", post))
    
    print("Bot Started Successfully!")
    
    # Python 3.14 + Render safe polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    while True:
        await asyncio.sleep(15)

# ---------------- RUN ----------------
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
