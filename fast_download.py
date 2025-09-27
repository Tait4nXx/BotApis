import asyncio
import yt_dlp
import os
import aiohttp
import aiofiles
from datetime import datetime
import logging
import random

logger = logging.getLogger(__name__)

class FastDownloader:
    def __init__(self):
        # Get a random user agent
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            'nocheckcertificate': True,
            'outtmpl': '%(title).100s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'continuedl': True,
            'http_chunk_size': 10485760,  # 10MB chunks
            'buffersize': 65536,
            'extractaudio': True,
            'audioformat': 'mp3',
            'prefer_ffmpeg': True,
            'keepvideo': False,
            # Bypass restrictions
            'ignoreerrors': True,
            'no_overwrites': True,
            'forceip': 4,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'geo_bypass_ip_block': '0.0.0.0/0',
            # Throttle to avoid detection
            'ratelimit': 1048576,  # 1 MB/s
            'throttledratelimit': 524288,
            # Custom headers
            'http_headers': {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
        }
    
    async def download_audio(self, url, quality='192'):
        """Download audio with specified quality"""
        try:
            opts = self.ydl_opts.copy()
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }],
                'http_headers': {
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                }
            })
            
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    # Try to extract info first
                    info = ydl.extract_info(url, download=False)
                    
                    # Now download
                    ydl.download([url])
                    
                    # Get the actual filename
                    filename = ydl.prepare_filename(info)
                    base_name = os.path.splitext(filename)[0]
                    mp3_file = f"{base_name}.mp3"
                    
                    # Check if file exists
                    if not os.path.exists(mp3_file):
                        # Try with different extension
                        possible_extensions = ['.mp3', '.m4a', '.webm']
                        for ext in possible_extensions:
                            if os.path.exists(f"{base_name}{ext}"):
                                mp3_file = f"{base_name}{ext}"
                                break
                    
                    return mp3_file, info
            
            loop = asyncio.get_event_loop()
            file_path, info = await loop.run_in_executor(None, sync_download)
            
            if not os.path.exists(file_path):
                raise Exception("Downloaded file not found")
            
            return {
                'success': True,
                'file_path': file_path,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', '')
            }
            
        except Exception as e:
            logger.error(f"Audio download error: {e}")
            # Try alternative method
            return await self.download_audio_alternative(url, quality)
    
    async def download_audio_alternative(self, url, quality='192'):
        """Alternative audio download method"""
        try:
            opts = self.ydl_opts.copy()
            opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }],
                'http_headers': {
                    'User-Agent': random.choice(self.user_agents),
                }
            })
            
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
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
            logger.error(f"Alternative audio download also failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def download_video(self, url, quality='best[height<=720]'):
        """Download video with specified quality"""
        try:
            opts = self.ydl_opts.copy()
            opts.update({
                'format': quality,
                'http_headers': {
                    'User-Agent': random.choice(self.user_agents),
                }
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
            return await self.download_video_alternative(url, quality)
    
    async def download_video_alternative(self, url, quality='best[height<=720]'):
        """Alternative video download method"""
        try:
            # Try simpler format selection
            opts = self.ydl_opts.copy()
            opts.update({
                'format': 'mp4[height<=720]',
                'http_headers': {
                    'User-Agent': random.choice(self.user_agents),
                }
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
            logger.error(f"Alternative video download also failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def cleanup_file(self, file_path):
        """Cleanup downloaded file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error for {file_path}: {e}")

# Global instance
downloader = FastDownloader()
