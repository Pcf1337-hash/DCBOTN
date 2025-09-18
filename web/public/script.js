// Socket.IO connection
const socket = io();

// DOM elements
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebarToggle');
const navItems = document.querySelectorAll('.nav-item');
const pages = document.querySelectorAll('.page');
const pageTitle = document.getElementById('pageTitle');
const connectionStatus = document.getElementById('connectionStatus');
const toastContainer = document.getElementById('toastContainer');
const loadingOverlay = document.getElementById('loadingOverlay');

// State
let currentPage = 'dashboard';
let botState = {};
let autoScrollLogs = true;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    initializeSocketListeners();
    showLoading();
});

// Event Listeners
function initializeEventListeners() {
    // Sidebar toggle
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });

    // Navigation
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            navigateToPage(page);
        });
    });

    // Dashboard quick actions
    document.getElementById('quickPlay')?.addEventListener('click', () => {
        const input = prompt('YouTube URL oder Suchbegriff:');
        if (input) playMusic(input);
    });

    document.getElementById('quickPause')?.addEventListener('click', pauseMusic);
    document.getElementById('quickStop')?.addEventListener('click', stopMusic);
    document.getElementById('quickShuffle')?.addEventListener('click', shuffleQueue);

    // Music player controls
    document.getElementById('playPauseBtn')?.addEventListener('click', togglePlayPause);
    document.getElementById('nextBtn')?.addEventListener('click', skipSong);
    document.getElementById('shuffleBtn')?.addEventListener('click', shuffleQueue);
    document.getElementById('repeatBtn')?.addEventListener('click', toggleRepeat);
    document.getElementById('addSongBtn')?.addEventListener('click', addSong);

    // Volume control
    const volumeSlider = document.getElementById('volumeSlider');
    if (volumeSlider) {
        volumeSlider.addEventListener('input', (e) => {
            setVolume(parseInt(e.target.value));
        });
    }

    // Queue controls
    document.getElementById('shuffleQueueBtn')?.addEventListener('click', shuffleQueue);
    document.getElementById('clearQueueBtn')?.addEventListener('click', clearQueue);

    // Log controls
    document.getElementById('clearLogsBtn')?.addEventListener('click', clearLogs);
    document.getElementById('autoScrollBtn')?.addEventListener('click', toggleAutoScroll);

    // Settings
    document.getElementById('saveSettingsBtn')?.addEventListener('click', saveSettings);
    document.getElementById('resetSettingsBtn')?.addEventListener('click', resetSettings);

    // Refresh button
    document.getElementById('refreshBtn')?.addEventListener('click', refreshData);

    // Close sidebar on mobile when clicking outside
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 1024 && !sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });
}

// Socket.IO listeners
function initializeSocketListeners() {
    socket.on('connect', () => {
        updateConnectionStatus(true);
        hideLoading();
        showToast('Verbindung hergestellt', 'success');
    });

    socket.on('disconnect', () => {
        updateConnectionStatus(false);
        showToast('Verbindung verloren', 'error');
    });

    socket.on('bot-state', (state) => {
        botState = state;
        updateUI();
    });

    socket.on('new-log', (logEntry) => {
        addLogEntry(logEntry);
    });

    socket.on('logs', (logs) => {
        displayLogs(logs);
    });

    socket.on('queue-update', (queue) => {
        botState.queue = queue;
        updateQueue();
    });

    socket.on('song-update', (song) => {
        botState.currentSong = song;
        updateNowPlaying();
    });
}

// Navigation
function navigateToPage(page) {
    // Update active nav item
    navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });

    // Show/hide pages
    pages.forEach(pageEl => {
        pageEl.classList.toggle('active', pageEl.id === page);
    });

    // Update page title
    const titles = {
        dashboard: 'Dashboard',
        player: 'Music Player',
        queue: 'Queue',
        logs: 'Logs',
        settings: 'Settings'
    };
    pageTitle.textContent = titles[page] || 'Dashboard';

    currentPage = page;

    // Close sidebar on mobile
    if (window.innerWidth <= 1024) {
        sidebar.classList.remove('open');
    }

    // Load page-specific data
    loadPageData(page);
}

function loadPageData(page) {
    switch (page) {
        case 'logs':
            requestLogs();
            break;
        case 'queue':
            updateQueue();
            break;
        case 'player':
            updateNowPlaying();
            break;
    }
}

// UI Updates
function updateUI() {
    updateDashboard();
    updateNowPlaying();
    updateQueue();
    updatePlayerControls();
}

