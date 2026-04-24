# ============================================================
#  VOID HELPER BOT — v5-final (полностью исправленный)
# ============================================================
# Исправления:
# 1. /setwelcome больше не отвечает дважды
# 2. /setwelcome текст — сразу сохраняет
# 3. /setwelcome + медиа в том же сообщении — сразу сохраняет
# 4. /setwelcome без ничего — ждёт следующее сообщение
# 5. Добавлена команда !give @user сумма для основателя
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
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

warnings.filterwarnings('ignore')

TOKEN    = '8203364413:AAHBW_Aek57yZvvSf5JzrYElxLOCky_vnEY'
OWNER_ID = 7173827114
DB_NAME  = 'void_final.db'
LOG_CHANNEL    = '@void_official_chat'
LOG_MESSAGE_ID = 19010

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp  = Dispatcher(storage=storage)

DICE_WAIT = {"🎲": 2, "🎯": 3, "🏀": 4, "⚽": 4, "🎳": 4, "🎰": 4}

# ============================================================
#  FSM для /setwelcome
# ============================================================
class SetWelcomeState(StatesGroup):
    waiting_for_welcome = State()

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
    BotCommand(command="addcoins", description="💰 Выдать монеты (основатель)"),
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
    BotCommand(command="addcoins",        description="💰 Выдать монеты (основатель)"),
]

# ============================================================
#  БАЗА ДАННЫХ
# ============================================================
def db(query, params=(), fetch=False):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch: return cur.fetchall()
        conn.commit()

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
    '''CREATE TABLE IF NOT EXISTS chat_permissions_backup (
        chat_id INTEGER PRIMARY KEY,
        can_send_messages BOOLEAN, can_send_media_messages BOOLEAN,
        can_send_polls BOOLEAN, can_send_other_messages BOOLEAN,
        can_add_web_page_previews BOOLEAN, can_change_info BOOLEAN,
        can_invite_users BOOLEAN, can_pin_messages BOOLEAN, can_manage_topics BOOLEAN)''',
    '''CREATE TABLE IF NOT EXISTS warns_system (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, chat_id INTEGER, reason TEXT, date INTEGER, expires INTEGER)''',
]:
    db(sql)

# Миграция существующих таблиц
try:
    db("ALTER TABLE group_welcome ADD COLUMN welcome_type TEXT DEFAULT 'text'")
except: pass
try:
    db("ALTER TABLE group_welcome ADD COLUMN welcome_file_id TEXT DEFAULT NULL")
except: pass

# ============================================================
#  ПРАВИЛА
# ============================================================
PUNISHMENT_RULES = {
    '18plus':              {'rule':'1.1. 18+ контент',             'warn_days':30,    'mute_hours':4},
    'insult':              {'rule':'1.2. Оскорбления',             'warn_days':30,    'mute_hours':8},
    'conflict':            {'rule':'1.3. Споры и конфликты',       'warn_days':30,    'mute_hours':2},
    'spam':                {'rule':'1.4. Нежелательные сообщения', 'warn_days':30,    'mute_hours':4},
    'mislead':             {'rule':'1.5. Ввод в заблуждение',      'warn_days':30,    'mute_hours':4},
    'admin_beg':           {'rule':'1.6. Выпрашивание админки',    'warn_days':36500, 'mute_hours':0},
    'admin_slander':       {'rule':'1.7. Клевета на админов',      'warn_days':30,    'mute_hours':24},
    'ideas_only':          {'rule':'3.1. Только идеи',             'warn_days':3,     'mute_hours':1},
    'creative_18plus':     {'rule':'4.1. Запрещённый контент',     'warn_days':30,    'mute_hours':4},
    'creative_discussion': {'rule':'4.2. Обсуждение',              'warn_days':7,     'mute_hours':2},
    'creative_ad':         {'rule':'4.3. Реклама',                 'warn_days':30,    'mute_hours':6},
}

def compile_words(word_list):
    return [re.compile(r'\b' + re.escape(w) + r'\b', re.IGNORECASE) for w in word_list]

BAD_WORDS = {
    '18plus': compile_words(['порно','секс','голый','голая','эротика','интим','пенис','влагалище','оральный','минет','куни','трах','ебля','дрочить','мастурбация','член','вагина','сиськи','попка','задница','жопа','хуй','пизда','сексуальный','сексуальная','возбуждает','оргазм','кончить','кончаю','расчленёнка','насилие','убийство','смерть','труп','кровь','жестокость','пытки','избиение','изнасилование','убийца','суицид','самоубийство','повеситься','зарезать','застрелить']),
    'insult': compile_words(['гандон','долбоёб','хуесос','уебок','ебанутый','пидор','чмо','шлюха','проститутка','сука','блядина','мудак','дебил','идиот','лох','урод','тварь','мразь','ничтожество','отброс','скотина','говно','жопа','сучка','даун','аутист','шизофреник','дегенерат']),
    'conflict': compile_words(['политика','путин','зеленский','трамп','байден','выборы','президент','расизм','нацист','фашист','раса','война','армия','всу','сво','мобилизация','фронт','оккупация','религия','церковь','ислам','христианство','иудаизм','буддизм','атеист','гендер','феминизм','лгбт','гей','лесбиянка','бисексуал','трансгендер','наркотики','наркота','кокаин','героин','спайс','соль','наркоман']),
    'spam': [re.compile(r) for r in [r'http[s]?://',r'www\.',r'\.ru\b',r'\.com\b',r'\.org\b',r'\.net\b',r't\.me/',r'telegram\.me',r'vk\.com',r'youtube\.',r'instagram\.',r'tiktok\.',r'discord\.gg']],
    'mislead': compile_words(['выдаю себя за','я админ','я модератор','я владелец','фейк']),
    'admin_beg': compile_words(['дай админку','сделай админом','хочу админку','назначь админом','возьми в админы']),
    'admin_slander': compile_words(['админ плохой','модеры тупые','тупые модеры','администрация дураки','модерация говно','клевета на админов']),
    'ideas_only': compile_words(['обсуждение','поговорить','вопрос','ответ','привет','как дела']),
    'creative_18plus': compile_words(['порно','секс','голый','эротика','расчленёнка','насилие','убийство']),
    'creative_discussion': compile_words(['обсуждение','комментарий','вопрос','ответ']),
    'creative_ad': compile_words(['реклама','самореклама','мой канал','подпишись','instagram','youtube']),
}

# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def detect_gender(name: str) -> int:
    n = name.lower().strip()
    if n in ('саша','женя','валя','слава','никита','вика','ната','тоня','саня'): return 2
    for e in ('а','я','ия','ь'):
        if n.endswith(e): return 1
    return 0

