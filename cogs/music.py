import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import random
from typing import Optional, List, Union
from config.settings import settings
from utils.logger import get_logger, LoggerMixin
from utils.music_helpers import search_youtube, download_audio, Song, create_now_playing_embed, clean_youtube_url, extract_playlist
from utils.ui_components import MusicControlView, QueueView, VolumeModal, JumpModal, AddYouTubeLinkModal
from utils.exceptions import *
from utils.queue_manager import QueueManager
from utils.monitoring import performance_monitor
from utils.cache import cache_manager
import time

class Music(commands.Cog, LoggerMixin):
    """Enhanced Music cog with modern Discord.py features and better architecture."""
    
    def __init__(self, bot):
        self.bot = bot
        self.queue_manager = QueueManager(settings.max_queue_size)
        self.current_song: Optional[Song] = None
        self.is_playing = False
        self.volume = settings.default_volume
        self.repeat_mode = False
        self.now_playing_message: Optional[discord.Message] = None
        self.update_task: Optional[asyncio.Task] = None
        self.seek_position = 0
        self.paused_time = 0
        self.pause_start: Optional[float] = None
        self.intro_dir = settings.intros_dir
        self.download_queue = asyncio.Queue()
        self.download_task = None
        self.auto_disconnect_task: Optional[asyncio.Task] = None
        self.last_activity = time.time()
        
        # Ensure intro directory exists
        self.intro_dir.mkdir(exist_ok=True)

    async def cog_load(self):
        """Called when the cog is loaded."""
        self.logger.info("Music cog loaded")
        await self.queue_manager.load_queue_state(self.bot)
        
        if settings.enable_slash_commands:
            await self._sync_slash_commands()

    async def cog_unload(self):
        """Called when the cog is unloaded."""
        await self.cleanup_all()
        self.logger.info("Music cog unloaded")

    async def _sync_slash_commands(self):
        """Sync slash commands if enabled."""
        try:
            synced = await self.bot.tree.sync()
            self.logger.info("Slash commands synced", count=len(synced))
        except Exception as e:
            self.logger.error("Failed to sync slash commands", error=str(e))

    # Hybrid commands (work as both prefix and slash commands)
    @commands.hybrid_command(name="play", aliases=['p'])
    @app_commands.describe(query="YouTube URL, search term, or playlist URL")
    async def play(self, ctx: commands.Context, *, query: str):
        """Play music from YouTube with enhanced features."""
        start_time = time.time()
        
        try:
            # Delete user message if it's a prefix command
            if ctx.prefix and hasattr(ctx, 'message'):
                try:
                    await ctx.message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
            
            # Defer response for slash commands
            if ctx.interaction:
                await ctx.defer()
            
            if not await self._ensure_voice_channel(ctx):
                return
            
            self._update_activity()
            cleaned_query = clean_youtube_url(query)
            
            # Check if it's a playlist
            if 'list=' in cleaned_query:
                await self._handle_playlist(ctx, cleaned_query)
            else:
                await self._handle_single_song(ctx, cleaned_query)
            
            self.log_command(ctx, 'play', query=query[:50])
            performance_monitor.record_command('play', time.time() - start_time, True)
            
        except Exception as e:
            error_msg = f"Fehler beim Abspielen: {str(e)}"
            self.logger.error("Play command failed", error=str(e), query=query[:50])
            performance_monitor.record_command('play', time.time() - start_time, False)
            
            if ctx.interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg, delete_after=10)

    async def _handle_single_song(self, ctx, query: str):
        """Handle single song addition."""
        song = await search_youtube(ctx, query)
        if not song:
            message = "❌ Kein passendes Video gefunden."
            if ctx.interaction:
                await ctx.followup.send(message, ephemeral=True)
            else:
                await ctx.send(message, delete_after=10)
            return

        await self.download_queue.put((song, ctx))
        
        if self.download_task is None or self.download_task.done():
            self.download_task = asyncio.create_task(self._process_download_queue())

        message = f"🎵 **{song.title}** wurde zur Warteschlange hinzugefügt."
        if ctx.interaction:
            await ctx.followup.send(message, ephemeral=True)
        else:
            await ctx.send(message, delete_after=10)

    async def _handle_playlist(self, ctx, playlist_url: str):
        """Handle playlist addition."""
        if ctx.interaction:
            await ctx.followup.send("🔄 Playlist wird verarbeitet...", ephemeral=True)
        else:
            processing_msg = await ctx.send("🔄 Playlist wird verarbeitet...")
        
        songs = await extract_playlist(ctx, playlist_url)
        if not songs:
            message = "❌ Keine Songs in der Playlist gefunden."
            if ctx.interaction:
                await ctx.edit_original_response(content=message)
            else:
                await processing_msg.edit(content=message)
            return
        
        added_count = await self.queue_manager.add_songs(songs)
        
        # Start downloads
        for song in songs[:added_count]:
            await self.download_queue.put((song, ctx))
        
        if self.download_task is None or self.download_task.done():
            self.download_task = asyncio.create_task(self._process_download_queue())
        
        message = f"📋 **{added_count}** Songs aus der Playlist hinzugefügt."
        if ctx.interaction:
            await ctx.edit_original_response(content=message)
        else:
            await processing_msg.edit(content=message)

    @commands.hybrid_command(name="skip", aliases=['s'])
    async def skip(self, ctx: commands.Context):
        """Skip the current song."""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send("❌ Es wird gerade keine Musik abgespielt.", ephemeral=True)
            return
        
        if self.current_song:
            skipped_title = self.current_song.title
            ctx.voice_client.stop()
            await ctx.send(f"⏭️ **{skipped_title}** wurde übersprungen.", ephemeral=True)
        else:
            await ctx.send("⏭️ Song übersprungen.", ephemeral=True)
        
        self._update_activity()
        self.log_command(ctx, 'skip')

    @commands.hybrid_command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Stop playback and clear the queue."""
        if ctx.voice_client:
            await self._cleanup(ctx)
            await ctx.send("⏹️ Wiedergabe gestoppt und Warteschlange geleert.", ephemeral=True)
        else:
            await ctx.send("❌ Bot ist nicht mit einem Sprachkanal verbunden.", ephemeral=True)
        
        self.log_command(ctx, 'stop')

    @commands.hybrid_command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Pause or resume playback."""
        if not ctx.voice_client:
            await ctx.send("❌ Bot ist nicht mit einem Sprachkanal verbunden.", ephemeral=True)
            return
        
        if ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            self.pause_start = time.time()
            await ctx.send("⏸️ Wiedergabe pausiert.", ephemeral=True)
        elif ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            if self.pause_start:
                self.paused_time += time.time() - self.pause_start
                self.pause_start = None
            await ctx.send("▶️ Wiedergabe fortgesetzt.", ephemeral=True)
        else:
            await ctx.send("❌ Es wird gerade keine Musik abgespielt.", ephemeral=True)
        
        self._update_activity()
        self.log_command(ctx, 'pause')

    @commands.hybrid_command(name="volume", aliases=['vol'])
    @app_commands.describe(volume="Volume level (0-100)")
    async def volume(self, ctx: commands.Context, volume: int = None):
        """Set or show the current volume."""
        if volume is None:
            current_vol = int(self.volume * 100)
            await ctx.send(f"🔊 Aktuelle Lautstärke: **{current_vol}%**", ephemeral=True)
            return
        
        if not 0 <= volume <= 100:
            await ctx.send("❌ Lautstärke muss zwischen 0 und 100 liegen.", ephemeral=True)
            return
        
        self.volume = volume / 100
        if ctx.voice_client and hasattr(ctx.voice_client, 'source') and ctx.voice_client.source:
            ctx.voice_client.source.volume = self.volume
        
        await ctx.send(f"🔊 Lautstärke auf **{volume}%** gesetzt.", ephemeral=True)
        self.log_command(ctx, 'volume', volume=volume)

    @commands.hybrid_command(name="queue", aliases=['q'])
    async def show_queue(self, ctx: commands.Context):
        """Show the current queue."""
        view = QueueView(self)
        embed = view.get_queue_embed()
        
        if ctx.interaction:
            await ctx.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.send(embed=embed, view=view)
        
        self.log_command(ctx, 'queue')

    @commands.hybrid_command(name="nowplaying", aliases=['np'])
    async def now_playing(self, ctx: commands.Context):
        """Show information about the currently playing song."""
        if not self.current_song:
            await ctx.send("❌ Es wird gerade keine Musik abgespielt.", ephemeral=True)
            return
        
        embed = await create_now_playing_embed(self)
        view = MusicControlView(self)
        
        if ctx.interaction:
            await ctx.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.send(embed=embed, view=view)
        
        self.log_command(ctx, 'nowplaying')

    @commands.hybrid_command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the queue."""
        if self.queue_manager.is_empty():
            await ctx.send("❌ Die Warteschlange ist leer.", ephemeral=True)
            return
        
        await self.queue_manager.shuffle()
        await ctx.send("🔀 Warteschlange wurde gemischt.", ephemeral=True)
        self.log_command(ctx, 'shuffle')

    @commands.hybrid_command(name="repeat")
    async def repeat(self, ctx: commands.Context):
        """Toggle repeat mode."""
        self.repeat_mode = not self.repeat_mode
        status = "aktiviert" if self.repeat_mode else "deaktiviert"
        emoji = "🔁" if self.repeat_mode else "🔁"
        await ctx.send(f"{emoji} Wiederholung **{status}**.", ephemeral=True)
        self.log_command(ctx, 'repeat', enabled=self.repeat_mode)

    @commands.hybrid_command(name="remove")
    @app_commands.describe(index="Position of the song to remove (1-based)")
    async def remove(self, ctx: commands.Context, index: int):
        """Remove a song from the queue."""
        if index < 1 or index > self.queue_manager.size():
            await ctx.send(f"❌ Ungültiger Index. Verwende 1-{self.queue_manager.size()}.", ephemeral=True)
            return
        
        removed_song = await self.queue_manager.remove_song(index - 1)
        if removed_song:
            await ctx.send(f"🗑️ **{removed_song.title}** wurde aus der Warteschlange entfernt.", ephemeral=True)
        else:
            await ctx.send("❌ Fehler beim Entfernen des Songs.", ephemeral=True)
        
        self.log_command(ctx, 'remove', index=index)

    @commands.hybrid_command(name="clear")
    async def clear_queue(self, ctx: commands.Context):
        """Clear the entire queue."""
        if self.queue_manager.is_empty():
            await ctx.send("❌ Die Warteschlange ist bereits leer.", ephemeral=True)
            return
        
        await self.queue_manager.clear()
        await ctx.send("🗑️ Warteschlange wurde geleert.", ephemeral=True)
        self.log_command(ctx, 'clear')

    # Voice channel management
    async def _ensure_voice_channel(self, ctx) -> bool:
        """Ensure bot is connected to voice channel."""
        if not ctx.author.voice:
            message = "❌ Du musst in einem Sprachkanal sein, um Musik abzuspielen."
            if ctx.interaction:
                await ctx.followup.send(message, ephemeral=True)
            else:
                await ctx.send(message, delete_after=10)
            return False

        if not ctx.voice_client:
            try:
                await ctx.author.voice.channel.connect()
                self.logger.info("Connected to voice channel", channel=ctx.author.voice.channel.name)
                await self._play_random_intro(ctx)
                
                # Start auto-disconnect timer
                if settings.enable_auto_disconnect:
                    self._start_auto_disconnect_timer(ctx)
                
                return True
            except Exception as e:
                self.logger.error("Failed to connect to voice channel", error=str(e))
                message = f"❌ Fehler beim Verbinden mit dem Sprachkanal: {str(e)}"
                if ctx.interaction:
                    await ctx.followup.send(message, ephemeral=True)
                else:
                    await ctx.send(message, delete_after=10)
                return False
        return True

    async def _play_random_intro(self, ctx):
        """Play a random intro sound."""
        try:
            intro_files = [f for f in self.intro_dir.iterdir() if f.suffix.lower() in ['.mp3', '.wav', '.ogg']]
            if not intro_files:
                self.logger.debug("No intro files found")
                return

            intro_file = random.choice(intro_files)
            
            if ctx.voice_client:
                source = discord.FFmpegPCMAudio(str(intro_file))
                ctx.voice_client.play(source)
                self.logger.info("Playing intro", file=intro_file.name)
                
                # Wait for intro to finish
                while ctx.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            self.logger.error("Failed to play intro", error=str(e))

    def _start_auto_disconnect_timer(self, ctx):
        """Start auto-disconnect timer."""
        if self.auto_disconnect_task:
            self.auto_disconnect_task.cancel()
        
        self.auto_disconnect_task = asyncio.create_task(self._auto_disconnect_check(ctx))

    async def _auto_disconnect_check(self, ctx):
        """Check for inactivity and disconnect if needed."""
        try:
            while ctx.voice_client and ctx.voice_client.is_connected():
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if time.time() - self.last_activity > settings.auto_disconnect_timeout:
                    if not self.is_playing or self.queue_manager.is_empty():
                        self.logger.info("Auto-disconnecting due to inactivity")
                        await self._cleanup(ctx)
                        break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error("Error in auto-disconnect check", error=str(e))

    def _update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()

    # Playback management
    async def _play_next(self, ctx):
        """Play the next song in the queue."""
        self.logger.debug("Playing next song")
        await self._stop_update_task()
        self.seek_position = 0
        self.paused_time = 0
        self.pause_start = None

        if self.queue_manager.is_empty() and not self.current_song:
            self.logger.info("Queue empty, cleaning up")
            await self._cleanup(ctx)
            return

        if self.queue_manager.is_empty() and self.repeat_mode and self.current_song:
            await self.queue_manager.add_song(self.current_song)

        next_song = await self.queue_manager.get_next_song()
        if next_song:
            self.current_song = next_song
            self.logger.info("Playing next song", title=next_song.title[:50])

            try:
                await asyncio.gather(
                    self._play_song(ctx),
                    self._update_now_playing(ctx),
                    self._start_update_task()
                )
                
                # Update monitoring
                performance_monitor.update_queue_size(str(ctx.guild.id), self.queue_manager.size())
                
            except Exception as e:
                self.logger.error("Failed to play song", error=str(e))
                await self._play_next(ctx)
        else:
            self.logger.info("No more songs in queue")
            await self._cleanup(ctx)

    async def _play_song(self, ctx):
        """Play the current song."""
        if not self.current_song or not self.current_song.is_downloaded:
            raise PlaybackError("Song not downloaded")
        
        try:
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(str(self.current_song.file_path)),
                volume=self.volume
            )
            
            ctx.voice_client.play(
                source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._play_next(ctx), self.bot.loop
                )
            )
            
            self.logger.info("Playback started", title=self.current_song.title[:50])
            self.is_playing = True
            self.current_song.start_time = time.time()
            self._update_activity()
            
        except Exception as e:
            self.logger.error("Failed to start playback", error=str(e))
            raise PlaybackError(f"Playback failed: {str(e)}")

    # UI and display management
    async def _start_update_task(self):
        """Start the now playing update task."""
        if self.update_task:
            self.update_task.cancel()
        self.update_task = asyncio.create_task(self._update_now_playing_periodically())

    async def _stop_update_task(self):
        """Stop the now playing update task."""
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

    async def _update_now_playing_periodically(self):
        """Periodically update the now playing message."""
        while self.is_playing and self.current_song:
            await asyncio.sleep(10)  # Update every 10 seconds
            if self.now_playing_message:
                try:
                    embed = await create_now_playing_embed(self)
                    await self.now_playing_message.edit(embed=embed, view=MusicControlView(self))
                except discord.NotFound:
                    self.now_playing_message = None
                    break
                except Exception as e:
                    self.logger.error("Failed to update now playing", error=str(e))

    async def _update_now_playing(self, ctx):
        """Update or create the now playing message."""
        channel = ctx.channel if hasattr(ctx, 'channel') else ctx.interaction.channel

        if self.now_playing_message:
            try:
                await self.now_playing_message.delete()
            except discord.NotFound:
                pass

        if not self.current_song:
            self.now_playing_message = None
            return

        embed = await create_now_playing_embed(self)
        self.now_playing_message = await channel.send(embed=embed, view=MusicControlView(self))

    # Download management
    async def _process_download_queue(self):
        """Process the download queue."""
        while True:
            try:
                song, ctx = await self.download_queue.get()
                
                try:
                    downloaded_song = await download_audio(song)
                    if downloaded_song:
                        await self.queue_manager.add_song(downloaded_song)
                        if not self.is_playing:
                            await self._play_next(ctx)
                        else:
                            await self._update_now_playing(ctx)
                except Exception as e:
                    self.logger.error("Download failed", title=song.title[:50], error=str(e))
                    # Notify user of download failure
                    try:
                        await ctx.send(f"❌ Download fehlgeschlagen: **{song.title}**", delete_after=10)
                    except:
                        pass
                finally:
                    self.download_queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in download queue processing", error=str(e))

    # Utility methods
    def get_current_time(self) -> str:
        """Get current playback time as formatted string."""
        if self.current_song and self.current_song.start_time:
            elapsed = self.get_current_time_seconds()
            return self._format_duration(elapsed)
        return "0:00"

    def get_current_time_seconds(self) -> float:
        """Get current playback time in seconds."""
        if self.current_song and self.current_song.start_time:
            current_time = time.time()
            elapsed = current_time - self.current_song.start_time - self.paused_time
            if self.pause_start:
                elapsed -= current_time - self.pause_start
            return max(0, elapsed + self.seek_position)
        return self.seek_position

    def is_paused(self) -> bool:
        """Check if playback is paused."""
        return self.pause_start is not None

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to MM:SS or HH:MM:SS."""
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    # Cleanup
    async def _cleanup(self, ctx):
        """Clean up resources and disconnect."""
        self.logger.debug("Cleaning up music cog")
        self.is_playing = False
        await self._stop_update_task()
        
        if self.auto_disconnect_task:
            self.auto_disconnect_task.cancel()
        
        self.current_song = None
        self.seek_position = 0
        self.paused_time = 0
        self.pause_start = None
        
        if self.now_playing_message:
            try:
                await self.now_playing_message.delete()
            except discord.NotFound:
                pass
        self.now_playing_message = None
        
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.logger.info("Disconnected from voice channel")
        
        # Update monitoring
        performance_monitor.update_voice_connections(0)
        performance_monitor.update_queue_size(str(ctx.guild.id), 0)

    async def cleanup_all(self):
        """Cleanup all resources."""
        await self._stop_update_task()
        if self.download_task:
            self.download_task.cancel()
        if self.auto_disconnect_task:
            self.auto_disconnect_task.cancel()
        await self.queue_manager.cleanup_all()

async def setup(bot):
    await bot.add_cog(Music(bot))