from telegram.ext import Application
import logging
import os
from dotenv import load_dotenv
from bot import setup_handlers
from database import init_db
import threading
from api_server import app as api_app

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_api_server():
    """Run the Flask API server in a separate thread"""
    host = os.getenv('API_SERVER_HOST', '0.0.0.0')
    port = int(os.getenv('API_SERVER_PORT', 3000))
    
    logger.info(f"🚀 Starting API server on {host}:{port}")
    api_app.run(host=host, port=port, debug=False, use_reloader=False)

def main():
    """Start the bot and API server"""
    # Initialize database
    init_db()
    
    # Start API server in a separate thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    # Create Telegram Bot Application
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # Setup bot handlers
    setup_handlers(application)

    # Start the Bot
    logger.info("🤖 Starting Telegram Bot...")
    application.run_polling()

if __name__ == '__main__':
    main()