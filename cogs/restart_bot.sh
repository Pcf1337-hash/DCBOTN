#!/bin/bash

# Funktion zum Beenden aller laufenden Bot-Instanzen
kill_bot_instances() {
    pkill -f "python3 main.py"
    screen -X -S dcbot quit >/dev/null 2>&1
    sleep 2  # Warte 2 Sekunden, um sicherzustellen, dass alle Prozesse beendet sind
}

# Beende alle laufenden Bot-Instanzen
kill_bot_instances

# Wechsle in das richtige Verzeichnis
cd /home/nos/beta

# Starte eine neue Screen-Session
screen -dmS dcbot python3 main.py

echo "Bot wurde neu gestartet in einer neuen Screen-Session."

