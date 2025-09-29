import logging
import os
import threading
from flask import Flask, request, Response
from pymongo import MongoClient
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN", "YOUR_BOT_TOKEN")
BOT_USERNAME = "freeefilebot"
DEV_URL = "https://t.me/hiden_25"
CHANNEL_URL = "https://t.me/freeotpss"
OWNER_ID = 7761576669
CHANNEL_ID = -1003033705024

MONGO_URL = "mongodb+srv://darkdevil9793:1aNXaCVF88VBo1Ma@cluster0.8a6miuy.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render automatically sets this env var

# ================ LOGGER ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# ================ DB INIT =================
try:
    mongo_client = MongoClient(MONGO_URL)
    db = mongo_client["file_bot_db"]
    files_col = db["files"]
    users_col = db["users"]
    logger.info("MongoDB connected successfully!")
except Exception as e:
    logger.error(f"Failed to connect MongoDB: {e}")
    raise

# ================ HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_col.update_one({"user_id": user.id}, {"$setOnInsert": {"user_id": user.id}}, upsert=True)

    if context.args:
        file_key = context.args[0]
        file_doc = files_col.find_one({"key": file_key})
        if file_doc:
            files_col.update_one({"key": file_key}, {"$inc": {"downloads": 1}})
            await update.message.reply_document(file_doc["file_id"])
            return
        else:
            await update.message.reply_text("❌ File not found or expired.")
            return

    keyboard = [
        [InlineKeyboardButton("👨‍💻 Developer", url=DEV_URL)],
        [InlineKeyboardButton("📢 Channel", url=CHANNEL_URL)]
    ]
    await update.message.reply_text(
        "📂 Welcome to *File Sharing Bot*\n\n"
        "➡️ Send me any file and I will give you a sharable link.\n\n"
        "🔹 Use /myfiles to see your uploaded files\n"
        "🔹 Use /delete <key> to delete a file\n"
        "🔹 Use /stats to see bot statistics (Admin only)\n",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    document = update.message.document
    photo = update.message.photo

    if document:
        file_id = document.file_id
    elif photo:
        file_id = photo[-1].file_id
    else:
        return await update.message.reply_text("⚠️ Please send a valid file.")

    file_key = str(abs(hash(file_id)))[:10]
    files_col.update_one(
        {"key": file_key},
        {"$set": {"file_id": file_id, "user_id": user.id}, "$setOnInsert": {"downloads": 0}},
        upsert=True
    )

    link = f"https://t.me/{BOT_USERNAME}?start={file_key}"
    await update.message.reply_text(f"✅ File stored!\n🔗 Link: {link}")

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    files = list(files_col.find({"user_id": user.id}))
    if not files:
        return await update.message.reply_text("📂 You have no uploaded files.")
    msg = "📁 *Your Files:*\n\n"
    for f in files:
        key = f["key"]
        link = f"https://t.me/{BOT_USERNAME}?start={key}"
        msg += f"🔗 {link}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if len(context.args) < 1:
        return await update.message.reply_text("⚠️ Usage: /delete <file_key>")
    file_key = context.args[0]
    files_col.delete_one({"key": file_key, "user_id": user.id})
    await update.message.reply_text("🗑 File deleted (if existed).")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ You are not allowed to use this command.")
    total_files = files_col.count_documents({})
    total_users = users_col.count_documents({})
    await update.message.reply_text(
        f"📊 *Bot Stats:*\n\n👥 Users: {total_users}\n📂 Files: {total_files}",
        parse_mode="Markdown"
    )

# ================ MAIN =================
application = ApplicationBuilder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
application.add_handler(CommandHandler("myfiles", myfiles))
application.add_handler(CommandHandler("delete", delete_file))
application.add_handler(CommandHandler("stats", stats))

@app.route("/health")
def health():
    return Response("OK", status=200)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return Response("ok", status=200)

if __name__ == "__main__":
    # Set webhook on startup
    import asyncio
    async def set_webhook():
        await application.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
        logger.info(f"Webhook set to {WEBHOOK_URL}/{TOKEN}")

    asyncio.get_event_loop().run_until_complete(set_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
