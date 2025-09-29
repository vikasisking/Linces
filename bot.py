import logging
import os
import sqlite3
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from flask import Flask, request, Response

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN", "7727135902:AAEINRfdD1rkV_78apIyMNqfWDwGyerM8xQ")
BOT_USERNAME = "freeefilebot"
DEV_URL = "https://t.me/hiden_25"
CHANNEL_URL = "https://t.me/freeotpss"
OWNER_ID = 7761576669
CHANNEL_ID = -1003033705024

DB_PATH = "filebot.db"

# ================ LOGGER ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# ================ DB INIT =================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS files (
    key TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    user_id INTEGER,
    downloads INTEGER DEFAULT 0
);
""")
conn.commit()

# ================ HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user.id,))
    conn.commit()

    if context.args:
        file_key = context.args[0]
        cur.execute("SELECT file_id FROM files WHERE key=?", (file_key,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE files SET downloads = downloads + 1 WHERE key=?", (file_key,))
            conn.commit()
            await update.message.reply_document(row[0])
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
    cur.execute(
        "INSERT OR REPLACE INTO files (key, file_id, user_id, downloads) VALUES (?, ?, ?, COALESCE((SELECT downloads FROM files WHERE key=?),0))",
        (file_key, file_id, user.id, file_key)
    )
    conn.commit()

    link = f"https://t.me/{BOT_USERNAME}?start={file_key}"
    await update.message.reply_text(f"✅ File stored!\n🔗 Link: {link}")

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cur.execute("SELECT key FROM files WHERE user_id=?", (user.id,))
    rows = cur.fetchall()
    if not rows:
        return await update.message.reply_text("📂 You have no uploaded files.")
    msg = "📁 *Your Files:*\n\n"
    for (key,) in rows:
        link = f"https://t.me/{BOT_USERNAME}?start={key}"
        msg += f"🔗 {link}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if len(context.args) < 1:
        return await update.message.reply_text("⚠️ Usage: /delete <file_key>")
    file_key = context.args[0]
    cur.execute("DELETE FROM files WHERE key=? AND user_id=?", (file_key, user.id))
    conn.commit()
    await update.message.reply_text("🗑 File deleted (if existed).")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ You are not allowed to use this command.")
    cur.execute("SELECT COUNT(*) FROM files")
    total_files = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
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
    import asyncio
    async def set_webhook():
        await application.bot.set_webhook(f"{os.getenv('RENDER_EXTERNAL_URL')}/{TOKEN}")
        logger.info("Webhook set!")

    asyncio.get_event_loop().run_until_complete(set_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
