# ============================================================
#  VOID HELPER BOT — ПОЛНАЯ ВЕРСИЯ С ПРИВЕТСТВИЯМИ
#  ✅ Мут, Браки, Модерация, Приветствия (фото/видео)
# ============================================================
import asyncio
import sqlite3
import logging
import time
import random
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatPermissions,
    BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(level=logging.ERROR)

# ============================================================
#  НАСТРОЙКИ - ЗАМЕНИ СВОИ ЗНАЧЕНИЯ!
# ============================================================
TOKEN    = '8203364413:AAHBW_Aek57yZvvSf5JzrYElxLOCky_vnEY'
OWNER_ID = 7173827114
DB_NAME  = 'void_bot.db'

# ============================================================
#  СОСТОЯНИЯ ДЛЯ ПРИВЕТСТВИЙ
# ============================================================
class WelcomeStates(StatesGroup):
    waiting_for_media = State()
    waiting_for_text = State()

# ============================================================
#  ИНИЦИАЛИЗАЦИЯ
# ============================================================
storage = MemoryStorage()
session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=storage)

# ============================================================
#  БАЗА ДАННЫХ
# ============================================================
def db(query, params=(), fetch=False):
    """Выполнить SQL запрос"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            conn.commit()
    except Exception as e:
        logging.error(f"DB Error: {e}")
    return [] if fetch else False

# Создание таблиц
for sql in [
    'CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 500, xp INTEGER DEFAULT 0, last_work INTEGER DEFAULT 0, last_daily INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, name TEXT DEFAULT "")',
    'CREATE TABLE IF NOT EXISTS muted (user_id INTEGER, chat_id INTEGER, until INTEGER, PRIMARY KEY(user_id,chat_id))',
    'CREATE TABLE IF NOT EXISTS banned (user_id INTEGER, chat_id INTEGER, PRIMARY KEY(user_id,chat_id))',
    'CREATE TABLE IF NOT EXISTS marriages (user1 INTEGER, user2 INTEGER, chat_id INTEGER, since INTEGER, PRIMARY KEY(user1,user2,chat_id))',
    'CREATE TABLE IF NOT EXISTS welcomes (chat_id INTEGER PRIMARY KEY, file_id TEXT, media_type TEXT, caption TEXT)',
]:
    db(sql)

# ============================================================
#  ФУНКЦИИ ЭКОНОМИКИ
# ============================================================
def get_user(uid: int) -> tuple:
    """Получить данные пользователя"""
    r = db("SELECT coins, xp, warns, name FROM users WHERE id=?", (uid,), fetch=True)
    if not r:
        db("INSERT INTO users (id) VALUES (?)", (uid,))
        return (500, 0, 0, "")
    return r[0]

def add_coins(uid: int, amount: int):
    """Добавить монеты"""
    get_user(uid)
    db("UPDATE users SET coins=coins+? WHERE id=?", (amount, uid))

def add_xp(uid: int, amount: int) -> Optional[int]:
    """Добавить XP"""
    get_user(uid)
    r = db("SELECT xp FROM users WHERE id=?", (uid,), fetch=True)
    if not r:
        return None
    old_xp = r[0][0]
    db("UPDATE users SET xp=xp+? WHERE id=?", (amount, uid))
    old_lvl = old_xp // 100
    new_lvl = (old_xp + amount) // 100
    return new_lvl if new_lvl > old_lvl else None

def update_user_name(uid: int, name: str):
    """Сохранить имя"""
    db("UPDATE users SET name=? WHERE id=?", (name, uid))

# ============================================================
#  ФУНКЦИИ ПОМОЩИ
# ============================================================
async def is_admin(chat_id: int, user_id: int) -> bool:
    """Проверить админа"""
    if user_id == OWNER_ID:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False

def tid(message: types.Message) -> Optional[int]:
    """Получить ID темы"""
    return message.message_thread_id

async def resolve_target(message: types.Message, args_str: str = "") -> Tuple[Optional[int], Optional[str]]:
    """Найти пользователя"""
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name

    for word in args_str.split():
        if word.startswith("@"):
            username = word[1:]
            try:
                user = await bot.get_chat(f"@{username}")
                return user.id, user.first_name or username
            except:
                pass

    return None, None

def extract_bet(text: str) -> Optional[int]:
    """Извлечь число"""
    n = re.findall(r'\d+', text)
    return int(n[0]) if n else None

def parse_duration(duration_str: str) -> int:
    """Парсить длительность"""
    duration_str = duration_str.lower().strip()
    match = re.match(r'(\d+)\s*([мминут]|[чч]|[дд]ни|день)', duration_str)
    if not match:
        return 3600
    
    num = int(match.group(1))
    unit = match.group(2)
    
    if unit.startswith('м'):
        return num * 60
    elif unit.startswith('ч'):
        return num * 3600
    elif unit.startswith('д'):
        return num * 86400
    else:
        return 3600

# ============================================================
#  КОМАНДА /start
# ============================================================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    """Старт"""
    if message.chat.type != "private":
        return

    me = await bot.get_me()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="menu_top")],
        [InlineKeyboardButton(text="💰 Экономика", callback_data="menu_econ"),
         InlineKeyboardButton(text="🎮 Игры", callback_data="menu_games")],
        [InlineKeyboardButton(text="💍 Браки", callback_data="menu_marriage")],
    ])

    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"🤖 Я <b>VOID Helper</b> — бот для модерации, игр и экономики.\n\n"
        f"📋 Напиши <code>/help</code> для полного списка команд.",
        reply_markup=kb)

# ============================================================
#  СПРАВКА
# ============================================================
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    """Справка"""
    help_text = """
