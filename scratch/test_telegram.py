import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from telegram_alerts import send_telegram_alert

async def main():
    print("Sending Telegram Test Alert...")
    await send_telegram_alert("🚀 *SOVEREIGN ONLINE*: Telegram Notifications are now ACTIVE.")
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
