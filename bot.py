from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters
from telegram import Update, Bot
from database import UserManager, KeyManager, RequestLogger
import logging
import os
import random
import string
from datetime import datetime

logger = logging.getLogger(__name__)

# Admin IDs
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "1362133845,6972508083").split(",")]
LOG_GROUP = os.getenv("LOG_GROUP", "@TaitanXKeys")

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def generate_taitan_key():
    """Generate random key in format Taitan{Random}"""
    # Generate 12 random characters (uppercase letters and digits)
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    return f"Taitan{random_part}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! 👋\n\n"
        "Welcome to TaitanX Audio/Video Downloader Bot! 🎵🎬\n\n"
        "Use /key to generate your API key\n"
        "Use /help to see all commands"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """
🤖 **TaitanX Bot Commands:**

**For Users:**
/start - Start the bot
/help - Show this help message
/key - Generate your API key (Valid 7 days, 200 daily requests)

**For Admins:**
/showallkey - Show all API keys
/stats - Show bot statistics
/broadcast - Broadcast message to all users
/deletekey <key> - Delete specific API key

**API Usage:**
- Audio: `http://94.177.164.89:3000/audio?url=YOUTUBE_URL&api_key=YOUR_KEY`
- Video: `http://94.177.164.89:3000/video?url=YOUTUBE_URL&api_key=YOUR_KEY`

📊 **Rate Limits:**
- New users: 200 requests/day
- Keys valid for 7 days
- Success responses only count

Join @TaitanXKeys for updates!
    """
    await update.message.reply_text(help_text)

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate API key for user"""
    user = update.effective_user
    user_id = user.id
    
    # Add user to database
    UserManager.add_user({
        "user_id": user_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_bot": user.is_bot
    })
    
    # Check if user already has active keys
    existing_keys = KeyManager.get_user_keys(user_id)
    active_keys = [k for k in existing_keys if k.get("is_active", True)]
    
    if active_keys:
        key_list = "\n".join([f"`{k['key']}`" for k in active_keys[:3]])  # Show only first 3 keys
        await update.message.reply_text(
            f"🔑 You already have active API keys:\n\n{key_list}\n\n"
            f"💡 Each key is valid for 7 days with 200 daily requests.\n"
            f"📊 Success responses only count toward your limit.",
            parse_mode='Markdown'
        )
        return
    
    # Generate new key automatically
    is_admin_user = is_admin(user_id)
    api_key = generate_taitan_key()
    
    # Save the generated key to database
    KeyManager.add_key({
        "key": api_key,
        "user_id": user_id,
        "is_admin": is_admin_user,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "expires_at": None if is_admin_user else datetime.utcnow().timestamp() + (7 * 24 * 60 * 60),
        "total_requests": 0,
        "daily_requests": 0,
        "last_reset": datetime.utcnow()
    })
    
    # Prepare message
    if is_admin_user:
        validity = "Lifetime ⭐ (Admin)"
        requests = "Unlimited"
    else:
        validity = "7 days"
        requests = "200 per day"
    
    key_message = (
        f"🎉 **Your API Key has been generated!**\n\n"
        f"🔑 **Key:** `{api_key}`\n"
        f"⏰ **Validity:** {validity}\n"
        f"📊 **Requests:** {requests}\n"
        f"✅ **Success responses only count**\n\n"
        f"🌐 **API Endpoints:**\n"
        f"• Audio: `http://94.177.164.89:3000/audio?url=URL&api_key={api_key}`\n"
        f"• Video: `http://94.177.164.89:3000/video?url=URL&api_key={api_key}`\n\n"
        f"📝 **Usage Examples:**\n"
        f"• By URL: `...url=https://youtu.be/VIDEO_ID`\n"
        f"• By ID: `...url=VIDEO_ID`\n"
        f"• By Name: `...name=SONG_NAME`\n\n"
        f"⚠️ **Keep this key secure!**\n"
        f"📣 Join {LOG_GROUP} for updates"
    )
    
    await update.message.reply_text(key_message, parse_mode='Markdown')
    
    # Notify log group
    try:
        bot = context.bot
        admin_status = "👑 Admin" if is_admin_user else "👤 User"
        log_message = (
            f"🔑 **New API Key Generated**\n\n"
            f"**User:** {user.first_name} ({user.id})\n"
            f"**Username:** @{user.username}\n"
            f"**Status:** {admin_status}\n"
            f"**Key:** `{api_key}`\n"
            f"**Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        await bot.send_message(chat_id=LOG_GROUP, text=log_message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Failed to send log message: {e}")

async def showallkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all API keys (Admin only)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only!")
        return
    
    all_keys = KeyManager.get_all_keys()
    
    if not all_keys:
        await update.message.reply_text("📭 No API keys found!")
        return
    
    key_list = []
    for key in all_keys:
        user_info = UserManager.get_user(key["user_id"])
        username = f"@{user_info['username']}" if user_info and user_info.get('username') else "No username"
        status = "🟢 Active" if key.get("is_active", True) else "🔴 Inactive"
        admin_flag = " 👑" if key.get("is_admin") else ""
        expires = key.get("expires_at", "Never")
        if expires and expires != "Never":
            if hasattr(expires, 'strftime'):
                expires = expires.strftime("%Y-%m-%d")
            else:
                expires = str(expires)
        
        key_list.append(
            f"🔑 `{key['key']}`\n"
            f"👤 {username} ({key['user_id']}){admin_flag}\n"
            f"📊 Used: {key.get('total_requests', 0)} times\n"
            f"⏰ Expires: {expires}\n"
            f"Status: {status}\n"
        )
    
    message = "🔐 **All API Keys:**\n\n" + "\n".join(key_list)
    
    # Split message if too long
    if len(message) > 4096:
        parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
        for part in parts:
            await update.message.reply_text(part, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics (Admin only)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only!")
        return
    
    stats = RequestLogger.get_daily_stats()
    total_users = UserManager.get_user_count()
    total_keys = len(KeyManager.get_all_keys())
    
    stats_message = (
        f"📊 **Bot Statistics**\n\n"
        f"👥 **Total Users:** {total_users}\n"
        f"🔑 **Total Keys:** {total_keys}\n"
        f"📈 **Today's Stats:**\n"
        f"   • Total Requests: {stats['total_requests']}\n"
        f"   • Successful: {stats['successful_requests']}\n"
        f"   • Unique Users: {stats['unique_users']}\n\n"
        f"⏰ Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
    
    await update.message.reply_text(stats_message, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users (Admin only)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    users = UserManager.get_all_users()
    successful = 0
    failed = 0
    
    broadcast_msg = await update.message.reply_text("📢 Starting broadcast...")
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["user_id"],
                text=f"📢 **Broadcast Message from TaitanX:**\n\n{message}"
            )
            successful += 1
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {user['user_id']}: {e}")
        
        # Update progress every 10 sends
        if (successful + failed) % 10 == 0:
            await broadcast_msg.edit_text(
                f"📢 Broadcasting...\n"
                f"✅ Successful: {successful}\n"
                f"❌ Failed: {failed}\n"
                f"📊 Progress: {successful + failed}/{len(users)}"
            )
    
    await broadcast_msg.edit_text(
        f"✅ **Broadcast Completed!**\n\n"
        f"✅ Successful: {successful}\n"
        f"❌ Failed: {failed}\n"
        f"📊 Total: {len(users)} users"
    )

async def deletekey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete specific API key (Admin only)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /deletekey <api_key>")
        return
    
    key_to_delete = context.args[0]
    
    if KeyManager.delete_key(key_to_delete):
        await update.message.reply_text(f"✅ API key `{key_to_delete}` deleted successfully!", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ API key not found!")

def setup_handlers(application):
    """Setup all bot handlers"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("key", key_command))
    application.add_handler(CommandHandler("showallkey", showallkey_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("deletekey", deletekey_command))
