import discord
from discord.ext import commands
import asyncio
import logging
import os
from dotenv import load_dotenv
from config.settings import settings
from utils.logger import setup_logger, get_logger
from utils.monitoring import performance_monitor
from utils.cache import cache_manager
from utils.exceptions import *
from web_integration import setup_web_integration
import time

load_dotenv()

class GrooveMaster(commands.Bot):
    """Enhanced Discord music bot with modern features and monitoring."""
    
    def __init__(self):
        # Enhanced intents for better functionality
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        intents.guild_messages = True
        
        super().__init__(
            command_prefix=self._get_prefix,
            intents=intents,
            help_command=None,  # We'll create a custom help command
            case_insensitive=True,
            strip_after_prefix=True
        )
        
        self.logger = get_logger('bot')
        self.start_time = time.time()
        self.owner_ids = set(settings.owner_ids)
        
        # Setup web integration
        self.web_integration = setup_web_integration(self)
        
        # Performance tracking
        self.command_count = 0
        self.error_count = 0

    async def _get_prefix(self, bot, message):
        """Dynamic prefix support."""
        # Could be extended to support per-guild prefixes from database
        return commands.when_mentioned_or(settings.command_prefix)(bot, message)

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        self.logger.info("Setting up bot...")
        
        # Load cogs
        try:
            await self.load_extension('cogs.music')
            await self.load_extension('cogs.admin')
            self.logger.info("All cogs loaded successfully")
        except Exception as e:
            self.logger.error("Failed to load cogs", error=str(e))
            raise
        
        # Start monitoring
        if settings.enable_metrics:
            await performance_monitor.start_monitoring()
        
        # Start web integration
        if settings.enable_web_interface:
            try:
                await self.web_integration.start()
            except Exception as e:
                self.logger.error("Failed to start web integration", error=str(e))
        
        self.logger.info("Bot setup completed")

    async def on_ready(self):
        """Called when bot is ready."""
        self.logger.info(
            "Bot is ready",
            bot_name=self.user.name,
            bot_id=self.user.id,
            guild_count=len(self.guilds),
            user_count=sum(guild.member_count for guild in self.guilds)
        )
        
        # Set presence
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{settings.command_prefix}help | {len(self.guilds)} servers"
        )
        await self.change_presence(activity=activity)
        
        # Update monitoring
        performance_monitor.update_voice_connections(
            sum(1 for guild in self.guilds if guild.voice_client)
        )

    async def on_guild_join(self, guild):
        """Called when bot joins a guild."""
        self.logger.info("Joined guild", guild_name=guild.name, guild_id=guild.id, member_count=guild.member_count)
        
        # Update presence
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{settings.command_prefix}help | {len(self.guilds)} servers"
        )
        await self.change_presence(activity=activity)

    async def on_guild_remove(self, guild):
        """Called when bot leaves a guild."""
        self.logger.info("Left guild", guild_name=guild.name, guild_id=guild.id)
        
        # Update presence
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{settings.command_prefix}help | {len(self.guilds)} servers"
        )
        await self.change_presence(activity=activity)

    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates for auto-disconnect."""
        if member == self.user:
            return
        
        # Check if bot is alone in voice channel
        for guild in self.guilds:
            if guild.voice_client and guild.voice_client.channel:
                members = [m for m in guild.voice_client.channel.members if not m.bot]
                if len(members) == 0:
                    # Bot is alone, start disconnect timer
                    music_cog = self.get_cog('Music')
                    if music_cog and settings.enable_auto_disconnect:
                        self.logger.info("Bot alone in voice channel, starting disconnect timer")
                        # The music cog will handle auto-disconnect

    async def on_command(self, ctx):
        """Called when a command is invoked."""
        self.command_count += 1
        self.logger.debug(
            "Command invoked",
            command=ctx.command.name,
            user=ctx.author.name,
            guild=ctx.guild.name if ctx.guild else "DM"
        )

    async def on_command_completion(self, ctx):
        """Called when a command completes successfully."""
        duration = time.time() - ctx.message.created_at.timestamp()
        performance_monitor.record_command(ctx.command.name, duration, True)

    async def on_command_error(self, ctx, error):
        """Enhanced error handling with better user feedback."""
        self.error_count += 1
        
        # Record error in monitoring
        if hasattr(ctx, 'command') and ctx.command:
            duration = time.time() - ctx.message.created_at.timestamp()
            performance_monitor.record_command(ctx.command.name, duration, False)
        
        # Handle specific error types
        if isinstance(error, commands.CommandNotFound):
            # Silently ignore unknown commands
            return
            
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Fehlender Parameter",
                description=f"Der Parameter `{error.param.name}` ist erforderlich.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Hilfe",
                value=f"Verwende `{settings.command_prefix}help {ctx.command}` für mehr Informationen.",
                inline=False
            )
            await ctx.send(embed=embed, delete_after=15)
            
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ Ungültiger Parameter",
                description="Ein oder mehrere Parameter sind ungültig.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Hilfe",
                value=f"Verwende `{settings.command_prefix}help {ctx.command}` für mehr Informationen.",
                inline=False
            )
            await ctx.send(embed=embed, delete_after=15)
            
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Fehlende Berechtigungen",
                description="Du hast nicht die erforderlichen Berechtigungen für diesen Befehl.",
                color=discord.Color.red()
            )
            missing_perms = ", ".join(error.missing_permissions)
            embed.add_field(name="Benötigte Berechtigungen", value=missing_perms, inline=False)
            await ctx.send(embed=embed, delete_after=15)
            
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="❌ Bot-Berechtigungen fehlen",
                description="Dem Bot fehlen die erforderlichen Berechtigungen.",
                color=discord.Color.red()
            )
            missing_perms = ", ".join(error.missing_permissions)
            embed.add_field(name="Fehlende Berechtigungen", value=missing_perms, inline=False)
            await ctx.send(embed=embed, delete_after=15)
            
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ Dieser Befehl kann nicht in privaten Nachrichten verwendet werden.", delete_after=10)
            
        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Befehl im Cooldown",
                description=f"Versuche es in {error.retry_after:.1f} Sekunden erneut.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed, delete_after=10)
            
        elif isinstance(error, commands.MaxConcurrencyReached):
            embed = discord.Embed(
                title="⚠️ Zu viele gleichzeitige Verwendungen",
                description="Dieser Befehl wird bereits zu oft gleichzeitig verwendet.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed, delete_after=10)
            
        # Handle custom exceptions
        elif isinstance(error, commands.CommandInvokeError):
            original_error = error.original
            
            if isinstance(original_error, QueueFullError):
                embed = discord.Embed(
                    title="📋 Warteschlange voll",
                    description=f"Die Warteschlange ist voll (max. {settings.max_queue_size} Songs).",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed, delete_after=15)
                
            elif isinstance(original_error, AudioDownloadError):
                embed = discord.Embed(
                    title="❌ Download-Fehler",
                    description="Der Song konnte nicht heruntergeladen werden.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=15)
                
            elif isinstance(original_error, VoiceConnectionError):
                embed = discord.Embed(
                    title="❌ Verbindungsfehler",
                    description="Fehler beim Verbinden mit dem Sprachkanal.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=15)
                
            else:
                # Log unexpected errors
                self.logger.error(
                    "Unexpected command error",
                    command=ctx.command.name if ctx.command else "Unknown",
                    error=str(original_error),
                    user=ctx.author.id,
                    guild=ctx.guild.id if ctx.guild else None
                )
                
                embed = discord.Embed(
                    title="❌ Unerwarteter Fehler",
                    description="Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es später erneut.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, delete_after=15)
        else:
            # Log other errors
            self.logger.error(
                "Unhandled command error",
                error_type=type(error).__name__,
                error=str(error),
                command=ctx.command.name if ctx.command else "Unknown"
            )

    async def on_error(self, event, *args, **kwargs):
        """Handle general bot errors."""
        self.logger.error(f"Error in event {event}", exc_info=True)

    async def close(self):
        """Cleanup when bot is shutting down."""
        self.logger.info("Bot is shutting down...")
        
        # Save cache
        await cache_manager.save_cache()
        
        # Stop monitoring
        if settings.enable_metrics:
            await performance_monitor.stop_monitoring()
        
        # Stop web integration
        if hasattr(self, 'web_integration'):
            await self.web_integration.stop()
        
        # Cleanup music cog
        music_cog = self.get_cog('Music')
        if music_cog:
            await music_cog.cleanup_all()
        
        await super().close()
        self.logger.info("Bot shutdown complete")

    def get_uptime(self) -> float:
        """Get bot uptime in seconds."""
        return time.time() - self.start_time

    def get_stats(self) -> dict:
        """Get bot statistics."""
        return {
            'uptime': self.get_uptime(),
            'guild_count': len(self.guilds),
            'user_count': sum(guild.member_count for guild in self.guilds),
            'command_count': self.command_count,
            'error_count': self.error_count,
            'voice_connections': sum(1 for guild in self.guilds if guild.voice_client)
        }

# Create and run bot
async def main():
    """Main bot runner with proper error handling."""
    bot = GrooveMaster()
    
    try:
        async with bot:
            await bot.start(settings.discord_token)
    except KeyboardInterrupt:
        bot.logger.info("Bot interrupted by user")
    except Exception as e:
        bot.logger.error("Fatal error", error=str(e))
        raise
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    # Setup basic logging for startup
    setup_logger()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")