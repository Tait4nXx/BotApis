import asyncio
import yt_dlp
import os
import aiohttp
import aiofiles
from datetime import datetime
import logging
import random
import json
import subprocess
import sys

logger = logging.getLogger(__name__)

class FastDownloader:
    def __init__(self):
        # Enhanced yt-dlp options without cookies
        self.ydl_opts = {
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'outtmpl': '%(title).100s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'keep_fragments': False,
            'buffersize': 16 * 1024 * 1024,
            'http_chunk_size': 16 * 1024 * 1024,
            'continuedl': True,
            
            # Force IPV4 to avoid connection issues
            'forceipv4': True,
            
            # Bypass restrictions
            'age_limit': 0,
            'ignore_no_formats_error': True,
            'extract_flat': False,
            
            # Modern extractor args
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web'],
                    'player_skip': ['webpage'],
                    'skip': ['dash', 'hls'],
                }
            },
            
            # Modern HTTP headers
            'http_headers': self._get_modern_headers(),
        }
    
    def _get_modern_headers(self):
        """Get modern headers for 2024"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        ]
        
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'DNT': '1',
            'Sec-GPC': '1',
        }
    
    def _get_mobile_headers(self):
        """Get mobile headers"""
        return {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'X-Requested-With': 'com.google.android.youtube',
        }
    
    def _get_enhanced_ytdl_options(self, media_type='audio'):
        """Get enhanced options for specific media type"""
        opts = self.ydl_opts.copy()
        
        if media_type == 'audio':
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:  # video
            opts.update({
                'format': 'best[height<=720]/best[height<=480]/best',
            })
        
        return opts
    
    async def _extract_info_with_fallback(self, url, opts):
        """Enhanced extraction with multiple fallback methods"""
        methods = [
            self._extract_simple,
            self._extract_with_mobile_headers,
            self._extract_with_embed,
        ]
        
        last_error = None
        for method in methods:
            try:
                logger.info(f"Trying extraction method: {method.__name__}")
                result = await method(url, opts)
                if result and result.get('formats'):
                    logger.info(f"Success with method: {method.__name__}")
                    return result
            except Exception as e:
                last_error = e
                logger.warning(f"Method {method.__name__} failed: {e}")
                continue
        
        # Final fallback: try with minimal options
        try:
            return await self._extract_minimal(url)
        except Exception as e:
            last_error = e
        
        raise Exception(f"All extraction methods failed. Last error: {last_error}")
    
    async def _extract_simple(self, url, opts):
        """Simple extraction without complex options"""
        simple_opts = {
            'quiet': True,
            'no_warnings': False,
            'ignoreerrors': True,
            'forceipv4': True,
            'extract_flat': False,
            'http_headers': self._get_modern_headers(),
        }
        
        def sync_extract():
            with yt_dlp.YoutubeDL(simple_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_extract)
    
    async def _extract_with_mobile_headers(self, url, opts):
        """Extract using mobile headers"""
        mobile_opts = opts.copy()
        mobile_opts.update({
            'http_headers': self._get_mobile_headers(),
        })
        
        def sync_extract():
            with yt_dlp.YoutubeDL(mobile_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_extract)
    
    async def _extract_with_embed(self, url, opts):
        """Extract using embed URL"""
        if 'youtube.com/watch?v=' in url:
            video_id = url.split('v=')[1].split('&')[0]
            embed_url = f'https://www.youtube.com/embed/{video_id}'
            
            def sync_extract():
                simple_opts = {
                    'quiet': True,
                    'no_warnings': False,
                    'ignoreerrors': True,
                    'forceipv4': True,
                }
                with yt_dlp.YoutubeDL(simple_opts) as ydl:
                    return ydl.extract_info(embed_url, download=False)
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, sync_extract)
        return None
    
    async def _extract_minimal(self, url):
        """Minimal extraction as last resort"""
        minimal_opts = {
            'quiet': True,
            'no_warnings': False,
            'ignoreerrors': True,
            'forceipv4': True,
            'extract_flat': False,
        }
        
        def sync_extract():
            with yt_dlp.YoutubeDL(minimal_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_extract)
    
    async def download_audio(self, url, quality='192'):
        """Download audio with enhanced error handling"""
        try:
            # Update yt-dlp first
            await self._update_yt_dlp()
            
            opts = self._get_enhanced_ytdl_options('audio')
            
            # Extract info first with fallback
            info = await self._extract_info_with_fallback(url, opts)
            
            if not info:
                return {'success': False, 'error': 'Failed to extract video information'}
            
            # Download with progress tracking
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    # Add progress hooks
                    ydl.add_progress_hook(self._progress_hook)
                    
                    download_info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(download_info)
                    
                    # Find the actual file
                    base_name = os.path.splitext(filename)[0]
                    mp3_file = f"{base_name}.mp3"
                    
                    possible_files = [mp3_file, filename]
                    for file in os.listdir('.'):
                        if file.startswith(base_name) and not file.endswith('.part'):
                            possible_files.append(file)
                    
                    for file_path in possible_files:
                        if os.path.exists(file_path):
                            return file_path, download_info
                    
                    raise FileNotFoundError("Downloaded file not found")
            
            loop = asyncio.get_event_loop()
            file_path, download_info = await loop.run_in_executor(None, sync_download)
            
            return {
                'success': True,
                'file_path': file_path,
                'title': download_info.get('title', 'Unknown'),
                'duration': download_info.get('duration', 0),
                'thumbnail': download_info.get('thumbnail', '')
            }
            
        except Exception as e:
            logger.error(f"Audio download error for {url}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _update_yt_dlp(self):
        """Update yt-dlp to latest version"""
        try:
            # Update yt-dlp using pip
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp', '--no-cache-dir'
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                logger.info("✅ yt-dlp updated successfully")
            else:
                logger.warning(f"yt-dlp update may have failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.warning("yt-dlp update timed out")
        except Exception as e:
            logger.warning(f"Could not update yt-dlp: {e}")
    
    def _progress_hook(self, d):
        """Progress hook for downloads"""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            logger.info(f"Download progress: {percent} at {speed}")
        elif d['status'] == 'finished':
            logger.info("Download completed, starting post-processing")
    
    async def download_video(self, url, quality='best[height<=720]'):
        """Download video with enhanced error handling"""
        try:
            # Update yt-dlp first
            await self._update_yt_dlp()
            
            opts = self._get_enhanced_ytdl_options('video')
            opts['format'] = quality
            
            # Extract info first with fallback
            info = await self._extract_info_with_fallback(url, opts)
            
            if not info:
                return {'success': False, 'error': 'Failed to extract video information'}
            
            # Download
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.add_progress_hook(self._progress_hook)
                    
                    download_info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(download_info)
                    
                    if not os.path.exists(filename):
                        base_name = os.path.splitext(filename)[0]
                        for file in os.listdir('.'):
                            if file.startswith(base_name) and not file.endswith('.part'):
                                filename = file
                                break
                        else:
                            raise FileNotFoundError("Downloaded file not found")
                    
                    return filename, download_info
            
            loop = asyncio.get_event_loop()
            file_path, download_info = await loop.run_in_executor(None, sync_download)
            
            return {
                'success': True,
                'file_path': file_path,
                'title': download_info.get('title', 'Unknown'),
                'duration': download_info.get('duration', 0),
                'thumbnail': download_info.get('thumbnail', ''),
                'resolution': download_info.get('resolution', 'Unknown')
            }
            
        except Exception as e:
            logger.error(f"Video download error for {url}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def cleanup_file(self, file_path):
        """Cleanup downloaded file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

# Global instance
downloader = FastDownloader()
