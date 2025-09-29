import logging
import os
import json
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from flask import Flask, Response

# ================= CONFIG =================
TOKEN = "7433667530:AAHTYaW6Y76lfX5wN3q8ht7Zvp6-wCurObk"
BOT_USERNAME = "freeefilebot"
DEV_URL = "https://t.me/hiden_25"
CHANNEL_URL = "https://t.me/freeotpss"
OWNER_ID = 7761576669
CHANNEL_ID = -1003033705024

DATA_FILE = "data.json"

# ================ LOGGER ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# ================ JSON STORAGE =================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "files": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ================ HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()

    # Add user if not exists
    if str(user.id) not in data["users"]:
        data["users"][str(user.id)] = {"files": [], "username": user.username}
        save_data(data)

    if context.args:
        file_key = context.args[0]
        if file_key in data["files"]:
            file_doc = data["files"][file_key]
            file_doc["downloads"] += 1
            save_data(data)
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
        "➡️ Send me any file and I will give you a sharable link.",
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
    data = load_data()

    data["files"][file_key] = {
        "file_id": file_id,
        "user_id": user.id,
        "downloads": 0
    }
    if str(user.id) not in data["users"]:
        data["users"][str(user.id)] = {"files": [], "username": user.username}
    data["users"][str(user.id)]["files"].append(file_key)

    save_data(data)

    link = f"https://t.me/{BOT_USERNAME}?start={file_key}"
    await update.message.reply_text(f"✅ File stored!\n🔗 Link: {link}")

    # 🔹 Admin ke liye Channel me Share Option
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
    keyboard = [[InlineKeyboardButton("📂 Download File", url=link)]]
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
    data = load_data()

    files = data["users"].get(str(user.id), {}).get("files", [])
    if not files:
        return await update.message.reply_text("📂 You have no uploaded files.")

    msg = "📁 *Your Files:*\n\n"
    for key in files:
        link = f"https://t.me/{BOT_USERNAME}?start={key}"
        msg += f"🔗 {link}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if len(context.args) < 1:
        return await update.message.reply_text("⚠️ Usage: /delete <file_key>")
    file_key = context.args[0]

    data = load_data()
    if file_key in data["files"] and data["files"][file_key]["user_id"] == user.id:
        del data["files"][file_key]
        if file_key in data["users"].get(str(user.id), {}).get("files", []):
            data["users"][str(user.id)]["files"].remove(file_key)
        save_data(data)
        await update.message.reply_text("🗑 File deleted successfully.")
    else:
        await update.message.reply_text("❌ File not found or you don't own it.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ You are not allowed to use this command.")

    data = load_data()
    total_files = len(data["files"])
    total_users = len(data["users"])

    await update.message.reply_text(
        f"📊 *Bot Stats:*\n\n👥 Users: {total_users}\n📂 Files: {total_files}",
        parse_mode="Markdown"
    )

# 🔹 Broadcast Command (Admin only)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ You are not allowed to use this command.")
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /broadcast <message>")

    message = " ".join(context.args)
    data = load_data()
    users = data["users"].keys()

    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=message)
            count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {uid}: {e}")

    await update.message.reply_text(f"📢 Broadcast sent to {count} users.")

# 🔹 Export Users.json (Admin only)
async def export_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ You are not allowed to use this command.")

    data = load_data()
    export_file = "users.json"
    with open(export_file, "w") as f:
        json.dump(data["users"], f, indent=4)

    await update.message.reply_document(document=InputFile(export_file), filename="users.json")

# Flask health check
@app.route('/health')
def health():
    return Response("OK", status=200)

@app.route("/")
def root():
    logger.info("Root endpoint requested")
    return Response("OK", status=200)

# ================ MAIN =================
def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
    application.add_handler(CommandHandler("myfiles", myfiles))
    application.add_handler(CommandHandler("delete", delete_file))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("exportusers", export_users))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, caption_handler))

    logger.info("Starting bot with polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    import threading
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True)
    flask_thread.start()

    main()