async def is_moderation_enabled(chat_id):
    r = db("SELECT enabled FROM moderation_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return r[0][0] == 1 if r else True

def get_user(uid):
    r = db("SELECT coins,xp,warns,xp_multiplier FROM users WHERE id=?", (uid,), fetch=True)
    if not r:
        db("INSERT INTO users (id) VALUES (?)", (uid,))
        return (500,0,0,1.0)
    return r[0]

def add_coins(uid, amount):
    get_user(uid); db("UPDATE users SET coins=coins+? WHERE id=?", (amount,uid))

def add_xp(uid, amount):
    get_user(uid)
    old = db("SELECT xp FROM users WHERE id=?", (uid,), fetch=True)[0][0]
    db("UPDATE users SET xp=xp+? WHERE id=?", (amount,uid))
    return (old+amount)//100 if old//100 < (old+amount)//100 else None

def user_link(uid, chat_id, default_name):
    r = db("SELECT nickname FROM user_nicknames WHERE user_id=? AND chat_id=?", (uid,chat_id), fetch=True)
    name = r[0][0] if r else default_name
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_mention(uid, chat_id, default_name):
    r = db("SELECT username FROM usernames WHERE user_id=?", (uid,), fetch=True)
    if r and r[0][0]: return f"@{r[0][0]}"
    return f'<a href="tg://user?id={uid}">{default_name}</a>'

def save_username(user: types.User):
    if user and user.username:
        db("INSERT OR REPLACE INTO usernames (username,user_id,name) VALUES (?,?,?)",
           (user.username.lower(), user.id, user.first_name))

async def resolve_target(message: types.Message, args: str = ""):
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name, message.reply_to_message
    for w in args.split():
        if w.startswith("@"):
            username = w[1:]
            r = db("SELECT user_id,name FROM usernames WHERE username=?", (username.lower(),), fetch=True)
            if r: return r[0][0], r[0][1], None
            try:
                c = await bot.get_chat(f"@{username}")
                if c.username:
                    db("INSERT OR REPLACE INTO usernames (username,user_id,name) VALUES (?,?,?)",
                       (c.username.lower(), c.id, c.first_name or username))
                return c.id, c.first_name or username, None
            except: continue
    return None, None, None

async def is_admin(chat_id, user_id) -> bool:
    if user_id == OWNER_ID: return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator","creator")
    except: return False

def parse_duration(s: str) -> int:
    s = s.lower().strip().replace(" ","")
    if 'мес' in s:
        n = re.findall(r'\d+', s); return int(n[0])*30*86400 if n else 300
    if 'год' in s or (s.endswith('г') and re.search(r'\d',s)):
        n = re.findall(r'\d+', s); return int(n[0])*365*86400 if n else 300
    if 'дн' in s or 'день' in s or (s.endswith('д') and re.search(r'\d',s)):
        n = re.findall(r'\d+', s); return int(n[0])*86400 if n else 300
    if 'час' in s or (s.endswith('ч') and re.search(r'\d',s)):
        n = re.findall(r'\d+', s); return int(n[0])*3600 if n else 300
    if 'мин' in s or (s.endswith('м') and re.search(r'\d',s)):
        n = re.findall(r'\d+', s); return int(n[0])*60 if n else 300
    n = re.findall(r'\d+', s); return int(n[0])*60 if n else 300

def fmt_dur(sec: int) -> str:
    if sec >= 31536000: return f"{sec//31536000} г."
    if sec >= 2592000:  return f"{sec//2592000} мес."
    if sec >= 86400:    return f"{sec//86400} дн."
    if sec >= 3600:     return f"{sec//3600} ч."
    return f"{sec//60} мин."

def extract_bet(text: str):
    n = re.findall(r'\d+', text)
    return int(n[0]) if n else None

async def is_chat_closed(chat_id):
    r = db("SELECT is_closed FROM chat_settings WHERE chat_id=?", (chat_id,), fetch=True)
    return bool(r and r[0][0])

# ============================================================
#  ВАРНЫ
# ============================================================
def get_user_warns(uid, chat_id):
    now = int(time.time())
    return db("SELECT id,reason,date,expires FROM warns_system WHERE user_id=? AND chat_id=? AND expires>? ORDER BY date DESC",
              (uid,chat_id,now), fetch=True)

def get_warn_count(uid, chat_id): return len(get_user_warns(uid, chat_id))

def add_warn(uid, chat_id, reason, days=30):
    now = int(time.time())
    db("INSERT INTO warns_system (user_id,chat_id,reason,date,expires) VALUES (?,?,?,?,?)",
       (uid,chat_id,reason,now,now+days*86400))
    return get_warn_count(uid, chat_id)

def clear_warns(uid, chat_id):
    db("DELETE FROM warns_system WHERE user_id=? AND chat_id=?", (uid,chat_id))

# ============================================================
#  ЛОГ
# ============================================================
async def send_log(source, target_id, action, reason, duration="", is_auto=False, admin_user=None):
    try:
        target = await bot.get_chat(target_id)
        if isinstance(source, types.Message):
            chat  = source.chat
            admin = source.from_user
        else:
            chat  = await bot.get_chat(source)
            admin = admin_user
        t  = f"{action}\n\n"
        t += f"👤 Нарушитель: {target.first_name}"
        if target.username: t += f" (@{target.username})"
        t += f"\n🆔 ID: {target.id}\n\n"
        t += "👮 Кто выдал: 🤖 Автомодерация\n" if is_auto else \
             f"👮 Кто выдал: {admin.first_name}" + (f" (@{admin.username})" if admin and admin.username else "") + "\n"
        t += f"\n💬 Чат: {chat.title}"
        if chat.username: t += f" (@{chat.username})"
        t += f"\n📌 Причина: {reason}"
        if duration: t += f"\n⏳ Срок: {duration}"
        await bot.send_message(LOG_CHANNEL, t, reply_to_message_id=LOG_MESSAGE_ID)
    except Exception as e:
        logging.error(f"Лог: {e}")

# ============================================================
#  АВТОМОДЕРАЦИЯ
# ============================================================
async def auto_moderate(message: types.Message):
    if message.chat.type not in ("group","supergroup"): return
    if message.from_user.is_bot: return
    if await is_admin(message.chat.id, message.from_user.id): return
    if not await is_moderation_enabled(message.chat.id): return
    text = (message.text or message.caption or "").lower()
    if not text: return
    tid = message.message_thread_id
    is_ideas    = (tid == 18357)
    is_creative = (tid == 19010)
    violation = rule = None
    for cat, patterns in BAD_WORDS.items():
        for pat in patterns:
            if pat.search(text):
                if is_ideas and cat == 'ideas_only':
                    violation, rule = cat, PUNISHMENT_RULES[cat]; break
                elif is_creative and cat in ('creative_18plus','creative_discussion','creative_ad'):
                    violation, rule = cat, PUNISHMENT_RULES[cat]; break
                elif cat in PUNISHMENT_RULES and not is_ideas and not is_creative:
                    violation, rule = cat, PUNISHMENT_RULES[cat]; break
        if violation: break
    if not violation: return
    uid = message.from_user.id
    cid = message.chat.id
    try: await message.delete()
    except: pass
    wc   = add_warn(uid, cid, f"Автомодерация: {rule['rule']}", rule['warn_days'])
    dur  = 0
    act  = "⚠️ ВАРН (автомодерация)"
    ptxt = f"⚠️ ВАРН #{wc}/3"
    if wc >= 3 and rule['mute_hours'] > 0:
        dur   = rule['mute_hours'] * 3600
        until = int(time.time()) + dur
        db("INSERT OR REPLACE INTO muted (user_id,chat_id,until) VALUES (?,?,?)", (uid,cid,until))
        try:
            await bot.restrict_chat_member(cid, uid,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.fromtimestamp(until, tz=timezone.utc))
        except Exception as e: logging.error(f"Авто-мут: {e}")
        act  = "🔇 МУТ (автомодерация)"
        ptxt = f"🔇 МУТ {rule['mute_hours']} ч. (варн #{wc})"
    try:
        await bot.send_message(uid,
            f"⚠️ <b>Предупреждение — автомодерация</b>\n\n"
            f"📌 Нарушение: {rule['rule']}\n📊 {ptxt}\n💬 Чат: {message.chat.title}")
    except:
        try: await bot.send_message(cid, f"⚠️ Сообщение удалено автомодерацией.\n📌 {rule['rule']}", message_thread_id=tid)
        except: pass
    await send_log(cid, uid, act, rule['rule'], fmt_dur(dur) if dur else "", is_auto=True)

# ============================================================
#  ПРАВА АДМИНИСТРАТОРА
# ============================================================
def get_default_perms() -> dict:
    return {
        'can_promote':       False,
        'can_change_info':   True,
        'can_delete':        True,
        'can_restrict':      True,
        'can_invite':        True,
        'can_pin':           True,
        'can_video_chats':   False,
        'can_manage_topics': True,
    }

async def get_admin_permissions(chat_id, user_id) -> dict:
    r = db("SELECT can_promote,can_change_info,can_delete,can_restrict,can_invite,"
           "can_pin,can_video_chats,can_manage_topics "
           "FROM admin_permissions WHERE chat_id=? AND user_id=?",
           (chat_id,user_id), fetch=True)
    if r:
        keys = ['can_promote','can_change_info','can_delete','can_restrict',
                'can_invite','can_pin','can_video_chats','can_manage_topics']
        return {k: bool(v) for k,v in zip(keys, r[0])}
    return get_default_perms()

def save_perms_db(chat_id, user_id, perms):
    db("INSERT OR REPLACE INTO admin_permissions "
       "(user_id,chat_id,can_promote,can_change_info,can_delete,can_restrict,"
       "can_invite,can_pin,can_video_chats,can_manage_topics) VALUES (?,?,?,?,?,?,?,?,?,?)",
       (user_id,chat_id,perms['can_promote'],perms['can_change_info'],
        perms['can_delete'],perms['can_restrict'],perms['can_invite'],
        perms['can_pin'],perms['can_video_chats'],perms['can_manage_topics']))

async def apply_admin_perms(chat_id, user_id, perms) -> tuple:
    bot_member = await bot.get_chat_member(chat_id, bot.id)
    if bot_member.status != 'administrator' or not bot_member.can_promote_members:
        return False, "❌ Бот не имеет права назначать администраторов!"
    kwargs = {
        'can_manage_chat':      True,
        'can_delete_messages':  perms['can_delete'],
        'can_restrict_members': perms['can_restrict'],
        'can_invite_users':     perms['can_invite'],
        'can_pin_messages':     perms['can_pin'],
        'can_change_info':      perms['can_change_info'],
        'can_promote_members':  perms['can_promote'],
        'can_manage_topics':    perms['can_manage_topics'],
        'can_manage_video_chats': perms['can_video_chats'],
    }
    optional = [
        'can_manage_video_chats',
        'can_promote_members',
        'can_manage_topics',
        'can_pin_messages',
        'can_change_info',
    ]
    while True:
        try:
            await bot.promote_chat_member(chat_id, user_id, **kwargs)
            return True, ""
        except Exception as e:
            err = str(e)
            if 'RIGHT_FORBIDDEN' in err or 'not enough rights' in err.lower():
                removed = False
                for opt in optional:
                    if opt in kwargs:
                        del kwargs[opt]
                        removed = True
                        break
                if not removed:
                    return False, f"❌ Ошибка прав: {err}"
            elif 'CHAT_ADMIN_REQUIRED' in err:
                return False, "❌ Бот не является администратором!"
            elif 'USER_NOT_PARTICIPANT' in err:
                return False, "❌ Пользователь не в чате."
            else:
                return False, f"❌ Ошибка: {err}"

# ============================================================
#  КЛАВИАТУРА АДМИН-ПАНЕЛИ
# ============================================================
def _e(flag): return "✅" if flag else "—"

def admin_panel_kb(uid, chat_id, perms):
    def btn(label, perm):
        return InlineKeyboardButton(
            text=f"{_e(perms.get(perm,False))} {label}",
            callback_data=f"ap|{uid}|{chat_id}|{perm}"
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("Назначение админов", "can_promote")],
        [btn("Профиль группы", "can_change_info"), btn("Удаление смс",  "can_delete")],
        [btn("Баны",           "can_restrict"),    btn("Инвайты",       "can_invite")],
        [btn("Закрепы",        "can_pin"),         btn("Трансляции",    "can_video_chats")],
        [btn("Управление темами", "can_manage_topics")],
        [InlineKeyboardButton(text="🔻 Разжаловать", callback_data=f"ap_rm|{uid}|{chat_id}")],
    ])

# ============================================================
#  УПРАВЛЕНИЕ ЧАТОМ
# ============================================================
async def save_chat_perms(chat_id):
    try:
        c = await bot.get_chat(chat_id)
        p = c.permissions or ChatPermissions(can_send_messages=True)
        db("INSERT OR REPLACE INTO chat_permissions_backup VALUES (?,?,?,?,?,?,?,?,?,?)",
           (chat_id,p.can_send_messages,p.can_send_media_messages,p.can_send_polls,
            p.can_send_other_messages,p.can_add_web_page_previews,p.can_change_info,
            p.can_invite_users,p.can_pin_messages,p.can_manage_topics))
        return True
    except: return False

