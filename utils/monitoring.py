"""Enhanced monitoring and metrics for the music bot."""

import asyncio
import psutil
import time
from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from config.settings import settings
from utils.logger import get_logger

logger = get_logger('monitoring')

# Prometheus metrics
commands_total = Counter('bot_commands_total', 'Total commands executed', ['command', 'status'])
command_duration = Histogram('bot_command_duration_seconds', 'Command execution time', ['command'])
active_voice_connections = Gauge('bot_voice_connections_active', 'Active voice connections')
queue_size = Gauge('bot_queue_size', 'Current queue size', ['guild'])
memory_usage = Gauge('bot_memory_usage_bytes', 'Memory usage in bytes')
cpu_usage = Gauge('bot_cpu_usage_percent', 'CPU usage percentage')
downloads_total = Counter('bot_downloads_total', 'Total downloads', ['status'])
download_duration = Histogram('bot_download_duration_seconds', 'Download duration')

class PerformanceMonitor:
    """Enhanced performance monitoring system."""
    
    def __init__(self):
        self.start_time = time.time()
        self.command_stats: Dict[str, Dict[str, Any]] = {}
        self.system_stats: Dict[str, Any] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        
        if settings.enable_metrics:
            self._start_metrics_server()
    
    def _start_metrics_server(self):
        """Start Prometheus metrics server."""
        try:
            start_http_server(settings.metrics_port)
            logger.info("Metrics server started", port=settings.metrics_port)
        except Exception as e:
            logger.error("Failed to start metrics server", error=str(e))
    
    async def start_monitoring(self):
        """Start background monitoring tasks."""
        if not self._monitoring_task:
            self._monitoring_task = asyncio.create_task(self._monitor_system())
            logger.info("Performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring tasks."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Performance monitoring stopped")
    
    async def _monitor_system(self):
        """Monitor system resources periodically."""
        while True:
            try:
                # Update system metrics
                process = psutil.Process()
                memory_info = process.memory_info()
                cpu_percent = process.cpu_percent()
                
                self.system_stats.update({
                    'memory_rss': memory_info.rss,
                    'memory_vms': memory_info.vms,
                    'cpu_percent': cpu_percent,
                    'uptime': time.time() - self.start_time
                })
                
                # Update Prometheus metrics
                if settings.enable_metrics:
                    memory_usage.set(memory_info.rss)
                    cpu_usage.set(cpu_percent)
                
                # Check memory usage
                memory_mb = memory_info.rss / 1024 / 1024
                if memory_mb > settings.max_memory_usage_mb:
                    logger.warning(
                        "High memory usage detected",
                        memory_mb=memory_mb,
                        limit_mb=settings.max_memory_usage_mb
                    )
                
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                logger.error("Error in system monitoring", error=str(e))
                await asyncio.sleep(60)
    
    def record_command(self, command_name: str, duration: float, success: bool = True):
        """Record command execution metrics."""
        status = 'success' if success else 'error'
        
        # Update internal stats
        if command_name not in self.command_stats:
            self.command_stats[command_name] = {
                'total_calls': 0,
                'total_duration': 0,
                'success_count': 0,
                'error_count': 0
            }
        
        stats = self.command_stats[command_name]
        stats['total_calls'] += 1
        stats['total_duration'] += duration
        
        if success:
            stats['success_count'] += 1
        else:
            stats['error_count'] += 1
        
        # Update Prometheus metrics
        if settings.enable_metrics:
            commands_total.labels(command=command_name, status=status).inc()
            command_duration.labels(command=command_name).observe(duration)
        
        logger.debug(
            "Command recorded",
            command=command_name,
            duration=duration,
            success=success
        )
    
    def record_download(self, duration: float, success: bool = True):
        """Record download metrics."""
        status = 'success' if success else 'error'
        
        if settings.enable_metrics:
            downloads_total.labels(status=status).inc()
            if success:
                download_duration.observe(duration)
    
    def update_voice_connections(self, count: int):
        """Update voice connection count."""
        if settings.enable_metrics:
            active_voice_connections.set(count)
    
    def update_queue_size(self, guild_id: str, size: int):
        """Update queue size for a guild."""
        if settings.enable_metrics:
            queue_size.labels(guild=guild_id).set(size)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return {
            'uptime': time.time() - self.start_time,
            'system_stats': self.system_stats,
            'command_stats': self.command_stats,
            'total_commands': sum(stats['total_calls'] for stats in self.command_stats.values())
        }

# Global monitor instance
performance_monitor = PerformanceMonitor()