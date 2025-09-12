#!/bin/bash

# Bestimme das aktuelle Verzeichnis des Skripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Funktion zum Beenden aller laufenden Bot-Instanzen
kill_bot_instances() {
    pkill -f "python3 main.py"
    screen -X -S dcbot quit >/dev/null 2>&1
    sleep 2  # Warte 2 Sekunden, um sicherzustellen, dass alle Prozesse beendet sind
}

# Beende alle laufenden Bot-Instanzen
kill_bot_instances

# Wechsle in das Projektverzeichnis
cd "$PROJECT_DIR"

# Starte eine neue Screen-Session
screen -dmS dcbot python3 main.py

echo "Bot wurde neu gestartet in einer neuen Screen-Session."

