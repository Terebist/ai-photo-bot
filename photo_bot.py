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

from gradio_client import Client, handle_file

# ================= НАСТРОЙКИ =================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не найдена")

SPACE_NAME = "multimodalart/FLUX.2-dev-turbo"

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

user_data = {}

# Стили
STYLE_PROMPTS = {
    "studio": "professional studio portrait, soft lighting, clean background, realistic skin, detailed face, premium photoshoot style",
    "business": "professional business portrait, formal clothes, office-style background, confident look, realistic photography",
    "street": "stylish street portrait with urban background, fashionable clothes, cinematic lighting, realistic details",
    "fashion": "high fashion editorial portrait, luxury magazine style, dramatic lighting, stylish outfit, ultra realistic",
    "luxury": "luxury premium portrait with elegant atmosphere, expensive interior, refined lighting, realistic professional photography"
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
        "Я создаю AI-фотосессии по твоему фото через FLUX модель.\n\n"
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


def generate_image_flux_sync(image_path: str, prompt: str) -> str:
    """
    Синхронная функция генерации через Hugging Face Space FLUX.2-dev-turbo
    Возвращает путь к сгенерированному файлу
    """
    client = Client(SPACE_NAME)

    image_file = handle_file(image_path)

    image_data = {
        "image": image_file,
        "caption": None
    }

    result = client.predict(
        prompt=prompt,
        input_images=[image_data],
        seed=0,
        randomize_seed=True,
        width=1024,
        height=1024,
        num_inference_steps=30,
        guidance_scale=2.5,
        prompt_upsampling=False,
        use_turbo=True,
        api_name="/infer"
    )

    # result — это tuple: (изображение, seed)
    image_result = result[0]

    # Проверяем формат ответа
    if isinstance(image_result, str):
        output_path = image_result
    elif isinstance(image_result, dict):
        output_path = image_result.get('path') or image_result.get('url')
    else:
        raise Exception(f"Неизвестный формат ответа: {type(image_result)}")

    return output_path


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
        "Обычно это занимает от 1 до 2 минут."
    )
    await callback.answer()

    try:
        loop = asyncio.get_event_loop()
        result_path = await loop.run_in_executor(
            None,
            generate_image_flux_sync,
            photo_path,
            prompt
        )

        result_file = FSInputFile(result_path)
        await callback.message.answer_photo(result_file)

        await callback.message.answer(
            "🔥 Готово!\n\n"
            "Если хочешь ещё один вариант — отправь новое фото."
        )

        try:
            os.remove(result_path)
        except Exception:
            pass

    except Exception as e:
        logging.exception("Ошибка генерации через FLUX Space")
        error_text = str(e)

        if "queue" in error_text.lower():
            await callback.message.answer(
                "⏳ Space сейчас перегружен. Попробуй ещё раз через минуту."
            )
        elif "503" in error_text or "sleeping" in error_text.lower():
            await callback.message.answer(
                "⏳ Space временно недоступен (спит). Попробуй через минуту."
            )
        else:
            await callback.message.answer(
                "❌ <b>Ошибка генерации</b>\n\n"
                "Попробуй ещё раз или отправь другое фото."
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
    logging.info("Бот запущен на FLUX Space версии")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())