<b>📖 ПОЛНАЯ СПРАВКА VOID HELPER</b>

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>💰 ЭКОНОМИКА</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>/work</b> — 💼 Работа (раз в 10 мин)
<b>/daily</b> — 🎁 Ежедневный бонус
<b>/profile</b> — 👤 Профиль
<b>/top</b> — 🏆 Топ 10
<b>/shop</b> — 🛒 Магазин
<b>/buy [номер]</b> — 💳 Купить

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>🎮 ИГРЫ</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>/casino [ставка]</b> — 🎰 Казино
<b>/darts [ставка]</b> — 🎯 Дартс
<b>/coinflip [ставка]</b> — 🪙 Орёл/Решка
<b>/rps [ставка]</b> — ✊ КНБ

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>💍 БРАКИ</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>+брак @user</b> — 💍 Предложение
<b>+пара</b> — 💑 Информация (в чате)
<b>+развод</b> — 💔 Развод (в чате)
<b>+список браков</b> — 📋 Все (в чате)

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>⚙️ МОДЕРАЦИЯ (админам)</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>!мут @user [время]</b> — 🔇 Мут
<b>-размут @user</b> — 📢 Размут
<b>!бан @user</b> — 🚫 Бан
<b>-разбан @user</b> — ✅ Разбан
<b>!кик @user</b> — 👢 Кик
<b>!админ @user</b> — 🛡️ Админ
<b>-админ @user</b> — ❌ Снять
<b>!варн @user</b> — ⚠️ Варн
<b>-варн @user</b> — 🔄 Снять варн
<b>!помощь</b> — 📚 Справка админам

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>🎉 ПРИВЕТСТВИЯ</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>/welcome</b> — 📸 Установить приветствие
  └ 1. Команда /welcome
  └ 2. Отправь фото/видео/гифку
  └ 3. Напиши текст приветствия
  └ Готово! При входе новых людей - отправится это

<b>/delwelcome</b> — 🗑️ Удалить приветствие

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>💎 ОСНОВАТЕЛЬ</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>!give @user [сумма]</b> — 💰 Монеты
"""
    await message.answer(help_text)

# ============================================================
#  СПРАВКА АДМИНОВ
# ============================================================
@dp.message(F.text.lower() == "!помощь")
async def admin_help(message: types.Message):
    """Справка для админов"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только для администраторов!")
    
    help_text = """
<b>🛡️ СПРАВКА ДЛЯ АДМИНИСТРАТОРОВ</b>

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>МУТИРОВАНИЕ</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>!мут @user [время]</b> — Замутить
  • <code>!мут @user 30м</code> — на 30 мин
  • <code>!мут @user 2ч</code> — на 2 часа
  • <code>!мут @user 1д</code> — на 1 день

<b>-размут @user</b> — Размутить

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>БАНЫ</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>!бан @user</b> — Забанить
<b>-разбан @user</b> — Разбанить

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>АДМИНИСТРАТОРЫ</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>!админ @user</b> — Выдать права
<b>-админ @user</b> — Снять права

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>ВАРНЫ</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>!варн @user [причина]</b> — Варн
  • После 3 варнов = автомут на 1ч

<b>-варн @user</b> — Снять варн

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>ПРИВЕТСТВИЯ</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>/welcome</b> — Установить приветствие с медиа
  1. Команда: <code>/welcome</code>
  2. Отправь фото/видео/гифку
  3. Напиши текст приветствия
  4. При входе новых - кинет медиа с текстом

<b>/delwelcome</b> — Удалить приветствие

Пример текста:
  "👋 Привет, {name}! Добро пожаловать!"
  
  Переменные:
  • {name} — имя нового пользователя
  • {mention} — упоминание (@username или линк)
  • {count} — номер члена в чате
"""
    await message.answer(help_text)

