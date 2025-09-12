import discord
import yt_dlp
import asyncio
import os
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
from config.settings import settings
from utils.exceptions import AudioDownloadError, InvalidTimeFormatError, RateLimitError
from utils.logger import get_logger
from utils.cache import cache_manager
from utils.monitoring import performance_monitor

logger = get_logger('music_helpers')

# Enhanced ThreadPoolExecutor with better resource management
download_executor = ThreadPoolExecutor(
    max_workers=settings.max_concurrent_downloads,
    thread_name_prefix="yt-dlp"
)

@dataclass
class Song:
    """Enhanced Song class with comprehensive metadata and validation."""
    url: str
    title: str
    duration: int
    requester: Union[discord.Member, discord.User]
    thumbnail: str = ""
    file_path: Optional[Path] = None
    start_time: Optional[float] = None
    added_at: datetime = field(default_factory=datetime.now)
    download_progress: float = 0.0
    uploader: str = ""
    view_count: int = 0
    like_count: int = 0
    upload_date: Optional[str] = None
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate and clean data after initialization."""
        self.title = self._clean_title(self.title)
        if self.file_path:
            self.file_path = Path(self.file_path)
    
    def _clean_title(self, title: str) -> str:
        """Clean and truncate title."""
        # Remove problematic characters
        cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
        return cleaned[:100] if len(cleaned) > 100 else cleaned
    
    @property
    def formatted_duration(self) -> str:
        """Get formatted duration string."""
        return format_duration(self.duration)
    
    @property
    def is_downloaded(self) -> bool:
        """Check if song is downloaded and file exists."""
        return self.file_path and self.file_path.exists()
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in MB."""
        if self.is_downloaded:
            return self.file_path.stat().st_size / 1024 / 1024
        return 0.0
    
    @property
    def age_minutes(self) -> float:
        """Get age of song in minutes since added."""
        return (datetime.now() - self.added_at).total_seconds() / 60
    
    def cleanup(self):
        """Clean up downloaded file with error handling."""
        if self.file_path and self.file_path.exists():
            try:
                self.file_path.unlink()
                logger.debug("File cleaned up", file=str(self.file_path))
            except Exception as e:
                logger.error("Failed to cleanup file", file=str(self.file_path), error=str(e))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'url': self.url,
            'title': self.title,
            'duration': self.duration,
            'requester_id': self.requester.id,
            'thumbnail': self.thumbnail,
            'uploader': self.uploader,
            'view_count': self.view_count,
            'added_at': self.added_at.isoformat()
        }

def create_progress_bar(current_time: float, total_time: float) -> str:
    """Create an enhanced visual progress bar."""
    if total_time <= 0:
        return f"[{settings.progress_bar_empty * settings.progress_bar_length}] 0%"
    
    progress = min(current_time / total_time, 1.0)
    filled_length = int(settings.progress_bar_length * progress)
    
    bar = ''.join([
        settings.progress_bar_filled if i < filled_length 
        else settings.progress_bar_empty 
        for i in range(settings.progress_bar_length)
    ])
    
    percentage = int(progress * 100)
    return f"[{bar}] {percentage}%"

def format_duration(duration: int) -> str:
    """Enhanced duration formatting with better handling."""
    if duration <= 0:
        return "0:00"
    
    hours, remainder = divmod(int(duration), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

def format_number(number: int) -> str:
    """Format large numbers with K/M/B suffixes."""
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    elif number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    elif number >= 1_000:
        return f"{number / 1_000:.1f}K"
    else:
        return str(number)

def parse_time_input(time_input: str) -> int:
    """Enhanced time parsing with better validation."""
    time_input = time_input.strip()
    
    # Handle MM:SS or HH:MM:SS format
    if ':' in time_input:
        parts = time_input.split(':')
        try:
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                if minutes < 0 or seconds < 0 or seconds >= 60:
                    raise InvalidTimeFormatError(f"Invalid time values: {time_input}")
                return minutes * 60 + seconds
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                if any(x < 0 for x in [hours, minutes, seconds]) or minutes >= 60 or seconds >= 60:
                    raise InvalidTimeFormatError(f"Invalid time values: {time_input}")
                return hours * 3600 + minutes * 60 + seconds
            else:
                raise InvalidTimeFormatError(f"Invalid time format: {time_input}")
        except ValueError:
            raise InvalidTimeFormatError(f"Invalid time format: {time_input}")
    
    # Handle seconds only
    try:
        seconds = int(time_input)
        if seconds < 0:
            raise InvalidTimeFormatError("Time cannot be negative")
        return seconds
    except ValueError:
        raise InvalidTimeFormatError(f"Invalid time format: {time_input}")

def clean_youtube_url(url: str) -> str:
    """Enhanced URL cleaning with playlist support."""
    # Handle playlist URLs
    playlist_match = re.search(r"[&?]list=([a-zA-Z0-9_-]+)", url)
    if playlist_match:
        return url  # Return full playlist URL
    
    # Handle video URLs
    video_patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"embed\/([0-9A-Za-z_-]{11})"
    ]
    
    for pattern in video_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
    
    return url

