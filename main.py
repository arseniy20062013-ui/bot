# ============================================================
#  VOID HELPER BOT — ПОЛНЫЙ ГОТОВЫЙ КОД
#  Версия: 3.0 ФИНАЛЬНАЯ
#  Дата: 21.04.2026
# ============================================================

import asyncio
import sqlite3
import logging
import time
import random
import re
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatMemberUpdated, ChatPermissions,
    BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats,
)
from aiogram.client.default import DefaultBotProperties

# ============================================================
#  НАСТРОЙКИ БОТА
# ============================================================
TOKEN = '8203364413:AAHBW_Aek57yZvvSf5JzrYElxLOCky_vnEY'
OWNER_ID = 7173827114
DB_NAME = 'void_final.db'
LOG_CHANNEL = '@void_official_chat'
LOG_MESSAGE_ID = 19010

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

DICE_WAIT = {"🎲": 2, "🎯": 3, "🏀": 4, "⚽": 4, "🎳": 4, "🎰": 4}

# ============================================================
#  КОМАНДЫ ДЛЯ МЕНЮ
# ============================================================
PRIVATE_COMMANDS = [
    BotCommand(command="start", description="🏠 Главное меню"),
    BotCommand(command="help", description="📋 Все команды"),
    BotCommand(command="profile", description="👤 Мой профиль"),
    BotCommand(command="top", description="🏆 Топ игроков"),
    BotCommand(command="work", description="⛏ Работа"),
    BotCommand(command="daily", description="🎁 Бонус"),
    BotCommand(command="shop", description="🛒 Магазин"),
    BotCommand(command="casino", description="🎰 Казино"),
    BotCommand(command="darts", description="🎯 Дартс"),
    BotCommand(command="coinflip", description="🪙 Орёл/Решка"),
    BotCommand(command="rps", description="✊ КНБ"),
]

GROUP_COMMANDS = [
    BotCommand(command="help", description="📋 Все команды"),
    BotCommand(command="profile", description="👤 Мой профиль"),
    BotCommand(command="top", description="🏆 Топ"),
    BotCommand(command="work", description="⛏ Работа"),
    BotCommand(command="daily", description="🎁 Бонус"),
    BotCommand(command="shop", description="🛒 Магазин"),
    BotCommand(command="casino", description="🎰 Казино"),
    BotCommand(command="darts", description="🎯 Дартс"),
    BotCommand(command="dice", description="🎲 Кости (дуэль)"),
    BotCommand(command="basketball", description="🏀 Баскетбол"),
    BotCommand(command="football", description="⚽ Футбол"),
    BotCommand(command="bowling", description="🎳 Боулинг"),
    BotCommand(command="coinflip", description="🪙 Орёл/Решка"),
    BotCommand(command="rps", description="✊ КНБ"),
    BotCommand(command="setwelcome", description="✏️ Приветствие"),
    BotCommand(command="setautoschedule", description="⏰ Настройка авто-закрытия"),
    BotCommand(command="check_schedule", description="🔍 Проверить расписание"),
    BotCommand(command="moderation", description="⚙️ Вкл/выкл автомодерацию"),
    BotCommand(command="rp", description="🎭 Список RP действий"),
]

# ============================================================
#  БАЗА ДАННЫХ
# ============================================================
def db(query, params=(), fetch=False):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch:
            return cur.fetchall()
        conn.commit()

