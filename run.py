from telegram.ext import Application
import logging
import os
from dotenv import load_dotenv
from bot import setup_handlers
from database import init_db

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Start the bot"""
    # Initialize database
    init_db()
    
    # Create Telegram Bot Application
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # Setup bot handlers
    setup_handlers(application)

    # Start the Bot
    logger.info("🤖 Starting Telegram Bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