async def restore_chat_perms(chat_id):
    r = db("SELECT * FROM chat_permissions_backup WHERE chat_id=?", (chat_id,), fetch=True)
    try:
        p = ChatPermissions(
            can_send_messages=bool(r[0][1]),can_send_media_messages=bool(r[0][2]),
            can_send_polls=bool(r[0][3]),can_send_other_messages=bool(r[0][4]),
            can_add_web_page_previews=bool(r[0][5]),can_change_info=bool(r[0][6]),
            can_invite_users=bool(r[0][7]),can_pin_messages=bool(r[0][8]),
            can_manage_topics=bool(r[0][9])
        ) if r else ChatPermissions(can_send_messages=True,can_send_media_messages=True,
                                    can_send_polls=True,can_invite_users=True)
        await bot.set_chat_permissions(chat_id, permissions=p)
        return True
    except: return False

async def close_chat(chat_id):
    await save_chat_perms(chat_id)
    db("UPDATE chat_settings SET is_closed=1 WHERE chat_id=?", (chat_id,))
    try:
        await bot.set_chat_permissions(chat_id, permissions=ChatPermissions(
            can_send_messages=False,can_send_media_messages=False,
            can_send_polls=False,can_send_other_messages=False,
            can_add_web_page_previews=False,can_invite_users=True))
        await bot.send_message(chat_id,"🔒 ЧАТ ЗАКРЫТ")
        return True
    except: return False

async def open_chat(chat_id):
    db("UPDATE chat_settings SET is_closed=0 WHERE chat_id=?", (chat_id,))
    await restore_chat_perms(chat_id)
    await bot.send_message(chat_id,"🔓 ЧАТ ОТКРЫТ")
    return True

# ============================================================
#  РАСПИСАНИЕ
# ============================================================
sent_notif: dict = {}

def msktime(): return datetime.now(timezone(timedelta(hours=3)))

async def apply_schedule_now(chat_id):
    r = db("SELECT close_time,open_time,is_closed FROM chat_settings WHERE chat_id=?", (chat_id,), fetch=True)
    if not r: return
    ct, ot, ic = r[0]
    if not ct or not ot: return
    now = msktime(); nm = now.hour*60+now.minute
    try:
        ch,cm = map(int,ct.split(':')); oh,om = map(int,ot.split(':'))
    except: return
    cl = ch*60+cm; op = oh*60+om
    if cl < op:
        should = cl <= nm < op
        stc = (cl-nm)*60 if nm < cl else (cl+1440-nm)*60
    else:
        should = nm >= cl or nm < op
        stc = (cl+1440-nm)*60 if nm >= cl else 0
    if should and not ic: await close_chat(chat_id)
    elif not should and ic: await open_chat(chat_id)
    if not should and not ic and stc > 0:
        for wt in [3600,1800,900,600,300,60,30,10]:
            if wt <= stc < wt+10:
                key = f"w_{chat_id}_{now.strftime('%Y%m%d')}_{wt}"
                if key not in sent_notif:
                    sent_notif[key] = True
                    ts = f"{wt//3600} час" if wt>=3600 else f"{wt//60} минут" if wt>=60 else f"{wt} секунд"
                    await bot.send_message(chat_id, f"⚠️ Чат закроется через {ts}.")
                break

