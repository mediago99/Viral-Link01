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
def home():
    return "Bot is Running Perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ---------------- CONFIGURATION ----------------
# Render-এর Environment Variables থেকে এই মানগুলো আসবে
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 6311806060  # আপনার আইডি নিশ্চিত করা হলো
CHANNEL_USERNAME = "@viralmoviehubbd"
APP_URL = os.environ.get("APP_URL") # আপনার মিনি অ্যাপের লিঙ্ক
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

# ১. স্টার্ট কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # নতুন ইউজার ও রেফারেল লজিক
    if not user_ref.child(user_id).get():
        ref_by = context.args[0] if context.args else None
        user_ref.child(user_id).set({"referrals": 0, "coins": 0, "ref_by": ref_by})
        if ref_by and ref_by != user_id:
            r = user_ref.child(ref_by).get() or {"referrals": 0, "coins": 0}
            user_ref.child(ref_by).update({
                "referrals": r.get("referrals", 0) + 1,
                "coins": r.get("coins", 0) + 100
            })
    
    # সাবস্ক্রিপশন চেক
    if not await is_subscribed(context.bot, user_id):
        kb = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ Joined", callback_data="check_join")]
        ]
        await update.message.reply_text("❌ আগে আমাদের চ্যানেলে জয়েন করুন।", reply_markup=InlineKeyboardMarkup(kb))
    else:
        kb = [[InlineKeyboardButton("🎬 Open Movie App", callback_data="open_app")]]
        await update.message.reply_text("🎬 Viral Movie Hub এ স্বাগতম! মুভি দেখতে নিচের বাটনে ক্লিক করুন।", reply_markup=InlineKeyboardMarkup(kb))

# ২. স্ট্যাটাস কমান্ড (রেফারেল চেক করার জন্য)
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = user_ref.child(user_id).get() or {"referrals": 0, "coins": 0}
    refs = user.get("referrals", 0)
    
    bot_me = await context.bot.get_me()
    text = (
        f"📊 **আপনার স্ট্যাটাস**\n\n"
        f"👥 মোট রেফার: {refs}/5\n"
        f"📈 অগ্রগতি: {progress_bar(refs)}\n\n"
        f"🔗 রেফার লিংক: `https://t.me/{bot_me.username}?start={user_id}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ৩. বাটন হ্যান্ডলার (মিনি অ্যাপ শো করার জন্য)
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
            await query.edit_message_text(
                f"🔒 এই মুভিটি আনলক করতে ৫ জন রেফার লাগবে।\n"
                f"আপনার বর্তমান রেফার: {refs}/5\n"
                f"প্রগ্রেস: {progress_bar(refs)}\n\n"
                f"আপনার লিংক: `https://t.me/{bot_me.username}?start={user_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # এখানে WebAppInfo ইমপ্লিমেন্ট করা হয়েছে যা মিনি অ্যাপ উইন্ডো খুলবে
            kb = [[InlineKeyboardButton("🚀 Launch Mini App", web_app=WebAppInfo(url=APP_URL))]]
            await query.edit_message_text("✅ অভিনন্দন! আপনার ৫ রেফার পূর্ণ হয়েছে। নিচের বাটনে ক্লিক করে মুভি দেখুন।", reply_markup=InlineKeyboardMarkup(kb))

# ৪. অ্যাডমিন পোস্ট কমান্ড (চ্যানেলে পোস্ট পাঠানোর জন্য)
async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        # ইনপুট ফরম্যাট: /post নাম | ইমেজ URL | মুভি লিংক
        data = " ".join(context.args).split("|")
        movie_name = data[0].strip()
        image_url = data[1].strip()
        movie_link = data[2].strip()
        
        # ডাটাবেজে মুভি সেভ করা যাতে মিনি অ্যাপে ইউজার এটি দেখতে পায়
        movie_ref.push({
            "title": movie_name,
            "image_url": image_url,
            "video_url": movie_link
        })
        
        # চ্যানেলে বাটনসহ পোস্ট পাঠানো (বাটনটি মিনি অ্যাপ ওপেন করবে)
        kb = [[InlineKeyboardButton("🎬 Watch Movie (Open App)", web_app=WebAppInfo(url=APP_URL))]]
        
        await context.bot.send_photo(
            chat_id=CHANNEL_USERNAME,
            photo=image_url,
            caption=f"🎬 **{movie_name}**\n\nমুভিটি দেখতে নিচের বাটনে ক্লিক করে অ্যাপ থেকে আনলক করুন।",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_text("✅ মুভিটি অ্যাপ এবং চ্যানেলে সফলভাবে পোস্ট হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ ভুল হয়েছে! সঠিকভাবে লিখুন:\n/post নাম | ইমেজ URL | মুভি লিঙ্ক\nError: {str(e)}")

# main.py এর নিচে এই অংশটুকু যোগ করুন

async def post_init(application):
    # আপনার মুভি অ্যাপের ফ্রন্টএন্ড লিঙ্ক (GitHub Pages লিঙ্ক) এখানে দিন
    # রেন্ডার লিঙ্ক নয়, যেখানে index.html আছে সেই লিঙ্কটি হবে।
    MOVIE_APP_FRONTEND = "https://mediago99.github.io/Viral-Link01" 
    
    await application.bot.set_chat_menu_button(
        menu_button=WebAppInfo(url=MOVIE_APP_FRONTEND)
    )

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    
    # application তৈরি করার সময় post_init যোগ করা হয়েছে
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("post", post))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is starting...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application.run_polling(drop_pending_updates=True)

        
