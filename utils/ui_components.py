import discord
from discord.ui import View, Button, Modal, TextInput, Select
from discord import ButtonStyle, SelectOption
from typing import Optional, List
from utils.exceptions import InvalidTimeFormatError
from utils.logger import get_logger
from utils.music_helpers import format_duration, format_number
from config.settings import settings

logger = get_logger('ui_components')

class MusicControlView(View):
    """Enhanced music control view with modern UI components."""
    
    def __init__(self, music_cog):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.music_cog = music_cog
        
        # Row 1: Primary playback controls
        self.add_item(PlayPauseButton(music_cog))
        self.add_item(StopButton())
        self.add_item(SkipButton())
        self.add_item(VolumeButton())
        
        # Row 2: Queue and settings controls
        self.add_item(RepeatButton(music_cog))
        self.add_item(ShuffleButton())
        self.add_item(QueueButton())
        self.add_item(JumpButton())
        
        # Row 3: Additional features
        self.add_item(AddSongButton())
        self.add_item(CopyLinkButton())

    async def on_timeout(self):
        """Called when the view times out."""
        for item in self.children:
            item.disabled = True
        
        if hasattr(self, 'message') and self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

class PlayPauseButton(Button):
    def __init__(self, music_cog):
        self.music_cog = music_cog
        is_playing = music_cog.is_playing and not music_cog.is_paused()
        super().__init__(
            emoji="⏸️" if is_playing else "▶️",
            label="Pause" if is_playing else "Play",
            style=ButtonStyle.primary,
            custom_id="play_pause"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("❌ Bot ist nicht verbunden.", ephemeral=True)
            return
        
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            self.music_cog.pause_start = interaction.created_at.timestamp()
            self.emoji = "▶️"
            self.label = "Play"
        elif interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            if self.music_cog.pause_start:
                self.music_cog.paused_time += interaction.created_at.timestamp() - self.music_cog.pause_start
                self.music_cog.pause_start = None
            self.emoji = "⏸️"
            self.label = "Pause"
        
        await interaction.response.edit_message(view=self.view)

class StopButton(Button):
    def __init__(self):
        super().__init__(
            emoji="⏹️",
            label="Stop",
            style=ButtonStyle.danger,
            custom_id="stop"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog and interaction.guild.voice_client:
            await music_cog._cleanup(interaction)
            await interaction.response.send_message("⏹️ Wiedergabe gestoppt.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nichts zu stoppen.", ephemeral=True)

class SkipButton(Button):
    def __init__(self):
        super().__init__(
            emoji="⏭️",
            label="Skip",
            style=ButtonStyle.secondary,
            custom_id="skip"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild.voice_client or not interaction.guild.voice_client.is_playing():
            await interaction.response.send_message("❌ Nichts zu überspringen.", ephemeral=True)
            return
        
        music_cog = interaction.client.get_cog('Music')
        if music_cog and music_cog.current_song:
            title = music_cog.current_song.title
            interaction.guild.voice_client.stop()
            await interaction.response.send_message(f"⏭️ **{title}** übersprungen.", ephemeral=True)
        else:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Song übersprungen.", ephemeral=True)

class VolumeButton(Button):
    def __init__(self):
        super().__init__(
            emoji="🔊",
            label="Volume",
            style=ButtonStyle.secondary,
            custom_id="volume"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await interaction.response.send_modal(VolumeModal(music_cog))
        else:
            await interaction.response.send_message("❌ Musik-System nicht verfügbar.", ephemeral=True)

class RepeatButton(Button):
    def __init__(self, music_cog):
        self.music_cog = music_cog
        super().__init__(
            emoji="🔁",
            label="Repeat",
            style=ButtonStyle.success if music_cog.repeat_mode else ButtonStyle.secondary,
            custom_id="repeat"
        )
    
    async def callback(self, interaction: discord.Interaction):
        self.music_cog.repeat_mode = not self.music_cog.repeat_mode
        self.style = ButtonStyle.success if self.music_cog.repeat_mode else ButtonStyle.secondary
        
        status = "aktiviert" if self.music_cog.repeat_mode else "deaktiviert"
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"🔁 Wiederholung **{status}**.", ephemeral=True)

class ShuffleButton(Button):
    def __init__(self):
        super().__init__(
            emoji="🔀",
            label="Shuffle",
            style=ButtonStyle.secondary,
            custom_id="shuffle"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            if music_cog.queue_manager.is_empty():
                await interaction.response.send_message("❌ Warteschlange ist leer.", ephemeral=True)
                return
            
            await music_cog.queue_manager.shuffle()
            await interaction.response.send_message("🔀 Warteschlange gemischt.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Musik-System nicht verfügbar.", ephemeral=True)

class QueueButton(Button):
    def __init__(self):
        super().__init__(
            emoji="📋",
            label="Queue",
            style=ButtonStyle.secondary,
            custom_id="queue"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            view = QueueView(music_cog)
            embed = view.get_queue_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Musik-System nicht verfügbar.", ephemeral=True)

class JumpButton(Button):
    def __init__(self):
        super().__init__(
            emoji="⏩",
            label="Jump",
            style=ButtonStyle.secondary,
            custom_id="jump"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog and music_cog.current_song:
            await interaction.response.send_modal(JumpModal(music_cog))
        else:
            await interaction.response.send_message("❌ Kein Song wird abgespielt.", ephemeral=True)

class AddSongButton(Button):
    def __init__(self):
        super().__init__(
            emoji="➕",
            label="Add Song",
            style=ButtonStyle.success,
            custom_id="add_song"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await interaction.response.send_modal(AddYouTubeLinkModal(music_cog))
        else:
            await interaction.response.send_message("❌ Musik-System nicht verfügbar.", ephemeral=True)

class CopyLinkButton(Button):
    def __init__(self):
        super().__init__(
            emoji="🔗",
            label="Copy Link",
            style=ButtonStyle.secondary,
            custom_id="copy_link"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog and music_cog.current_song:
            await interaction.response.send_message(
                f"🔗 **Link:** {music_cog.current_song.url}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Kein Song wird abgespielt.", ephemeral=True)

# Modals
class VolumeModal(Modal):
    """Enhanced volume modal with validation and presets."""
    
    def __init__(self, music_cog):
        super().__init__(title="🔊 Lautstärke einstellen")
        self.music_cog = music_cog
        
        current_volume = int(music_cog.volume * 100)
        self.volume = TextInput(
            label="Lautstärke (0-100)",
            placeholder=f"Aktuell: {current_volume}%",
            default=str(current_volume),
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.volume)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            volume = int(self.volume.value)
            if not 0 <= volume <= 100:
                await interaction.response.send_message(
                    "❌ Lautstärke muss zwischen 0 und 100 liegen.",
                    ephemeral=True
                )
                return
            
            self.music_cog.volume = volume / 100
            if interaction.guild.voice_client and hasattr(interaction.guild.voice_client, 'source'):
                if interaction.guild.voice_client.source:
                    interaction.guild.voice_client.source.volume = self.music_cog.volume
            
            await interaction.response.send_message(
                f"🔊 Lautstärke auf **{volume}%** gesetzt.",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Bitte gib eine gültige Zahl ein.",
                ephemeral=True
            )

class AddYouTubeLinkModal(Modal):
    """Enhanced modal for adding YouTube links with better validation."""
    
    def __init__(self, music_cog):
        super().__init__(title="➕ Song hinzufügen")
        self.music_cog = music_cog
        
        self.link = TextInput(
            label="YouTube-Link oder Suchbegriff",
            placeholder="https://youtube.com/watch?v=... oder 'Song Name Artist'",
            min_length=3,
            max_length=500,
            required=True
        )
        self.add_item(self.link)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Use the play command logic
            ctx = await interaction.client.get_context(interaction)
            ctx.author = interaction.user
            ctx.guild = interaction.guild
            ctx.channel = interaction.channel
            
            await self.music_cog._handle_single_song(ctx, self.link.value)
            
        except Exception as e:
            logger.error("Error adding song via modal", error=str(e))
            await interaction.followup.send(
                f"❌ Fehler beim Hinzufügen: {str(e)}",
                ephemeral=True
            )

class JumpModal(Modal):
    """Enhanced jump modal with better time parsing and validation."""
    
    def __init__(self, music_cog):
        super().__init__(title="⏩ Zu Zeitpunkt springen")
        self.music_cog = music_cog
        
        current_time = self.music_cog.get_current_time()
        duration = format_duration(self.music_cog.current_song.duration) if self.music_cog.current_song else "0:00"
        
        self.jump_time = TextInput(
            label="Zeit (MM:SS oder Sekunden)",
            placeholder=f"z.B. 2:30 oder 150 (aktuell: {current_time}/{duration})",
            min_length=1,
            max_length=10,
            required=True
        )
        self.add_item(self.jump_time)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            from utils.music_helpers import parse_time_input
            
            target_seconds = parse_time_input(self.jump_time.value)
            
            if not self.music_cog.current_song:
                await interaction.response.send_message("❌ Kein Song wird abgespielt.", ephemeral=True)
                return
            
            if target_seconds > self.music_cog.current_song.duration:
                await interaction.response.send_message(
                    f"❌ Zeit ist länger als die Song-Dauer ({format_duration(self.music_cog.current_song.duration)}).",
                    ephemeral=True
                )
                return
            
            # Implement jump logic
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_playing():
                voice_client.pause()
                
                # Create new audio source with seek
                audio_source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(
                        str(self.music_cog.current_song.file_path),
                        before_options=f"-ss {target_seconds}"
                    ),
                    volume=self.music_cog.volume
                )
                
                voice_client.source = audio_source
                voice_client.resume()
                
                # Update timing
                self.music_cog.seek_position = target_seconds
                self.music_cog.current_song.start_time = interaction.created_at.timestamp() - target_seconds
                self.music_cog.paused_time = 0
                self.music_cog.pause_start = None
                
                await interaction.response.send_message(
                    f"⏩ Zu **{format_duration(target_seconds)}** gesprungen.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Kein Song wird abgespielt.", ephemeral=True)
                
        except InvalidTimeFormatError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error("Error jumping to time", error=str(e))
            await interaction.response.send_message(
                f"❌ Fehler beim Springen: {str(e)}",
                ephemeral=True
            )

# Queue View
class QueueView(View):
    """Enhanced paginated queue view with more features."""
    
    def __init__(self, music_cog, page: int = 0):
        super().__init__(timeout=300)
        self.music_cog = music_cog
        self.page = page
        self.per_page = 10
        
        # Add navigation and control buttons
        self.add_item(PreviousPageButton())
        self.add_item(NextPageButton())
        self.add_item(ClearQueueButton())
        self.add_item(ShuffleQueueButton())
        
        # Add queue management select menu if queue has items
        if not music_cog.queue_manager.is_empty():
            self.add_item(QueueManagementSelect(music_cog))
    
    def get_queue_embed(self) -> discord.Embed:
        """Generate enhanced queue embed for current page."""
        queue = self.music_cog.queue_manager.queue
        queue_info = self.music_cog.queue_manager.get_queue_info()
        
        embed = discord.Embed(
            title="📋 Musik-Warteschlange",
            color=discord.Color(settings.embed_color)
        )
        
        if not queue:
            embed.description = "Die Warteschlange ist leer.\nVerwende `/play` um Songs hinzuzufügen!"
            embed.set_footer(text="Tipp: Du kannst auch YouTube-Playlists hinzufügen!")
            return embed
        
        # Calculate pagination
        total_pages = (len(queue) - 1) // self.per_page + 1
        start_idx = self.page * self.per_page
        end_idx = start_idx + self.per_page
        page_songs = queue[start_idx:end_idx]
        
        # Build queue list
        queue_text = []
        for i, song in enumerate(page_songs, start=start_idx + 1):
            duration = format_duration(song.duration)
            title = song.title[:35] + "..." if len(song.title) > 35 else song.title
            
            # Add status indicators
            status = ""
            if song.is_downloaded:
                status = "✅"
            else:
                status = f"⏳ {int(song.download_progress * 100)}%"
            
            queue_text.append(f"`{i:2d}.` **{title}** `[{duration}]` {status}")
        
        embed.description = "\n".join(queue_text)
        
        # Enhanced statistics
        embed.add_field(
            name="📊 Statistiken",
            value=f"**Songs:** {queue_info['size']}/{queue_info['max_size']}\n"
                  f"**Gesamtdauer:** {queue_info['total_duration_formatted']}\n"
                  f"**Anfrager:** {queue_info['unique_requesters']}",
            inline=True
        )
        
        # Current song info
        if self.music_cog.current_song:
            current_time = self.music_cog.get_current_time()
            embed.add_field(
                name="🎵 Aktuell",
                value=f"**{self.music_cog.current_song.title[:30]}**\n"
                      f"⏰ {current_time}/{self.music_cog.current_song.formatted_duration}",
                inline=True
            )
        
        # Queue status
        status_text = []
        if queue_info['is_shuffled']:
            status_text.append("🔀 Gemischt")
        if self.music_cog.repeat_mode:
            status_text.append("🔁 Wiederholung")
        if queue_info['is_full']:
            status_text.append("⚠️ Voll")
        
        if status_text:
            embed.add_field(
                name="⚙️ Status",
                value=" • ".join(status_text),
                inline=True
            )
        
        embed.set_footer(text=f"Seite {self.page + 1}/{total_pages} • {len(queue)} Songs insgesamt")
        
        return embed

class PreviousPageButton(Button):
    def __init__(self):
        super().__init__(emoji="◀️", style=ButtonStyle.secondary, custom_id="prev_page")
    
    async def callback(self, interaction: discord.Interaction):
        view: QueueView = self.view
        if view.page > 0:
            view.page -= 1
            embed = view.get_queue_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.defer()

class NextPageButton(Button):
    def __init__(self):
        super().__init__(emoji="▶️", style=ButtonStyle.secondary, custom_id="next_page")
    
    async def callback(self, interaction: discord.Interaction):
        view: QueueView = self.view
        queue = view.music_cog.queue_manager.queue
        total_pages = (len(queue) - 1) // view.per_page + 1 if queue else 1
        
        if view.page < total_pages - 1:
            view.page += 1
            embed = view.get_queue_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.defer()

class ClearQueueButton(Button):
    def __init__(self):
        super().__init__(emoji="🗑️", label="Clear", style=ButtonStyle.danger, custom_id="clear_queue")
    
    async def callback(self, interaction: discord.Interaction):
        view: QueueView = self.view
        if view.music_cog.queue_manager.is_empty():
            await interaction.response.send_message("❌ Warteschlange ist bereits leer.", ephemeral=True)
            return
        
        await view.music_cog.queue_manager.clear()
        embed = view.get_queue_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class ShuffleQueueButton(Button):
    def __init__(self):
        super().__init__(emoji="🔀", label="Shuffle", style=ButtonStyle.secondary, custom_id="shuffle_queue")
    
    async def callback(self, interaction: discord.Interaction):
        view: QueueView = self.view
        if view.music_cog.queue_manager.is_empty():
            await interaction.response.send_message("❌ Warteschlange ist leer.", ephemeral=True)
            return
        
        await view.music_cog.queue_manager.shuffle()
        embed = view.get_queue_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class QueueManagementSelect(Select):
    """Select menu for queue management actions."""
    
    def __init__(self, music_cog):
        self.music_cog = music_cog
        
        options = [
            SelectOption(
                label="Song entfernen",
                description="Entferne einen Song aus der Warteschlange",
                emoji="🗑️",
                value="remove_song"
            ),
            SelectOption(
                label="Song verschieben",
                description="Verschiebe einen Song in der Warteschlange",
                emoji="↕️",
                value="move_song"
            ),
            SelectOption(
                label="Meine Songs anzeigen",
                description="Zeige nur deine Songs in der Warteschlange",
                emoji="👤",
                value="show_my_songs"
            )
        ]
        
        super().__init__(
            placeholder="Warteschlange verwalten...",
            options=options,
            custom_id="queue_management"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "remove_song":
            await interaction.response.send_modal(RemoveSongModal(self.music_cog))
        elif self.values[0] == "move_song":
            await interaction.response.send_modal(MoveSongModal(self.music_cog))
        elif self.values[0] == "show_my_songs":
            user_songs = self.music_cog.queue_manager.get_user_songs(interaction.user.id)
            if not user_songs:
                await interaction.response.send_message("❌ Du hast keine Songs in der Warteschlange.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title=f"👤 Deine Songs ({len(user_songs)})",
                color=discord.Color(settings.embed_color)
            )
            
            song_list = []
            for i, song in enumerate(user_songs[:10], 1):  # Limit to 10
                title = song.title[:40] + "..." if len(song.title) > 40 else song.title
                song_list.append(f"`{i}.` **{title}** `[{song.formatted_duration}]`")
            
            embed.description = "\n".join(song_list)
            if len(user_songs) > 10:
                embed.set_footer(text=f"... und {len(user_songs) - 10} weitere Songs")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

class RemoveSongModal(Modal):
    def __init__(self, music_cog):
        super().__init__(title="🗑️ Song entfernen")
        self.music_cog = music_cog
        
        self.position = TextInput(
            label="Position (1-basiert)",
            placeholder=f"1-{music_cog.queue_manager.size()}",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.position)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            pos = int(self.position.value)
            if pos < 1 or pos > self.music_cog.queue_manager.size():
                await interaction.response.send_message(
                    f"❌ Position muss zwischen 1 und {self.music_cog.queue_manager.size()} liegen.",
                    ephemeral=True
                )
                return
            
            removed_song = await self.music_cog.queue_manager.remove_song(pos - 1)
            if removed_song:
                await interaction.response.send_message(
                    f"🗑️ **{removed_song.title}** wurde entfernt.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Fehler beim Entfernen.", ephemeral=True)
                
        except ValueError:
            await interaction.response.send_message("❌ Bitte gib eine gültige Zahl ein.", ephemeral=True)

class MoveSongModal(Modal):
    def __init__(self, music_cog):
        super().__init__(title="↕️ Song verschieben")
        self.music_cog = music_cog
        
        self.from_pos = TextInput(
            label="Von Position",
            placeholder=f"1-{music_cog.queue_manager.size()}",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.from_pos)
        
        self.to_pos = TextInput(
            label="Zu Position",
            placeholder=f"1-{music_cog.queue_manager.size()}",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.to_pos)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            from_pos = int(self.from_pos.value) - 1
            to_pos = int(self.to_pos.value) - 1
            
            if not (0 <= from_pos < self.music_cog.queue_manager.size()):
                await interaction.response.send_message("❌ Ungültige Ausgangsposition.", ephemeral=True)
                return
            
            if not (0 <= to_pos < self.music_cog.queue_manager.size()):
                await interaction.response.send_message("❌ Ungültige Zielposition.", ephemeral=True)
                return
            
            success = await self.music_cog.queue_manager.move_song(from_pos, to_pos)
            if success:
                await interaction.response.send_message(
                    f"↕️ Song von Position {from_pos + 1} zu {to_pos + 1} verschoben.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Fehler beim Verschieben.", ephemeral=True)
                
        except ValueError:
            await interaction.response.send_message("❌ Bitte gib gültige Zahlen ein.", ephemeral=True)