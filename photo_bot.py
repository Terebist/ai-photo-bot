import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import replicate

# ================= НАСТРОЙКИ =================

TOKEN = "8350146751:AAEkzNuqqpbRy-QWfxureXOD9KwZAobvVAs"
os.environ["REPLICATE_API_TOKEN"] = os.getenv("REPLICATE_API_TOKEN")

# ============================================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ========= СТАРТ =========
@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Я превращаю <b>твои обычные фото</b> в стильную AI-фотосессию 🔥\n\n"
        "Пока можно протестировать генерацию.\n"
        "Напиши команду:\n\n"
        "/gen"
    )


# ========= ТЕСТ ГЕНЕРАЦИИ =========
@dp.message(F.text == "/gen")
async def gen_test(message: Message):
    await message.answer("⏳ Генерирую фото...")

try:
    output = replicate.run(
        "lucataco/realistic-vision-v5",
        input={
            "prompt": "portrait photo of a person, ultra realistic, 8k, studio lighting",
        }
    )

    if isinstance(output, list):
        for img in output:
            await message.answer_photo(img)
    else:
        await message.answer_photo(output)

except Exception as e:
    await message.answer(f"Ошибка генерации:\n{e}")


# ========= ЗАПУСК =========
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())