import asyncio
import logging
import os
import tempfile
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)

# ================= НАСТРОЙКИ =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не найдена")

if not HF_TOKEN:
    raise ValueError("Переменная окружения HF_TOKEN не найдена")

HF_MODEL_URL = "https://api-inference.huggingface.co/models/timbrooks/instruct-pix2pix"

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

user_data = {}

STYLE_PROMPTS = {
    "studio": "Turn this photo into a professional studio portrait with soft lighting, clean background, realistic skin, detailed face, premium photoshoot style.",
    "business": "Turn this photo into a professional business portrait, formal clothes, office-style background, confident look, realistic photography.",
    "street": "Turn this photo into a stylish street portrait with urban background, fashionable clothes, cinematic lighting, realistic details.",
    "fashion": "Turn this photo into a high-fashion editorial portrait, luxury magazine style, dramatic lighting, stylish outfit, ultra realistic.",
    "luxury": "Turn this photo into a luxury premium portrait with elegant atmosphere, expensive interior, refined lighting, realistic professional photography."
}


def get_styles_keyboard():
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
async def start_handler(message: Message):
    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Я создаю AI-фотосессии по твоему фото.\n\n"
        "<b>Как это работает:</b>\n"
        "1. Ты отправляешь фото\n"
        "2. Выбираешь стиль\n"
        "3. Я генерирую результат\n\n"
        "<b>Для лучшего результата:</b>\n"
        "• на фото должен быть один человек\n"
        "• лицо должно быть хорошо видно\n"
        "• лучше без очков и сильных теней\n"
        "• лучше использовать селфи или портрет\n\n"
        "📷 Просто отправь фото, чтобы начать"
    )


@dp.message(F.photo)
async def photo_handler(message: Message):
    user_id = message.from_user.id

    if user_id in user_data and user_data[user_id].get("is_generating"):
        await message.answer("⏳ Подожди, я уже генерирую твою фотосессию.")
        return

    photo = message.photo[-1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_path = temp_file.name

    await bot.download(photo, destination=temp_path)

    if user_id in user_data:
        old_photo = user_data[user_id].get("photo_path")
        if old_photo and os.path.exists(old_photo):
            try:
                os.remove(old_photo)
            except Exception:
                pass

    user_data[user_id] = {
        "photo_path": temp_path,
        "is_generating": False
    }

    await message.answer(
        "✅ Фото получено!\n\n"
        "Теперь выбери стиль фотосессии:",
        reply_markup=get_styles_keyboard()
    )


async def generate_image_huggingface(image_path: str, prompt: str) -> bytes:
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}"
    }

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    data = aiohttp.FormData()
    data.add_field("inputs", prompt)
    data.add_field(
        "image",
        image_bytes,
        filename="photo.jpg",
        content_type="image/jpeg"
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(HF_MODEL_URL, headers=headers, data=data) as response:
            content_type = response.headers.get("content-type", "")

            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"HF API error {response.status}: {error_text}")

            if "image" not in content_type:
                text = await response.text()
                raise Exception(f"HF вернул не изображение: {text}")

            return await response.read()


@dp.callback_query(F.data.startswith("style:"))
async def style_handler(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in user_data or "photo_path" not in user_data[user_id]:
        await callback.message.answer("❗ Сначала отправь фото.")
        await callback.answer()
        return

    if user_data[user_id].get("is_generating"):
        await callback.answer("Генерация уже идёт...", show_alert=True)
        return

    style_key = callback.data.split(":")[1]
    prompt = STYLE_PROMPTS.get(style_key)

    if not prompt:
        await callback.message.answer("❌ Неизвестный стиль.")
        await callback.answer()
        return

    user_data[user_id]["is_generating"] = True
    photo_path = user_data[user_id]["photo_path"]

    await callback.message.answer(
        "⏳ <b>Генерирую твою AI-фотосессию...</b>\n\n"
        "Обычно это занимает 20–60 секунд."
    )
    await callback.answer()

    try:
        result_bytes = await generate_image_huggingface(photo_path, prompt)

        result_file = BufferedInputFile(result_bytes, filename="result.png")
        await callback.message.answer_photo(result_file)

        await callback.message.answer(
            "🔥 Готово!\n\n"
            "Если хочешь ещё один вариант — отправь новое фото."
        )

    except Exception as e:
        logging.exception("Ошибка генерации через Hugging Face")
        error_text = str(e)

        if "503" in error_text:
            await callback.message.answer(
                "⏳ Модель Hugging Face сейчас загружается. Подожди немного и попробуй ещё раз."
            )
        elif "429" in error_text:
            await callback.message.answer(
                "⏳ Слишком много запросов к API. Попробуй чуть позже."
            )
        elif "401" in error_text:
            await callback.message.answer(
                "❌ Ошибка авторизации Hugging Face. Проверь HF_TOKEN в Railway."
            )
        else:
            await callback.message.answer(
                f"❌ <b>Ошибка генерации</b>\n\n<code>{error_text[:700]}</code>"
            )

    finally:
        if os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except Exception:
                pass

        user_data.pop(user_id, None)


@dp.message(F.text == "/help")
async def help_handler(message: Message):
    await message.answer(
        "📌 Отправь фото, затем выбери стиль.\n\n"
        "Если генерация не удалась — попробуй ещё раз через минуту."
    )


@dp.message()
async def fallback_handler(message: Message):
    await message.answer(
        "Я понимаю фото и команды.\n\n"
        "📷 Отправь фото, чтобы создать AI-фотосессию.\n"
        "Или нажми /start"
    )


async def main():
    logging.info("Бот запущен на Hugging Face версии")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())