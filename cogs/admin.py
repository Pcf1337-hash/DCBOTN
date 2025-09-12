import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import os
import psutil
import asyncio
from pathlib import Path
from config.settings import settings
from utils.logger import get_logger, LoggerMixin
from utils.monitoring import performance_monitor
from utils.cache import cache_manager
from utils.exceptions import *
import time

class Admin(commands.Cog, LoggerMixin):
    """Enhanced admin cog with better system management and monitoring."""
    
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Called when the cog is loaded."""
        self.logger.info("Admin cog loaded")

    def cog_check(self, ctx):
        """Check if user has admin permissions or is bot owner."""
        if ctx.author.id in self.bot.owner_ids:
            return True
        return ctx.author.guild_permissions.administrator

    @commands.hybrid_command(name="restart")
    @commands.has_permissions(administrator=True)
    async def restart(self, ctx: commands.Context):
        """Restart the bot with enhanced error handling."""
        embed = discord.Embed(
            title="🔄 Bot wird neu gestartet...",
            description="Der Bot wird in wenigen Sekunden neu gestartet.",
            color=discord.Color.orange()
        )
        restart_message = await ctx.send(embed=embed)
        
        # Save current state
        try:
            await cache_manager.save_cache()
            self.logger.info("Cache saved before restart")
        except Exception as e:
            self.logger.error("Failed to save cache before restart", error=str(e))
        
        # Get script directory dynamically
        script_dir = Path(__file__).parent.parent
        restart_script = script_dir / "cogs" / "restart_bot.sh"
        
        self.logger.info("Attempting to restart bot", script_path=str(restart_script))
        
        try:
            # Try to delete the restart message
            await restart_message.delete()
        except discord.NotFound:
            pass
        
        try:
            # Execute restart script
            result = subprocess.run(
                ["/bin/bash", str(restart_script)], 
                capture_output=True, 
                text=True, 
                cwd=str(script_dir),
                timeout=30
            )
            
            self.logger.info("Restart script output", stdout=result.stdout, stderr=result.stderr)
            
            if result.returncode != 0:
                self.logger.error("Restart script failed", return_code=result.returncode)
            else:
                self.logger.info("Restart script executed successfully")
                
        except subprocess.TimeoutExpired:
            self.logger.error("Restart script timed out")
        except Exception as e:
            self.logger.error("Failed to execute restart script", error=str(e))
        finally:
            # Close the bot
            await self.bot.close()

    @commands.hybrid_command(name="status")
    async def status(self, ctx: commands.Context):
        """Show comprehensive bot status and statistics."""
        # Get system info
        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent()
        
        # Get bot stats
        bot_stats = self.bot.get_stats()
        
        # Create embed
        embed = discord.Embed(
            title="🤖 Bot Status",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        # Bot info
        uptime_seconds = int(bot_stats['uptime'])
        uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
        
        embed.add_field(
            name="📊 Bot Statistiken",
            value=f"**Uptime:** {uptime_str}\n"
                  f"**Server:** {bot_stats['guild_count']}\n"
                  f"**Benutzer:** {bot_stats['user_count']:,}\n"
                  f"**Befehle:** {bot_stats['command_count']:,}\n"
                  f"**Fehler:** {bot_stats['error_count']:,}",
            inline=True
        )
        
        # System info
        memory_mb = memory_info.rss / 1024 / 1024
        embed.add_field(
            name="💻 System",
            value=f"**RAM:** {memory_mb:.1f} MB\n"
                  f"**CPU:** {cpu_percent:.1f}%\n"
                  f"**Python:** {psutil.__version__}\n"
                  f"**Discord.py:** {discord.__version__}",
            inline=True
        )
        
        # Voice connections
        voice_connections = bot_stats['voice_connections']
        embed.add_field(
            name="🎵 Musik",
            value=f"**Verbindungen:** {voice_connections}\n"
                  f"**Max Queue:** {settings.max_queue_size}\n"
                  f"**Downloads:** {settings.max_concurrent_downloads}",
            inline=True
        )
        
        # Cache info
        cache_stats = cache_manager.get_stats()
        embed.add_field(
            name="💾 Cache",
            value=f"**Einträge:** {cache_stats['active_entries']}\n"
                  f"**Abgelaufen:** {cache_stats['expired_entries']}\n"
                  f"**Gesamt:** {cache_stats['total_entries']}",
            inline=True
        )
        
        # Performance monitoring
        if settings.enable_metrics:
            perf_stats = performance_monitor.get_stats()
            embed.add_field(
                name="📈 Performance",
                value=f"**Befehle:** {perf_stats['total_commands']}\n"
                      f"**Uptime:** {perf_stats['uptime']:.1f}s\n"
                      f"**Monitoring:** ✅",
                inline=True
            )
        
        embed.set_footer(text=f"Bot Version • {settings.command_prefix}help für Befehle")
        
        await ctx.send(embed=embed)
        self.log_command(ctx, 'status')

    @commands.hybrid_command(name="cleanup")
    @commands.has_permissions(administrator=True)
    async def cleanup(self, ctx: commands.Context):
        """Clean up temporary files and cache."""
        embed = discord.Embed(
            title="🧹 Cleanup wird ausgeführt...",
            color=discord.Color.orange()
        )
        message = await ctx.send(embed=embed)
        
        cleaned_files = 0
        freed_space = 0
        
        try:
            # Clean downloads directory
            downloads_dir = settings.downloads_dir
            if downloads_dir.exists():
                for file_path in downloads_dir.iterdir():
                    if file_path.is_file():
                        try:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            cleaned_files += 1
                            freed_space += file_size
                        except Exception as e:
                            self.logger.warning("Failed to delete file", file=str(file_path), error=str(e))
            
            # Clean cache
            expired_count = await cache_manager.cleanup_expired()
            
            # Format freed space
            freed_mb = freed_space / 1024 / 1024
            
            embed = discord.Embed(
                title="✅ Cleanup abgeschlossen",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📊 Ergebnisse",
                value=f"**Dateien gelöscht:** {cleaned_files}\n"
                      f"**Speicher freigegeben:** {freed_mb:.1f} MB\n"
                      f"**Cache-Einträge:** {expired_count}",
                inline=False
            )
            
            await message.edit(embed=embed)
            self.logger.info("Cleanup completed", files=cleaned_files, space_mb=freed_mb)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Cleanup fehlgeschlagen",
                description=f"Fehler: {str(e)}",
                color=discord.Color.red()
            )
            await message.edit(embed=embed)
            self.logger.error("Cleanup failed", error=str(e))
        
        self.log_command(ctx, 'cleanup')

    @commands.hybrid_command(name="logs")
    @commands.has_permissions(administrator=True)
    async def logs(self, ctx: commands.Context, lines: int = 50):
        """Show recent log entries."""
        if lines > 100:
            lines = 100
        
        try:
            log_file = settings.logs_dir / "bot.log"
            if not log_file.exists():
                await ctx.send("❌ Log-Datei nicht gefunden.", ephemeral=True)
                return
            
            # Read last N lines
            with open(log_file, 'r', encoding='utf-8') as f:
                log_lines = f.readlines()
            
            recent_lines = log_lines[-lines:]
            log_content = ''.join(recent_lines)
            
            # Truncate if too long for Discord
            if len(log_content) > 1900:
                log_content = log_content[-1900:]
                log_content = "...\n" + log_content
            
            embed = discord.Embed(
                title=f"📋 Letzte {len(recent_lines)} Log-Einträge",
                description=f"```\n{log_content}\n```",
                color=discord.Color.blue()
            )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"❌ Fehler beim Lesen der Logs: {str(e)}", ephemeral=True)
            self.logger.error("Failed to read logs", error=str(e))
        
        self.log_command(ctx, 'logs', lines=lines)

    @commands.hybrid_command(name="config")
    @commands.has_permissions(administrator=True)
    async def config(self, ctx: commands.Context):
        """Show current bot configuration."""
        embed = discord.Embed(
            title="⚙️ Bot Konfiguration",
            color=discord.Color.blue()
        )
        
        # Music settings
        embed.add_field(
            name="🎵 Musik",
            value=f"**Max Queue:** {settings.max_queue_size}\n"
                  f"**Max Song Duration:** {settings.max_song_duration}s\n"
                  f"**Download Timeout:** {settings.download_timeout}s\n"
                  f"**Concurrent Downloads:** {settings.max_concurrent_downloads}",
            inline=True
        )
        
        # System settings
        embed.add_field(
            name="💻 System",
            value=f"**Max Memory:** {settings.max_memory_usage_mb} MB\n"
                  f"**Cleanup Interval:** {settings.cleanup_interval}s\n"
                  f"**Log Level:** {settings.log_level}\n"
                  f"**JSON Logging:** {'✅' if settings.enable_json_logging else '❌'}",
            inline=True
        )
        
        # Features
        embed.add_field(
            name="🔧 Features",
            value=f"**Slash Commands:** {'✅' if settings.enable_slash_commands else '❌'}\n"
                  f"**Auto Disconnect:** {'✅' if settings.enable_auto_disconnect else '❌'}\n"
                  f"**Metrics:** {'✅' if settings.enable_metrics else '❌'}\n"
                  f"**User Playlists:** {'✅' if settings.enable_user_playlists else '❌'}",
            inline=True
        )
        
        await ctx.send(embed=embed, ephemeral=True)
        self.log_command(ctx, 'config')

    @commands.hybrid_command(name="reload")
    @commands.has_permissions(administrator=True)
    async def reload_cog(self, ctx: commands.Context, cog_name: str = None):
        """Reload a specific cog or all cogs."""
        if cog_name:
            try:
                await self.bot.reload_extension(f'cogs.{cog_name}')
                embed = discord.Embed(
                    title="✅ Cog neu geladen",
                    description=f"Cog `{cog_name}` wurde erfolgreich neu geladen.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed, ephemeral=True)
                self.logger.info("Cog reloaded", cog=cog_name)
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Fehler beim Neuladen",
                    description=f"Fehler beim Neuladen von `{cog_name}`: {str(e)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, ephemeral=True)
                self.logger.error("Failed to reload cog", cog=cog_name, error=str(e))
        else:
            # Reload all cogs
            cogs_to_reload = ['music', 'admin']
            reloaded = []
            failed = []
            
            for cog in cogs_to_reload:
                try:
                    await self.bot.reload_extension(f'cogs.{cog}')
                    reloaded.append(cog)
                except Exception as e:
                    failed.append(f"{cog}: {str(e)}")
            
            embed = discord.Embed(
                title="🔄 Cogs neu geladen",
                color=discord.Color.green() if not failed else discord.Color.orange()
            )
            
            if reloaded:
                embed.add_field(
                    name="✅ Erfolgreich",
                    value="\n".join(reloaded),
                    inline=False
                )
            
            if failed:
                embed.add_field(
                    name="❌ Fehlgeschlagen",
                    value="\n".join(failed),
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
        
        self.log_command(ctx, 'reload', cog=cog_name)

    @restart.error
    @cleanup.error
    @logs.error
    @config.error
    @reload_cog.error
    async def admin_command_error(self, ctx, error):
        """Handle admin command errors."""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Keine Berechtigung",
                description="Du benötigst Administrator-Rechte für diesen Befehl.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            self.logger.warning("Unauthorized admin command attempt", user=ctx.author.id, command=ctx.command.name)
        else:
            self.logger.error("Admin command error", error=str(error), command=ctx.command.name)

async def setup(bot):
    await bot.add_cog(Admin(bot))