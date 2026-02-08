import os
import asyncio
import json
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

DB_PATH = Path("users.json")

def load_db() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {}

def save_db(db: dict) -> None:
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
            [KeyboardButton(text="❌ Не хочу делиться")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    db = load_db()
    user_id = str(message.from_user.id)

    if user_id in db and db[user_id].get("phone"):
        await message.answer("С возвращением! Контакт уже сохранён ✅", reply_markup=ReplyKeyboardRemove())
        return

    await message.answer(
        "Привет! Чтобы продолжить, нажми кнопку и поделись контактом.",
        reply_markup=contact_keyboard()
    )

@dp.message(F.contact)
async def got_contact(message: Message):
    # Проверяем, что прислали контакт самого пользователя
    if not message.from_user or message.contact.user_id != message.from_user.id:
        await message.answer("Нужно отправить *свой* контакт через кнопку ниже.", reply_markup=contact_keyboard())
        return

    db = load_db()
    user_id = str(message.from_user.id)
    db[user_id] = {
        "phone": message.contact.phone_number,
        "first_name": message.from_user.first_name,
        "username": message.from_user.username,
    }
    save_db(db)

    await message.answer(
        f"Спасибо! Номер сохранён: {message.contact.phone_number} ✅",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(F.text == "❌ Не хочу делиться")
async def no_contact(message: Message):
    await message.answer("Ок, без номера тоже можно, но часть функций будет недоступна.", reply_markup=ReplyKeyboardRemove())

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN. В PowerShell выполни: $env:BOT_TOKEN='твой_токен'")

    bot = Bot(token)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
@dp.message()
async def block_without_phone(message: Message):
    db = load_db()
    user_id = str(message.from_user.id)

    if user_id not in db:
        await message.answer(
            "Чтобы пользоваться ботом, нужно сначала поделиться номером телефона 👇",
            reply_markup=contact_keyboard()
        )
        return
