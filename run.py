#!/usr/bin/env python3
"""
Run this file to start both Telegram Bot and API Server
"""

import threading
import logging
from main import main as bot_main
from api_server import app as api_app
import os
from dotenv import load_dotenv
import time

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_api():
    """Run API server"""
    host = os.getenv('API_SERVER_HOST', '0.0.0.0')
    port = int(os.getenv('API_SERVER_PORT', 3000))
    
    # Wait a moment to ensure bot initialization is complete
    time.sleep(2)
    
    try:
        api_app.run(host=host, port=port, debug=False, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            logger.error(f"❌ Port {port} is already in use. Please stop the other program or use a different port.")
        else:
            logger.error(f"❌ API server error: {e}")

if __name__ == "__main__":
    logger.info("🚀 Starting TaitanX System...")
    
    # Start API server in background thread
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    
    # Start Telegram bot (main thread)
    try:
        bot_main()
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down TaitanX System...")
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
