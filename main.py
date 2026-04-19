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
#  НАСТРОЙКИ (ЗАМЕНИТЕ ТОКЕН И ID ВЛАДЕЛЬЦА!)
# ============================================================
TOKEN    = '8203364413:AAHBW_Aek57yZvvSf5JzrYElxLOCky_vnEY'
OWNER_ID = 7173827114
DB_NAME  = 'void_final.db'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

DICE_WAIT = {"🎲": 2, "🎯": 3, "🏀": 4, "⚽": 4, "🎳": 4, "🎰": 4}

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
    welcome_text TEXT DEFAULT '👋 Добро пожаловать, {упоминание}!\nТы вош{ла|ёл|ли} в наш чат.'
)''')
db('''CREATE TABLE IF NOT EXISTS usernames (
    username TEXT PRIMARY KEY,
    user_id  INTEGER,
    name     TEXT
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

# ============================================================
#  АВТООПРЕДЕЛЕНИЕ ПОЛА ПО ИМЕНИ (КАК IRIS)
# ============================================================
def detect_gender_by_name(name: str) -> int:
    name_lower = name.lower().strip()
    female_endings = ('а', 'я', 'ия', 'ь')
    unisex_names = ('саша', 'женя', 'валя', 'слава', 'никита', 'вика', 'ната', 'тоня', 'саня')
    if name_lower in unisex_names:
        return 2
    for ending in female_endings:
        if name_lower.endswith(ending):
            return 1
    return 0

# ============================================================
#  АВТОМОДЕРАЦИЯ (ПО ПРАВИЛАМ ЧАТА)
# ============================================================
BAD_WORDS = {
    'мат': [
        'хуй', 'пизда', 'бля', 'ебать', 'ебаный', 'мудак', 'сука', 'гандон', 'пидор', 'хуесос',
        'долбоеб', 'уебок', 'пиздец', 'ебанутый', 'залупа', 'хуйло', 'сучка', 'блядина'
    ],
    '18plus': [
        'порно', 'секс', 'голый', 'голая', 'эротика', 'интим', 'пенис', 'влагалище', 'оральный',
        'минет', 'куни', 'трах', 'ебля', 'дрочить', 'мастурбация', 'член', 'вагина', 'грудь'
    ],
    'insult': [
        'тупой', 'дебил', 'идиот', 'кретин', 'лох', 'олень', 'баран', 'овца', 'дурак', 'глупый',
        'урод', 'чмо', 'шлюха', 'проститутка'
    ],
    'spam': [r'http[s]?://', r'www\.', r'\.ru', r'\.com', r'\.org', r'\.net']
}

PUNISHMENT_RULES = {
    '18plus': {'warn_days': 30, 'mute_hours': 4},
    'insult': {'warn_days': 30, 'mute_hours': 8},
    'spam': {'warn_days': 30, 'mute_hours': 4},
    'мат': {'warn_days': 30, 'mute_hours': 4},
}

async def auto_moderate(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if message.from_user.is_bot:
        return
    if await is_admin(message.chat.id, message.from_user.id):
        return

    text = (message.text or message.caption or "").lower()
    if not text:
        return

    violations = []
    for word in BAD_WORDS['мат']:
        if word in text:
            violations.append('мат')
            break
    for word in BAD_WORDS['18plus']:
        if word in text:
            violations.append('18plus')
            break
    for word in BAD_WORDS['insult']:
        if word in text:
            violations.append('insult')
            break
    for pattern in BAD_WORDS['spam']:
        if re.search(pattern, text):
            violations.append('spam')
            break

    if not violations:
        return

    violation = violations[0]
    rule = PUNISHMENT_RULES.get(violation, {'warn_days': 30, 'mute_hours': 4})

    uid = message.from_user.id
    db("UPDATE users SET warns = warns + 1 WHERE id=?", (uid,))
    warns = db("SELECT warns FROM users WHERE id=?", (uid,), fetch=True)[0][0]

    reason = f"Автомодерация: {violation}"
    db("INSERT INTO warns_log (user_id, chat_id, reason, date) VALUES (?,?,?,?)",
       (uid, message.chat.id, reason, int(time.time())))

    mute_seconds = rule['mute_hours'] * 3600
    until = int(time.time()) + mute_seconds
    db("INSERT OR REPLACE INTO muted (user_id, chat_id, until) VALUES (?,?,?)", (uid, message.chat.id, until))
    try:
        await bot.restrict_chat_member(
            message.chat.id, uid,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=datetime.fromtimestamp(until, tz=timezone.utc)
        )
        await message.delete()
        await message.answer(
            f"⚠️ {user_link_with_nick(uid, message.chat.id, message.from_user.first_name)} "
            f"нарушил(а) правила ({reason}). Выдан мут на {rule['mute_hours']} часов.",
            delete_after=10
        )
    except Exception as e:
        logging.error(f"Auto-mute error: {e}")

# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
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
    if new_lvl > old_lvl:
        return new_lvl
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
        u = message.reply_to_message.from_user
        return u.id, u.first_name
    for word in args.split():
        if word.startswith("@"):
            uname = word[1:].lower()
            r = db("SELECT user_id,name FROM usernames WHERE username=?", (uname,), fetch=True)
            if r:
                return r[0][0], r[0][1]
            try:
                chat = await bot.get_chat(f"@{uname}")
                return chat.id, getattr(chat, "first_name", uname) or uname
            except:
                pass
    return None, None

async def is_admin(chat_id, user_id) -> bool:
    if user_id == OWNER_ID:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False

def parse_duration(s: str) -> int:
    try:
        if s.endswith("м"): return int(s[:-1]) * 60
        if s.endswith("ч"): return int(s[:-1]) * 3600
        if s.endswith("д"): return int(s[:-1]) * 86400
        if s.endswith("мин"): return int(s[:-3]) * 60
        return int(s) * 60
    except:
        return 300

def fmt_dur(sec: int) -> str:
    if sec >= 86400: return f"{sec//86400} дн."
    if sec >= 3600:  return f"{sec//3600} ч."
    return f"{sec//60} мин."

def get_gender_verb_suffix(gender):
    return "ёл" if gender == 0 else "ла" if gender == 1 else "ли"

def process_welcome_template(template: str, name: str, mention: str, verb_suffix: str) -> str:
    result = template.replace("{name}", name).replace("{имя}", name)
    result = result.replace("{mention}", mention).replace("{упоминание}", mention)
    pattern = r'вош\{[^}]+\}'
    matches = re.findall(pattern, result)
    for match in matches:
        replacement = "вошёл" if verb_suffix == "ёл" else "вошла" if verb_suffix == "ла" else "вошли"
        result = result.replace(match, replacement)
    return result

def extract_bet(text: str):
    numbers = re.findall(r'\d+', text)
    return int(numbers[0]) if numbers else None

async def get_chat_schedule(chat_id):
    row = db("SELECT close_time, open_time FROM chat_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return (row[0][0], row[0][1]) if row else (None, None)

async def set_chat_schedule(chat_id, close_time, open_time):
    db("INSERT OR REPLACE INTO chat_settings (chat_id, close_time, open_time) VALUES (?,?,?)", 
       (chat_id, close_time, open_time))

async def is_chat_closed(chat_id):
    row = db("SELECT is_closed FROM chat_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return row and row[0][0] == 1

async def close_chat(chat_id):
    db("INSERT OR REPLACE INTO chat_settings (chat_id, is_closed) VALUES (?,?)", (chat_id, 1))
    try:
        await bot.set_chat_permissions(
            chat_id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_invite_users=True
            )
        )
    except Exception as e:
        logging.error(f"Ошибка закрытия чата: {e}")

async def open_chat(chat_id):
    db("DELETE FROM chat_settings WHERE chat_id=?", (chat_id,))
    try:
        await bot.set_chat_permissions(
            chat_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True
            )
        )
    except Exception as e:
        logging.error(f"Ошибка открытия чата: {e}")

# ============================================================
#  MIDDLEWARE (С АВТОМОДЕРАЦИЕЙ)
# ============================================================
class MainMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            if event.from_user:
                save_username(event.from_user)
            if event.chat and event.chat.type in ("group", "supergroup") and event.from_user:
                uid = event.from_user.id
                cid = event.chat.id
                if db("SELECT 1 FROM banned WHERE user_id=? AND chat_id=?", (uid, cid), fetch=True):
                    try: await event.delete()
                    except: pass
                    return
                row = db("SELECT until FROM muted WHERE user_id=? AND chat_id=?", (uid, cid), fetch=True)
                if row and row[0][0] > int(time.time()):
                    try: await event.delete()
                    except: pass
                    return
                if await is_chat_closed(cid):
                    if not await is_admin(cid, uid):
                        try: await event.delete()
                        except: pass
                        return
                # Автомодерация
                await auto_moderate(event)
        return await handler(event, data)

dp.message.middleware(MainMiddleware())

# ============================================================
#  ГЛАВНОЕ МЕНЮ И КНОПКИ
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
    if message.chat.type == "private" and message.from_user.id != OWNER_ID:
        return await message.reply("❌ Извините, бот только для владельца.")
    me = await bot.get_me()
    if message.chat.type != "private":
        return await message.reply("✅ VOID Helper активен!\n/help — все команды.")
    await message.answer(
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        f"Я <b>VOID Helper</b> — бот для твоего чата.\n\n"
        f"🎮 Игры на монеты\n💼 Экономика\n❤️ RP действия\n🛡 Модерация\n⏰ Авто-закрытие\n\n"
        f"📋 /help — все команды",
        reply_markup=main_menu_kb(me.username)
    )

@dp.callback_query(F.data == "m_profile")
async def cb_profile(call: types.CallbackQuery):
    if call.message.chat.type == "private" and call.from_user.id != OWNER_ID:
        return await call.answer("❌ Только для владельца!", show_alert=True)
    uid = call.from_user.id
    coins, xp, warns, mult = get_user(uid)
    level = xp // 100
    await call.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"Имя: {user_link_with_nick(uid, call.message.chat.id, call.from_user.first_name)}\n"
        f"⭐ Уровень: <b>{level}</b>\n💰 Монеты: <b>{coins}</b>\n"
        f"📊 Опыт: <b>{xp}</b> / {(level+1)*100}\n⚠️ Варны: {warns}/3",
        reply_markup=back_kb()
    )
    await call.answer()

@dp.callback_query(F.data == "m_top")
async def cb_top(call: types.CallbackQuery):
    if call.message.chat.type == "private" and call.from_user.id != OWNER_ID:
        return await call.answer("❌ Только для владельца!", show_alert=True)
    rows = db("SELECT id, coins FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    lines = ["🏆 <b>Топ монет</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, coins) in enumerate(rows):
        m = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{m} {user_link_with_nick(uid, call.message.chat.id, '')} — {coins}💰")
    if not rows:
        lines.append("Пока никого")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_shop")
async def cb_shop(call: types.CallbackQuery):
    if call.message.chat.type == "private" and call.from_user.id != OWNER_ID:
        return await call.answer("❌ Только для владельца!", show_alert=True)
    await call.message.edit_text(
        "🛒 <b>Магазин</b>\n\n1️⃣ Множитель x2 — 500💰 (1 час)\n2️⃣ Сброс работы — 300💰\n\n/buy 1  /buy 2",
        reply_markup=back_kb()
    )
    await call.answer()

@dp.callback_query(F.data == "m_games")
async def cb_games(call: types.CallbackQuery):
    if call.message.chat.type == "private" and call.from_user.id != OWNER_ID:
        return await call.answer("❌ Только для владельца!", show_alert=True)
    await call.message.edit_text(
        "🎮 <b>Игры</b>\n\n"
        "/casino 100 — слоты\n/darts 100 — дартс\n/coinflip 50 — орёл/решка\n"
        "/guess 20 — угадай число\n/rps 15 — КНБ\n\n"
        "<b>Дуэли (ответом):</b>\n/dice, /basketball, /football, /bowling",
        reply_markup=back_kb()
    )
    await call.answer()

@dp.callback_query(F.data == "m_rp")
async def cb_rp(call: types.CallbackQuery):
    if call.message.chat.type == "private" and call.from_user.id != OWNER_ID:
        return await call.answer("❌ Только для владельца!", show_alert=True)
    await call.message.edit_text(
        "❤️ <b>RP ДЕЙСТВИЯ</b>\n\n/rp — список всех действий\n"
        "+обнять, +поцеловать, +прижаться, +взять_за_руку, +обнять_крепко, +пошептать\n"
        "+погладить_по_щеке, +посмотреть_в_глаза, +улыбнуться, +комплимент\n\n"
        "💍 Браки: +брак, +развод, +пара, +список браков, +отношения\n"
        "📛 Ники: +ник @user НовыйНик (доступно всем!)",
        reply_markup=back_kb()
    )
    await call.answer()

@dp.callback_query(F.data == "m_back")
async def cb_back(call: types.CallbackQuery):
    if call.message.chat.type == "private" and call.from_user.id != OWNER_ID:
        return await call.answer("❌ Только для владельца!", show_alert=True)
    me = await bot.get_me()
    await call.message.edit_text(
        f"👋 <b>Привет, {call.from_user.first_name}!</b>\n\nЯ <b>VOID Helper</b> — бот для твоего чата.",
        reply_markup=main_menu_kb(me.username)
    )
    await call.answer()

# ============================================================
#  КОМАНДА /help
# ============================================================
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.reply("""
📋 <b>VOID Helper — команды</b>

👤 <b>ПРОФИЛЬ</b>
/profile, /top

💼 <b>ЭКОНОМИКА</b>
/work, /daily, /shop

🎮 <b>ИГРЫ</b>
/casino, /darts, /coinflip, /guess, /rps
Дуэли: /dice, /basketball, /football, /bowling

❤️ <b>RP ДЕЙСТВИЯ</b>
/rp — список
+обнять, +поцеловать, +прижаться, +взять_за_руку
+обнять_крепко, +пошептать, +погладить_по_щеке
+посмотреть_в_глаза, +улыбнуться, +комплимент

💍 <b>БРАКИ</b>
+брак, +развод, +пара, +список браков, +отношения

📛 <b>НИКНЕЙМЫ (доступно всем!)</b>
+ник @user НовыйНик

🔒 <b>УПРАВЛЕНИЕ</b>
-чат, +чат, /setautoschedule

🛡 <b>МОДЕРАЦИЯ</b>
!бан, !разбан, !кик, !мут, !размут, !варн, !админ, +админ, -админ

⚙️ <b>НАСТРОЙКА</b>
/setwelcome, /testwelcome
""")

# ============================================================
#  ЭКОНОМИКА (СОКРАЩЕННО, НО ПОЛНОСТЬЮ РАБОТАЕТ)
# ============================================================
@dp.message(Command("profile"))
async def profile(message: types.Message):
    uid = message.from_user.id
    coins, xp, warns, mult = get_user(uid)
    level = xp // 100
    await message.reply(
        f"👤 <b>Профиль</b>\n\nИмя: {user_link_with_nick(uid, message.chat.id, message.from_user.first_name)}\n"
        f"⭐ Уровень: {level}\n💰 Монеты: {coins}\n📊 Опыт: {xp}\n⚠️ Варны: {warns}/3"
    )

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    rows = db("SELECT id, coins FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    if not rows:
        return await message.reply("🏆 Пока никого")
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Топ монет</b>"]
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
    jobs = [
        ("💻 Написал бота", 600, 1000), ("📦 Развёз посылки", 400, 700),
        ("🚗 Отвёз клиента", 500, 800), ("🎨 Дизайн лендинга", 450, 750),
        ("🔧 Починил сервер", 700, 1000), ("🎮 Стрим + донаты", 300, 600),
        ("📱 Продал айфон", 350, 650), ("🛒 Купил монеты", 200, 1200),
        ("🤖 Обучил нейронку", 550, 950), ("🎵 Продал биты", 400, 800),
    ]
    job, mn, mx = random.choice(jobs)
    pay = random.randint(mn, mx)
    xpg = random.randint(15, 35)
    add_coins(uid, pay)
    add_xp(uid, xpg)
    db("UPDATE users SET last_work=? WHERE id=?", (now, uid))
    await message.reply(f"⛏ {job}\n💰 +{pay}💰\n✨ +{xpg} XP")

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
    add_xp(uid, 50)
    db("UPDATE users SET last_daily=? WHERE id=?", (now, uid))
    await message.reply(f"🎁 Бонус! +{bonus}💰 +50 XP")

@dp.message(Command("shop"))
async def shop_cmd(message: types.Message):
    await message.reply("🛒 <b>Магазин</b>\n\n1️⃣ Множитель x2 — 500💰\n2️⃣ Сброс работы — 300💰\n\n/buy 1  /buy 2")

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("❌ Укажи номер: /buy 1")
    try:
        item = int(args[1])
    except:
        return await message.reply("❌ Некорректный номер")
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if item == 1:
        if coins < 500:
            return await message.reply(f"❌ Нужно 500💰, у тебя {coins}💰")
        add_coins(uid, -500)
        db("UPDATE users SET xp_multiplier=2.0 WHERE id=?", (uid,))
        asyncio.create_task(reset_multiplier(uid, 3600))
        await message.reply("✨ Множитель x2 активирован на 1 час!")
    elif item == 2:
        if coins < 300:
            return await message.reply(f"❌ Нужно 300💰, у тебя {coins}💰")
        add_coins(uid, -300)
        db("UPDATE users SET last_work=0 WHERE id=?", (uid,))
        await message.reply("⚡ Кулдаун работы сброшен!")
    else:
        await message.reply("❌ Неверный номер. Доступно: 1, 2")

async def reset_multiplier(uid, delay):
    await asyncio.sleep(delay)
    db("UPDATE users SET xp_multiplier=1.0 WHERE id=?", (uid,))

# ============================================================
#  ИГРЫ (СОЛО)
# ============================================================
async def check_bet(message, bet, min_bet=10):
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet < min_bet:
        await message.reply(f"❌ Мин. ставка: {min_bet} монет")
        return None
    if bet > coins:
        await message.reply(f"❌ Не хватает! У тебя {coins}💰")
        return None
    add_coins(uid, -bet)
    return uid

@dp.message(Command("casino"))
async def casino_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet:
        return await message.reply("🎰 Укажи ставку: /casino 100 или казино 100")
    uid = await check_bet(message, bet, 10)
    if not uid:
        return
    msg = await bot.send_dice(message.chat.id, emoji="🎰")
    await asyncio.sleep(DICE_WAIT["🎰"])
    v = msg.dice.value
    if v == 64:
        prize = bet * 10
        add_coins(uid, prize)
        add_xp(uid, 150)
        await message.reply(f"🎉 ДЖЕКПОТ! +{prize}💰 +150 XP")
    elif v >= 50:
        prize = bet * 4
        add_coins(uid, prize)
        add_xp(uid, 40)
        await message.reply(f"🎰 КРУПНО! +{prize}💰 +40 XP")
    elif v >= 30:
        prize = bet * 2
        add_coins(uid, prize)
        add_xp(uid, 15)
        await message.reply(f"🎰 ВЫИГРЫШ! +{prize}💰 +15 XP")
    elif v >= 15:
        add_coins(uid, bet)
        await message.reply(f"🎰 Возврат {bet}💰")
    else:
        await message.reply(f"😞 Проиграл {bet}💰")

@dp.message(Command("darts"))
async def darts_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet:
        return await message.reply("🎯 Укажи ставку: /darts 100 или дартс 100")
    uid = await check_bet(message, bet, 10)
    if not uid:
        return
    msg = await bot.send_dice(message.chat.id, emoji="🎯")
    await asyncio.sleep(DICE_WAIT["🎯"])
    v = msg.dice.value
    if v == 6:
        prize = bet * 5
        add_coins(uid, prize)
        add_xp(uid, 60)
        await message.reply(f"🎯 БУЛЛ-АЙ! +{prize}💰 +60 XP")
    elif v == 5:
        prize = bet * 3
        add_coins(uid, prize)
        add_xp(uid, 30)
        await message.reply(f"🎯 ОТЛИЧНО! +{prize}💰 +30 XP")
    elif v == 4:
        prize = bet * 2
        add_coins(uid, prize)
        add_xp(uid, 15)
        await message.reply(f"🎯 ХОРОШО! +{prize}💰 +15 XP")
    elif v == 3:
        add_coins(uid, bet)
        await message.reply(f"🎯 Попал! Возврат {bet}💰")
    else:
        await message.reply(f"😞 Мимо! -{bet}💰")

@dp.message(Command("coinflip"))
async def coinflip_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet:
        return await message.reply("🪙 Укажи ставку: /coinflip 50 или монетка 50")
    uid = await check_bet(message, bet, 10)
    if not uid:
        return
    result = random.choice(["орёл", "решка"])
    user_choice = random.choice(["орёл", "решка"])
    msg = await message.reply(f"🪙 Монетка летит...\n💰 Ставка: {bet}")
    await asyncio.sleep(2)
    if result == user_choice:
        win = bet * 2
        add_coins(uid, win)
        await msg.edit_text(f"🪙 {result}!\n🎉 Вы угадали! +{win}💰")
    else:
        await msg.edit_text(f"🪙 {result}!\n😞 Не угадал! -{bet}💰")

@dp.message(Command("guess"))
async def guess_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet:
        return await message.reply("🔢 Укажи ставку: /guess 20 или угадай 20")
    uid = await check_bet(message, bet, 10)
    if not uid:
        return
    number = random.randint(1, 10)
    await message.reply(f"🔢 Я загадал число 1-10\nНапиши число в ответ (10 сек)\n💰 Ставка: {bet}")
    try:
        answer = await bot.wait_for("message", timeout=10.0,
            check=lambda m: m.from_user.id == uid and m.text and m.text.isdigit() and
                           m.reply_to_message and m.reply_to_message.message_id == message.message_id)
        guess = int(answer.text)
        if guess == number:
            win = bet * 5
            add_coins(uid, win)
            await message.reply(f"🎉 Правильно! {number}\n+{win}💰")
        else:
            await message.reply(f"❌ Не угадал! Было {number}\n-{bet}💰")
    except:
        await message.reply(f"⏰ Время вышло! Было {number}\n-{bet}💰")

@dp.message(Command("rps"))
async def rps_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet:
        return await message.reply("✊ Укажи ставку: /rps 15 или кнб 15")
    uid = await check_bet(message, bet, 10)
    if not uid:
        return
    await message.reply("✊ Камень, ножницы или бумага?\nНапиши в ответ (15 сек)")
    try:
        answer = await bot.wait_for("message", timeout=15.0,
            check=lambda m: m.from_user.id == uid and m.text and m.text.lower() in ["камень", "ножницы", "бумага"] and
                           m.reply_to_message and m.reply_to_message.message_id == message.message_id)
        user = answer.text.lower()
        bot_choice = random.choice(["камень", "ножницы", "бумага"])
        if user == bot_choice:
            add_coins(uid, bet)
            await message.reply(f"🤝 Ничья! {bot_choice}\nВозврат {bet}💰")
        elif (user == "камень" and bot_choice == "ножницы") or \
             (user == "ножницы" and bot_choice == "бумага") or \
             (user == "бумага" and bot_choice == "камень"):
            win = bet * 2
            add_coins(uid, win)
            await message.reply(f"🎉 Победа! {user} > {bot_choice}\n+{win}💰")
        else:
            await message.reply(f"😞 Поражение! {bot_choice} > {user}\n-{bet}💰")
    except:
        await message.reply("⏰ Время вышло! Ставка возвращена")
        add_coins(uid, bet)

# ============================================================
#  ДУЭЛИ (С ПРИГЛАШЕНИЯМИ И АВТО-БРОСКАМИ)
# ============================================================
active_duels = {}
DUEL_GAMES = {
    "dice": {"emoji": "🎲", "name": "Кости"},
    "basketball": {"emoji": "🏀", "name": "Баскетбол"},
    "football": {"emoji": "⚽", "name": "Футбол"},
    "bowling": {"emoji": "🎳", "name": "Боулинг"},
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
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Дуэли доступны только в группах.")
    if not message.reply_to_message:
        return await message.reply("❌ Ответь на сообщение соперника командой!")
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
    _, _, game_type, challenger_id_str, chat_id_str = call.data.split("_")
    challenger_id = int(challenger_id_str)
    chat_id = int(chat_id_str)
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

@dp.callback_query(F.data.startswith("duel_decline_"))
async def duel_decline(call: types.CallbackQuery):
    _, _, game_type, challenger_id_str = call.data.split("_")
    challenger_id = int(challenger_id_str)
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
        f"🎲 Начинаем..."
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
        f"🆚 {user_link_with_nick(player1_id, chat_id, p1_name)} vs {user_link_with_nick(player2_id, chat_id, p2_name)}\n\n"
        f"🎲 {user_link_with_nick(player1_id, chat_id, p1_name)} выбросил: <b>{score1}</b>\n\n"
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
            f"🆚 {user_link_with_nick(player1_id, chat_id, p1_name)}: <b>{score1}</b>\n"
            f"{user_link_with_nick(player2_id, chat_id, p2_name)}: <b>{score2}</b>\n\n"
            f"🏆 <b>ПОБЕДИТЕЛЬ:</b> {user_link_with_nick(winner_id, chat_id, winner_name)}!\n\n"
            f"💰 +150 монет, ✨ +30 XP"
        )
    else:
        await msg.edit_text(
            f"{game['emoji']} <b>{game['name']}</b>\n\n"
            f"🆚 {user_link_with_nick(player1_id, chat_id, p1_name)}: <b>{score1}</b>\n"
            f"{user_link_with_nick(player2_id, chat_id, p2_name)}: <b>{score2}</b>\n\n"
            f"🤝 <b>НИЧЬЯ!</b>"
        )
    duel_key = f"{chat_id}_{player1_id}_{player2_id}"
    if duel_key in active_duels:
        del active_duels[duel_key]

# ============================================================
#  RP ДЕЙСТВИЯ
# ============================================================
RP_ACTIONS = {
    "обнять": ["🤗 обнял", "🤗 обняла", "🤗 обняли"],
    "поцеловать": ["😘 поцеловал", "😘 поцеловала", "😘 поцеловали"],
    "ударить": ["👊 ударил", "👊 ударила", "👊 ударили"],
    "погладить": ["🫳 погладил", "🫳 погладила", "🫳 погладили"],
    "кинуть_мяч": ["⚾ кинул мяч", "⚾ кинула мяч", "⚾ кинули мяч"],
    "подарить": ["🎁 подарил", "🎁 подарила", "🎁 подарили"],
    "угостить": ["🍪 угостил", "🍪 угостила", "🍪 угостили"],
    "пожалеть": ["🥺 пожалел", "🥺 пожалела", "🥺 пожалели"],
    "похвалить": ["👍 похвалил", "👍 похвалила", "👍 похвалили"],
    "подшутить": ["😜 подшутил", "😜 подшутила", "😜 подшутили"],
    "поздравить": ["🎉 поздравил", "🎉 поздравила", "🎉 поздравили"],
    "извиниться": ["🙏 извинился", "🙏 извинилась", "🙏 извинились"],
    "попросить_прощения": ["🙇 попросил прощения", "🙇 попросила прощения", "🙇 попросили прощения"],
    "спасти": ["🦸‍♂️ спас", "🦸‍♀️ спасла", "🦸 спасли"],
    "накормить": ["🍲 накормил", "🍲 накормила", "🍲 накормили"],
    "напоить": ["☕ напоил", "☕ напоила", "☕ напоили"],
    "расчесать": ["💇 расчесал", "💇 расчесала", "💇 расчесали"],
    "помассировать": ["💆 помассировал", "💆 помассировала", "💆 помассировали"],
    "подбодрить": ["💪 подбодрил", "💪 подбодрила", "💪 подбодрили"],
    "поддержать": ["🤝 поддержал", "🤝 поддержала", "🤝 поддержали"],
    "прижаться": ["💕 прижался", "💕 прижалась", "💕 прижались"],
    "взять_за_руку": ["💑 взял за руку", "💑 взяла за руку", "💑 взяли за руку"],
    "обнять_крепко": ["🤗 крепко обнял", "🤗 крепко обняла", "🤗 крепко обняли"],
    "пошептать": ["🤫 шепнул на ухо", "🤫 шепнула на ухо", "🤫 шепнули на ухо"],
    "погладить_по_щеке": ["🫳 погладил по щеке", "🫳 погладила по щеке", "🫳 погладили по щеке"],
    "посмотреть_в_глаза": ["👀 посмотрел в глаза", "👀 посмотрела в глаза", "👀 посмотрели в глаза"],
    "улыбнуться": ["😊 улыбнулся", "😊 улыбнулась", "😊 улыбнулись"],
    "комплимент": ["💝 сделал комплимент", "💝 сделала комплимент", "💝 сделали комплимент"],
}

@dp.message(Command("rp"))
async def rp_list_cmd(message: types.Message):
    actions = "\n".join([f"• +{k}" for k in RP_ACTIONS.keys()])
    await message.reply(f"🎭 <b>Доступные RP действия ({len(RP_ACTIONS)}):</b>\n\n{actions}\n\nИспользование: +обнять @user")

@dp.message(F.text.lower().startswith(tuple(f"+{k}" for k in RP_ACTIONS.keys())))
async def rp_action(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ RP действия доступны только в группах.")
    action = None
    for key in RP_ACTIONS.keys():
        if message.text.lower().startswith(f"+{key}"):
            action = key
            break
    if not action:
        return
    args = message.text[len(f"+{action}"):].strip()
    target_id, target_name = await resolve_target(message, args)
    if not target_id:
        return await message.reply(f"❌ Укажи @юзертег или ответь.\nПример: +{action} @user")
    if target_id == message.from_user.id:
        return await message.reply("❌ Нельзя выполнить действие над самим собой!")
    gender_row = db("SELECT gender FROM user_gender WHERE user_id=?", (message.from_user.id,), fetch=True)
    gender = gender_row[0][0] if gender_row else 0
    verb = RP_ACTIONS[action][0] if gender == 0 else RP_ACTIONS[action][1] if gender == 1 else RP_ACTIONS[action][2]
    await message.reply(
        f"{user_link_with_nick(message.from_user.id, message.chat.id, message.from_user.first_name)} "
        f"{verb} "
        f"{user_link_with_nick(target_id, message.chat.id, target_name)}!"
    )

# ============================================================
#  БРАКИ
# ============================================================
async def get_marriage_info(uid, chat_id):
    row = db("SELECT user1, user2, since FROM marriages WHERE chat_id=? AND (user1=? OR user2=?)", 
             (chat_id, uid, uid), fetch=True)
    if row:
        u1, u2, since = row[0]
        partner = u2 if u1 == uid else u1
        days = (int(time.time()) - since) // 86400
        return partner, days
    return None, None

@dp.message(F.text.lower().startswith(("+брак", "!брак", "-брак")))
async def marry_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    uid = message.from_user.id
    partner_id, _ = await get_marriage_info(uid, message.chat.id)
    if partner_id:
        return await message.reply("❌ Вы уже в браке! +развод чтобы развестись.")
    raw = message.text
    for prefix in ["+брак", "!брак", "-брак"]:
        if raw.lower().startswith(prefix):
            args = raw[len(prefix):].strip()
            break
    else:
        args = raw
    target_id, target_name = await resolve_target(message, args)
    if not target_id:
        return await message.reply("❌ Укажи @юзертег или ответь.")
    if target_id == uid:
        return await message.reply("❌ Нельзя жениться на себе!")
    partner_id, _ = await get_marriage_info(target_id, message.chat.id)
    if partner_id:
        return await message.reply("❌ Этот пользователь уже в браке!")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💍 Принять", callback_data=f"marry_accept_{uid}_{target_id}_{message.chat.id}"),
         InlineKeyboardButton(text="❌ Отказать", callback_data=f"marry_deny_{uid}_{target_id}")]
    ])
    await message.reply(
        f"💍 <b>ПРЕДЛОЖЕНИЕ БРАКА</b>\n\n"
        f"{user_link_with_nick(uid, message.chat.id, message.from_user.first_name)} предлагает брак "
        f"{user_link_with_nick(target_id, message.chat.id, target_name)}!\n\n❤️ Согласны?",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("marry_accept_"))
