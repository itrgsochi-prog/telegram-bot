import os
import json
from pathlib import Path
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# ====== ENV ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")          # https://your-app.onrender.com
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret")
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

if not BOT_TOKEN or not BASE_URL:
    raise RuntimeError("BOT_TOKEN и BASE_URL должны быть заданы")

# ====== STORAGE ======
DB_PATH = Path("users.json")

def load_db() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {}

def save_db(db: dict) -> None:
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

# ====== BOT ======
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

@dp.message(CommandStart())
async def start(message: Message):
    db = load_db()
    user_id = str(message.from_user.id)

    if db.get(user_id, {}).get("phone"):
        await message.answer(
            "С возвращением! Контакт уже сохранён ✅",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await message.answer(
        "Чтобы продолжить, поделитесь номером телефона 👇",
        reply_markup=contact_keyboard(),
    )

@dp.message(F.contact)
async def got_contact(message: Message):
    if message.contact.user_id != message.from_user.id:
        await message.answer("Нужно отправить *свой* контакт.")
        return

    db = load_db()
    db[str(message.from_user.id)] = {
        "phone": message.contact.phone_number,
        "first_name": message.from_user.first_name,
        "username": message.from_user.username,
    }
    save_db(db)

    await message.answer(
        "Спасибо! Номер сохранён ✅",
        reply_markup=ReplyKeyboardRemove(),
    )

@dp.message()
async def block_without_phone(message: Message):
    db = load_db()
    user_id = str(message.from_user.id)

    if not db.get(user_id, {}).get("phone"):
        await message.answer(
            "Для работы с ботом нужен номер телефона 👇",
            reply_markup=contact_keyboard(),
        )

# ====== WEBHOOK APP ======
async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()

app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

SimpleRequestHandler(
    dispatcher=dp,
    bot=bot,
).register(app, path=WEBHOOK_PATH)

setup_application(app, dp)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