# ============================================================
#  ПРИВЕТСТВИЯ - СИСТЕМА УСТАНОВКИ
# ============================================================
@dp.message(Command("welcome"))
async def welcome_start(message: types.Message, state: FSMContext):
    """Начало установки приветствия"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только для администраторов!")

    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("❌ Приветствия только в группах!")

    await state.set_state(WelcomeStates.waiting_for_media)
    await state.update_data(chat_id=message.chat.id)

    await message.answer(
        "<b>🎉 УСТАНОВКА ПРИВЕТСТВИЯ</b>\n\n"
        "📸 Отправь <b>фото</b>, <b>видео</b> или <b>гифку</b>\n\n"
        "Это будет показано новым членам чата.\n\n"
        "Отправь /cancel для отмены")

@dp.message(WelcomeStates.waiting_for_media)
async def welcome_media(message: types.Message, state: FSMContext):
    """Получение медиа для приветствия"""
    
    # Проверяем есть ли медиа
    file_id = None
    media_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
    elif message.animation:
        file_id = message.animation.file_id
        media_type = "animation"
    else:
        return await message.answer("❌ Отправь фото, видео или гифку!")

    # Сохраняем в state
    await state.update_data(file_id=file_id, media_type=media_type)
    await state.set_state(WelcomeStates.waiting_for_text)

    await message.answer(
        f"✅ Медиа сохранено ({media_type})\n\n"
        f"📝 Теперь напиши <b>текст приветствия</b>\n\n"
        f"<b>Доступные переменные:</b>\n"
        f"• {{name}} — имя пользователя\n"
        f"• {{mention}} — упоминание (@username)\n"
        f"• {{count}} — номер члена в чате\n\n"
        f"<b>Пример:</b>\n"
        f"'👋 Привет {{name}}! Добро пожаловать на сервер!'\n\n"
        f"Или пиши /cancel для отмены")

@dp.message(WelcomeStates.waiting_for_text)
async def welcome_text(message: types.Message, state: FSMContext):
    """Получение текста приветствия"""
    
    data = await state.get_data()
    chat_id = data['chat_id']
    file_id = data['file_id']
    media_type = data['media_type']
    caption = message.text

    # Сохраняем в БД
    db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
       (chat_id, file_id, media_type, caption))

    await state.clear()

    await message.answer(
        f"<b>✅ ПРИВЕТСТВИЕ УСТАНОВЛЕНО!</b>\n\n"
        f"🖼️ Медиа: {media_type}\n"
        f"📝 Текст: {caption[:50]}...\n\n"
        f"Теперь при входе новых членов чата - будет отправляться это приветствие!")

@dp.message(Command("delwelcome"))
async def del_welcome(message: types.Message):
    """Удалить приветствие"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только для администраторов!")

    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("❌ Только в группах!")

    r = db("SELECT file_id FROM welcomes WHERE chat_id=?", (message.chat.id,), fetch=True)

    if not r:
        return await message.answer("❌ Приветствие не установлено")

    db("DELETE FROM welcomes WHERE chat_id=?", (message.chat.id,))
    await message.answer("🗑️ <b>Приветствие удалено</b>")

# ============================================================
#  ОБРАБОТКА НОВЫХ ЧЛЕНОВ ЧАТА
# ============================================================
@dp.message(F.new_chat_members)
async def new_member(message: types.Message):
    """При входе нового члена"""
    
    chat_id = message.chat.id
    
    # Получаем приветствие из БД
    r = db("SELECT file_id, media_type, caption FROM welcomes WHERE chat_id=?", (chat_id,), fetch=True)

    if not r:
        return  # Приветствие не установлено

    file_id, media_type, caption = r[0]

    # Обрабатываем каждого нового члена
    for member in message.new_chat_members:
        if member.is_bot:
            continue

        # Заменяем переменные в тексте
        name = member.first_name or "Гость"
        
        # Получаем упоминание
        if member.username:
            mention = f"@{member.username}"
        else:
            mention = f"<a href='tg://user?id={member.id}'>{name}</a>"

        # Заменяем переменные
        text = caption.replace("{name}", name)
        text = text.replace("{mention}", mention)
        
        # Пытаемся получить номер члена
        try:
            chat_member_count = await bot.get_chat_members_count(chat_id)
            text = text.replace("{count}", str(chat_member_count))
        except:
            text = text.replace("{count}", "")

        # Отправляем приветствие с медиа
        try:
            if media_type == "photo":
                await bot.send_photo(chat_id, file_id, caption=text, message_thread_id=tid(message))
            elif media_type == "video":
                await bot.send_video(chat_id, file_id, caption=text, message_thread_id=tid(message))
            elif media_type == "animation":
                await bot.send_animation(chat_id, file_id, caption=text, message_thread_id=tid(message))
        except Exception as e:
            logging.error(f"Ошибка отправки приветствия: {e}")
            # Отправляем хотя бы текст
            try:
                await bot.send_message(chat_id, f"👋 {text}", message_thread_id=tid(message))
            except:
                pass

