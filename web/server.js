const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');
const path = require('path');
const fs = require('fs');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

// Security middleware
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
            fontSrc: ["'self'", "https://fonts.gstatic.com"],
            scriptSrc: ["'self'", "'unsafe-inline'"],
            imgSrc: ["'self'", "data:", "https:", "http:"],
            connectSrc: ["'self'", "ws:", "wss:"]
        }
    }
}));

app.use(compression());
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Rate limiting
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100 // limit each IP to 100 requests per windowMs
});
app.use('/api', limiter);

// Bot state (will be updated by Python bot)
let botState = {
    status: 'offline',
    guilds: 0,
    users: 0,
    uptime: 0,
    memory: 0,
    cpu: 0,
    currentSong: null,
    queue: [],
    volume: 80,
    isPlaying: false,
    isPaused: false,
    repeatMode: false,
    voiceConnections: 0
};

let logs = [];
const MAX_LOGS = 1000;

// API Routes
app.get('/api/status', (req, res) => {
    res.json(botState);
});

app.get('/api/queue', (req, res) => {
    res.json(botState.queue);
});

app.get('/api/logs', (req, res) => {
    res.json(logs.slice(-100)); // Return last 100 logs
});

app.post('/api/play', (req, res) => {
    const { query } = req.body;
    if (!query) {
        return res.status(400).json({ error: 'Query is required' });
    }
    
    // Emit to Python bot
    io.emit('bot-command', { command: 'play', args: [query] });
    res.json({ success: true, message: 'Play command sent' });
});

app.post('/api/skip', (req, res) => {
    io.emit('bot-command', { command: 'skip' });
    res.json({ success: true, message: 'Skip command sent' });
});

app.post('/api/pause', (req, res) => {
    io.emit('bot-command', { command: 'pause' });
    res.json({ success: true, message: 'Pause command sent' });
});

app.post('/api/stop', (req, res) => {
    io.emit('bot-command', { command: 'stop' });
    res.json({ success: true, message: 'Stop command sent' });
});

app.post('/api/volume', (req, res) => {
    const { volume } = req.body;
    if (volume < 0 || volume > 100) {
        return res.status(400).json({ error: 'Volume must be between 0 and 100' });
    }
    
    io.emit('bot-command', { command: 'volume', args: [volume] });
    res.json({ success: true, message: 'Volume command sent' });
});

app.post('/api/shuffle', (req, res) => {
    io.emit('bot-command', { command: 'shuffle' });
    res.json({ success: true, message: 'Shuffle command sent' });
});

app.post('/api/clear', (req, res) => {
    io.emit('bot-command', { command: 'clear' });
    res.json({ success: true, message: 'Clear command sent' });
});

app.post('/api/remove', (req, res) => {
    const { index } = req.body;
    if (!index || index < 1) {
        return res.status(400).json({ error: 'Valid index is required' });
    }
    
    io.emit('bot-command', { command: 'remove', args: [index] });
    res.json({ success: true, message: 'Remove command sent' });
});

app.post('/api/repeat', (req, res) => {
    io.emit('bot-command', { command: 'repeat' });
    res.json({ success: true, message: 'Repeat command sent' });
});

// Socket.IO connection handling
io.on('connection', (socket) => {
    console.log('Client connected:', socket.id);
    
    // Send current state to new client
    socket.emit('bot-state', botState);
    socket.emit('logs', logs.slice(-50));
    
    // Handle bot state updates from Python
    socket.on('update-bot-state', (data) => {
        botState = { ...botState, ...data };
        socket.broadcast.emit('bot-state', botState);
    });
    
    // Handle log updates from Python
    socket.on('new-log', (logEntry) => {
        logs.push({
            ...logEntry,
            timestamp: new Date().toISOString()
        });
        
        // Keep only last MAX_LOGS entries
        if (logs.length > MAX_LOGS) {
            logs = logs.slice(-MAX_LOGS);
        }
        
        io.emit('new-log', logEntry);
    });
    
    socket.on('disconnect', () => {
        console.log('Client disconnected:', socket.id);
    });
});

// Error handling
app.use((err, req, res, next) => {
    console.error(err.stack);
    res.status(500).json({ error: 'Something went wrong!' });
});

// 404 handler
app.use((req, res) => {
    res.status(404).json({ error: 'Not found' });
});

const PORT = process.env.WEB_PORT || 3000;
server.listen(PORT, () => {
    console.log(`Web interface running on http://localhost:${PORT}`);
});

module.exports = { app, io };