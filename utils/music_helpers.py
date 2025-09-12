import discord
import yt_dlp
import asyncio
import os
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from config.settings import settings
from utils.exceptions import AudioDownloadError, InvalidTimeFormatError
from utils.logger import get_logger

logger = get_logger('music_helpers')

# Globaler ThreadPoolExecutor für Downloads
download_executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_downloads)

@dataclass
class Song:
    """Enhanced Song class with better type safety and validation."""
    url: str
    title: str
    duration: int
    requester: discord.Member
    thumbnail: str = ""
    file_path: Optional[str] = None
    start_time: Optional[float] = None
    added_at: datetime = field(default_factory=datetime.now)
    download_progress: float = 0.0
    
    @property
    def formatted_duration(self) -> str:
        """Get formatted duration string."""
        return format_duration(self.duration)
    
    @property
    def is_downloaded(self) -> bool:
        """Check if song is downloaded and file exists."""
        return self.file_path and Path(self.file_path).exists()
    
    def cleanup(self):
        """Clean up downloaded file."""
        if self.file_path and Path(self.file_path).exists():
            try:
                Path(self.file_path).unlink()
                logger.debug(f"Cleaned up file: {self.file_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup file {self.file_path}: {e}")

def create_progress_bar(current_time: float, total_time: float) -> str:
    """Create a visual progress bar."""
    if total_time <= 0:
        return f"[{settings.progress_bar_empty * settings.progress_bar_length}] 0%"
    
    progress = min(current_time / total_time, 1.0)
    filled_length = int(settings.progress_bar_length * progress)
    bar = ''.join([
        settings.progress_bar_filled if i < filled_length 
        else settings.progress_bar_empty 
        for i in range(settings.progress_bar_length)
    ])
    return f"[{bar}] {progress:.0%}"

def format_duration(duration: int) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    if duration <= 0:
        return "0:00"
    
    minutes, seconds = divmod(int(duration), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

def parse_time_input(time_input: str) -> int:
    """Parse time input in various formats to seconds."""
    time_input = time_input.strip()
    
    # Handle MM:SS or HH:MM:SS format
    if ':' in time_input:
        parts = time_input.split(':')
        try:
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            else:
                raise InvalidTimeFormatError(f"Invalid time format: {time_input}")
        except ValueError:
            raise InvalidTimeFormatError(f"Invalid time format: {time_input}")
    
    # Handle seconds only
    try:
        return int(time_input)
    except ValueError:
        raise InvalidTimeFormatError(f"Invalid time format: {time_input}")

def clean_youtube_url(url: str) -> str:
    """Clean and normalize YouTube URL."""
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if video_id_match:
        video_id = video_id_match.group(1)
        return f"https://www.youtube.com/watch?v={video_id}"
    return url

def get_ydl_opts(download: bool = False) -> Dict[str, Any]:
    """Get yt-dlp options based on operation type."""
    base_opts = {
        'quiet': True,
        'no_warnings': True,
        'extractaudio': True,
        'audioformat': 'mp3',
        'audioquality': '192',
        'socket_timeout': 30,
        'retries': 3,
    }
    
    if download:
        base_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': str(Path(settings.downloads_dir) / '%(title)s.%(ext)s'),
        })
    else:
        base_opts.update({
            'format': 'bestaudio/best',
            'extract_flat': 'in_playlist',
            'skip_download': True,
        })
    
    return base_opts

async def search_youtube(ctx, query: str) -> Optional[Song]:
    """Search YouTube and return Song object."""
    ydl_opts = get_ydl_opts(download=False)
    
    try:
        loop = asyncio.get_event_loop()
        
        def extract_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(query, download=False)
        
        # Use asyncio.wait_for for timeout
        info = await asyncio.wait_for(
            loop.run_in_executor(download_executor, extract_info),
            timeout=30.0
        )
        
        # Handle different response types
        video = None
        if 'entries' in info and info['entries']:
            video = info['entries'][0]
        elif '_type' in info and info['_type'] == 'url':
            # Re-extract for single video
            info = await asyncio.wait_for(
                loop.run_in_executor(download_executor, lambda: extract_info()),
                timeout=30.0
            )
            video = info
        elif 'formats' in info:
            video = info
        
        if not video or 'webpage_url' not in video or 'title' not in video:
            logger.error("Required information could not be extracted")
            return None
        
        # Validate duration
        duration = video.get('duration', 0)
        if duration > settings.max_song_duration:
            logger.warning(f"Song too long: {duration}s > {settings.max_song_duration}s")
            return None
        
        # Handle both Context and Interaction objects
        requester = ctx.author if hasattr(ctx, 'author') else ctx.user
        
        return Song(
            url=video['webpage_url'],
            title=video['title'][:100],  # Limit title length
            duration=duration,
            requester=requester,
            thumbnail=video.get('thumbnail', '') if isinstance(video.get('thumbnail'), str) else ''
        )
        
    except asyncio.TimeoutError:
        logger.error(f"Timeout while searching for: {query}")
        return None
    except Exception as e:
        logger.error(f"Error searching YouTube for '{query}': {e}")
        return None