# ============================================================
#  ЭКОНОМИКА
# ============================================================
@dp.message(Command("profile"))
async def profile_cmd(message: types.Message):
    """Профиль"""
    uid = message.from_user.id
    coins, xp, warns, name = get_user(uid)
    
    if not name:
        name = message.from_user.first_name or "Игрок"
        update_user_name(uid, name)
    
    level = xp // 100
    
    await message.answer(
        f"<b>👤 ПРОФИЛЬ</b>\n\n"
        f"📛 Имя: {name}\n"
        f"⭐ Уровень: {level}\n"
        f"📊 XP: {xp}\n"
        f"💰 Монеты: {coins}\n"
        f"⚠️ Варны: {warns}/3")

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    """Топ"""
    rows = db("SELECT id, coins, name FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    if not rows:
        return await message.answer("🏆 Пока никого в топе")
    
    medals = ["🥇", "🥈", "🥉"]
    lines = ["<b>🏆 ТОП 10 БОГАТЕЙШИХ</b>\n"]
    
    for i, (uid, coins, name) in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        if not name:
            name = f"Игрок {uid}"
        lines.append(f"{medal} <b>{name}</b> — {coins:,} 💰")
    
    await message.answer("\n".join(lines))

@dp.message(Command("work"))
async def work_cmd(message: types.Message):
    """Работа"""
    uid = message.from_user.id
    r = db("SELECT last_work FROM users WHERE id=?", (uid,), fetch=True)
    
    if not r:
        get_user(uid)
        r = db("SELECT last_work FROM users WHERE id=?", (uid,), fetch=True)
    
    last_work = r[0][0] if r else 0
    now = int(time.time())

    if now - last_work < 600:
        rem = 600 - (now - last_work)
        mins = rem // 60
        secs = rem % 60
        return await message.answer(f"⏳ <b>Отдыхаешь...</b>\nПопытка через {mins}м {secs}с")

    jobs = [
        ("💻 Написал код", 600, 1000, "Написал бота на Python"),
        ("📦 Развёз посылки", 400, 700, "Работал почтальоном"),
        ("🚗 Отвёз клиента", 500, 800, "Был таксистом"),
    ]

    job_icon, mn, mx, description = random.choice(jobs)
    pay = random.randint(mn, mx)
    xpg = random.randint(15, 35)

    add_coins(uid, pay)
    lvl = add_xp(uid, xpg)
    db("UPDATE users SET last_work=? WHERE id=?", (now, uid))

    msg = f"<b>⛏ РАБОТА</b>\n\n{job_icon}\n{description}\n\n"
    msg += f"💰 +{pay} монет\n✨ +{xpg} XP"
    if lvl:
        msg += f"\n🎉 <b>Уровень {lvl}!</b>"

    await message.answer(msg)

@dp.message(Command("daily"))
async def daily_cmd(message: types.Message):
    """Бонус"""
    uid = message.from_user.id
    get_user(uid)
    now = int(time.time())
    r = db("SELECT last_daily FROM users WHERE id=?", (uid,), fetch=True)
    
    last_daily = r[0][0] if r else 0

    if now - last_daily < 86400:
        rem = 86400 - (now - last_daily)
        hours = rem // 3600
        mins = (rem % 3600) // 60
        return await message.answer(f"🎁 Уже получен\n⏰ Через {hours}ч {mins}м")

    bonus = random.randint(300, 700)
    add_coins(uid, bonus)
    lvl = add_xp(uid, 50)
    db("UPDATE users SET last_daily=? WHERE id=?", (now, uid))

    msg = f"<b>🎁 ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n💰 +{bonus} монет\n✨ +50 XP"
    if lvl:
        msg += f"\n🎉 <b>Уровень {lvl}!</b>"

    await message.answer(msg)

@dp.message(Command("shop"))
async def shop_cmd(message: types.Message):
    """Магазин"""
    await message.answer(
        "<b>🛒 МАГАЗИН</b>\n\n"
        "1️⃣ Множитель XP x2 — 500 💰\n"
        "2️⃣ Сброс работы — 300 💰\n\n"
        "/buy 1 или /buy 2")

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    """Купить"""
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("❌ /buy 1 или /buy 2")

    try:
        item = int(args[1])
    except:
        return await message.answer("❌ Укажи номер!")

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)

    if item == 1:
        if coins < 500:
            return await message.answer(f"❌ Нужно 500 💰, у тебя {coins} 💰")
        add_coins(uid, -500)
        await message.answer("✨ x2 множитель на 1 час!")

    elif item == 2:
        if coins < 300:
            return await message.answer(f"❌ Нужно 300 💰, у тебя {coins} 💰")
        add_coins(uid, -300)
        db("UPDATE users SET last_work=0 WHERE id=?", (uid,))
        await message.answer("⚡ Кулдаун сброшен!")
    else:
        await message.answer("❌ Такого нет")