async def scheduler_loop():
    while True:
        try:
            today = msktime().strftime('%Y%m%d')
            for k in [k for k in list(sent_notif) if today not in k]: del sent_notif[k]
            for (cid,) in db("SELECT chat_id FROM chat_settings WHERE close_time IS NOT NULL", fetch=True):
                await apply_schedule_now(cid)
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
                if await is_admin(cid, uid): return await handler(event, data)
                if db("SELECT 1 FROM banned WHERE user_id=? AND chat_id=?", (uid,cid), fetch=True):
                    try: await event.delete()
                    except: pass
                    return
                r = db("SELECT until FROM muted WHERE user_id=? AND chat_id=?", (uid,cid), fetch=True)
                if r and r[0][0] > int(time.time()):
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
#  МЕНЮ
# ============================================================
def main_menu_kb(username):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль",callback_data="m_profile"),
         InlineKeyboardButton(text="🏆 Топ",callback_data="m_top")],
        [InlineKeyboardButton(text="🛒 Магазин",callback_data="m_shop"),
         InlineKeyboardButton(text="🎮 Игры",callback_data="m_games")],
        [InlineKeyboardButton(text="❤️ RP",callback_data="m_rp"),
         InlineKeyboardButton(text="➕ В группу",url=f"https://t.me/{username}?startgroup=L")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад",callback_data="m_back")]])

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    me = await bot.get_me()
    if message.chat.type != "private":
        tid = message.message_thread_id
        return await bot.send_message(message.chat.id, "✅ VOID Helper активен! /help", message_thread_id=tid)
    await message.answer(
        f"👋 Привет, {get_mention(message.from_user.id,message.chat.id,message.from_user.first_name)}!\n"
        f"Я VOID Helper. /help",
        reply_markup=main_menu_kb(me.username))

@dp.callback_query(F.data=="m_profile")
async def cb_profile(call: types.CallbackQuery):
    uid = call.from_user.id; coins,xp,warns,_ = get_user(uid)
    await call.message.edit_text(
        f"👤 {user_link(uid,call.message.chat.id,call.from_user.first_name)}\n"
        f"⭐ Уровень: {xp//100}\n💰 Монеты: {coins}\n📊 XP: {xp}\n⚠️ Варны: {warns}/3",
        reply_markup=back_kb())
    await call.answer()

@dp.callback_query(F.data=="m_top")
async def cb_top(call: types.CallbackQuery):
    rows = db("SELECT id,coins FROM users ORDER BY coins DESC LIMIT 10",fetch=True)
    if not rows: return await call.message.edit_text("🏆 Пока никого",reply_markup=back_kb())
    medals=["🥇","🥈","🥉"]
    lines=["🏆 Топ монет"]+[f"{medals[i] if i<3 else f'{i+1}.'} {user_link(uid,call.message.chat.id,str(uid))} — {c}💰" for i,(uid,c) in enumerate(rows)]
    await call.message.edit_text("\n".join(lines),reply_markup=back_kb()); await call.answer()

@dp.callback_query(F.data=="m_shop")
async def cb_shop(call: types.CallbackQuery):
    await call.message.edit_text("🛒 Магазин\n1️⃣ Множитель x2 — 500💰\n2️⃣ Сброс работы — 300💰\n\n/buy 1  /buy 2",reply_markup=back_kb()); await call.answer()

@dp.callback_query(F.data=="m_games")
async def cb_games(call: types.CallbackQuery):
    await call.message.edit_text("🎮 Игры\n/casino /darts /coinflip /rps\n⚔️ Дуэли: /dice /basketball /football /bowling",reply_markup=back_kb()); await call.answer()

@dp.callback_query(F.data=="m_rp")
async def cb_rp(call: types.CallbackQuery):
    await call.message.edit_text("❤️ RP: обнять, поцеловать, ударить, погладить\n💍 Браки: +брак, +развод, +пара",reply_markup=back_kb()); await call.answer()

@dp.callback_query(F.data=="m_back")
async def cb_back(call: types.CallbackQuery):
    me = await bot.get_me()
    await call.message.edit_text(f"👋 Привет, {call.from_user.first_name}!\nЯ VOID Helper.",reply_markup=main_menu_kb(me.username)); await call.answer()

# ============================================================
#  ОБНОВЛЁННЫЙ /help
# ============================================================
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    tid = message.message_thread_id
    await bot.send_message(message.chat.id, """
<b>⭐ VOID HELPER — ПОЛНЫЙ ГАЙД</b>

<b>⚖️ Основные правила</b>
1.1. 18+ контент – варн месяц + мут 4 ч
1.2. Оскорбления – варн месяц + мут 8 ч
1.3. Споры/конфликты – варн месяц + мут 2 ч
1.4. Спам/флуд/реклама – варн месяц + мут 4 ч
1.5. Ввод в заблуждение – варн месяц + мут 4 ч
1.6. Выпрашивание админки – варн навсегда
1.7. Клевета на админов – варн месяц + мут 24 ч
3.1. Не по теме в идеях – варн 3 дня + мут 1 ч
4.1–4.3. Нарушения в творчестве – по правилам

<b>🛡 Модерация (только для админов)</b>
• !мут @user 10м причина – замутить
• -размут @user – размутить
• !бан @user 7д причина – забанить
• -разбан @user – разбанить
• !кик @user – кикнуть
• !варн @user причина – выдать варн
• -варн @user – снять 1 варн
• !варны [@user] – просмотр варнов
• -очиститьварны @user – очистить все
• !мутлист / !банлист – список наказанных
• !админ @user – назначить админа + панель прав
• -админ @user – разжаловать

<b>💰 Экономика</b>
• /work – работа (раз в 10 мин)
• /daily – ежедневный бонус
• /shop – магазин
• /buy 1 | /buy 2 – покупка
• /profile /top – профиль и рейтинг
• !give @user 1000 – выдать монеты (основатель)

<b>🎰 Игры</b>
• /casino ставка, /darts ставка
• /coinflip ставка, /rps ставка
• /dice /basketball /football /bowling (дуэли)

<b>💞 RP и браки</b>
• обнять|поцеловать|ударить|погладить @user
• +брак @user / +развод / +пара / +список браков

<b>🔧 Управление чатом</b>
• -чат / +чат – закрыть/открыть чат
• /setautoschedule 23:00 09:00 – автооткрытие
• /check_schedule – статус расписания
• /moderation on|off – вкл/выкл автомодерацию
• /setwelcome – установить приветствие (текст/фото/гиф)

⏱ Длительность наказаний указывается так: 10м, 2ч, 3д, 1мес, 1г.
""", message_thread_id=tid)

# ============================================================
#  ЭКОНОМИКА
# ============================================================
@dp.message(Command("profile"))
async def profile(message: types.Message):
    uid=message.from_user.id; coins,xp,warns,_=get_user(uid)
    await message.answer(
        f"👤 {user_link(uid,message.chat.id,message.from_user.first_name)}\n"
        f"⭐ Уровень: {xp//100}\n💰 Монеты: {coins}\n📊 XP: {xp}\n⚠️ Варны: {warns}/3")

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    rows=db("SELECT id,coins FROM users ORDER BY coins DESC LIMIT 10",fetch=True)
    if not rows: return await message.answer("🏆 Пока никого")
    medals=["🥇","🥈","🥉"]
    lines=["🏆 Топ монет"]+[f"{medals[i] if i<3 else f'{i+1}.'} {user_link(uid,message.chat.id,str(uid))} — {c}💰" for i,(uid,c) in enumerate(rows)]
    await message.answer("\n".join(lines))

@dp.message(Command("work"))
async def work(message: types.Message):
    uid=message.from_user.id
    last=db("SELECT last_work FROM users WHERE id=?",(uid,),fetch=True)[0][0]
    now=int(time.time())
    if now-last<600:
        rem=600-(now-last); return await message.answer(f"⏳ Отдых {rem//60}м {rem%60}с")
    jobs=[("💻 Написал бота",600,1000),("📦 Развёз посылки",400,700),("🚗 Отвёз клиента",500,800)]
    job,mn,mx=random.choice(jobs); pay=random.randint(mn,mx); xpg=random.randint(15,35)
    add_coins(uid,pay); lvl=add_xp(uid,xpg)
    db("UPDATE users SET last_work=? WHERE id=?",(now,uid))
    await message.answer(f"⛏ {job}\n💰 +{pay}💰\n✨ +{xpg} XP"+(f"\n🎉 {lvl} уровень!" if lvl else ""))

@dp.message(Command("daily"))
async def daily(message: types.Message):
    uid=message.from_user.id; get_user(uid)
    now=int(time.time()); last=db("SELECT last_daily FROM users WHERE id=?",(uid,),fetch=True)[0][0]
    if now-last<86400:
        rem=86400-(now-last); return await message.answer(f"🎁 Уже получен. Следующий через {rem//3600}ч {(rem%3600)//60}мин")
    b=random.randint(300,700); add_coins(uid,b); lvl=add_xp(uid,50)
    db("UPDATE users SET last_daily=? WHERE id=?",(now,uid))
    await message.answer(f"🎁 Бонус!\n💰 +{b}💰\n✨ +50 XP"+(f"\n🎉 {lvl} уровень!" if lvl else ""))

@dp.message(Command("shop"))
async def shop_cmd(message: types.Message):
    await message.answer("🛒 Магазин\n1️⃣ Множитель x2 — 500💰\n2️⃣ Сброс работы — 300💰\n\n/buy 1  /buy 2")

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    args=message.text.split()
    if len(args)<2: return await message.answer("❌ /buy 1 или /buy 2")
    try: item=int(args[1])
    except: return await message.answer("❌ Некорректный номер")
    uid=message.from_user.id; coins,_,_,_=get_user(uid)
    if item==1:
        if coins<500: return await message.answer("❌ Нужно 500💰")
        add_coins(uid,-500); db("UPDATE users SET xp_multiplier=2.0 WHERE id=?",(uid,))
        asyncio.create_task(reset_mult(uid,3600)); await message.answer("✨ Множитель x2 на 1 час!")
    elif item==2:
        if coins<300: return await message.answer("❌ Нужно 300💰")
        add_coins(uid,-300); db("UPDATE users SET last_work=0 WHERE id=?",(uid,))
        await message.answer("⚡ Кулдаун работы сброшен!")
    else: await message.answer("❌ Неверный номер")

async def reset_mult(uid,delay):
    await asyncio.sleep(delay); db("UPDATE users SET xp_multiplier=1.0 WHERE id=?",(uid,))

# ============================================================
#  КОМАНДЫ ВЫДАЧИ МОНЕТ (основатель)
# ============================================================

# /addcoins @user сумма
@dp.message(Command("addcoins"))
async def addcoins_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Только для основателя!")
    args = message.text.split()
    if len(args) < 3:
        return await message.reply("Использование: /addcoins @user сумма")
    target = None
    amount = None
    for w in args[1:]:
        if w.startswith("@"):
            target = w
        else:
            try: amount = int(w)
            except: pass
    if target is None or amount is None:
        return await message.reply("❌ Формат: /addcoins @user 1000")
    uid,name,_ = await resolve_target(message, target)
    if not uid: return await message.reply("❌ Пользователь не найден.")
    add_coins(uid, amount)
    await message.reply(f"✅ {user_link(uid, message.chat.id, name)} получил {amount} монет.")

# !give @user сумма (альтернативная команда)
@dp.message(F.text.lower().regexp(r'^!\s*give\s+'))
async def give_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Только для основателя!")
    
    # Убираем !give из текста
    text = re.sub(r'^!\s*give\s+', '', message.text, flags=re.IGNORECASE).strip()
    if not text:
        return await message.reply("❌ Использование: !give @user 1000")
    
    # Ищем @username и сумму
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
        return await message.reply("❌ Укажи @username пользователя!")
    if not amount:
        return await message.reply("❌ Укажи сумму для выдачи!")
    
    uid, name, _ = await resolve_target(message, target)
    if not uid:
        return await message.reply("❌ Пользователь не найден!")
    
    add_coins(uid, amount)
    await message.reply(f"✅ {user_link(uid, message.chat.id, name)} получил {amount} монет от основателя!")

# ============================================================
#  ИГРЫ — ФИКС ВЕТОК + reply
# ============================================================
async def check_bet(message, bet, min_bet=10):
    uid=message.from_user.id; coins,_,_,_=get_user(uid)
    if bet<min_bet:
        await bot.send_message(message.chat.id,f"❌ Мин. ставка: {min_bet}",message_thread_id=tid(message),
                               reply_to_message_id=message.message_id)
        return None
    if bet>coins:
        await bot.send_message(message.chat.id,f"❌ У тебя {coins}💰",message_thread_id=tid(message),
                               reply_to_message_id=message.message_id)
        return None
    add_coins(uid,-bet); return uid

def tid(message): return message.message_thread_id

@dp.message(Command("casino"))
async def casino_cmd(message: types.Message):
    bet=extract_bet(message.text)
    if not bet:
        return await bot.send_message(message.chat.id,"🎰 /casino 100",message_thread_id=tid(message),
                                      reply_to_message_id=message.message_id)
    uid=await check_bet(message,bet,10)
    if not uid: return
    dice_msg=await bot.send_dice(message.chat.id,emoji="🎰",message_thread_id=tid(message),
                                 reply_to_message_id=message.message_id)
    await asyncio.sleep(DICE_WAIT["🎰"])
    v=dice_msg.dice.value
    if v==64:   add_coins(uid,bet*10); add_xp(uid,150); txt=f"🎉 ДЖЕКПОТ! +{bet*10}💰"
    elif v>=50: add_coins(uid,bet*4);  add_xp(uid,40);  txt=f"🎰 КРУПНО! +{bet*4}💰"
    elif v>=30: add_coins(uid,bet*2);  add_xp(uid,15);  txt=f"🎰 ВЫИГРЫШ! +{bet*2}💰"
    elif v>=15: add_coins(uid,bet);                      txt=f"🎰 Возврат {bet}💰"
    else:                                                 txt=f"😞 Проиграл {bet}💰"
    await bot.send_message(message.chat.id, txt, message_thread_id=tid(message),
                           reply_to_message_id=dice_msg.message_id)

@dp.message(Command("darts"))
async def darts_cmd(message: types.Message):
    bet=extract_bet(message.text)
    if not bet:
        return await bot.send_message(message.chat.id,"🎯 /darts 50",message_thread_id=tid(message),
                                      reply_to_message_id=message.message_id)
    uid=await check_bet(message,bet,10)
    if not uid: return
    dice_msg=await bot.send_dice(message.chat.id,emoji="🎯",message_thread_id=tid(message),
                                 reply_to_message_id=message.message_id)
    await asyncio.sleep(DICE_WAIT["🎯"])
    v=dice_msg.dice.value
    if v==6:   add_coins(uid,bet*5); txt=f"🎯 БУЛЛ-АЙ! +{bet*5}💰"
    elif v==5: add_coins(uid,bet*3); txt=f"🎯 ОТЛИЧНО! +{bet*3}💰"
    elif v==4: add_coins(uid,bet*2); txt=f"🎯 ХОРОШО! +{bet*2}💰"
    elif v==3: add_coins(uid,bet);   txt=f"🎯 Возврат {bet}💰"
    else:                             txt=f"😞 Мимо! -{bet}💰"
    await bot.send_message(message.chat.id, txt, message_thread_id=tid(message),
                           reply_to_message_id=dice_msg.message_id)

@dp.message(Command("coinflip"))
async def coinflip_cmd(message: types.Message):
    bet=extract_bet(message.text)
    if not bet:
        return await bot.send_message(message.chat.id,"🪙 /coinflip 30",message_thread_id=tid(message),
                                      reply_to_message_id=message.message_id)
    uid=await check_bet(message,bet,10)
    if not uid: return
    result=random.choice(["орёл","решка"]); guess=random.choice(["орёл","решка"])
    if result==guess: add_coins(uid,bet*2); txt=f"🪙 {result}!\n🎉 +{bet*2}💰"
    else:                                   txt=f"🪙 {result}!\n😞 -{bet}💰"
    await bot.send_message(message.chat.id, txt, message_thread_id=tid(message),
                           reply_to_message_id=message.message_id)

@dp.message(Command("rps"))
async def rps_cmd(message: types.Message):
    bet=extract_bet(message.text)
    if not bet:
        return await bot.send_message(message.chat.id,"✊ /rps 15",message_thread_id=tid(message),
                                      reply_to_message_id=message.message_id)
    uid=await check_bet(message,bet,10)
    if not uid: return
    await bot.send_message(message.chat.id,"✊ Камень, ножницы или бумага? (15 сек)",message_thread_id=tid(message),
                           reply_to_message_id=message.message_id)
    try:
        ans=await bot.wait_for("message",timeout=15.0,
            check=lambda m: m.from_user.id==uid and m.chat.id==message.chat.id
                            and m.text and m.text.lower() in ["камень","ножницы","бумага"])
        u=ans.text.lower(); bc=random.choice(["камень","ножницы","бумага"])
        if u==bc: add_coins(uid,bet); txt=f"🤝 Ничья! {bc}\nВозврат {bet}💰"
        elif (u=="камень" and bc=="ножницы") or (u=="ножницы" and bc=="бумага") or (u=="бумага" and bc=="камень"):
            add_coins(uid,bet*2); txt=f"🎉 Победа! +{bet*2}💰"
        else: txt=f"😞 Поражение! -{bet}💰"
    except:
        add_coins(uid,bet); txt="⏰ Время вышло! Возврат"
    await bot.send_message(message.chat.id, txt, message_thread_id=tid(message),
                           reply_to_message_id=message.message_id)

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

def duel_kb(game_type, ch_id, cid):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принять",  callback_data=f"da_{game_type}_{ch_id}_{cid}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"dd_{game_type}_{ch_id}"),
    ]])