async def marry_accept(call: types.CallbackQuery):
    _, _, suitor_id, target_id, chat_id = call.data.split("_")
    suitor_id, target_id, chat_id = int(suitor_id), int(target_id), int(chat_id)
    if call.from_user.id != target_id:
        return await call.answer("Это предложение не вам!", show_alert=True)
    s_partner, _ = await get_marriage_info(suitor_id, chat_id)
    t_partner, _ = await get_marriage_info(target_id, chat_id)
    if s_partner or t_partner:
        return await call.message.edit_text("❌ Один из вас уже в браке!")
    now = int(time.time())
    db("INSERT INTO marriages (user1, user2, chat_id, since) VALUES (?,?,?,?)", 
       (suitor_id, target_id, chat_id, now))
    await call.message.edit_text(
        f"💍 <b>ПОЗДРАВЛЯЕМ С БРАКОМ!</b> 💍\n\n"
        f"{user_link_with_nick(suitor_id, chat_id, '')} и {user_link_with_nick(target_id, chat_id, '')} теперь муж и жена!\n\n❤️ Желаем счастья!"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("marry_deny_"))
async def marry_deny(call: types.CallbackQuery):
    _, _, suitor_id, target_id = call.data.split("_")
    suitor_id, target_id = int(suitor_id), int(target_id)
    if call.from_user.id != target_id:
        return await call.answer("Это предложение не вам!", show_alert=True)
    await call.message.edit_text(
        f"❌ <b>ОТКАЗ В БРАКЕ</b>\n\n"
        f"{user_link_with_nick(target_id, call.message.chat.id, '')} отказал(а) {user_link_with_nick(suitor_id, call.message.chat.id, '')}."
    )
    await call.answer()