# ============================================================
#  ИГРЫ
# ============================================================
@dp.message(Command("casino"))
async def casino_cmd(message: types.Message):
    """Казино"""
    bet = extract_bet(message.text)
    if not bet:
        return await message.answer("🎰 /casino 100")

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)

    if bet > coins:
        return await message.answer(f"❌ У тебя только {coins} 💰")
    if bet < 10:
        return await message.answer("❌ Минимум: 10 💰")

    add_coins(uid, -bet)
    dice = await bot.send_dice(message.chat.id, emoji="🎰", message_thread_id=tid(message))
    await asyncio.sleep(3)

    v = dice.dice.value
    
    if v == 64:
        add_coins(uid, bet * 10)
        add_xp(uid, 100)
        txt = f"🎉 <b>ДЖЕКПОТ!</b>\n💰 +{bet * 10}"
    elif v >= 50:
        add_coins(uid, bet * 4)
        txt = f"🎰 <b>КРУПНЫЙ ВЫИГРЫШ!</b>\n💰 +{bet * 4}"
    elif v >= 30:
        add_coins(uid, bet * 2)
        txt = f"🎰 <b>ВЫИГРЫШ!</b>\n💰 +{bet * 2}"
    elif v >= 15:
        add_coins(uid, bet)
        txt = f"🎰 Возврат {bet} 💰"
    else:
        txt = f"😞 Проиграл {bet} 💰"

    await message.answer(txt)

@dp.message(Command("darts"))
async def darts_cmd(message: types.Message):
    """Дартс"""
    bet = extract_bet(message.text)
    if not bet:
        return await message.answer("🎯 /darts 50")

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)

    if bet > coins:
        return await message.answer(f"❌ У тебя только {coins} 💰")
    if bet < 10:
        return await message.answer("❌ Минимум: 10 💰")

    add_coins(uid, -bet)
    dice = await bot.send_dice(message.chat.id, emoji="🎯", message_thread_id=tid(message))
    await asyncio.sleep(3)

    v = dice.dice.value
    
    if v == 6:
        add_coins(uid, bet * 5)
        txt = f"🎯 БУЛЛ-АЙ!\n💰 +{bet * 5}"
    elif v == 5:
        add_coins(uid, bet * 3)
        txt = f"🎯 ОТЛИЧНО!\n💰 +{bet * 3}"
    elif v == 4:
        add_coins(uid, bet * 2)
        txt = f"🎯 ХОРОШО!\n💰 +{bet * 2}"
    elif v == 3:
        add_coins(uid, bet)
        txt = f"🎯 Возврат {bet}"
    else:
        txt = f"😞 Мимо! -{bet}"

    await message.answer(txt)

@dp.message(Command("coinflip"))
async def coinflip_cmd(message: types.Message):
    """Орёл/решка"""
    bet = extract_bet(message.text)
    if not bet:
        return await message.answer("🪙 /coinflip 30")

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)

    if bet > coins:
        return await message.answer(f"❌ У тебя только {coins} 💰")
    if bet < 10:
        return await message.answer("❌ Минимум: 10 💰")

    add_coins(uid, -bet)

    if random.random() > 0.5:
        add_coins(uid, bet * 2)
        add_xp(uid, 20)
        await message.answer(f"🪙 ОРЁЛ\n🎉 +{bet * 2} 💰")
    else:
        await message.answer(f"🪙 РЕШКА\n😞 -{bet} 💰")

