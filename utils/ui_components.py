import discord
from discord.ui import View, Button, Modal, TextInput
from discord import ButtonStyle
from typing import Optional
from utils.exceptions import InvalidTimeFormatError
from utils.logger import get_logger

logger = get_logger('ui_components')

class MusicControlView(View):
    """Enhanced music control view with better UX."""
    
    def __init__(self, music_cog):
        super().__init__(timeout=None)
        self.music_cog = music_cog
        
        # Row 1: Playback controls
        self.add_item(PlayPauseButton(music_cog))
        self.add_item(StopButton())
        self.add_item(SkipButton())
        self.add_item(VolumeButton())
        
        # Row 2: Queue controls
        self.add_item(RepeatButton(music_cog))
        self.add_item(ShuffleButton())
        self.add_item(QueueButton())
        self.add_item(JumpButton())
        
        # Row 3: Additional features
        self.add_item(AddLinkButton())
        self.add_item(CopyLinkButton())

class PlayPauseButton(Button):
    def __init__(self, music_cog):
        self.music_cog = music_cog
        is_playing = music_cog.is_playing and not music_cog.is_paused()
        super().__init__(
            label="⏸️ Pause" if is_playing else "▶️ Play",
            style=ButtonStyle.primary,
            custom_id="play_pause"
        )
    
    async def callback(self, interaction: discord.Interaction):
        await self.music_cog.toggle_playback(interaction)

