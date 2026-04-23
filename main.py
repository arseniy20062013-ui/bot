# ============================================================
#  VOID HELPER BOT — v3 (ФИКС RIGHT_FORBIDDEN)
# ============================================================
# ИСПРАВЛЕНИЯ v3:
# 1. RIGHT_FORBIDDEN — бот проверяет собственные права перед выдачей
# 2. Клавиатура точно по скриншоту
# 3. ap_toggle использует | как разделитель (фикс can_delete/can_restrict)
# 4. !админ работает через ответ на сообщение
# 5. Авто-варн → только в личку нарушителю
# 6. Лог показывает правильного нарушителя
# ============================================================

import asyncio
import sqlite3
import logging
import time
import random
import re
import warnings
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatPermissions,
    BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

warnings.filterwarnings('ignore')

# ============================================================
#  НАСТРОЙКИ
# ============================================================
TOKEN = '8203364413:AAHBW_Aek57yZvvSf5JzrYElxLOCky_vnEY'
OWNER_ID = 7173827114
DB_NAME = 'void_final.db'
LOG_CHANNEL = '@void_official_chat'
LOG_MESSAGE_ID = 19010

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

DICE_WAIT = {"🎲": 2, "🎯": 3, "🏀": 4, "⚽": 4, "🎳": 4, "🎰": 4}

