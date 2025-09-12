from collections import deque
import os
import discord
import logging

COMMAND_PREFIX = "!"
DOWNLOADS_DIR = "downloads"
MUSIC_QUEUE = deque()
CURRENT_SONG = None
REPEAT_MODE = False
VOLUME = 0.8
NOW_PLAYING_MESSAGE = None

# Neue Konfigurationsoptionen
MAX_QUEUE_SIZE = 20
DEFAULT_VOLUME = 0.8
PROGRESS_BAR_LENGTH = 20
PROGRESS_BAR_FILLED = '▰'
PROGRESS_BAR_EMPTY = '▱'

# Logging-Konfiguration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL = logging.DEBUG

# Definiere die benötigten Intents
INTENTS = discord.Intents.default()
INTENTS.message_content = True

# Bestimme das Verzeichnis des Skripts
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS_PATH = os.path.join(BASE_DIR, DOWNLOADS_DIR)

# Erstelle den Downloads-Ordner, falls er nicht existiert
if not os.path.exists(DOWNLOADS_PATH):
    os.makedirs(DOWNLOADS_PATH)

# Initialize logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

#Rest of the bot code would go here.  Example:
#intents = discord.Intents.default()
#intents.message_content = True
#client = discord.Client(intents=intents)

#@client.event
#async def on_ready():
#    print(f'Logged in as {client.user}')

#@client.event
#async def on_message(message):
#    if message.author == client.user:
#        return

#    if message.content.startswith(COMMAND_PREFIX):
#        #Process commands here.

#client.run("YOUR_BOT_TOKEN")

