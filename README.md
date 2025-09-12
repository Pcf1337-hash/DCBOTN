# 🎵 GrooveMaster - Advanced Discord Music Bot

Ein moderner, funktionsreicher Discord-Musikbot mit erweiterten Features und professioneller Architektur.

## ✨ Features

### 🎵 Musik-Features
- **YouTube-Integration**: Unterstützung für Videos, Playlists und Suche
- **Erweiterte Warteschlange**: Bis zu 100 Songs mit Shuffle, Repeat und Management
- **Hochwertige Audio-Wiedergabe**: 192kbps MP3 mit Lautstärkeregelung
- **Sprungfunktion**: Springe zu beliebigen Zeitpunkten im Song
- **Auto-Disconnect**: Automatisches Verlassen bei Inaktivität
- **Intro-Sounds**: Zufällige Intro-Sounds beim Verbinden

### 🎛️ Benutzeroberfläche
- **Hybrid Commands**: Sowohl Slash-Commands als auch Prefix-Commands
- **Interaktive Buttons**: Moderne Discord-UI mit Buttons und Modals
- **Paginierte Warteschlange**: Übersichtliche Darstellung großer Warteschlangen
- **Echtzeit-Updates**: Live-Updates der Now-Playing-Nachrichten
- **Responsive Design**: Optimiert für Desktop und Mobile

### 🔧 Administration
- **Erweiterte Logs**: Strukturiertes Logging mit Rotation
- **Performance-Monitoring**: Prometheus-Metriken und Systemüberwachung
- **Cache-System**: Intelligentes Caching für bessere Performance
- **Konfigurierbar**: Umfangreiche Konfigurationsmöglichkeiten
- **Restart-Management**: Sichere Bot-Neustarts mit Zustandserhaltung

### 🛡️ Robustheit
- **Fehlerbehandlung**: Umfassende Fehlerbehandlung mit Benutzer-Feedback
- **Rate-Limiting**: Schutz vor Spam und Missbrauch
- **Memory-Management**: Automatische Bereinigung und Speicherverwaltung
- **Retry-Logic**: Automatische Wiederholung bei temporären Fehlern
- **Graceful Shutdown**: Sauberes Herunterfahren mit Ressourcen-Cleanup

## 🚀 Installation

### Voraussetzungen
- Python 3.8+
- FFmpeg
- Git
- Screen (optional, für Hintergrund-Ausführung)

### 1. Repository klonen
```bash
git clone <repository-url>
cd discord-music-bot
```

### 2. Virtual Environment erstellen
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows
```

### 3. Dependencies installieren
```bash
pip install -r requirements.txt
```

### 4. Konfiguration
```bash
cp .env.example .env
# Bearbeite .env mit deinen Einstellungen
```

### 5. Bot starten
```bash
python3 main.py
# oder für Hintergrund-Ausführung:
./1.sh
```

## ⚙️ Konfiguration

### Discord Bot Setup
1. Gehe zu [Discord Developer Portal](https://discord.com/developers/applications)
2. Erstelle eine neue Application
3. Gehe zu "Bot" und erstelle einen Bot
4. Kopiere den Token in deine `.env` Datei
5. Aktiviere "Message Content Intent" und "Server Members Intent"

### Wichtige Einstellungen

```env
# Discord
DISCORD_BOT_TOKEN=dein_bot_token
COMMAND_PREFIX=!
OWNER_IDS=deine_user_id

# Musik
MAX_QUEUE_SIZE=100
MAX_SONG_DURATION=7200
MAX_CONCURRENT_DOWNLOADS=3