@dp.message(Command("dice"))
async def cmd_dice(m): await start_duel(m,"dice")
@dp.message(Command("basketball"))
async def cmd_basketball(m): await start_duel(m,"basketball")
@dp.message(Command("football"))
async def cmd_football(m): await start_duel(m,"football")
@dp.message(Command("bowling"))
async def cmd_bowling(m): await start_duel(m,"bowling")

async def start_duel(message: types.Message, game_type: str):
    if not message.reply_to_message:
        return await bot.send_message(message.chat.id,"❌ Ответь на сообщение соперника!",message_thread_id=tid(message),
                                      reply_to_message_id=message.message_id)
    ch=message.from_user; opp=message.reply_to_message.from_user
    if ch.id==opp.id:  return await bot.send_message(message.chat.id,"❌ Нельзя с собой!",message_thread_id=tid(message))
    if opp.is_bot:     return await bot.send_message(message.chat.id,"❌ Нельзя с ботом!",message_thread_id=tid(message))
    cid=message.chat.id; key=f"{cid}_{ch.id}_{opp.id}"
    if key in active_duels: return await bot.send_message(message.chat.id,"⚠️ Уже вызвали!",message_thread_id=tid(message))
    active_duels[key]={"thread_id": tid(message)}
    g=DUEL_GAMES[game_type]
    await bot.send_message(message.chat.id,
        f"{g['emoji']} {g['name']}\n\n"
        f"{user_link(ch.id,cid,ch.first_name)} вызывает {user_link(opp.id,cid,opp.first_name)}!",
        message_thread_id=tid(message), reply_markup=duel_kb(game_type,ch.id,cid))

@dp.callback_query(F.data.startswith("da_"))
async def duel_accept(call: types.CallbackQuery):
    parts=call.data.split("_"); game_type=parts[1]; ch_id=int(parts[2]); cid=int(parts[3])
    opp_id=call.from_user.id; key=f"{cid}_{ch_id}_{opp_id}"
    if key not in active_duels: return await call.answer("❌ Устарело!",show_alert=True)
    thread_id=active_duels[key].get("thread_id")
    try: await call.message.delete()
    except: pass
    await bot.send_message(cid,f"✅ {user_link(opp_id,cid,call.from_user.first_name)} принял(а)!",
                           message_thread_id=thread_id)
    await run_duel(cid, ch_id, opp_id, game_type, thread_id)

@dp.callback_query(F.data.startswith("dd_"))
async def duel_decline(call: types.CallbackQuery):
    parts=call.data.split("_"); ch_id=int(parts[2]); opp_id=call.from_user.id; cid=call.message.chat.id
    active_duels.pop(f"{cid}_{ch_id}_{opp_id}",None)
    await call.message.edit_text(f"❌ {user_link(opp_id,cid,call.from_user.first_name)} отклонил(а)!")

async def run_duel(cid, p1, p2, game_type, thread_id):
    g=DUEL_GAMES[game_type]
    p1m=await bot.get_chat_member(cid,p1); p2m=await bot.get_chat_member(cid,p2)
    p1n,p2n=p1m.user.first_name,p2m.user.first_name
    msg=await bot.send_message(cid,
        f"{g['emoji']} {g['name']}\n🆚 {user_link(p1,cid,p1n)} vs {user_link(p2,cid,p2n)}\n\n"
        f"🎲 {user_link(p1,cid,p1n)} бросает...",
        message_thread_id=thread_id)
    d1=await bot.send_dice(cid,emoji="🎲",message_thread_id=thread_id)
    await asyncio.sleep(DICE_WAIT["🎲"]); s1=d1.dice.value
    await msg.edit_text(
        f"{g['emoji']} {g['name']}\n🆚 {user_link(p1,cid,p1n)}: {s1}\n"
        f"{user_link(p2,cid,p2n)} бросает...")
    d2=await bot.send_dice(cid,emoji="🎲",message_thread_id=thread_id)
    await asyncio.sleep(DICE_WAIT["🎲"]); s2=d2.dice.value
    w_id=p1 if s1>s2 else p2 if s2>s1 else None
    w_nm=p1n if s1>s2 else p2n if s2>s1 else None
    if w_id:
        add_coins(w_id,150); add_xp(w_id,30)
        await msg.edit_text(
            f"{g['emoji']} {g['name']}\n\n{p1n}: {s1}\n{p2n}: {s2}\n\n"
            f"🏆 {user_link(w_id,cid,w_nm)}!\n💰 +150, ✨ +30 XP")
    else:
        await msg.edit_text(f"{g['emoji']} {g['name']}\n\n{p1n}: {s1}\n{p2n}: {s2}\n\n🤝 НИЧЬЯ!")
    active_duels.pop(f"{cid}_{p1}_{p2}",None)

# ============================================================
#  ПРИВЕТСТВИЯ (поддержка фото/гиф/видео/текст)
# ============================================================
def gsfx(g): return "ёл" if g==0 else "ла" if g==1 else "ли"

def proc_welcome(tmpl,name,mention,sfx):
    r=tmpl.replace("{name}",name).replace("{имя}",name)\
          .replace("{mention}",mention).replace("{упоминание}",mention)
    for m in re.findall(r'вош[\(\{][^\)\}]+[\)\}]',r):
        r=r.replace(m,"вошёл" if sfx=="ёл" else "вошла" if sfx=="ла" else "вошли")
    return r

async def get_gender(uid,name):
    r=db("SELECT gender FROM user_gender WHERE user_id=?",(uid,),fetch=True)
    if r: return r[0][0]
    g=detect_gender(name)
    if g==2: g=0
    db("INSERT OR REPLACE INTO user_gender (user_id,gender) VALUES (?,?)",(uid,g))
    return g

async def send_welcome_message(chat_id, member, thread_id):
    r = db("SELECT welcome_text, welcome_type, welcome_file_id FROM group_welcome WHERE chat_id=?",
           (chat_id,), fetch=True)
    
    if not r:
        tmpl = "👋 Добро пожаловать, {упоминание}!\nТы вош{ла|ёл|ли} в наш чат."
        welcome_type = "text"
        welcome_text = tmpl
        file_id = None
    else:
        welcome_text, welcome_type, file_id = r[0]
        if not welcome_text:
            welcome_text = "👋 Добро пожаловать, {упоминание}!\nТы вош{ла|ёл|ли} в наш чат."
        if not welcome_type:
            welcome_type = "text"
    
    g = await get_gender(member.id, member.first_name)
    mention = get_mention(member.id, chat_id, member.first_name)
    sfx = gsfx(g)
    
    if welcome_text and welcome_type in ["text", "photo", "video", "animation", "gif"]:
        caption = proc_welcome(welcome_text, member.first_name, mention, sfx)
    else:
        caption = None
    
    try:
        if welcome_type == "text" or not file_id:
            await bot.send_message(chat_id, caption or welcome_text, message_thread_id=thread_id)
        elif welcome_type == "photo":
            await bot.send_photo(chat_id, file_id, caption=caption, message_thread_id=thread_id)
        elif welcome_type in ["animation", "gif"]:
            await bot.send_animation(chat_id, file_id, caption=caption, message_thread_id=thread_id)
        elif welcome_type == "video":
            await bot.send_video(chat_id, file_id, caption=caption, message_thread_id=thread_id)
        elif welcome_type == "sticker":
            await bot.send_sticker(chat_id, file_id, message_thread_id=thread_id)
            if caption and caption != welcome_text:
                await bot.send_message(chat_id, caption, message_thread_id=thread_id)
        elif welcome_type == "voice":
            await bot.send_voice(chat_id, file_id, caption=caption, message_thread_id=thread_id)
        elif welcome_type == "video_note":
            await bot.send_video_note(chat_id, file_id, message_thread_id=thread_id)
            if caption and caption != welcome_text:
                await bot.send_message(chat_id, caption, message_thread_id=thread_id)
        else:
            await bot.send_message(chat_id, caption or welcome_text, message_thread_id=thread_id)
    except Exception as e:
        logging.error(f"Ошибка отправки приветствия: {e}")
        try:
            await bot.send_message(chat_id, caption or "👋 Добро пожаловать!", message_thread_id=thread_id)
        except:
            pass

@dp.message(F.new_chat_members)
async def welcome_new(message: types.Message):
    cid = message.chat.id
    me_id = (await bot.get_me()).id
    for member in message.new_chat_members:
        if member.id == me_id:
            continue
        await send_welcome_message(cid, member, message.message_thread_id)

