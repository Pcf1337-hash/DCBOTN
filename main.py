import asyncio
import os
import signal
import sys
from dotenv import load_dotenv
from bot import GrooveMaster

load_dotenv()

def signal_handler(sig, frame):
    print("Strg+C erkannt. Beende den Bot...")
    sys.exit(0)

async def main():
    bot = GrooveMaster()
    
    # Registriere den Signal-Handler für SIGINT (Strg+C)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        await bot.start(os.getenv('DISCORD_BOT_TOKEN'))
    except KeyboardInterrupt:
        print("Bot wird beendet...")
    finally:
        await bot.close()
        print("Bot wurde erfolgreich beendet.")

if __name__ == "__main__":
    asyncio.run(main())