def get_ydl_opts(download: bool = False) -> Dict[str, Any]:
    """Enhanced yt-dlp options with better error handling and performance."""
    base_opts = {
        'quiet': True,
        'no_warnings': True,
        'extractaudio': True,
        'audioformat': 'mp3',
        'audioquality': '192',
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'skip_unavailable_fragments': True,
        'ignoreerrors': False,
        'no_color': True,
        'extract_flat': False,
    }
    
    if download:
        base_opts.update({
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': str(settings.downloads_dir / '%(title)s-%(id)s.%(ext)s'),
            'writeinfojson': False,
            'writethumbnail': False,
        })
    else:
        base_opts.update({
            'format': 'bestaudio/best',
            'skip_download': True,
        })
    
    return base_opts

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def search_youtube(ctx, query: str) -> Optional[Song]:
    """Enhanced YouTube search with caching and better error handling."""
    start_time = time.time()
    
    # Check cache first
    cache_key = f"search:{hash(query)}"
    cached_result = await cache_manager.get(cache_key)
    if cached_result:
        logger.debug("Search cache hit", query=query[:50])
        # Recreate Song object with current requester
        requester = ctx.author if hasattr(ctx, 'author') else ctx.user
        cached_result['requester'] = requester
        return Song(**cached_result)
    
    ydl_opts = get_ydl_opts(download=False)
    
    try:
        loop = asyncio.get_event_loop()
        
        def extract_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(query, download=False)
        
        # Use asyncio.wait_for for timeout
        info = await asyncio.wait_for(
            loop.run_in_executor(download_executor, extract_info),
            timeout=45.0
        )
        
        # Handle different response types
        video = None
        if 'entries' in info and info['entries']:
            # Playlist or search results
            video = info['entries'][0]
            if not video:
                logger.warning("No valid entries found", query=query[:50])
                return None
        elif 'formats' in info or 'url' in info:
            # Single video
            video = info
        
        if not video or not video.get('title'):
            logger.warning("No video information extracted", query=query[:50])
            return None
        
        # Validate duration
        duration = video.get('duration', 0)
        if duration and duration > settings.max_song_duration:
            logger.warning(
                "Song too long",
                duration=duration,
                max_duration=settings.max_song_duration,
                title=video.get('title', '')[:50]
            )
            return None
        
        # Handle both Context and Interaction objects
        requester = ctx.author if hasattr(ctx, 'author') else ctx.user
        
        # Create song object with enhanced metadata
        song_data = {
            'url': video.get('webpage_url', video.get('url', query)),
            'title': video.get('title', 'Unknown Title'),
            'duration': duration or 0,
            'requester': requester,
            'thumbnail': video.get('thumbnail', ''),
            'uploader': video.get('uploader', ''),
            'view_count': video.get('view_count', 0),
            'like_count': video.get('like_count', 0),
            'upload_date': video.get('upload_date'),
            'description': video.get('description', '')[:500],  # Limit description
            'tags': video.get('tags', [])[:10]  # Limit tags
        }
        
        song = Song(**song_data)
        
        # Cache the result (without requester for reusability)
        cache_data = song_data.copy()
        del cache_data['requester']
        await cache_manager.set(cache_key, cache_data, ttl=3600)
        
        duration = time.time() - start_time
        performance_monitor.record_command('search_youtube', duration, True)
        
        logger.info(
            "YouTube search successful",
            title=song.title[:50],
            duration=song.formatted_duration,
            search_time=f"{duration:.2f}s"
        )
        
        return song
        
    except asyncio.TimeoutError:
        logger.error("Search timeout", query=query[:50])
        performance_monitor.record_command('search_youtube', time.time() - start_time, False)
        return None
    except Exception as e:
        logger.error("Search failed", query=query[:50], error=str(e))
        performance_monitor.record_command('search_youtube', time.time() - start_time, False)
        return None

