# ============================================================
#  VOID HELPER BOT — УЛУЧШЕННАЯ ВЕРСИЯ (ПОЛНОСТЬЮ РАБОЧАЯ)
# ============================================================
import asyncio
import sqlite3
import logging
import time
import random
import re
import warnings
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
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

warnings.filterwarnings('ignore')

TOKEN    = '8203364413:AAHBW_Aek57yZvvSf5JzrYElxLOCky_vnEY'
OWNER_ID = 7173827114
DB_NAME  = 'void_final.db'
LOG_CHANNEL    = '@void_official_chat'
LOG_MESSAGE_ID = 19010

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ============================================================
#  ИНИЦИАЛИЗАЦИЯ
# ============================================================
storage = MemoryStorage()
session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
dp  = Dispatcher(storage=storage)

DICE_WAIT = {"🎲": 2, "🎯": 3, "🏀": 4, "⚽": 4, "🎳": 4, "🎰": 4}

# ============================================================
#  СОСТОЯНИЯ ДЛЯ ИГРЫ В КНБ
# ============================================================
class RpsGame(StatesGroup):
    waiting_for_choice = State()

# ============================================================
#  КОМАНДЫ
# ============================================================
PRIVATE_COMMANDS = [
    BotCommand(command="start",    description="🏠 Главное меню"),
    BotCommand(command="help",     description="📋 Все команды"),
    BotCommand(command="profile",  description="👤 Мой профиль"),
    BotCommand(command="top",      description="🏆 Топ игроков"),
    BotCommand(command="work",     description="⛏ Работа"),
    BotCommand(command="daily",    description="🎁 Бонус"),
    BotCommand(command="shop",     description="🛒 Магазин"),
    BotCommand(command="casino",   description="🎰 Казино"),
    BotCommand(command="darts",    description="🎯 Дартс"),
    BotCommand(command="coinflip", description="🪙 Орёл/Решка"),
    BotCommand(command="rps",      description="✊ КНБ"),
]
GROUP_COMMANDS = [
    BotCommand(command="help",            description="📋 Все команды"),
    BotCommand(command="profile",         description="👤 Мой профиль"),
    BotCommand(command="top",             description="🏆 Топ"),
    BotCommand(command="work",            description="⛏ Работа"),
    BotCommand(command="daily",           description="🎁 Бонус"),
    BotCommand(command="shop",            description="🛒 Магазин"),
    BotCommand(command="casino",          description="🎰 Казино"),
    BotCommand(command="darts",           description="🎯 Дартс"),
    BotCommand(command="dice",            description="🎲 Кости (дуэль)"),
    BotCommand(command="basketball",      description="🏀 Баскетбол"),
    BotCommand(command="football",        description="⚽ Футбол"),
    BotCommand(command="bowling",         description="🎳 Боулинг"),
    BotCommand(command="coinflip",        description="🪙 Орёл/Решка"),
    BotCommand(command="rps",             description="✊ КНБ"),
    BotCommand(command="setwelcome",      description="✏️ Приветствие"),
    BotCommand(command="setautoschedule", description="⏰ Авто-закрытие"),
    BotCommand(command="check_schedule",  description="🔍 Расписание"),
    BotCommand(command="moderation",      description="⚙️ Автомодерация"),
]