function updateDashboard() {
    // Update stats
    document.getElementById('guildCount').textContent = botState.guilds || 0;
    document.getElementById('userCount').textContent = formatNumber(botState.users || 0);
    document.getElementById('uptime').textContent = formatUptime(botState.uptime || 0);
    document.getElementById('voiceConnections').textContent = botState.voiceConnections || 0;

    // Update performance metrics
    const cpuProgress = document.getElementById('cpuProgress');
    const memoryProgress = document.getElementById('memoryProgress');
    const cpuValue = document.getElementById('cpuValue');
    const memoryValue = document.getElementById('memoryValue');

    if (cpuProgress && botState.cpu !== undefined) {
        cpuProgress.style.width = `${botState.cpu}%`;
        cpuValue.textContent = `${botState.cpu.toFixed(1)}%`;
    }

    if (memoryProgress && botState.memory !== undefined) {
        const memoryPercent = Math.min((botState.memory / 512) * 100, 100); // Assuming 512MB limit
        memoryProgress.style.width = `${memoryPercent}%`;
        memoryValue.textContent = `${botState.memory.toFixed(1)} MB`;
    }
}

function updateNowPlaying() {
    const songTitle = document.getElementById('songTitle');
    const songArtist = document.getElementById('songArtist');
    const albumArt = document.getElementById('albumArt');
    const currentTime = document.getElementById('currentTime');
    const totalTime = document.getElementById('totalTime');
    const songProgress = document.getElementById('songProgress');

    if (botState.currentSong) {
        const song = botState.currentSong;
        songTitle.textContent = song.title || 'Unbekannter Titel';
        songArtist.textContent = song.artist || song.uploader || 'Unbekannter Künstler';

        // Update album art
        if (song.thumbnail) {
            albumArt.innerHTML = `<img src="${song.thumbnail}" alt="Album Art">`;
        } else {
            albumArt.innerHTML = '<i class="fas fa-music"></i>';
        }

        // Update progress
        if (song.duration && song.currentTime !== undefined) {
            const progress = (song.currentTime / song.duration) * 100;
            songProgress.style.width = `${progress}%`;
            currentTime.textContent = formatTime(song.currentTime);
            totalTime.textContent = formatTime(song.duration);
        }
    } else {
        songTitle.textContent = 'Kein Song wird abgespielt';
        songArtist.textContent = '-';
        albumArt.innerHTML = '<i class="fas fa-music"></i>';
        songProgress.style.width = '0%';
        currentTime.textContent = '0:00';
        totalTime.textContent = '0:00';
    }
}

