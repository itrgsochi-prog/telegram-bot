import os
import asyncio
from aiogram import Bot

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан")
    bot = Bot(token)
    result = await bot.delete_webhook(drop_pending_updates=True)
    print("delete_webhook:", result)
    await bot.session.close()

asyncio.run(main())