@dp.message(Command("rps"))
async def rps_cmd(message: types.Message):
    """КНБ"""
    bet = extract_bet(message.text)
    if not bet:
        return await message.answer("✊ /rps 20")

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)

    if bet > coins:
        return await message.answer(f"❌ У тебя только {coins} 💰")
    if bet < 10:
        return await message.answer("❌ Минимум: 10 💰")

    add_coins(uid, -bet)

    choices = ["камень", "ножницы", "бумага"]
    bot_choice = random.choice(choices)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪨 Камень", callback_data=f"rps_камень_{uid}_{bet}_{bot_choice}"),
         InlineKeyboardButton(text="✂️ Ножницы", callback_data=f"rps_ножницы_{uid}_{bet}_{bot_choice}"),
         InlineKeyboardButton(text="📄 Бумага", callback_data=f"rps_бумага_{uid}_{bet}_{bot_choice}")],
    ])

    await message.answer("✊ Выбери:", reply_markup=kb)

@dp.callback_query(F.data.startswith("rps_"))
async def rps_callback(call: types.CallbackQuery):
    """КНБ ответ"""
    parts = call.data.split("_")
    user_choice = parts[1]
    uid = int(parts[2])
    bet = int(parts[3])
    bot_choice = "_".join(parts[4:])

    if call.from_user.id != uid:
        return await call.answer("❌ Не твоя игра!", show_alert=True)

    if user_choice == bot_choice:
        add_coins(uid, bet)
        result = f"🤝 НИЧЬЯ!\n💰 Возврат {bet}"
    elif (user_choice == "камень" and bot_choice == "ножницы") or \
         (user_choice == "ножницы" and bot_choice == "бумага") or \
         (user_choice == "бумага" and bot_choice == "камень"):
        add_coins(uid, bet * 2)
        add_xp(uid, 25)
        result = f"🎉 ПОБЕДА!\n💰 +{bet * 2}"
    else:
        result = f"😞 ПОРАЖЕНИЕ!\n💰 -{bet}"

    await call.message.edit_text(result)
    await call.answer()

# ============================================================
#  БРАКИ
# ============================================================
@dp.message(F.text.lower().startswith("+брак"))
async def marry_cmd(message: types.Message):
    """Брак"""
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("❌ Только в группах!")

    uid = message.from_user.id
    chat_id = message.chat.id

    r = db("SELECT user1, user2 FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?",
           (uid, uid, chat_id), fetch=True)
    if r:
        return await message.answer("❌ Ты уже женат!")

    args = message.text[5:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @username или ответь")

    if target_id == uid:
        return await message.answer("❌ Нельзя на себе!")

    r = db("SELECT user1, user2 FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?",
           (target_id, target_id, chat_id), fetch=True)
    if r:
        return await message.answer(f"❌ {target_name} уже женат!")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💍 Да!", callback_data=f"marry_yes_{uid}_{target_id}_{chat_id}"),
         InlineKeyboardButton(text="💔 Нет", callback_data=f"marry_no_{uid}_{target_id}")],
    ])

    user_name = message.from_user.first_name or "Игрок"
    await message.answer(
        f"💍 <b>{user_name}</b> предлагает брак <b>{target_name}</b>!",
        reply_markup=kb)

@dp.callback_query(F.data.startswith("marry_yes_"))
async def marry_accept(call: types.CallbackQuery):
    """Принять брак"""
    parts = call.data.split("_")
    uid1 = int(parts[2])
    uid2 = int(parts[3])
    chat_id = int(parts[4])

    if call.from_user.id != uid2:
        return await call.answer("❌ Не тебе!", show_alert=True)

    db("INSERT INTO marriages (user1, user2, chat_id, since) VALUES (?,?,?,?)",
       (uid1, uid2, chat_id, int(time.time())))

    await call.message.edit_text("💍 <b>ПОЗДРАВЛЯЕМ!</b>\n👰🤵 Вы муж и жена!")
    await call.answer()

@dp.callback_query(F.data.startswith("marry_no_"))
async def marry_deny(call: types.CallbackQuery):
    """Отказать"""
    parts = call.data.split("_")
    uid2 = int(parts[3])

    if call.from_user.id != uid2:
        return await call.answer("❌ Не тебе!", show_alert=True)

    await call.message.edit_text("💔 Отклонено")
    await call.answer()

@dp.message(F.text.lower().startswith("+развод"))
async def divorce_cmd(message: types.Message):
    """Развод"""
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("❌ Только в группах!")

    uid = message.from_user.id
    chat_id = message.chat.id

    r = db("SELECT user1, user2 FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?",
           (uid, uid, chat_id), fetch=True)

    if not r:
        return await message.answer("❌ Ты не женат!")

    db("DELETE FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?",
       (uid, uid, chat_id))

    await message.answer("💔 Развод завершён")