@dp.message(F.text.lower().startswith(("+развод", "!развод", "-развод")))
async def divorce_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    uid = message.from_user.id
    partner, days = await get_marriage_info(uid, message.chat.id)
    if not partner:
        return await message.reply("❌ Вы не в браке!")
    db("DELETE FROM marriages WHERE chat_id=? AND (user1=? OR user2=?)", (message.chat.id, uid, uid))
    await message.reply(f"💔 <b>РАЗВОД</b>\n\n{user_link_with_nick(uid, message.chat.id, '')} и {user_link_with_nick(partner, message.chat.id, '')} развелись.\n📅 Были вместе {days} дней.")

@dp.message(F.text.lower().startswith(("+пара", "!пара", "-пара")))
async def couple_info(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    uid = message.from_user.id
    partner, days = await get_marriage_info(uid, message.chat.id)
    if not partner:
        return await message.reply("💔 Вы не в браке.\n+брак @user чтобы пожениться.")
    await message.reply(
        f"💑 <b>ВАША ПАРА</b>\n\n"
        f"{user_link_with_nick(uid, message.chat.id, '')} 💕 {user_link_with_nick(partner, message.chat.id, '')}\n"
        f"📅 Вместе: <b>{days}</b> дней"
    )

@dp.message(F.text.lower().startswith(("+список браков", "!список браков", "-список браков")))
async def marriages_list(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    rows = db("SELECT user1, user2, since FROM marriages WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not rows:
        return await message.reply("📋 В этом чате пока нет браков.")
    lines = ["📋 <b>СПИСОК БРАКОВ</b>"]
    for u1, u2, since in rows:
        days = (int(time.time()) - since) // 86400
        lines.append(f"💑 {user_link_with_nick(u1, message.chat.id, '')} + {user_link_with_nick(u2, message.chat.id, '')} — {days} дн.")
    await message.reply("\n".join(lines))

@dp.message(F.text.lower().startswith(("+отношения", "!отношения", "-отношения")))
async def relationship_status(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    uid = message.from_user.id
    partner, days = await get_marriage_info(uid, message.chat.id)
    if partner:
        await message.reply(f"❤️ Вы в браке с {user_link_with_nick(partner, message.chat.id, '')} ({days} дней)")
    else:
        await message.reply("💔 Вы холост/холоста.\n+брак @user чтобы найти пару!")

# ============================================================
#  НИКНЕЙМЫ (ДОСТУПНО ВСЕМ)
# ============================================================
@dp.message(F.text.lower().startswith(("+ник", "!ник")))
async def set_nickname(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    raw = message.text
    for prefix in ["+ник", "!ник"]:
        if raw.lower().startswith(prefix):
            args = raw[len(prefix):].strip()
            break
    else:
        args = raw
    if not args:
        return await message.reply("📛 Пример: +ник @user НовыйНик")
    target_id = None
    target_name = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name
        words = args.split()
        nickname = " ".join([w for w in words if not w.startswith("@")])
    else:
        words = args.split()
        target = None
        nickname_parts = []
        for w in words:
            if w.startswith("@") and not target:
                target = w
            else:
                nickname_parts.append(w)
        nickname = " ".join(nickname_parts)
        if target:
            uname = target[1:].lower()
            r = db("SELECT user_id, name FROM usernames WHERE username=?", (uname,), fetch=True)
            if r:
                target_id = r[0][0]
                target_name = r[0][1]
    if not target_id:
        return await message.reply("❌ Не удалось определить пользователя.")
    if not nickname:
        return await message.reply("❌ Укажи ник!")
    if target_id != message.from_user.id and not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Ты можешь изменить ник только себе! Администраторы могут менять ники другим.")
    db("INSERT OR REPLACE INTO user_nicknames (user_id, chat_id, nickname) VALUES (?,?,?)",
       (target_id, message.chat.id, nickname))
    await message.reply(f"✅ Ник изменён! {user_link_with_nick(target_id, message.chat.id, target_name)} теперь <b>{nickname}</b>")

# ============================================================
#  КОМАНДА !АДМИН (С ПОДТВЕРЖДЕНИЕМ И КНОПКАМИ)
# ============================================================
@dp.message(F.text.lower().startswith("!админ"))
async def give_admin_with_confirm(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    try:
        caller = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if caller.status != "creator" and message.from_user.id != OWNER_ID:
            return await message.reply("❌ Выдавать права может только создатель группы.")
    except:
        pass
    args = message.text[6:].strip()
    uid, name = await resolve_target(message, args)
    if not uid:
        return await message.reply("❌ Укажите @юзертег или ответьте на сообщение.")
    try:
        member = await bot.get_chat_member(message.chat.id, uid)
        if member.status in ("administrator", "creator"):
            return await message.reply(f"❌ {user_link_with_nick(uid, message.chat.id, name)} уже администратор.")
    except:
        pass
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Назначить", callback_data=f"confirm_admin_{uid}_{message.chat.id}"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin")]
    ])
    await message.reply(
        f"⚠️ Вы собираетесь назначить {user_link_with_nick(uid, message.chat.id, name)} администратором.\n"
        f"Подтвердите действие:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("confirm_admin_"))
async def confirm_admin(call: types.CallbackQuery):
    _, _, uid_str, chat_id_str = call.data.split("_")
    uid = int(uid_str)
    chat_id = int(chat_id_str)
    try:
        caller = await bot.get_chat_member(chat_id, call.from_user.id)
        if caller.status != "creator" and call.from_user.id != OWNER_ID:
            return await call.answer("❌ Только создатель может подтвердить!", show_alert=True)
    except:
        pass
    try:
        await bot.promote_chat_member(
            chat_id, uid,
            can_manage_chat=True,
            can_delete_messages=True,
            can_restrict_members=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_change_info=True,
            can_promote_members=False
        )
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка: {e}")
        return
    name = (await bot.get_chat_member(chat_id, uid)).user.first_name
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔧 Изменить права", callback_data=f"edit_admin_{uid}_{chat_id}"),
         InlineKeyboardButton(text="🔻 Снять админку", callback_data=f"remove_admin_{uid}_{chat_id}")]
    ])
    await call.message.edit_text(
        f"✅ {user_link_with_nick(uid, chat_id, name)} назначен администратором!\n\n"
        f"Права: управление чатом, удаление сообщений, блокировка, приглашения, закреп, изменение информации.\n"
        f"Для изменения прав используйте кнопки ниже.",
        reply_markup=keyboard
    )
    await call.answer()

