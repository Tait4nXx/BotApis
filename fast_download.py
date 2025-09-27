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
        # Enhanced yt-dlp options to avoid detection
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            'ignoreerrors': False,
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
            
            # Enhanced extractor configuration
            'extractor_retries': 5,
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_client': ['android', 'web'],
                    'player_skip': ['config', 'webpage'],
                }
            },
            
            # Enhanced HTTP headers with rotation
            'http_headers': self._get_random_headers(),
            
            # Throttling to avoid rate limits
            'ratelimit': 1048576,  # 1 MB/s limit
            'throttledratelimit': 524288,
            
            # Force specific extractors
            'force_generic_extractor': False,
            'allowed_extractors': ['.*youtube.*'],
            
            # Bypass age restrictions and other blocks
            'age_limit': 0,
            'ignore_no_formats_error': True,
        }
    
    def _get_random_headers(self):
        """Get random headers to avoid detection"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        ]
        
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
        }
    
    def _get_enhanced_ytdl_options(self, media_type='audio'):
        """Get enhanced options for specific media type"""
        opts = self.ydl_opts.copy()
        
        # Add format selection based on media type
        if media_type == 'audio':
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                # Audio-specific extractor args
                'extractor_args': {
                    'youtube': {
                        'skip': ['dash', 'hls'],
                        'player_client': ['android', 'web'],
                        'player_skip': ['config', 'webpage'],
                        'extract_flat': False,
                    }
                },
            })
        else:  # video
            opts.update({
                'format': 'best[height<=720]/best[height<=480]/best',
                # Video-specific extractor args
                'extractor_args': {
                    'youtube': {
                        'skip': ['dash', 'hls'],
                        'player_client': ['android', 'web'],
                        'player_skip': ['config', 'webpage'],
                        'extract_flat': False,
                    }
                },
            })
        
        return opts
    
    async def _extract_info_with_fallback(self, url, opts):
        """Extract video info with multiple fallback methods"""
        methods = [
            self._extract_normal,
            self._extract_embed,
            self._extract_no_player,
        ]
        
        for method in methods:
            try:
                result = await method(url, opts)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Extraction method {method.__name__} failed: {e}")
                continue
        
        raise Exception("All extraction methods failed")
    
    async def _extract_normal(self, url, opts):
        """Normal extraction method"""
        def sync_extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_extract)
    
    async def _extract_embed(self, url, opts):
        """Extract using embed URL"""
        if 'youtube.com/watch?v=' in url:
            video_id = url.split('v=')[1].split('&')[0]
            embed_url = f'https://www.youtube.com/embed/{video_id}'
            
            def sync_extract():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(embed_url, download=False)
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, sync_extract)
        return None
    
    async def _extract_no_player(self, url, opts):
        """Extract without player response"""
        opts_no_player = opts.copy()
        opts_no_player.update({
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_client': [],
                    'player_skip': ['config', 'webpage', 'js'],
                    'extract_flat': True,
                }
            }
        })
        
        def sync_extract():
            with yt_dlp.YoutubeDL(opts_no_player) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_extract)
    
    async def download_audio(self, url, quality='192'):
        """Download audio with enhanced error handling"""
        try:
            opts = self._get_enhanced_ytdl_options('audio')
            
            # First extract info to verify availability
            info = await self._extract_info_with_fallback(url, opts)
            
            if not info:
                return {'success': False, 'error': 'Failed to extract video information'}
            
            # Now download with enhanced options
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    download_info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(download_info)
                    
                    # For audio, find the converted mp3 file
                    base_name = os.path.splitext(filename)[0]
                    mp3_file = f"{base_name}.mp3"
                    
                    # Check various possible file locations
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
    
    async def download_video(self, url, quality='best[height<=720]'):
        """Download video with enhanced error handling"""
        try:
            opts = self._get_enhanced_ytdl_options('video')
            opts['format'] = quality
            
            # First extract info to verify availability
            info = await self._extract_info_with_fallback(url, opts)
            
            if not info:
                return {'success': False, 'error': 'Failed to extract video information'}
            
            # Now download with enhanced options
            def sync_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    download_info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(download_info)
                    
                    # Check if file exists
                    if not os.path.exists(filename):
                        # Try to find the actual file
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