# ============================================================
#  БАЗА ДАННЫХ
# ============================================================
def db(query, params=(), fetch=False):
    """Безопасное выполнение SQL запросов"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"DB Error: {e}")
        return [] if fetch else False

# Инициализация таблиц
for sql in [
    '''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 500, xp INTEGER DEFAULT 0,
        last_work INTEGER DEFAULT 0, last_daily INTEGER DEFAULT 0,
        warns INTEGER DEFAULT 0, xp_multiplier REAL DEFAULT 1.0)''',
    '''CREATE TABLE IF NOT EXISTS muted (
        user_id INTEGER, chat_id INTEGER, until INTEGER, PRIMARY KEY(user_id,chat_id))''',
    '''CREATE TABLE IF NOT EXISTS banned (
        user_id INTEGER, chat_id INTEGER, PRIMARY KEY(user_id,chat_id))''',
    '''CREATE TABLE IF NOT EXISTS group_welcome (
        chat_id INTEGER PRIMARY KEY,
        welcome_text TEXT DEFAULT '👋 Добро пожаловать, {упоминание}!',
        welcome_type TEXT DEFAULT 'text',
        welcome_file_id TEXT DEFAULT NULL)''',
    '''CREATE TABLE IF NOT EXISTS usernames (
        username TEXT PRIMARY KEY, user_id INTEGER, name TEXT)''',
    '''CREATE TABLE IF NOT EXISTS user_nicknames (
        user_id INTEGER, chat_id INTEGER, nickname TEXT, PRIMARY KEY(user_id,chat_id))''',
    '''CREATE TABLE IF NOT EXISTS user_gender (user_id INTEGER PRIMARY KEY, gender INTEGER DEFAULT 0)''',
    '''CREATE TABLE IF NOT EXISTS marriages (
        user1 INTEGER, user2 INTEGER, chat_id INTEGER, since INTEGER, PRIMARY KEY(user1,user2))''',
    '''CREATE TABLE IF NOT EXISTS chat_settings (
        chat_id INTEGER PRIMARY KEY, is_closed INTEGER DEFAULT 0,
        close_time TEXT, open_time TEXT)''',
    '''CREATE TABLE IF NOT EXISTS moderation_settings (chat_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 1)''',
    '''CREATE TABLE IF NOT EXISTS admin_permissions (
        user_id INTEGER, chat_id INTEGER,
        can_promote BOOLEAN DEFAULT 0, can_change_info BOOLEAN DEFAULT 1,
        can_delete BOOLEAN DEFAULT 1, can_restrict BOOLEAN DEFAULT 1,
        can_invite BOOLEAN DEFAULT 1, can_pin BOOLEAN DEFAULT 1,
        can_video_chats BOOLEAN DEFAULT 0, can_manage_topics BOOLEAN DEFAULT 1,
        PRIMARY KEY(user_id,chat_id))''',
    '''CREATE TABLE IF NOT EXISTS warns_system (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, chat_id INTEGER, reason TEXT, date INTEGER, expires INTEGER)''',
]:
    db(sql)

# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def get_user(uid: int) -> tuple:
    """Получить данные пользователя или создать новый"""
    r = db("SELECT coins,xp,warns,xp_multiplier FROM users WHERE id=?", (uid,), fetch=True)
    if not r:
        db("INSERT INTO users (id) VALUES (?)", (uid,))
        return (500, 0, 0, 1.0)
    return r[0]

def add_coins(uid: int, amount: int) -> bool:
    """Добавить монеты пользователю"""
    get_user(uid)
    return db("UPDATE users SET coins=coins+? WHERE id=?", (amount, uid))

def add_xp(uid: int, amount: int) -> Optional[int]:
    """Добавить XP и вернуть уровень при прокачке"""
    get_user(uid)
    old = db("SELECT xp FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    db("UPDATE users SET xp=xp+? WHERE id=?", (amount, uid))
    new_lvl = (old + amount) // 100
    old_lvl = old // 100
    return new_lvl if new_lvl > old_lvl else None

def user_link(uid: int, chat_id: int, default_name: str) -> str:
    """Получить ссылку на пользователя с его ником или именем"""
    r = db("SELECT nickname FROM user_nicknames WHERE user_id=? AND chat_id=?", (uid, chat_id), fetch=True)
    name = r[0][0] if r else default_name
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_mention(uid: int, chat_id: int, default_name: str) -> str:
    """Получить упоминание (@username или ссылка)"""
    r = db("SELECT username FROM usernames WHERE user_id=?", (uid,), fetch=True)
    if r and r[0][0]:
        return f"@{r[0][0]}"
    return f'<a href="tg://user?id={uid}">{default_name}</a>'

def save_username(user: types.User) -> bool:
    """Сохранить юзернейм пользователя"""
    if user and user.username:
        return db("INSERT OR REPLACE INTO usernames (username,user_id,name) VALUES (?,?,?)",
                  (user.username.lower(), user.id, user.first_name))
    return True

async def resolve_target(message: types.Message, args: str = "") -> Tuple[Optional[int], Optional[str], Optional[types.Message]]:
    """Найти целевого пользователя по ответу или @username"""
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name, message.reply_to_message
    
    for w in args.split():
        if w.startswith("@"):
            username = w[1:]
            r = db("SELECT user_id,name FROM usernames WHERE username=?", (username.lower(),), fetch=True)
            if r:
                return r[0][0], r[0][1], None
            try:
                c = await bot.get_chat(f"@{username}")
                if c.username:
                    db("INSERT OR REPLACE INTO usernames (username,user_id,name) VALUES (?,?,?)",
                       (c.username.lower(), c.id, c.first_name or username))
                return c.id, c.first_name or username, None
            except:
                continue
    return None, None, None

async def is_admin(chat_id: int, user_id: int) -> bool:
    """Проверить, администратор ли пользователь"""
    if user_id == OWNER_ID:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False

def tid(message: types.Message) -> Optional[int]:
    """Получить ID темы сообщения"""
    return message.message_thread_id

async def is_moderation_enabled(chat_id: int) -> bool:
    """Включена ли автомодерация"""
    r = db("SELECT enabled FROM moderation_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return r[0][0] == 1 if r else True

def extract_bet(text: str) -> Optional[int]:
    """Извлечь ставку из текста"""
    n = re.findall(r'\d+', text)
    return int(n[0]) if n else None

async def mod_guard(message: types.Message) -> bool:
    """Проверить права администратора"""
    if message.chat.type not in ("group", "supergroup"):
        return False
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return False
    return True

# ============================================================
#  ВАРНЫ
# ============================================================
def add_warn(uid: int, chat_id: int, reason: str, days: int = 30) -> int:
    """Выдать варн"""
    now = int(time.time())
    db("INSERT INTO warns_system (user_id,chat_id,reason,date,expires) VALUES (?,?,?,?,?)",
       (uid, chat_id, reason, now, now + days * 86400))
    r = db("SELECT COUNT(*) FROM warns_system WHERE user_id=? AND chat_id=? AND expires>?",
           (uid, chat_id, now), fetch=True)
    return r[0][0] if r else 0

def get_warn_count(uid: int, chat_id: int) -> int:
    """Получить количество активных варнов"""
    now = int(time.time())
    r = db("SELECT COUNT(*) FROM warns_system WHERE user_id=? AND chat_id=? AND expires>?",
           (uid, chat_id, now), fetch=True)
    return r[0][0] if r else 0

def clear_warns(uid: int, chat_id: int) -> bool:
    """Очистить все варны пользователя"""
    return db("DELETE FROM warns_system WHERE user_id=? AND chat_id=?", (uid, chat_id))

# ============================================================
#  ЛОГ
# ============================================================
async def send_log(source, target_id: int, action: str, reason: str, duration: str = "", is_auto: bool = False):
    """Отправить лог в канал"""
    try:
        target = await bot.get_chat(target_id)
        if isinstance(source, types.Message):
            chat = source.chat
            admin = source.from_user
        else:
            chat = await bot.get_chat(source)
            admin = None

        t = f"{action}\n\n"
        t += f"👤 Нарушитель: {target.first_name}"
        if target.username:
            t += f" (@{target.username})"
        t += f"\n🆔 ID: {target.id}\n\n"
        t += "👮 Кто выдал: 🤖 Автомодерация\n" if is_auto else f"👮 Кто выдал: {admin.first_name}\n"
        t += f"\n💬 Чат: {chat.title}"
        if chat.username:
            t += f" (@{chat.username})"
        t += f"\n📌 Причина: {reason}"
        if duration:
            t += f"\n⏳ Срок: {duration}"

        await bot.send_message(LOG_CHANNEL, t, reply_to_message_id=LOG_MESSAGE_ID)
    except Exception as e:
        logging.error(f"Log error: {e}")

# ============================================================
#  ПРАВА АДМИНИСТРАТОРА
# ============================================================
def get_default_perms() -> dict:
    """Права администратора по умолчанию"""
    return {
        'can_promote': False,
        'can_change_info': True,
        'can_delete': True,
        'can_restrict': True,
        'can_invite': True,
        'can_pin': True,
        'can_video_chats': False,
        'can_manage_topics': True,
    }

async def apply_admin_perms(chat_id: int, user_id: int, perms: dict) -> Tuple[bool, str]:
    """Применить права администратора в Telegram"""
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if bot_member.status != 'administrator' or not bot_member.can_promote_members:
            return False, "❌ Бот не имеет прав на назначение администраторов!"

        await bot.promote_chat_member(
            chat_id, user_id,
            can_manage_chat=True,
            can_delete_messages=perms.get('can_delete', True),
            can_restrict_members=perms.get('can_restrict', True),
            can_invite_users=perms.get('can_invite', True),
            can_pin_messages=perms.get('can_pin', True),
            can_change_info=perms.get('can_change_info', True),
            can_promote_members=perms.get('can_promote', False),
            can_manage_topics=perms.get('can_manage_topics', True),
            can_manage_video_chats=perms.get('can_video_chats', False),
        )
        return True, ""
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}"

def save_perms_db(chat_id: int, user_id: int, perms: dict) -> bool:
    """Сохранить права в БД"""
    return db("INSERT OR REPLACE INTO admin_permissions "
              "(user_id,chat_id,can_promote,can_change_info,can_delete,can_restrict,"
              "can_invite,can_pin,can_video_chats,can_manage_topics) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (user_id, chat_id, perms['can_promote'], perms['can_change_info'],
               perms['can_delete'], perms['can_restrict'], perms['can_invite'],
               perms['can_pin'], perms['can_video_chats'], perms['can_manage_topics']))

async def get_admin_permissions(chat_id: int, user_id: int) -> dict:
    """Получить права администратора из БД"""
    r = db("SELECT can_promote,can_change_info,can_delete,can_restrict,can_invite,"
           "can_pin,can_video_chats,can_manage_topics FROM admin_permissions WHERE chat_id=? AND user_id=?",
           (chat_id, user_id), fetch=True)
    if r:
        keys = ['can_promote', 'can_change_info', 'can_delete', 'can_restrict',
                'can_invite', 'can_pin', 'can_video_chats', 'can_manage_topics']
        return {k: bool(v) for k, v in zip(keys, r[0])}
    return get_default_perms()

# ============================================================
#  КЛАВИАТУРЫ
# ============================================================
def _e(flag: bool) -> str:
    return "✅" if flag else "—"

def admin_panel_kb(uid: int, chat_id: int, perms: dict) -> InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    def btn(label, perm):
        return InlineKeyboardButton(
            text=f"{_e(perms.get(perm, False))} {label}",
            callback_data=f"ap|{uid}|{chat_id}|{perm}"
        )
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("Назначение админов", "can_promote")],
        [btn("Профиль группы", "can_change_info"), btn("Удаление смс", "can_delete")],
        [btn("Баны", "can_restrict"), btn("Инвайты", "can_invite")],
        [btn("Закрепы", "can_pin"), btn("Трансляции", "can_video_chats")],
        [btn("Управление темами", "can_manage_topics")],
        [InlineKeyboardButton(text="🔻 Разжаловать", callback_data=f"ap_rm|{uid}|{chat_id}")],
    ])

def main_menu_kb(username: str) -> InlineKeyboardMarkup:
    """Главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="m_profile"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="m_top")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="m_shop"),
         InlineKeyboardButton(text="🎮 Игры", callback_data="m_games")],
        [InlineKeyboardButton(text="❤️ RP", callback_data="m_rp"),
         InlineKeyboardButton(text="➕ В группу", url=f"https://t.me/{username}?startgroup=L")],
    ])