@dp.callback_query(F.data.startswith("edit_admin_"))
async def edit_admin_permissions(call: types.CallbackQuery):
    _, _, uid_str, chat_id_str = call.data.split("_")
    uid = int(uid_str)
    chat_id = int(chat_id_str)
    try:
        caller = await bot.get_chat_member(chat_id, call.from_user.id)
        if caller.status != "creator" and call.from_user.id != OWNER_ID:
            return await call.answer("❌ Только создатель!", show_alert=True)
    except:
        pass
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалять сообщения", callback_data=f"perm_del_{uid}_{chat_id}"),
         InlineKeyboardButton(text="🔨 Блокировать участников", callback_data=f"perm_ban_{uid}_{chat_id}")],
        [InlineKeyboardButton(text="📌 Закреплять", callback_data=f"perm_pin_{uid}_{chat_id}"),
         InlineKeyboardButton(text="ℹ️ Изменять инфо", callback_data=f"perm_info_{uid}_{chat_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_admin_{uid}_{chat_id}")]
    ])
    await call.message.edit_text(
        f"Настройка прав для {user_link_with_nick(uid, chat_id, 'пользователя')}:\n"
        f"Выберите действие.",
        reply_markup=keyboard
    )
    await call.answer()

@dp.callback_query(F.data.startswith("perm_del_"))
async def toggle_perm_delete(call: types.CallbackQuery):
    await call.answer("Функция в разработке (можно переключать права)", show_alert=True)

