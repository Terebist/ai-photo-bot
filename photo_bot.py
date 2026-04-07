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
)

import replicate

# ================= НАСТРОЙКИ =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не найдена")

if not REPLICATE_API_TOKEN:
    raise ValueError("Переменная окружения REPLICATE_API_TOKEN не найдена")

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Временное хранилище данных пользователей
# user_id -> {"photo_path": "...", "is_generating": False}
user_data = {}

# Стили фотосессий
STYLE_PROMPTS = {
    "studio": "professional studio portrait, soft beauty lighting, highly detailed, realistic skin, premium photoshoot, ultra realistic",
    "business": "professional business portrait, elegant formal outfit, office background, realistic photography, premium headshot, ultra realistic",
    "street": "modern street style portrait, urban background, fashionable clothes, cinematic lighting, realistic photo, ultra realistic",
    "fashion": "high fashion editorial portrait, magazine photoshoot, luxury style, dramatic lighting, ultra realistic, highly detailed",
    "luxury": "luxury portrait, expensive interior, elegant premium look, sophisticated photoshoot, ultra realistic, rich details"
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
            ],
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
        "• подойдут селфи и портреты\n\n"
        "📷 Просто отправь фото, чтобы начать"
    )


@dp.message(F.text == "/help")
async def help_handler(message: Message):
    await message.answer(
        "Команды:\n"
        "/start — начать работу\n"
        "/help — помощь\n"
        "/styles — показать стили\n\n"
        "Чтобы создать фотосессию, просто отправь фото."
    )


@dp.message(F.text == "/styles")
async def styles_handler(message: Message):
    await message.answer(
        "<b>Доступные стили:</b>\n"
        "📸 Studio\n"
        "💼 Business\n"
        "🏙 Street\n"
        "👗 Fashion\n"
        "💎 Luxury\n\n"
        "Отправь фото, и я предложу выбрать стиль."
    )


@dp.message(F.photo)
async def photo_handler(message: Message):
    user_id = message.from_user.id

    # Если уже идёт генерация
    if user_id in user_data and user_data[user_id].get("is_generating"):
        await message.answer("⏳ Подожди, я уже генерирую твою фотосессию.")
        return

    photo = message.photo[-1]

    # Создаём временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_path = temp_file.name

    # Скачиваем фото из Telegram
    await bot.download(photo, destination=temp_path)

    # Если у пользователя было старое фото — удалим
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


@dp.callback_query(F.data.startswith("style:"))
async def style_callback_handler(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in user_data or "photo_path" not in user_data[user_id]:
        await callback.message.answer("❗ Сначала отправь фото.")
        await callback.answer()
        return

    if user_data[user_id].get("is_generating"):
        await callback.answer("Генерация уже идёт...", show_alert=True)
        return

    style_key = callback.data.split(":")[1]
    style_prompt = STYLE_PROMPTS.get(style_key)

    if not style_prompt:
        await callback.message.answer("❌ Неизвестный стиль.")
        await callback.answer()
        return

    photo_path = user_data[user_id]["photo_path"]
    user_data[user_id]["is_generating"] = True

    await callback.message.answer(
        "⏳ <b>Генерирую твою AI-фотосессию...</b>\n\n"
        "Обычно это занимает от 20 до 60 секунд."
    )
    await callback.answer()

    try:
        with open(photo_path, "rb") as image_file:
            # =========================================================
            # ВАЖНО:
            # Здесь нужно указать модель Replicate, которая поддерживает
            # генерацию по изображению (image-to-image / InstantID / PhotoMaker и т.д.)
            #
            # Сейчас ниже стоит пример-заглушка.
            # Если у модели другие входные параметры — их нужно поменять.
            # =========================================================
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": style_prompt
                    # Пример, если модель поддерживает входное фото:
                    # "image": image_file
                    # или "input_image": image_file
                    # или "init_image": image_file
                }
            )

        if isinstance(output, list):
            if len(output) == 0:
                await callback.message.answer("❌ Генерация не вернула изображений.")
            else:
                for item in output:
                    await callback.message.answer_photo(item)
        else:
            await callback.message.answer_photo(output)

        await callback.message.answer(
            "🔥 Готово!\n\n"
            "Если хочешь ещё один вариант — отправь новое фото."
        )

    except Exception as e:
        logging.exception("Ошибка при генерации")
        await callback.message.answer(
            f"❌ <b>Ошибка генерации</b>\n\n<code>{str(e)}</code>"
        )

    finally:
        # Удаляем временный файл
        if os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except Exception:
                pass

        user_data.pop(user_id, None)


@dp.message()
async def fallback_handler(message: Message):
    await message.answer(
        "Я понимаю только фото и команды.\n\n"
        "📷 Отправь фото, чтобы я сделал AI-фотосессию.\n"
        "Или используй /start"
    )


async def main():
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())