# ============================================================
#  /setwelcome — ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ
# ============================================================

@dp.message(Command("setwelcome"))
async def set_welcome_cmd(message: types.Message, state: FSMContext):
    if not await mod_guard(message):
        return
    
    # Сбрасываем предыдущее состояние
    await state.clear()
    
    # Проверяем, есть ли медиа В СООБЩЕНИИ С КОМАНДОЙ
    has_media = (
        message.photo or 
        message.animation or 
        message.video or
        message.sticker or 
        message.voice or 
        message.video_note
    )
    
    # Получаем текст после команды (если есть)
    full_text = message.text or message.caption or ""
    # Убираем /setwelcome и всё что до него
    text_after = re.sub(r'.*?/setwelcome\s*', '', full_text, flags=re.IGNORECASE).strip()
    
    # Если есть медиа ИЛИ есть текст после команды - сохраняем сразу
    if has_media or text_after:
        caption = text_after if text_after else (message.caption or "")
        await save_welcome_from_message(message, caption)
        return
    
    # Если ничего нет — ждём следующее сообщение
    await state.set_state(SetWelcomeState.waiting_for_welcome)
    await message.reply(
        "📸 <b>Отправь приветствие следующим сообщением!</b>\n\n"
        "Это может быть:\n"
        "• Текст (можно с шаблонами {имя}, {упоминание}, вош{ла|ёл|ли})\n"
        "• Фото (с подписью или без)\n"
        "• Гифка / анимация\n"
        "• Видео\n"
        "• Стикер\n"
        "• Голосовое сообщение\n"
        "• Видеокружок\n\n"
        "⏳ У тебя 60 секунд."
    )


@dp.message(SetWelcomeState.waiting_for_welcome)
async def set_welcome_receive(message: types.Message, state: FSMContext):
    if not await mod_guard(message):
        await state.clear()
        return
    
    # Если это другая команда — отменяем
    if message.text and message.text.startswith('/'):
        await state.clear()
        return
    
    caption = message.text or message.caption or ""
    await save_welcome_from_message(message, caption)
    await state.clear()


async def save_welcome_from_message(message: types.Message, caption: str):
    """Сохраняет приветствие из сообщения"""
    chat_id = message.chat.id
    welcome_type = "text"
    file_id = None
    
    # Определяем тип контента
    if message.photo:
        welcome_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.animation:
        welcome_type = "animation"
        file_id = message.animation.file_id
    elif message.video:
        welcome_type = "video"
        file_id = message.video.file_id
    elif message.sticker:
        welcome_type = "sticker"
        file_id = message.sticker.file_id
    elif message.voice:
        welcome_type = "voice"
        file_id = message.voice.file_id
    elif message.video_note:
        welcome_type = "video_note"
        file_id = message.video_note.file_id
    elif message.text:
        welcome_type = "text"
        file_id = None
    else:
        await message.reply("❌ Неподдерживаемый тип сообщения. Попробуй ещё раз /setwelcome")
        return
    
    # Если подпись не задана, ставим стандартный текст
    if not caption:
        caption = "👋 Добро пожаловать, {упоминание}!"
    
    # Сохраняем в базу
    db("INSERT OR REPLACE INTO group_welcome (chat_id, welcome_text, welcome_type, welcome_file_id) VALUES (?,?,?,?)",
       (chat_id, caption, welcome_type, file_id))
    
    type_names = {
        "text": "📝 Текст",
        "photo": "🖼 Фото",
        "animation": "🎞 Гифка",
        "video": "🎬 Видео",
        "sticker": "⭐ Стикер",
        "voice": "🎤 Голосовое",
        "video_note": "🔵 Видеокружок",
    }
    await message.reply(f"✅ Приветствие сохранено! Тип: {type_names.get(welcome_type, welcome_type)}")


# ============================================================
#  МОДЕРАЦИЯ
# ============================================================
async def mod_guard(message) -> bool:
    if message.chat.type not in ("group","supergroup"): return False
    if not await is_admin(message.chat.id,message.from_user.id):
        await message.reply("❌ Только для администраторов"); return False
    return True

def parse_args(args_text, has_reply):
    if not has_reply:
        args_text=" ".join(p for p in args_text.split() if not p.startswith("@"))
    words=args_text.split(); dur_str=None; reason_parts=[]; i=0
    while i<len(words):
        w=words[i]
        if re.match(r'^\d+$',w) and i+1<len(words) and re.match(r'^(м|мин|ч|час|д|дн|день|мес|г|год)',words[i+1].lower()):
            dur_str=w+words[i+1]; i+=2; continue
        if re.search(r'\d+[мчдг]|мин|час|дн|мес|год',w.lower()):
            dur_str=w; i+=1; continue
        reason_parts.append(w); i+=1
    return dur_str or "1ч", " ".join(reason_parts) or "нарушение правил"

@dp.message(F.text.lower().regexp(r'^!\s*мут'))
async def mute_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^!\s*мут\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!\n!мут @user 10м причина")
    if await is_admin(message.chat.id,uid): return await message.reply("❌ Нельзя замутить администратора!")
    dur_str,reason=parse_args(args,bool(message.reply_to_message))
    sec=parse_duration(dur_str); until=int(time.time())+sec
    db("INSERT OR REPLACE INTO muted (user_id,chat_id,until) VALUES (?,?,?)",(uid,message.chat.id,until))
    warns=get_warn_count(uid,message.chat.id)
    try:
        if message.reply_to_message:
            try: await message.reply_to_message.delete()
            except: pass
        await bot.restrict_chat_member(message.chat.id,uid,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=datetime.fromtimestamp(until,tz=timezone.utc))
        await message.reply(f"🔇 МУТ\n👤 {user_link(uid,message.chat.id,name)}\n⏳ {fmt_dur(sec)}\n📌 {reason}"
                            +(f"\n⚠️ Варнов: {warns}" if warns else ""))
        await send_log(message,uid,'🔇 МУТ',reason,fmt_dur(sec))
    except Exception as e: await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().regexp(r'^!\s*бан'))
async def ban_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^!\s*бан\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!\n!бан @user 7д причина")
    if await is_admin(message.chat.id,uid): return await message.reply("❌ Нельзя забанить администратора!")
    dur_str,reason=parse_args(args,bool(message.reply_to_message))
    warns=get_warn_count(uid,message.chat.id)
    db("INSERT OR IGNORE INTO banned (user_id,chat_id) VALUES (?,?)",(uid,message.chat.id))
    try:
        if message.reply_to_message:
            try: await message.reply_to_message.delete()
            except: pass
        await bot.ban_chat_member(message.chat.id,uid)
        sec=parse_duration(dur_str)
        if dur_str!="1ч" or sec!=3600:
            await message.reply(f"🚫 БАН\n👤 {user_link(uid,message.chat.id,name)}\n⏳ {fmt_dur(sec)}\n📌 {reason}"
                                +(f"\n⚠️ Варнов: {warns}" if warns else ""))
            asyncio.create_task(unban_after(uid,message.chat.id,sec))
            await send_log(message,uid,'🚫 БАН',reason,fmt_dur(sec))
        else:
            await message.reply(f"🚫 БАН НАВСЕГДА\n👤 {user_link(uid,message.chat.id,name)}\n📌 {reason}"
                                +(f"\n⚠️ Варнов: {warns}" if warns else ""))
            await send_log(message,uid,'🚫 БАН',reason,"навсегда")
    except Exception as e: await message.reply(f"❌ Ошибка: {e}")

async def unban_after(uid,chat_id,delay):
    await asyncio.sleep(delay)
    db("DELETE FROM banned WHERE user_id=? AND chat_id=?",(uid,chat_id))
    try: await bot.unban_chat_member(chat_id,uid)
    except: pass

@dp.message(F.text.lower().regexp(r'^!\s*варн'))
async def give_warn_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^!\s*варн\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    if await is_admin(message.chat.id,uid): return await message.reply("❌ Нельзя варнить администратора!")
    reason=(args if message.reply_to_message else " ".join(p for p in args.split() if not p.startswith("@"))) or "нарушение правил"
    if message.reply_to_message:
        try: await message.reply_to_message.delete()
        except: pass
    wc=add_warn(uid,message.chat.id,reason,30)
    await message.reply(f"⚠️ ПРЕДУПРЕЖДЕНИЕ\n👤 {user_link(uid,message.chat.id,name)}\n📌 {reason}\n⚠️ ВАРН #{wc}/3")
    await send_log(message,uid,'⚠️ ВАРН',reason)

@dp.message(F.text.lower().regexp(r'^-\s*размут'))
async def unmute_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^-\s*размут\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    db("DELETE FROM muted WHERE user_id=? AND chat_id=?",(uid,message.chat.id))
    try:
        await bot.restrict_chat_member(message.chat.id,uid,permissions=ChatPermissions(
            can_send_messages=True,can_send_media_messages=True,can_send_polls=True,
            can_send_other_messages=True,can_add_web_page_previews=True,can_invite_users=True))
    except: pass
    await message.reply(f"✅ {user_link(uid,message.chat.id,name)} размучен.")

@dp.message(F.text.lower().regexp(r'^!\s*мутлист'))
async def mutelist_cmd(message: types.Message):
    if not await mod_guard(message): return
    rows=db("SELECT user_id,until FROM muted WHERE chat_id=? AND until>? ORDER BY until",
            (message.chat.id,int(time.time())),fetch=True)
    if not rows: return await message.reply("📋 Замученных нет.")
    lines=["📋 ЗАМУЧЕННЫЕ:"]
    for uid,until in rows[:20]:
        try:
            u=await bot.get_chat(uid)
            lines.append(f"• {user_link(uid,message.chat.id,u.first_name)} — до {datetime.fromtimestamp(until).strftime('%d.%m %H:%M')}")
        except: lines.append(f"• ID {uid} (недоступен)")
    await message.reply("\n".join(lines))