@dp.callback_query(F.data.startswith("perm_ban_"))
async def toggle_perm_ban(call: types.CallbackQuery):
    await call.answer("Функция в разработке", show_alert=True)

@dp.callback_query(F.data.startswith("perm_pin_"))
async def toggle_perm_pin(call: types.CallbackQuery):
    await call.answer("Функция в разработке", show_alert=True)

@dp.callback_query(F.data.startswith("perm_info_"))
async def toggle_perm_info(call: types.CallbackQuery):
    await call.answer("Функция в разработке", show_alert=True)

@dp.callback_query(F.data.startswith("back_admin_"))
async def back_admin(call: types.CallbackQuery):
    _, _, uid_str, chat_id_str = call.data.split("_")
    uid = int(uid_str)
    chat_id = int(chat_id_str)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔧 Изменить права", callback_data=f"edit_admin_{uid}_{chat_id}"),
         InlineKeyboardButton(text="🔻 Снять админку", callback_data=f"remove_admin_{uid}_{chat_id}")]
    ])
    await call.message.edit_text(
        f"Управление правами для {user_link_with_nick(uid, chat_id, 'администратора')}:",
        reply_markup=keyboard
    )
    await call.answer()

@dp.callback_query(F.data.startswith("remove_admin_"))
async def remove_admin_from_callback(call: types.CallbackQuery):
    _, _, uid_str, chat_id_str = call.data.split("_")
    uid = int(uid_str)
    chat_id = int(chat_id_str)
    try:
        caller = await bot.get_chat_member(chat_id, call.from_user.id)
        if caller.status != "creator" and call.from_user.id != OWNER_ID:
            return await call.answer("❌ Только создатель!", show_alert=True)
    except:
        pass
    try:
        await bot.promote_chat_member(
            chat_id, uid,
            can_manage_chat=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_invite_users=False,
            can_pin_messages=False,
            can_change_info=False,
            can_promote_members=False
        )
        await call.message.edit_text(f"🔻 Администратор {user_link_with_nick(uid, chat_id, '')} лишён прав.")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка: {e}")

