import discord
from discord.ui import View, Button, Modal, TextInput

class MusicControlView(View):
    def __init__(self, music_cog):
        super().__init__(timeout=None)
        self.music_cog = music_cog
        
        self.add_item(Button(label="Play/Pause", custom_id="play_pause", style=discord.ButtonStyle.primary))
        self.add_item(Button(label="Stop", custom_id="stop", style=discord.ButtonStyle.danger))
        self.add_item(Button(label="Skip", custom_id="skip", style=discord.ButtonStyle.secondary))
        self.add_item(Button(label="Lautstärke", custom_id="volume", style=discord.ButtonStyle.secondary))
        self.add_item(Button(label="Wiederholen", custom_id="repeat", style=discord.ButtonStyle.secondary))
        self.add_item(Button(label="Mischen", custom_id="shuffle", style=discord.ButtonStyle.secondary))
        self.add_item(Button(label="YouTube-Link hinzufügen", custom_id="add_link", style=discord.ButtonStyle.success))
        self.add_item(Button(label="Aktuellen Link kopieren", custom_id="copy_link", style=discord.ButtonStyle.secondary))
        self.add_item(Button(label="Springen", custom_id="jump", style=discord.ButtonStyle.secondary))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] == "play_pause":
            await self.music_cog.toggle_playback(interaction)
        elif interaction.data["custom_id"] == "stop":
            await self.music_cog.stop(interaction)
        elif interaction.data["custom_id"] == "skip":
            await self.music_cog.skip(interaction)
        elif interaction.data["custom_id"] == "volume":
            await interaction.response.send_modal(VolumeModal(self.music_cog))
        elif interaction.data["custom_id"] == "repeat":
            await self.music_cog.toggle_repeat(interaction)
        elif interaction.data["custom_id"] == "shuffle":
            await self.music_cog.shuffle(interaction)
        elif interaction.data["custom_id"] == "add_link":
            await interaction.response.send_modal(AddYouTubeLinkModal(self.music_cog))
        elif interaction.data["custom_id"] == "copy_link":
            await self.music_cog.copy_current_track_link(interaction)
        elif interaction.data["custom_id"] == "jump":
            await interaction.response.send_modal(JumpModal(self.music_cog))
        return True

class VolumeModal(Modal):
    def __init__(self, music_cog):
        super().__init__(title="Lautstärke einstellen")
        self.music_cog = music_cog
        self.volume = TextInput(label="Lautstärke (0-100)", placeholder="Gib eine Zahl zwischen 0 und 100 ein")
        self.add_item(self.volume)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            volume = int(self.volume.value)
            if 0 <= volume <= 100:
                await self.music_cog.set_volume(interaction, volume)
            else:
                await interaction.response.send_message("Bitte gib eine Zahl zwischen 0 und 100 ein.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Ungültige Eingabe. Bitte gib eine Zahl ein.", ephemeral=True)

class AddYouTubeLinkModal(Modal):
    def __init__(self, music_cog):
        super().__init__(title="YouTube-Link hinzufügen")
        self.music_cog = music_cog
        self.link = TextInput(label="YouTube-Link", placeholder="Füge hier den YouTube-Link ein")
        self.add_item(self.link)
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.music_cog.add_youtube_link(interaction, self.link.value)

class JumpModal(Modal):
    def __init__(self, music_cog):
        super().__init__(title="Zu Zeitpunkt springen")
        self.music_cog = music_cog
        self.jump_time = TextInput(label="Zeit (Sekunden oder MM:SS)", placeholder="Gib die Zeit in Sekunden oder im Format MM:SS ein")
        self.add_item(self.jump_time)
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.music_cog.jump(interaction, self.jump_time.value)