class StopButton(Button):
    def __init__(self):
        super().__init__(
            label="⏹️ Stop",
            style=ButtonStyle.danger,
            custom_id="stop"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await music_cog.stop(interaction)

class SkipButton(Button):
    def __init__(self):
        super().__init__(
            label="⏭️ Skip",
            style=ButtonStyle.secondary,
            custom_id="skip"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await music_cog.skip(interaction)

class VolumeButton(Button):
    def __init__(self):
        super().__init__(
            label="🔊 Volume",
            style=ButtonStyle.secondary,
            custom_id="volume"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await interaction.response.send_modal(VolumeModal(music_cog))

class RepeatButton(Button):
    def __init__(self, music_cog):
        self.music_cog = music_cog
        super().__init__(
            label="🔁 Repeat" if music_cog.repeat_mode else "🔁 Repeat",
            style=ButtonStyle.success if music_cog.repeat_mode else ButtonStyle.secondary,
            custom_id="repeat"
        )
    
    async def callback(self, interaction: discord.Interaction):
        await self.music_cog.toggle_repeat(interaction)

class ShuffleButton(Button):
    def __init__(self):
        super().__init__(
            label="🔀 Shuffle",
            style=ButtonStyle.secondary,
            custom_id="shuffle"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await music_cog.shuffle(interaction)

class QueueButton(Button):
    def __init__(self):
        super().__init__(
            label="📋 Queue",
            style=ButtonStyle.secondary,
            custom_id="queue"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await music_cog.show_queue(interaction)

class JumpButton(Button):
    def __init__(self):
        super().__init__(
            label="⏩ Jump",
            style=ButtonStyle.secondary,
            custom_id="jump"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await interaction.response.send_modal(JumpModal(music_cog))

class AddLinkButton(Button):
    def __init__(self):
        super().__init__(
            label="➕ Add Song",
            style=ButtonStyle.success,
            custom_id="add_link"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await interaction.response.send_modal(AddYouTubeLinkModal(music_cog))

class CopyLinkButton(Button):
    def __init__(self):
        super().__init__(
            label="🔗 Copy Link",
            style=ButtonStyle.secondary,
            custom_id="copy_link"
        )
    
    async def callback(self, interaction: discord.Interaction):
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            await music_cog.copy_current_track_link(interaction)

class VolumeModal(Modal):
    """Enhanced volume modal with validation."""
    
    def __init__(self, music_cog):
        super().__init__(title="Lautstärke einstellen")
        self.music_cog = music_cog
        
        current_volume = int(music_cog.volume * 100)
        self.volume = TextInput(
            label="Lautstärke (0-100)",
            placeholder=f"Aktuelle Lautstärke: {current_volume}%",
            default=str(current_volume),
            min_length=1,
            max_length=3
        )
        self.add_item(self.volume)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            volume = int(self.volume.value)
            if 0 <= volume <= 100:
                await self.music_cog.set_volume(interaction, volume)
                await interaction.response.send_message(
                    f"🔊 Lautstärke auf {volume}% gesetzt",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Bitte gib eine Zahl zwischen 0 und 100 ein.",
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(
                "❌ Ungültige Eingabe. Bitte gib eine Zahl ein.",
                ephemeral=True
            )

class AddYouTubeLinkModal(Modal):
    """Enhanced modal for adding YouTube links."""
    
    def __init__(self, music_cog):
        super().__init__(title="YouTube-Link hinzufügen")
        self.music_cog = music_cog
        self.link = TextInput(
            label="YouTube-Link oder Suchbegriff",
            placeholder="https://youtube.com/watch?v=... oder 'Song Name Artist'",
            min_length=3,
            max_length=500
        )
        self.add_item(self.link)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.music_cog.add_youtube_link(interaction, self.link.value)
        except Exception as e:
            logger.error(f"Error adding YouTube link: {e}")
            await interaction.followup.send(
                f"❌ Fehler beim Hinzufügen: {str(e)}",
                ephemeral=True
            )

class JumpModal(Modal):
    """Enhanced jump modal with better time parsing."""
    
    def __init__(self, music_cog):
        super().__init__(title="Zu Zeitpunkt springen")
        self.music_cog = music_cog
        self.jump_time = TextInput(
            label="Zeit (Sekunden, MM:SS oder HH:MM:SS)",
            placeholder="z.B. 120, 2:30 oder 1:30:45",
            min_length=1,
            max_length=10
        )
        self.add_item(self.jump_time)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.music_cog.jump(interaction, self.jump_time.value)
            await interaction.response.send_message(
                f"⏩ Zu {self.jump_time.value} gesprungen",
                ephemeral=True
            )
        except InvalidTimeFormatError as e:
            await interaction.response.send_message(
                f"❌ {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error jumping to time: {e}")
            await interaction.response.send_message(
                f"❌ Fehler beim Springen: {str(e)}",
                ephemeral=True
            )

class QueueView(View):
    """Paginated queue view."""
    
    def __init__(self, music_cog, page: int = 0):
        super().__init__(timeout=300)
        self.music_cog = music_cog
        self.page = page
        self.per_page = 10
        
        # Add navigation buttons
        self.add_item(PreviousPageButton())
        self.add_item(NextPageButton())
        self.add_item(ClearQueueButton())
    
    def get_queue_embed(self) -> discord.Embed:
        """Generate queue embed for current page."""
        queue = self.music_cog.queue_manager.queue
        total_pages = (len(queue) - 1) // self.per_page + 1 if queue else 1
        
        embed = discord.Embed(
            title="📋 Musik-Warteschlange",
            color=discord.Color.blue()
        )
        
        if not queue:
            embed.description = "Die Warteschlange ist leer"
            return embed
        
        start_idx = self.page * self.per_page
        end_idx = start_idx + self.per_page
        page_songs = queue[start_idx:end_idx]
        
        queue_text = []
        for i, song in enumerate(page_songs, start=start_idx + 1):
            duration = song.formatted_duration
            title = song.title[:40] + "..." if len(song.title) > 40 else song.title
            queue_text.append(f"`{i:2d}.` **{title}** `[{duration}]`")
        
        embed.description = "\n".join(queue_text)
        
        # Queue stats
        total_duration = sum(song.duration for song in queue)
        embed.add_field(
            name="📊 Statistiken",
            value=f"Songs: {len(queue)}\nGesamtdauer: {format_duration(total_duration)}",
            inline=True
        )
        
        embed.set_footer(text=f"Seite {self.page + 1}/{total_pages}")
        
        return embed

class PreviousPageButton(Button):
    def __init__(self):
        super().__init__(label="◀️ Zurück", style=ButtonStyle.secondary)
    
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
        super().__init__(label="Weiter ▶️", style=ButtonStyle.secondary)
    
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
        super().__init__(label="🗑️ Leeren", style=ButtonStyle.danger)
    
    async def callback(self, interaction: discord.Interaction):
        view: QueueView = self.view
        view.music_cog.queue_manager.clear()
        embed = view.get_queue_embed()
        await interaction.response.edit_message(embed=embed, view=view)

