from flask import Flask, request, jsonify
import time
import logging
from fast_download import downloader
from database import KeyManager, RequestLogger
import asyncio
import aiohttp
from telegram import Bot
import os
import re

app = Flask(__name__)

# Configuration
CREATOR = "@Tait4nXx"
TELEGRAM_CHANNEL = "https://t.me/TaitanXBots"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TaitanX-API")

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    if url.startswith('ytsearch:'):
        return "search_result"
    
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return "unknown"

def get_youtube_url(url_param, name_param):
    """Convert parameters to YouTube URL"""
    if url_param:
        if 'youtube.com' in url_param or 'youtu.be' in url_param:
            return url_param
        elif len(url_param) == 11:  # Video ID
            return f"https://youtube.com/watch?v={url_param}"
    elif name_param:
        # Search for video by name
        return f"ytsearch:{name_param}"
    
    return None

async def upload_to_telegram(file_path, file_type="audio"):
    """Upload file to Telegram and get download URL"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
        
        if not bot_token or not channel_id:
            return {'success': False, 'error': 'Telegram configuration missing'}
        
        bot = Bot(token=bot_token)
        
        # Check if file exists and has reasonable size
        if not os.path.exists(file_path):
            return {'success': False, 'error': 'File not found after download'}
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return {'success': False, 'error': 'File is empty'}
        
        # Telegram has 50MB file size limit for bots
        if file_size > 50 * 1024 * 1024:
            return {'success': False, 'error': 'File too large for Telegram'}
        
        if file_type == "audio":
            with open(file_path, 'rb') as file:
                message = await bot.send_audio(
                    chat_id=channel_id,
                    audio=file,
                    caption="🎵 Downloaded via TaitanX API"
                )
                file_id = message.audio.file_id
        else:  # video
            with open(file_path, 'rb') as file:
                message = await bot.send_video(
                    chat_id=channel_id,
                    video=file,
                    caption="🎬 Downloaded via TaitanX API",
                    supports_streaming=True
                )
                file_id = message.video.file_id
        
        # Get file URL
        file_info = await bot.get_file(file_id)
        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_info.file_path}"
        
        return {
            'success': True,
            'download_url': download_url,
            'file_id': file_id
        }
            
    except Exception as e:
        logger.error(f"Telegram upload error: {e}")
        return {'success': False, 'error': str(e)}

def format_error_response(message, file_type="Audio"):
    """Format error response"""
    # Remove ANSI color codes from error messages
    import re
    message = re.sub(r'\x1b\[[0-9;]*m', '', message)
    
    return {
        "cached": False,
        "creator": CREATOR,
        "download_time": 0,
        "result": {
            "type": file_type,
            "quality": "0kbps" if file_type == "Audio" else "0p",
            "url": "",
            "video_id": "",
            "title": ""
        },
        "status": False,
        "telegram": TELEGRAM_CHANNEL,
        "total_api_time": 0,
        "upload_time": 0,
        "error": message
    }

@app.route('/audio', methods=['GET'])
def audio_endpoint():
    """Audio download endpoint"""
    start_time = time.time()
    
    try:
        # Get parameters
        url = request.args.get('url', '')
        name = request.args.get('name', '')
        api_key = request.args.get('api_key', '')
        
        # Validate API key
        if not api_key:
            return jsonify(format_error_response("Missing api_key parameter", "Audio")), 400
        
        is_valid, key_data = KeyManager.validate_key(api_key)
        if not is_valid:
            return jsonify(format_error_response(key_data, "Audio")), 401
        
        # Get YouTube URL
        youtube_url = get_youtube_url(url, name)
        if not youtube_url:
            return jsonify(format_error_response("Missing url or name parameter", "Audio")), 400
        
        logger.info(f"Processing audio request for: {youtube_url}")
        
        # Process request asynchronously
        result = asyncio.run(process_audio_request(youtube_url, api_key, start_time))
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Audio endpoint error: {e}")
        return jsonify(format_error_response("Internal server error", "Audio")), 500

@app.route('/video', methods=['GET'])
def video_endpoint():
    """Video download endpoint"""
    start_time = time.time()
    
    try:
        # Get parameters
        url = request.args.get('url', '')
        name = request.args.get('name', '')
        api_key = request.args.get('api_key', '')
        
        # Validate API key
        if not api_key:
            return jsonify(format_error_response("Missing api_key parameter", "Video")), 400
        
        is_valid, key_data = KeyManager.validate_key(api_key)
        if not is_valid:
            return jsonify(format_error_response(key_data, "Video")), 401
        
        # Get YouTube URL
        youtube_url = get_youtube_url(url, name)
        if not youtube_url:
            return jsonify(format_error_response("Missing url or name parameter", "Video")), 400
        
        logger.info(f"Processing video request for: {youtube_url}")
        
        # Process request asynchronously
        result = asyncio.run(process_video_request(youtube_url, api_key, start_time))
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Video endpoint error: {e}")
        return jsonify(format_error_response("Internal server error", "Video")), 500

async def process_audio_request(youtube_url, api_key, start_time):
    """Process audio download request"""
    download_start = time.time()
    
    try:
        # Download audio
        download_result = await downloader.download_audio(youtube_url, '192')
        
        if not download_result['success']:
            user_id = KeyManager.validate_key(api_key)[1]['user_id']
            RequestLogger.log_request(user_id, '/audio', success=False)
            return format_error_response(download_result['error'], "Audio")
        
        download_time = time.time() - download_start
        
        # Upload to Telegram
        upload_start = time.time()
        upload_result = await upload_to_telegram(download_result['file_path'], "audio")
        upload_time = time.time() - upload_start
        
        # Cleanup file
        await downloader.cleanup_file(download_result['file_path'])
        
        if upload_result['success']:
            # Increment request counter only on success
            KeyManager.increment_request(api_key)
            user_id = KeyManager.validate_key(api_key)[1]['user_id']
            RequestLogger.log_request(user_id, '/audio', success=True)
            
            total_time = time.time() - start_time
            
            return {
                "cached": False,
                "creator": CREATOR,
                "download_time": round(download_time, 2),
                "result": {
                    "type": "Audio",
                    "quality": "192kbps",
                    "url": upload_result['download_url'],
                    "video_id": extract_video_id(youtube_url),
                    "title": download_result.get('title', 'Unknown')
                },
                "status": True,
                "telegram": TELEGRAM_CHANNEL,
                "total_api_time": round(total_time, 2),
                "upload_time": round(upload_time, 2)
            }
        else:
            user_id = KeyManager.validate_key(api_key)[1]['user_id']
            RequestLogger.log_request(user_id, '/audio', success=False)
            return format_error_response(upload_result['error'], "Audio")
            
    except Exception as e:
        logger.error(f"Audio processing error: {e}")
        user_id = KeyManager.validate_key(api_key)[1]['user_id']
        RequestLogger.log_request(user_id, '/audio', success=False)
        return format_error_response(str(e), "Audio")

async def process_video_request(youtube_url, api_key, start_time):
    """Process video download request"""
    download_start = time.time()
    
    try:
        # Download video (720p max for faster processing)
        download_result = await downloader.download_video(youtube_url, 'best[height<=720]')
        
        if not download_result['success']:
            user_id = KeyManager.validate_key(api_key)[1]['user_id']
            RequestLogger.log_request(user_id, '/video', success=False)
            return format_error_response(download_result['error'], "Video")
        
        download_time = time.time() - download_start
        
        # Upload to Telegram
        upload_start = time.time()
        upload_result = await upload_to_telegram(download_result['file_path'], "video")
        upload_time = time.time() - upload_start
        
        # Cleanup file
        await downloader.cleanup_file(download_result['file_path'])
        
        if upload_result['success']:
            # Increment request counter only on success
            KeyManager.increment_request(api_key)
            user_id = KeyManager.validate_key(api_key)[1]['user_id']
            RequestLogger.log_request(user_id, '/video', success=True)
            
            total_time = time.time() - start_time
            
            return {
                "cached": False,
                "creator": CREATOR,
                "download_time": round(download_time, 2),
                "result": {
                    "type": "Video",
                    "quality": download_result.get('resolution', '720p'),
                    "url": upload_result['download_url'],
                    "video_id": extract_video_id(youtube_url),
                    "title": download_result.get('title', 'Unknown'),
                    "duration": download_result.get('duration', 0)
                },
                "status": True,
                "telegram": TELEGRAM_CHANNEL,
                "total_api_time": round(total_time, 2),
                "upload_time": round(upload_time, 2)
            }
        else:
            user_id = KeyManager.validate_key(api_key)[1]['user_id']
            RequestLogger.log_request(user_id, '/video', success=False)
            return format_error_response(upload_result['error'], "Video")
            
    except Exception as e:
        logger.error(f"Video processing error: {e}")
        user_id = KeyManager.validate_key(api_key)[1]['user_id']
        RequestLogger.log_request(user_id, '/video', success=False)
        return format_error_response(str(e), "Video")

@app.route('/')
def index():
    """API information endpoint"""
    return jsonify({
        "message": "TaitanX Audio/Video Download API",
        "creator": CREATOR,
        "endpoints": {
            "audio": "/audio?url=YOUTUBE_URL&api_key=YOUR_KEY",
            "video": "/video?url=YOUTUBE_URL&api_key=YOUR_KEY"
        },
        "examples": {
            "by_url": "http://94.177.164.89:3000/audio?url=https://youtu.be/VIDEO_ID&api_key=KEY",
            "by_id": "http://94.177.164.89:3000/audio?url=VIDEO_ID&api_key=KEY",
            "by_name": "http://94.177.164.89:3000/audio?name=SONG_NAME&api_key=KEY"
        }
    })

if __name__ == '__main__':
    from database import init_db
    init_db()
    
    host = os.getenv('API_SERVER_HOST', '0.0.0.0')
    port = int(os.getenv('API_SERVER_PORT', 3000))
    
    logger.info(f"🚀 TaitanX API Server starting on {host}:{port}")
    app.run(host=host, port=port, debug=False)