async def extract_playlist(ctx, playlist_url: str) -> List[Song]:
    """Enhanced playlist extraction with better handling."""
    start_time = time.time()
    
    # Check cache first
    cache_key = f"playlist:{hash(playlist_url)}"
    cached_result = await cache_manager.get(cache_key)
    if cached_result:
        logger.debug("Playlist cache hit", url=playlist_url[:50])
        requester = ctx.author if hasattr(ctx, 'author') else ctx.user
        songs = []
        for song_data in cached_result:
            song_data['requester'] = requester
            songs.append(Song(**song_data))
        return songs
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'playlistend': settings.max_playlist_size,
    }
    
    try:
        loop = asyncio.get_event_loop()
        
        def extract_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(playlist_url, download=False)
        
        info = await asyncio.wait_for(
            loop.run_in_executor(download_executor, extract_info),
            timeout=60.0
        )
        
        if 'entries' not in info:
            logger.warning("No playlist entries found", url=playlist_url[:50])
            return []
        
        songs = []
        requester = ctx.author if hasattr(ctx, 'author') else ctx.user
        cache_data = []
        
        for entry in info['entries'][:settings.max_playlist_size]:
            if not entry or not entry.get('url'):
                continue
            
            song_data = {
                'url': entry['url'],
                'title': entry.get('title', 'Unknown Title'),
                'duration': entry.get('duration', 0),
                'requester': requester,
                'thumbnail': entry.get('thumbnail', ''),
                'uploader': entry.get('uploader', ''),
            }
            
            # Skip songs that are too long
            if song_data['duration'] > settings.max_song_duration:
                continue
            
            song = Song(**song_data)
            songs.append(song)
            
            # Prepare cache data
            cache_song_data = song_data.copy()
            del cache_song_data['requester']
            cache_data.append(cache_song_data)
        
        # Cache the playlist
        await cache_manager.set(cache_key, cache_data, ttl=1800)  # 30 minutes
        
        duration = time.time() - start_time
        logger.info(
            "Playlist extracted",
            url=playlist_url[:50],
            song_count=len(songs),
            extraction_time=f"{duration:.2f}s"
        )
        
        return songs
        
    except Exception as e:
        logger.error("Playlist extraction failed", url=playlist_url[:50], error=str(e))
        return []

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=8)
)
async def download_audio(song: Song, progress_callback=None) -> Optional[Song]:
    """Enhanced audio download with progress tracking and better error handling."""
    if song.is_downloaded:
        logger.debug("Song already downloaded", title=song.title[:50])
        return song
    
    start_time = time.time()
    ydl_opts = get_ydl_opts(download=True)
    
    # Add progress hook if callback provided
    if progress_callback:
        def progress_hook(d):
            if d['status'] == 'downloading':
                if 'total_bytes' in d and 'downloaded_bytes' in d:
                    progress = d['downloaded_bytes'] / d['total_bytes']
                    song.download_progress = progress
                    asyncio.create_task(progress_callback(progress))
                elif '_percent_str' in d:
                    # Fallback for percentage string
                    try:
                        percent_str = d['_percent_str'].strip().rstrip('%')
                        progress = float(percent_str) / 100
                        song.download_progress = progress
                        asyncio.create_task(progress_callback(progress))
                    except (ValueError, AttributeError):
                        pass
        
        ydl_opts['progress_hooks'] = [progress_hook]
    
    try:
        loop = asyncio.get_event_loop()
        
        def download_func():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(song.url, download=True)
                
                # Get the actual file path
                if 'filepath' in info:
                    return Path(info['filepath'])
                else:
                    # Fallback: construct path from template
                    filename = ydl.prepare_filename(info)
                    # Replace extension with .mp3
                    base_path = Path(filename).with_suffix('.mp3')
                    return base_path
        
        logger.info("Starting download", title=song.title[:50])
        
        final_path = await asyncio.wait_for(
            loop.run_in_executor(download_executor, download_func),
            timeout=settings.download_timeout
        )
        
        if not final_path.exists():
            raise AudioDownloadError(f"Downloaded file not found: {final_path}")
        
        song.file_path = final_path
        song.download_progress = 1.0
        
        download_time = time.time() - start_time
        file_size_mb = song.file_size_mb
        
        performance_monitor.record_download(download_time, True)
        
        logger.info(
            "Download completed",
            title=song.title[:50],
            duration=f"{download_time:.2f}s",
            file_size_mb=f"{file_size_mb:.1f}MB"
        )
        
        return song
        
    except asyncio.TimeoutError:
        error_msg = f"Download timeout after {settings.download_timeout}s: {song.title}"
        logger.error("Download timeout", title=song.title[:50], timeout=settings.download_timeout)
        performance_monitor.record_download(time.time() - start_time, False)
        raise AudioDownloadError(error_msg)
    except Exception as e:
        error_msg = f"Download failed: {str(e)}"
        logger.error("Download failed", title=song.title[:50], error=str(e))
        performance_monitor.record_download(time.time() - start_time, False)
        raise AudioDownloadError(error_msg)

