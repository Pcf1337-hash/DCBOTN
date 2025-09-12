import discord
from discord.ext import commands
import subprocess
import os

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def restart(self, ctx):
        restart_message = await ctx.send("Bot wird neu gestartet...")
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        restart_script = os.path.join(script_dir, "cogs", "restart_bot.sh")
        self.bot.logger.debug(f"Versuche, Restart-Skript auszuführen: {restart_script}")
        try:
            await restart_message.delete()
            result = subprocess.run(["/bin/bash", restart_script], capture_output=True, text=True, cwd=script_dir)
            self.bot.logger.info(f"Restart-Skript Ausgabe: {result.stdout}")
            if result.stderr:
                self.bot.logger.error(f"Restart-Skript Fehler: {result.stderr}")
            else:
                self.bot.logger.info("Restart-Skript erfolgreich ausgeführt")
        except Exception as e:
            self.bot.logger.error(f"Fehler beim Ausführen des Restart-Skripts: {str(e)}")
        await self.bot.close()

    @restart.error
    async def restart_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            self.bot.logger.warning(f"Benutzer {ctx.author} hat versucht, den Bot neu zu starten, ohne die erforderlichen Berechtigungen.")
        else:
            self.bot.logger.error(f"Unerwarteter Fehler beim Restart-Befehl: {str(error)}")

async def setup(bot):
    await bot.add_cog(Admin(bot))