db('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 500,
    xp INTEGER DEFAULT 0,
    last_work INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0,
    warns INTEGER DEFAULT 0,
    xp_multiplier REAL DEFAULT 1.0
)''')
db('''CREATE TABLE IF NOT EXISTS muted (
    user_id INTEGER, chat_id INTEGER, until INTEGER,
    PRIMARY KEY(user_id, chat_id)
)''')
db('''CREATE TABLE IF NOT EXISTS banned (
    user_id INTEGER, chat_id INTEGER,
    PRIMARY KEY(user_id, chat_id)
)''')
db('''CREATE TABLE IF NOT EXISTS group_welcome (
    chat_id INTEGER PRIMARY KEY,
    welcome_text TEXT DEFAULT '👋 Добро пожаловать, {упоминание}!'
)''')
db('''CREATE TABLE IF NOT EXISTS usernames (
    username TEXT PRIMARY KEY,
    user_id INTEGER,
    name TEXT
)''')
db('''CREATE TABLE IF NOT EXISTS user_nicknames (
    user_id INTEGER,
    chat_id INTEGER,
    nickname TEXT,
    PRIMARY KEY(user_id, chat_id)
)''')
db('''CREATE TABLE IF NOT EXISTS warns_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, chat_id INTEGER,
    reason TEXT, date INTEGER
)''')
db('''CREATE TABLE IF NOT EXISTS user_gender (
    user_id INTEGER PRIMARY KEY,
    gender INTEGER DEFAULT 0
)''')
db('''CREATE TABLE IF NOT EXISTS marriages (
    user1 INTEGER,
    user2 INTEGER,
    chat_id INTEGER,
    since INTEGER,
    PRIMARY KEY(user1, user2)
)''')
db('''CREATE TABLE IF NOT EXISTS chat_settings (
    chat_id INTEGER PRIMARY KEY,
    is_closed INTEGER DEFAULT 0,
    close_time TEXT,
    open_time TEXT
)''')
db('''CREATE TABLE IF NOT EXISTS moderation_settings (
    chat_id INTEGER PRIMARY KEY,
    enabled INTEGER DEFAULT 1
)''')
db('''CREATE TABLE IF NOT EXISTS chat_permissions_backup (
    chat_id INTEGER PRIMARY KEY,
    can_send_messages BOOLEAN,
    can_send_media_messages BOOLEAN,
    can_send_polls BOOLEAN,
    can_send_other_messages BOOLEAN,
    can_add_web_page_previews BOOLEAN,
    can_change_info BOOLEAN,
    can_invite_users BOOLEAN,
    can_pin_messages BOOLEAN,
    can_manage_topics BOOLEAN
)''')
db('''CREATE TABLE IF NOT EXISTS warns_system (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    chat_id INTEGER,
    reason TEXT,
    date INTEGER,
    expires INTEGER
)''')

# ============================================================
#  ЗАПРЕЩЁННЫЕ СЛОВА
# ============================================================
BAD_WORDS = {
    '18plus': [
        'порно', 'секс', 'голый', 'голая', 'эротика', 'интим', 'пенис', 'влагалище',
        'оральный', 'минет', 'куни', 'трах', 'ебля', 'дрочить', 'мастурбация', 'член',
        'вагина', 'грудь', 'сиськи', 'попка', 'задница', 'жопа', 'хуй', 'пизда',
        'сексуальный', 'сексуальная', 'возбуждает', 'оргазм',
        'расчленёнка', 'насилие', 'убийство', 'труп', 'кровь', 'жестокость',
        'наркотики', 'наркота', 'кокаин', 'героин', 'наркоман',
    ],
    'insult': [
        'тупой', 'дебил', 'идиот', 'кретин', 'лох', 'олень', 'баран', 'дурак',
        'урод', 'чмо', 'шлюха', 'проститутка', 'пидор', 'гандон', 'хуесос',
        'долбоеб', 'уебок', 'ебанутый', 'хуйло', 'сучка', 'блядина', 'мудак', 'сука',
        'даун', 'аутист', 'дегенерат', 'ничтожество', 'отброс', 'мразь',
    ],
    'spam': [
        r'http[s]?://', r'www\.', r'\.ru\b', r'\.com\b', r't\.me/',
        r'telegram\.me', r'vk\.com', r'youtube\.', r'instagram\.',
    ],
}

PUNISHMENT_RULES = {
    '18plus': {'rule': '1.1. 18+ контент', 'warn_days': 30},
    'insult': {'rule': '1.2. Оскорбления', 'warn_days': 30},
    'conflict': {'rule': '1.3. Споры и конфликты', 'warn_days': 30},
    'spam': {'rule': '1.4. Нежелательные сообщения', 'warn_days': 30},
}

CONFLICT_WORDS = ['политика', 'путин', 'война', 'религия', 'гендер', 'лгбт']

# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def detect_gender_by_name(name: str) -> int:
    name_lower = name.lower().strip()
    female_endings = ('а', 'я', 'ия', 'ь')
    unisex_names = ('саша', 'женя', 'валя', 'слава', 'никита', 'вика', 'ната', 'тоня', 'саня')
    if name_lower in unisex_names: return 2
    for ending in female_endings:
        if name_lower.endswith(ending): return 1
    return 0

async def is_moderation_enabled(chat_id):
    row = db("SELECT enabled FROM moderation_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return row[0][0] == 1 if row else True

def get_user(uid):
    r = db("SELECT coins, xp, warns, xp_multiplier FROM users WHERE id=?", (uid,), fetch=True)
    if not r:
        db("INSERT INTO users (id) VALUES (?)", (uid,))
        return (500, 0, 0, 1.0)
    return r[0]

def add_coins(uid, amount):
    get_user(uid)
    db("UPDATE users SET coins=coins+? WHERE id=?", (amount, uid))

def add_xp(uid, amount):
    get_user(uid)
    old_xp = db("SELECT xp FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    db("UPDATE users SET xp=xp+? WHERE id=?", (amount, uid))
    old_lvl = old_xp // 100
    new_lvl = (old_xp + amount) // 100
    if new_lvl > old_lvl: return new_lvl
    return None

def get_nickname(user_id, chat_id):
    row = db("SELECT nickname FROM user_nicknames WHERE user_id=? AND chat_id=?", (user_id, chat_id), fetch=True)
    return row[0][0] if row else None

def get_display_name(user_id, chat_id, default_name):
    nick = get_nickname(user_id, chat_id)
    return nick if nick else default_name

def user_link_with_nick(user_id, chat_id, default_name):
    display_name = get_display_name(user_id, chat_id, default_name)
    return f'<a href="tg://user?id={user_id}">{display_name}</a>'

def save_username(user: types.User):
    if user and user.username:
        db("INSERT OR REPLACE INTO usernames (username,user_id,name) VALUES (?,?,?)",
           (user.username.lower(), user.id, user.first_name))

async def resolve_target(message: types.Message, args: str = ""):
    if message.reply_to_message and message.reply_to_message.from_user:
        return (message.reply_to_message.from_user.id,
                message.reply_to_message.from_user.first_name,
                message.reply_to_message)
    for word in args.split():
        if word.startswith("@"):
            username = word[1:]
            r = db("SELECT user_id, name FROM usernames WHERE username=?", (username.lower(),), fetch=True)
            if r: return r[0][0], r[0][1], None
            try:
                chat = await bot.get_chat(f"@{username}")
                if chat.username:
                    db("INSERT OR REPLACE INTO usernames (username,user_id,name) VALUES (?,?,?)",
                       (chat.username.lower(), chat.id, chat.first_name or username))
                return chat.id, chat.first_name or username, None
            except: continue
    return None, None, None

async def is_admin(chat_id, user_id) -> bool:
    if user_id == OWNER_ID: return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except: return False

def parse_duration(s: str) -> int:
    s = s.lower().strip()
    if 'мес' in s:
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 30 * 86400
    if 'г' in s or 'год' in s:
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 365 * 86400
    if s.endswith('д') or 'дн' in s:
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 86400
    if s.endswith('ч') or 'час' in s:
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 3600
    if s.endswith('м') or 'мин' in s:
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 60
    num = re.findall(r'\d+', s)
    if num: return int(num[0]) * 60
    return 300

def fmt_dur(sec: int) -> str:
    if sec >= 31536000: return f"{sec // 31536000} г."
    if sec >= 2592000: return f"{sec // 2592000} мес."
    if sec >= 86400: return f"{sec // 86400} дн."
    if sec >= 3600: return f"{sec // 3600} ч."
    return f"{sec // 60} мин."

def extract_bet(text: str):
    numbers = re.findall(r'\d+', text)
    return int(numbers[0]) if numbers else None

async def get_chat_schedule(chat_id):
    row = db("SELECT close_time, open_time FROM chat_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return (row[0][0], row[0][1]) if row else (None, None)

async def set_chat_schedule(chat_id, close_time, open_time):
    db("INSERT OR REPLACE INTO chat_settings (chat_id, close_time, open_time, is_closed) VALUES (?,?,?,0)",
       (chat_id, close_time, open_time))

async def is_chat_closed(chat_id):
    row = db("SELECT is_closed FROM chat_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return row and row[0][0] == 1

# ============================================================
#  СИСТЕМА ВАРНОВ
# ============================================================
def get_user_warns(uid, chat_id):
    now = int(time.time())
    return db("SELECT id, reason, date, expires FROM warns_system WHERE user_id=? AND chat_id=? AND expires > ? ORDER BY date DESC",
              (uid, chat_id, now), fetch=True)

def get_warn_count(uid, chat_id):
    warns = get_user_warns(uid, chat_id)
    return len(warns) if warns else 0

def add_warn(uid, chat_id, reason, days=30):
    now = int(time.time())
    expires = now + (days * 86400)
    db("INSERT INTO warns_system (user_id, chat_id, reason, date, expires) VALUES (?,?,?,?,?)",
       (uid, chat_id, reason, now, expires))
    return get_warn_count(uid, chat_id)

def clear_warns(uid, chat_id):
    db("DELETE FROM warns_system WHERE user_id=? AND chat_id=?", (uid, chat_id))

def get_warn_punishment(warn_count):
    if warn_count >= 6: return 'ban', None, '🔴 БАН навсегда'
    elif warn_count == 5: return 'mute', 30 * 86400, '🔇 МУТ на 30 дней'
    elif warn_count == 4: return 'mute', 14 * 86400, '🔇 МУТ на 14 дней'
    elif warn_count == 3: return 'mute', 7 * 86400, '🔇 МУТ на 7 дней'
    else: return 'warn', None, f'⚠️ ВАРН #{warn_count}/3'

# ============================================================
#  ЛОГИРОВАНИЕ
# ============================================================
async def send_punishment_log(message: types.Message, target_id: int, action: str,
                              reason: str, duration: str = ""):
    try:
        target_user = await bot.get_chat(target_id)
        admin = message.from_user
        chat = message.chat
        log_text = f"{action}\n\n👤 Нарушитель: {target_user.first_name}"
        if target_user.username: log_text += f" (@{target_user.username})"
        log_text += f"\n🆔 ID: {target_user.id}\n\n👮 Админ: {admin.first_name}"
        if admin.username: log_text += f" (@{admin.username})"
        log_text += f"\n\n💬 Чат: {chat.title}"
        if chat.username: log_text += f" (@{chat.username})"
        log_text += f"\n📌 Причина: {reason}"
        if duration: log_text += f"\n⏳ Срок: {duration}"
        await bot.send_message(LOG_CHANNEL, log_text, reply_to_message_id=LOG_MESSAGE_ID)
    except Exception as e:
        logging.error(f"Ошибка отправки лога: {e}")

# ============================================================
#  АВТОМОДЕРАЦИЯ
# ============================================================
async def auto_moderate(message: types.Message):
    if message.chat.type not in ("group", "supergroup"): return
    if message.from_user.is_bot: return
    if await is_admin(message.chat.id, message.from_user.id): return
    if not await is_moderation_enabled(message.chat.id): return
    
    text = (message.text or message.caption or "").lower()
    if not text: return
    
    violation = None
    for word in BAD_WORDS['18plus']:
        if word in text: violation = '18plus'; break
    if not violation:
        for word in BAD_WORDS['insult']:
            if word in text: violation = 'insult'; break
    if not violation:
        for word in CONFLICT_WORDS:
            if word in text: violation = 'conflict'; break
    if not violation:
        for pattern in BAD_WORDS['spam']:
            if re.search(pattern, text): violation = 'spam'; break
    if not violation: return
    
    rule = PUNISHMENT_RULES[violation]
    uid = message.from_user.id
    chat_id = message.chat.id
    
    try: await message.delete()
    except: pass
    
    warn_count = add_warn(uid, chat_id, f"Автомодерация: {rule['rule']}", rule['warn_days'])
    punishment_type, duration, punishment_text = get_warn_punishment(warn_count)
    
    if punishment_type == 'mute':
        until = int(time.time()) + duration
        db("INSERT OR REPLACE INTO muted (user_id, chat_id, until) VALUES (?,?,?)", (uid, chat_id, until))
        try: await bot.restrict_chat_member(chat_id, uid, permissions=ChatPermissions(can_send_messages=False), until_date=datetime.fromtimestamp(until, tz=timezone.utc))
        except: pass
    elif punishment_type == 'ban':
        db("INSERT OR IGNORE INTO banned (user_id, chat_id) VALUES (?,?)", (uid, chat_id))
        try: await bot.ban_chat_member(chat_id, uid)
        except: pass
    
    warn_msg = f"⚠️ {user_link_with_nick(uid, chat_id, message.from_user.first_name)} нарушил(а) правила!\n📌 {rule['rule']}\n{punishment_text}"
    await message.answer(warn_msg)
    await send_punishment_log(message, uid, punishment_text.split()[0], rule['rule'], fmt_dur(duration) if duration else "")

# ============================================================
#  УПРАВЛЕНИЕ ЧАТОМ
# ============================================================
async def save_current_permissions(chat_id):
    try:
        chat = await bot.get_chat(chat_id)
        perms = chat.permissions
        if perms is None:
            perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_polls=True,
                                    can_send_other_messages=True, can_add_web_page_previews=True, can_change_info=True,
                                    can_invite_users=True, can_pin_messages=True, can_manage_topics=True)
        db("""INSERT OR REPLACE INTO chat_permissions_backup VALUES (?,?,?,?,?,?,?,?,?,?)""",
           (chat_id, perms.can_send_messages, perms.can_send_media_messages, perms.can_send_polls,
            perms.can_send_other_messages, perms.can_add_web_page_previews, perms.can_change_info,
            perms.can_invite_users, perms.can_pin_messages, perms.can_manage_topics))
        return True
    except: return False

async def restore_saved_permissions(chat_id):
    row = db("SELECT * FROM chat_permissions_backup WHERE chat_id=?", (chat_id,), fetch=True)
    if row:
        perms = ChatPermissions(can_send_messages=bool(row[0][1]), can_send_media_messages=bool(row[0][2]),
                                can_send_polls=bool(row[0][3]), can_send_other_messages=bool(row[0][4]),
                                can_add_web_page_previews=bool(row[0][5]), can_change_info=bool(row[0][6]),
                                can_invite_users=bool(row[0][7]), can_pin_messages=bool(row[0][8]),
                                can_manage_topics=bool(row[0][9]))
        try: await bot.set_chat_permissions(chat_id, permissions=perms); return True
        except: return False
    else:
        try:
            await bot.set_chat_permissions(chat_id, permissions=ChatPermissions(
                can_send_messages=True, can_send_media_messages=True, can_send_polls=True,
                can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True))
            return True
        except: return False

async def close_chat(chat_id):
    if not await save_current_permissions(chat_id): return False
    db("UPDATE chat_settings SET is_closed=1 WHERE chat_id=?", (chat_id,))
    try:
        await bot.set_chat_permissions(chat_id, permissions=ChatPermissions(
            can_send_messages=False, can_send_media_messages=False, can_send_polls=False,
            can_send_other_messages=False, can_add_web_page_previews=False, can_invite_users=True,
            can_change_info=False, can_pin_messages=False))
        await bot.send_message(chat_id, "🔒 ЧАТ ЗАКРЫТ")
        return True
    except: return False

async def open_chat(chat_id):
    db("UPDATE chat_settings SET is_closed=0 WHERE chat_id=?", (chat_id,))
    if not await restore_saved_permissions(chat_id): return False
    await bot.send_message(chat_id, "🔓 ЧАТ ОТКРЫТ")
    return True

# ============================================================
#  РАСПИСАНИЕ
# ============================================================
sent_notifications = {}

def msktime() -> datetime:
    return datetime.now(timezone(timedelta(hours=3)))

async def apply_schedule_now(chat_id):
    row = db("SELECT close_time, open_time, is_closed FROM chat_settings WHERE chat_id=?", (chat_id,), fetch=True)
    if not row: return
    close_time, open_time, is_closed = row[0]
    if not close_time or not open_time: return
    
    now = msktime()
    now_minutes = now.hour * 60 + now.minute
    try:
        close_h, close_m = map(int, close_time.split(':'))
        open_h, open_m = map(int, open_time.split(':'))
    except: return
    
    close_minutes = close_h * 60 + close_m
    open_minutes = open_h * 60 + open_m
    
    if close_minutes < open_minutes:
        should_be_closed = (close_minutes <= now_minutes < open_minutes)
        seconds_until_close = (close_minutes - now_minutes) * 60 if now_minutes < close_minutes else (close_minutes + 1440 - now_minutes) * 60
    else:
        should_be_closed = (now_minutes >= close_minutes or now_minutes < open_minutes)
        seconds_until_close = (close_minutes + 1440 - now_minutes) * 60 if now_minutes >= close_minutes else 0
    
    if should_be_closed and not is_closed: await close_chat(chat_id)
    elif not should_be_closed and is_closed: await open_chat(chat_id)
    
    if not should_be_closed and not is_closed and seconds_until_close > 0:
        for wt in [3600, 1800, 900, 600, 300, 60, 30, 10]:
            if wt <= seconds_until_close < wt + 10:
                key = f"warn_{chat_id}_{now.strftime('%Y%m%d')}_{wt}"
                if key not in sent_notifications:
                    sent_notifications[key] = True
                    time_str = f"{wt//3600} час" if wt >= 3600 else f"{wt//60} минут" if wt >= 60 else f"{wt} секунд"
                    await bot.send_message(chat_id, f"⚠️ Чат закроется через {time_str}.")
                break

async def scheduler_loop():
    while True:
        try:
            today = msktime().strftime('%Y%m%d')
            for k in [k for k in sent_notifications.keys() if today not in k]: del sent_notifications[k]
            chats = db("SELECT chat_id FROM chat_settings WHERE close_time IS NOT NULL AND open_time IS NOT NULL", fetch=True)
            for chat in chats: await apply_schedule_now(chat[0])
        except: pass
        await asyncio.sleep(10)

# ============================================================
#  MIDDLEWARE
# ============================================================
class MainMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            if event.from_user: save_username(event.from_user)
            if event.chat and event.chat.type in ("group", "supergroup") and event.from_user:
                uid, cid = event.from_user.id, event.chat.id
                if db("SELECT 1 FROM banned WHERE user_id=? AND chat_id=?", (uid, cid), fetch=True):
                    try: await event.delete()
                    except: pass
                    return
                row = db("SELECT until FROM muted WHERE user_id=? AND chat_id=?", (uid, cid), fetch=True)
                if row and row[0][0] > int(time.time()):
                    try: await event.delete()
                    except: pass
                    return
                if await is_chat_closed(cid) and not await is_admin(cid, uid):
                    try: await event.delete()
                    except: pass
                    return
                await apply_schedule_now(cid)
                await auto_moderate(event)
        return await handler(event, data)

dp.message.middleware(MainMiddleware())

# ============================================================
#  ГЛАВНОЕ МЕНЮ
# ============================================================
def main_menu_kb(username):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="m_profile"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="m_top")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="m_shop"),
         InlineKeyboardButton(text="🎮 Игры", callback_data="m_games")],
        [InlineKeyboardButton(text="❤️ RP", callback_data="m_rp"),
         InlineKeyboardButton(text="➕ Добавить в группу", url=f"https://t.me/{username}?startgroup=L")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="m_back")]])

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    me = await bot.get_me()
    if message.chat.type != "private": return await message.reply("✅ VOID Helper активен!\n/help — все команды.")
    await message.answer(f"👋 Привет, {message.from_user.first_name}!\nЯ VOID Helper.\n📋 /help", reply_markup=main_menu_kb(me.username))

@dp.callback_query(F.data == "m_profile")
async def cb_profile(call: types.CallbackQuery):
    uid = call.from_user.id
    coins, xp, warns, _ = get_user(uid)
    await call.message.edit_text(f"👤 Профиль\n\n{user_link_with_nick(uid, call.message.chat.id, call.from_user.first_name)}\n⭐ Уровень: {xp//100}\n💰 Монеты: {coins}\n📊 Опыт: {xp}\n⚠️ Варны: {warns}/3", reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_top")
async def cb_top(call: types.CallbackQuery):
    rows = db("SELECT id, coins FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    if not rows: return await call.message.edit_text("🏆 Пока никого", reply_markup=back_kb())
    medals, lines = ["🥇", "🥈", "🥉"], ["🏆 Топ монет"]
    for i, (uid, coins) in enumerate(rows):
        m = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{m} {user_link_with_nick(uid, call.message.chat.id, '')} — {coins}💰")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_shop")
async def cb_shop(call: types.CallbackQuery):
    await call.message.edit_text("🛒 Магазин\n1️⃣ Множитель x2 — 500💰\n2️⃣ Сброс работы — 300💰\n\n/buy 1  /buy 2", reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_games")
async def cb_games(call: types.CallbackQuery):
    await call.message.edit_text("🎮 Игры\n/casino 100 — слоты\n/darts 50 — дартс\n/coinflip 30 — орёл/решка\n/rps 15 — КНБ\n\n⚔️ Дуэли:\n/dice, /basketball, /football, /bowling", reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_rp")
async def cb_rp(call: types.CallbackQuery):
    await call.message.edit_text("❤️ RP действия\n/rp — список\nобнять @user, поцеловать @user\n💍 Браки: +брак, +развод, +пара\n📛 Ники: +ник @user НовыйНик", reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_back")
async def cb_back(call: types.CallbackQuery):
    me = await bot.get_me()
    await call.message.edit_text(f"👋 Привет, {call.from_user.first_name}!\nЯ VOID Helper.", reply_markup=main_menu_kb(me.username))
    await call.answer()

# ============================================================
#  HELP
# ============================================================
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.reply("""
📋 <b>VOID HELPER</b>

<b>👤 Профиль:</b> /profile, /top
<b>💼 Экономика:</b> /work, /daily, /shop, /buy
<b>🎮 Игры:</b> /casino, /darts, /coinflip, /rps
<b>⚔️ Дуэли:</b> /dice, /basketball, /football, /bowling
<b>❤️ RP:</b> обнять, поцеловать, ударить, погладить
<b>💍 Браки:</b> +брак, +развод, +пара, +список браков
<b>📛 Ники:</b> +ник @user НовыйНик

<b>🔒 Управление чатом:</b>
-чат, +чат, /setautoschedule, /check_schedule, /setwelcome

<b>🛡 Модерация:</b>
!мут @user 10м причина — замутить
-размут @user — размутить
!мутлист — список замученных

!бан @user 7д причина — забанить
-разбан @user — разбанить
!банлист — список забаненных

!кик @user — кикнуть

!варн @user причина — выдать варн
-варн @user — снять варн
!варны @user — посмотреть варны
-очиститьварны @user — очистить все варны

!админ @user — назначить админа
-админ @user — снять админа

/moderation on/off — автомодерация

⚠️ <b>Система варнов:</b>
1-2 — предупреждение
3 — мут 7 дней
4 — мут 14 дней
5 — мут 30 дней
6+ — бан навсегда
""")

# ============================================================
#  ЭКОНОМИКА
# ============================================================
@dp.message(Command("profile"))
async def profile(message: types.Message):
    uid = message.from_user.id
    coins, xp, warns, _ = get_user(uid)
    await message.reply(f"👤 Профиль\n\n{user_link_with_nick(uid, message.chat.id, message.from_user.first_name)}\n⭐ Уровень: {xp//100}\n💰 Монеты: {coins}\n📊 Опыт: {xp}\n⚠️ Варны: {warns}/3")

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    rows = db("SELECT id, coins FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    if not rows: return await message.reply("🏆 Пока никого")
    medals, lines = ["🥇", "🥈", "🥉"], ["🏆 Топ монет"]
    for i, (uid, coins) in enumerate(rows):
        m = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{m} {user_link_with_nick(uid, message.chat.id, '')} — {coins}💰")
    await message.reply("\n".join(lines))

@dp.message(Command("work"))
async def work(message: types.Message):
    uid = message.from_user.id
    last = db("SELECT last_work FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    now = int(time.time())
    if now - last < 600:
        rem = 600 - (now - last)
        return await message.reply(f"⏳ Отдых {rem//60}м {rem%60}с")
    jobs = [("💻 Написал бота", 600, 1000), ("📦 Развёз посылки", 400, 700), ("🚗 Отвёз клиента", 500, 800)]
    job, mn, mx = random.choice(jobs)
    pay = random.randint(mn, mx)
    xpg = random.randint(15, 35)
    add_coins(uid, pay)
    new_level = add_xp(uid, xpg)
    db("UPDATE users SET last_work=? WHERE id=?", (now, uid))
    await message.reply(f"⛏ {job}\n💰 +{pay}💰\n✨ +{xpg} XP" + (f"\n🎉 {new_level} уровень!" if new_level else ""))

@dp.message(Command("daily"))
async def daily(message: types.Message):
    uid = message.from_user.id
    now = int(time.time())
    last = db("SELECT last_daily FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    if now - last < 86400:
        rem = 86400 - (now - last)
        return await message.reply(f"🎁 Бонус через {rem//3600}ч {(rem%3600)//60}м")
    bonus = random.randint(300, 700)
    add_coins(uid, bonus)
    new_level = add_xp(uid, 50)
    db("UPDATE users SET last_daily=? WHERE id=?", (now, uid))
    await message.reply(f"🎁 Бонус! +{bonus}💰 +50 XP" + (f"\n🎉 {new_level} уровень!" if new_level else ""))

@dp.message(Command("shop"))
async def shop_cmd(message: types.Message):
    await message.reply("🛒 Магазин\n1️⃣ Множитель x2 — 500💰\n2️⃣ Сброс работы — 300💰\n\n/buy 1  /buy 2")

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    args = message.text.split()
    if len(args) < 2: return await message.reply("❌ /buy 1")
    try: item = int(args[1])
    except: return await message.reply("❌ Некорректный номер")
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if item == 1:
        if coins < 500: return await message.reply(f"❌ Нужно 500💰")
        add_coins(uid, -500)
        db("UPDATE users SET xp_multiplier=2.0 WHERE id=?", (uid,))
        asyncio.create_task(reset_multiplier(uid, 3600))
        await message.reply("✨ Множитель x2 на 1 час!")
    elif item == 2:
        if coins < 300: return await message.reply(f"❌ Нужно 300💰")
        add_coins(uid, -300)
        db("UPDATE users SET last_work=0 WHERE id=?", (uid,))
        await message.reply("⚡ Кулдаун работы сброшен!")

async def reset_multiplier(uid, delay):
    await asyncio.sleep(delay)
    db("UPDATE users SET xp_multiplier=1.0 WHERE id=?", (uid,))

# ============================================================
#  ИГРЫ
# ============================================================
async def check_bet(message, bet, min_bet=10):
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet < min_bet: await message.reply(f"❌ Мин. ставка: {min_bet}"); return None
    if bet > coins: await message.reply(f"❌ У тебя {coins}💰"); return None
    add_coins(uid, -bet)
    return uid

@dp.message(Command("casino"))
async def casino_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet: return await message.reply("🎰 /casino 100")
    uid = await check_bet(message, bet, 10)
    if not uid: return
    msg = await bot.send_dice(message.chat.id, emoji="🎰")
    await asyncio.sleep(DICE_WAIT["🎰"])
    v = msg.dice.value
    if v == 64: add_coins(uid, bet*10); add_xp(uid, 150); await message.reply(f"🎉 ДЖЕКПОТ! +{bet*10}💰")
    elif v >= 50: add_coins(uid, bet*4); add_xp(uid, 40); await message.reply(f"🎰 КРУПНО! +{bet*4}💰")
    elif v >= 30: add_coins(uid, bet*2); add_xp(uid, 15); await message.reply(f"🎰 ВЫИГРЫШ! +{bet*2}💰")
    elif v >= 15: add_coins(uid, bet); await message.reply(f"🎰 Возврат {bet}💰")
    else: await message.reply(f"😞 Проиграл {bet}💰")

@dp.message(Command("darts"))
async def darts_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet: return await message.reply("🎯 /darts 50")
    uid = await check_bet(message, bet, 10)
    if not uid: return
    msg = await bot.send_dice(message.chat.id, emoji="🎯")
    await asyncio.sleep(DICE_WAIT["🎯"])
    v = msg.dice.value
    if v == 6: add_coins(uid, bet*5); await message.reply(f"🎯 БУЛЛ-АЙ! +{bet*5}💰")
    elif v == 5: add_coins(uid, bet*3); await message.reply(f"🎯 ОТЛИЧНО! +{bet*3}💰")
    elif v == 4: add_coins(uid, bet*2); await message.reply(f"🎯 ХОРОШО! +{bet*2}💰")
    elif v == 3: add_coins(uid, bet); await message.reply(f"🎯 Возврат {bet}💰")
    else: await message.reply(f"😞 Мимо! -{bet}💰")

@dp.message(Command("coinflip"))
async def coinflip_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet: return await message.reply("🪙 /coinflip 30")
    uid = await check_bet(message, bet, 10)
    if not uid: return
    result = random.choice(["орёл", "решка"])
    user_choice = random.choice(["орёл", "решка"])
    if result == user_choice: add_coins(uid, bet*2); await message.reply(f"🪙 {result}!\n🎉 +{bet*2}💰")
    else: await message.reply(f"🪙 {result}!\n😞 -{bet}💰")

@dp.message(Command("rps"))
async def rps_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet: return await message.reply("✊ /rps 15")
    uid = await check_bet(message, bet, 10)
    if not uid: return
    await message.reply("✊ Камень, ножницы или бумага? (15 сек)")
    try:
        answer = await bot.wait_for("message", timeout=15.0, check=lambda m: m.from_user.id == uid and m.text and m.text.lower() in ["камень", "ножницы", "бумага"] and m.reply_to_message)
        user = answer.text.lower()
        bot_choice = random.choice(["камень", "ножницы", "бумага"])
        if user == bot_choice: add_coins(uid, bet); await message.reply(f"🤝 Ничья! {bot_choice}\nВозврат {bet}💰")
        elif (user == "камень" and bot_choice == "ножницы") or (user == "ножницы" and bot_choice == "бумага") or (user == "бумага" and bot_choice == "камень"):
            add_coins(uid, bet*2); await message.reply(f"🎉 Победа! +{bet*2}💰")
        else: await message.reply(f"😞 Поражение! -{bet}💰")
    except:
        await message.reply("⏰ Время вышло! Ставка возвращена")
        add_coins(uid, bet)

# ============================================================
#  ДУЭЛИ (ИСПРАВЛЕНО)
# ============================================================
active_duels = {}
DUEL_GAMES = {
    "dice": {"emoji": "🎲", "name": "Кости"}, 
    "basketball": {"emoji": "🏀", "name": "Баскетбол"}, 
    "football": {"emoji": "⚽", "name": "Футбол"}, 
    "bowling": {"emoji": "🎳", "name": "Боулинг"}
}

def duel_invite_kb(game_type, challenger_id, chat_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"duel_accept_{game_type}_{challenger_id}_{chat_id}"),
         InlineKeyboardButton(text="❌ Отказать", callback_data=f"duel_decline_{game_type}_{challenger_id}")]
    ])

@dp.message(Command("dice"))
async def cmd_dice(message: types.Message):
    await start_duel_invite(message, "dice")

@dp.message(Command("basketball"))
async def cmd_basketball(message: types.Message):
    await start_duel_invite(message, "basketball")

@dp.message(Command("football"))
async def cmd_football(message: types.Message):
    await start_duel_invite(message, "football")

@dp.message(Command("bowling"))
async def cmd_bowling(message: types.Message):
    await start_duel_invite(message, "bowling")

async def start_duel_invite(message: types.Message, game_type: str):
    if not message.reply_to_message:
        return await message.reply("❌ Ответь на сообщение соперника!")
    
    challenger = message.from_user
    opponent = message.reply_to_message.from_user
    
    if challenger.id == opponent.id:
        return await message.reply("❌ Нельзя играть с самим собой!")
    
    if opponent.is_bot:
        return await message.reply("❌ Нельзя играть с ботом!")
    
    chat_id = message.chat.id
    duel_key = f"{chat_id}_{challenger.id}_{opponent.id}"
    
    if duel_key in active_duels:
        return await message.reply("⚠️ Вы уже вызвали этого игрока! Дождитесь ответа.")
    
    game = DUEL_GAMES[game_type]
    active_duels[duel_key] = {
        "game_type": game_type, 
        "challenger": challenger.id, 
        "opponent": opponent.id, 
        "chat_id": chat_id, 
        "status": "waiting"
    }
    
    await message.reply(
        f"{game['emoji']} <b>{game['name']}</b>\n\n"
        f"{user_link_with_nick(challenger.id, chat_id, challenger.first_name)} вызывает "
        f"{user_link_with_nick(opponent.id, chat_id, opponent.first_name)} на дуэль!\n\n"
        f"Согласны?",
        reply_markup=duel_invite_kb(game_type, challenger.id, chat_id)
    )

@dp.callback_query(F.data.startswith("duel_accept_"))
async def duel_accept(call: types.CallbackQuery):
    parts = call.data.split("_")
    game_type = parts[2]
    challenger_id = int(parts[3])
    chat_id = int(parts[4])
    opponent_id = call.from_user.id
    
    duel_key = f"{chat_id}_{challenger_id}_{opponent_id}"
    
    if duel_key not in active_duels:
        return await call.answer("❌ Вызов уже недействителен!", show_alert=True)
    
    if active_duels[duel_key]["opponent"] != opponent_id:
        return await call.answer("❌ Это не ваш вызов!", show_alert=True)
    
    active_duels[duel_key]["status"] = "accepted"
    await call.message.delete()
    await call.message.answer(f"✅ {user_link_with_nick(opponent_id, chat_id, call.from_user.first_name)} принял(а) вызов!")
    await run_duel(chat_id, challenger_id, opponent_id, game_type)
    await call.answer()

@dp.callback_query(F.data.startswith("duel_decline_"))
async def duel_decline(call: types.CallbackQuery):
    parts = call.data.split("_")
    game_type = parts[2]
    challenger_id = int(parts[3])
    opponent_id = call.from_user.id
    chat_id = call.message.chat.id
    
    duel_key = f"{chat_id}_{challenger_id}_{opponent_id}"
    if duel_key in active_duels:
        del active_duels[duel_key]
    
    await call.message.edit_text(
        f"❌ {user_link_with_nick(opponent_id, chat_id, call.from_user.first_name)} отклонил(а) вызов на дуэль!"
    )
    await call.answer()

async def run_duel(chat_id: int, player1_id: int, player2_id: int, game_type: str):
    game = DUEL_GAMES[game_type]
    p1 = await bot.get_chat_member(chat_id, player1_id)
    p2 = await bot.get_chat_member(chat_id, player2_id)
    p1_name = p1.user.first_name
    p2_name = p2.user.first_name
    
    msg = await bot.send_message(
        chat_id,
        f"{game['emoji']} <b>{game['name']}</b>\n\n"
        f"🆚 {user_link_with_nick(player1_id, chat_id, p1_name)} vs {user_link_with_nick(player2_id, chat_id, p2_name)}\n\n"
        f"🎲 {user_link_with_nick(player1_id, chat_id, p1_name)} бросает..."
    )
    
    await asyncio.sleep(1)
    await msg.edit_text(
        f"{game['emoji']} <b>{game['name']}</b>\n\n"
        f"🆚 {user_link_with_nick(player1_id, chat_id, p1_name)} vs {user_link_with_nick(player2_id, chat_id, p2_name)}\n\n"
        f"🎲 {user_link_with_nick(player1_id, chat_id, p1_name)} бросает..."
    )
    
    dice1 = await bot.send_dice(chat_id, emoji="🎲")
    await asyncio.sleep(DICE_WAIT["🎲"])
    score1 = dice1.dice.value
    
    await msg.edit_text(
        f"{game['emoji']} <b>{game['name']}</b>\n\n"
        f"🆚 {user_link_with_nick(player1_id, chat_id, p1_name)}: <b>{score1}</b>\n"
        f"🎲 {user_link_with_nick(player2_id, chat_id, p2_name)} бросает..."
    )
    
    dice2 = await bot.send_dice(chat_id, emoji="🎲")
    await asyncio.sleep(DICE_WAIT["🎲"])
    score2 = dice2.dice.value
    
    if score1 > score2:
        winner_id = player1_id
        winner_name = p1_name
    elif score2 > score1:
        winner_id = player2_id
        winner_name = p2_name
    else:
        winner_id = None
    
    if winner_id:
        add_coins(winner_id, 150)
        add_xp(winner_id, 30)
        await msg.edit_text(
            f"{game['emoji']} <b>{game['name']}</b>\n\n"
            f"{user_link_with_nick(player1_id, chat_id, p1_name)}: <b>{score1}</b>\n"
            f"{user_link_with_nick(player2_id, chat_id, p2_name)}: <b>{score2}</b>\n\n"
            f"🏆 <b>ПОБЕДИТЕЛЬ:</b> {user_link_with_nick(winner_id, chat_id, winner_name)}!\n"
            f"💰 +150 монет, ✨ +30 XP"
        )
    else:
        await msg.edit_text(
            f"{game['emoji']} <b>{game['name']}</b>\n\n"
            f"{user_link_with_nick(player1_id, chat_id, p1_name)}: <b>{score1}</b>\n"
            f"{user_link_with_nick(player2_id, chat_id, p2_name)}: <b>{score2}</b>\n\n"
            f"🤝 <b>НИЧЬЯ!</b>"
        )
    
    duel_key = f"{chat_id}_{player1_id}_{player2_id}"
    if duel_key in active_duels:
        del active_duels[duel_key]


# ============================================================
#  RP ДЕЙСТВИЯ
# ============================================================
RP_ACTIONS = {"обнять": ["🤗 обнял", "🤗 обняла", "🤗 обняли"], "поцеловать": ["😘 поцеловал", "😘 поцеловала", "😘 поцеловали"], "ударить": ["👊 ударил", "👊 ударила", "👊 ударили"], "погладить": ["🫳 погладил", "🫳 погладила", "🫳 погладили"], "прижаться": ["💕 прижался", "💕 прижалась", "💕 прижались"], "взять_за_руку": ["💑 взял за руку", "💑 взяла за руку", "💑 взяли за руку"]}

@dp.message(Command("rp"))
async def rp_list_cmd(message: types.Message):
    await message.reply(f"🎭 RP действия:\n" + "\n".join([f"• {k}" for k in RP_ACTIONS.keys()]))

@dp.message(F.text.lower().startswith(tuple(RP_ACTIONS.keys())))
async def rp_action(message: types.Message):
    if message.chat.type not in ("group", "supergroup"): return
    text = message.text.lower()
    action = next((k for k in RP_ACTIONS.keys() if text.startswith(k)), None)
    if not action: return
    target_id, target_name, _ = await resolve_target(message, message.text[len(action):].strip())
    if not target_id: return await message.reply(f"❌ Укажи @юзертег")
    if target_id == message.from_user.id: return await message.reply("❌ Нельзя с собой!")
    gender_row = db("SELECT gender FROM user_gender WHERE user_id=?", (message.from_user.id,), fetch=True)
    gender = gender_row[0][0] if gender_row else 0
    verb = RP_ACTIONS[action][0] if gender == 0 else RP_ACTIONS[action][1] if gender == 1 else RP_ACTIONS[action][2]
    await message.reply(f"{user_link_with_nick(message.from_user.id, message.chat.id, message.from_user.first_name)} {verb} {user_link_with_nick(target_id, message.chat.id, target_name)}!")

# ============================================================
#  БРАКИ
# ============================================================
async def get_marriage_info(uid, chat_id):
    row = db("SELECT user1, user2, since FROM marriages WHERE chat_id=? AND (user1=? OR user2=?)", (chat_id, uid, uid), fetch=True)
    if row:
        u1, u2, since = row[0]
        return (u2 if u1 == uid else u1, (int(time.time()) - since) // 86400)
    return None, None

@dp.message(F.text.lower().startswith(("+брак", "!брак")))
async def marry_cmd(message: types.Message):
    uid = message.from_user.id
    if (await get_marriage_info(uid, message.chat.id))[0]: return await message.reply("❌ Вы уже в браке!")
    args = message.text[5:].strip() if message.text.startswith("+брак") else message.text[5:].strip()
    target_id, target_name, _ = await resolve_target(message, args)
    if not target_id: return await message.reply("❌ Укажи @юзертег")
    if target_id == uid: return await message.reply("❌ Нельзя на себе!")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💍 Принять", callback_data=f"marry_accept_{uid}_{target_id}_{message.chat.id}"), InlineKeyboardButton(text="❌ Отказать", callback_data=f"marry_deny_{uid}_{target_id}")]])
    await message.reply(f"💍 {user_link_with_nick(uid, message.chat.id, message.from_user.first_name)} предлагает брак {user_link_with_nick(target_id, message.chat.id, target_name)}!", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("marry_accept_"))
async def marry_accept(call: types.CallbackQuery):
    _, _, s_id, t_id, c_id = call.data.split("_")
    s_id, t_id, c_id = int(s_id), int(t_id), int(c_id)
    if call.from_user.id != t_id: return await call.answer("Не вам!", show_alert=True)
    db("INSERT INTO marriages (user1, user2, chat_id, since) VALUES (?,?,?,?)", (s_id, t_id, c_id, int(time.time())))
    await call.message.edit_text(f"💍 ПОЗДРАВЛЯЕМ!\n\n{user_link_with_nick(s_id, c_id, '')} и {user_link_with_nick(t_id, c_id, '')} теперь в браке!")

@dp.callback_query(F.data.startswith("marry_deny_"))
async def marry_deny(call: types.CallbackQuery):
    _, _, s_id, t_id = call.data.split("_")
    if call.from_user.id != int(t_id): return await call.answer("Не вам!", show_alert=True)
    await call.message.edit_text(f"❌ Отказ в браке.")

@dp.message(F.text.lower().startswith(("+развод", "!развод")))
async def divorce_cmd(message: types.Message):
    uid = message.from_user.id
    partner, days = await get_marriage_info(uid, message.chat.id)
    if not partner: return await message.reply("❌ Не в браке!")
    db("DELETE FROM marriages WHERE chat_id=? AND (user1=? OR user2=?)", (message.chat.id, uid, uid))
    await message.reply(f"💔 Развод! Были вместе {days} дней.")

@dp.message(F.text.lower().startswith(("+пара", "!пара")))
async def couple_info(message: types.Message):
    uid = message.from_user.id
    partner, days = await get_marriage_info(uid, message.chat.id)
    if not partner: return await message.reply("💔 Не в браке.")
    await message.reply(f"💑 Пара: {user_link_with_nick(uid, message.chat.id, '')} 💕 {user_link_with_nick(partner, message.chat.id, '')}\n📅 {days} дней")

@dp.message(F.text.lower().startswith(("+список браков", "!список браков")))
async def marriages_list(message: types.Message):
    rows = db("SELECT user1, user2, since FROM marriages WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not rows: return await message.reply("📋 Нет браков.")
    lines = ["📋 Список браков:"]
    for u1, u2, since in rows:
        days = (int(time.time()) - since) // 86400
        lines.append(f"💑 {user_link_with_nick(u1, message.chat.id, '')} + {user_link_with_nick(u2, message.chat.id, '')} — {days} дн.")
    await message.reply("\n".join(lines))

# ============================================================
#  НИКНЕЙМЫ
# ============================================================
@dp.message(F.text.lower().startswith(("+ник", "!ник")))
async def set_nickname(message: types.Message):
    args = message.text[4:].strip() if message.text.startswith("+ник") else message.text[4:].strip()
    target_id, target_name, _ = await resolve_target(message, args)
    if not target_id: return await message.reply("❌ Укажи @юзертег")
    nickname = " ".join([w for w in args.split() if not w.startswith("@")])
    if not nickname: return await message.reply("❌ Укажи ник!")
    db("INSERT OR REPLACE INTO user_nicknames (user_id, chat_id, nickname) VALUES (?,?,?)", (target_id, message.chat.id, nickname))
    await message.reply(f"✅ Ник: {user_link_with_nick(target_id, message.chat.id, target_name)} → <b>{nickname}</b>")

# ============================================================
#  МОДЕРАЦИЯ
# ============================================================
async def mod_guard(message):
    if message.chat.type not in ("group", "supergroup"): return False
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Только для админов")
        return False
    return True

@dp.message(F.text.lower().startswith(("!мут", "-мут")))
async def mute_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split(maxsplit=1)
    target_arg = args[1] if len(args) > 1 else ""
    uid, name, _ = await resolve_target(message, target_arg)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!\nПример: !мут @user 10м причина")
    if await is_admin(message.chat.id, uid): return await message.reply("❌ Нельзя замутить админа!")
    
    parts = message.text.split()
    duration_str = next((p for p in parts[1:] if re.search(r'\d+[мчд]|мин|час|дн|мес|год', p.lower())), "1ч")
    reason = " ".join([p for p in parts[1:] if not p.startswith("@") and p != duration_str]) or "нарушение правил"
    
    sec = parse_duration(duration_str)
    until = int(time.time()) + sec
    db("INSERT OR REPLACE INTO muted (user_id, chat_id, until) VALUES (?,?,?)", (uid, message.chat.id, until))
    
    try:
        if message.reply_to_message: await message.reply_to_message.delete()
        await bot.restrict_chat_member(message.chat.id, uid, permissions=ChatPermissions(can_send_messages=False), until_date=datetime.fromtimestamp(until, tz=timezone.utc))
        await message.reply(f"🔇 МУТ\n👤 {user_link_with_nick(uid, message.chat.id, name)}\n⏳ {fmt_dur(sec)}\n📌 {reason}")
        await send_punishment_log(message, uid, '🔇 МУТ', reason, fmt_dur(sec))
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().startswith(("!размут", "-размут")))
async def unmute_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split(maxsplit=1)
    target_arg = args[1] if len(args) > 1 else ""
    uid, name, _ = await resolve_target(message, target_arg)
    if not uid: return await message.reply("❌ Укажи @юзертег!")
    db("DELETE FROM muted WHERE user_id=? AND chat_id=?", (uid, message.chat.id))
    try: await bot.restrict_chat_member(message.chat.id, uid, permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True))
    except: pass
    await message.reply(f"✅ {user_link_with_nick(uid, message.chat.id, name)} размучен.")

@dp.message(F.text.lower().startswith(("!мутлист", "-мутлист")))
async def mutelist_cmd(message: types.Message):
    if not await mod_guard(message): return
    muted = db("SELECT user_id, until FROM muted WHERE chat_id=? AND until > ? ORDER BY until", (message.chat.id, int(time.time())), fetch=True)
    if not muted: return await message.reply("📋 Нет замученных.")
    lines = ["📋 ЗАМУЧЕННЫЕ:"]
    for uid, until in muted[:20]:
        try:
            u = await bot.get_chat(uid)
            lines.append(f"• {user_link_with_nick(uid, message.chat.id, u.first_name)} — до {datetime.fromtimestamp(until).strftime('%d.%m.%Y %H:%M')}")
        except: lines.append(f"• ID {uid}")
    await message.reply("\n".join(lines))

@dp.message(F.text.lower().startswith(("!бан", "-бан")))
async def ban_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split(maxsplit=1)
    target_arg = args[1] if len(args) > 1 else ""
    uid, name, _ = await resolve_target(message, target_arg)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!\nПример: !бан @user 7д причина")
    if await is_admin(message.chat.id, uid): return await message.reply("❌ Нельзя забанить админа!")
    
    parts = message.text.split()
    duration_str = next((p for p in parts[1:] if re.search(r'\d+[мчд]|мин|час|дн|мес|год', p.lower())), None)
    reason = " ".join([p for p in parts[1:] if not p.startswith("@") and p != duration_str]) or "нарушение правил"
    
    db("INSERT OR IGNORE INTO banned (user_id, chat_id) VALUES (?,?)", (uid, message.chat.id))
    try:
        if message.reply_to_message: await message.reply_to_message.delete()
        await bot.ban_chat_member(message.chat.id, uid)
        if duration_str:
            sec = parse_duration(duration_str)
            await message.reply(f"🚫 БАН\n👤 {user_link_with_nick(uid, message.chat.id, name)}\n⏳ {fmt_dur(sec)}\n📌 {reason}")
            asyncio.create_task(unban_after(uid, message.chat.id, sec))
        else: await message.reply(f"🚫 БАН НАВСЕГДА\n👤 {user_link_with_nick(uid, message.chat.id, name)}\n📌 {reason}")
        await send_punishment_log(message, uid, '🚫 БАН', reason, fmt_dur(sec) if duration_str else "навсегда")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

async def unban_after(uid, chat_id, delay):
    await asyncio.sleep(delay)
    db("DELETE FROM banned WHERE user_id=? AND chat_id=?", (uid, chat_id))
    try: await bot.unban_chat_member(chat_id, uid)
    except: pass

@dp.message(F.text.lower().startswith(("!разбан", "-разбан")))
async def unban_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split(maxsplit=1)
    target_arg = args[1] if len(args) > 1 else ""
    uid, name, _ = await resolve_target(message, target_arg)
    if not uid: return await message.reply("❌ Укажи @юзертег!")
    db("DELETE FROM banned WHERE user_id=? AND chat_id=?", (uid, message.chat.id))
    try: await bot.unban_chat_member(message.chat.id, uid)
    except: pass
    await message.reply(f"✅ {user_link_with_nick(uid, message.chat.id, name)} разбанен.")

@dp.message(F.text.lower().startswith(("!банлист", "-банлист")))
async def banlist_cmd(message: types.Message):
    if not await mod_guard(message): return
    banned = db("SELECT user_id FROM banned WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not banned: return await message.reply("📋 Нет забаненных.")
    lines = ["📋 ЗАБАНЕННЫЕ:"]
    for (uid,) in banned[:20]:
        try:
            u = await bot.get_chat(uid)
            lines.append(f"• {user_link_with_nick(uid, message.chat.id, u.first_name)}")
        except: lines.append(f"• ID {uid}")
    await message.reply("\n".join(lines))

@dp.message(F.text.lower().startswith(("!кик", "-кик")))
async def kick_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split(maxsplit=1)
    target_arg = args[1] if len(args) > 1 else ""
    uid, name, _ = await resolve_target(message, target_arg)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    if await is_admin(message.chat.id, uid): return await message.reply("❌ Нельзя кикнуть админа!")
    try:
        if message.reply_to_message: await message.reply_to_message.delete()
        await bot.ban_chat_member(message.chat.id, uid)
        await asyncio.sleep(0.5)
        await bot.unban_chat_member(message.chat.id, uid)
        await message.reply(f"👢 {user_link_with_nick(uid, message.chat.id, name)} кикнут.")
        await send_punishment_log(message, uid, '👢 КИК', "нарушение правил")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# ============================================================
#  !варн — ВЫДАТЬ ВАРН
# ============================================================
@dp.message(F.text.lower().startswith("!варн"))
async def give_warn_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split(maxsplit=1)
    target_arg = args[1] if len(args) > 1 else ""
    uid, name, _ = await resolve_target(message, target_arg)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!\nПример: !варн @user оскорбление")
    if await is_admin(message.chat.id, uid): return await message.reply("❌ Нельзя выдать варн админу!")
    
    parts = message.text.split()
    reason = " ".join([p for p in parts[1:] if not p.startswith("@")]) or "нарушение правил"
    
    if message.reply_to_message:
        try: await message.reply_to_message.delete()
        except: pass
    
    warn_count = add_warn(uid, message.chat.id, reason, 30)
    punishment_type, duration, punishment_text = get_warn_punishment(warn_count)
    
    if punishment_type == 'mute':
        until = int(time.time()) + duration
        db("INSERT OR REPLACE INTO muted (user_id, chat_id, until) VALUES (?,?,?)", (uid, message.chat.id, until))
        try: await bot.restrict_chat_member(message.chat.id, uid, permissions=ChatPermissions(can_send_messages=False), until_date=datetime.fromtimestamp(until, tz=timezone.utc))
        except: pass
    elif punishment_type == 'ban':
        db("INSERT OR IGNORE INTO banned (user_id, chat_id) VALUES (?,?)", (uid, message.chat.id))
        try: await bot.ban_chat_member(message.chat.id, uid)
        except: pass
    
    await message.reply(f"⚠️ ПРЕДУПРЕЖДЕНИЕ\n👤 {user_link_with_nick(uid, message.chat.id, name)}\n📌 {reason}\n{punishment_text}")
    await send_punishment_log(message, uid, punishment_text.split()[0], reason, fmt_dur(duration) if duration else "")

# ============================================================
#  -варн — СНЯТЬ ВАРН
# ============================================================
@dp.message(F.text.lower().startswith("-варн"))
async def remove_warn_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split(maxsplit=1)
    target_arg = args[1] if len(args) > 1 else ""
    uid, name, _ = await resolve_target(message, target_arg)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!\nПример: -варн @user")
    
    warns = get_user_warns(uid, message.chat.id)
    if not warns: return await message.reply(f"❌ У {user_link_with_nick(uid, message.chat.id, name)} нет варнов.")
    
    db("DELETE FROM warns_system WHERE id=?", (warns[0][0],))
    await message.reply(f"✅ Снят 1 варн с {user_link_with_nick(uid, message.chat.id, name)}.\n📊 Осталось: {len(warns)-1}")

# ============================================================
#  !варны / !варнлист — ПОСМОТРЕТЬ ВАРНЫ
# ============================================================
@dp.message(F.text.lower().startswith(("!варны", "!варнлист", "-варны", "-варнлист")))
async def warnlist_cmd(message: types.Message):
    args = message.text.split(maxsplit=1)
    target_arg = args[1] if len(args) > 1 else ""
    uid, name, _ = await resolve_target(message, target_arg)
    
    if uid and uid != message.from_user.id:
        if not await is_admin(message.chat.id, message.from_user.id):
            return await message.reply("❌ Только админы могут смотреть чужие варны!")
    
    if not uid:
        uid = message.from_user.id
        name = message.from_user.first_name
    
    warns = get_user_warns(uid, message.chat.id)
    warn_count = len(warns) if warns else 0
    
    if warn_count == 0:
        return await message.reply(f"✅ У {user_link_with_nick(uid, message.chat.id, name)} нет варнов.")
    
    punishment_type, duration, punishment_text = get_warn_punishment(warn_count)
    lines = [f"📋 ВАРНЫ: {user_link_with_nick(uid, message.chat.id, name)}", f"📊 Всего: {warn_count}/3", "", "История:"]
    for w in warns[:10]:
        lines.append(f"• {datetime.fromtimestamp(w[2]).strftime('%d.%m.%Y')}: {w[1]} (до {datetime.fromtimestamp(w[3]).strftime('%d.%m.%Y')})")
    lines.extend(["", f"Статус: {punishment_text}"])
    await message.reply("\n".join(lines))

# ============================================================
#  -очиститьварны — ОЧИСТИТЬ ВСЕ ВАРНЫ
# ============================================================
@dp.message(F.text.lower().startswith(("-очиститьварны", "!очиститьварны")))
async def clear_warns_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split(maxsplit=1)
    target_arg = args[1] if len(args) > 1 else ""
    uid, name, _ = await resolve_target(message, target_arg)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    clear_warns(uid, message.chat.id)
    await message.reply(f"✅ Варны {user_link_with_nick(uid, message.chat.id, name)} очищены.")

# ============================================================
#  !админ / -админ
# ============================================================
@dp.message(F.text.lower().startswith(("!админ", "+тг")))
async def give_admin_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split()
    if len(args) < 2: return await message.reply("❌ Укажи @юзертег!")
    uid, name, _ = await resolve_target(message, args[1])
    if not uid: return await message.reply("❌ Не найден!")
    try:
        await bot.promote_chat_member(message.chat.id, uid, can_manage_chat=True, can_delete_messages=True, can_restrict_members=True, can_invite_users=True, can_pin_messages=True, can_change_info=True, can_promote_members=False, can_manage_topics=True)
        await message.reply(f"✅ {user_link_with_nick(uid, message.chat.id, name)} назначен админом!")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().startswith(("-админ", "!снятьадмин")))
async def remove_admin_cmd(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.split()
    if len(args) < 2: return await message.reply("❌ Укажи @юзертег!")
    uid, name, _ = await resolve_target(message, args[1])
    if not uid: return await message.reply("❌ Не найден!")
    try:
        await bot.promote_chat_member(message.chat.id, uid, can_manage_chat=False, can_delete_messages=False, can_restrict_members=False, can_invite_users=False, can_pin_messages=False, can_change_info=False, can_promote_members=False)
        await message.reply(f"🔻 {user_link_with_nick(uid, message.chat.id, name)} лишён прав.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# ============================================================
#  УПРАВЛЕНИЕ ЧАТОМ
# ============================================================
@dp.message(Command("moderation"))
async def toggle_moderation(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.replace("/moderation", "").strip().lower()
    if args == "on": db("INSERT OR REPLACE INTO moderation_settings VALUES (?,?)", (message.chat.id, 1)); await message.reply("✅ ВКЛ")
    elif args == "off": db("INSERT OR REPLACE INTO moderation_settings VALUES (?,?)", (message.chat.id, 0)); await message.reply("✅ ВЫКЛ")
    else: await message.reply(f"Статус: {'ВКЛ' if await is_moderation_enabled(message.chat.id) else 'ВЫКЛ'}")

@dp.message(Command("setautoschedule"))
async def set_auto_schedule(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.replace("/setautoschedule", "").strip().split()
    if len(args) < 2: return await message.reply("⏰ /setautoschedule 23:00 09:00")
    if args[0].lower() == "off":
        db("UPDATE chat_settings SET close_time=NULL, open_time=NULL WHERE chat_id=?", (message.chat.id,))
        return await message.reply("✅ Отключено.")
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', args[0]) or not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', args[1]):
        return await message.reply("❌ Формат: ЧЧ:ММ")
    await set_chat_schedule(message.chat.id, args[0], args[1])
    await apply_schedule_now(message.chat.id)
    await message.reply(f"✅ Закрытие: {args[0]}, открытие: {args[1]}")

@dp.message(Command("check_schedule"))
async def check_schedule_cmd(message: types.Message):
    row = db("SELECT close_time, open_time, is_closed FROM chat_settings WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not row or not row[0][0]: return await message.reply("⏰ Расписание не установлено.")
    await message.reply(f"📅 Закрытие: {row[0][0]}\n🔓 Открытие: {row[0][1]}\nСтатус: {'🔒 ЗАКРЫТ' if row[0][2] else '🔓 ОТКРЫТ'}")

@dp.message(F.text.lower().startswith(("-чат", "!чат")))
async def close_chat_cmd(message: types.Message):
    if not await mod_guard(message): return
    if await is_chat_closed(message.chat.id): return await message.reply("🔒 Уже закрыт!")
    if await close_chat(message.chat.id):
        await message.reply("✅ Чат закрыт.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔓 Открыть", callback_data=f"open_chat_{message.chat.id}")]]))

@dp.message(F.text.lower().startswith(("+чат", "!открытьчат")))
async def open_chat_cmd(message: types.Message):
    if not await mod_guard(message): return
    if not await is_chat_closed(message.chat.id): return await message.reply("🔓 Уже открыт!")
    if await open_chat(message.chat.id): await message.reply("✅ Чат открыт.")

@dp.callback_query(F.data.startswith("open_chat_"))
async def open_chat_callback(call: types.CallbackQuery):
    chat_id = int(call.data.split("_")[2])
    if not await is_admin(chat_id, call.from_user.id): return await call.answer("❌ Только для админов!", show_alert=True)
    if await open_chat(chat_id):
        await call.message.delete()
        await call.message.answer("✅ Чат открыт.")

# ============================================================
#  ПРИВЕТСТВИЯ
# ============================================================
@dp.my_chat_member()
async def on_bot_added(update: ChatMemberUpdated):
    if update.old_chat_member.status in ('left', 'kicked') and update.new_chat_member.status in ('member', 'administrator'):
        if update.chat.type in ('group', 'supergroup'):
            await bot.send_message(update.chat.id, "👋 VOID Helper здесь!\n/help — все команды.")

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    row = db("SELECT welcome_text FROM group_welcome WHERE chat_id=?", (message.chat.id,), fetch=True)
    template = row[0][0] if row else "👋 Добро пожаловать, {упоминание}!"
    for member in message.new_chat_members:
        if member.id == bot.id: continue
        await message.answer(template.replace("{упоминание}", user_link_with_nick(member.id, message.chat.id, member.first_name)).replace("{имя}", member.first_name))

@dp.message(Command("setwelcome"))
async def set_welcome(message: types.Message):
    if not await mod_guard(message): return
    text = message.text.replace("/setwelcome", "").strip()
    if not text: return await message.reply("📝 /setwelcome текст")
    db("INSERT OR REPLACE INTO group_welcome (chat_id, welcome_text) VALUES (?,?)", (message.chat.id, text))
    await message.reply("✅ Приветствие сохранено!")

# ============================================================
#  РУССКИЕ КОМАНДЫ
# ============================================================
@dp.message(F.text)
async def text_aliases(message: types.Message):
    if not message.text: return
    text = message.text.strip().lower()
    if text == "профиль": return await profile(message)
    if text == "топ": return await top_cmd(message)
    if text == "работа": return await work(message)
    if text in ["бонус", "ежедневный"]: return await daily(message)
    if text == "магазин": return await shop_cmd(message)
    if text.startswith("казино"):
        bet = extract_bet(text)
        if bet: message.text = f"/casino {bet}"; return await casino_cmd(message)
    if text.startswith("дартс"):
        bet = extract_bet(text)
        if bet: message.text = f"/darts {bet}"; return await darts_cmd(message)
    if text.startswith("монетка"):
        bet = extract_bet(text)
        if bet: message.text = f"/coinflip {bet}"; return await coinflip_cmd(message)
    if text.startswith(("кнб", "камень")):
        bet = extract_bet(text)
        if bet: message.text = f"/rps {bet}"; return await rps_cmd(message)
    if text == "кости": return await cmd_dice(message)
    if text == "баскетбол": return await cmd_basketball(message)
    if text == "футбол": return await cmd_football(message)
    if text == "боулинг": return await cmd_bowling(message)

# ============================================================
#  ЗАПУСК
# ============================================================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
    me = await bot.get_me()
    print(f"✅ @{me.username} запущен!")
    
    chats = db("SELECT chat_id FROM chat_settings WHERE close_time IS NOT NULL AND open_time IS NOT NULL", fetch=True)
    for chat in chats: await apply_schedule_now(chat[0])
    
    asyncio.create_task(scheduler_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