@dp.message(F.text.lower().regexp(r'^-\s*разбан'))
async def unban_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^-\s*разбан\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid: return await message.reply("❌ Укажи @юзертег!")
    db("DELETE FROM banned WHERE user_id=? AND chat_id=?",(uid,message.chat.id))
    try: await bot.unban_chat_member(message.chat.id,uid)
    except: pass
    await message.reply(f"✅ {user_link(uid,message.chat.id,name)} разбанен.")

@dp.message(F.text.lower().regexp(r'^!\s*банлист'))
async def banlist_cmd(message: types.Message):
    if not await mod_guard(message): return
    rows=db("SELECT user_id FROM banned WHERE chat_id=?",(message.chat.id,),fetch=True)
    if not rows: return await message.reply("📋 Забаненных нет.")
    lines=["📋 ЗАБАНЕННЫЕ:"]
    for (uid,) in rows[:20]:
        try:
            u=await bot.get_chat(uid)
            lines.append(f"• {user_link(uid,message.chat.id,u.first_name)}")
        except: lines.append(f"• ID {uid} (недоступен)")
    await message.reply("\n".join(lines))

@dp.message(F.text.lower().regexp(r'^!\s*кик'))
async def kick_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^!\s*кик\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    if await is_admin(message.chat.id,uid): return await message.reply("❌ Нельзя кикнуть администратора!")
    try:
        if message.reply_to_message:
            try: await message.reply_to_message.delete()
            except: pass
        await bot.ban_chat_member(message.chat.id,uid)
        await asyncio.sleep(0.5)
        await bot.unban_chat_member(message.chat.id,uid)
        await message.reply(f"👢 {user_link(uid,message.chat.id,name)} кикнут.")
        await send_log(message,uid,'👢 КИК',"нарушение правил")
    except Exception as e: await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.text.lower().regexp(r'^-\s*варн\b'))
async def remove_warn_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^-\s*варн\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    warns=get_user_warns(uid,message.chat.id)
    if not warns: return await message.reply(f"❌ У {user_link(uid,message.chat.id,name)} нет варнов.")
    db("DELETE FROM warns_system WHERE id=?",(warns[0][0],))
    await message.reply(f"✅ Снят 1 варн с {user_link(uid,message.chat.id,name)}. Осталось: {len(warns)-1}")

@dp.message(F.text.lower().regexp(r'^!\s*варны'))
async def warnlist_cmd(message: types.Message):
    args=re.sub(r'^!\s*варны\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if uid and uid!=message.from_user.id:
        if not await is_admin(message.chat.id,message.from_user.id):
            return await message.reply("❌ Только администраторы могут смотреть чужие варны!")
    if not uid: uid=message.from_user.id; name=message.from_user.first_name
    warns=get_user_warns(uid,message.chat.id)
    if not warns: return await message.reply(f"✅ У {user_link(uid,message.chat.id,name)} нет варнов.")
    lines=[f"📋 ВАРНЫ: {user_link(uid,message.chat.id,name)}",f"📊 Всего: {len(warns)}","","История:"]
    for w in warns[:10]:
        lines.append(f"• {datetime.fromtimestamp(w[2]).strftime('%d.%m.%Y')}: {w[1]}")
    await message.reply("\n".join(lines))

@dp.message(F.text.lower().regexp(r'^-\s*очиститьварны'))
async def clear_warns_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^-\s*очиститьварны\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    clear_warns(uid,message.chat.id)
    await message.reply(f"✅ Варны {user_link(uid,message.chat.id,name)} очищены.")

# ============================================================
#  КОМАНДЫ АДМИН-ПАНЕЛИ
# ============================================================
@dp.message(F.text.lower().regexp(r'^[!+]\s*(админ|тг)'))
async def give_admin_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^[!+]\s*(админ|тг)\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid:
        return await message.reply("❌ Ответь на сообщение или укажи @юзертег!\n!админ @user")
    cid=message.chat.id
    try:
        member=await bot.get_chat_member(cid,uid)
        if member.status in ("administrator","creator"):
            return await message.reply(f"❌ {name} уже администратор.")
    except Exception as e:
        return await message.reply(f"❌ Ошибка: {e}")
    perms=get_default_perms()
    ok,err=await apply_admin_perms(cid,uid,perms)
    if not ok: return await message.reply(err)
    save_perms_db(cid,uid,perms)
    tag=f"@{message.chat.username}" if message.chat.username else message.chat.title
    await message.reply(
        f"<b>🛡 Панель прав администратора</b>\n\n"
        f"👤 {user_link(uid,cid,name)}\n💬 Чат: {tag}\n🕐 {datetime.now().strftime('%H:%M')}\n\n"
        f"Нажимайте кнопки для изменения прав:",
        reply_markup=admin_panel_kb(uid,cid,perms))

@dp.callback_query(F.data.startswith("ap|"))
async def toggle_admin_perm(call: types.CallbackQuery):
    parts=call.data.split("|")
    if len(parts)<4: return await call.answer("❌ Ошибка",show_alert=True)
    uid=int(parts[1]); chat_id=int(parts[2]); perm=parts[3]
    if not await is_admin(chat_id,call.from_user.id):
        return await call.answer("❌ Только для администраторов!",show_alert=True)
    perms=await get_admin_permissions(chat_id,uid)
    if perm not in perms: return await call.answer("❌ Неизвестное право",show_alert=True)
    perms[perm]=not perms[perm]
    ok,err=await apply_admin_perms(chat_id,uid,perms)
    if ok:
        save_perms_db(chat_id,uid,perms)
        try: await call.message.edit_reply_markup(reply_markup=admin_panel_kb(uid,chat_id,perms))
        except: pass
        await call.answer("✅ включено" if perms[perm] else "❌ выключено")
    else:
        perms[perm]=not perms[perm]
        await call.answer(err,show_alert=True)

@dp.callback_query(F.data.startswith("ap_rm|"))
async def remove_admin_cb(call: types.CallbackQuery):
    parts=call.data.split("|"); uid=int(parts[1]); chat_id=int(parts[2])
    if not await is_admin(chat_id,call.from_user.id):
        return await call.answer("❌ Только для администраторов!",show_alert=True)
    try:
        await bot.promote_chat_member(chat_id,uid,
            can_manage_chat=False,can_delete_messages=False,
            can_restrict_members=False,can_invite_users=False,
            can_pin_messages=False,can_change_info=False,
            can_promote_members=False,can_manage_topics=False,
            can_manage_video_chats=False)
        db("DELETE FROM admin_permissions WHERE user_id=? AND chat_id=?",(uid,chat_id))
        await call.message.edit_text(f"🔻 Администратор разжалован. (ID: {uid})")
        await call.answer("✅ Разжалован")
    except Exception as e: await call.answer(f"❌ {e}",show_alert=True)

@dp.message(F.text.lower().regexp(r'^-\s*админ'))
async def remove_admin_cmd(message: types.Message):
    if not await mod_guard(message): return
    args=re.sub(r'^-\s*админ\s*','',message.text,flags=re.IGNORECASE).strip()
    uid,name,_=await resolve_target(message,args)
    if not uid: return await message.reply("❌ Укажи @юзертег или ответь!")
    try:
        await bot.promote_chat_member(message.chat.id,uid,
            can_manage_chat=False,can_delete_messages=False,
            can_restrict_members=False,can_invite_users=False,
            can_pin_messages=False,can_change_info=False,
            can_promote_members=False,can_manage_topics=False,
            can_manage_video_chats=False)
        db("DELETE FROM admin_permissions WHERE user_id=? AND chat_id=?",(uid,message.chat.id))
        await message.reply(f"🔻 {user_link(uid,message.chat.id,name)} лишён прав администратора.")
    except Exception as e: await message.reply(f"❌ Ошибка: {e}")

# ============================================================
#  УПРАВЛЕНИЕ ЧАТОМ
# ============================================================
@dp.message(Command("moderation"))
async def toggle_moderation(message: types.Message):
    if not await mod_guard(message): return
    arg=message.text.replace("/moderation","").strip().lower()
    if arg=="on":   db("INSERT OR REPLACE INTO moderation_settings VALUES (?,?)",(message.chat.id,1)); await message.reply("✅ Автомодерация включена")
    elif arg=="off":db("INSERT OR REPLACE INTO moderation_settings VALUES (?,?)",(message.chat.id,0)); await message.reply("✅ Автомодерация выключена")
    else: await message.reply(f"Автомодерация: {'ВКЛ' if await is_moderation_enabled(message.chat.id) else 'ВЫКЛ'}")

@dp.message(Command("setautoschedule"))
async def set_schedule(message: types.Message):
    if not await mod_guard(message): return
    args=message.text.replace("/setautoschedule","").strip().split()
    if len(args)<2: return await message.reply("⏰ /setautoschedule 23:00 09:00\n/setautoschedule off")
    if args[0].lower()=="off":
        db("UPDATE chat_settings SET close_time=NULL,open_time=NULL WHERE chat_id=?",(message.chat.id,))
        return await message.reply("✅ Расписание отключено.")
    fmt=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
    if not re.match(fmt,args[0]) or not re.match(fmt,args[1]):
        return await message.reply("❌ Формат: ЧЧ:ММ")
    db("INSERT OR REPLACE INTO chat_settings (chat_id,close_time,open_time,is_closed) VALUES (?,?,?,0)",
       (message.chat.id,args[0],args[1]))
    await apply_schedule_now(message.chat.id)
    await message.reply(f"✅ Закрытие: {args[0]}, открытие: {args[1]}")

@dp.message(Command("check_schedule"))
async def check_schedule_cmd(message: types.Message):
    r=db("SELECT close_time,open_time,is_closed FROM chat_settings WHERE chat_id=?",(message.chat.id,),fetch=True)
    if not r or not r[0][0]: return await message.reply("⏰ Расписание не установлено.")
    await message.reply(f"📅 Закрытие: {r[0][0]}\n🔓 Открытие: {r[0][1]}\nСтатус: {'🔒 ЗАКРЫТ' if r[0][2] else '🔓 ОТКРЫТ'}")

@dp.message(F.text.lower().startswith(("-чат","!чат")))
async def close_chat_cmd(message: types.Message):
    if not await mod_guard(message): return
    if await is_chat_closed(message.chat.id): return await message.reply("🔒 Уже закрыт!")
    if await close_chat(message.chat.id):
        await message.reply("✅ Чат закрыт.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔓 Открыть",callback_data=f"oc_{message.chat.id}")]]))

