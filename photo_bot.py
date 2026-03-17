import asyncio
import random

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


# ==============================
import os
TOKEN = os.getenv("TOKEN")
# ==============================

ADMIN_ID = 6840152992
CHANNEL_USERNAME = "@Neiro_Setevoy"


bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

queue_count = 0


# ===== СОСТОЯНИЯ =====

class Form(StatesGroup):
    name = State()
    goal = State()
    photos = State()
    is_paid = State()


# ===== КНОПКИ =====

start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📸 Бесплатная ИИ-фотосессия")],
        [KeyboardButton(text="⚡ Без очереди (10 фото — 199₽)")],
        [KeyboardButton(text="✅ Проверить подписку")]
    ],
    resize_keyboard=True
)


# ===== ПРОВЕРКА ПОДПИСКИ =====

async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "creator", "administrator"]
    except:
        return False


# ===== СТАРТ =====

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Здесь можно получить <b>бесплатную ИИ-фотосессию</b> 📸\n\n"
        "Я превращаю обычные фото в стильные AI-изображения.\n"
        "Лучшие работы публикуются в канале.\n\n"
        "Выбери вариант ниже 👇",
        reply_markup=start_keyboard
    )


# ===== ПРОВЕРКА КНОПКОЙ =====

@dp.message(F.text == "✅ Проверить подписку")
async def check_sub_button(message: Message):

    subscribed = await check_subscription(message.from_user.id)

    if subscribed:
        await message.answer("✅ Подписка подтверждена! Теперь можешь подать заявку.")
    else:
        await message.answer(
            "❗ Ты ещё не подписан\n\n"
            "Подпишись и нажми кнопку снова:\n"
            "https://t.me/Neiro_Setevoy"
        )


# ===== ОБЫЧНАЯ ЗАЯВКА =====

@dp.message(F.text == "📸 Бесплатная ИИ-фотосессия")
async def start_form(message: Message, state: FSMContext):

    subscribed = await check_subscription(message.from_user.id)

    if not subscribed:
        await message.answer(
            "❗ Чтобы подать заявку на <b>бесплатную ИИ-фотосессию</b>, подпишись:\n\n"
            "https://t.me/Neiro_Setevoy\n\n"
            "После этого нажми «Проверить подписку»"
        )
        return

    await state.update_data(is_paid=False)

    await message.answer("Как тебя назвать?")
    await state.set_state(Form.name)


# ===== ПЛАТНАЯ ЗАЯВКА =====

@dp.message(F.text == "⚡ Без очереди (10 фото — 199₽)")
async def paid_start(message: Message, state: FSMContext):

    await state.update_data(is_paid=True)

    await message.answer(
        "⚡ <b>Фотосессия без очереди</b>\n\n"
        "Ты получишь <b>10 AI-фото</b> без ожидания.\n\n"
        "Для начала напиши имя:"
    )

    await state.set_state(Form.name)


# ===== ИМЯ =====

@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):

    await state.update_data(name=message.text)

    await message.answer("Для чего нужна фотосессия?")
    await state.set_state(Form.goal)


# ===== ЦЕЛЬ =====

@dp.message(Form.goal)
async def get_goal(message: Message, state: FSMContext):

    await state.update_data(goal=message.text)
    await state.update_data(photos=[])

    await message.answer(
        "Пришли <b>3–5 фото</b> 📸\n\n"
        "⚠ Если бот не отвечает — отправь фото ещё раз."
    )

    await state.set_state(Form.photos)


# ===== ФОТО =====

@dp.message(Form.photos, F.photo)
async def get_photos(message: Message, state: FSMContext):

    data = await state.get_data()
    photos = data.get("photos", [])

    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    count = len(photos)

    if count < 3:
        await message.answer(f"Сейчас {count} фото. Нужно минимум 3.")
        return

    if count > 5:
        return

    is_paid = data.get("is_paid", False)

    name = data["name"]
    goal = data["goal"]

    username = message.from_user.username
    username = f"@{username}" if username else "не указан"

    # ===== ПОЛЬЗОВАТЕЛЬ =====

    if is_paid:

        await message.answer(
            "🔥 Заявка принята!\n\n"
            "Я напишу тебе для оплаты и сразу начну работу."
        )

    else:

        global queue_count
        queue_count += 1

        queue_position = queue_count + random.randint(5, 40)

        await message.answer(
            f"🔥 Заявка принята!\n\n"
            f"Сейчас в очереди: <b>{queue_position}</b>\n\n"
            "Хочешь без ожидания?\n"
            "Жми кнопку «Без очереди» 👇"
        )

    # ===== АДМИН =====

    text = (
        "📸 <b>Новая заявка</b>\n\n"
        f"<b>Тип:</b> {'ПЛАТНАЯ' if is_paid else 'обычная'}\n\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Username:</b> {username}\n"
        f"<b>ID:</b> {message.from_user.id}\n"
        f"<b>Цель:</b> {goal}"
    )

    await bot.send_message(ADMIN_ID, text)

    media = [InputMediaPhoto(media=p) for p in photos]
    await bot.send_media_group(ADMIN_ID, media)

    await state.clear()


# ===== ЗАПУСК =====

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())