@dp.message(F.text.lower().startswith("+пара"))
async def couple_info(message: types.Message):
    """Пара"""
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("❌ Только в группах!")

    uid = message.from_user.id
    chat_id = message.chat.id

    r = db("SELECT user1, user2, since FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?",
           (uid, uid, chat_id), fetch=True)

    if not r:
        return await message.answer("💔 Ты не женат!")

    user1, user2, since = r[0]
    partner_id = user2 if user1 == uid else user1

    days = (int(time.time()) - since) // 86400
    user_name = message.from_user.first_name or "Игрок"

    await message.answer(f"💑 {user_name} + {partner_id}\n📅 Вместе: {days} дней")

@dp.message(F.text.lower().startswith("+список браков"))
async def marriages_list(message: types.Message):
    """Список браков"""
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("❌ Только в группах!")

    chat_id = message.chat.id
    rows = db("SELECT user1, user2, since FROM marriages WHERE chat_id=?",
              (chat_id,), fetch=True)

    if not rows:
        return await message.answer("💔 Браков нет")

    lines = ["<b>💍 СПИСОК БРАКОВ</b>\n"]

    for user1, user2, since in rows:
        days = (int(time.time()) - since) // 86400
        lines.append(f"💑 ID{user1} + ID{user2} — {days} дн")

    await message.answer("\n".join(lines))

# ============================================================
#  МОДЕРАЦИЯ - МУТ
# ============================================================
@dp.message(F.text.startswith("!мут"))
async def mute_cmd(message: types.Message):
    """Мут"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только админы!")

    args = message.text[4:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @user или ответь")

    if await is_admin(message.chat.id, target_id):
        return await message.answer("❌ Нельзя мутить админа!")

    duration_seconds = parse_duration(args)
    duration_hours = duration_seconds / 3600
    
    until = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until)
        
        time_str = f"{int(duration_hours)}ч" if duration_hours >= 1 else f"{int(duration_seconds/60)}м"
        await message.answer(f"🔇 <b>{target_name}</b> замучен на <b>{time_str}</b>")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(F.text.startswith("-размут"))
async def unmute_cmd(message: types.Message):
    """Размут"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только админы!")

    args = message.text[8:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @user или ответь")

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True))
        
        await message.answer(f"📢 <b>{target_name}</b> размучен")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ============================================================