@dp.callback_query(F.data.startswith("cancel_admin"))
async def cancel_admin(call: types.CallbackQuery):
    await call.message.edit_text("❌ Действие отменено.")
    await call.answer()

# ============================================================
#  УПРАВЛЕНИЕ ЧАТОМ (-чат / +чат)
# ============================================================
@dp.message(Command("setautoschedule"))
async def set_auto_schedule(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Только для админов!")
    args = message.text.replace("/setautoschedule", "").strip().split()
    if len(args) < 2:
        return await message.reply("⏰ /setautoschedule 23:00 09:00\n\nЧтобы отключить: /setautoschedule off")
    if args[0].lower() == "off":
        db("DELETE FROM chat_settings WHERE chat_id=?", (message.chat.id,))
        return await message.reply("✅ Авто-закрытие отключено.")
    close_time, open_time = args[0], args[1]
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', close_time):
        return await message.reply("❌ Неверный формат времени закрытия")
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', open_time):
        return await message.reply("❌ Неверный формат времени открытия")
    await set_chat_schedule(message.chat.id, close_time, open_time)
    await message.reply(f"✅ Расписание: закрытие в {close_time}, открытие в {open_time}")

@dp.message(F.text.lower().startswith(("-чат", "!чат")))
async def close_chat_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Только для админов!")
    chat_id = message.chat.id
    if await is_chat_closed(chat_id):
        return await message.reply("🔒 Чат уже закрыт!")
    await close_chat(chat_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Открыть чат", callback_data=f"open_chat_{chat_id}")]
    ])
    await message.reply("🔒 <b>ЧАТ ЗАКРЫТ</b>\n\nПисать могут только администраторы.", reply_markup=keyboard)

@dp.message(F.text.lower().startswith(("+чат", "!открытьчат")))
async def open_chat_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Только для админов!")
    chat_id = message.chat.id
    if not await is_chat_closed(chat_id):
        return await message.reply("🔓 Чат уже открыт!")
    await open_chat(chat_id)
    async for msg in bot.get_chat_history(chat_id, limit=10):
        if msg.from_user and msg.from_user.id == bot.id and msg.reply_markup:
            try:
                await msg.delete()
            except:
                pass
            break
    await message.reply("🔓 <b>ЧАТ ОТКРЫТ</b>\n\nВсе пользователи могут писать.")

