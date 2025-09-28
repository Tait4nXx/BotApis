from flask import Flask, request, jsonify
import time
import logging
from fast_download import downloader
from database import KeyManager, RequestLogger
from mongo_cache import cache_db
import asyncio
import aiohttp
from telegram import Bot
import os
import re
import json
from datetime import date, datetime
import traceback

app = Flask(__name__)

# Configuration
CREATOR = "@Tait4nXx"
TELEGRAM_CHANNEL = "https://t.me/TaitanXBots"
TELEGRAM_BOT_TOKEN = "8403153728:AAGt5oeBupRaIfmGuyJBRHe8PA8teoKzigo"
TELEGRAM_CHANNEL_ID = "@TaitanXApi"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TaitanX-API")

# Custom JSON encoder to handle date objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

app.json_encoder = CustomJSONEncoder

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    if url.startswith('ytsearch:'):
        return f"search_{hash(url)}"
    
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
        elif len(url_param) == 11:
            return f"https://youtube.com/watch?v={url_param}"
    elif name_param:
        return f"ytsearch:{name_param}"
    
    return None

async def upload_to_telegram(file_path, file_type="audio"):
    """Upload file to Telegram and get direct file URL"""
    try:
        if not file_path or not os.path.exists(file_path):
            return {'success': False, 'error': 'File not found for upload'}
            
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        if file_type == "audio":
            with open(file_path, 'rb') as file:
                message = await bot.send_audio(
                    chat_id=TELEGRAM_CHANNEL_ID,
                    audio=file,
                    caption="🎵 Downloaded via TaitanX API"
                )
                file_id = message.audio.file_id
                file_info = await bot.get_file(file_id)
                download_url = f"{TELEGRAM_FILE_API}/{file_info.file_path}"
                
                return {
                    'success': True,
                    'download_url': download_url,
                    'file_id': file_id,
                    'msg_id': message.message_id,
                    'duration': message.audio.duration
                }
        else:
            with open(file_path, 'rb') as file:
                message = await bot.send_video(
                    chat_id=TELEGRAM_CHANNEL_ID,
                    video=file,
                    caption="🎬 Downloaded via TaitanX API",
                    supports_streaming=True
                )
                file_id = message.video.file_id
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

def format_success_response(file_type, upload_result, download_result, total_api_time, download_time, upload_time, video_id):
    """Format success response according to desired format"""
    response = {
        "cached": False,
        "creator": CREATOR,
        "download_time": round(download_time, 2),
        "result": {
            "quality": download_result.get('resolution', '192kbps') if file_type == "Video" else "192kbps",
            "title": download_result.get('title', 'Unknown'),
            "url": upload_result.get('download_url', ''),
            "video_id": video_id
        },
        "status": True,
        "telegram": TELEGRAM_CHANNEL,
        "total_api_time": round(total_api_time, 2),
        "upload_time": round(upload_time, 2)
    }
    
    return response

def format_cached_response(cached_response):
    """Format cached response"""
    if cached_response:
        cached_response['cached'] = True
        cached_response['cache_timestamp'] = time.time()
        return cached_response
    return None

def format_error_response(message, file_type="Audio"):
    """Format error response"""
    return {
        "cached": False,
        "creator": CREATOR,
        "download_time": 0,
        "result": {
            "quality": "Unknown",
            "title": "",
            "url": "",
            "video_id": ""
        },
        "status": False,
        "telegram": TELEGRAM_CHANNEL,
        "total_api_time": 0,
        "upload_time": 0,
        "error": message
    }

def validate_api_key(api_key):
    """Validate API key and return key data"""
    if not api_key:
        return False, "Missing API key"
    
    is_valid, key_data = KeyManager.validate_key(api_key)
    if not is_valid:
        return False, key_data
    
    return True, key_data

