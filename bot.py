import logging
import sqlite3
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

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN", "7433667530:AAHTYaW6Y76lfX5wN3q8ht7Zvp6-wCurObk")
BOT_USERNAME = "freeefilebot"
DEV_URL = "https://t.me/hiden_25"
CHANNEL_URL = "https://t.me/freeotpss"
OWNER_ID = 7761576669
CHANNEL_ID = -1003033705024
DB_PATH = "/var/data/files.db"  # Persistent storage path for Render

# ================ LOGGER ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================ DB INIT =================
try:
    # Ensure the directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    logger.info(f"Ensured directory exists: {os.path.dirname(DB_PATH)}")
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        key TEXT PRIMARY KEY,
        file_id TEXT,
        user_id INTEGER,
        downloads INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY
    )
    """)
    conn.commit()
    logger.info(f"Database initialized successfully at {DB_PATH}")
except sqlite3.Error as e:
    logger.error(f"Failed to initialize database at {DB_PATH}: {e}")
    raise
except OSError as e:
    logger.error(f"Failed to create directory for database at {os.path.dirname(DB_PATH)}: {e}")
    raise

# ================ HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user.id,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error in start: {e}")
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
        return

    if context.args:
        file_key = context.args[0]
        try:
            cursor.execute("SELECT file_id, downloads FROM files WHERE key=?", (file_key,))
            row = cursor.fetchone()
            if row:
                file_id, downloads = row
                cursor.execute("UPDATE files SET downloads=? WHERE key=?", (downloads + 1, file_key))
                conn.commit()
                await update.message.reply_document(file_id)
                return
            else:
                await update.message.reply_text("❌ File not found or expired.")
                return
        except sqlite3.Error as e:
            logger.error(f"Database error in start: {e}")
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
        file_id = photo[-1].file_id  # Use highest quality photo
    else:
        return await update.message.reply_text("⚠️ Please send a valid file.")

    file_key = str(abs(hash(file_id)))[:10]
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO files (key, file_id, user_id, downloads) VALUES (?, ?, ?, 0)",
            (file_key, file_id, user.id)
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error in handle_file: {e}")
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
        cursor.execute("SELECT key FROM files WHERE user_id=?", (user.id,))
        files = cursor.fetchall()
        if not files:
            return await update.message.reply_text("📂 You have no uploaded files.")
        msg = "📁 *Your Files:*\n\n"
        for f in files:
            key = f[0]
            link = f"https://t.me/{BOT_USERNAME}?start={key}"
            msg += f"🔗 {link}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except sqlite3.Error as e:
        logger.error(f"Database error in myfiles: {e}")
        await update.message.reply_text("⚠️ An error occurred while retrieving your files.")

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if len(context.args) < 1:
        return await update.message.reply_text("⚠️ Usage: /delete <file_key>")
    file_key = context.args[0]
    try:
        cursor.execute("DELETE FROM files WHERE key=? AND user_id=?", (file_key, user.id))
        conn.commit()
        await update.message.reply_text("🗑 File deleted (if existed).")
    except sqlite3.Error as e:
        logger.error(f"Database error in delete_file: {e}")
        await update.message.reply_text("⚠️ An error occurred while deleting the file.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ You are not allowed to use this command.")
    try:
        cursor.execute("SELECT COUNT(*) FROM files")
        total_files = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        await update.message.reply_text(
            f"📊 *Bot Stats:*\n\n👥 Users: {total_users}\n📂 Files: {total_files}",
            parse_mode="Markdown"
        )
    except sqlite3.Error as e:
        logger.error(f"Database error in stats: {e}")
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
