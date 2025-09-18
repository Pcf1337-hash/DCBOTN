"""
Web Interface Integration für Discord Music Bot
Verbindet den Discord Bot mit dem Web Interface über Socket.IO
"""

import asyncio
import threading
import time
import psutil
import json
from typing import Dict, Any, Optional
from socketio import AsyncClient
from utils.logger import get_logger
from config.settings import settings

logger = get_logger('web_integration')

class WebIntegration:
    """Integration zwischen Discord Bot und Web Interface."""
    
    def __init__(self, bot):
        self.bot = bot
        self.sio = AsyncClient()
        self.connected = False
        self.web_server_url = f"http://localhost:{settings.web_port}"
        self.update_task: Optional[asyncio.Task] = None
        
        # Setup event handlers
        self.setup_socket_handlers()
    
    def setup_socket_handlers(self):
        """Setup Socket.IO event handlers."""
        
        @self.sio.event
        async def connect():
            self.connected = True
            logger.info("Connected to web interface")
            await self.send_initial_state()
        
        @self.sio.event
        async def disconnect():
            self.connected = False
            logger.info("Disconnected from web interface")
        
        @self.sio.on('bot-command')
        async def handle_bot_command(data):
            """Handle commands from web interface."""
            try:
                command = data.get('command')
                args = data.get('args', [])
                
                logger.info("Received web command", command=command, args=args)
                
                # Find a guild with voice connection or use first guild
                guild = None
                for g in self.bot.guilds:
                    if g.voice_client:
                        guild = g
                        break
                
                if not guild and self.bot.guilds:
                    guild = self.bot.guilds[0]
                
                if not guild:
                    logger.warning("No guild available for web command")
                    return
                
                # Create a mock context for commands
                channel = guild.text_channels[0] if guild.text_channels else None
                if not channel:
                    logger.warning("No text channel available for web command")
                    return
                
                # Get music cog
                music_cog = self.bot.get_cog('Music')
                if not music_cog:
                    logger.error("Music cog not found")
                    return
                
                # Execute command
                await self.execute_web_command(music_cog, guild, channel, command, args)
                
            except Exception as e:
                logger.error("Error handling web command", error=str(e))
        
        @self.sio.on('request-update')
        async def handle_update_request():
            """Handle update request from web interface."""
            await self.send_bot_state()
        
        @self.sio.on('request-logs')
        async def handle_logs_request():
            """Handle logs request from web interface."""
            await self.send_recent_logs()
        
        @self.sio.on('update-settings')
        async def handle_settings_update(data):
            """Handle settings update from web interface."""
            logger.info("Settings update received", settings=data)
            # Here you could update bot settings if needed
    
    async def execute_web_command(self, music_cog, guild, channel, command: str, args: list):
        """Execute a command from the web interface."""
        try:
            # Create a mock context
            class MockContext:
                def __init__(self, guild, channel, bot):
                    self.guild = guild
                    self.channel = channel
                    self.bot = bot
                    self.voice_client = guild.voice_client
                    self.author = bot.user  # Use bot as author
                
                async def send(self, content=None, **kwargs):
                    # Don't actually send messages for web commands
                    pass
            
            ctx = MockContext(guild, channel, self.bot)
            
            # Execute command based on type
            if command == 'play' and args:
                await music_cog.play(ctx, query=' '.join(args))
            elif command == 'skip':
                await music_cog.skip(ctx)
            elif command == 'pause':
                await music_cog.pause(ctx)
            elif command == 'stop':
                await music_cog.stop(ctx)
            elif command == 'volume' and args:
                await music_cog.volume(ctx, volume=int(args[0]))
            elif command == 'shuffle':
                await music_cog.shuffle(ctx)
            elif command == 'clear':
                await music_cog.clear_queue(ctx)
            elif command == 'remove' and args:
                await music_cog.remove(ctx, index=int(args[0]))
            elif command == 'repeat':
                await music_cog.repeat(ctx)
            elif command == 'seek' and args:
                # Implement seek functionality if available
                pass
            else:
                logger.warning("Unknown web command", command=command)
            
            # Send updated state after command
            await asyncio.sleep(0.5)  # Small delay to let command complete
            await self.send_bot_state()
            
        except Exception as e:
            logger.error("Error executing web command", command=command, error=str(e))
    
    async def start(self):
        """Start the web integration."""
        try:
            await self.sio.connect(self.web_server_url)
            
            # Start periodic updates
            self.update_task = asyncio.create_task(self.periodic_updates())
            
            logger.info("Web integration started")
            
        except Exception as e:
            logger.error("Failed to start web integration", error=str(e))
    
    async def stop(self):
        """Stop the web integration."""
        if self.update_task:
            self.update_task.cancel()
        
        if self.connected:
            await self.sio.disconnect()
        
        logger.info("Web integration stopped")
    
    async def periodic_updates(self):
        """Send periodic updates to web interface."""
        while True:
            try:
                if self.connected:
                    await self.send_bot_state()
                await asyncio.sleep(10)  # Update every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in periodic updates", error=str(e))
                await asyncio.sleep(30)  # Wait longer on error
    
    async def send_initial_state(self):
        """Send initial bot state to web interface."""
        await self.send_bot_state()
        await self.send_recent_logs()
    
    async def send_bot_state(self):
        """Send current bot state to web interface."""
        try:
            music_cog = self.bot.get_cog('Music')
            
            # Get system info
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()
            
            # Build state
            state = {
                'status': 'online' if self.bot.is_ready() else 'offline',
                'guilds': len(self.bot.guilds),
                'users': sum(guild.member_count for guild in self.bot.guilds),
                'uptime': time.time() - self.bot.start_time if hasattr(self.bot, 'start_time') else 0,
                'memory': memory_info.rss / 1024 / 1024,  # MB
                'cpu': cpu_percent,
                'voiceConnections': sum(1 for guild in self.bot.guilds if guild.voice_client),
                'currentSong': None,
                'queue': [],
                'volume': 80,
                'isPlaying': False,
                'isPaused': False,
                'repeatMode': False,
                'shuffleMode': False
            }
            
            # Add music-specific data if available
            if music_cog:
                state.update({
                    'volume': int(music_cog.volume * 100),
                    'isPlaying': music_cog.is_playing,
                    'isPaused': music_cog.is_paused() if hasattr(music_cog, 'is_paused') else False,
                    'repeatMode': music_cog.repeat_mode,
                    'shuffleMode': getattr(music_cog.queue_manager, 'shuffle_mode', False)
                })
                
                # Current song info
                if music_cog.current_song:
                    song = music_cog.current_song
                    current_time = music_cog.get_current_time_seconds()
                    
                    state['currentSong'] = {
                        'title': song.title,
                        'artist': getattr(song, 'uploader', ''),
                        'duration': song.duration,
                        'currentTime': current_time,
                        'thumbnail': getattr(song, 'thumbnail', ''),
                        'url': song.url
                    }
                
                # Queue info
                if hasattr(music_cog, 'queue_manager') and music_cog.queue_manager.queue:
                    state['queue'] = []
                    for song in music_cog.queue_manager.queue[:50]:  # Limit to 50 songs
                        state['queue'].append({
                            'title': song.title,
                            'artist': getattr(song, 'uploader', ''),
                            'duration': song.duration,
                            'thumbnail': getattr(song, 'thumbnail', ''),
                            'url': song.url,
                            'requester': song.requester.display_name
                        })
            
            await self.sio.emit('bot-state', state)
            
        except Exception as e:
            logger.error("Error sending bot state", error=str(e))
    
    async def send_recent_logs(self):
        """Send recent log entries to web interface."""
        try:
            # This would need to be implemented based on your logging system
            # For now, send a placeholder
            logs = [
                {
                    'timestamp': time.time() * 1000,
                    'level': 'INFO',
                    'message': 'Web interface connected'
                }
            ]
            
            await self.sio.emit('logs', logs)
            
        except Exception as e:
            logger.error("Error sending logs", error=str(e))
    
    async def send_log_entry(self, level: str, message: str):
        """Send a single log entry to web interface."""
        if not self.connected:
            return
        
        try:
            log_entry = {
                'timestamp': time.time() * 1000,
                'level': level.upper(),
                'message': message
            }
            
            await self.sio.emit('new-log', log_entry)
            
        except Exception as e:
            logger.error("Error sending log entry", error=str(e))
    
    async def notify_song_change(self, song=None):
        """Notify web interface of song change."""
        if not self.connected:
            return
        
        try:
            song_data = None
            if song:
                music_cog = self.bot.get_cog('Music')
                current_time = music_cog.get_current_time_seconds() if music_cog else 0
                
                song_data = {
                    'title': song.title,
                    'artist': getattr(song, 'uploader', ''),
                    'duration': song.duration,
                    'currentTime': current_time,
                    'thumbnail': getattr(song, 'thumbnail', ''),
                    'url': song.url
                }
            
            await self.sio.emit('song-update', song_data)
            
        except Exception as e:
            logger.error("Error notifying song change", error=str(e))
    
    async def notify_queue_change(self):
        """Notify web interface of queue change."""
        if not self.connected:
            return
        
        try:
            music_cog = self.bot.get_cog('Music')
            if not music_cog or not hasattr(music_cog, 'queue_manager'):
                return
            
            queue_data = []
            for song in music_cog.queue_manager.queue[:50]:  # Limit to 50 songs
                queue_data.append({
                    'title': song.title,
                    'artist': getattr(song, 'uploader', ''),
                    'duration': song.duration,
                    'thumbnail': getattr(song, 'thumbnail', ''),
                    'url': song.url,
                    'requester': song.requester.display_name
                })
            
            await self.sio.emit('queue-update', queue_data)
            
        except Exception as e:
            logger.error("Error notifying queue change", error=str(e))

# Global web integration instance
web_integration: Optional[WebIntegration] = None

def get_web_integration():
    """Get the global web integration instance."""
    return web_integration

def setup_web_integration(bot):
    """Setup web integration for the bot."""
    global web_integration
    web_integration = WebIntegration(bot)
    return web_integration