function updateQueue() {
    const queueList = document.getElementById('queueList');
    const queueCount = document.getElementById('queueCount');
    const totalDuration = document.getElementById('totalDuration');

    if (!queueList) return;

    const queue = botState.queue || [];
    queueCount.textContent = queue.length;

    if (queue.length === 0) {
        queueList.innerHTML = `
            <div class="empty-queue">
                <i class="fas fa-music"></i>
                <p>Die Warteschlange ist leer</p>
                <p>Füge Songs über den Music Player hinzu</p>
            </div>
        `;
        totalDuration.textContent = '0:00';
        return;
    }

    // Calculate total duration
    const total = queue.reduce((sum, song) => sum + (song.duration || 0), 0);
    totalDuration.textContent = formatTime(total);

    // Render queue items
    queueList.innerHTML = queue.map((song, index) => `
        <div class="queue-item">
            <div class="queue-item-number">${index + 1}</div>
            <div class="queue-item-thumbnail">
                ${song.thumbnail ? 
                    `<img src="${song.thumbnail}" alt="Thumbnail">` : 
                    '<i class="fas fa-music"></i>'
                }
            </div>
            <div class="queue-item-info">
                <div class="queue-item-title">${song.title || 'Unbekannter Titel'}</div>
                <div class="queue-item-artist">${song.artist || song.uploader || 'Unbekannter Künstler'}</div>
            </div>
            <div class="queue-item-duration">${formatTime(song.duration || 0)}</div>
            <div class="queue-item-actions">
                <button onclick="removeFromQueue(${index + 1})" title="Entfernen">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

function updatePlayerControls() {
    const playPauseBtn = document.getElementById('playPauseBtn');
    const shuffleBtn = document.getElementById('shuffleBtn');
    const repeatBtn = document.getElementById('repeatBtn');
    const volumeSlider = document.getElementById('volumeSlider');
    const volumeValue = document.getElementById('volumeValue');

    if (playPauseBtn) {
        const isPlaying = botState.isPlaying && !botState.isPaused;
        playPauseBtn.innerHTML = isPlaying ? 
            '<i class="fas fa-pause"></i>' : 
            '<i class="fas fa-play"></i>';
    }

    if (shuffleBtn) {
        shuffleBtn.classList.toggle('active', botState.shuffleMode);
    }

    if (repeatBtn) {
        repeatBtn.classList.toggle('active', botState.repeatMode);
    }

    if (volumeSlider && botState.volume !== undefined) {
        volumeSlider.value = botState.volume;
        volumeValue.textContent = `${botState.volume}%`;
    }
}

function updateConnectionStatus(connected) {
    const indicator = connectionStatus.querySelector('.status-indicator');
    const text = connectionStatus.querySelector('span');

    if (connected) {
        indicator.classList.remove('offline');
        indicator.classList.add('online');
        text.textContent = 'Online';
    } else {
        indicator.classList.remove('online');
        indicator.classList.add('offline');
        text.textContent = 'Offline';
    }
}

// Music Controls
async function playMusic(query) {
    try {
        showLoading();
        const response = await fetch('/api/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });

        const result = await response.json();
        if (result.success) {
            showToast('Song wird hinzugefügt...', 'success');
        } else {
            showToast(result.error || 'Fehler beim Hinzufügen', 'error');
        }
    } catch (error) {
        showToast('Netzwerkfehler', 'error');
    } finally {
        hideLoading();
    }
}

async function pauseMusic() {
    try {
        const response = await fetch('/api/pause', { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            showToast('Wiedergabe pausiert/fortgesetzt', 'info');
        }
    } catch (error) {
        showToast('Fehler beim Pausieren', 'error');
    }
}

async function stopMusic() {
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            showToast('Wiedergabe gestoppt', 'info');
        }
    } catch (error) {
        showToast('Fehler beim Stoppen', 'error');
    }
}

async function skipSong() {
    try {
        const response = await fetch('/api/skip', { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            showToast('Song übersprungen', 'info');
        }
    } catch (error) {
        showToast('Fehler beim Überspringen', 'error');
    }
}

async function setVolume(volume) {
    try {
        const response = await fetch('/api/volume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ volume })
        });

        const result = await response.json();
        if (result.success) {
            document.getElementById('volumeValue').textContent = `${volume}%`;
        }
    } catch (error) {
        showToast('Fehler beim Ändern der Lautstärke', 'error');
    }
}

async function shuffleQueue() {
    try {
        const response = await fetch('/api/shuffle', { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            showToast('Warteschlange gemischt', 'info');
        }
    } catch (error) {
        showToast('Fehler beim Mischen', 'error');
    }
}

async function clearQueue() {
    if (!confirm('Möchten Sie die gesamte Warteschlange löschen?')) return;

    try {
        const response = await fetch('/api/clear', { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            showToast('Warteschlange geleert', 'info');
        }
    } catch (error) {
        showToast('Fehler beim Leeren', 'error');
    }
}

async function removeFromQueue(index) {
    try {
        const response = await fetch('/api/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ index })
        });

        const result = await response.json();
        if (result.success) {
            showToast('Song entfernt', 'info');
        }
    } catch (error) {
        showToast('Fehler beim Entfernen', 'error');
    }
}

function togglePlayPause() {
    pauseMusic();
}

async function toggleRepeat() {
    try {
        const response = await fetch('/api/repeat', { method: 'POST' });
        const result = await response.json();
        if (result.success) {
            showToast('Wiederholung umgeschaltet', 'info');
        }
    } catch (error) {
        showToast('Fehler beim Umschalten', 'error');
    }
}

function addSong() {
    const input = document.getElementById('songInput');
    const query = input.value.trim();
    
    if (!query) {
        showToast('Bitte geben Sie eine URL oder einen Suchbegriff ein', 'warning');
        return;
    }

    playMusic(query);
    input.value = '';
}

// Logs
function addLogEntry(logEntry) {
    const logsContainer = document.getElementById('logsContainer');
    if (!logsContainer) return;

    const logElement = document.createElement('div');
    logElement.className = `log-entry ${logEntry.level.toLowerCase()}`;
    
    const time = new Date(logEntry.timestamp).toLocaleTimeString();
    logElement.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-level ${logEntry.level.toLowerCase()}">${logEntry.level}</span>
        <span class="log-message">${logEntry.message}</span>
    `;

    logsContainer.appendChild(logElement);

    // Remove old entries (keep last 1000)
    const entries = logsContainer.querySelectorAll('.log-entry');
    if (entries.length > 1000) {
        entries[0].remove();
    }

    // Auto scroll
    if (autoScrollLogs) {
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }
}

function displayLogs(logs) {
    const logsContainer = document.getElementById('logsContainer');
    if (!logsContainer) return;

    logsContainer.innerHTML = logs.map(log => {
        const time = new Date(log.timestamp).toLocaleTimeString();
        return `
            <div class="log-entry ${log.level.toLowerCase()}">
                <span class="log-time">${time}</span>
                <span class="log-level ${log.level.toLowerCase()}">${log.level}</span>
                <span class="log-message">${log.message}</span>
            </div>
        `;
    }).join('');

    if (autoScrollLogs) {
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }
}

function clearLogs() {
    const logsContainer = document.getElementById('logsContainer');
    if (logsContainer) {
        logsContainer.innerHTML = '';
        showToast('Logs geleert', 'info');
    }
}

function toggleAutoScroll() {
    const btn = document.getElementById('autoScrollBtn');
    autoScrollLogs = !autoScrollLogs;
    
    btn.dataset.enabled = autoScrollLogs;
    btn.innerHTML = autoScrollLogs ? 
        '<i class="fas fa-arrow-down"></i> Auto Scroll' : 
        '<i class="fas fa-pause"></i> Manual Scroll';
    
    showToast(`Auto Scroll ${autoScrollLogs ? 'aktiviert' : 'deaktiviert'}`, 'info');
}

function requestLogs() {
    socket.emit('request-logs');
}

// Settings
function saveSettings() {
    const settings = {
        commandPrefix: document.getElementById('commandPrefix')?.value,
        maxQueueSize: parseInt(document.getElementById('maxQueueSize')?.value),
        autoDisconnectTimeout: parseInt(document.getElementById('autoDisconnectTimeout')?.value),
        darkMode: document.getElementById('darkMode')?.checked,
        notifications: document.getElementById('notifications')?.checked,
        autoRefresh: document.getElementById('autoRefresh')?.checked
    };

    // Save to localStorage
    localStorage.setItem('botSettings', JSON.stringify(settings));
    
    // Send to server
    socket.emit('update-settings', settings);
    
    showToast('Einstellungen gespeichert', 'success');
}

function resetSettings() {
    if (!confirm('Möchten Sie alle Einstellungen zurücksetzen?')) return;

    // Reset form values
    document.getElementById('commandPrefix').value = '!';
    document.getElementById('maxQueueSize').value = '100';
    document.getElementById('autoDisconnectTimeout').value = '300';
    document.getElementById('darkMode').checked = true;
    document.getElementById('notifications').checked = true;
    document.getElementById('autoRefresh').checked = true;

    // Clear localStorage
    localStorage.removeItem('botSettings');
    
    showToast('Einstellungen zurückgesetzt', 'info');
}

function loadSettings() {
    const saved = localStorage.getItem('botSettings');
    if (!saved) return;

    try {
        const settings = JSON.parse(saved);
        
        if (settings.commandPrefix) document.getElementById('commandPrefix').value = settings.commandPrefix;
        if (settings.maxQueueSize) document.getElementById('maxQueueSize').value = settings.maxQueueSize;
        if (settings.autoDisconnectTimeout) document.getElementById('autoDisconnectTimeout').value = settings.autoDisconnectTimeout;
        if (settings.darkMode !== undefined) document.getElementById('darkMode').checked = settings.darkMode;
        if (settings.notifications !== undefined) document.getElementById('notifications').checked = settings.notifications;
        if (settings.autoRefresh !== undefined) document.getElementById('autoRefresh').checked = settings.autoRefresh;
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// Utility Functions
function formatTime(seconds) {
    if (!seconds || seconds < 0) return '0:00';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function formatUptime(seconds) {
    if (!seconds) return '0s';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    }[type] || 'fas fa-info-circle';
    
    toast.innerHTML = `
        <i class="${icon}"></i>
        <span>${message}</span>
    `;
    
    toastContainer.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

function showLoading() {
    loadingOverlay.classList.add('active');
}

function hideLoading() {
    loadingOverlay.classList.remove('active');
}

function refreshData() {
    socket.emit('request-update');
    showToast('Daten werden aktualisiert...', 'info');
}

// Initialize settings on load
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
});

// Auto-refresh every 30 seconds
setInterval(() => {
    const autoRefresh = document.getElementById('autoRefresh')?.checked;
    if (autoRefresh && socket.connected) {
        socket.emit('request-update');
    }
}, 30000);

// Handle song input enter key
document.getElementById('songInput')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        addSong();
    }
});

// Handle progress bar clicks
document.querySelector('.progress-bar-large')?.addEventListener('click', (e) => {
    if (!botState.currentSong || !botState.currentSong.duration) return;
    
    const rect = e.target.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    const seekTime = percent * botState.currentSong.duration;
    
    // Send seek command to bot
    socket.emit('bot-command', { command: 'seek', args: [seekTime] });
});