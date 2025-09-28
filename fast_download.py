import asyncio
import yt_dlp
import os
import logging
import random
import subprocess
import sys
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

class FastDownloader:
    def __init__(self):
        # Simple yt-dlp options without complex configurations
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'outtmpl': '%(title).100s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'keep_fragments': False,
            'forceipv4': True,
            'extract_flat': False,
        }
    
    def _get_simple_headers(self):
        """Get simple headers"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    
    async def _update_yt_dlp(self):
        """Force update yt-dlp"""
        try:
            logger.info("🔄 Updating yt-dlp...")
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp', '--no-cache-dir'
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                logger.info("✅ yt-dlp updated successfully")
            else:
                logger.warning(f"yt-dlp update failed: {result.stderr}")
        except Exception as e:
            logger.warning(f"Could not update yt-dlp: {e}")
    
    async def _try_direct_download(self, url, media_type, quality=None):
        """Try direct download without extraction first"""
        try:
            opts = self.ydl_opts.copy()
            
            if media_type == 'audio':
                opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': quality or '192',
                    }],
                })
            else:  # video
                opts.update({
                    'format': quality or 'best[height<=720]/best[height<=480]/best',
                })
            
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    # Try direct download without pre-extraction
                    try:
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info)
                        
                        # Find the actual file
                        if media_type == 'audio':
                            base_name = os.path.splitext(filename)[0]
                            mp3_file = f"{base_name}.mp3"
                            if os.path.exists(mp3_file):
                                return mp3_file, info
                        
                        if os.path.exists(filename):
                            return filename, info
                        
                        # Search for file
                        base_name = os.path.splitext(filename)[0]
                        for file in os.listdir('.'):
                            if file.startswith(base_name) and not file.endswith('.part'):
                                return file, info
                        
                        return None, None
                        
                    except Exception as e:
                        logger.error(f"Direct download failed: {e}")
                        return None, None
            
            loop = asyncio.get_event_loop()
            file_path, info = await loop.run_in_executor(None, sync_download)
            
            if file_path and info:
                return {
                    'success': True,
                    'file_path': file_path,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'resolution': info.get('resolution', 'Unknown') if media_type == 'video' else '192kbps',
                    'video_id': info.get('id', '')
                }
            return {'success': False, 'error': 'Direct download failed'}
            
        except Exception as e:
            logger.error(f"Direct download error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _try_alternative_methods(self, url, media_type, quality=None):
        """Try alternative download methods"""
        methods = [
            self._try_with_simple_opts,
            self._try_with_best_format,
            self._try_with_worst_format,  # Sometimes lower quality works better
        ]
        
        for method in methods:
            try:
                result = await method(url, media_type, quality)
                if result['success']:
                    logger.info(f"✅ Success with method: {method.__name__}")
                    return result
            except Exception as e:
                logger.warning(f"Method {method.__name__} failed: {e}")
                continue
        
        return {'success': False, 'error': 'All alternative methods failed'}
    
    async def _try_with_simple_opts(self, url, media_type, quality=None):
        """Try with simplest possible options"""
        opts = {
            'quiet': True,
            'no_warnings': False,
            'ignoreerrors': True,
            'forceipv4': True,
            'outtmpl': '%(title).50s.%(ext)s',
        }
        
        if media_type == 'audio':
            opts['format'] = 'bestaudio'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        else:
            opts['format'] = 'worst[height>=360]'  # Try lower quality first
        
        return await self._download_with_opts(url, opts, media_type)
    
    async def _try_with_best_format(self, url, media_type, quality=None):
        """Try with best format"""
        opts = self.ydl_opts.copy()
        
        if media_type == 'audio':
            opts['format'] = 'bestaudio'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        else:
            opts['format'] = 'best[height<=480]'  # Medium quality
        
        return await self._download_with_opts(url, opts, media_type)
    
    async def _try_with_worst_format(self, url, media_type, quality=None):
        """Try with worst format (sometimes works better)"""
        opts = self.ydl_opts.copy()
        
        if media_type == 'audio':
            opts['format'] = 'worstaudio'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        else:
            opts['format'] = 'worst[height>=240]'
        
        return await self._download_with_opts(url, opts, media_type)
    
    async def _download_with_opts(self, url, opts, media_type):
        """Download with given options"""
        try:
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    
                    if os.path.exists(filename):
                        return filename, info
                    
                    # Search for file
                    base_name = os.path.splitext(filename)[0]
                    for file in os.listdir('.'):
                        if file.startswith(base_name) and not file.endswith('.part'):
                            return file, info
                    
                    return None, None
            
            loop = asyncio.get_event_loop()
            file_path, info = await loop.run_in_executor(None, sync_download)
            
            if file_path and info:
                return {
                    'success': True,
                    'file_path': file_path,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'resolution': info.get('resolution', 'Unknown') if media_type == 'video' else '192kbps',
                    'video_id': info.get('id', '')
                }
            return {'success': False, 'error': 'Download failed'}
            
        except Exception as e:
            logger.error(f"Download with opts error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def download_audio(self, url, quality='192'):
        """Download audio with multiple fallback methods"""
        try:
            await self._update_yt_dlp()
            
            # Try direct download first
            result = await self._try_direct_download(url, 'audio', quality)
            if result['success']:
                return result
            
            # Try alternative methods
            result = await self._try_alternative_methods(url, 'audio', quality)
            if result['success']:
                return result
            
            return {'success': False, 'error': 'All audio download methods failed'}
            
        except Exception as e:
            logger.error(f"Audio download error for {url}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def download_video(self, url, quality='best[height<=720]'):
        """Download video with multiple fallback methods"""
        try:
            await self._update_yt_dlp()
            
            # Try direct download first
            result = await self._try_direct_download(url, 'video', quality)
            if result['success']:
                return result
            
            # Try alternative methods
            result = await self._try_alternative_methods(url, 'video', quality)
            if result['success']:
                return result
            
            return {'success': False, 'error': 'All video download methods failed'}
            
        except Exception as e:
            logger.error(f"Video download error for {url}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def cleanup_file(self, file_path):
        """Cleanup downloaded file"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

# Global instance
downloader = FastDownloader()
