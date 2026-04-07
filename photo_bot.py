import asyncio
import logging
import os
import tempfile

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

import replicate

# ================= НАСТРОЙКИ =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN в переменных окружения")

if not REPLICATE_API_TOKEN:
    raise ValueError("Не найден REPLICATE_API_TOKEN в переменных окружения")

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Простое временное хранилище в памяти
# user_id -> {"photo_path": "..."}
user_data = {}

# Стили
STYLE_PROMPTS = {
    "studio": "professional studio portrait, soft light, realistic skin, luxury photoshoot, high detail",
    "business": "business portrait, formal clothes, office background, professional photoshoot, ultra realistic",
    "street": "street style portrait, urban background, fashionable, realistic photography, cinematic light",
    "fashion": "high fashion editorial portrait, magazine style, dramatic light, luxury look, ultra realistic",
    "luxury": "luxury portrait, expensive interior, elegant style, premium photoshoot, ultra realistic",
}


def style_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📸 Studio", callback_data="style:studio"),
                InlineKeyboardButton(text="💼 Business", callback_data="style:business"),
            ],
            [
                InlineKeyboardButton(text="🏙 Street", callback_data="style:street"),
                InlineKeyboardButton(text="👗 Fashion", callback_data="style:fashion"),
            ],
            [
                InlineKeyboardButton(text="💎 Luxury", callback_data="style:luxury"),
            ]
        ]
    )


@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Я создаю AI-фотосессии по твоему фото.\n\n"
        "Как это работает:\n"
        "1. Отправь мне своё фото\n"
        "2. Выбери стиль\n"
        "3. Я сгенерирую результат\n\n"
        "Отправь фото, чтобы начать 📷"
    )


@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    photo = message.photo[-1]  # самое большое фото

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        temp_path = tmp.name

    await bot.download(photo, destination=temp_path)

    user_data[user_id] = {"photo_path": temp_path}

    await message.answer(
        "Фото получено ✅\n\nТеперь выбери стиль:",
        reply_markup=style_keyboard()
    )


@dp.callback_query(F.data.startswith("style:"))
async def process_style(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in user_data or "photo_path" not in user_data[user_id]:
        await callback.message.answer("Сначала отправь фото 📷")
        await callback.answer()
        return

    style_key = callback.data.split(":")[1]
    prompt_style = STYLE_PROMPTS.get(style_key)

    if not prompt_style:
        await callback.message.answer("Неизвестный стиль.")
        await callback.answer()
        return

    photo_path = user_data[user_id]["photo_path"]

    await callback.message.answer("⏳ Генерирую твою AI-фотосессию... Это может занять до минуты.")
    await callback.answer()

    try:
        # ВАЖНО:
        # Ниже пример для image-to-image модели.
        # Возможно, тебе понадобится заменить модель на другую рабочую в Replicate.
        with open(photo_path, "rb") as image_file:
            output = replicate.run(
                "stability-ai/sdxl:39ed52f2a78e934b1df3a0f0f4b0b9ea873b0a2a6c7b0d4b6df2c33f6c68f1b1",
                input={
                    "prompt": prompt_style,
                    # Если модель не поддерживает image, надо выбрать другую image-to-image модель
                    # "image": image_file
                }
            )

        # Если output — список ссылок
        if isinstance(output, list) and len(output) > 0:
            for item in output:
                await callback.message.answer_photo(item)
        else:
            await callback.message.answer_photo(output)

    except Exception as e:
        logging.exception("Ошибка генерации")
        await callback.message.answer(f"❌ Ошибка генерации:\n<code>{e}</code>")

    finally:
        try:
            os.remove(photo_path)
        except Exception:
            pass
        user_data.pop(user_id, None)


@dp.message(F.text == "/gen")
async def gen_help(message: Message):
    await message.answer("Отправь фото, а затем выбери стиль.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())