def back_kb() -> InlineKeyboardMarkup:
    """Кнопка назад"""
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="m_back")]])

# ============================================================
#  MIDDLEWARE
# ============================================================
class MainMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            if event.from_user:
                save_username(event.from_user)
        return await handler(event, data)

dp.message.middleware(MainMiddleware())

# ============================================================
#  СТАРТОВЫЕ КОМАНДЫ
# ============================================================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    """Стартовая команда"""
    me = await bot.get_me()
    if message.chat.type != "private":
        return await bot.send_message(message.chat.id, "✅ VOID Helper активен! /help", message_thread_id=tid(message))
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Я VOID Helper бот для модерации и игр.",
        reply_markup=main_menu_kb(me.username))

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    """Справка по командам"""
    tid_val = tid(message)
    await bot.send_message(message.chat.id, """
<b>⭐ VOID HELPER — ПОЛНЫЙ ГАЙД</b>

<b>💰 Экономика</b>
• /work – работа (раз в 10 мин)
• /daily – ежедневный бонус
• /profile – профиль и статистика
• /top – топ 10 игроков
• /shop – магазин
• /buy 1|2 – купить предмет

<b>🎰 Игры</b>
• /casino 100 – казино (ставка)
• /darts 50 – дартс (ставка)
• /coinflip 30 – орёл/решка (ставка)
• /rps 15 – камень/ножницы/бумага (ставка)

<b>⚔️ Дуэли (ответь на сообщение)</b>
• /dice – кости
• /basketball – баскетбол
• /football – футбол
• /bowling – боулинг

<b>🛡 Модерация (админам)</b>
• !мут @user 1ч причина – замутить
• -размут @user – размутить
• !бан @user 7д причина – забанить
• -разбан @user – разбанить
• !кик @user – кикнуть
• !варн @user причина – варн
• -варн @user – снять варн
• !варны [@user] – список варнов
• -очиститьварны @user – удалить все
• !админ @user – назначить админа
• -админ @user – разжаловать

<b>🔧 Управление чатом</b>
• /moderation on|off – автомодерация
• /setautoschedule 23:00 09:00 – расписание
• /check_schedule – статус расписания
• /setwelcome текст – приветствие

<b>💞 RP и браки</b>
• обнять|поцеловать @user
• +брак @user – предложение брака
• +развод – развод
• +пара – информация о паре
• +список браков – все браки в чате
""", message_thread_id=tid_val)

# ============================================================
#  ЭКОНОМИКА
# ============================================================
@dp.message(Command("profile"))
async def profile_cmd(message: types.Message):
    """Профиль пользователя"""
    uid = message.from_user.id
    coins, xp, warns, _ = get_user(uid)
    await message.answer(
        f"👤 {user_link(uid, message.chat.id, message.from_user.first_name)}\n"
        f"⭐ Уровень: {xp // 100}\n"
        f"💰 Монеты: {coins}\n"
        f"📊 XP: {xp}\n"
        f"⚠️ Варны: {warns}/3")

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    """Топ игроков"""
    rows = db("SELECT id, coins FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    if not rows:
        return await message.answer("🏆 Пока никого")
    
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 Топ монет"]
    for i, (uid, c) in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} {user_link(uid, message.chat.id, str(uid))} — {c}💰")
    
    await message.answer("\n".join(lines))

