import asyncio
import logging
import os
import random

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ================= НАСТРОЙКИ =================

TOKEN = os.getenv("TOKEN")  # токен из Railway
ADMIN_ID = 6840152992       # твой ID
CHANNEL_USERNAME = "@Neiro_Setevoy"

# ============================================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ================= СОСТОЯНИЯ =================

class Form(StatesGroup):
    name = State()
    goal = State()
    photos = State()
    paid_photos = State()


# ================= КНОПКИ =================

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📸 Подать заявку на бесплатную фотосессию")],
        [KeyboardButton(text="⚡️ Без очереди (10 фото — 199₽)")]
    ],
    resize_keyboard=True
)


# ================= ПРОВЕРКА ПОДПИСКИ =================

async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["member", "creator", "administrator"]
    except:
        return False


# ================= СТАРТ =================

@dp.message(F.text == "/start")
async def start(message: Message):
    text = (
        "👋 Привет!\n\n"
        "Я превращаю ТВОИ обычные фото в стильную AI-фотосессию и отдаю готовый результат 📸\n\n"
        "Ты получишь:\n"
        "— аватарки\n"
        "— фото для соцсетей\n"
        "— или просто красивую фотосессию\n\n"
        "Результаты публикуются в канале «Нейросетевой»\n\n"
        "👇 Нажми кнопку ниже, чтобы подать заявку"
    )
    await message.answer(text, reply_markup=main_kb)


# ================= БЕСПЛАТНАЯ ЗАЯВКА =================

@dp.message(F.text == "📸 Подать заявку на бесплатную фотосессию")
async def start_form(message: Message, state: FSMContext):

    if not await check_subscription(message.from_user.id):
        await message.answer(
            f"❗️Чтобы подать заявку, подпишись на канал:\n{CHANNEL_USERNAME}\n\nПосле этого нажми кнопку ещё раз"
        )
        return

    await state.set_state(Form.name)
    await message.answer("Как к тебе обращаться? 🙂\n(Имя или ник — как удобно)")


@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.goal)

    await message.answer(
        "Какой результат ты хочешь получить? 🎯\n\n"
        "Например:\n"
        "— аватарка\n"
        "— соцсети\n"
        "— деловой стиль\n"
        "— что-то креативное\n\n"
        "✍️ Можешь описать своими словами (по желанию)"
    )


@dp.message(Form.goal)
async def get_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await state.update_data(photos=[])
    await state.set_state(Form.photos)

    await message.answer(
        "Теперь пришли 3–5 своих фото ОДНИМ сообщением 📸\n\n"
        "❗️Важно:\n"
        "— лицо должно быть хорошо видно\n"
        "— без сильных фильтров\n"
        "— желательно разные ракурсы\n\n"
        "Это сильно влияет на качество результата\n\n"
        "⚠️ Если после отправки бот не отвечает — просто отправь фото ещё раз (иногда Telegram лагает)\n\n"
        "Отправляя фото, ты соглашаешься, что результат может быть опубликован в канале."
    )


# ================= ПРИЁМ ФОТО =================

@dp.message(Form.photos, F.photo)
async def get_photos(message: Message, state: FSMContext):

    data = await state.get_data()
    photos = data.get("photos", [])

    # если альбом — берём все фото
    if message.media_group_id:
        photos.append(message.photo[-1].file_id)
    else:
        photos.append(message.photo[-1].file_id)

    await state.update_data(photos=photos)

    if len(photos) < 3:
        await message.answer(
            f"Фото получено 👍\n\n"
            f"Нужно ещё {3 - len(photos)} фото\n\n"
            f"⚠️ Если отправлял несколько — попробуй отправить ещё раз"
        )
        return

    if len(photos) > 5:
        photos = photos[:5]

    # финал заявки
    user_data = await state.get_data()
    name = user_data["name"]
    goal = user_data["goal"]

    username = f"@{message.from_user.username}" if message.from_user.username else "нет username"

    queue_position = random.randint(12, 47)

    # сообщение пользователю
    await message.answer(
        f"🔥 Заявка принята!\n\n"
        f"Сейчас ты в очереди примерно: {queue_position} место\n\n"
        f"⏳ Обычно ожидание занимает от 1 дня до 2-ух недель\n\n"
        f"Если тебя выберут — я напишу лично и сделаю фотосессию\n\n"
        f"Следи за результатами в канале 👇\n"
        f"https://t.me/Neiro_Setevoy\n\n"
        f"⚡️ Хочешь без очереди?\n"
        f"Могу сделать для тебя фотосессию вне очереди (10 фото) — 199₽"
    )

    # отправка админу
    caption = (
        f"🔥 Новая заявка\n\n"
        f"Имя: {name}\n"
        f"Username: {username}\n"
        f"ID: {message.from_user.id}\n\n"
        f"Цель:\n{goal}"
    )

    media = []
    for i, photo in enumerate(photos):
        if i == 0:
            media.append(InputMediaPhoto(media=photo, caption=caption))
        else:
            media.append(InputMediaPhoto(media=photo))

    await bot.send_media_group(chat_id=ADMIN_ID, media=media)

    await state.clear()


# ================= ПЛАТНАЯ ЗАЯВКА =================

@dp.message(F.text == "⚡️ Без очереди (10 фото — 199₽)")
async def paid_start(message: Message, state: FSMContext):

    if not await check_subscription(message.from_user.id):
        await message.answer(
            f"❗️Сначала подпишись на канал:\n{CHANNEL_USERNAME}\n\nПосле этого нажми кнопку ещё раз"
        )
        return

    await state.set_state(Form.paid_photos)
    await state.update_data(photos=[])

    await message.answer(
        "Отправь 3–5 фото для фотосессии 📸\n\n"
        "После этого я напишу тебе для оплаты и сразу сделаю без очереди"
    )


@dp.message(Form.paid_photos, F.photo)
async def paid_photos(message: Message, state: FSMContext):

    data = await state.get_data()
    photos = data.get("photos", [])

    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    if len(photos) < 3:
        await message.answer(f"Нужно ещё {3 - len(photos)} фото")
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "нет username"

    await message.answer(
        "🔥 Заявка принята!\n\n"
        "Я напишу тебе для оплаты и сразу сделаю фотосессию без очереди"
    )

    caption = (
        f"💰 ПЛАТНАЯ ЗАЯВКА\n\n"
        f"Username: {username}\n"
        f"ID: {message.from_user.id}"
    )

    media = []
    for i, photo in enumerate(photos):
        if i == 0:
            media.append(InputMediaPhoto(media=photo, caption=caption))
        else:
            media.append(InputMediaPhoto(media=photo))

    await bot.send_media_group(chat_id=ADMIN_ID, media=media)

    await state.clear()


# ================= ЗАПУСК =================

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())