# Features
ENABLE_SLASH_COMMANDS=true
ENABLE_AUTO_DISCONNECT=true
ENABLE_METRICS=false
```

## 📋 Befehle

### 🎵 Musik-Befehle
- `/play <query>` - Spiele Musik von YouTube ab
- `/skip` - Überspringe den aktuellen Song
- `/stop` - Stoppe die Wiedergabe und leere die Warteschlange
- `/pause` - Pausiere/Setze die Wiedergabe fort
- `/volume <0-100>` - Setze die Lautstärke
- `/queue` - Zeige die aktuelle Warteschlange
- `/nowplaying` - Zeige Informationen zum aktuellen Song
- `/shuffle` - Mische die Warteschlange
- `/repeat` - Aktiviere/Deaktiviere Wiederholung
- `/remove <position>` - Entferne einen Song aus der Warteschlange
- `/clear` - Leere die gesamte Warteschlange

### 🔧 Admin-Befehle
- `/restart` - Starte den Bot neu
- `/status` - Zeige Bot-Status und Statistiken
- `/cleanup` - Bereinige temporäre Dateien
- `/logs <lines>` - Zeige aktuelle Log-Einträge
- `/config` - Zeige aktuelle Konfiguration
- `/reload <cog>` - Lade ein Cog neu

## 🏗️ Architektur

### Projektstruktur
```
├── bot.py                 # Haupt-Bot-Klasse
├── main.py               # Entry Point
├── config/
│   └── settings.py       # Konfiguration mit Pydantic
├── cogs/
│   ├── music.py         # Musik-Funktionalität
│   ├── admin.py         # Admin-Befehle
│   └── restart_bot.sh   # Restart-Skript
├── utils/
│   ├── cache.py         # Cache-Management
│   ├── exceptions.py    # Custom Exceptions
│   ├── logger.py        # Logging-System
│   ├── monitoring.py    # Performance-Monitoring
│   ├── music_helpers.py # Musik-Hilfsfunktionen
│   ├── queue_manager.py # Warteschlangen-Management
│   └── ui_components.py # Discord-UI-Komponenten
├── downloads/           # Temporäre Audio-Dateien
├── intros/             # Intro-Sound-Dateien
├── logs/               # Log-Dateien
└── cache/              # Cache-Dateien
```

### Technologie-Stack
- **Discord.py 2.4.0**: Moderne Discord-API-Integration
- **yt-dlp**: YouTube-Download und -Extraktion
- **Pydantic**: Typsichere Konfiguration
- **Structlog**: Strukturiertes Logging
- **Prometheus**: Metriken und Monitoring
- **asyncio**: Asynchrone Programmierung
- **FFmpeg**: Audio-Verarbeitung

## 📊 Monitoring

### Metriken (Optional)
Aktiviere Prometheus-Metriken in der Konfiguration:
```env
ENABLE_METRICS=true
METRICS_PORT=8000
```

Verfügbare Metriken:
- Bot-Befehle (Anzahl, Dauer, Erfolg/Fehler)
- Aktive Voice-Verbindungen
- Warteschlangen-Größe
- System-Ressourcen (RAM, CPU)
- Download-Statistiken

### Logs
Strukturierte Logs mit verschiedenen Levels:
- **DEBUG**: Detaillierte Debugging-Informationen
- **INFO**: Allgemeine Informationen
- **WARNING**: Warnungen
- **ERROR**: Fehler
- **CRITICAL**: Kritische Fehler

## 🔒 Sicherheit

- **Berechtigungsprüfungen**: Alle Admin-Befehle prüfen Berechtigungen
- **Input-Validierung**: Alle Benutzereingaben werden validiert
- **Rate-Limiting**: Schutz vor Spam und Missbrauch
- **Sichere Konfiguration**: Sensible Daten in Umgebungsvariablen
- **Error-Handling**: Keine sensiblen Informationen in Fehlermeldungen

## 🤝 Beitragen

1. Fork das Repository
2. Erstelle einen Feature-Branch (`git checkout -b feature/AmazingFeature`)
3. Committe deine Änderungen (`git commit -m 'Add some AmazingFeature'`)
4. Push zum Branch (`git push origin feature/AmazingFeature`)
5. Öffne einen Pull Request

## 📝 Lizenz

Dieses Projekt steht unter der MIT-Lizenz. Siehe `LICENSE` Datei für Details.

## 🆘 Support

Bei Problemen oder Fragen:
1. Überprüfe die Logs (`/logs` Befehl)
2. Überprüfe die Konfiguration (`/config` Befehl)
3. Überprüfe den Bot-Status (`/status` Befehl)
4. Erstelle ein Issue im Repository

## 🎯 Roadmap

- [ ] Spotify-Integration
- [ ] Benutzer-Playlists
- [ ] Web-Dashboard
- [ ] Multi-Guild-Konfiguration
- [ ] Audio-Effekte
- [ ] Lyrics-Integration
- [ ] Voice-Channel-Statistiken
- [ ] Automatische Playlist-Generierung

---

**GrooveMaster** - Dein professioneller Discord-Musikbot für die beste Musik-Erfahrung! 🎵