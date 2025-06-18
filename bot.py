import os
import json
import threading
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import instaloader
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TOKEN = os.getenv('BOT_TOKEN')
ADMINS = os.getenv('ADMINS', '').split(',')
STATS_FILE = "bot_stats.json"

# Initialize stats
bot_stats = {
    "total_users": 0,
    "active_users": set(),
    "total_downloads": 0
}

# Helper functions
def load_stats():
    global bot_stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                data = json.load(f)
                bot_stats.update({
                    "total_users": data.get("total_users", 0),
                    "active_users": set(data.get("active_users", [])),
                    "total_downloads": data.get("total_downloads", 0)
                })
    except Exception as e:
        print(f"Stats loading error: {e}")

def save_stats():
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump({
                "total_users": bot_stats["total_users"],
                "active_users": list(bot_stats["active_users"]),
                "total_downloads": bot_stats["total_downloads"]
            }, f)
    except Exception as e:
        print(f"Stats saving error: {e}")

def update_user_stats(user_id):
    user_id = str(user_id)
    if user_id not in bot_stats["active_users"]:
        bot_stats["active_users"].add(user_id)
        bot_stats["total_users"] = len(bot_stats["active_users"])
        threading.Thread(target=save_stats).start()

def is_admin(user_id):
    return str(user_id) in ADMINS

# Command handlers
async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    update_user_stats(user.id)

    message = (
        f"👋 Assalomu alaykum {user.first_name}!\n\n"
        "Instagram video linkini yuboring, men yuklab beraman.\n\n"
        f"📊 Bot statistikasi:\n"
        f"• Foydalanuvchilar: {bot_stats['total_users']}\n"
        f"• Yuklab olishlar: {bot_stats['total_downloads']}"
    )
    await update.message.reply_text(message)

async def stats(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    update_user_stats(user.id)
    await update.message.reply_text(
        f"📊 Bot statistikasi:\n"
        f"• Jami foydalanuvchilar: {bot_stats['total_users']}\n"
        f"• Yuklab olishlar: {bot_stats['total_downloads']}"
    )

async def admin_stats(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat adminlar uchun!")
        return

    await update.message.reply_text(
        f"👑 Admin statistikasi:\n"
        f"• Faol foydalanuvchilar: {len(bot_stats['active_users'])}\n"
        f"• Jami yuklab olishlar: {bot_stats['total_downloads']}\n\n"
        f"📢 Xabar yuborish: /broadcast <xabar>"
    )

async def broadcast(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Bu buyruq faqat adminlar uchun!")
        return

    if not context.args:
        await update.message.reply_text("❌ Iltimos xabar matnini kiriting!\nMasalan: /broadcast Salom do'stlar!")
        return

    message = " ".join(context.args)
    total_users = len(bot_stats['active_users'])
    await update.message.reply_text(f"📢 Xabar {total_users} foydalanuvchiga yuborilmoqda...")

    success = 0
    failed = 0

    for user_id in bot_stats["active_users"]:
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=f"📢 Yangilik:\n\n{message}\n\n👉 @{context.bot.username}"
            )
            success += 1
            time.sleep(0.3)  # Rate limit
        except Exception as e:
            print(f"Xabar yuborishda xatolik ({user_id}): {e}")
            failed += 1

    await update.message.reply_text(
        f"✅ Xabar yuborish yakunlandi!\n"
        f"• Muvaffaqiyatli: {success}\n"
        f"• Muvaffaqiyatsiz: {failed}"
    )

async def handle_instagram(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    update_user_stats(user.id)
    message_text = update.message.text

    if 'instagram.com' not in message_text:
        await update.message.reply_text("⚠️ Iltimos Instagram video linkini yuboring!")
        return

    await update.message.reply_text("📥 Video yuklanmoqda, iltimos kuting...")

    try:
        L = instaloader.Instaloader()
        shortcode = message_text.split('/')[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        folder_name = f"{post.owner_username}_{post.shortcode}"

        L.download_post(post, target=folder_name)

        for file in os.listdir(folder_name):
            if file.endswith('.mp4'):
                video_path = os.path.join(folder_name, file)
                with open(video_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption="✅ Video muvaffaqiyatli yuklab olindi!\n\nYana video yuklab olish uchun link yuboring."
                    )

                bot_stats["total_downloads"] += 1
                threading.Thread(target=save_stats).start()
                break

        # Cleanup
        for file in os.listdir(folder_name):
            os.remove(os.path.join(folder_name, file))
        os.rmdir(folder_name)

    except instaloader.exceptions.InstaloaderException as e:
        await update.message.reply_text("❌ Instagramdan video yuklab olishda xatolik. Linkni tekshiring!")
    except Exception as e:
        await update.message.reply_text(f"❌ Kutilmagan xatolik: {str(e)}")

def main() -> None:
    # Load stats
    load_stats()
    print(f"🤖 Bot ishga tushirilmoqda... | Foydalanuvchilar: {bot_stats['total_users']} | Yuklab olishlar: {bot_stats['total_downloads']}")

    # Create application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("admin", admin_stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_instagram))

    # Start polling
    print("✅ Bot muvaffaqiyatli ishga tushirildi!")
    application.run_polling()

if __name__ == '__main__':
    main()