async def create_now_playing_embed(music_cog) -> discord.Embed:
    """Create enhanced now playing embed with comprehensive information."""
    if not music_cog.current_song:
        embed = discord.Embed(
            title="🎵 Keine Musik",
            description="Derzeit wird kein Song abgespielt",
            color=discord.Color.red()
        )
        return embed

    song = music_cog.current_song
    embed = discord.Embed(
        title="🎵 Jetzt läuft",
        description=f"**[{song.title}]({song.url})**",
        color=discord.Color(settings.embed_color),
        timestamp=datetime.now()
    )
    
    # Basic info with enhanced formatting
    embed.add_field(
        name="👤 Angefordert von", 
        value=f"{song.requester.display_name}", 
        inline=True
    )
    embed.add_field(
        name="⏱️ Dauer", 
        value=song.formatted_duration, 
        inline=True
    )
    embed.add_field(
        name="🔊 Lautstärke", 
        value=f"{int(music_cog.volume * 100)}%", 
        inline=True
    )
    
    # Enhanced metadata
    if song.uploader:
        embed.add_field(
            name="📺 Kanal",
            value=song.uploader[:30] + ("..." if len(song.uploader) > 30 else ""),
            inline=True
        )
    
    if song.view_count > 0:
        embed.add_field(
            name="👁️ Aufrufe",
            value=format_number(song.view_count),
            inline=True
        )
    
    if song.file_size_mb > 0:
        embed.add_field(
            name="💾 Dateigröße",
            value=f"{song.file_size_mb:.1f} MB",
            inline=True
        )
    
    # Time and progress with enhanced display
    current_time = music_cog.get_current_time()
    current_seconds = music_cog.get_current_time_seconds()
    progress_bar = create_progress_bar(current_seconds, song.duration)
    
    embed.add_field(
        name="⏰ Fortschritt", 
        value=f"{current_time} / {song.formatted_duration}\n`{progress_bar}`", 
        inline=False
    )
    
    # Queue info with better formatting
    queue_size = len(music_cog.queue_manager.queue)
    if queue_size > 0:
        next_songs = music_cog.queue_manager.get_upcoming_songs(3)
        next_list = []
        for i, next_song in enumerate(next_songs, 1):
            title = next_song.title[:40] + "..." if len(next_song.title) > 40 else next_song.title
            next_list.append(f"`{i}.` **{title}** `[{next_song.formatted_duration}]`")
        
        queue_text = "\n".join(next_list)
        if queue_size > 3:
            queue_text += f"\n*... und {queue_size - 3} weitere Songs*"
        
        embed.add_field(
            name=f"📋 Warteschlange ({queue_size} Songs)",
            value=queue_text,
            inline=False
        )
    
    # Enhanced status indicators
    status_indicators = []
    if music_cog.repeat_mode:
        status_indicators.append("🔁 Wiederholen")
    if hasattr(music_cog, 'is_paused') and music_cog.is_paused():
        status_indicators.append("⏸️ Pausiert")
    if music_cog.queue_manager.size() == 0:
        status_indicators.append("🔚 Letzter Song")
    
    if status_indicators:
        embed.add_field(
            name="⚙️ Status",
            value=" • ".join(status_indicators),
            inline=False
        )
    
    # Thumbnail with fallback
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    
    # Enhanced footer
    embed.set_footer(
        text=f"Hinzugefügt vor {int(song.age_minutes)} Min • {song.requester.display_name}",
        icon_url=song.requester.display_avatar.url
    )
    
    return embed