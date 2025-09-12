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
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Fehlender Parameter: {error.param.name}. Verwende `!help {ctx.command}` für mehr Informationen.", delete_after=10)
            self.logger.warning(f"Fehlender Parameter für Befehl {ctx.command}: {error.param.name}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Ungültiger Parameter. Verwende `!help {ctx.command}` für mehr Informationen.", delete_after=10)
            self.logger.warning(f"Ungültiger Parameter für Befehl {ctx.command}: {str(error)}")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("Du hast nicht die erforderlichen Berechtigungen für diesen Befehl.", delete_after=10)
            self.logger.warning(f"Benutzer {ctx.author} hat versucht, {ctx.command} ohne Berechtigung auszuführen")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("Dem Bot fehlen die erforderlichen Berechtigungen für diesen Befehl.", delete_after=10)
            self.logger.error(f"Bot fehlen Berechtigungen für Befehl {ctx.command}: {error.missing_permissions}")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("Dieser Befehl kann nicht in privaten Nachrichten verwendet werden.", delete_after=10)
            self.logger.debug(f"Befehl {ctx.command} wurde in privater Nachricht versucht")
        else:
            self.logger.error(f"Fehler beim Ausführen eines Befehls: {str(error)}")
            await ctx.send("Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es später erneut.", delete_after=10)

    async def on_message(self, message):
        self.logger.debug(f"Nachricht erhalten: {message.content}")
        await self.process_commands(message)

bot = GrooveMaster()
bot.run(os.getenv("DISCORD_BOT_TOKEN"))