@app.route('/audio', methods=['GET'])
def audio_endpoint():
    """Audio download endpoint"""
    start_time = time.time()
    
    try:
        url = request.args.get('url', '')
        name = request.args.get('name', '')
        api_key = request.args.get('api_key', '')
        
        # Validate API key
        is_valid, key_data_or_error = validate_api_key(api_key)
        if not is_valid:
            return jsonify(format_error_response(key_data_or_error, "Audio")), 401
        
        # Get YouTube URL
        youtube_url = get_youtube_url(url, name)
        if not youtube_url:
            return jsonify(format_error_response("Missing url or name parameter", "Audio")), 400
        
        video_id = extract_video_id(youtube_url)
        
        # Check cache - only cache successful responses
        if not youtube_url.startswith('ytsearch:'):
            cached_response = cache_db.get_audio_cache(video_id)
            if cached_response:
                logger.info(f"🎵 Audio cache HIT for video_id: {video_id}")
                KeyManager.increment_request(api_key)
                RequestLogger.log_request(key_data_or_error['user_id'], '/audio', success=True, cached=True)
                return jsonify(format_cached_response(cached_response))
        
        logger.info(f"🎵 Audio cache MISS for video_id: {video_id}")
        
        # Process request
        result = asyncio.run(process_audio_request(youtube_url, video_id, api_key, key_data_or_error, start_time))
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Audio endpoint error: {traceback.format_exc()}")
        return jsonify(format_error_response("Internal server error", "Audio")), 500

@app.route('/video', methods=['GET'])
def video_endpoint():
    """Video download endpoint"""
    start_time = time.time()
    
    try:
        url = request.args.get('url', '')
        name = request.args.get('name', '')
        api_key = request.args.get('api_key', '')
        
        # Validate API key
        is_valid, key_data_or_error = validate_api_key(api_key)
        if not is_valid:
            return jsonify(format_error_response(key_data_or_error, "Video")), 401
        
        # Get YouTube URL
        youtube_url = get_youtube_url(url, name)
        if not youtube_url:
            return jsonify(format_error_response("Missing url or name parameter", "Video")), 400
        
        video_id = extract_video_id(youtube_url)
        
        # Check cache - only cache successful responses
        if not youtube_url.startswith('ytsearch:'):
            cached_response = cache_db.get_video_cache(video_id)
            if cached_response:
                logger.info(f"🎬 Video cache HIT for video_id: {video_id}")
                KeyManager.increment_request(api_key)
                RequestLogger.log_request(key_data_or_error['user_id'], '/video', success=True, cached=True)
                return jsonify(format_cached_response(cached_response))
        
        logger.info(f"🎬 Video cache MISS for video_id: {video_id}")
        
        # Process request
        result = asyncio.run(process_video_request(youtube_url, video_id, api_key, key_data_or_error, start_time))
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Video endpoint error: {traceback.format_exc()}")
        return jsonify(format_error_response("Internal server error", "Video")), 500

async def process_audio_request(youtube_url, video_id, api_key, key_data, start_time):
    """Process audio download request"""
    download_start = time.time()
    try:
        # Download audio
        download_result = await downloader.download_audio(youtube_url, '192')
        download_time = time.time() - download_start
        
        if not download_result['success']:
            RequestLogger.log_request(key_data['user_id'], '/audio', success=False)
            return format_error_response(f"Download failed: {download_result['error']}", "Audio")
        
        upload_start = time.time()
        # Upload to Telegram
        upload_result = await upload_to_telegram(download_result['file_path'], "audio")
        upload_time = time.time() - upload_start
        
        # Cleanup file
        await downloader.cleanup_file(download_result['file_path'])
        
        if upload_result['success']:
            KeyManager.increment_request(api_key)
            RequestLogger.log_request(key_data['user_id'], '/audio', success=True)
            
            total_api_time = time.time() - start_time
            
            response = format_success_response(
                "Audio", 
                upload_result, 
                download_result, 
                total_api_time,
                download_time,
                upload_time,
                video_id
            )
            
            # Cache only successful responses
            if not youtube_url.startswith('ytsearch:'):
                cache_db.set_audio_cache(video_id, response)
                logger.info(f"🎵 Audio response cached for video_id: {video_id}")
            
            return response
        else:
            RequestLogger.log_request(key_data['user_id'], '/audio', success=False)
            return format_error_response(f"Upload failed: {upload_result['error']}", "Audio")
            
    except Exception as e:
        logger.error(f"Audio processing error: {traceback.format_exc()}")
        RequestLogger.log_request(key_data['user_id'], '/audio', success=False)
        return format_error_response(str(e), "Audio")

