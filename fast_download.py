import asyncio
import yt_dlp
import os
import aiohttp
import aiofiles
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FastDownloader:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'outtmpl': '%(title).100s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'retries': 3,
            'buffersize': 16 * 1024 * 1024,
            'http_chunk_size': 16 * 1024 * 1024,
            'continuedl': True,
        }
    
    async def download_audio(self, url, quality='192'):
        """Download audio with specified quality"""
        try:
            opts = self.ydl_opts.copy()
            opts.update({
                'format': 'bestaudio/best',
                'extractaudio': True,
                'audioformat': 'mp3',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }],
            })
            
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    # Replace extension with .mp3
                    base_name = os.path.splitext(filename)[0]
                    return f"{base_name}.mp3", info
            
            loop = asyncio.get_event_loop()
            file_path, info = await loop.run_in_executor(None, sync_download)
            
            return {
                'success': True,
                'file_path': file_path,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', '')
            }
            
        except Exception as e:
            logger.error(f"Audio download error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def download_video(self, url, quality='best[height<=720]'):
        """Download video with specified quality"""
        try:
            opts = self.ydl_opts.copy()
            opts.update({
                'format': quality,
            })
            
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    return filename, info
            
            loop = asyncio.get_event_loop()
            file_path, info = await loop.run_in_executor(None, sync_download)
            
            return {
                'success': True,
                'file_path': file_path,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'resolution': info.get('resolution', 'Unknown')
            }
            
        except Exception as e:
            logger.error(f"Video download error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def cleanup_file(self, file_path):
        """Cleanup downloaded file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

# Global instance
downloader = FastDownloader()