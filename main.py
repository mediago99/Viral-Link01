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
    MenuButtonWebApp 
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
MOVIE_APP_URL = "https://mediago99.github.io/Viral-Link01/"
FIREBASE_DB_URL = "https://viralmoviehubbd-default-rtdb.firebaseio.com/"
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS")

# কতজন রেফার লাগবে? (৫ থেকে কমিয়ে ১ করা হয়েছে)
REFERRAL_COUNT_NEEDED = 1 

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

def progress_bar(count, total=REFERRAL_COUNT_NEEDED):
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
        await update.message.reply_text("❌ মুভি দেখতে হলে আগে আমাদের চ্যানেলে জয়েন করুন।", reply_markup=InlineKeyboardMarkup(kb))
    else:
        kb = [[InlineKeyboardButton("🎬 Open Movie App", callback_data="open_app")]]
        await update.message.reply_text("🎬 Viral Movie Hub এ স্বাগতম!", reply_markup=InlineKeyboardMarkup(kb))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = user_ref.child(user_id).get() or {"referrals": 0, "coins": 0}
    refs = user.get("referrals", 0)
    bot_me = await context.bot.get_me()
    text = f"📊 **আপনার স্ট্যাটাস**\n\n👥 মোট রেফার: {refs}/{REFERRAL_COUNT_NEEDED}\n📈 অগ্রগতি: {progress_bar(refs)}\n\n🔗 লিংক: `https://t.me/{bot_me.username}?start={user_id}`"
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
        if refs < REFERRAL_COUNT_NEEDED:
            bot_me = await context.bot.get_me()
            await query.edit_message_text(f"🔒 {REFERRAL_COUNT_NEEDED} জন রেফার লাগবে। আপনার আছে: {refs}/{REFERRAL_COUNT_NEEDED}\n{progress_bar(refs)}", parse_mode=ParseMode.MARKDOWN)
        else:
            kb = [[InlineKeyboardButton("🚀 Launch Mini App", web_app=WebAppInfo(url=APP_URL))]]
            await query.edit_message_text("✅ রেফার পূর্ণ হয়েছে! নিচের বাটনে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(kb))

# ব্রডকাস্ট ফাংশন: এটি সবার ইনবক্সে মেসেজ পাঠাবে এবং অ্যাক্টিভ ইউজার রিপোর্ট দেবে
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ যে মেসেজটি সবার কাছে পাঠাতে চান, সেটির ওপর রিপ্লাই দিয়ে /broadcast লিখুন।")
        return

    reply_msg = update.message.reply_to_message
    all_users = user_ref.get()
    if not all_users: 
        await update.message.reply_text("ডেটাবেজে কোনো ইউজার নেই!")
        return

    status_msg = await update.message.reply_text(f"⏳ ব্রডকাস্ট শুরু হয়েছে...\nমোট ইউজার: {len(all_users)}")
    
    success = 0
    blocked = 0
    
    for user_id in all_users:
        try:
            # কপি মেসেজ ফাংশন ব্যবহার করা হয়েছে যাতে টেক্সট, ফটো সব পাঠানো যায়
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=reply_msg.chat.id,
                message_id=reply_msg.message_id
            )
            success += 1
            await asyncio.sleep(0.05) # রেট লিমিট এড়াতে ছোট বিরতি
        except Exception:
            blocked += 1
            
    await status_msg.edit_text(f"✅ ব্রডকাস্ট সম্পন্ন!\n\n🚀 সফল: {success}\n🚫 ইনঅ্যাক্টিভ/ব্লক: {blocked}\n📊 মোট ইউজার ডেটা: {len(all_users)}")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    full_text = " ".join(context.args)
    data = [i.strip() for i in full_text.split("|")]
    
    if len(data) < 3:
        await update.message.reply_text("❌ ফরম্যাট: /post নাম | ইমেজ URL | মুভি লিঙ্ক")
        return

    movie_name, image_url, movie_link = data[0], data[1], data[2]
    movie_ref.push({"title": movie_name, "image_url": image_url, "video_url": movie_link})
    
    bot_me = await context.bot.get_me()
    kb = [[InlineKeyboardButton("🎬 Watch Movie", url=f"https://t.me/{bot_me.username}")]]
    
    await context.bot.send_photo(
        chat_id=CHANNEL_USERNAME, 
        photo=image_url, 
        caption=f"🎬 **{movie_name}**\n\nমুভিটি দেখতে নিচের বাটনে ক্লিক করুন।", 
        reply_markup=InlineKeyboardMarkup(kb), 
        parse_mode=ParseMode.MARKDOWN
    )
    await update.message.reply_text("✅ চ্যানেলে পোস্ট সফল হয়েছে! সবাইকে পাঠাতে এই মেসেজের ওপর রিপ্লাই দিয়ে /broadcast লিখুন।")

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

async def post_init(application):
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="ভিডিও দেখুন", 
                web_app=WebAppInfo(url=MOVIE_APP_URL)
            )
        )
    except Exception as e:
        print(f"Failed to set Menu Button: {e}")

# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("post", post))
    application.add_handler(CommandHandler("users", admin_stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is starting with Broadcast feature...")
    application.run_polling(drop_pending_updates=True)
    