@dp.callback_query(F.data.startswith("open_chat_"))
async def open_chat_callback(call: types.CallbackQuery):
    chat_id = int(call.data.split("_")[2])
    if not await is_admin(chat_id, call.from_user.id):
        return await call.answer("❌ Только для админов!", show_alert=True)
    if not await is_chat_closed(chat_id):
        return await call.answer("Чат уже открыт!", show_alert=True)
    await open_chat(chat_id)
    try:
        await call.message.delete()
    except:
        pass
    await call.message.answer("🔓 <b>ЧАТ ОТКРЫТ</b>\n\nВсе пользователи могут писать.")
    await call.answer()

# ============================================================
#  АВТО-РАСПИСАНИЕ (МСК)
# ============================================================
sent_notifications = {}

async def send_close_warning(chat_id, seconds_left):
    if seconds_left >= 3600:
        hours = seconds_left // 3600
        time_str = f"{hours} час" + ("а" if hours % 10 == 1 and hours % 100 != 11 else "ов" if hours > 4 else "а")
    elif seconds_left >= 60:
        minutes = seconds_left // 60
        time_str = f"{minutes} минут" + ("а" if minutes % 10 == 1 and minutes % 100 != 11 else "ы" if minutes % 10 in [2,3,4] and minutes % 100 not in [12,13,14] else "")
    else:
        time_str = f"{seconds_left} секунд"
    await bot.send_message(chat_id, f"⚠️ <b>ВНИМАНИЕ!</b>\n\nЧат будет закрыт через <b>{time_str}</b>!")

async def check_and_apply_schedule(chat_id):
    close_time, open_time = await get_chat_schedule(chat_id)
    if not close_time or not open_time:
        return
    now = datetime.now(timezone(timedelta(hours=3)))
    current_time = now.strftime("%H:%M")
    if current_time == close_time:
        key = f"close_{chat_id}_{now.strftime('%Y%m%d')}"
        if key not in sent_notifications:
            sent_notifications[key] = True
            if not await is_chat_closed(chat_id):
                await close_chat(chat_id)
                await bot.send_message(chat_id, "🔒 Чат автоматически закрыт по расписанию.")
    if current_time == open_time:
        key = f"open_{chat_id}_{now.strftime('%Y%m%d')}"
        if key not in sent_notifications:
            sent_notifications[key] = True
            if await is_chat_closed(chat_id):
                await open_chat(chat_id)
                await bot.send_message(chat_id, "🔓 Чат автоматически открыт по расписанию.")
    if not await is_chat_closed(chat_id):
        try:
            close_hour, close_minute = map(int, close_time.split(":"))
            close_today = now.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)
            if close_today < now:
                close_today += timedelta(days=1)
            seconds = (close_today - now).total_seconds()
            warning_times = [3600, 1800, 900, 600, 300, 60, 30]
            for wt in warning_times:
                if wt <= seconds < wt + 10:
                    key = f"warn_{chat_id}_{now.strftime('%Y%m%d')}_{wt}"
                    if key not in sent_notifications:
                        sent_notifications[key] = True
                        await send_close_warning(chat_id, wt)
                        break
        except:
            pass

async def scheduler_loop():
    while True:
        try:
            chats = db("SELECT chat_id FROM chat_settings WHERE close_time IS NOT NULL AND open_time IS NOT NULL", fetch=True)
            for chat in chats:
                await check_and_apply_schedule(chat[0])
        except:
            pass
        await asyncio.sleep(30)

# ============================================================
#  ПРИВЕТСТВИЯ (АВТООПРЕДЕЛЕНИЕ ПОЛА)
# ============================================================
@dp.my_chat_member()
async def on_bot_added(update: ChatMemberUpdated):
    old, new = update.old_chat_member.status, update.new_chat_member.status
    if old in ('left','kicked') and new in ('member','administrator'):
        if update.chat.type in ('group','supergroup'):
            await bot.send_message(update.chat.id, "👋 VOID Helper здесь!\n/help — все команды.")

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    chat_id = message.chat.id
    row = db("SELECT welcome_text FROM group_welcome WHERE chat_id=?", (chat_id,), fetch=True)
    template = row[0][0] if row else "👋 Добро пожаловать, {упоминание}!\nТы вош{ла|ёл|ли} в наш чат."
    for member in message.new_chat_members:
        if member.id == bot.id:
            continue
        gender = detect_gender_by_name(member.first_name)
        if gender == 2:
            gender = 0
        existing = db("SELECT gender FROM user_gender WHERE user_id=?", (member.id,), fetch=True)
        if not existing:
            db("INSERT OR REPLACE INTO user_gender (user_id, gender) VALUES (?,?)", (member.id, gender))
        else:
            gender = existing[0][0]
        name = member.first_name
        mention = user_link_with_nick(member.id, chat_id, name)
        verb_suffix = get_gender_verb_suffix(gender)
        text = process_welcome_template(template, name, mention, verb_suffix)
        await message.answer(text)

@dp.message(Command("testwelcome"))
async def test_welcome(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Только для админов!")
    row = db("SELECT welcome_text FROM group_welcome WHERE chat_id=?", (message.chat.id,), fetch=True)
    template = row[0][0] if row else "👋 Добро пожаловать, {упоминание}!\nТы вош{ла|ёл|ли} в наш чат."
    gender_row = db("SELECT gender FROM user_gender WHERE user_id=?", (message.from_user.id,), fetch=True)
    gender = gender_row[0][0] if gender_row else 0
    name = message.from_user.first_name
    mention = user_link_with_nick(message.from_user.id, message.chat.id, name)
    verb_suffix = get_gender_verb_suffix(gender)
    text = process_welcome_template(template, name, mention, verb_suffix)
    await message.reply(f"🔍 <b>Тест приветствия:</b>\n\n{text}")

@dp.message(Command("setwelcome"))
async def set_welcome(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("❌ Только в группах.")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Только для админов!")
    text = message.text.replace("/setwelcome", "").strip()
    if not text:
        return await message.reply("📝 /setwelcome текст\n\nПлейсхолдеры:\n{имя} или {name}\n{упоминание} или {mention}\nвош{ла|ёл|ли}")
    db("INSERT OR REPLACE INTO group_welcome (chat_id, welcome_text) VALUES (?,?)", (message.chat.id, text))
    await message.reply("✅ Приветствие сохранено!\n/testwelcome для проверки.")

# ============================================================
#  МОДЕРАЦИЯ (ОСТАЛЬНЫЕ КОМАНДЫ)
# ============================================================
async def mod_guard(message):
    if message.chat.type not in ("group", "supergroup"):
        return False
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Только для админов")
        return False
    return True

@dp.message(F.text.lower().startswith(("!мут", "-мут")))
async def mute_cmd(message: types.Message):
    if not await mod_guard(message):
        return
    raw = message.text
    args = raw[4:].strip() if raw.startswith("!мут") else raw[4:].strip()
    dur_match = re.search(r'(\d+)(?:м|мин|ч|д)', args)
    dur_str = dur_match.group(0) if dur_match else "5м"
    user_part = re.sub(r'\d+(?:м|мин|ч|д)', '', args).strip()
    uid, name = await resolve_target(message, user_part)
    if not uid:
        return await message.reply("❌ Укажи @юзертег или ответь")
    if await is_admin(message.chat.id, uid):
        return await message.reply("❌ Нельзя замутить админа")
    sec = parse_duration(dur_str)
    until = int(time.time()) + sec
    db("INSERT OR REPLACE INTO muted (user_id, chat_id, until) VALUES (?,?,?)", (uid, message.chat.id, until))
    try:
        await bot.restrict_chat_member(message.chat.id, uid, permissions=ChatPermissions(can_send_messages=False), until_date=datetime.fromtimestamp(until, tz=timezone.utc))
        await message.reply(f"🔇 {user_link_with_nick(uid, message.chat.id, name)} замучен на {fmt_dur(sec)}")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().startswith(("!размут", "-размут")))
async def unmute_cmd(message: types.Message):
    if not await mod_guard(message):
        return
    args = message.text[7:].strip() if message.text.startswith("!размут") else message.text[7:].strip()
    uid, name = await resolve_target(message, args)
    if not uid:
        return await message.reply("❌ Укажи @юзертег или ответь")
    db("DELETE FROM muted WHERE user_id=? AND chat_id=?", (uid, message.chat.id))
    try:
        await bot.restrict_chat_member(message.chat.id, uid, permissions=ChatPermissions(
            can_send_messages=True, can_send_media_messages=True, can_send_polls=True,
            can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True))
        await message.reply(f"✅ {user_link_with_nick(uid, message.chat.id, name)} размучен")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().startswith(("!бан", "-бан")))
