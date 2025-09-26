import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from pymongo import MongoClient

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN", "7433667530:AAHTYaW6Y76lfX5wN3q8ht7Zvp6-wCurObk")
BOT_USERNAME = "freeefilebot"
DEV_URL = "https://t.me/hiden_25"
CHANNEL_URL = "https://t.me/freeotpss"
OWNER_ID = 7761576669
CHANNEL_ID = -1003033705024

MONGO_URL = "mongodb+srv://darkdevil9793:1aNXaCVF88VBo1Ma@cluster0.8a6miuy.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# ================ LOGGER ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    try:
        users_col.update_one({"user_id": user.id}, {"$setOnInsert": {"user_id": user.id}}, upsert=True)
    except Exception as e:
        logger.error(f"MongoDB error in start: {e}")
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
        return

    if context.args:
        file_key = context.args[0]
        try:
            file_doc = files_col.find_one({"key": file_key})
            if file_doc:
                files_col.update_one({"key": file_key}, {"$inc": {"downloads": 1}})
                await update.message.reply_document(file_doc["file_id"])
                return
            else:
                await update.message.reply_text("❌ File not found or expired.")
                return
        except Exception as e:
            logger.error(f"MongoDB error in start: {e}")
            await update.message.reply_text("⚠️ An error occurred while retrieving the file.")
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
    try:
        files_col.update_one(
            {"key": file_key},
            {"$set": {"file_id": file_id, "user_id": user.id}, "$setOnInsert": {"downloads": 0}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"MongoDB error in handle_file: {e}")
        await update.message.reply_text("⚠️ An error occurred while storing the file.")
        return

    link = f"https://t.me/{BOT_USERNAME}?start={file_key}"
    await update.message.reply_text(f"✅ File stored!\n🔗 Link: {link}")

    if user.id == OWNER_ID:
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"share_yes:{file_key}"),
                InlineKeyboardButton("❌ No", callback_data="share_no")
            ]
        ]
        await update.message.reply_text(
            "📢 Do you want to share this file in your channel?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("share_yes:"):
        file_key = query.data.split(":")[1]
        context.user_data["share_file_key"] = file_key
        await query.message.reply_text("✍️ Please send the caption text for the channel post.")
    elif query.data == "share_no":
        await query.message.reply_text("❌ File not shared to channel.")

async def caption_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "share_file_key" not in context.user_data:
        return
    caption = update.message.text
    file_key = context.user_data.pop("share_file_key")
    link = f"https://t.me/{BOT_USERNAME}?start={file_key}"
    keyboard = [[InlineKeyboardButton("Click Here", url=link)]]
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=caption,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text("✅ File shared in channel!")
    except Exception as e:
        logger.error(f"Error sharing to channel: {e}")
        await update.message.reply_text("⚠️ An error occurred while sharing to the channel.")

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        files = files_col.find({"user_id": user.id})
        files = list(files)
        if not files:
            return await update.message.reply_text("📂 You have no uploaded files.")
        msg = "📁 *Your Files:*\n\n"
        for f in files:
            key = f["key"]
            link = f"https://t.me/{BOT_USERNAME}?start={key}"
            msg += f"🔗 {link}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"MongoDB error in myfiles: {e}")
        await update.message.reply_text("⚠️ An error occurred while retrieving your files.")

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if len(context.args) < 1:
        return await update.message.reply_text("⚠️ Usage: /delete <file_key>")
    file_key = context.args[0]
    try:
        files_col.delete_one({"key": file_key, "user_id": user.id})
        await update.message.reply_text("🗑 File deleted (if existed).")
    except Exception as e:
        logger.error(f"MongoDB error in delete_file: {e}")
        await update.message.reply_text("⚠️ An error occurred while deleting the file.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ You are not allowed to use this command.")
    try:
        total_files = files_col.count_documents({})
        total_users = users_col.count_documents({})
        await update.message.reply_text(
            f"📊 *Bot Stats:*\n\n👥 Users: {total_users}\n📂 Files: {total_files}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"MongoDB error in stats: {e}")
        await update.message.reply_text("⚠️ An error occurred while retrieving stats.")

# ================ MAIN =================
async def main():
    try:
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
        app.add_handler(CommandHandler("myfiles", myfiles))
        app.add_handler(CommandHandler("delete", delete_file))
        app.add_handler(CommandHandler("stats", stats))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), caption_handler))
        app.add_handler(CallbackQueryHandler(button_handler))

        logger.info("Starting bot with polling...")
        await app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