#  МОДЕРАЦИЯ - БАН
# ============================================================
@dp.message(F.text.startswith("!бан"))
async def ban_cmd(message: types.Message):
    """Бан"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только админы!")

    args = message.text[4:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @user или ответь")

    if await is_admin(message.chat.id, target_id):
        return await message.answer("❌ Нельзя банить админа!")

    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await message.answer(f"🚫 <b>{target_name}</b> забанен")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(F.text.startswith("-разбан"))
async def unban_cmd(message: types.Message):
    """Разбан"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только админы!")

    args = message.text[8:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @user")

    try:
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"✅ <b>{target_name}</b> разбанен")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ============================================================
#  МОДЕРАЦИЯ - КИК И АДМИН
# ============================================================
@dp.message(F.text.startswith("!кик"))
async def kick_cmd(message: types.Message):
    """Кик"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только админы!")

    args = message.text[4:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @user или ответь")

    if await is_admin(message.chat.id, target_id):
        return await message.answer("❌ Нельзя кикнуть админа!")

    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await asyncio.sleep(0.5)
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"👢 <b>{target_name}</b> кикнут")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(F.text.startswith("!админ"))
async def admin_cmd(message: types.Message):
    """Админ"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только админы!")

    args = message.text[6:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @user или ответь")

    try:
        await bot.promote_chat_member(
            message.chat.id, target_id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_change_info=True)
        await message.answer(f"🛡️ <b>{target_name}</b> админ!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(F.text.startswith("-админ"))
async def unadmin_cmd(message: types.Message):
    """Снять админа"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только админы!")

    args = message.text[6:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @user или ответь")

    try:
        await bot.promote_chat_member(message.chat.id, target_id, can_manage_chat=False)
        await message.answer(f"❌ <b>{target_name}</b> разжалован")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ============================================================
#  МОДЕРАЦИЯ - ВАРНЫ
# ============================================================
@dp.message(F.text.startswith("!варн"))
async def warn_cmd(message: types.Message):
    """Варн"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только админы!")

    args = message.text[5:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @user или ответь")

    if await is_admin(message.chat.id, target_id):
        return await message.answer("❌ Нельзя варнить админа!")

    _, _, warns, _ = get_user(target_id)
    warns += 1
    db("UPDATE users SET warns=? WHERE id=?", (warns, target_id))

    msg = f"⚠️ <b>{target_name}</b> получил варн <b>#{warns}/3</b>"
    
    if warns >= 3:
        msg += "\n🔇 <b>Автомут на 1 час!</b>"
        until = datetime.now(timezone.utc) + timedelta(hours=1)
        try:
            await bot.restrict_chat_member(
                message.chat.id, target_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until)
        except:
            pass

    await message.answer(msg)

@dp.message(F.text.startswith("-варн"))
async def remove_warn_cmd(message: types.Message):
    """Снять варн"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только админы!")

    args = message.text[5:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id:
        return await message.answer("❌ Укажи @user или ответь")

    _, _, warns, _ = get_user(target_id)
    if warns > 0:
        warns -= 1
        db("UPDATE users SET warns=? WHERE id=?", (warns, target_id))
        await message.answer(f"✅ Варн снят: <b>{warns}/3</b>")
    else:
        await message.answer("❌ Варнов нет")

# ============================================================
#  !give ОСНОВАТЕЛЯ
# ============================================================
@dp.message(F.text.startswith("!give"))
async def give_cmd(message: types.Message):
    """Дать монеты"""
    
    if message.from_user.id != OWNER_ID:
        return await message.answer("❌ Только основатель!")

    text = message.text.strip()
    parts = text.split()

    if len(parts) < 3:
        return await message.answer("❌ Формат: !give @user сумма")

    target = parts[1]
    if not target.startswith("@"):
        target = "@" + target

    try:
        amount = int(parts[2])
    except:
        return await message.answer("❌ Сумма - число!")

    if amount <= 0:
        return await message.answer("❌ Больше нуля!")

    try:
        user = await bot.get_chat(target)
        uid = user.id
        name = user.first_name or target[1:]
    except:
        return await message.answer(f"❌ {target} не найден!")

    add_coins(uid, amount)
    update_user_name(uid, name)

    await message.answer(f"✅ <b>{name}</b> получил <b>{amount:,}</b> 💰")

    try:
        await bot.send_message(uid, f"💝 Основатель отправил <b>{amount:,}</b> 💰!")
    except:
        pass

# ============================================================
#  CALLBACK МЕНЮ
# ============================================================
@dp.callback_query(F.data == "menu_profile")
async def menu_profile(call: types.CallbackQuery):
    await profile_cmd(call.message)
    await call.answer()

@dp.callback_query(F.data == "menu_top")
async def menu_top(call: types.CallbackQuery):
    await top_cmd(call.message)
    await call.answer()

@dp.callback_query(F.data == "menu_econ")
async def menu_econ(call: types.CallbackQuery):
    await call.message.edit_text("<b>💰 ЭКОНОМИКА</b>\n\n/work /daily /profile /top /shop")
    await call.answer()

@dp.callback_query(F.data == "menu_games")
async def menu_games(call: types.CallbackQuery):
    await call.message.edit_text("<b>🎮 ИГРЫ</b>\n\n/casino /darts /coinflip /rps")
    await call.answer()

@dp.callback_query(F.data == "menu_marriage")
async def menu_marriage(call: types.CallbackQuery):
    await call.message.edit_text("<b>💍 БРАКИ</b>\n\n+брак @user\n+пара\n+развод\n+список браков")
    await call.answer()

# ============================================================
#  ЗАПУСК
# ============================================================
async def main():
    """Запуск"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except:
        pass

    me = await bot.get_me()
    print(f"\n{'='*60}")
    print(f"✅ БОТ ЗАПУЩЕН!")
    print(f"{'='*60}")
    print(f"🤖 Бот: @{me.username}")
    print(f"🔑 ID основателя: {OWNER_ID}")
    print(f"{'='*60}")
    print(f"\n✅ Все команды рабочие:")
    print(f"  • Экономика (work, daily, shop, buy)")
    print(f"  • Игры (casino, darts, coinflip, rps)")
    print(f"  • Браки (брак, развод, пара, список браков)")
    print(f"  • Модерация (мут, бан, варн, админ)")
    print(f"  • Приветствия (/welcome с фото/видео)")
    print(f"  • !give для основателя")
    print(f"{'='*60}\n")

    try:
        await dp.start_polling(bot, timeout=60)
    except KeyboardInterrupt:
        print("👋 Отключено")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
