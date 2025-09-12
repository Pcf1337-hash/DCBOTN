#!/bin/bash

# Enhanced restart script with better error handling and portability

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to kill bot processes
kill_bot_processes() {
    log "Stopping existing bot processes..."
    
    # Kill by process name
    pkill -f "python.*main.py" 2>/dev/null
    pkill -f "python.*bot.py" 2>/dev/null
    
    # Kill screen sessions
    screen -X -S dcbot quit >/dev/null 2>&1
    screen -X -S groovemaster quit >/dev/null 2>&1
    
    # Wait for processes to terminate
    sleep 3
    
    # Force kill if still running
    pkill -9 -f "python.*main.py" 2>/dev/null
    pkill -9 -f "python.*bot.py" 2>/dev/null
    
    log "Bot processes stopped"
}

# Function to start bot
start_bot() {
    log "Starting bot in new screen session..."
    
    cd "$PROJECT_DIR" || {
        log "ERROR: Could not change to project directory: $PROJECT_DIR"
        exit 1
    }
    
    # Check if main.py exists
    if [[ ! -f "main.py" ]]; then
        log "ERROR: main.py not found in $PROJECT_DIR"
        exit 1
    fi
    
    # Check if bot.py exists as fallback
    if [[ ! -f "bot.py" ]] && [[ ! -f "main.py" ]]; then
        log "ERROR: Neither main.py nor bot.py found"
        exit 1
    fi
    
    # Determine which file to run
    if [[ -f "main.py" ]]; then
        PYTHON_FILE="main.py"
    else
        PYTHON_FILE="bot.py"
    fi
    
    # Start in screen session
    screen -dmS groovemaster python3 "$PYTHON_FILE"
    
    # Check if screen session started successfully
    if screen -list | grep -q "groovemaster"; then
        log "Bot started successfully in screen session 'groovemaster'"
        log "Use 'screen -r groovemaster' to attach to the session"
    else
        log "ERROR: Failed to start bot in screen session"
        # Try to start without screen as fallback
        log "Attempting to start bot without screen..."
        nohup python3 "$PYTHON_FILE" > bot.log 2>&1 &
        if [[ $? -eq 0 ]]; then
            log "Bot started without screen (running in background)"
        else
            log "ERROR: Failed to start bot"
            exit 1
        fi
    fi
}

# Function to check dependencies
check_dependencies() {
    log "Checking dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log "ERROR: python3 not found"
        exit 1
    fi
    
    # Check screen (optional)
    if ! command -v screen &> /dev/null; then
        log "WARNING: screen not found, will run without screen session"
    fi
    
    # Check if virtual environment should be activated
    if [[ -f "$PROJECT_DIR/venv/bin/activate" ]]; then
        log "Activating virtual environment..."
        source "$PROJECT_DIR/venv/bin/activate"
    elif [[ -f "$PROJECT_DIR/.venv/bin/activate" ]]; then
        log "Activating virtual environment..."
        source "$PROJECT_DIR/.venv/bin/activate"
    fi
    
    log "Dependencies checked"
}

# Main execution
main() {
    log "=== Bot Restart Script Started ==="
    log "Script directory: $SCRIPT_DIR"
    log "Project directory: $PROJECT_DIR"
    
    check_dependencies
    kill_bot_processes
    start_bot
    
    log "=== Bot Restart Script Completed ==="
}

# Run main function
main "$@"