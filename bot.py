import os
import json
import re
from pathlib import Path
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

DB_PATH = Path("/var/data/users.json")


def load_db() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {}


def save_db(db: dict) -> None:
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_phone(text: str) -> str:
    # оставляем цифры и плюс
    s = re.sub(r"[^\d+]", "", (text or "").strip())
    # плюс только в начале
    if s.count("+") > 1 or ("+" in s and not s.startswith("+")):
        return ""
    return s


def is_valid_phone(phone: str) -> bool:
    if not phone:
        return False
    # допустимы только + и цифры
    if not re.fullmatch(r"\+?\d+", phone):
        return False

    digits = re.sub(r"\D", "", phone)
    # E.164: 10..15 цифр — хороший практичный диапазон
    if not (10 <= len(digits) <= 15):
        return False

    # чтобы не принимал "0000000000"
    if digits.count(digits[0]) == len(digits):
        return False

    return True


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
        ],
        resize_keyboard=True,
        # one_time_keyboard убрали
    )


# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")  # например: https://telegram-bot7315.onrender.com
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret2")

if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN в переменных окружения Render")
if not BASE_URL:
    raise RuntimeError("Не задан BASE_URL в переменных окружения Render")

# нормализуем BASE_URL (убираем слэш в конце, если есть)
BASE_URL = BASE_URL.rstrip("/")

WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    db = load_db()
    user_id = str(message.from_user.id)

    if user_id in db and db[user_id].get("phone"):
        await message.answer(
            "С возвращением! Контакт уже сохранён ✅",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await message.answer(
        "Привет! Чтобы продолжить, нажми кнопку и поделись контактом.\n"
        "Если кнопки нет — просто напиши номер в формате +7XXXXXXXXXX.",
        reply_markup=contact_keyboard(),
    )


@dp.message(F.contact)
async def got_contact(message: Message):
    # контакт должен быть самого пользователя
    if not message.from_user or message.contact.user_id != message.from_user.id:
        await message.answer(
            "Нужно отправить *свой* контакт через кнопку ниже.",
            reply_markup=contact_keyboard(),
        )
        return

    db = load_db()
    user_id = str(message.from_user.id)
    db[user_id] = {
        "phone": message.contact.phone_number,
        "first_name": message.from_user.first_name,
        "username": message.from_user.username,
    }
    save_db(db)

    # ✅ Изменённый текст после сохранения номера
    await message.answer(
        f"Спасибо, номер сохранён: {message.contact.phone_number}\n\n"
        "Напишите название и адрес вашего объекта.",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message()
async def block_without_phone(message: Message):
    # не мешаем /start и контакту (их обработают другие хендлеры)
    if message.text and message.text.startswith("/start"):
        return
    if message.contact:
        return

    db = load_db()
    user_id = str(message.from_user.id)

    # ✅ если номера нет, но пользователь написал его руками — попробуем распознать и сохранить
    if (user_id not in db or not db[user_id].get("phone")) and message.text:
        raw = (message.text or "").strip()
        phone = normalize_phone(raw)

        if is_valid_phone(phone):
            db[user_id] = {
                "phone": phone,
                "first_name": message.from_user.first_name,
                "username": message.from_user.username,
            }
            save_db(db)
            await message.answer(
                f"Спасибо, номер сохранён: {phone}\n\n"
                "Напишите название и адрес вашего объекта.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

    if user_id not in db or not db[user_id].get("phone"):
        await message.answer(
            "Чтобы пользоваться ботом, нужно сначала поделиться номером телефона 👇\n"
            "Если кнопки нет — просто напишите номер в формате +7XXXXXXXXXX.",
            reply_markup=contact_keyboard(),
        )


async def on_startup(app: web.Application):
    await bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
    )
    print("Webhook set:", WEBHOOK_URL)


# ✅ ВАЖНО: webhook на shutdown НЕ удаляем
# Render может часто перезапускать контейнер, и delete_webhook() приводит к url:"" в getWebhookInfo
async def on_shutdown(app: web.Application):
    print("Shutting down... (webhook NOT deleted)")


async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")


def main():
    app = web.Application()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # health-check: https://<BASE_URL>/health
    app.router.add_get("/health", health)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    ).register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    port = int(os.getenv("PORT", "8080"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()