@dp.message(F.text.lower().startswith(("+чат","!открытьчат")))
async def open_chat_cmd(message: types.Message):
    if not await mod_guard(message): return
    if not await is_chat_closed(message.chat.id): return await message.reply("🔓 Уже открыт!")
    await open_chat(message.chat.id)

@dp.callback_query(F.data.startswith("oc_"))
async def open_chat_cb(call: types.CallbackQuery):
    cid=int(call.data.split("_")[1])
    if not await is_admin(cid,call.from_user.id): return await call.answer("❌ Только для администраторов!",show_alert=True)
    await open_chat(cid)
    try: await call.message.delete()
    except: pass

# ============================================================
#  RP
# ============================================================
RP_ACTIONS={
    "обнять":       ["🤗 обнял","🤗 обняла","🤗 обняли"],
    "поцеловать":   ["😘 поцеловал","😘 поцеловала","😘 поцеловали"],
    "ударить":      ["👊 ударил","👊 ударила","👊 ударили"],
    "погладить":    ["🫳 погладил","🫳 погладила","🫳 погладили"],
    "прижаться":    ["💕 прижался","💕 прижалась","💕 прижались"],
    "взять_за_руку":["💑 взял за руку","💑 взяла за руку","💑 взяли за руку"],
}

@dp.message(Command("rp"))
async def rp_list(message: types.Message):
    await message.reply("🎭 RP:\n"+"\n".join(f"• {k}" for k in RP_ACTIONS))

@dp.message(F.text.lower().startswith(tuple(RP_ACTIONS.keys())))
async def rp_action(message: types.Message):
    if message.chat.type not in ("group","supergroup"): return
    text=message.text.lower()
    action=next((k for k in RP_ACTIONS if text.startswith(k)),None)
    if not action: return
    uid2,name2,_=await resolve_target(message,message.text[len(action):].strip())
    if not uid2: return await message.reply("❌ Укажи @юзертег")
    if uid2==message.from_user.id: return await message.reply("❌ Нельзя с собой!")
    gr=db("SELECT gender FROM user_gender WHERE user_id=?",(message.from_user.id,),fetch=True)
    g=gr[0][0] if gr else 0
    await message.reply(
        f"{user_link(message.from_user.id,message.chat.id,message.from_user.first_name)} "
        f"{RP_ACTIONS[action][g if g<3 else 0]} {user_link(uid2,message.chat.id,name2)}!")

# ============================================================
#  БРАКИ
# ============================================================
async def get_marriage(uid,cid):
    r=db("SELECT user1,user2,since FROM marriages WHERE chat_id=? AND (user1=? OR user2=?)",(cid,uid,uid),fetch=True)
    if r:
        u1,u2,since=r[0]; return (u2 if u1==uid else u1),(int(time.time())-since)//86400
    return None,None

@dp.message(F.text.lower().startswith(("+брак","!брак")))
async def marry_cmd(message: types.Message):
    uid=message.from_user.id
    if (await get_marriage(uid,message.chat.id))[0]: return await message.reply("❌ Вы уже в браке!")
    args=message.text[5:].strip()
    t_id,t_name,_=await resolve_target(message,args)
    if not t_id: return await message.reply("❌ Укажи @юзертег")
    if t_id==uid: return await message.reply("❌ Нельзя на себе!")
    kb=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💍 Принять",callback_data=f"ma_{uid}_{t_id}_{message.chat.id}"),
        InlineKeyboardButton(text="❌ Отказать",callback_data=f"md_{uid}_{t_id}"),
    ]])
    await message.reply(f"💍 {user_link(uid,message.chat.id,message.from_user.first_name)} предлагает брак {user_link(t_id,message.chat.id,t_name)}!",reply_markup=kb)

@dp.callback_query(F.data.startswith("ma_"))
async def marry_accept(call: types.CallbackQuery):
    _,_,s,t,c=call.data.split("_"); s,t,c=int(s),int(t),int(c)
    if call.from_user.id!=t: return await call.answer("Не вам!",show_alert=True)
    db("INSERT INTO marriages (user1,user2,chat_id,since) VALUES (?,?,?,?)",(s,t,c,int(time.time())))
    await call.message.edit_text(f"💍 ПОЗДРАВЛЯЕМ!\n{user_link(s,c,'')} и {user_link(t,c,'')} теперь в браке!")

@dp.callback_query(F.data.startswith("md_"))
async def marry_deny(call: types.CallbackQuery):
    _,_,s,t=call.data.split("_")
    if call.from_user.id!=int(t): return await call.answer("Не вам!",show_alert=True)
    await call.message.edit_text("❌ Предложение отклонено.")

@dp.message(F.text.lower().startswith(("+развод","!развод")))
async def divorce_cmd(message: types.Message):
    uid=message.from_user.id; p,days=await get_marriage(uid,message.chat.id)
    if not p: return await message.reply("❌ Вы не в браке!")
    db("DELETE FROM marriages WHERE chat_id=? AND (user1=? OR user2=?)",(message.chat.id,uid,uid))
    await message.reply(f"💔 Развод. Были вместе {days} дней.")

@dp.message(F.text.lower().startswith(("+пара","!пара")))
async def couple_info(message: types.Message):
    uid=message.from_user.id; p,days=await get_marriage(uid,message.chat.id)
    if not p: return await message.reply("💔 Не в браке.")
    await message.reply(f"💑 {user_link(uid,message.chat.id,'')} 💕 {user_link(p,message.chat.id,'')}\n📅 {days} дней")

@dp.message(F.text.lower().startswith(("+список браков","!список браков")))
async def marriages_list(message: types.Message):
    rows=db("SELECT user1,user2,since FROM marriages WHERE chat_id=?",(message.chat.id,),fetch=True)
    if not rows: return await message.reply("📋 Браков нет.")
    lines=["📋 Список браков:"]
    for u1,u2,since in rows:
        lines.append(f"💑 {user_link(u1,message.chat.id,'')} + {user_link(u2,message.chat.id,'')} — {(int(time.time())-since)//86400} дн.")
    await message.reply("\n".join(lines))

# ============================================================
#  НИКНЕЙМЫ
# ============================================================
@dp.message(F.text.lower().startswith(("+ник","!ник")))
async def set_nickname(message: types.Message):
    args=message.text[4:].strip()
    t_id,t_name,_=await resolve_target(message,args)
    if not t_id: return await message.reply("❌ Укажи @юзертег")
    nick=" ".join(w for w in args.split() if not w.startswith("@"))
    if not nick: return await message.reply("❌ Укажи ник!")
    db("INSERT OR REPLACE INTO user_nicknames (user_id,chat_id,nickname) VALUES (?,?,?)",(t_id,message.chat.id,nick))
    await message.reply(f"✅ {user_link(t_id,message.chat.id,t_name)} → <b>{nick}</b>")

# ============================================================
#  РУССКИЕ ПСЕВДОНИМЫ
# ============================================================
@dp.message(F.text)
async def text_aliases(message: types.Message):
    if not message.text: return
    t=message.text.strip().lower()
    if t=="профиль":            return await profile(message)
    if t=="топ":                return await top_cmd(message)
    if t=="работа":             return await work(message)
    if t in ("бонус","ежедневный"): return await daily(message)
    if t=="магазин":            return await shop_cmd(message)
    if t.startswith("казино"):
        b=extract_bet(t)
        if b: message.text=f"/casino {b}"; return await casino_cmd(message)
    if t.startswith("дартс"):
        b=extract_bet(t)
        if b: message.text=f"/darts {b}"; return await darts_cmd(message)
    if t.startswith("монетка"):
        b=extract_bet(t)
        if b: message.text=f"/coinflip {b}"; return await coinflip_cmd(message)
    if t.startswith(("кнб","камень")):
        b=extract_bet(t)
        if b: message.text=f"/rps {b}"; return await rps_cmd(message)
    if t=="кости":     return await cmd_dice(message)
    if t=="баскетбол": return await cmd_basketball(message)
    if t=="футбол":    return await cmd_football(message)
    if t=="боулинг":   return await cmd_bowling(message)

# ============================================================
#  ЗАПУСК
# ============================================================
async def main():
    try: await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e: logging.warning(f"Webhook: {e}")
    try:
        await bot.set_my_commands(PRIVATE_COMMANDS,scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(GROUP_COMMANDS,scope=BotCommandScopeAllGroupChats())
    except Exception as e: logging.warning(f"Commands: {e}")
    me=await bot.get_me()
    print(f"✅ @{me.username} запущен! v5-final")
    print("   ✅ /setwelcome полностью исправлен")
    print("   ✅ !give @user сумма — для основателя")
    try:
        for (cid,) in db("SELECT chat_id FROM chat_settings WHERE close_time IS NOT NULL",fetch=True):
            await apply_schedule_now(cid)
    except Exception as e: logging.error(f"Schedule: {e}")
    asyncio.create_task(scheduler_loop())
    try:
        await dp.start_polling(bot,timeout=60,relax=0.5)
    except Exception as e:
        logging.error(f"Polling: {e}"); await asyncio.sleep(5)
        await dp.start_polling(bot,timeout=120,relax=1.0)

if __name__=="__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("👋 Остановлен!")
    except Exception as e:
        print(f"❌ {e}"); time.sleep(5); asyncio.run(main())