async def process_video_request(youtube_url, video_id, api_key, key_data, start_time):
    """Process video download request"""
    download_start = time.time()
    try:
        # Download video
        download_result = await downloader.download_video(youtube_url, 'best[height<=720]')
        download_time = time.time() - download_start
        
        if not download_result['success']:
            RequestLogger.log_request(key_data['user_id'], '/video', success=False)
            return format_error_response(f"Download failed: {download_result['error']}", "Video")
        
        upload_start = time.time()
        # Upload to Telegram
        upload_result = await upload_to_telegram(download_result['file_path'], "video")
        upload_time = time.time() - upload_start
        
        # Cleanup file
        await downloader.cleanup_file(download_result['file_path'])
        
        if upload_result['success']:
            KeyManager.increment_request(api_key)
            RequestLogger.log_request(key_data['user_id'], '/video', success=True)
            
            total_api_time = time.time() - start_time
            
            response = format_success_response(
                "Video", 
                upload_result, 
                download_result, 
                total_api_time,
                download_time,
                upload_time,
                video_id
            )
            
            # Cache only successful responses
            if not youtube_url.startswith('ytsearch:'):
                cache_db.set_video_cache(video_id, response)
                logger.info(f"🎬 Video response cached for video_id: {video_id}")
            
            return response
        else:
            RequestLogger.log_request(key_data['user_id'], '/video', success=False)
            return format_error_response(f"Upload failed: {upload_result['error']}", "Video")
            
    except Exception as e:
        logger.error(f"Video processing error: {traceback.format_exc()}")
        RequestLogger.log_request(key_data['user_id'], '/video', success=False)
        return format_error_response(str(e), "Video")

@app.route('/cache/clear/<video_id>', methods=['DELETE'])
def clear_cache(video_id):
    """Clear cache for specific video ID"""
    try:
        audio_deleted = cache_db.delete_audio_cache(video_id)
        video_deleted = cache_db.delete_video_cache(video_id)
        
        return jsonify({
            "success": True,
            "message": f"Cache cleared for video_id: {video_id}",
            "audio_cache_deleted": audio_deleted,
            "video_cache_deleted": video_deleted
        })
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/cache/stats', methods=['GET'])
def cache_stats():
    """Get cache statistics"""
    try:
        if cache_db.db is not None:
            audio_count = cache_db.db.audio_cache.count_documents({})
            video_count = cache_db.db.video_cache.count_documents({})
            
            return jsonify({
                "audio_cache_entries": audio_count,
                "video_cache_entries": video_count,
                "total_entries": audio_count + video_count
            })
        else:
            return jsonify({"error": "MongoDB not connected"}), 500
    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    """API information endpoint"""
    return jsonify({
        "message": "TaitanX Audio/Video Download API",
        "creator": CREATOR,
        "features": ["MongoDB Caching", "Telegram Upload", "API Key Management"],
        "endpoints": {
            "audio": "/audio?url=YOUTUBE_URL&api_key=YOUR_KEY",
            "video": "/video?url=YOUTUBE_URL&api_key=YOUR_KEY",
            "cache_clear": "/cache/clear/VIDEO_ID (DELETE)",
            "cache_stats": "/cache/stats"
        },
        "examples": {
            "by_url": f"/audio?url=https://youtu.be/VIDEO_ID&api_key=KEY",
            "by_id": f"/audio?url=VIDEO_ID&api_key=KEY",
            "by_name": f"/audio?name=SONG_NAME&api_key=KEY"
        },
        "telegram": TELEGRAM_CHANNEL,
        "caching": {
            "enabled": True,
            "ttl_hours": 24,
            "separate_caches": ["audio", "video"]
        }
    })

if __name__ == '__main__':
    from database import init_db
    init_db()
    
    host = os.getenv('API_SERVER_HOST', '0.0.0.0')
    port = int(os.getenv('API_SERVER_PORT', 3000))
    
    logger.info(f"🚀 TaitanX API Server starting on {host}:{port}")
    app.run(host=host, port=port, debug=False)