# ============================================================
#  КОМАНДЫ МЕНЮ
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
    BotCommand(command="moderation",      description="⚙️ Автомодерация on/off"),
    BotCommand(command="rp",              description="🎭 Список RP действий"),
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
    welcome_text TEXT DEFAULT '👋 Добро пожаловать, {упоминание}!\nТы вош{ла|ёл|ли} в наш чат.'
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
db('''CREATE TABLE IF NOT EXISTS admin_permissions (
    user_id INTEGER,
    chat_id INTEGER,
    can_promote          BOOLEAN DEFAULT 0,
    can_change_info      BOOLEAN DEFAULT 1,
    can_delete           BOOLEAN DEFAULT 1,
    can_restrict         BOOLEAN DEFAULT 1,
    can_invite           BOOLEAN DEFAULT 1,
    can_pin              BOOLEAN DEFAULT 1,
    can_video_chats      BOOLEAN DEFAULT 0,
    is_anonymous         BOOLEAN DEFAULT 0,
    can_post_stories     BOOLEAN DEFAULT 0,
    can_manage_topics    BOOLEAN DEFAULT 1,
    PRIMARY KEY(user_id, chat_id)
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
#  ПРАВИЛА VOID
# ============================================================
PUNISHMENT_RULES = {
    '18plus':             {'rule': '1.1. 18+ контент',              'warn_days': 30,    'mute_hours': 4},
    'insult':             {'rule': '1.2. Оскорбления',              'warn_days': 30,    'mute_hours': 8},
    'conflict':           {'rule': '1.3. Споры и конфликты',        'warn_days': 30,    'mute_hours': 2},
    'spam':               {'rule': '1.4. Нежелательные сообщения',  'warn_days': 30,    'mute_hours': 4},
    'mislead':            {'rule': '1.5. Ввод в заблуждение',       'warn_days': 30,    'mute_hours': 4},
    'admin_beg':          {'rule': '1.6. Выпрашивание админки',     'warn_days': 36500, 'mute_hours': 0},
    'admin_slander':      {'rule': '1.7. Клевета на админов',       'warn_days': 30,    'mute_hours': 24},
    'ideas_only':         {'rule': '3.1. Только идеи',              'warn_days': 3,     'mute_hours': 1},
    'creative_18plus':    {'rule': '4.1. Запрещённый контент',      'warn_days': 30,    'mute_hours': 4},
    'creative_discussion':{'rule': '4.2. Обсуждение',               'warn_days': 7,     'mute_hours': 2},
    'creative_ad':        {'rule': '4.3. Реклама',                  'warn_days': 30,    'mute_hours': 6},
}

BAD_WORDS = {
    '18plus': ['порно','секс','голый','голая','эротика','интим','пенис','влагалище','оральный','минет','куни','трах','ебля','дрочить','мастурбация','член','вагина','грудь','сиськи','попка','задница','жопа','хуй','пизда','сексуальный','сексуальная','возбуждает','оргазм','кончить','кончаю','расчленёнка','расчлененка','насилие','убийство','смерть','труп','кровь','жестокость','пытки','избиение','изнасилование','убийца','суицид','самоубийство','повеситься','зарезать','застрелить'],
    'insult': ['тупой','дебил','идиот','кретин','лох','олень','баран','овца','дурак','глупый','урод','чмо','шлюха','проститутка','пидор','гандон','хуесос','долбоеб','уебок','ебанутый','хуйло','сучка','блядина','мудак','сука','даун','аутист','шизофреник','псих','больной','дегенерат','ничтожество','отброс','мусор','грязь','скотина','тварь','мразь','убогий','жалкий','никчёмный','бесполезный','тупица','бездарь'],
    'conflict': ['политика','путин','зеленский','трамп','байден','выборы','президент','национальность','расизм','нацист','фашист','раса','негр','черный','белый','война','войска','армия','всу','сво','мобилизация','фронт','оккупация','религия','церковь','ислам','христианство','иудаизм','буддизм','атеист','гендер','феминизм','лгбт','гей','лесбиянка','бисексуал','трансгендер','рабство','рабы','рабовладелец','колонизация','наркотики','наркота','кокаин','героин','метамфетамин','спайс','соль','наркоман','доза','передоз'],
    'spam': [r'http[s]?://',r'www\.',r'\.ru\b',r'\.com\b',r'\.org\b',r'\.net\b',r't\.me/',r'telegram\.me',r'vk\.com',r'youtube\.',r'instagram\.',r'tiktok\.',r'discord\.gg',r'whatsapp\.',r'viber\.'],
    'mislead': ['выдаю себя за','я админ','я модератор','я владелец','ложная информация','фейк','обманул','вру','враньё'],
    'admin_beg': ['дай админку','сделай админом','хочу админку','назначь админом','дайте админку','сделайте админом','возьми в админы'],
    'admin_slander': ['админ плохой','модеры тупые','администрация дураки','модерация говно','админ несправедливый','модер злоупотребляет','клевета на админов'],
    'ideas_only': ['обсуждение','поговорить','вопрос','ответ','привет','как дела'],
    'creative_18plus': ['порно','секс','голый','эротика','расчленёнка','насилие','убийство'],
    'creative_discussion': ['обсуждение','комментарий','вопрос','ответ'],
    'creative_ad': ['реклама','самореклама','мой канал','подпишись','instagram','youtube'],
}

# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def detect_gender_by_name(name: str) -> int:
    name_lower = name.lower().strip()
    unisex = ('саша','женя','валя','слава','никита','вика','ната','тоня','саня')
    if name_lower in unisex: return 2
    for e in ('а','я','ия','ь'):
        if name_lower.endswith(e): return 1
    return 0

async def is_moderation_enabled(chat_id):
    row = db("SELECT enabled FROM moderation_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return row[0][0] == 1 if row else True

def get_user(uid):
    r = db("SELECT coins,xp,warns,xp_multiplier FROM users WHERE id=?", (uid,), fetch=True)
    if not r:
        db("INSERT INTO users (id) VALUES (?)", (uid,))
        return (500, 0, 0, 1.0)
    return r[0]

def add_coins(uid, amount):
    get_user(uid)
    db("UPDATE users SET coins=coins+? WHERE id=?", (amount, uid))

def add_xp(uid, amount):
    get_user(uid)
    old = db("SELECT xp FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    db("UPDATE users SET xp=xp+? WHERE id=?", (amount, uid))
    if old // 100 < (old + amount) // 100:
        return (old + amount) // 100
    return None

def get_nickname(uid, chat_id):
    r = db("SELECT nickname FROM user_nicknames WHERE user_id=? AND chat_id=?", (uid, chat_id), fetch=True)
    return r[0][0] if r else None

def user_link_with_nick(uid, chat_id, default_name):
    nick = get_nickname(uid, chat_id)
    name = nick if nick else default_name
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_user_mention(uid, chat_id, default_name):
    try:
        r = db("SELECT username FROM usernames WHERE user_id=?", (uid,), fetch=True)
        if r and r[0][0]:
            return f"@{r[0][0]}"
    except: pass
    return f'<a href="tg://user?id={uid}">{default_name}</a>'

def save_username(user: types.User):
    if user and user.username:
        db("INSERT OR REPLACE INTO usernames (username,user_id,name) VALUES (?,?,?)",
           (user.username.lower(), user.id, user.first_name))

async def resolve_target(message: types.Message, args: str = ""):
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name, message.reply_to_message
    for word in args.split():
        if word.startswith("@"):
            username = word[1:]
            r = db("SELECT user_id,name FROM usernames WHERE username=?", (username.lower(),), fetch=True)
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
    s = s.lower().strip().replace(" ", "")
    if 'мес' in s:
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 30 * 86400
    if 'год' in s or (s.endswith('г') and re.search(r'\d', s)):
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 365 * 86400
    if 'дн' in s or 'день' in s or (s.endswith('д') and re.search(r'\d', s)):
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 86400
    if 'час' in s or (s.endswith('ч') and re.search(r'\d', s)):
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 3600
    if 'мин' in s or (s.endswith('м') and re.search(r'\d', s)):
        num = re.findall(r'\d+', s)
        if num: return int(num[0]) * 60
    num = re.findall(r'\d+', s)
    return int(num[0]) * 60 if num else 300

def fmt_dur(sec: int) -> str:
    if sec >= 31536000: return f"{sec//31536000} г."
    if sec >= 2592000:  return f"{sec//2592000} мес."
    if sec >= 86400:    return f"{sec//86400} дн."
    if sec >= 3600:     return f"{sec//3600} ч."
    return f"{sec//60} мин."

def extract_bet(text: str):
    nums = re.findall(r'\d+', text)
    return int(nums[0]) if nums else None

async def is_chat_closed(chat_id):
    r = db("SELECT is_closed FROM chat_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return bool(r and r[0][0])

# ============================================================
#  СИСТЕМА ВАРНОВ
# ============================================================
def get_user_warns(uid, chat_id):
    now = int(time.time())
    return db("SELECT id,reason,date,expires FROM warns_system WHERE user_id=? AND chat_id=? AND expires>? ORDER BY date DESC",
              (uid, chat_id, now), fetch=True)

def get_warn_count(uid, chat_id):
    return len(get_user_warns(uid, chat_id))

def add_warn(uid, chat_id, reason, days=30):
    now = int(time.time())
    db("INSERT INTO warns_system (user_id,chat_id,reason,date,expires) VALUES (?,?,?,?,?)",
       (uid, chat_id, reason, now, now + days * 86400))
    return get_warn_count(uid, chat_id)

def clear_warns(uid, chat_id):
    db("DELETE FROM warns_system WHERE user_id=? AND chat_id=?", (uid, chat_id))

# ============================================================
#  ЛОГИРОВАНИЕ
# ============================================================
async def send_punishment_log(source, target_id: int, action: str, reason: str,
                               duration: str = "", is_auto: bool = False, admin_user=None):
    try:
        target = await bot.get_chat(target_id)
        if isinstance(source, types.Message):
            chat  = source.chat
            admin = source.from_user
        else:
            chat  = await bot.get_chat(source)
            admin = admin_user

        text = f"{action}\n\n"
        text += f"👤 Нарушитель: {target.first_name}"
        if target.username: text += f" (@{target.username})"
        text += f"\n🆔 ID: {target.id}\n\n"
        if is_auto:
            text += "👮 Кто выдал: 🤖 Автомодерация\n"
        elif admin:
            text += f"👮 Кто выдал: {admin.first_name}"
            if admin.username: text += f" (@{admin.username})"
            text += "\n"
        text += f"\n💬 Чат: {chat.title}"
        if chat.username: text += f" (@{chat.username})"
        text += f"\n📌 Причина: {reason}"
        if duration: text += f"\n⏳ Срок: {duration}"

        await bot.send_message(LOG_CHANNEL, text, reply_to_message_id=LOG_MESSAGE_ID)
    except Exception as e:
        logging.error(f"Лог ошибка: {e}")

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

    thread_id  = message.message_thread_id
    is_ideas   = (thread_id == 18357)
    is_creative= (thread_id == 19010)

    violation = rule = None
    for cat, words in BAD_WORDS.items():
        for w in words:
            hit = (w in text) if cat != 'spam' else bool(re.search(w, text))
            if not hit: continue
            if is_ideas and cat == 'ideas_only':
                violation, rule = cat, PUNISHMENT_RULES[cat]; break
            if is_creative and cat in ('creative_18plus','creative_discussion','creative_ad'):
                violation, rule = cat, PUNISHMENT_RULES[cat]; break
            if cat in PUNISHMENT_RULES and not is_ideas and not is_creative:
                violation, rule = cat, PUNISHMENT_RULES[cat]; break
        if violation: break
    if not violation: return

    uid     = message.from_user.id
    chat_id = message.chat.id

    try: await message.delete()
    except: pass

    warn_count  = add_warn(uid, chat_id, f"Автомодерация: {rule['rule']}", rule['warn_days'])
    duration    = 0
    action_text = "⚠️ ВАРН (автомодерация)"
    ptext       = f"⚠️ ВАРН #{warn_count}/3"

    if warn_count >= 3 and rule['mute_hours'] > 0:
        duration = rule['mute_hours'] * 3600
        until    = int(time.time()) + duration
        db("INSERT OR REPLACE INTO muted (user_id,chat_id,until) VALUES (?,?,?)", (uid, chat_id, until))
        try:
            await bot.restrict_chat_member(
                chat_id, uid,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.fromtimestamp(until, tz=timezone.utc)
            )
        except Exception as e:
            logging.error(f"Мут авто-мод: {e}")
        action_text = "🔇 МУТ (автомодерация)"
        ptext = f"🔇 МУТ на {rule['mute_hours']} ч. (варн #{warn_count})"
    elif warn_count >= 3:
        action_text = "⚠️ ВАРН (автомодерация)"
        ptext = f"⚠️ ВАРН #{warn_count} (навсегда)"

    # Пишем ТОЛЬКО нарушителю в личку
    try:
        await bot.send_message(
            uid,
            f"⚠️ <b>Предупреждение — автомодерация</b>\n\n"
            f"📌 Нарушение: {rule['rule']}\n"
            f"📊 {ptext}\n\n"
            f"💬 Чат: {message.chat.title}"
        )
    except Exception:
        # Личка закрыта — краткое уведомление в чат без имени
        try:
            await bot.send_message(
                chat_id,
                f"⚠️ Сообщение удалено автомодерацией.\n📌 {rule['rule']}",
                message_thread_id=thread_id
            )
        except: pass

    await send_punishment_log(
        chat_id, uid, action_text, rule['rule'],
        fmt_dur(duration) if duration else "",
        is_auto=True
    )

# ============================================================
#  КЛЮЧЕВАЯ ФУНКЦИЯ: ПОЛУЧИТЬ ПРАВА БОТА В ЧАТЕ
# ============================================================
async def get_bot_rights(chat_id: int) -> dict:
    """
    Возвращает словарь с реальными правами бота в чате.
    Используется перед promote_chat_member, чтобы не выдавать
    права, которых у бота нет → фикс RIGHT_FORBIDDEN.
    """
    try:
        me   = await bot.get_me()
        memb = await bot.get_chat_member(chat_id, me.id)
        return {
            'can_delete':        getattr(memb, 'can_delete_messages',    False) or False,
            'can_restrict':      getattr(memb, 'can_restrict_members',   False) or False,
            'can_invite':        getattr(memb, 'can_invite_users',       False) or False,
            'can_pin':           getattr(memb, 'can_pin_messages',       False) or False,
            'can_change_info':   getattr(memb, 'can_change_info',        False) or False,
            'can_promote':       getattr(memb, 'can_promote_members',    False) or False,
            'can_manage_topics': getattr(memb, 'can_manage_topics',      False) or False,
            'can_video_chats':   getattr(memb, 'can_manage_video_chats', False) or False,
            'is_anonymous':      getattr(memb, 'is_anonymous',           False) or False,
        }
    except Exception as e:
        logging.error(f"get_bot_rights: {e}")
        return {k: False for k in ('can_delete','can_restrict','can_invite','can_pin',
                                    'can_change_info','can_promote','can_manage_topics',
                                    'can_video_chats','is_anonymous')}

# ============================================================
#  ПРИМЕНЕНИЕ ПРАВ АДМИНИСТРАТОРА (ФИКС RIGHT_FORBIDDEN)
# ============================================================
async def apply_admin_permissions(chat_id: int, user_id: int, perms: dict) -> tuple[bool, str]:
    """
    Применяет права к участнику. Сначала проверяет права бота,
    чтобы не передавать параметры, которых бот сам не имеет.
    Возвращает (успех, сообщение_об_ошибке).
    """
    bot_rights = await get_bot_rights(chat_id)

    # Только то, что бот сам может выдать
    kwargs = dict(
        can_manage_chat      = True,
        can_delete_messages  = perms['can_delete']   and bot_rights['can_delete'],
        can_restrict_members = perms['can_restrict'] and bot_rights['can_restrict'],
        can_invite_users     = perms['can_invite']   and bot_rights['can_invite'],
        can_pin_messages     = perms['can_pin']      and bot_rights['can_pin'],
        can_change_info      = perms['can_change_info'] and bot_rights['can_change_info'],
        can_promote_members  = perms['can_promote']  and bot_rights['can_promote'],
        can_manage_topics    = perms['can_manage_topics'] and bot_rights['can_manage_topics'],
        can_manage_video_chats = perms['can_video_chats'] and bot_rights['can_video_chats'],
    )

    # is_anonymous: добавляем только если бот сам анонимен или является создателем
    if bot_rights['is_anonymous'] or perms.get('is_anonymous') is False:
        kwargs['is_anonymous'] = perms.get('is_anonymous', False) and bot_rights['is_anonymous']

    try:
        await bot.promote_chat_member(chat_id, user_id, **kwargs)
        return True, ""
    except Exception as e:
        err = str(e)
        logging.error(f"promote_chat_member: {e}")
        if 'CHAT_ADMIN_REQUIRED' in err:
            return False, "❌ Бот не является администратором чата!"
        if 'RIGHT_FORBIDDEN' in err:
            return False, "❌ У бота нет прав для выдачи некоторых разрешений.\nУбедитесь, что у бота есть все нужные права."
        if 'USER_NOT_PARTICIPANT' in err:
            return False, "❌ Пользователь не является участником чата."
        return False, f"❌ Ошибка Telegram: {err}"

def get_default_perms() -> dict:
    return {
        'can_promote':       False,
        'can_change_info':   True,
        'can_delete':        True,
        'can_restrict':      True,
        'can_invite':        True,
        'can_pin':           True,
        'can_video_chats':   False,
        'is_anonymous':      False,
        'can_post_stories':  False,
        'can_manage_topics': True,
    }

async def get_admin_permissions(chat_id: int, user_id: int) -> dict:
    row = db(
        "SELECT can_promote,can_change_info,can_delete,can_restrict,can_invite,"
        "can_pin,can_video_chats,is_anonymous,can_post_stories,can_manage_topics "
        "FROM admin_permissions WHERE chat_id=? AND user_id=?",
        (chat_id, user_id), fetch=True
    )
    if row:
        keys = ['can_promote','can_change_info','can_delete','can_restrict','can_invite',
                'can_pin','can_video_chats','is_anonymous','can_post_stories','can_manage_topics']
        return {k: bool(v) for k, v in zip(keys, row[0])}
    return get_default_perms()

def save_admin_perms_db(chat_id: int, user_id: int, perms: dict):
    db(
        "INSERT OR REPLACE INTO admin_permissions "
        "(user_id,chat_id,can_promote,can_change_info,can_delete,can_restrict,can_invite,"
        "can_pin,can_video_chats,is_anonymous,can_post_stories,can_manage_topics) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, chat_id,
         perms['can_promote'], perms['can_change_info'], perms['can_delete'],
         perms['can_restrict'], perms['can_invite'], perms['can_pin'],
         perms['can_video_chats'], perms['is_anonymous'],
         perms.get('can_post_stories', False), perms['can_manage_topics'])
    )

# ============================================================
#  КЛАВИАТУРА АДМИН-ПАНЕЛИ (по скриншоту)
# ============================================================
def _e(flag: bool) -> str:
    return "✅" if flag else "—"

def admin_panel_kb(uid: int, chat_id: int, perms: dict) -> InlineKeyboardMarkup:
    def btn(label, perm):
        return InlineKeyboardButton(
            text=f"{_e(perms[perm])} {label}",
            callback_data=f"ap|toggle|{uid}|{chat_id}|{perm}"
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        # Строка 1 — полная ширина
        [btn("Назначение админов", "can_promote")],
        # Строка 2
        [btn("Профиль группы", "can_change_info"),  btn("Удаление смс",  "can_delete")],
        # Строка 3
        [btn("Баны",            "can_restrict"),     btn("Инвайты",       "can_invite")],
        # Строка 4
        [btn("Закрепы",         "can_pin"),          btn("Трансляции",    "can_video_chats")],
        # Строка 5
        [btn("Анонимность",     "is_anonymous"),     btn("Теги",          "can_post_stories")],
        # Строка 6 — полная ширина
        [btn("Управление темами", "can_manage_topics")],
        # Строка 7 — Разжаловать
        [InlineKeyboardButton(text="🔻 Разжаловать",
                              callback_data=f"ap|remove|{uid}|{chat_id}")],
    ])

# ============================================================
#  УПРАВЛЕНИЕ ЧАТОМ
# ============================================================
async def save_current_permissions(chat_id):
    try:
        chat = await bot.get_chat(chat_id)
        p = chat.permissions or ChatPermissions(
            can_send_messages=True, can_send_media_messages=True,
            can_send_polls=True, can_send_other_messages=True,
            can_add_web_page_previews=True, can_change_info=True,
            can_invite_users=True, can_pin_messages=True, can_manage_topics=True
        )
        db("INSERT OR REPLACE INTO chat_permissions_backup VALUES (?,?,?,?,?,?,?,?,?,?)",
           (chat_id, p.can_send_messages, p.can_send_media_messages, p.can_send_polls,
            p.can_send_other_messages, p.can_add_web_page_previews, p.can_change_info,
            p.can_invite_users, p.can_pin_messages, p.can_manage_topics))
        return True
    except: return False

async def restore_saved_permissions(chat_id):
    row = db("SELECT * FROM chat_permissions_backup WHERE chat_id=?", (chat_id,), fetch=True)
    try:
        if row:
            p = ChatPermissions(
                can_send_messages=bool(row[0][1]), can_send_media_messages=bool(row[0][2]),
                can_send_polls=bool(row[0][3]), can_send_other_messages=bool(row[0][4]),
                can_add_web_page_previews=bool(row[0][5]), can_change_info=bool(row[0][6]),
                can_invite_users=bool(row[0][7]), can_pin_messages=bool(row[0][8]),
                can_manage_topics=bool(row[0][9])
            )
        else:
            p = ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                                can_send_polls=True, can_send_other_messages=True,
                                can_add_web_page_previews=True, can_invite_users=True)
        await bot.set_chat_permissions(chat_id, permissions=p)
        return True
    except: return False

async def close_chat(chat_id):
    await save_current_permissions(chat_id)
    db("UPDATE chat_settings SET is_closed=1 WHERE chat_id=?", (chat_id,))
    try:
        await bot.set_chat_permissions(chat_id, permissions=ChatPermissions(
            can_send_messages=False, can_send_media_messages=False,
            can_send_polls=False, can_send_other_messages=False,
            can_add_web_page_previews=False, can_invite_users=True,
            can_change_info=False, can_pin_messages=False
        ))
        await bot.send_message(chat_id, "🔒 ЧАТ ЗАКРЫТ")
        return True
    except: return False

async def open_chat(chat_id):
    db("UPDATE chat_settings SET is_closed=0 WHERE chat_id=?", (chat_id,))
    await restore_saved_permissions(chat_id)
    await bot.send_message(chat_id, "🔓 ЧАТ ОТКРЫТ")
    return True

# ============================================================
#  РАСПИСАНИЕ
# ============================================================
sent_notifications: dict = {}

def msktime() -> datetime:
    return datetime.now(timezone(timedelta(hours=3)))

async def apply_schedule_now(chat_id):
    row = db("SELECT close_time,open_time,is_closed FROM chat_settings WHERE chat_id=?", (chat_id,), fetch=True)
    if not row: return
    close_time, open_time, is_closed = row[0]
    if not close_time or not open_time: return
    now = msktime()
    nm  = now.hour * 60 + now.minute
    try:
        ch, cm = map(int, close_time.split(':'))
        oh, om = map(int, open_time.split(':'))
    except: return
    cl_m = ch * 60 + cm
    op_m = oh * 60 + om
    if cl_m < op_m:
        should_close = cl_m <= nm < op_m
        sec_to_close = (cl_m - nm) * 60 if nm < cl_m else (cl_m + 1440 - nm) * 60
    else:
        should_close = nm >= cl_m or nm < op_m
        sec_to_close = (cl_m + 1440 - nm) * 60 if nm >= cl_m else 0
    if should_close and not is_closed:   await close_chat(chat_id)
    elif not should_close and is_closed: await open_chat(chat_id)
    if not should_close and not is_closed and sec_to_close > 0:
        for wt in [3600, 1800, 900, 600, 300, 60, 30, 10]:
            if wt <= sec_to_close < wt + 10:
                key = f"warn_{chat_id}_{now.strftime('%Y%m%d')}_{wt}"
                if key not in sent_notifications:
                    sent_notifications[key] = True
                    ts = f"{wt//3600} час" if wt >= 3600 else f"{wt//60} минут" if wt >= 60 else f"{wt} секунд"
                    await bot.send_message(chat_id, f"⚠️ Чат закроется через {ts}.")
                break

async def scheduler_loop():
    while True:
        try:
            today = msktime().strftime('%Y%m%d')
            for k in [k for k in list(sent_notifications) if today not in k]:
                del sent_notifications[k]
            chats = db("SELECT chat_id FROM chat_settings WHERE close_time IS NOT NULL AND open_time IS NOT NULL", fetch=True)
            for (cid,) in chats: await apply_schedule_now(cid)
        except: pass
        await asyncio.sleep(10)

# ============================================================
#  MIDDLEWARE
# ============================================================
class MainMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            if event.from_user: save_username(event.from_user)
            if event.chat and event.chat.type in ("group","supergroup") and event.from_user:
                uid, cid = event.from_user.id, event.chat.id
                if await is_admin(cid, uid):
                    return await handler(event, data)
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
        [InlineKeyboardButton(text="👤 Профиль",     callback_data="m_profile"),
         InlineKeyboardButton(text="🏆 Топ",         callback_data="m_top")],
        [InlineKeyboardButton(text="🛒 Магазин",     callback_data="m_shop"),
         InlineKeyboardButton(text="🎮 Игры",        callback_data="m_games")],
        [InlineKeyboardButton(text="❤️ RP",          callback_data="m_rp"),
         InlineKeyboardButton(text="➕ Добавить в группу", url=f"https://t.me/{username}?startgroup=L")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="m_back")]])

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    me = await bot.get_me()
    if message.chat.type != "private":
        return await bot.send_message(message.chat.id, "✅ VOID Helper активен!\n/help — все команды.",
                                      message_thread_id=message.message_thread_id)
    mention = get_user_mention(message.from_user.id, message.chat.id, message.from_user.first_name)
    await message.answer(f"👋 Привет, {mention}!\nЯ VOID Helper.\n📋 /help",
                         reply_markup=main_menu_kb(me.username))

@dp.callback_query(F.data == "m_profile")
async def cb_profile(call: types.CallbackQuery):
    uid = call.from_user.id
    coins, xp, warns, _ = get_user(uid)
    await call.message.edit_text(
        f"👤 Профиль\n\n{user_link_with_nick(uid, call.message.chat.id, call.from_user.first_name)}\n"
        f"⭐ Уровень: {xp//100}\n💰 Монеты: {coins}\n📊 Опыт: {xp}\n⚠️ Варны: {warns}/3",
        reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_top")
async def cb_top(call: types.CallbackQuery):
    rows = db("SELECT id,coins FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    if not rows: return await call.message.edit_text("🏆 Пока никого", reply_markup=back_kb())
    medals = ["🥇","🥈","🥉"]
    lines  = ["🏆 Топ монет"]
    for i,(uid,coins) in enumerate(rows):
        m = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{m} {user_link_with_nick(uid, call.message.chat.id, str(uid))} — {coins}💰")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_shop")
async def cb_shop(call: types.CallbackQuery):
    await call.message.edit_text("🛒 Магазин\n1️⃣ Множитель x2 — 500💰\n2️⃣ Сброс работы — 300💰\n\n/buy 1  /buy 2",
                                  reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_games")
async def cb_games(call: types.CallbackQuery):
    await call.message.edit_text(
        "🎮 Игры\n/casino 100 — слоты\n/darts 50 — дартс\n/coinflip 30 — орёл/решка\n/rps 15 — КНБ\n\n"
        "⚔️ Дуэли:\n/dice, /basketball, /football, /bowling",
        reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_rp")
async def cb_rp(call: types.CallbackQuery):
    await call.message.edit_text(
        "❤️ RP действия\n/rp — список\nобнять @user, поцеловать @user\n"
        "💍 Браки: +брак, +развод, +пара\n📛 Ники: +ник @user НовыйНик",
        reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data == "m_back")
async def cb_back(call: types.CallbackQuery):
    me = await bot.get_me()
    await call.message.edit_text(f"👋 Привет, {call.from_user.first_name}!\nЯ VOID Helper.",
                                  reply_markup=main_menu_kb(me.username))
    await call.answer()

# ============================================================
#  HELP
# ============================================================
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await bot.send_message(message.chat.id, """
📋 <b>VOID HELPER — ПРАВИЛА И КОМАНДЫ</b>

<b>⚠️ ПРАВИЛА ЧАТА VOID:</b>
1.1. 18+ контент — варн на месяц + мут 4 часа
1.2. Оскорбления — варн на месяц + мут 8 часов
1.3. Споры и конфликты — варн на месяц + мут 2 часа
1.4. Спам/флуд/реклама — варн на месяц + мут 4 часа
1.5. Ввод в заблуждение — варн на месяц + мут 4 часа
1.6. Выпрашивание админки — варн навсегда
1.7. Клевета на админов — варн на месяц + мут 24 часа
3.1. Только идеи (в ветке идей) — варн 3 дня + мут 1 час
4.1. Запрещённый контент (творчество) — варн месяц + мут 4 часа
4.2. Обсуждение в творчестве — варн неделя + мут 2 часа
4.3. Реклама в творчестве — варн месяц + мут 6 часов

<b>🤖 СИСТЕМА ВАРНОВ:</b>
• 1-2 варна — предупреждение (личное сообщение)
• 3 варна — мут согласно правилам
• Варны сгорают через указанный срок

<b>👤 ПРОФИЛЬ:</b> /profile, /top
<b>💼 ЭКОНОМИКА:</b> /work, /daily, /shop, /buy
<b>🎮 ИГРЫ:</b> /casino, /darts, /coinflip, /rps
<b>⚔️ ДУЭЛИ:</b> /dice, /basketball, /football, /bowling
<b>❤️ RP:</b> обнять, поцеловать, ударить, погладить
<b>💍 БРАКИ:</b> +брак, +развод, +пара, +список браков
<b>📛 НИКИ:</b> +ник @user НовыйНик

<b>🔒 УПРАВЛЕНИЕ ЧАТОМ:</b>
-чат, +чат, /setautoschedule, /check_schedule, /setwelcome

<b>🛡 МОДЕРАЦИЯ (только для админов):</b>
!мут @user 10м причина    — замутить
!мут [ответ] 10м причина  — замутить ответом
-размут @user / [ответ]   — размутить
!мутлист                  — список замученных
!бан @user 7д причина     — забанить
!бан [ответ] 7д причина   — забанить ответом
-разбан @user             — разбанить
!банлист                  — список забаненных
!кик @user / [ответ]      — кикнуть
!варн @user причина       — выдать варн
-варн @user               — снять варн
!варны @user              — варны пользователя
-очиститьварны @user      — очистить варны
!админ @user / [ответ]    — назначить + открыть панель прав
-админ @user              — снять администратора
/moderation on/off        — автомодерация

Длительность: 10м, 2ч, 3д, 1мес, 1г
""", message_thread_id=message.message_thread_id)

# ============================================================
#  ЭКОНОМИКА
# ============================================================
@dp.message(Command("profile"))
async def profile(message: types.Message):
    uid = message.from_user.id
    coins, xp, warns, _ = get_user(uid)
    await message.answer(
        f"👤 Профиль\n\n{user_link_with_nick(uid, message.chat.id, message.from_user.first_name)}\n"
        f"⭐ Уровень: {xp//100}\n💰 Монеты: {coins}\n📊 Опыт: {xp}\n⚠️ Варны: {warns}/3"
    )

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    rows = db("SELECT id,coins FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    if not rows: return await message.answer("🏆 Пока никого")
    medals = ["🥇","🥈","🥉"]
    lines  = ["🏆 Топ монет"]
    for i,(uid,coins) in enumerate(rows):
        m = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{m} {user_link_with_nick(uid, message.chat.id, str(uid))} — {coins}💰")
    await message.answer("\n".join(lines))

@dp.message(Command("work"))
async def work(message: types.Message):
    uid  = message.from_user.id
    last = db("SELECT last_work FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    now  = int(time.time())
    if now - last < 600:
        rem = 600 - (now - last)
        return await message.answer(f"⏳ Отдых ещё {rem//60}м {rem%60}с")
    jobs = [("💻 Написал бота",600,1000),("📦 Развёз посылки",400,700),("🚗 Отвёз клиента",500,800)]
    job,mn,mx = random.choice(jobs)
    pay = random.randint(mn, mx)
    xpg = random.randint(15, 35)
    add_coins(uid, pay)
    new_level = add_xp(uid, xpg)
    db("UPDATE users SET last_work=? WHERE id=?", (now, uid))
    await message.answer(f"⛏ {job}\n💰 +{pay}💰\n✨ +{xpg} XP" + (f"\n🎉 {new_level} уровень!" if new_level else ""))

@dp.message(Command("daily"))
async def daily(message: types.Message):
    uid = message.from_user.id
    get_user(uid)
    now  = int(time.time())
    last = db("SELECT last_daily FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    if now - last < 86400:
        rem = 86400 - (now - last)
        return await message.answer(f"🎁 Бонус уже получен! Следующий через {rem//3600} ч {(rem%3600)//60} мин")
    bonus = random.randint(300, 700)
    add_coins(uid, bonus)
    new_level = add_xp(uid, 50)
    db("UPDATE users SET last_daily=? WHERE id=?", (now, uid))
    msg = f"🎁 Ежедневный бонус!\n💰 +{bonus} монет\n✨ +50 XP"
    if new_level: msg += f"\n🎉 Вы достигли {new_level} уровня!"
    await message.answer(msg)

@dp.message(Command("shop"))
async def shop_cmd(message: types.Message):
    await message.answer("🛒 Магазин\n1️⃣ Множитель x2 — 500💰\n2️⃣ Сброс работы — 300💰\n\n/buy 1  /buy 2")

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    args = message.text.split()
    if len(args) < 2: return await message.answer("❌ /buy 1 или /buy 2")
    try: item = int(args[1])
    except: return await message.answer("❌ Некорректный номер")
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if item == 1:
        if coins < 500: return await message.answer("❌ Нужно 500💰")
        add_coins(uid, -500)
        db("UPDATE users SET xp_multiplier=2.0 WHERE id=?", (uid,))
        asyncio.create_task(reset_multiplier(uid, 3600))
        await message.answer("✨ Множитель x2 на 1 час!")
    elif item == 2:
        if coins < 300: return await message.answer("❌ Нужно 300💰")
        add_coins(uid, -300)
        db("UPDATE users SET last_work=0 WHERE id=?", (uid,))
        await message.answer("⚡ Кулдаун работы сброшен!")
    else:
        await message.answer("❌ Неверный номер товара")

async def reset_multiplier(uid, delay):
    await asyncio.sleep(delay)
    db("UPDATE users SET xp_multiplier=1.0 WHERE id=?", (uid,))

# ============================================================
#  ИГРЫ
# ============================================================
async def check_bet(message, bet, min_bet=10):
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet < min_bet:       await message.reply(f"❌ Мин. ставка: {min_bet}"); return None
    if bet > coins:         await message.reply(f"❌ У тебя {coins}💰");        return None
    add_coins(uid, -bet);   return uid

@dp.message(Command("casino"))
async def casino_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet: return await message.reply("🎰 /casino 100")
    uid = await check_bet(message, bet, 10)
    if not uid: return
    msg = await message.reply_dice(emoji="🎰")
    await asyncio.sleep(DICE_WAIT["🎰"])
    v = msg.dice.value
    if v == 64: add_coins(uid, bet*10); add_xp(uid,150); await message.reply(f"🎉 ДЖЕКПОТ! +{bet*10}💰")
    elif v >= 50: add_coins(uid, bet*4); add_xp(uid,40); await message.reply(f"🎰 КРУПНО! +{bet*4}💰")
    elif v >= 30: add_coins(uid, bet*2); add_xp(uid,15); await message.reply(f"🎰 ВЫИГРЫШ! +{bet*2}💰")
    elif v >= 15: add_coins(uid, bet);                    await message.reply(f"🎰 Возврат {bet}💰")
    else:                                                  await message.reply(f"😞 Проиграл {bet}💰")

@dp.message(Command("darts"))
async def darts_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet: return await message.reply("🎯 /darts 50")
    uid = await check_bet(message, bet, 10)
    if not uid: return
    msg = await message.reply_dice(emoji="🎯")
    await asyncio.sleep(DICE_WAIT["🎯"])
    v = msg.dice.value
    if v == 6: add_coins(uid, bet*5); await message.reply(f"🎯 БУЛЛ-АЙ! +{bet*5}💰")
    elif v == 5: add_coins(uid, bet*3); await message.reply(f"🎯 ОТЛИЧНО! +{bet*3}💰")
    elif v == 4: add_coins(uid, bet*2); await message.reply(f"🎯 ХОРОШО! +{bet*2}💰")
    elif v == 3: add_coins(uid, bet);   await message.reply(f"🎯 Возврат {bet}💰")
    else:                               await message.reply(f"😞 Мимо! -{bet}💰")

@dp.message(Command("coinflip"))
async def coinflip_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet: return await message.reply("🪙 /coinflip 30")
    uid = await check_bet(message, bet, 10)
    if not uid: return
    result = random.choice(["орёл","решка"])
    guess  = random.choice(["орёл","решка"])
    if result == guess: add_coins(uid, bet*2); await message.reply(f"🪙 {result}!\n🎉 +{bet*2}💰")
    else:                                       await message.reply(f"🪙 {result}!\n😞 -{bet}💰")

@dp.message(Command("rps"))
async def rps_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet: return await message.reply("✊ /rps 15")
    uid = await check_bet(message, bet, 10)
    if not uid: return
    await message.reply("✊ Камень, ножницы или бумага? (15 сек)")
    try:
        answer = await bot.wait_for("message", timeout=15.0,
            check=lambda m: m.from_user.id == uid and m.text and
                            m.text.lower() in ["камень","ножницы","бумага"])
        user = answer.text.lower()
        bot_c = random.choice(["камень","ножницы","бумага"])
        if user == bot_c:
            add_coins(uid, bet); await message.reply(f"🤝 Ничья! {bot_c}\nВозврат {bet}💰")
        elif (user=="камень" and bot_c=="ножницы") or \
             (user=="ножницы" and bot_c=="бумага") or \
             (user=="бумага"  and bot_c=="камень"):
            add_coins(uid, bet*2); await message.reply(f"🎉 Победа! +{bet*2}💰")
        else: await message.reply(f"😞 Поражение! -{bet}💰")
    except:
        add_coins(uid, bet); await message.reply("⏰ Время вышло! Ставка возвращена")

# ============================================================
#  ДУЭЛИ
# ============================================================
active_duels: dict = {}
DUEL_GAMES = {
    "dice":       {"emoji":"🎲","name":"Кости"},
    "basketball": {"emoji":"🏀","name":"Баскетбол"},
    "football":   {"emoji":"⚽","name":"Футбол"},
    "bowling":    {"emoji":"🎳","name":"Боулинг"},
}

def duel_kb(game_type, challenger_id, chat_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принять",  callback_data=f"duel_accept_{game_type}_{challenger_id}_{chat_id}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"duel_decline_{game_type}_{challenger_id}"),
    ]])

@dp.message(Command("dice"))
async def cmd_dice(m): await start_duel_invite(m, "dice")

@dp.message(Command("basketball"))
async def cmd_basketball(m): await start_duel_invite(m, "basketball")

@dp.message(Command("football"))
async def cmd_football(m): await start_duel_invite(m, "football")

@dp.message(Command("bowling"))
async def cmd_bowling(m): await start_duel_invite(m, "bowling")

async def start_duel_invite(message: types.Message, game_type: str):
    if not message.reply_to_message:
        return await message.reply("❌ Ответь на сообщение соперника!")
    ch  = message.from_user
    opp = message.reply_to_message.from_user
    if ch.id == opp.id:  return await message.reply("❌ Нельзя с собой!")
    if opp.is_bot:       return await message.reply("❌ Нельзя с ботом!")
    cid = message.chat.id
    key = f"{cid}_{ch.id}_{opp.id}"
    if key in active_duels: return await message.reply("⚠️ Уже вызвали!")
    game = DUEL_GAMES[game_type]
    active_duels[key] = {"status":"waiting"}
    await message.reply(
        f"{game['emoji']} {game['name']}\n\n"
        f"{user_link_with_nick(ch.id, cid, ch.first_name)} вызывает "
        f"{user_link_with_nick(opp.id, cid, opp.first_name)}!",
        reply_markup=duel_kb(game_type, ch.id, cid)
    )

@dp.callback_query(F.data.startswith("duel_accept_"))
async def duel_accept(call: types.CallbackQuery):
    parts = call.data.split("_")
    game_type = parts[2]
    ch_id = int(parts[3])
    cid   = int(parts[4])
    opp_id = call.from_user.id
    key = f"{cid}_{ch_id}_{opp_id}"
    if key not in active_duels: return await call.answer("❌ Устарело!", show_alert=True)
    await call.message.delete()
    await call.message.answer(f"✅ {user_link_with_nick(opp_id, cid, call.from_user.first_name)} принял(а)!")
    await run_duel(cid, ch_id, opp_id, game_type, call.message)

@dp.callback_query(F.data.startswith("duel_decline_"))
async def duel_decline(call: types.CallbackQuery):
    parts  = call.data.split("_")
    ch_id  = int(parts[3])
    opp_id = call.from_user.id
    cid    = call.message.chat.id
    active_duels.pop(f"{cid}_{ch_id}_{opp_id}", None)
    await call.message.edit_text(f"❌ {user_link_with_nick(opp_id, cid, call.from_user.first_name)} отклонил(а)!")

async def run_duel(cid, p1, p2, game_type, orig):
    game = DUEL_GAMES[game_type]
    p1m  = await bot.get_chat_member(cid, p1)
    p2m  = await bot.get_chat_member(cid, p2)
    p1n, p2n = p1m.user.first_name, p2m.user.first_name
    msg = await orig.reply(
        f"{game['emoji']} {game['name']}\n🆚 "
        f"{user_link_with_nick(p1,cid,p1n)} vs {user_link_with_nick(p2,cid,p2n)}\n\n"
        f"🎲 {user_link_with_nick(p1,cid,p1n)} бросает..."
    )
    d1 = await msg.reply_dice(emoji="🎲")
    await asyncio.sleep(DICE_WAIT["🎲"])
    s1 = d1.dice.value
    await msg.edit_text(
        f"{game['emoji']} {game['name']}\n🆚 "
        f"{user_link_with_nick(p1,cid,p1n)}: {s1}\n"
        f"{user_link_with_nick(p2,cid,p2n)} бросает..."
    )
    d2 = await msg.reply_dice(emoji="🎲")
    await asyncio.sleep(DICE_WAIT["🎲"])
    s2 = d2.dice.value
    w_id = p1 if s1 > s2 else p2 if s2 > s1 else None
    w_nm = p1n if s1 > s2 else p2n if s2 > s1 else None
    if w_id:
        add_coins(w_id, 150); add_xp(w_id, 30)
        await msg.edit_text(
            f"{game['emoji']} {game['name']}\n\n{p1n}: {s1}\n{p2n}: {s2}\n\n"
            f"🏆 Победитель: {user_link_with_nick(w_id,cid,w_nm)}!\n💰 +150, ✨ +30 XP"
        )
    else:
        await msg.edit_text(f"{game['emoji']} {game['name']}\n\n{p1n}: {s1}\n{p2n}: {s2}\n\n🤝 НИЧЬЯ!")
    active_duels.pop(f"{cid}_{p1}_{p2}", None)

# ============================================================
#  ПРИВЕТСТВИЯ
# ============================================================
def gender_suffix(g): return "ёл" if g==0 else "ла" if g==1 else "ли"

def process_welcome(tmpl: str, name: str, mention: str, suffix: str) -> str:
    r = tmpl.replace("{name}",name).replace("{имя}",name)\
            .replace("{mention}",mention).replace("{упоминание}",mention)
    for m in re.findall(r'вош[\(\{][^\)\}]+[\)\}]', r):
        r = r.replace(m, "вошёл" if suffix=="ёл" else "вошла" if suffix=="ла" else "вошли")
    return r

async def get_or_detect_gender(uid, first_name):
    row = db("SELECT gender FROM user_gender WHERE user_id=?", (uid,), fetch=True)
    if row: return row[0][0]
    g = detect_gender_by_name(first_name)
    if g == 2: g = 0
    db("INSERT OR REPLACE INTO user_gender (user_id,gender) VALUES (?,?)", (uid, g))
    return g

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    cid = message.chat.id
    row = db("SELECT welcome_text FROM group_welcome WHERE chat_id=?", (cid,), fetch=True)
    tmpl = row[0][0] if row else "👋 Добро пожаловать, {упоминание}!\nТы вош{ла|ёл|ли} в наш чат."
    for member in message.new_chat_members:
        if member.id == (await bot.get_me()).id: continue
        g   = await get_or_detect_gender(member.id, member.first_name)
        txt = process_welcome(tmpl, member.first_name,
                              get_user_mention(member.id, cid, member.first_name),
                              gender_suffix(g))
        await bot.send_message(cid, txt, message_thread_id=message.message_thread_id)

@dp.message(Command("setwelcome"))
async def set_welcome(message: types.Message):
    if not await mod_guard(message): return
    text = message.text.replace("/setwelcome","").strip()
    if not text: return await message.reply("📝 /setwelcome текст\n\nПеременные: {имя}, {упоминание}, вош{ла|ёл|ли}")
    db("INSERT OR REPLACE INTO group_welcome (chat_id,welcome_text) VALUES (?,?)", (message.chat.id, text))
    await message.reply("✅ Приветствие сохранено!")

# ============================================================
#  МОДЕРАЦИЯ — вспомогательное
# ============================================================
async def mod_guard(message) -> bool:
    if message.chat.type not in ("group","supergroup"): return False
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return False
    return True

def parse_mute_args(args_text: str, has_reply: bool):
    """Парсит строку аргументов: возвращает (duration_str, reason)"""
    if not has_reply:
        parts = [p for p in args_text.split() if not p.startswith("@")]
        args_text = " ".join(parts)
    words = args_text.split()
    dur_str = None
    reason_parts = []
    i = 0
    while i < len(words):
        w = words[i]
        if re.match(r'^\d+$', w) and i+1 < len(words) and re.match(r'^(м|мин|ч|час|д|дн|день|мес|г|год)', words[i+1].lower()):
            dur_str = w + words[i+1]; i += 2; continue
        if re.search(r'\d+[мчдг]|мин|час|дн|мес|год', w.lower()):
            dur_str = w; i += 1; continue
        reason_parts.append(w); i += 1
    return dur_str or "1ч", " ".join(reason_parts) or "нарушение правил"

# ============================================================
#  КОМАНДЫ МОДЕРАЦИИ
# ============================================================
@dp.message(F.text.lower().regexp(r'^[!]\s*мут'))
async def mute_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[!]\s*мут\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!\nПример: !мут @user 10м причина")
    if await is_admin(message.chat.id, uid): return await message.reply("❌ Нельзя замутить администратора!")
    dur_str, reason = parse_mute_args(args_text, bool(message.reply_to_message))
    sec   = parse_duration(dur_str)
    until = int(time.time()) + sec
    db("INSERT OR REPLACE INTO muted (user_id,chat_id,until) VALUES (?,?,?)", (uid, message.chat.id, until))
    warns = get_warn_count(uid, message.chat.id)
    try:
        if message.reply_to_message:
            try: await message.reply_to_message.delete()
            except: pass
        await bot.restrict_chat_member(
            message.chat.id, uid,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=datetime.fromtimestamp(until, tz=timezone.utc)
        )
        await message.reply(
            f"🔇 МУТ\n👤 {user_link_with_nick(uid, message.chat.id, name)}\n"
            f"⏳ {fmt_dur(sec)}\n📌 {reason}" + (f"\n⚠️ Варнов: {warns}" if warns else "")
        )
        await send_punishment_log(message, uid, '🔇 МУТ', reason, fmt_dur(sec))
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().regexp(r'^[!]\s*бан'))
async def ban_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[!]\s*бан\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!\nПример: !бан @user 7д спам")
    if await is_admin(message.chat.id, uid): return await message.reply("❌ Нельзя забанить администратора!")
    dur_str, reason = parse_mute_args(args_text, bool(message.reply_to_message))
    warns = get_warn_count(uid, message.chat.id)
    db("INSERT OR IGNORE INTO banned (user_id,chat_id) VALUES (?,?)", (uid, message.chat.id))
    try:
        if message.reply_to_message:
            try: await message.reply_to_message.delete()
            except: pass
        await bot.ban_chat_member(message.chat.id, uid)
        if dur_str and dur_str != "1ч":
            sec = parse_duration(dur_str)
            await message.reply(
                f"🚫 БАН\n👤 {user_link_with_nick(uid, message.chat.id, name)}\n"
                f"⏳ {fmt_dur(sec)}\n📌 {reason}" + (f"\n⚠️ Варнов: {warns}" if warns else "")
            )
            asyncio.create_task(unban_after(uid, message.chat.id, sec))
            await send_punishment_log(message, uid, '🚫 БАН', reason, fmt_dur(sec))
        else:
            await message.reply(
                f"🚫 БАН НАВСЕГДА\n👤 {user_link_with_nick(uid, message.chat.id, name)}\n"
                f"📌 {reason}" + (f"\n⚠️ Варнов: {warns}" if warns else "")
            )
            await send_punishment_log(message, uid, '🚫 БАН', reason, "навсегда")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

async def unban_after(uid, chat_id, delay):
    await asyncio.sleep(delay)
    db("DELETE FROM banned WHERE user_id=? AND chat_id=?", (uid, chat_id))
    try: await bot.unban_chat_member(chat_id, uid)
    except: pass

@dp.message(F.text.lower().regexp(r'^[!]\s*варн'))
async def give_warn_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[!]\s*варн\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!\nПример: !варн @user причина")
    if await is_admin(message.chat.id, uid): return await message.reply("❌ Нельзя выдать варн администратору!")
    if message.reply_to_message:
        reason = args_text or "нарушение правил"
        try: await message.reply_to_message.delete()
        except: pass
    else:
        reason = " ".join(p for p in args_text.split() if not p.startswith("@")) or "нарушение правил"
    warn_count = add_warn(uid, message.chat.id, reason, 30)
    await message.reply(
        f"⚠️ ПРЕДУПРЕЖДЕНИЕ\n👤 {user_link_with_nick(uid, message.chat.id, name)}\n"
        f"📌 {reason}\n⚠️ ВАРН #{warn_count}/3"
    )
    await send_punishment_log(message, uid, '⚠️ ВАРН', reason)

@dp.message(F.text.lower().regexp(r'^[-]\s*размут'))
async def unmute_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[-]\s*размут\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    db("DELETE FROM muted WHERE user_id=? AND chat_id=?", (uid, message.chat.id))
    try:
        await bot.restrict_chat_member(message.chat.id, uid, permissions=ChatPermissions(
            can_send_messages=True, can_send_media_messages=True, can_send_polls=True,
            can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True
        ))
    except: pass
    await message.reply(f"✅ {user_link_with_nick(uid, message.chat.id, name)} размучен.")

@dp.message(F.text.lower().regexp(r'^[!]\s*мутлист'))
async def mutelist_cmd(message: types.Message):
    if not await mod_guard(message): return
    rows = db("SELECT user_id,until FROM muted WHERE chat_id=? AND until>? ORDER BY until",
              (message.chat.id, int(time.time())), fetch=True)
    if not rows: return await message.reply("📋 Замученных нет.")
    lines = ["📋 ЗАМУЧЕННЫЕ:"]
    for uid, until in rows[:20]:
        try:
            u = await bot.get_chat(uid)
            lines.append(f"• {user_link_with_nick(uid, message.chat.id, u.first_name)} — до {datetime.fromtimestamp(until).strftime('%d.%m %H:%M')}")
        except: lines.append(f"• ID {uid}")
    await message.reply("\n".join(lines))

@dp.message(F.text.lower().regexp(r'^[-]\s*разбан'))
async def unban_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[-]\s*разбан\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid: return await message.reply("❌ Укажи @юзертег!")
    db("DELETE FROM banned WHERE user_id=? AND chat_id=?", (uid, message.chat.id))
    try: await bot.unban_chat_member(message.chat.id, uid)
    except: pass
    await message.reply(f"✅ {user_link_with_nick(uid, message.chat.id, name)} разбанен.")

@dp.message(F.text.lower().regexp(r'^[!]\s*банлист'))
async def banlist_cmd(message: types.Message):
    if not await mod_guard(message): return
    rows = db("SELECT user_id FROM banned WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not rows: return await message.reply("📋 Забаненных нет.")
    lines = ["📋 ЗАБАНЕННЫЕ:"]
    for (uid,) in rows[:20]:
        try:
            u = await bot.get_chat(uid)
            lines.append(f"• {user_link_with_nick(uid, message.chat.id, u.first_name)}")
        except: lines.append(f"• ID {uid}")
    await message.reply("\n".join(lines))

@dp.message(F.text.lower().regexp(r'^[!]\s*кик'))
async def kick_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[!]\s*кик\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    if await is_admin(message.chat.id, uid): return await message.reply("❌ Нельзя кикнуть администратора!")
    try:
        if message.reply_to_message:
            try: await message.reply_to_message.delete()
            except: pass
        await bot.ban_chat_member(message.chat.id, uid)
        await asyncio.sleep(0.5)
        await bot.unban_chat_member(message.chat.id, uid)
        await message.reply(f"👢 {user_link_with_nick(uid, message.chat.id, name)} кикнут.")
        await send_punishment_log(message, uid, '👢 КИК', "нарушение правил")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().regexp(r'^[-]\s*варн\b'))
async def remove_warn_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[-]\s*варн\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    warns = get_user_warns(uid, message.chat.id)
    if not warns: return await message.reply(f"❌ У {user_link_with_nick(uid, message.chat.id, name)} нет варнов.")
    db("DELETE FROM warns_system WHERE id=?", (warns[0][0],))
    await message.reply(f"✅ Снят 1 варн с {user_link_with_nick(uid, message.chat.id, name)}.\n📊 Осталось: {len(warns)-1}")

@dp.message(F.text.lower().regexp(r'^[!]\s*варны'))
async def warnlist_cmd(message: types.Message):
    args_text = re.sub(r'^[!]\s*варны\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if uid and uid != message.from_user.id:
        if not await is_admin(message.chat.id, message.from_user.id):
            return await message.reply("❌ Только администраторы могут смотреть чужие варны!")
    if not uid:
        uid  = message.from_user.id
        name = message.from_user.first_name
    warns = get_user_warns(uid, message.chat.id)
    if not warns:
        return await message.reply(f"✅ У {user_link_with_nick(uid, message.chat.id, name)} нет варнов.")
    lines = [f"📋 ВАРНЫ: {user_link_with_nick(uid, message.chat.id, name)}",
             f"📊 Всего: {len(warns)}", "", "История:"]
    for w in warns[:10]:
        lines.append(f"• {datetime.fromtimestamp(w[2]).strftime('%d.%m.%Y')}: {w[1]}")
    await message.reply("\n".join(lines))

@dp.message(F.text.lower().regexp(r'^[-]\s*очиститьварны'))
async def clear_warns_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[-]\s*очиститьварны\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    clear_warns(uid, message.chat.id)
    await message.reply(f"✅ Варны {user_link_with_nick(uid, message.chat.id, name)} очищены.")

# ============================================================
#  КОМАНДЫ АДМИН-ПАНЕЛИ
# ============================================================
@dp.message(F.text.lower().regexp(r'^[!+]\s*(админ|тг)'))
async def give_admin_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[!+]\s*(админ|тг)\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid:
        return await message.reply(
            "❌ Ответь на сообщение или укажи @юзертег!\n"
            "Пример: !админ @user"
        )
    cid = message.chat.id
    try:
        member = await bot.get_chat_member(cid, uid)
        if member.status in ("administrator","creator"):
            return await message.reply(f"❌ {name} уже является администратором.")
    except Exception as e:
        return await message.reply(f"❌ Не удалось получить данные: {e}")

    perms   = get_default_perms()
    ok, err = await apply_admin_permissions(cid, uid, perms)
    if not ok:
        return await message.reply(err)

    save_admin_perms_db(cid, uid, perms)

    chat    = message.chat
    tag     = f"@{chat.username}" if chat.username else chat.title
    now_str = datetime.now().strftime('%H:%M')

    await message.reply(
        f"<b>🛡 Панель прав администратора</b>\n\n"
        f"👤 Администратор: {user_link_with_nick(uid, cid, name)}\n"
        f"💬 Чат: {tag}\n"
        f"🕐 {now_str}\n\n"
        f"Нажимайте кнопки для изменения прав.\n"
        f"Изменения применяются мгновенно.",
        reply_markup=admin_panel_kb(uid, cid, perms)
    )

@dp.callback_query(F.data.startswith("ap|toggle|"))
async def toggle_admin_perm(call: types.CallbackQuery):
    # Формат: ap|toggle|{uid}|{chat_id}|{perm}
    parts = call.data.split("|")
    if len(parts) < 5: return await call.answer("❌ Ошибка", show_alert=True)
    uid     = int(parts[2])
    chat_id = int(parts[3])
    perm    = parts[4]

    if not await is_admin(chat_id, call.from_user.id):
        return await call.answer("❌ Только для администраторов!", show_alert=True)

    perms = await get_admin_permissions(chat_id, uid)
    if perm not in perms:
        return await call.answer("❌ Неизвестное право", show_alert=True)

    perms[perm] = not perms[perm]

    # Применяем + сохраняем
    ok, err = await apply_admin_permissions(chat_id, uid, perms)
    if ok:
        save_admin_perms_db(chat_id, uid, perms)
        try:
            await call.message.edit_reply_markup(reply_markup=admin_panel_kb(uid, chat_id, perms))
        except: pass
        status = "✅ включено" if perms[perm] else "❌ выключено"
        await call.answer(f"Обновлено: {status}")
    else:
        # Откатываем
        perms[perm] = not perms[perm]
        await call.answer(err, show_alert=True)

@dp.callback_query(F.data.startswith("ap|remove|"))
async def remove_admin_panel(call: types.CallbackQuery):
    parts   = call.data.split("|")
    uid     = int(parts[2])
    chat_id = int(parts[3])
    if not await is_admin(chat_id, call.from_user.id):
        return await call.answer("❌ Только для администраторов!", show_alert=True)
    try:
        await bot.promote_chat_member(
            chat_id, uid,
            can_manage_chat=False, can_delete_messages=False,
            can_restrict_members=False, can_invite_users=False,
            can_pin_messages=False, can_change_info=False,
            can_promote_members=False, can_manage_topics=False,
            is_anonymous=False, can_manage_video_chats=False,
        )
        db("DELETE FROM admin_permissions WHERE user_id=? AND chat_id=?", (uid, chat_id))
        await call.message.edit_text(f"🔻 Администратор разжалован. (ID: {uid})")
        await call.answer("✅ Разжалован")
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)

@dp.message(F.text.lower().regexp(r'^[-]\s*админ'))
async def remove_admin_cmd(message: types.Message):
    if not await mod_guard(message): return
    args_text = re.sub(r'^[-]\s*админ\s*', '', message.text, flags=re.IGNORECASE).strip()
    uid, name, _ = await resolve_target(message, args_text)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    try:
        await bot.promote_chat_member(
            message.chat.id, uid,
            can_manage_chat=False, can_delete_messages=False,
            can_restrict_members=False, can_invite_users=False,
            can_pin_messages=False, can_change_info=False,
            can_promote_members=False, can_manage_topics=False,
            is_anonymous=False, can_manage_video_chats=False,
        )
        db("DELETE FROM admin_permissions WHERE user_id=? AND chat_id=?", (uid, message.chat.id))
        await message.reply(f"🔻 {user_link_with_nick(uid, message.chat.id, name)} лишён прав администратора.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# ============================================================
#  УПРАВЛЕНИЕ ЧАТОМ
# ============================================================
@dp.message(Command("moderation"))
async def toggle_moderation(message: types.Message):
    if not await mod_guard(message): return
    arg = message.text.replace("/moderation","").strip().lower()
    if arg == "on":
        db("INSERT OR REPLACE INTO moderation_settings VALUES (?,?)", (message.chat.id, 1))
        await message.reply("✅ Автомодерация включена")
    elif arg == "off":
        db("INSERT OR REPLACE INTO moderation_settings VALUES (?,?)", (message.chat.id, 0))
        await message.reply("✅ Автомодерация выключена")
    else:
        status = "ВКЛ" if await is_moderation_enabled(message.chat.id) else "ВЫКЛ"
        await message.reply(f"Автомодерация: {status}")

@dp.message(Command("setautoschedule"))
async def set_auto_schedule(message: types.Message):
    if not await mod_guard(message): return
    args = message.text.replace("/setautoschedule","").strip().split()
    if len(args) < 2: return await message.reply("⏰ /setautoschedule 23:00 09:00\n/setautoschedule off — отключить")
    if args[0].lower() == "off":
        db("UPDATE chat_settings SET close_time=NULL, open_time=NULL WHERE chat_id=?", (message.chat.id,))
        return await message.reply("✅ Расписание отключено.")
    fmt = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
    if not re.match(fmt, args[0]) or not re.match(fmt, args[1]):
        return await message.reply("❌ Формат времени: ЧЧ:ММ (пример: 23:00 09:00)")
    db("INSERT OR REPLACE INTO chat_settings (chat_id,close_time,open_time,is_closed) VALUES (?,?,?,0)",
       (message.chat.id, args[0], args[1]))
    await apply_schedule_now(message.chat.id)
    await message.reply(f"✅ Чат закрывается в {args[0]}, открывается в {args[1]}")

@dp.message(Command("check_schedule"))
async def check_schedule_cmd(message: types.Message):
    row = db("SELECT close_time,open_time,is_closed FROM chat_settings WHERE chat_id=?",
             (message.chat.id,), fetch=True)
    if not row or not row[0][0]: return await message.reply("⏰ Расписание не установлено.")
    st = "🔒 ЗАКРЫТ" if row[0][2] else "🔓 ОТКРЫТ"
    await message.reply(f"📅 Закрытие: {row[0][0]}\n🔓 Открытие: {row[0][1]}\nСтатус: {st}")

@dp.message(F.text.lower().startswith(("-чат","!чат")))
async def close_chat_cmd(message: types.Message):
    if not await mod_guard(message): return
    if await is_chat_closed(message.chat.id): return await message.reply("🔒 Уже закрыт!")
    if await close_chat(message.chat.id):
        await message.reply("✅ Чат закрыт.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔓 Открыть", callback_data=f"open_chat_{message.chat.id}")
        ]]))

@dp.message(F.text.lower().startswith(("+чат","!открытьчат")))
async def open_chat_cmd(message: types.Message):
    if not await mod_guard(message): return
    if not await is_chat_closed(message.chat.id): return await message.reply("🔓 Уже открыт!")
    await open_chat(message.chat.id)

@dp.callback_query(F.data.startswith("open_chat_"))
async def open_chat_callback(call: types.CallbackQuery):
    cid = int(call.data.split("_")[2])
    if not await is_admin(cid, call.from_user.id):
        return await call.answer("❌ Только для администраторов!", show_alert=True)
    await open_chat(cid)
    try: await call.message.delete()
    except: pass

# ============================================================
#  RP ДЕЙСТВИЯ
# ============================================================
RP_ACTIONS = {
    "обнять":       ["🤗 обнял","🤗 обняла","🤗 обняли"],
    "поцеловать":   ["😘 поцеловал","😘 поцеловала","😘 поцеловали"],
    "ударить":      ["👊 ударил","👊 ударила","👊 ударили"],
    "погладить":    ["🫳 погладил","🫳 погладила","🫳 погладили"],
    "прижаться":    ["💕 прижался","💕 прижалась","💕 прижались"],
    "взять_за_руку":["💑 взял за руку","💑 взяла за руку","💑 взяли за руку"],
}

@dp.message(Command("rp"))
async def rp_list_cmd(message: types.Message):
    await message.reply("🎭 RP действия:\n" + "\n".join(f"• {k}" for k in RP_ACTIONS))

@dp.message(F.text.lower().startswith(tuple(RP_ACTIONS.keys())))
async def rp_action(message: types.Message):
    if message.chat.type not in ("group","supergroup"): return
    text   = message.text.lower()
    action = next((k for k in RP_ACTIONS if text.startswith(k)), None)
    if not action: return
    uid2, name2, _ = await resolve_target(message, message.text[len(action):].strip())
    if not uid2: return await message.reply("❌ Укажи @юзертег")
    if uid2 == message.from_user.id: return await message.reply("❌ Нельзя с собой!")
    g_row = db("SELECT gender FROM user_gender WHERE user_id=?", (message.from_user.id,), fetch=True)
    g     = g_row[0][0] if g_row else 0
    verb  = RP_ACTIONS[action][g if g < 3 else 0]
    await message.reply(
        f"{user_link_with_nick(message.from_user.id, message.chat.id, message.from_user.first_name)} "
        f"{verb} {user_link_with_nick(uid2, message.chat.id, name2)}!"
    )

# ============================================================
#  БРАКИ
# ============================================================
async def get_marriage(uid, chat_id):
    r = db("SELECT user1,user2,since FROM marriages WHERE chat_id=? AND (user1=? OR user2=?)",
           (chat_id, uid, uid), fetch=True)
    if r:
        u1,u2,since = r[0]
        return (u2 if u1==uid else u1), (int(time.time())-since)//86400
    return None, None

@dp.message(F.text.lower().startswith(("+брак","!брак")))
async def marry_cmd(message: types.Message):
    uid = message.from_user.id
    if (await get_marriage(uid, message.chat.id))[0]: return await message.reply("❌ Вы уже в браке!")
    args = message.text[5:].strip()
    t_id, t_name, _ = await resolve_target(message, args)
    if not t_id: return await message.reply("❌ Укажи @юзертег")
    if t_id == uid: return await message.reply("❌ Нельзя на себе!")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💍 Принять",  callback_data=f"marry_a_{uid}_{t_id}_{message.chat.id}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"marry_d_{uid}_{t_id}"),
    ]])
    await message.reply(
        f"💍 {user_link_with_nick(uid, message.chat.id, message.from_user.first_name)} "
        f"предлагает брак {user_link_with_nick(t_id, message.chat.id, t_name)}!",
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("marry_a_"))
async def marry_accept(call: types.CallbackQuery):
    _, _, s_id, t_id, c_id = call.data.split("_")
    s_id,t_id,c_id = int(s_id),int(t_id),int(c_id)
    if call.from_user.id != t_id: return await call.answer("Не вам!", show_alert=True)
    db("INSERT INTO marriages (user1,user2,chat_id,since) VALUES (?,?,?,?)", (s_id,t_id,c_id,int(time.time())))
    await call.message.edit_text(
        f"💍 ПОЗДРАВЛЯЕМ!\n{user_link_with_nick(s_id,c_id,'')} и {user_link_with_nick(t_id,c_id,'')} теперь в браке!"
    )

@dp.callback_query(F.data.startswith("marry_d_"))
async def marry_deny(call: types.CallbackQuery):
    _, _, s_id, t_id = call.data.split("_")
    if call.from_user.id != int(t_id): return await call.answer("Не вам!", show_alert=True)
    await call.message.edit_text("❌ Предложение отклонено.")

@dp.message(F.text.lower().startswith(("+развод","!развод")))
async def divorce_cmd(message: types.Message):
    uid = message.from_user.id
    partner, days = await get_marriage(uid, message.chat.id)
    if not partner: return await message.reply("❌ Вы не состоите в браке!")
    db("DELETE FROM marriages WHERE chat_id=? AND (user1=? OR user2=?)", (message.chat.id,uid,uid))
    await message.reply(f"💔 Развод оформлен. Вместе: {days} дней.")

@dp.message(F.text.lower().startswith(("+пара","!пара")))
async def couple_info(message: types.Message):
    uid = message.from_user.id
    partner, days = await get_marriage(uid, message.chat.id)
    if not partner: return await message.reply("💔 Вы не в браке.")
    await message.reply(
        f"💑 {user_link_with_nick(uid,message.chat.id,'')} 💕 "
        f"{user_link_with_nick(partner,message.chat.id,'')}\n📅 Вместе: {days} дней"
    )

@dp.message(F.text.lower().startswith(("+список браков","!список браков")))
async def marriages_list(message: types.Message):
    rows = db("SELECT user1,user2,since FROM marriages WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not rows: return await message.reply("📋 Браков пока нет.")
    lines = ["📋 Список браков:"]
    for u1,u2,since in rows:
        lines.append(f"💑 {user_link_with_nick(u1,message.chat.id,'')} + "
                     f"{user_link_with_nick(u2,message.chat.id,'')} — {(int(time.time())-since)//86400} дн.")
    await message.reply("\n".join(lines))

# ============================================================
#  НИКНЕЙМЫ
# ============================================================
@dp.message(F.text.lower().startswith(("+ник","!ник")))
async def set_nickname(message: types.Message):
    args = message.text[4:].strip()
    t_id, t_name, _ = await resolve_target(message, args)
    if not t_id: return await message.reply("❌ Укажи @юзертег")
    nick = " ".join(w for w in args.split() if not w.startswith("@"))
    if not nick: return await message.reply("❌ Укажи ник!")
    db("INSERT OR REPLACE INTO user_nicknames (user_id,chat_id,nickname) VALUES (?,?,?)",
       (t_id, message.chat.id, nick))
    await message.reply(f"✅ {user_link_with_nick(t_id,message.chat.id,t_name)} → <b>{nick}</b>")

# ============================================================
#  РУССКИЕ ПСЕВДОНИМЫ
# ============================================================
@dp.message(F.text)
async def text_aliases(message: types.Message):
    if not message.text: return
    t = message.text.strip().lower()
    if t == "профиль":           return await profile(message)
    if t == "топ":               return await top_cmd(message)
    if t == "работа":            return await work(message)
    if t in ("бонус","ежедневный"): return await daily(message)
    if t == "магазин":           return await shop_cmd(message)
    if t.startswith("казино"):
        b = extract_bet(t)
        if b: message.text = f"/casino {b}"; return await casino_cmd(message)
    if t.startswith("дартс"):
        b = extract_bet(t)
        if b: message.text = f"/darts {b}"; return await darts_cmd(message)
    if t.startswith("монетка"):
        b = extract_bet(t)
        if b: message.text = f"/coinflip {b}"; return await coinflip_cmd(message)
    if t.startswith(("кнб","камень")):
        b = extract_bet(t)
        if b: message.text = f"/rps {b}"; return await rps_cmd(message)
    if t == "кости":     return await cmd_dice(message)
    if t == "баскетбол": return await cmd_basketball(message)
    if t == "футбол":    return await cmd_football(message)
    if t == "боулинг":   return await cmd_bowling(message)

# ============================================================
#  ЗАПУСК
# ============================================================
async def main():
    try: await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e: logging.warning(f"Webhook: {e}")

    try:
        await bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(GROUP_COMMANDS,   scope=BotCommandScopeAllGroupChats())
    except Exception as e: logging.warning(f"Commands: {e}")

    me = await bot.get_me()
    print(f"✅ @{me.username} запущен! (v3 — RIGHT_FORBIDDEN фикс)")

    try:
        chats = db("SELECT chat_id FROM chat_settings WHERE close_time IS NOT NULL", fetch=True)
        for (cid,) in chats: await apply_schedule_now(cid)
    except Exception as e: logging.error(f"Schedule init: {e}")

    asyncio.create_task(scheduler_loop())

    try:
        await dp.start_polling(bot, timeout=60, relax=0.5)
    except Exception as e:
        logging.error(f"Polling: {e}")
        await asyncio.sleep(5)
        await dp.start_polling(bot, timeout=120, relax=1.0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Бот остановлен!")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        time.sleep(5)
        asyncio.run(main())