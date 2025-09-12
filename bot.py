import discord
from discord.ext import commands
import asyncio
import logging
import os
from dotenv import load_dotenv
from utils.logger import setup_logger
from utils.constants import COMMAND_PREFIX, INTENTS, DOWNLOADS_DIR
from cogs.music import Music
from cogs.admin import Admin

load_dotenv()

class GrooveMaster(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=COMMAND_PREFIX, intents=INTENTS)
        self.logger = setup_logger()
        self.logger.setLevel(logging.DEBUG)

    async def setup_hook(self):
        await self.add_cog(Music(self))
        await self.add_cog(Admin(self))

    async def on_ready(self):
        self.logger.info(f'Bot ist bereit! Eingeloggt als {self.user.name} (ID: {self.user.id})')
        await self.change_presence(activity=discord.Game(name="!help für Befehle"))
        
        music_cog = self.get_cog('Music')
        if music_cog:
            await music_cog.cleanup_downloads()

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            self.logger.debug(f"Unbekannter Befehl: {ctx.message.content}")
        else:
            self.logger.error(f"Fehler beim Ausführen eines Befehls: {str(error)}")

    async def on_message(self, message):
        self.logger.debug(f"Nachricht erhalten: {message.content}")
        await self.process_commands(message)

bot = GrooveMaster()
bot.run(os.getenv("DISCORD_TOKEN"))

