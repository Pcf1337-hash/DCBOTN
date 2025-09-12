import discord
from discord.ext import commands
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import random
from typing import Optional, List
from utils.constants import DOWNLOADS_DIR, MAX_QUEUE_SIZE, DEFAULT_VOLUME
from utils.logger import setup_logger
from utils.music_helpers import search_youtube, download_audio, Song, create_progress_bar, format_duration, create_now_playing_embed, clean_youtube_url
from utils.ui_components import MusicControlView
from utils.error_handler import ErrorHandler, ErrorCategory
from utils.queue_manager import QueueManager

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue_manager = QueueManager(MAX_QUEUE_SIZE)
        self.current_song: Optional[Song] = None
        self.is_playing = False
        self.volume = DEFAULT_VOLUME
        self.repeat_mode = False
        self.now_playing_message: Optional[discord.Message] = None
        self.update_task: Optional[asyncio.Task] = None
        self.seek_position = 0
        self.paused_time = 0
        self.pause_start: Optional[float] = None
        self.logger = setup_logger('music_cog')
        self.error_handler = ErrorHandler(self.logger)
        self.intro_dir = os.path.join(os.path.dirname(__file__), "..", "intros")
        self.download_queue = asyncio.Queue()
        self.download_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f'{self.__class__.__name__} Cog has been loaded')

    async def start_update_task(self):
        self.update_task = asyncio.create_task(self.update_now_playing_periodically())

    async def stop_update_task(self):
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

    async def update_now_playing_periodically(self):
        while self.is_playing:
            await asyncio.sleep(5)
            if self.now_playing_message and self.current_song:
                try:
                    embed = await create_now_playing_embed(self)
                    await self.now_playing_message.edit(embed=embed, view=MusicControlView(self))
                except discord.errors.NotFound:
                    self.now_playing_message = None
                    break
            else:
                break

    async def cleanup_downloads(self):
        for file in os.listdir(DOWNLOADS_DIR):
            file_path = os.path.join(DOWNLOADS_DIR, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                self.logger.error(f"Fehler beim Löschen von {file_path}. Grund: {e}")

    async def play_random_intro(self, ctx):
        intro_files = [f for f in os.listdir(self.intro_dir) if f.endswith('.mp3')]
        if not intro_files:
            self.logger.warning("Keine Intro-MP3s gefunden.")
            return

        intro_file = random.choice(intro_files)
        intro_path = os.path.join(self.intro_dir, intro_file)

        if ctx.voice_client:
            ctx.voice_client.play(discord.FFmpegPCMAudio(intro_path))
            self.logger.info(f"Intro wird abgespielt: {intro_file}")
            while ctx.voice_client.is_playing():
                await asyncio.sleep(0.1)
        else:
            self.logger.error("Kein Voice Client verfügbar für Intro-Wiedergabe.")

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str):
        self.logger.info(f"Play-Befehl aufgerufen mit Query: {query}")
        
        try:
            await ctx.message.delete()
        except discord.errors.NotFound:
            pass
        except discord.errors.Forbidden:
            await self.error_handler.log_and_notify(ctx, "Keine Berechtigung zum Löschen der Nachricht")
        except Exception as e:
            await self.error_handler.log_and_notify(ctx, f"Fehler beim Löschen der Nachricht: {str(e)}")

        if not await self.ensure_voice_channel(ctx):
            return

        try:
            cleaned_query = clean_youtube_url(query)
            
            song = await search_youtube(ctx, cleaned_query, self.logger)
            if not song:
                await ctx.send("Kein passendes Video gefunden.", delete_after=10)
                return

            await self.download_queue.put((song, ctx))
            
            if self.download_task is None or self.download_task.done():
                self.download_task = asyncio.create_task(self.process_download_queue())

            await ctx.send(f"'{song.title}' wurde zur Download-Warteschlange hinzugefügt.", delete_after=10)
        except Exception as e:
            error_message = self.error_handler.handle_error(e, ErrorCategory.UNKNOWN)
            await ctx.send(f"Ein Fehler ist aufgetreten: {error_message}", delete_after=10)

    async def ensure_voice_channel(self, ctx):
        if not ctx.author.voice:
            self.logger.debug("Benutzer ist in keinem Sprachkanal.")
            return False

        if not ctx.voice_client:
            try:
                await ctx.author.voice.channel.connect()
                self.logger.debug(f"Bot hat sich mit dem Sprachkanal verbunden: {ctx.author.voice.channel.name}")
                await self.play_random_intro(ctx)
                return True
            except Exception as e:
                self.logger.error(f"Fehler beim Verbinden mit dem Sprachkanal: {str(e)}")
                return False
        return True

    async def toggle_playback(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            if interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.pause()
                self.pause_start = asyncio.get_event_loop().time()
            else:
                interaction.guild.voice_client.resume()
                if self.pause_start:
                    self.paused_time += asyncio.get_event_loop().time() - self.pause_start
                    self.pause_start = None
            await interaction.response.defer()
            await self.update_now_playing(interaction)
        else:
            await interaction.response.defer()

    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            self.is_playing = False
            await self.stop_update_task()
            await interaction.guild.voice_client.disconnect()
            self.queue_manager.clear()
            self.current_song = None
            self.paused_time = 0
            self.pause_start = None
            await self.cleanup_downloads()
            if self.now_playing_message:
                try:
                    await self.now_playing_message.delete()
                except discord.errors.NotFound:
                    pass
            self.now_playing_message = None
        await interaction.response.defer()

    async def skip(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
        await interaction.response.defer()

    async def set_volume(self, interaction: discord.Interaction, volume: int):
        if interaction.guild.voice_client is None:
            await interaction.response.defer()
            return

        if 0 <= volume <= 100:
            self.volume = volume / 100
            if interaction.guild.voice_client.source:
                interaction.guild.voice_client.source.volume = self.volume
            await self.update_now_playing(interaction)
        await interaction.response.defer()

    async def toggle_repeat(self, interaction: discord.Interaction):
        self.repeat_mode = not self.repeat_mode
        await interaction.response.defer()
        await self.update_now_playing(interaction)

    async def shuffle(self, interaction: discord.Interaction):
        self.queue_manager.shuffle()
        await self.update_now_playing(interaction)
        await interaction.response.defer()

    async def jump(self, interaction: discord.Interaction, time_input: str):
        if not self.current_song:
            await interaction.response.defer()
            return

        try:
            if ':' in time_input:
                minutes, seconds = map(int, time_input.split(':'))
                total_seconds = (minutes * 60 + seconds) // 2
            else:
                total_seconds = int(time_input) // 2

            if total_seconds < 0 or total_seconds > self.current_song.duration:
                await interaction.response.defer()
                return

            voice_client = interaction.guild.voice_client
            if voice_client:
                voice_client.pause()
                
                audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
                    self.current_song.file_path,
                    before_options=f"-ss {total_seconds}"
                ))
                
                voice_client.source = audio_source
                voice_client.source.volume = self.volume
                voice_client.resume()
                
                self.seek_position = total_seconds
                self.current_song.start_time = asyncio.get_event_loop().time() - total_seconds
                self.paused_time = 0
                self.pause_start = None
                
                await self.update_now_playing(interaction)
            await interaction.response.defer()
        except ValueError:
            await interaction.response.defer()

    async def add_youtube_link(self, interaction: discord.Interaction, url: str):
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("Der Bot ist nicht mit einem Sprachkanal verbunden.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
        
            cleaned_url = clean_youtube_url(url)
            song = await search_youtube(interaction, cleaned_url, self.logger)
            if not song:
                await interaction.followup.send("Kein passendes Video gefunden.", ephemeral=True)
                return

            await self.download_queue.put((song, interaction))
            
            if self.download_task is None or self.download_task.done():
                self.download_task = asyncio.create_task(self.process_download_queue())

            await interaction.followup.send(f"'{song.title}' wurde zur Download-Warteschlange hinzugefügt.", ephemeral=True)
        except Exception as e:
            error_message = self.error_handler.handle_error(e, ErrorCategory.UNKNOWN)
            self.logger.error(f"Fehler beim Hinzufügen des YouTube-Links: {error_message}")
            await interaction.followup.send(f"Ein Fehler ist aufgetreten: {error_message}", ephemeral=True)


    async def copy_current_track_link(self, interaction: discord.Interaction):
        if self.current_song:
            await interaction.response.send_message(f"Link des aktuellen Tracks: {self.current_song.url}", ephemeral=True)
        else:
            await interaction.response.defer()

    async def play_next(self, ctx):
        self.logger.info("play_next aufgerufen")
        await self.stop_update_task()
        self.seek_position = 0
        self.paused_time = 0
        self.pause_start = None

        if self.queue_manager.is_empty() and not self.current_song:
            self.logger.info("Keine Songs in der Warteschlange. Beende Wiedergabe.")
            await self.cleanup(ctx)
            return

        if self.queue_manager.is_empty() and self.repeat_mode and self.current_song:
            self.queue_manager.add_song(self.current_song)

        next_song = self.queue_manager.get_next_song()
        if next_song:
            self.current_song = next_song
            self.logger.info(f"Spiele nächsten Song: {self.current_song.title}")

            try:
                await asyncio.gather(
                    self.play_song(ctx),
                    self.update_now_playing(ctx),
                    self.start_update_task()
                )
            except Exception as e:
                error_message = self.error_handler.handle_error(e, ErrorCategory.UNKNOWN)
                self.logger.error(f"Fehler beim Abspielen des Songs: {error_message}")
                await self.play_next(ctx)
        else:
            self.logger.info("Keine weiteren Songs in der Warteschlange.")
            await self.cleanup(ctx)

    async def play_song(self, ctx):
        ctx.voice_client.play(
            discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(self.current_song.file_path),
                volume=self.volume
            ),
            after=lambda e: asyncio.run_coroutine_threadsafe(
                self.play_next(ctx), self.bot.loop
            )
        )
        self.logger.info(f"Wiedergabe gestartet für: {self.current_song.title}")
        self.is_playing = True
        self.current_song.start_time = asyncio.get_event_loop().time()

    async def cleanup(self, ctx):
        self.logger.debug("Führe Cleanup durch...")
        self.is_playing = False
        await self.stop_update_task()
        self.current_song = None
        self.seek_position = 0
        self.paused_time = 0
        self.pause_start = None
        if self.now_playing_message:
            try:
                await self.now_playing_message.delete()
            except discord.errors.NotFound:
                pass
        self.now_playing_message = None
        
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.logger.debug("Bot hat den Sprachkanal verlassen.")

    async def update_now_playing(self, ctx):
        if isinstance(ctx, discord.Interaction):
            channel = ctx.channel
        else:
            channel = ctx.channel

        if self.now_playing_message:
            try:
                await self.now_playing_message.delete()
            except discord.errors.NotFound:
                pass

        if not self.current_song:
            self.now_playing_message = None
            return

        embed = await create_now_playing_embed(self)
        self.now_playing_message = await channel.send(embed=embed, view=MusicControlView(self))

    def get_current_time(self):
        if self.current_song and self.current_song.start_time:
            elapsed = self.get_current_time_seconds()
            return format_duration(elapsed)
        return "0:00"

    def get_current_time_seconds(self):
        if self.current_song and self.current_song.start_time:
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - self.current_song.start_time - self.paused_time
            if self.pause_start:
                elapsed -= current_time - self.pause_start
            return max(0, elapsed + self.seek_position)
        return self.seek_position

    def create_progress_bar(self):
        if not self.current_song:
            return "Kein Song wird abgespielt"
        
        current_time = self.get_current_time_seconds()
        total_time = self.current_song.duration
        return create_progress_bar(current_time, total_time)

    @commands.Cog.listener()
    async def on_command(self, ctx):
        self.logger.debug(f"Befehl erkannt: {ctx.command}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        self.logger.error(f"Fehler bei Befehl {ctx.command}: {error}")

    async def process_download_queue(self):
        while True:
            song, ctx = await self.download_queue.get()
            try:
                downloaded_song = await download_audio(ctx, song, self.logger)
                if downloaded_song:
                    self.queue_manager.add_song(downloaded_song)
                    if not self.is_playing:
                        await self.play_next(ctx)
                    else:
                        await self.update_now_playing(ctx)
            except Exception as e:
                self.logger.error(f"Fehler beim Verarbeiten des Downloads: {str(e)}")
            finally:
                self.download_queue.task_done()

async def setup(bot):
    await bot.add_cog(Music(bot))