async def extract_playlist(ctx, playlist_url: str) -> List[Song]:
    """Extract all songs from a YouTube playlist."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
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
            return []
        
        songs = []
        requester = ctx.author if hasattr(ctx, 'author') else ctx.user
        
        for entry in info['entries'][:settings.max_queue_size]:  # Limit playlist size
            if entry and 'url' in entry:
                song = Song(
                    url=entry['url'],
                    title=entry.get('title', 'Unknown Title')[:100],
                    duration=entry.get('duration', 0),
                    requester=requester,
                    thumbnail=entry.get('thumbnail', '')
                )
                
                # Skip songs that are too long
                if song.duration <= settings.max_song_duration:
                    songs.append(song)
        
        return songs
        
    except Exception as e:
        logger.error(f"Error extracting playlist: {e}")
        return []

async def download_audio(song: Song, progress_callback=None) -> Optional[Song]:
    """Download audio for a song with progress tracking."""
    if song.is_downloaded:
        return song
    
    ydl_opts = get_ydl_opts(download=True)
    
    # Add progress hook if callback provided
    if progress_callback:
        def progress_hook(d):
            if d['status'] == 'downloading':
                if 'total_bytes' in d and 'downloaded_bytes' in d:
                    progress = d['downloaded_bytes'] / d['total_bytes']
                    progress_callback(progress)
        
        ydl_opts['progress_hooks'] = [progress_hook]
    
    try:
        loop = asyncio.get_event_loop()
        
        def download_func():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(song.url, download=True)
                
                # Get the actual file path
                if 'filepath' in info:
                    return info['filepath']
                else:
                    # Fallback for older yt-dlp versions
                    filename = ydl.prepare_filename(info)
                    return filename.rsplit(".", 1)[0] + ".mp3"
        
        logger.debug(f"Starting download for: {song.title}")
        start_time = time.time()
        
        final_filename = await asyncio.wait_for(
            loop.run_in_executor(download_executor, download_func),
            timeout=settings.download_timeout
        )
        
        download_time = time.time() - start_time
        logger.info(f"Download completed in {download_time:.2f}s: {song.title}")
        
        if not Path(final_filename).exists():
            raise AudioDownloadError(f"Downloaded file not found: {final_filename}")
        
        song.file_path = final_filename
        song.download_progress = 1.0
        return song
        
    except asyncio.TimeoutError:
        logger.error(f"Download timeout for: {song.title}")
        raise AudioDownloadError(f"Download timeout: {song.title}")
    except Exception as e:
        logger.error(f"Download failed for '{song.title}': {e}")
        raise AudioDownloadError(f"Download failed: {e}")

async def create_now_playing_embed(music_cog):
    """Create enhanced now playing embed with more information."""
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
        description=f"**{song.title}**",
        color=discord.Color.blue(),
        url=song.url
    )
    
    # Basic info
    embed.add_field(
        name="👤 Angefordert von", 
        value=song.requester.display_name, 
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
    
    # Time and progress
    current_time = music_cog.get_current_time()
    embed.add_field(
        name="⏰ Zeit", 
        value=f"{current_time} / {song.formatted_duration}", 
        inline=True
    )
    
    progress_bar = music_cog.create_progress_bar()
    embed.add_field(
        name="📊 Fortschritt", 
        value=f"`{progress_bar}`", 
        inline=False
    )
    
    # Queue info
    queue_size = len(music_cog.queue_manager.queue)
    if queue_size > 0:
        next_songs = music_cog.queue_manager.get_upcoming_songs(5)
        next_list = "\n".join([
            f"`{i+1}.` {song.title[:50]}{'...' if len(song.title) > 50 else ''}"
            for i, song in enumerate(next_songs)
        ])
        embed.add_field(
            name=f"📋 Warteschlange ({queue_size} Songs)",
            value=next_list or "Leer",
            inline=False
        )
    
    # Settings
    settings_text = []
    if music_cog.repeat_mode:
        settings_text.append("🔁 Wiederholen")
    if music_cog.is_paused():
        settings_text.append("⏸️ Pausiert")
    
    if settings_text:
        embed.add_field(
            name="⚙️ Status",
            value=" • ".join(settings_text),
            inline=True
        )
    
    # Thumbnail
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    
    # Footer with timestamp
    embed.set_footer(
        text=f"Hinzugefügt am {song.added_at.strftime('%H:%M:%S')}",
        icon_url=song.requester.display_avatar.url
    )
    
    return embed