async def ban_cmd(message: types.Message):
    if not await mod_guard(message):
        return
    args = message.text[4:].strip() if message.text.startswith("!бан") else message.text[4:].strip()
    uid, name = await resolve_target(message, args)
    if not uid:
        return await message.reply("❌ Укажи @юзертег или ответь")
    if await is_admin(message.chat.id, uid):
        return await message.reply("❌ Нельзя забанить админа")
    db("INSERT OR IGNORE INTO banned (user_id, chat_id) VALUES (?,?)", (uid, message.chat.id))
    try:
        await bot.ban_chat_member(message.chat.id, uid)
        await message.reply(f"🚫 {user_link_with_nick(uid, message.chat.id, name)} забанен")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().startswith(("!разбан", "-разбан")))
async def unban_cmd(message: types.Message):
    if not await mod_guard(message):
        return
    args = message.text[7:].strip() if message.text.startswith("!разбан") else message.text[7:].strip()
    uid, name = await resolve_target(message, args)
    if not uid:
        return await message.reply("❌ Укажи @юзертег или ответь")
    db("DELETE FROM banned WHERE user_id=? AND chat_id=?", (uid, message.chat.id))
    try:
        await bot.unban_chat_member(message.chat.id, uid)
        await message.reply(f"✅ {user_link_with_nick(uid, message.chat.id, name)} разбанен")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().startswith(("!кик", "-кик")))
async def kick_cmd(message: types.Message):
    if not await mod_guard(message):
        return
    args = message.text[4:].strip() if message.text.startswith("!кик") else message.text[4:].strip()
    uid, name = await resolve_target(message, args)
    if not uid:
        return await message.reply("❌ Укажи @юзертег или ответь")
    if await is_admin(message.chat.id, uid):
        return await message.reply("❌ Нельзя кикнуть админа")
    try:
        await bot.ban_chat_member(message.chat.id, uid)
        await asyncio.sleep(0.5)
        await bot.unban_chat_member(message.chat.id, uid)
        await message.reply(f"👢 {user_link_with_nick(uid, message.chat.id, name)} выгнан")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().startswith(("!варн", "-варн")))
async def warn_cmd(message: types.Message):
    if not await mod_guard(message):
        return
    args = message.text[5:].strip() if message.text.startswith("!варн") else message.text[5:].strip()
    uid, name = await resolve_target(message, args)
    if not uid:
        return await message.reply("❌ Укажи @юзертег или ответь")
    reason = args.strip() or "нарушение"
    db("UPDATE users SET warns=warns+1 WHERE id=?", (uid,))
    warns = db("SELECT warns FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    await message.reply(f"⚠️ {user_link_with_nick(uid, message.chat.id, name)} предупреждение!\nПричина: {reason}\nВарнов: {warns}/3")
    if warns >= 3:
        until = int(time.time()) + 3600
        db("INSERT OR REPLACE INTO muted (user_id, chat_id, until) VALUES (?,?,?)", (uid, message.chat.id, until))
        try:
            await bot.restrict_chat_member(message.chat.id, uid, permissions=ChatPermissions(can_send_messages=False), until_date=datetime.fromtimestamp(until, tz=timezone.utc))
            await message.reply(f"🔇 {user_link_with_nick(uid, message.chat.id, name)} получил 3 варна и замучен на 1 час")
        except:
            pass
        db("UPDATE users SET warns=0 WHERE id=?", (uid,))

@dp.message(F.text.lower().startswith(("+админ", "!админ")))  # Обратите внимание, !админ уже есть, но оставим и +админ как альтернативу
async def give_admin_alt(message: types.Message):
    # Дублирующий обработчик, можно оставить для совместимости, но уже есть !админ
    pass

@dp.message(F.text.lower().startswith(("-админ", "!снятьадмин")))
async def remove_admin_cmd(message: types.Message):
    if not await mod_guard(message):
        return
    args = message.text[6:].strip() if message.text.startswith("-админ") else message.text[9:].strip()
    uid, name = await resolve_target(message, args)
    if not uid:
        return await message.reply("❌ Укажи @юзертег или ответь")
    try:
        await bot.promote_chat_member(message.chat.id, uid,
            can_manage_chat=False, can_delete_messages=False, can_restrict_members=False,
            can_invite_users=False, can_pin_messages=False, can_change_info=False)
        await message.reply(f"🔻 {user_link_with_nick(uid, message.chat.id, name)} лишён прав админа")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# ============================================================
#  РУССКИЕ КОМАНДЫ (АЛИАСЫ)
# ============================================================
@dp.message(F.text)
async def text_aliases(message: types.Message):
    if not message.text:
        return
    text = message.text.strip().lower()
    if text == "профиль":
        return await profile(message)
    if text == "топ":
        return await top_cmd(message)
    if text == "работа":
        return await work(message)
    if text in ["бонус", "ежедневный"]:
        return await daily(message)
    if text == "магазин":
        return await shop_cmd(message)
    if text.startswith("казино"):
        bet = extract_bet(text)
        if bet:
            message.text = f"/casino {bet}"
            return await casino_cmd(message)
        return await message.reply("🎰 Укажи ставку! Пример: казино 100")
    if text.startswith("дартс"):
        bet = extract_bet(text)
        if bet:
            message.text = f"/darts {bet}"
            return await darts_cmd(message)
        return await message.reply("🎯 Укажи ставку! Пример: дартс 50")
    if text.startswith("монетка"):
        bet = extract_bet(text)
        if bet:
            message.text = f"/coinflip {bet}"
            return await coinflip_cmd(message)
        return await message.reply("🪙 Укажи ставку! Пример: монетка 30")
    if text.startswith("угадай"):
        bet = extract_bet(text)
        if bet:
            message.text = f"/guess {bet}"
            return await guess_cmd(message)
        return await message.reply("🔢 Укажи ставку! Пример: угадай 20")
    if text.startswith("кнб") or text.startswith("камень"):
        bet = extract_bet(text)
        if bet:
            message.text = f"/rps {bet}"
            return await rps_cmd(message)
        return await message.reply("✊ Укажи ставку! Пример: кнб 15")
    if text == "кости":
        return await cmd_dice(message)
    if text == "баскетбол":
        return await cmd_basketball(message)
    if text == "футбол":
        return await cmd_football(message)
    if text == "боулинг":
        return await cmd_bowling(message)

# ============================================================
#  ЗАПУСК
# ============================================================
async def apply_schedule_on_startup():
    chats = db("SELECT chat_id FROM chat_settings WHERE close_time IS NOT NULL AND open_time IS NOT NULL", fetch=True)
    for chat in chats:
        await check_and_apply_schedule(chat[0])

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
    me = await bot.get_me()
    print(f"✅ @{me.username} запущен!")
    await apply_schedule_on_startup()
    asyncio.create_task(scheduler_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
