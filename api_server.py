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
TELEGRAM_CHANNEL = "https://t.me/VibeBots"
TELEGRAM_BOT_TOKEN = "8403153728:AAGt5oeBupRaIfmGuyJBRHe8PA8teoKzigo"
TELEGRAM_CHANNEL_ID = "@TaitanXApi"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"

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
    """Upload file to Telegram and get direct file URL"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        async with aiohttp.ClientSession() as session:
            if file_type == "audio":
                with open(file_path, 'rb') as file:
                    message = await bot.send_audio(
                        chat_id=TELEGRAM_CHANNEL_ID,
                        audio=file,
                        caption="🎵 Downloaded via TaitanX API"
                    )
                    file_id = message.audio.file_id
                    
                    # Get file info for direct URL
                    file_info = await bot.get_file(file_id)
                    download_url = f"{TELEGRAM_FILE_API}/{file_info.file_path}"
                    
                    return {
                        'success': True,
                        'download_url': download_url,
                        'file_id': file_id,
                        'msg_id': message.message_id,
                        'duration': message.audio.duration
                    }
            else:  # video
                with open(file_path, 'rb') as file:
                    message = await bot.send_video(
                        chat_id=TELEGRAM_CHANNEL_ID,
                        video=file,
                        caption="🎬 Downloaded via TaitanX API",
                        supports_streaming=True
                    )
                    file_id = message.video.file_id
                    
                    # Get file info for direct URL
                    file_info = await bot.get_file(file_id)
                    download_url = f"{TELEGRAM_FILE_API}/{file_info.file_path}"
                    
                    return {
                        'success': True,
                        'download_url': download_url,
                        'file_id': file_id,
                        'msg_id': message.message_id,
                        'duration': message.video.duration
                    }
            
    except Exception as e:
        logger.error(f"Telegram upload error: {e}")
        return {'success': False, 'error': str(e)}

def format_duration(duration_seconds):
    """Convert seconds to ISO 8601 duration format (PT3M14S)"""
    if not duration_seconds:
        return "PT0S"
    
    hours = int(duration_seconds // 3600)
    minutes = int((duration_seconds % 3600) // 60)
    seconds = int(duration_seconds % 60)
    
    duration_str = "PT"
    if hours > 0:
        duration_str += f"{hours}H"
    if minutes > 0:
        duration_str += f"{minutes}M"
    if seconds > 0 or duration_str == "PT":
        duration_str += f"{seconds}S"
    
    return duration_str

def format_success_response(file_type, upload_result, download_result, total_time):
    """Format success response as requested"""
    duration = format_duration(upload_result.get('duration', download_result.get('duration', 0)))
    
    return {
        "creator": CREATOR,
        "result": {
            "duration": duration,
            "file_id": upload_result.get('file_id', ''),
            "quality": download_result.get('resolution', 'Unknown') if file_type == "Video" else "Unknown",
            "source": "telegram_cache",
            "telegram_msg": {
                "msg_id": upload_result.get('msg_id', 0),
                "tlink": f"https://t.me/{TELEGRAM_CHANNEL_ID.replace('@', '')}/{upload_result.get('msg_id', 0)}"
            },
            "url": upload_result.get('download_url', '')
        },
        "status": True,
        "type": file_type,
        "telegram": TELEGRAM_CHANNEL
    }

def format_error_response(message, file_type="Audio"):
    """Format error response"""
    return {
        "creator": CREATOR,
        "result": {
            "duration": "PT0S",
            "file_id": "",
            "quality": "Unknown",
            "source": "telegram_cache",
            "telegram_msg": {
                "msg_id": 0,
                "tlink": ""
            },
            "url": ""
        },
        "status": False,
        "type": file_type,
        "telegram": TELEGRAM_CHANNEL,
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
        
        # Process request asynchronously
        result = asyncio.run(process_video_request(youtube_url, api_key, start_time))
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Video endpoint error: {e}")
        return jsonify(format_error_response("Internal server error", "Video")), 500

async def process_audio_request(youtube_url, api_key, start_time):
    """Process audio download request"""
    try:
        # Download audio
        download_result = await downloader.download_audio(youtube_url, '192')
        
        if not download_result['success']:
            # Log failed request
            if KeyManager.validate_key(api_key)[0]:
                RequestLogger.log_request(KeyManager.validate_key(api_key)[1]['user_id'], '/audio', success=False)
            return format_error_response(download_result['error'], "Audio")
        
        # Upload to Telegram
        upload_result = await upload_to_telegram(download_result['file_path'], "audio")
        
        # Cleanup file immediately after upload
        await downloader.cleanup_file(download_result['file_path'])
        
        if upload_result['success']:
            # Increment request counter and log success
            KeyManager.increment_request(api_key)
            if KeyManager.validate_key(api_key)[0]:
                RequestLogger.log_request(KeyManager.validate_key(api_key)[1]['user_id'], '/audio', success=True)
            
            total_time = time.time() - start_time
            logger.info(f"Audio request completed in {total_time:.2f}s")
            
            return format_success_response("Audio", upload_result, download_result, total_time)
        else:
            # Log failed upload
            if KeyManager.validate_key(api_key)[0]:
                RequestLogger.log_request(KeyManager.validate_key(api_key)[1]['user_id'], '/audio', success=False)
            return format_error_response(upload_result['error'], "Audio")
            
    except Exception as e:
        logger.error(f"Audio processing error: {e}")
        # Log error
        if KeyManager.validate_key(api_key)[0]:
            RequestLogger.log_request(KeyManager.validate_key(api_key)[1]['user_id'], '/audio', success=False)
        return format_error_response(str(e), "Audio")

async def process_video_request(youtube_url, api_key, start_time):
    """Process video download request"""
    try:
        # Download video (720p max for faster processing)
        download_result = await downloader.download_video(youtube_url, 'best[height<=720]')
        
        if not download_result['success']:
            # Log failed request
            if KeyManager.validate_key(api_key)[0]:
                RequestLogger.log_request(KeyManager.validate_key(api_key)[1]['user_id'], '/video', success=False)
            return format_error_response(download_result['error'], "Video")
        
        # Upload to Telegram
        upload_result = await upload_to_telegram(download_result['file_path'], "video")
        
        # Cleanup file immediately after upload
        await downloader.cleanup_file(download_result['file_path'])
        
        if upload_result['success']:
            # Increment request counter and log success
            KeyManager.increment_request(api_key)
            if KeyManager.validate_key(api_key)[0]:
                RequestLogger.log_request(KeyManager.validate_key(api_key)[1]['user_id'], '/video', success=True)
            
            total_time = time.time() - start_time
            logger.info(f"Video request completed in {total_time:.2f}s")
            
            return format_success_response("Video", upload_result, download_result, total_time)
        else:
            # Log failed upload
            if KeyManager.validate_key(api_key)[0]:
                RequestLogger.log_request(KeyManager.validate_key(api_key)[1]['user_id'], '/video', success=False)
            return format_error_response(upload_result['error'], "Video")
            
    except Exception as e:
        logger.error(f"Video processing error: {e}")
        # Log error
        if KeyManager.validate_key(api_key)[0]:
            RequestLogger.log_request(KeyManager.validate_key(api_key)[1]['user_id'], '/video', success=False)
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
            "by_url": f"/audio?url=https://youtu.be/VIDEO_ID&api_key=KEY",
            "by_id": f"/audio?url=VIDEO_ID&api_key=KEY",
            "by_name": f"/audio?name=SONG_NAME&api_key=KEY"
        },
        "telegram": TELEGRAM_CHANNEL
    })

if __name__ == '__main__':
    from database import init_db
    init_db()
    
    host = os.getenv('API_SERVER_HOST', '0.0.0.0')
    port = int(os.getenv('API_SERVER_PORT', 3000))
    
    logger.info(f"🚀 TaitanX API Server starting on {host}:{port}")
    app.run(host=host, port=port, debug=False)