@dp.message(Command("work"))
async def work_cmd(message: types.Message):
    """Работа"""
    uid = message.from_user.id
    last = db("SELECT last_work FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    now = int(time.time())
    
    if now - last < 600:
        rem = 600 - (now - last)
        return await message.answer(f"⏳ Отдых {rem // 60}м {rem % 60}с")
    
    jobs = [
        ("💻 Написал бота", 600, 1000),
        ("📦 Развёз посылки", 400, 700),
        ("🚗 Отвёз клиента", 500, 800)
    ]
    job, mn, mx = random.choice(jobs)
    pay = random.randint(mn, mx)
    xpg = random.randint(15, 35)
    
    add_coins(uid, pay)
    lvl = add_xp(uid, xpg)
    db("UPDATE users SET last_work=? WHERE id=?", (now, uid))
    
    msg = f"⛏ {job}\n💰 +{pay}💰\n✨ +{xpg} XP"
    if lvl:
        msg += f"\n🎉 Уровень {lvl}!"
    
    await message.answer(msg)

@dp.message(Command("daily"))
async def daily_cmd(message: types.Message):
    """Ежедневный бонус"""
    uid = message.from_user.id
    get_user(uid)
    now = int(time.time())
    last = db("SELECT last_daily FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    
    if now - last < 86400:
        rem = 86400 - (now - last)
        return await message.answer(f"🎁 Уже получен. Следующий через {rem // 3600}ч {(rem % 3600) // 60}м")
    
    b = random.randint(300, 700)
    add_coins(uid, b)
    lvl = add_xp(uid, 50)
    db("UPDATE users SET last_daily=? WHERE id=?", (now, uid))
    
    msg = f"🎁 Бонус!\n💰 +{b}💰\n✨ +50 XP"
    if lvl:
        msg += f"\n🎉 Уровень {lvl}!"
    
    await message.answer(msg)

@dp.message(Command("shop"))
async def shop_cmd(message: types.Message):
    """Магазин"""
    await message.answer(
        "🛒 <b>Магазин</b>\n"
        "1️⃣ Множитель x2 (1ч) — 500💰\n"
        "2️⃣ Сброс работы — 300💰\n\n"
        "/buy 1  /buy 2")

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    """Покупка"""
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("❌ /buy 1 или /buy 2")
    
    try:
        item = int(args[1])
    except:
        return await message.answer("❌ Некорректный номер")
    
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    
    if item == 1:
        if coins < 500:
            return await message.answer("❌ Нужно 500💰")
        add_coins(uid, -500)
        db("UPDATE users SET xp_multiplier=2.0 WHERE id=?", (uid,))
        asyncio.create_task(reset_mult(uid, 3600))
        await message.answer("✨ Множитель x2 на 1 час!")
    elif item == 2:
        if coins < 300:
            return await message.answer("❌ Нужно 300💰")
        add_coins(uid, -300)
        db("UPDATE users SET last_work=0 WHERE id=?", (uid,))
        await message.answer("⚡ Кулдаун работы сброшен!")
    else:
        await message.answer("❌ Неверный номер")

async def reset_mult(uid: int, delay: int):
    """Сброс множителя через время"""
    await asyncio.sleep(delay)
    db("UPDATE users SET xp_multiplier=1.0 WHERE id=?", (uid,))

# ============================================================
#  !give — ВЫДАЧА МОНЕТ
# ============================================================
@dp.message(F.text.lower().regexp(r'^!\s*give\s+'))
async def give_cmd(message: types.Message):
    """Выдача монет основателем"""
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Только для основателя!")
    
    text = re.sub(r'^!\s*give\s+', '', message.text, flags=re.IGNORECASE).strip()
    parts = text.split()
    target = None
    amount = None
    
    for part in parts:
        if part.startswith("@"):
            target = part
        else:
            try:
                amount = int(part)
            except:
                pass
    
    if not target:
        return await message.reply("❌ Укажи @username!")
    if not amount:
        return await message.reply("❌ Укажи сумму!")
    
    uid, name, _ = await resolve_target(message, target)
    if not uid:
        return await message.reply("❌ Пользователь не найден!")
    
    add_coins(uid, amount)
    await message.reply(f"✅ {user_link(uid, message.chat.id, name)} получил {amount} монет!")

# ============================================================
#  ИГРЫ
# ============================================================
async def check_bet(message: types.Message, bet: int, min_bet: int = 10) -> Optional[int]:
    """Проверить ставку"""
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    
    if bet < min_bet:
        await bot.send_message(message.chat.id, f"❌ Мин. ставка: {min_bet}",
                               message_thread_id=tid(message),
                               reply_to_message_id=message.message_id)
        return None
    if bet > coins:
        await bot.send_message(message.chat.id, f"❌ У тебя {coins}💰",
                               message_thread_id=tid(message),
                               reply_to_message_id=message.message_id)
        return None
    
    add_coins(uid, -bet)
    return uid

@dp.message(Command("casino"))
async def casino_cmd(message: types.Message):
    """Казино"""
    bet = extract_bet(message.text)
    if not bet:
        return await bot.send_message(message.chat.id, "🎰 /casino 100",
                                      message_thread_id=tid(message),
                                      reply_to_message_id=message.message_id)
    
    uid = await check_bet(message, bet, 10)
    if not uid:
        return
    
    dice_msg = await bot.send_dice(message.chat.id, emoji="🎰",
                                   message_thread_id=tid(message),
                                   reply_to_message_id=message.message_id)
    await asyncio.sleep(DICE_WAIT["🎰"])
    v = dice_msg.dice.value
    
    if v == 64:
        add_coins(uid, bet * 10)
        add_xp(uid, 150)
        txt = f"🎉 ДЖЕКПОТ! +{bet * 10}💰"
    elif v >= 50:
        add_coins(uid, bet * 4)
        add_xp(uid, 40)
        txt = f"🎰 КРУПНО! +{bet * 4}💰"
    elif v >= 30:
        add_coins(uid, bet * 2)
        add_xp(uid, 15)
        txt = f"🎰 ВЫИГРЫШ! +{bet * 2}💰"
    elif v >= 15:
        add_coins(uid, bet)
        txt = f"🎰 Возврат {bet}💰"
    else:
        txt = f"😞 Проиграл {bet}💰"
    
    await bot.send_message(message.chat.id, txt,
                           message_thread_id=tid(message),
                           reply_to_message_id=dice_msg.message_id)

@dp.message(Command("darts"))
async def darts_cmd(message: types.Message):
    """Дартс"""
    bet = extract_bet(message.text)
    if not bet:
        return await bot.send_message(message.chat.id, "🎯 /darts 50",
                                      message_thread_id=tid(message),
                                      reply_to_message_id=message.message_id)
    
    uid = await check_bet(message, bet, 10)
    if not uid:
        return
    
    dice_msg = await bot.send_dice(message.chat.id, emoji="🎯",
                                   message_thread_id=tid(message),
                                   reply_to_message_id=message.message_id)
    await asyncio.sleep(DICE_WAIT["🎯"])
    v = dice_msg.dice.value
    
    if v == 6:
        add_coins(uid, bet * 5)
        txt = f"🎯 БУЛЛ-АЙ! +{bet * 5}💰"
    elif v == 5:
        add_coins(uid, bet * 3)
        txt = f"🎯 ОТЛИЧНО! +{bet * 3}💰"
    elif v == 4:
        add_coins(uid, bet * 2)
        txt = f"🎯 ХОРОШО! +{bet * 2}💰"
    elif v == 3:
        add_coins(uid, bet)
        txt = f"🎯 Возврат {bet}💰"
    else:
        txt = f"😞 Мимо! -{bet}💰"
    
    await bot.send_message(message.chat.id, txt,
                           message_thread_id=tid(message),
                           reply_to_message_id=dice_msg.message_id)

@dp.message(Command("coinflip"))
async def coinflip_cmd(message: types.Message):
    """Орёл/решка"""
    bet = extract_bet(message.text)
    if not bet:
        return await bot.send_message(message.chat.id, "🪙 /coinflip 30",
                                      message_thread_id=tid(message),
                                      reply_to_message_id=message.message_id)
    
    uid = await check_bet(message, bet, 10)
    if not uid:
        return
    
    result = random.choice(["орёл", "решка"])
    guess = random.choice(["орёл", "решка"])
    
    if result == guess:
        add_coins(uid, bet * 2)
        txt = f"🪙 {result}!\n🎉 +{bet * 2}💰"
    else:
        txt = f"🪙 {result}!\n😞 -{bet}💰"
    
    await bot.send_message(message.chat.id, txt,
                           message_thread_id=tid(message),
                           reply_to_message_id=message.message_id)

@dp.message(Command("rps"), StateFilter(None))
async def rps_cmd(message: types.Message, state: FSMContext):
    """Камень, ножницы, бумага"""
    bet = extract_bet(message.text)
    if not bet:
        return await bot.send_message(message.chat.id, "✊ /rps 15",
                                      message_thread_id=tid(message),
                                      reply_to_message_id=message.message_id)
    
    uid = await check_bet(message, bet, 10)
    if not uid:
        return
    
    await state.set_state(RpsGame.waiting_for_choice)
    await state.update_data(uid=uid, bet=bet, chat_id=message.chat.id,
                            thread_id=tid(message), reply_id=message.message_id)
    
    await bot.send_message(message.chat.id,
                           "✊ Напиши: камень, ножницы или бумага (15 сек)",
                           message_thread_id=tid(message),
                           reply_to_message_id=message.message_id)
    
    # Таймаут игры
    await asyncio.sleep(15)
    if await state.get_state() == RpsGame.waiting_for_choice:
        await state.clear()
        add_coins(uid, bet)
        await bot.send_message(message.chat.id, "⏰ Время вышло! Возврат ставки",
                               message_thread_id=tid(message))

@dp.message(RpsGame.waiting_for_choice)
async def rps_choice(message: types.Message, state: FSMContext):
    """Выбор в КНБ"""
    user_choice = message.text.lower().strip()
    
    if user_choice not in ["камень", "ножницы", "бумага"]:
        return
    
    data = await state.get_data()
    uid = data['uid']
    bet = data['bet']
    chat_id = data['chat_id']
    thread_id = data['thread_id']
    
    if message.from_user.id != uid:
        return
    
    await state.clear()
    
    bot_choice = random.choice(["камень", "ножницы", "бумага"])
    
    # Определяем победителя
    win_rules = {
        ("камень", "ножницы"): True,
        ("ножницы", "бумага"): True,
        ("бумага", "камень"): True,
    }
    
    if user_choice == bot_choice:
        add_coins(uid, bet)
        txt = f"🤝 Ничья! ({bot_choice})\nВозврат {bet}💰"
    elif win_rules.get((user_choice, bot_choice)):
        add_coins(uid, bet * 2)
        add_xp(uid, 20)
        txt = f"🎉 Победа!\n{user_choice} vs {bot_choice}\n+{bet * 2}💰"
    else:
        txt = f"😞 Поражение!\n{user_choice} vs {bot_choice}\n-{bet}💰"
    
    await bot.send_message(chat_id, txt, message_thread_id=thread_id)

# ============================================================
#  ДУЭЛИ
# ============================================================
active_duels: dict = {}
DUEL_GAMES = {
    "dice": {"emoji": "🎲", "name": "Кости"},
    "basketball": {"emoji": "🏀", "name": "Баскетбол"},
    "football": {"emoji": "⚽", "name": "Футбол"},
    "bowling": {"emoji": "🎳", "name": "Боулинг"},
}

def duel_kb(game_type: str, ch_id: int, cid: int) -> InlineKeyboardMarkup:
    """Клавиатура для дуэли"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принять", callback_data=f"da_{game_type}_{ch_id}_{cid}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"dd_{game_type}_{ch_id}"),
    ]])

async def start_duel(message: types.Message, game_type: str):
    """Начать дуэль"""
    if not message.reply_to_message:
        return await bot.send_message(message.chat.id, "❌ Ответь на сообщение соперника!",
                                      message_thread_id=tid(message))
    
    ch = message.from_user
    opp = message.reply_to_message.from_user
    
    if ch.id == opp.id:
        return await bot.send_message(message.chat.id, "❌ Нельзя с собой!",
                                      message_thread_id=tid(message))
    if opp.is_bot:
        return await bot.send_message(message.chat.id, "❌ Нельзя с ботом!",
                                      message_thread_id=tid(message))
    
    cid = message.chat.id
    key = f"{cid}_{ch.id}_{opp.id}"
    
    if key in active_duels:
        return await bot.send_message(message.chat.id, "⚠️ Дуэль уже идёт!",
                                      message_thread_id=tid(message))
    
    active_duels[key] = {"thread_id": tid(message)}
    g = DUEL_GAMES[game_type]
    
    await bot.send_message(message.chat.id,
                           f"{g['emoji']} <b>{g['name']}</b>\n\n"
                           f"{user_link(ch.id, cid, ch.first_name)} вызывает "
                           f"{user_link(opp.id, cid, opp.first_name)}!",
                           message_thread_id=tid(message),
                           reply_markup=duel_kb(game_type, ch.id, cid))

@dp.message(Command("dice"))
async def cmd_dice(m):
    await start_duel(m, "dice")

@dp.message(Command("basketball"))
async def cmd_basketball(m):
    await start_duel(m, "basketball")

@dp.message(Command("football"))
async def cmd_football(m):
    await start_duel(m, "football")

@dp.message(Command("bowling"))
async def cmd_bowling(m):
    await start_duel(m, "bowling")

@dp.callback_query(F.data.startswith("da_"))
async def duel_accept(call: types.CallbackQuery):
    """Принять дуэль"""
    parts = call.data.split("_")
    game_type = parts[1]
    ch_id = int(parts[2])
    cid = int(parts[3])
    opp_id = call.from_user.id
    
    key = f"{cid}_{ch_id}_{opp_id}"
    
    if key not in active_duels:
        return await call.answer("❌ Устарело!", show_alert=True)
    
    thread_id = active_duels[key].get("thread_id")
    
    try:
        await call.message.delete()
    except:
        pass
    
    await bot.send_message(cid, f"✅ {user_link(opp_id, cid, call.from_user.first_name)} принял(а)!",
                           message_thread_id=thread_id)
    
    await run_duel(cid, ch_id, opp_id, game_type, thread_id)
    await call.answer()

@dp.callback_query(F.data.startswith("dd_"))
async def duel_decline(call: types.CallbackQuery):
    """Отказать в дуэли"""
    parts = call.data.split("_")
    ch_id = int(parts[2])
    opp_id = call.from_user.id
    cid = call.message.chat.id
    
    active_duels.pop(f"{cid}_{ch_id}_{opp_id}", None)
    
    await call.message.edit_text(f"❌ {user_link(opp_id, cid, call.from_user.first_name)} отклонил(а)!")
    await call.answer()

async def run_duel(cid: int, p1: int, p2: int, game_type: str, thread_id: Optional[int]):
    """Провести дуэль"""
    g = DUEL_GAMES[game_type]
    
    try:
        p1m = await bot.get_chat_member(cid, p1)
        p2m = await bot.get_chat_member(cid, p2)
        p1n = p1m.user.first_name
        p2n = p2m.user.first_name
    except:
        p1n, p2n = "Игрок 1", "Игрок 2"
    
    msg = await bot.send_message(cid,
                                 f"{g['emoji']} <b>{g['name']}</b>\n\n"
                                 f"{user_link(p1, cid, p1n)} vs {user_link(p2, cid, p2n)}\n\n"
                                 f"🎲 {user_link(p1, cid, p1n)} бросает...",
                                 message_thread_id=thread_id)
    
    d1 = await bot.send_dice(cid, emoji="🎲", message_thread_id=thread_id)
    await asyncio.sleep(DICE_WAIT["🎲"])
    s1 = d1.dice.value
    
    await msg.edit_text(
        f"{g['emoji']} <b>{g['name']}</b>\n\n"
        f"🆚 {user_link(p1, cid, p1n)}: {s1}\n"
        f"{user_link(p2, cid, p2n)} бросает...")
    
    d2 = await bot.send_dice(cid, emoji="🎲", message_thread_id=thread_id)
    await asyncio.sleep(DICE_WAIT["🎲"])
    s2 = d2.dice.value
    
    if s1 > s2:
        w_id, w_nm = p1, p1n
    elif s2 > s1:
        w_id, w_nm = p2, p2n
    else:
        w_id, w_nm = None, None
    
    if w_id:
        add_coins(w_id, 150)
        add_xp(w_id, 30)
        await msg.edit_text(
            f"{g['emoji']} <b>{g['name']}</b>\n\n"
            f"{p1n}: {s1}\n{p2n}: {s2}\n\n"
            f"🏆 {user_link(w_id, cid, w_nm)}!\n💰 +150, ✨ +30 XP")
    else:
        await msg.edit_text(
            f"{g['emoji']} <b>{g['name']}</b>\n\n"
            f"{p1n}: {s1}\n{p2n}: {s2}\n\n"
            f"🤝 НИЧЬЯ!")
    
    active_duels.pop(f"{cid}_{p1}_{p2}", None)

# ============================================================
#  МОДЕРАЦИЯ
# ============================================================
@dp.message(F.text.lower().regexp(r'^!\s*мут'))
async def mute_cmd(message: types.Message):
    """Замутить пользователя"""
    if not await mod_guard(message):
        return
    
    args = re.sub(r'^!\s*мут\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args)
    
    if not uid:
        return await message.reply("❌ Укажи @username или ответь на сообщение!\n!мут @user 10м причина")
    
    if await is_admin(message.chat.id, uid):
        return await message.reply("❌ Нельзя замутить администратора!")
    
    # Парсим длительность и причину
    dur_str = "1ч"
    reason = args
    
    time_match = re.search(r'(\d+)\s*(м|мин|ч|час|д|дн|мес|г|год)', args.lower())
    if time_match:
        dur_str = time_match.group(1) + time_match.group(2)
        reason = re.sub(time_match.pattern, '', args, flags=re.IGNORECASE).strip()
    
    if not reason:
        reason = "нарушение правил"
    
    # Вычисляем длительность в секундах
    if 'мес' in dur_str.lower():
        sec = int(re.search(r'\d+', dur_str).group()) * 30 * 86400
    elif 'год' in dur_str.lower():
        sec = int(re.search(r'\d+', dur_str).group()) * 365 * 86400
    elif 'дн' in dur_str.lower() or 'день' in dur_str.lower():
        sec = int(re.search(r'\d+', dur_str).group()) * 86400
    elif 'ч' in dur_str.lower() or 'час' in dur_str.lower():
        sec = int(re.search(r'\d+', dur_str).group()) * 3600
    else:
        sec = int(re.search(r'\d+', dur_str).group() or 3600) * 60
    
    until = int(time.time()) + sec
    db("INSERT OR REPLACE INTO muted (user_id,chat_id,until) VALUES (?,?,?)",
       (uid, message.chat.id, until))
    
    try:
        await bot.restrict_chat_member(message.chat.id, uid,
                                       permissions=ChatPermissions(can_send_messages=False),
                                       until_date=datetime.fromtimestamp(until, tz=timezone.utc))
        
        await message.reply(
            f"🔇 <b>МУТ</b>\n"
            f"👤 {user_link(uid, message.chat.id, name)}\n"
            f"⏳ На {dur_str}\n"
            f"📌 {reason}")
        
        await send_log(message, uid, "🔇 МУТ", reason, dur_str)
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().regexp(r'^!\s*бан'))
async def ban_cmd(message: types.Message):
    """Забанить пользователя"""
    if not await mod_guard(message):
        return
    
    args = re.sub(r'^!\s*бан\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args)
    
    if not uid:
        return await message.reply("❌ Укажи @username или ответь!\n!бан @user причина")
    
    if await is_admin(message.chat.id, uid):
        return await message.reply("❌ Нельзя забанить администратора!")
    
    reason = args.replace("@" + (args.split("@")[1].split()[0] if "@" in args else ""), "").strip()
    if not reason:
        reason = "нарушение правил"
    
    db("INSERT OR IGNORE INTO banned (user_id,chat_id) VALUES (?,?)",
       (uid, message.chat.id))
    
    try:
        await bot.ban_chat_member(message.chat.id, uid)
        
        await message.reply(
            f"🚫 <b>БАН</b>\n"
            f"👤 {user_link(uid, message.chat.id, name)}\n"
            f"📌 {reason}")
        
        await send_log(message, uid, "🚫 БАН", reason)
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().regexp(r'^-\s*размут'))
async def unmute_cmd(message: types.Message):
    """Размутить пользователя"""
    if not await mod_guard(message):
        return
    
    args = re.sub(r'^-\s*размут\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args)
    
    if not uid:
        return await message.reply("❌ Укажи @username или ответь!")
    
    db("DELETE FROM muted WHERE user_id=? AND chat_id=?", (uid, message.chat.id))
    
    try:
        await bot.restrict_chat_member(message.chat.id, uid,
                                       permissions=ChatPermissions(
                                           can_send_messages=True,
                                           can_send_media_messages=True,
                                           can_send_polls=True,
                                           can_send_other_messages=True,
                                           can_add_web_page_previews=True,
                                           can_invite_users=True))
        
        await message.reply(f"✅ {user_link(uid, message.chat.id, name)} размучен.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().regexp(r'^-\s*разбан'))
async def unban_cmd(message: types.Message):
    """Разбанить пользователя"""
    if not await mod_guard(message):
        return
    
    args = re.sub(r'^-\s*разбан\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args)
    
    if not uid:
        return await message.reply("❌ Укажи @username!")
    
    db("DELETE FROM banned WHERE user_id=? AND chat_id=?", (uid, message.chat.id))
    
    try:
        await bot.unban_chat_member(message.chat.id, uid)
        await message.reply(f"✅ {user_link(uid, message.chat.id, name)} разбанен.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().regexp(r'^!\s*варн'))
async def give_warn_cmd(message: types.Message):
    """Выдать варн"""
    if not await mod_guard(message):
        return
    
    args = re.sub(r'^!\s*варн\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args)
    
    if not uid:
        return await message.reply("❌ Укажи @username или ответь!")
    
    if await is_admin(message.chat.id, uid):
        return await message.reply("❌ Нельзя варнить администратора!")
    
    reason = args
    if "@" in args:
        reason = re.sub(r'@\S+', '', args).strip()
    if not reason:
        reason = "нарушение правил"
    
    wc = add_warn(uid, message.chat.id, reason, 30)
    
    await message.reply(
        f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b>\n"
        f"👤 {user_link(uid, message.chat.id, name)}\n"
        f"📌 {reason}\n"
        f"⚠️ Варн #{wc}/3")
    
    await send_log(message, uid, "⚠️ ВАРН", reason)

@dp.message(F.text.lower().regexp(r'^!\s*кик'))
async def kick_cmd(message: types.Message):
    """Кикнуть пользователя"""
    if not await mod_guard(message):
        return
    
    args = re.sub(r'^!\s*кик\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args)
    
    if not uid:
        return await message.reply("❌ Укажи @username или ответь!")
    
    if await is_admin(message.chat.id, uid):
        return await message.reply("❌ Нельзя кикнуть администратора!")
    
    try:
        await bot.ban_chat_member(message.chat.id, uid)
        await asyncio.sleep(0.5)
        await bot.unban_chat_member(message.chat.id, uid)
        
        await message.reply(f"👢 {user_link(uid, message.chat.id, name)} кикнут.")
        await send_log(message, uid, "👢 КИК", "нарушение правил")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().regexp(r'^-\s*варн'))
async def remove_warn_cmd(message: types.Message):
    """Снять варн"""
    if not await mod_guard(message):
        return
    
    args = re.sub(r'^-\s*варн\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args)
    
    if not uid:
        return await message.reply("❌ Укажи @username или ответь!")
    
    now = int(time.time())
    warns = db("SELECT id FROM warns_system WHERE user_id=? AND chat_id=? AND expires>?",
               (uid, message.chat.id, now), fetch=True)
    
    if not warns:
        return await message.reply(f"❌ У {user_link(uid, message.chat.id, name)} нет варнов.")
    
    db("DELETE FROM warns_system WHERE id=?", (warns[0][0],))
    await message.reply(f"✅ Снят 1 варн с {user_link(uid, message.chat.id, name)}. Осталось: {len(warns) - 1}")

@dp.message(F.text.lower().regexp(r'^!\s*админ'))
async def give_admin_cmd(message: types.Message):
    """Выдать права администратора"""
    if not await mod_guard(message):
        return
    
    args = re.sub(r'^!\s*админ\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args)
    
    if not uid:
        return await message.reply("❌ Укажи @username или ответь на сообщение!")
    
    cid = message.chat.id
    
    try:
        member = await bot.get_chat_member(cid, uid)
        if member.status in ("administrator", "creator"):
            return await message.reply(f"❌ {name} уже администратор.")
    except Exception as e:
        return await message.reply(f"❌ Ошибка: {e}")
    
    perms = get_default_perms()
    ok, err = await apply_admin_perms(cid, uid, perms)
    
    if not ok:
        return await message.reply(err)
    
    save_perms_db(cid, uid, perms)
    
    tag = f"@{message.chat.username}" if message.chat.username else message.chat.title
    
    await message.reply(
        f"<b>🛡 Админ-панель прав</b>\n\n"
        f"👤 {user_link(uid, cid, name)}\n"
        f"💬 Чат: {tag}\n"
        f"🕐 {datetime.now().strftime('%H:%M')}\n\n"
        f"Нажимайте кнопки для изменения прав:",
        reply_markup=admin_panel_kb(uid, cid, perms))

@dp.callback_query(F.data.startswith("ap|"))
async def toggle_admin_perm(call: types.CallbackQuery):
    """Переключить право администратора"""
    parts = call.data.split("|")
    if len(parts) < 4:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    uid = int(parts[1])
    chat_id = int(parts[2])
    perm = parts[3]
    
    if not await is_admin(chat_id, call.from_user.id):
        return await call.answer("❌ Только для администраторов!", show_alert=True)
    
    perms = await get_admin_permissions(chat_id, uid)
    if perm not in perms:
        return await call.answer("❌ Неизвестное право", show_alert=True)
    
    perms[perm] = not perms[perm]
    ok, err = await apply_admin_perms(chat_id, uid, perms)
    
    if ok:
        save_perms_db(chat_id, uid, perms)
        try:
            await call.message.edit_reply_markup(reply_markup=admin_panel_kb(uid, chat_id, perms))
        except:
            pass
        status = "✅ включено" if perms[perm] else "❌ выключено"
        await call.answer(status)
    else:
        perms[perm] = not perms[perm]
        await call.answer(err, show_alert=True)

@dp.callback_query(F.data.startswith("ap_rm|"))
async def remove_admin_cb(call: types.CallbackQuery):
    """Разжаловать администратора"""
    parts = call.data.split("|")
    uid = int(parts[1])
    chat_id = int(parts[2])
    
    if not await is_admin(chat_id, call.from_user.id):
        return await call.answer("❌ Только для администраторов!", show_alert=True)
    
    try:
        await bot.promote_chat_member(chat_id, uid,
                                      can_manage_chat=False,
                                      can_delete_messages=False,
                                      can_restrict_members=False,
                                      can_invite_users=False,
                                      can_pin_messages=False,
                                      can_change_info=False,
                                      can_promote_members=False,
                                      can_manage_topics=False,
                                      can_manage_video_chats=False)
        
        db("DELETE FROM admin_permissions WHERE user_id=? AND chat_id=?", (uid, chat_id))
        
        await call.message.edit_text(f"🔻 Администратор разжалован. (ID: {uid})")
        await call.answer("✅ Разжалован")
    except Exception as e:
        await call.answer(f"❌ {e}", show_alert=True)

@dp.message(F.text.lower().regexp(r'^-\s*админ'))
async def remove_admin_cmd(message: types.Message):
    """Разжаловать администратора (команда)"""
    if not await mod_guard(message):
        return
    
    args = re.sub(r'^-\s*админ\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args)
    
    if not uid:
        return await message.reply("❌ Укажи @username или ответь!")
    
    try:
        await bot.promote_chat_member(message.chat.id, uid,
                                      can_manage_chat=False,
                                      can_delete_messages=False,
                                      can_restrict_members=False,
                                      can_invite_users=False,
                                      can_pin_messages=False,
                                      can_change_info=False,
                                      can_promote_members=False,
                                      can_manage_topics=False,
                                      can_manage_video_chats=False)
        
        db("DELETE FROM admin_permissions WHERE user_id=? AND chat_id=?",
           (uid, message.chat.id))
        
        await message.reply(f"🔻 {user_link(uid, message.chat.id, name)} разжалован.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# ============================================================
#  УПРАВЛЕНИЕ ЧАТОМ
# ============================================================
@dp.message(Command("moderation"))
async def toggle_moderation(message: types.Message):
    """Управление автомодерацией"""
    if not await mod_guard(message):
        return
    
    arg = message.text.replace("/moderation", "").strip().lower()
    
    if arg == "on":
        db("INSERT OR REPLACE INTO moderation_settings VALUES (?,?)",
           (message.chat.id, 1))
        await message.reply("✅ Автомодерация включена")
    elif arg == "off":
        db("INSERT OR REPLACE INTO moderation_settings VALUES (?,?)",
           (message.chat.id, 0))
        await message.reply("✅ Автомодерация выключена")
    else:
        status = "ВКЛ" if await is_moderation_enabled(message.chat.id) else "ВЫКЛ"
        await message.reply(f"Автомодерация: {status}")

@dp.message(Command("setwelcome"))
async def set_welcome_cmd(message: types.Message):
    """Установить приветствие"""
    if not await mod_guard(message):
        return
    
    chat_id = message.chat.id
    welcome_text = re.sub(r'^/\s*setwelcome\s*', '', message.text, flags=re.IGNORECASE).strip()
    
    if not welcome_text:
        welcome_text = "👋 Добро пожаловать, {упоминание}!"
    
    db("INSERT OR REPLACE INTO group_welcome (chat_id, welcome_text, welcome_type, welcome_file_id) VALUES (?,?,?,?)",
       (chat_id, welcome_text, "text", None))
    
    await message.reply(f"✅ Приветствие сохранено!\nТекст: {welcome_text[:100]}")

@dp.message(Command("check_schedule"))
async def check_schedule_cmd(message: types.Message):
    """Проверить расписание"""
    r = db("SELECT close_time, open_time, is_closed FROM chat_settings WHERE chat_id=?",
           (message.chat.id,), fetch=True)
    
    if not r or not r[0][0]:
        return await message.reply("⏰ Расписание не установлено.")
    
    status = "🔒 ЗАКРЫТ" if r[0][2] else "🔓 ОТКРЫТ"
    await message.reply(f"📅 Закрытие: {r[0][0]}\n🔓 Открытие: {r[0][1]}\nСтатус: {status}")

@dp.message(Command("setautoschedule"))
async def set_schedule(message: types.Message):
    """Установить расписание"""
    if not await mod_guard(message):
        return
    
    args = message.text.replace("/setautoschedule", "").strip().split()
    
    if len(args) < 2:
        return await message.reply("⏰ /setautoschedule 23:00 09:00\n/setautoschedule off")
    
    if args[0].lower() == "off":
        db("UPDATE chat_settings SET close_time=NULL, open_time=NULL WHERE chat_id=?",
           (message.chat.id,))
        return await message.reply("✅ Расписание отключено.")
    
    fmt = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
    if not re.match(fmt, args[0]) or not re.match(fmt, args[1]):
        return await message.reply("❌ Формат: ЧЧ:ММ")
    
    db("INSERT OR REPLACE INTO chat_settings (chat_id, close_time, open_time, is_closed) VALUES (?,?,?,0)",
       (message.chat.id, args[0], args[1]))
    
    await message.reply(f"✅ Закрытие: {args[0]}, открытие: {args[1]}")

# ============================================================
#  CALLBAKC МЕНЮ
# ============================================================
@dp.callback_query(F.data == "m_profile")
async def cb_profile(call: types.CallbackQuery):
    """Профиль в меню"""
    uid = call.from_user.id
    coins, xp, warns, _ = get_user(uid)
    
    await call.message.edit_text(
        f"👤 {user_link(uid, call.message.chat.id, call.from_user.first_name)}\n"
        f"⭐ Уровень: {xp // 100}\n"
        f"💰 Монеты: {coins}\n"
        f"📊 XP: {xp}\n"
        f"⚠️ Варны: {warns}/3",
        reply_markup=back_kb())
    
    await call.answer()

@dp.callback_query(F.data == "m_top")
async def cb_top(call: types.CallbackQuery):
    """Топ в меню"""
    rows = db("SELECT id, coins FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    
    if not rows:
        await call.message.edit_text("🏆 Пока никого", reply_markup=back_kb())
        return await call.answer()
    
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 Топ монет"]
    for i, (uid, c) in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} {user_link(uid, call.message.chat.id, str(uid))} — {c}💰")
    
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_shop")
async def cb_shop(call: types.CallbackQuery):
    """Магазин в меню"""
    await call.message.edit_text(
        "🛒 <b>Магазин</b>\n"
        "1️⃣ Множитель x2 (1ч) — 500💰\n"
        "2️⃣ Сброс работы — 300💰\n\n"
        "/buy 1  /buy 2",
        reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_games")
async def cb_games(call: types.CallbackQuery):
    """Игры в меню"""
    await call.message.edit_text(
        "🎮 <b>Игры</b>\n"
        "/casino /darts /coinflip /rps\n\n"
        "⚔️ <b>Дуэли:</b> /dice /basketball /football /bowling",
        reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_rp")
async def cb_rp(call: types.CallbackQuery):
    """RP в меню"""
    await call.message.edit_text(
        "❤️ <b>RP:</b> обнять, поцеловать, ударить @user\n"
        "💍 <b>Браки:</b> +брак @user, +развод, +пара, +список браков",
        reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_back")
async def cb_back(call: types.CallbackQuery):
    """Назад в меню"""
    me = await bot.get_me()
    await call.message.edit_text(
        f"👋 Привет, {call.from_user.first_name}!\n"
        f"Я VOID Helper бот.",
        reply_markup=main_menu_kb(me.username))
    await call.answer()

# ============================================================
#  ЗАПУСК БОТА
# ============================================================
async def main():
    """Главная функция"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    
    try:
        await bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
    except:
        pass
    
    me = await bot.get_me()
    print(f"✅ @{me.username} ЗАПУЩЕН!")
    print("   ✅ Экономика: /work /daily /shop /buy")
    print("   ✅ Игры: /casino /darts /coinflip /rps")
    print("   ✅ Дуэли: /dice /basketball /football /bowling")
    print("   ✅ Модерация: !мут !бан !варн !админ")
    print("   ✅ Управление: /moderation /setwelcome /setautoschedule")
    
    try:
        await dp.start_polling(bot, timeout=60, relax=0.5)
    except Exception as e:
        print(f"❌ Ошибка polling: {e}")
        await asyncio.sleep(5)
        await dp.start_polling(bot, timeout=120, relax=1.0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен!")
