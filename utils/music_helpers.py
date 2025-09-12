import discord
import yt_dlp
import asyncio
import os
import re
from concurrent.futures import ThreadPoolExecutor
from utils.constants import DOWNLOADS_DIR, PROGRESS_BAR_LENGTH, PROGRESS_BAR_FILLED, PROGRESS_BAR_EMPTY

# Globaler ThreadPoolExecutor für Downloads
download_executor = ThreadPoolExecutor(max_workers=2)

def create_progress_bar(current_time, total_time):
    progress = min(current_time / total_time, 1)
    filled_length = int(PROGRESS_BAR_LENGTH * progress)
    bar = ''.join([PROGRESS_BAR_FILLED if i < filled_length else PROGRESS_BAR_EMPTY for i in range(PROGRESS_BAR_LENGTH)])
    return f"[{bar}] {progress:.0%}"

def format_duration(duration):
    minutes, seconds = divmod(int(duration), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

def clean_youtube_url(url):
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if video_id_match:
        video_id = video_id_match.group(1)
        return f"https://www.youtube.com/watch?v={video_id}"
    return url

async def search_youtube(ctx, query, logger):
    ydl_opts = {
        'format': 'bestaudio/best',
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'quiet': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.debug(f"Extrahiere Informationen für: {query}")
            info = await asyncio.get_event_loop().run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            
            if 'entries' in info:
                logger.debug("Playlist erkannt")
                if info['entries']:
                    video = info['entries'][0]
                else:
                    logger.error("Leere Playlist")
                    return None
            elif '_type' in info and info['_type'] == 'url':
                logger.debug("Einzelnes Video erkannt, extrahiere erneut")
                info = await asyncio.get_event_loop().run_in_executor(None, lambda: ydl.extract_info(info['url'], download=False))
                video = info
            elif 'formats' in info:
                logger.debug("Einzelnes Video erkannt")
                video = info
            else:
                logger.error("Unerwartetes Format der extrahierten Informationen")
                return None

            if 'webpage_url' not in video or 'title' not in video:
                logger.error("Erforderliche Informationen konnten nicht extrahiert werden")
                logger.debug(f"Verfügbare Schlüssel: {video.keys()}")
                return None

            logger.debug(f"Erfolgreich extrahiert: {video['title']}")
            
            # Handle both Context and Interaction objects
            requester = ctx.author if hasattr(ctx, 'author') else ctx.user
            
            return Song(
                video['webpage_url'],
                video['title'],
                video.get('duration', 0),
                requester,
                video.get('thumbnail', '') if isinstance(video.get('thumbnail', ''), str) else '',
                None
            )
    except Exception as e:
        logger.error(f"Fehler beim Suchen auf YouTube: {str(e)}")
        return None

async def download_audio(ctx, song, logger):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': f'{DOWNLOADS_DIR}/%(title)s.%(ext)s',
        'verbose': True,
    }
    
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.debug(f"Starte Download für URL: {song.url}")
            info = await loop.run_in_executor(download_executor, lambda: ydl.extract_info(song.url, download=True))
            filename = ydl.prepare_filename(info)
            final_filename = filename.rsplit(".", 1)[0] + ".mp3"
            logger.debug(f"Download abgeschlossen. Datei: {final_filename}")
            
            if not os.path.exists(final_filename):
                logger.error(f"Die heruntergeladene Datei wurde nicht gefunden: {final_filename}")
                return None
            
            song.file_path = final_filename
            return song
    except Exception as e:
        logger.error(f"Fehler beim Herunterladen von {song.title}: {str(e)}")
        return None

async def create_now_playing_embed(music_cog):
    if not music_cog.current_song:
        return discord.Embed(title="Kein Song wird derzeit abgespielt", color=discord.Color.red())

    embed = discord.Embed(title="Jetzt läuft", color=discord.Color.blue())
    embed.add_field(name="**Titel**", value=music_cog.current_song.title, inline=False)
    embed.add_field(name="**Angefordert von**", value=music_cog.current_song.requester.name, inline=True)
    embed.add_field(name="**Dauer**", value=format_duration(music_cog.current_song.duration), inline=True)
    embed.add_field(name="**Lautstärke**", value=f"{int(music_cog.volume * 100)}%", inline=True)
    
    current_time = music_cog.get_current_time()
    total_time = format_duration(music_cog.current_song.duration)
    embed.add_field(name="**Zeit**", value=f"{current_time} / {total_time}", inline=True)
    
    progress_bar = music_cog.create_progress_bar()
    embed.add_field(name="**Fortschritt**", value=progress_bar, inline=False)
    
    if music_cog.current_song.thumbnail:
        embed.set_thumbnail(url=music_cog.current_song.thumbnail)
    
    next_songs = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(music_cog.queue_manager.get_upcoming_songs(10))])
    if next_songs:
        embed.add_field(name="**Nächste Songs**", value=next_songs, inline=False)
    else:
        embed.add_field(name="**Nächste Songs**", value="Keine weiteren Songs in der Warteschlange", inline=False)
    
    embed.add_field(name="**Wiederholungsmodus**", value="Aktiviert" if music_cog.repeat_mode else "Deaktiviert", inline=True)
    
    return embed

class Song:
    def __init__(self, url, title, duration, requester, thumbnail, file_path):
        self.url = url
        self.title = title
        self.duration = duration
        self.requester = requester
        self.thumbnail = thumbnail
        self.file_path = file_path
        self.start_time = None

