# ============================================================
#  VOID HELPER BOT — ИСПРАВЛЕННАЯ ВЕРСИЯ
#  (исправлен парсинг !мут, !бан, !варн, добавлены синонимы,
#   обновлён /adminhelp, улучшена работа расписания)
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
)
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(level=logging.ERROR)

TOKEN    = '8203364413:AAHBW_Aek57yZvvSf5JzrYElxLOCky_vnEY'
OWNER_ID = 7173827114
DB_NAME  = 'void_bot.db'

# ---------- Состояния для приветствия ----------
class WelcomeSetup(StatesGroup):
    waiting_for_media = State()
    waiting_for_text = State()

storage = MemoryStorage()
session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=storage)

# ---------- База данных ----------
def db(query, params=(), fetch=False):
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

for sql in [
    'CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 500, xp INTEGER DEFAULT 0, last_work INTEGER DEFAULT 0, last_daily INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, name TEXT DEFAULT "")',
    'CREATE TABLE IF NOT EXISTS muted (user_id INTEGER, chat_id INTEGER, until INTEGER, PRIMARY KEY(user_id,chat_id))',
    'CREATE TABLE IF NOT EXISTS bans (user_id INTEGER, chat_id INTEGER, reason TEXT DEFAULT "", banned_until INTEGER DEFAULT 0, PRIMARY KEY(user_id,chat_id))',
    'CREATE TABLE IF NOT EXISTS marriages (user1 INTEGER, user2 INTEGER, chat_id INTEGER, since INTEGER, PRIMARY KEY(user1,user2,chat_id))',
    'CREATE TABLE IF NOT EXISTS welcomes (chat_id INTEGER PRIMARY KEY, file_id TEXT, media_type TEXT, caption TEXT)',
    'CREATE TABLE IF NOT EXISTS warns (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, issued_at INTEGER, expires_at INTEGER)',
    'CREATE TABLE IF NOT EXISTS warn_settings (chat_id INTEGER PRIMARY KEY, max_warns INTEGER DEFAULT 3, ban_duration INTEGER DEFAULT 0, warn_duration INTEGER DEFAULT 86400)',
    'CREATE TABLE IF NOT EXISTS schedules (chat_id INTEGER PRIMARY KEY, close_time TEXT, open_time TEXT, enabled INTEGER DEFAULT 0)',
]:
    db(sql)

# ---------- Вспомогательные функции ----------
def get_user(uid: int) -> tuple:
    r = db("SELECT coins, xp, warns, name FROM users WHERE id=?", (uid,), fetch=True)
    if not r:
        db("INSERT INTO users (id) VALUES (?)", (uid,))
        return (500, 0, 0, "")
    return r[0]

def add_coins(uid: int, amount: int):
    get_user(uid)
    db("UPDATE users SET coins=coins+? WHERE id=?", (amount, uid))

def add_xp(uid: int, amount: int) -> Optional[int]:
    get_user(uid)
    r = db("SELECT xp FROM users WHERE id=?", (uid,), fetch=True)
    if not r:
        return None
    old_xp = r[0][0]
    db("UPDATE users SET xp=xp+? WHERE id=?", (amount, uid))
    old_lvl = old_xp // 100
    new_lvl = (old_xp + amount) // 100
    return new_lvl if new_lvl > old_lvl else None

async def is_admin(chat_id: int, user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False

def tid(message: types.Message) -> Optional[int]:
    return message.message_thread_id

async def resolve_target_from_reply(message: types.Message):
    """Получить цель из ответа на сообщение"""
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name
    return None, None

async def resolve_target_from_text(chat_id, text: str):
    """Поиск цели по @username или числовому ID в тексте"""
    words = text.split()
    for word in words:
        if word.startswith("@"):
            username = word[1:]
            try:
                user = await bot.get_chat(f"@{username}")
                return user.id, user.first_name or username
            except:
                pass
        if word.isdigit():
            try:
                user = await bot.get_chat(int(word))
                return user.id, user.first_name or str(user.id)
            except:
                pass
    return None, None

def extract_duration(text: str) -> Tuple[Optional[int], str]:
    """
    Ищет длительность в строке, возвращает (секунды, оставшийся текст без длительности).
    Если не найдено, возвращает (None, text).
    """
    # Регулярка: число + единица времени (русские сокращения)
    pattern = r'(\d+)\s*(м|мин|минуты|минута|ч|час|часа|часов|д|день|дня|дней)\b'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        unit = match.group(2).lower()
        if unit.startswith('м'):
            sec = num * 60
        elif unit.startswith('ч'):
            sec = num * 3600
        elif unit.startswith('д'):
            sec = num * 86400
        else:
            sec = 3600
        # Удаляем найденную длительность из текста
        cleaned = text[:match.start()] + text[match.end():]
        return sec, cleaned.strip()
    return None, text

async def parse_mute_args(message: types.Message):
    """
    Универсальный парсинг для !мут, !варн, !бан.
    Возвращает (duration_sec, target_id, target_name) или (None, None, None) при ошибке.
    """
    text = message.text.strip()
    # Разделим на команду и аргументы
    parts = text.split(maxsplit=1)
    args_str = parts[1] if len(parts) > 1 else ""

    # Сначала проверяем reply
    target_id, target_name = await resolve_target_from_reply(message)
    
    # Ищем длительность в аргументах
    duration, clean_args = extract_duration(args_str)
    
    # Если цель не получена через reply, ищем в очищенных аргументах
    if not target_id:
        target_id, target_name = await resolve_target_from_text(message.chat.id, clean_args)
    
    # Если длительность не найдена, для мута она обязательна, для бана — нет
    return duration, target_id, target_name

def format_help():
    return (
        "<b>📖 VOID HELPER — КОМАНДЫ</b>\n\n"
        "<b>💰 Экономика</b>\n"
        "/work – работа, /daily – бонус, /profile, /top, /shop, /buy\n\n"
        "<b>🎮 Игры</b>\n"
        "/casino, /darts, /coinflip, /rps\n\n"
        "<b>💍 Браки</b>\n"
        "+брак @user, +развод\n\n"
        "<b>🗣 Модерация (синонимы: / !)</b>\n"
        "⚜️ <b>Варн</b> /warn !варн !пред – варн <срок> <цель>\n"
        "⚜️ <b>Мут</b> !мут !mute !заткнуть – !мут <срок> <цель>\n"
        "⚜️ <b>Бан</b> !бан !ban !permban !чс – !бан <срок?> <цель> [причина]\n"
        "⚜️ <b>Разбан</b> !разбан !unban\n"
        "⚜️ <b>Кик</b> !кик !kick\n"
        "⚜️ <b>Амнистия</b> !амнистия\n"
        "⚜️ <b>Банлист</b> !банлист\n\n"
        "<b>👮 Админка</b>\n"
        "!админ @user / -админ @user\n\n"
        "<b>🎉 Приветствие</b> /welcome, /delwelcome\n\n"
        "<b>🕒 Расписание</b> /setautoschedule H:M H:M\n\n"
        "<b>👑 Владелец</b> !give @user сумма\n\n"
        "<b>📘 Админ-справка:</b> /adminhelp"
    )

# ---------- Фоновая задача расписания ----------
closed_chats = set()

async def schedule_task():
    """Проверяет расписание и закрывает/открывает чаты."""
    while True:
        try:
            rows = db("SELECT chat_id, close_time, open_time FROM schedules WHERE enabled=1", fetch=True)
            now = datetime.now().strftime("%H:%M")
            for chat_id, close, open_t in rows:
                close_min = int(close.split(":")[0]) * 60 + int(close.split(":")[1])
                open_min = int(open_t.split(":")[0]) * 60 + int(open_t.split(":")[1])
                now_min = int(now.split(":")[0]) * 60 + int(now.split(":")[1])
                
                should_close = False
                if close_min < open_min:
                    if close_min <= now_min < open_min:
                        should_close = True
                else:
                    if now_min >= close_min or now_min < open_min:
                        should_close = True

                if should_close:
                    if chat_id not in closed_chats:
                        try:
                            await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
                            closed_chats.add(chat_id)
                        except:
                            pass
                else:
                    if chat_id in closed_chats:
                        try:
                            await bot.set_chat_permissions(chat_id,
                                ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                                                can_send_polls=True, can_send_other_messages=True,
                                                can_add_web_page_previews=True, can_change_info=True,
                                                can_invite_users=True, can_pin_messages=True))
                            closed_chats.discard(chat_id)
                        except:
                            pass
        except Exception as e:
            logging.error(f"Schedule error: {e}")
        await asyncio.sleep(60)

# ===================== КОМАНДЫ =====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.type != "private":
        return
    me = await bot.get_me()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="menu_top")],
        [InlineKeyboardButton(text="💰 Эконом", callback_data="menu_econ"),
         InlineKeyboardButton(text="🎮 Игры", callback_data="menu_games")],
    ])
    await message.answer(f"👋 Привет!\n\n🤖 VOID Helper\n\n📋 /help — команды", reply_markup=kb)

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer(format_help())

# ---------- Приветствия ----------
@dp.message(Command("welcome"))
async def welcome_cmd(message: types.Message, state: FSMContext):
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("❌ Команду пиши в группе!")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только для администраторов!")
    await state.set_state(WelcomeSetup.waiting_for_media)
    await state.update_data(chat_id=message.chat.id)
    await message.answer("<b>🎉 УСТАНОВКА ПРИВЕТСТВИЯ</b>\n\n📸 ОТПРАВЬ ФОТО, ВИДЕО ИЛИ ГИФКУ")

@dp.message(WelcomeSetup.waiting_for_media)
async def welcome_media_handler(message: types.Message, state: FSMContext):
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
        return await message.answer("❌ ОШИБКА! Отправь фото, видео или гифку!")
    await state.update_data(file_id=file_id, media_type=media_type)
    await state.set_state(WelcomeSetup.waiting_for_text)
    await message.answer("✅ Медиа получено!\n📝 Напиши текст приветствия")

@dp.message(WelcomeSetup.waiting_for_text)
async def welcome_text_handler(message: types.Message, state: FSMContext):
    if not message.text:
        return await message.answer("❌ Напиши текст!")
    text = message.text.strip()
    data = await state.get_data()
    chat_id, file_id, media_type = data['chat_id'], data['file_id'], data['media_type']
    if not file_id:
        await state.clear()
        return
    db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
       (chat_id, file_id, media_type, text))
    await state.clear()
    await message.answer(f"<b>✅ ПРИВЕТСТВИЕ УСТАНОВЛЕНО!</b>\n📝 {text[:50]}...")

@dp.message(Command("delwelcome"))
async def del_welcome_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    r = db("SELECT file_id FROM welcomes WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not r:
        return await message.answer("❌ Приветствия нет")
    db("DELETE FROM welcomes WHERE chat_id=?", (message.chat.id,))
    await message.answer("🗑️ Удалено")

@dp.message(F.new_chat_members)
async def new_member_handler(message: types.Message):
    chat_id = message.chat.id
    r = db("SELECT file_id, media_type, caption FROM welcomes WHERE chat_id=?", (chat_id,), fetch=True)
    if not r:
        return
    file_id, media_type, caption = r[0]
    for member in message.new_chat_members:
        if member.is_bot:
            continue
        name = member.first_name or "Гость"
        mention = f"@{member.username}" if member.username else f"<a href='tg://user?id={member.id}'>{name}</a>"
        text = caption.replace("{name}", name).replace("{mention}", mention)
        try:
            count = await bot.get_chat_members_count(chat_id)
            text = text.replace("{count}", str(count))
        except:
            pass
        try:
            if media_type == "photo":
                await bot.send_photo(chat_id, file_id, caption=text, message_thread_id=tid(message))
            elif media_type == "video":
                await bot.send_video(chat_id, file_id, caption=text, message_thread_id=tid(message))
            elif media_type == "animation":
                await bot.send_animation(chat_id, file_id, caption=text, message_thread_id=tid(message))
        except Exception as e:
            logging.error(f"Welcome: {e}")

# ---------- Экономика и игры ----------
@dp.message(Command("profile"))
async def profile_cmd(message: types.Message):
    uid = message.from_user.id
    coins, xp, warns, name = get_user(uid)
    level = xp // 100
    await message.answer(f"👤 {name}\n⭐ {level}\n💰 {coins}\n📊 {xp}")

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    rows = db("SELECT id, coins, name FROM users ORDER BY coins DESC LIMIT 10", fetch=True)
    if not rows:
        return await message.answer("🏆 Пусто")
    medals = ["🥇", "🥈", "🥉"]
    lines = ["<b>🏆 ТОП</b>\n"]
    for i, (uid, coins, name) in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        n = name if name else f"ID{uid}"
        lines.append(f"{medal} {n} — {coins}")
    await message.answer("\n".join(lines))

@dp.message(Command("work"))
async def work_cmd(message: types.Message):
    uid = message.from_user.id
    r = db("SELECT last_work FROM users WHERE id=?", (uid,), fetch=True)
    last = r[0][0] if r else 0
    now = int(time.time())
    if now - last < 600:
        return await message.answer(f"⏳ Через {(600-(now-last))//60}м")
    pay = random.randint(400, 1000)
    xpg = random.randint(15, 35)
    add_coins(uid, pay)
    lvl = add_xp(uid, xpg)
    db("UPDATE users SET last_work=? WHERE id=?", (now, uid))
    msg = f"💰 +{pay}\n✨ +{xpg}"
    if lvl:
        msg += f"\n🎉 Уровень {lvl}!"
    await message.answer(msg)

@dp.message(Command("daily"))
async def daily_cmd(message: types.Message):
    uid = message.from_user.id
    get_user(uid)
    now = int(time.time())
    r = db("SELECT last_daily FROM users WHERE id=?", (uid,), fetch=True)
    last = r[0][0] if r else 0
    if now - last < 86400:
        return await message.answer(f"🎁 Через {(86400-(now-last))//3600}ч")
    bonus = random.randint(300, 700)
    add_coins(uid, bonus)
    lvl = add_xp(uid, 50)
    db("UPDATE users SET last_daily=? WHERE id=?", (now, uid))
    msg = f"💰 +{bonus}\n✨ +50"
    if lvl:
        msg += f"\n🎉 Уровень {lvl}!"
    await message.answer(msg)

@dp.message(Command("shop"))
async def shop_cmd(message: types.Message):
    await message.answer("1️⃣ x2 множитель — 500\n2️⃣ Сброс работы — 300\n\n/buy 1 или /buy 2")

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    args = message.text.split()
    if len(args) < 2: return
    try: item = int(args[1])
    except: return
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if item == 1:
        if coins < 500: return
        add_coins(uid, -500)
        await message.answer("✨ x2 на 1 час!")
    elif item == 2:
        if coins < 300: return
        add_coins(uid, -300)
        db("UPDATE users SET last_work=0 WHERE id=?", (uid,))
        await message.answer("⚡ Сброс!")

@dp.message(Command("casino"))
async def casino_cmd(message: types.Message):
    bet = re.findall(r'\d+', message.text)
    if not bet: return
    bet = int(bet[0])
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins or bet < 10: return
    add_coins(uid, -bet)
    dice = await bot.send_dice(message.chat.id, emoji="🎰", message_thread_id=tid(message))
    await asyncio.sleep(3)
    v = dice.dice.value
    if v == 64:
        add_coins(uid, bet * 10); txt = f"🎉 ДЖЕКПОТ!\n+{bet * 10}"
    elif v >= 50:
        add_coins(uid, bet * 4); txt = f"🎰 +{bet * 4}"
    elif v >= 30:
        add_coins(uid, bet * 2); txt = f"+{bet * 2}"
    elif v >= 15:
        add_coins(uid, bet); txt = f"Возврат {bet}"
    else:
        txt = f"Минус {bet}"
    await message.answer(txt)

@dp.message(Command("darts"))
async def darts_cmd(message: types.Message):
    bet = re.findall(r'\d+', message.text)
    if not bet: return
    bet = int(bet[0])
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins or bet < 10: return
    add_coins(uid, -bet)
    dice = await bot.send_dice(message.chat.id, emoji="🎯", message_thread_id=tid(message))
    await asyncio.sleep(3)
    v = dice.dice.value
    if v == 6:
        add_coins(uid, bet * 5); txt = f"+{bet * 5}"
    elif v == 5:
        add_coins(uid, bet * 3); txt = f"+{bet * 3}"
    elif v == 4:
        add_coins(uid, bet * 2); txt = f"+{bet * 2}"
    else:
        txt = f"-{bet}"
    await message.answer(txt)

@dp.message(Command("coinflip"))
async def coinflip_cmd(message: types.Message):
    bet = re.findall(r'\d+', message.text)
    if not bet: return
    bet = int(bet[0])
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins or bet < 10: return
    add_coins(uid, -bet)
    if random.random() > 0.5:
        add_coins(uid, bet * 2)
        await message.answer(f"🪙 +{bet * 2}")
    else:
        await message.answer(f"🪙 -{bet}")

@dp.message(Command("rps"))
async def rps_cmd(message: types.Message):
    bet = re.findall(r'\d+', message.text)
    if not bet: return
    bet = int(bet[0])
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins or bet < 10: return
    add_coins(uid, -bet)
    choices = ["камень", "ножницы", "бумага"]
    bot_choice = random.choice(choices)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪨", callback_data=f"rps_камень_{uid}_{bet}_{bot_choice}"),
         InlineKeyboardButton(text="✂️", callback_data=f"rps_ножницы_{uid}_{bet}_{bot_choice}"),
         InlineKeyboardButton(text="📄", callback_data=f"rps_бумага_{uid}_{bet}_{bot_choice}")],
    ])
    await message.answer("✊", reply_markup=kb)

@dp.callback_query(F.data.startswith("rps_"))
async def rps_callback(call: types.CallbackQuery):
    parts = call.data.split("_")
    user_choice, uid, bet = parts[1], int(parts[2]), int(parts[3])
    bot_choice = "_".join(parts[4:])
    if call.from_user.id != uid: return
    if user_choice == bot_choice:
        add_coins(uid, bet); result = "🤝"
    elif (user_choice == "камень" and bot_choice == "ножницы") or \
         (user_choice == "ножницы" and bot_choice == "бумага") or \
         (user_choice == "бумага" and bot_choice == "камень"):
        add_coins(uid, bet * 2); result = f"🎉 +{bet * 2}"
    else:
        result = f"😞 -{bet}"
    await call.message.edit_text(result)
    await call.answer()

# ---------- Браки ----------
@dp.message(F.text.lower().startswith("+брак"))
async def marry_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"): return
    uid = message.from_user.id
    target_id, target_name = await resolve_target_from_text(message.chat.id, message.text[5:].strip())
    if not target_id or target_id == uid: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data=f"marry_yes_{uid}_{target_id}_{message.chat.id}"),
         InlineKeyboardButton(text="❌", callback_data=f"marry_no_{uid}_{target_id}")],
    ])
    await message.answer(f"💍 {message.from_user.first_name} → {target_name}?", reply_markup=kb)

@dp.callback_query(F.data.startswith("marry_yes_"))
async def marry_accept(call: types.CallbackQuery):
    _, _, uid1, uid2, chat_id = call.data.split("_")
    uid1, uid2, chat_id = int(uid1), int(uid2), int(chat_id)
    if call.from_user.id != uid2: return
    db("INSERT INTO marriages (user1, user2, chat_id, since) VALUES (?,?,?,?)",
       (uid1, uid2, chat_id, int(time.time())))
    await call.message.edit_text("💍 ДА!")
    await call.answer()

@dp.callback_query(F.data.startswith("marry_no_"))
async def marry_deny(call: types.CallbackQuery):
    await call.message.edit_text("💔")
    await call.answer()

@dp.message(F.text.lower().startswith("+развод"))
async def divorce_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"): return
    uid = message.from_user.id
    db("DELETE FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?", (uid, uid, message.chat.id))
    await message.answer("💔")

# ===================== МОДЕРАЦИЯ (исправлено) =====================
# ---------- Мут (улучшенный парсинг) ----------
@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!мут","!mute","!заткнуть","/mute","/мут") for _ in [0]))
async def mute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    duration, target_id, target_name = await parse_mute_args(message)
    if duration is None:
        return await message.answer("⚠️ Укажи длительность. Например: !мут 1ч @user или !мут @user 30 мин")
    if not target_id:
        return await message.answer("❌ Укажи цель (ответ на сообщение или @username)!")
    if await is_admin(message.chat.id, target_id):
        return await message.answer("❌ Нельзя замьютить администратора.")
    
    until = datetime.now(timezone.utc) + timedelta(seconds=duration)
    try:
        await bot.restrict_chat_member(message.chat.id, target_id,
                                       permissions=ChatPermissions(can_send_messages=False),
                                       until_date=until)
        await message.answer(f"🔇 {target_name} замьючен на {duration // 60} мин")
    except:
        await message.answer("❗ Не удалось замьютить. Возможно, у бота недостаточно прав.")

# ---------- Размут ----------
@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!размут","!unmute","-размут","!говори","/unmute","/размут") for _ in [0]))
async def unmute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    target_id, target_name = await resolve_target_from_text(message.chat.id, message.text.split(maxsplit=1)[-1] if len(message.text.split())>1 else "")
    if not target_id:
        return await message.answer("❌ Укажи цель (@username или ответ)")
    try:
        await bot.restrict_chat_member(message.chat.id, target_id,
                                       permissions=ChatPermissions(can_send_messages=True))
        await message.answer(f"🔊 {target_name} размьючен")
    except:
        pass

# ---------- Варн (улучшенный парсинг) ----------
@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!варн","!warn","!пред","!предупреждение","/warn","/варн") for _ in [0]))
async def warn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    duration, target_id, target_name = await parse_mute_args(message)  # та же логика
    if duration is None:
        return await message.answer("⚠️ Укажи срок варна. Например: !варн 1ч @user")
    if not target_id:
        return await message.answer("❌ Укажи цель (@username или ответ)!")
    if await is_admin(message.chat.id, target_id):
        return await message.answer("❌ Нельзя выдать варн администратору.")
    
    now = int(time.time())
    expires = now + duration
    db("INSERT INTO warns (user_id, chat_id, issued_at, expires_at) VALUES (?,?,?,?)",
       (target_id, message.chat.id, now, expires))
    max_warns, ban_duration, _ = get_warn_settings(message.chat.id)
    active = get_active_warns(target_id, message.chat.id)
    await message.answer(f"⚜️ {target_name} получил предупреждение ({active}/{max_warns})")
    
    if active >= max_warns:
        until = now + ban_duration if ban_duration else 0
        reason = f"Лимит предупреждений ({max_warns})"
        db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,?,?)",
           (target_id, message.chat.id, reason, until))
        try:
            await bot.ban_chat_member(message.chat.id, target_id,
                                      until_date=None if until==0 else datetime.fromtimestamp(until, tz=timezone.utc))
            await message.answer(f"🚫 {target_name} забанен по достижению лимита варнов.")
        except:
            pass

def get_warn_settings(chat_id):
    r = db("SELECT max_warns, ban_duration, warn_duration FROM warn_settings WHERE chat_id=?", (chat_id,), fetch=True)
    if r:
        return r[0]
    db("INSERT INTO warn_settings (chat_id) VALUES (?)", (chat_id,))
    return (3, 0, 86400)

def get_active_warns(uid, chat_id):
    now = int(time.time())
    r = db("SELECT COUNT(*) FROM warns WHERE user_id=? AND chat_id=? AND expires_at > ?", (uid, chat_id, now), fetch=True)
    return r[0][0] if r else 0

# Управление варнами
@dp.message(F.text.lower().startswith("!варны лимит"))
async def set_warn_limit(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    nums = re.findall(r'\d+', message.text)
    if not nums: return
    limit = int(nums[0])
    db("INSERT OR REPLACE INTO warn_settings (chat_id, max_warns, ban_duration, warn_duration) VALUES (?,?,?,?)",
       (message.chat.id, limit, 0, 86400))
    await message.answer(f"⚜️ Лимит варнов: {limit}")

@dp.message(F.text.lower().startswith("!варны чс"))
async def set_warn_ban_duration(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4: return await message.answer("!варны чс <срок>")
    dur = parse_duration(parts[3])
    db("UPDATE warn_settings SET ban_duration=? WHERE chat_id=?", (dur, message.chat.id))
    await message.answer(f"⚜️ Бан при лимите: {'навсегда' if dur==0 else f'{dur//3600}ч'}")

@dp.message(F.text.lower().startswith("!варны период"))
async def set_warn_duration(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4: return await message.answer("!варны период <срок>")
    dur = parse_duration(parts[3])
    db("UPDATE warn_settings SET warn_duration=? WHERE chat_id=?", (dur, message.chat.id))
    await message.answer(f"⚜️ Срок варна: {dur//3600}ч")

@dp.message(F.text.lower().startswith("!варны помощь"))
async def warns_help_cmd(message: types.Message):
    await message.answer(
        "⚜️ <b>Предупреждения</b>\n"
        "!варн <срок> <цель> — выдать\n"
        "!варны лимит <число>\n"
        "!варны чс <срок>\n"
        "!варны период <срок>\n"
        "!варны <цель> — просмотр\n"
        "!снять варны [кол-во] <цель>"
    )

@dp.message(F.text.lower().startswith("!варны "))
async def list_warns_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target_str = message.text[6:].strip()
    if not target_str:
        return
    target_id, target_name = await resolve_target_from_text(message.chat.id, target_str)
    if not target_id:
        target_id, target_name = await resolve_target_from_reply(message)
        if not target_id: return await message.answer("Пользователь не найден.")
    active = get_active_warns(target_id, message.chat.id)
    await message.answer(f"⚜️ {target_name}: {active} активных варнов")

@dp.message(F.text.lower().startswith("!снять варны"))
async def remove_warns_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    args = message.text[12:].strip()
    if not args: return
    parts = args.split()
    num = None
    target_str = args
    if parts[0].isdigit():
        num = int(parts[0])
        target_str = " ".join(parts[1:])
    target_id, target_name = await resolve_target_from_text(message.chat.id, target_str)
    if not target_id:
        target_id, target_name = await resolve_target_from_reply(message)
        if not target_id: return await message.answer("Цель не найдена.")
    now = int(time.time())
    if num:
        rows = db("SELECT id FROM warns WHERE user_id=? AND chat_id=? AND expires_at>? ORDER BY issued_at ASC LIMIT ?",
                  (target_id, message.chat.id, now, num), fetch=True)
        for r in rows:
            db("DELETE FROM warns WHERE id=?", (r[0],))
        await message.answer(f"⚜️ Снято {len(rows)} варнов с {target_name}")
    else:
        db("DELETE FROM warns WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
        await message.answer(f"⚜️ Все варны сняты с {target_name}")

# ---------- Бан (улучшенный парсинг) ----------
@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!бан","!ban","!permban","!чс","/бан","/ban") for _ in [0]))
async def ban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    text = message.text.strip()
    # Отделяем команду
    cmd = text.split()[0].lower()
    args_str = text[len(cmd):].strip()
    # Ищем длительность (необязательно)
    duration, clean_args = extract_duration(args_str)
    # Ищем цель
    target_id, target_name = await resolve_target_from_reply(message)
    if not target_id:
        target_id, target_name = await resolve_target_from_text(message.chat.id, clean_args)
    if not target_id:
        return await message.answer("❌ Укажи цель (@username или ответ)!")
    if await is_admin(message.chat.id, target_id):
        return await message.answer("❌ Нельзя забанить администратора.")
    
    reason = clean_args  # всё, что не длительность и не цель
    # Удалим из reason @упоминания и числа, чтобы оставить текст причины
    reason = re.sub(r'(@\w+|\d+)', '', reason).strip()
    now = int(time.time())
    banned_until = now + duration if duration else 0
    db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,?,?)",
       (target_id, message.chat.id, reason, banned_until))
    try:
        await bot.ban_chat_member(message.chat.id, target_id,
                                  until_date=None if not duration else datetime.fromtimestamp(banned_until, tz=timezone.utc))
        msg = f"🚫 {target_name} забанен"
        if duration:
            msg += f" на {duration//3600}ч"
        if reason:
            msg += f"\nПричина: {reason}"
        await message.answer(msg)
    except:
        await message.answer("❗ Не удалось забанить.")

# ---------- Разбан ----------
@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!разбан","!unban","/разбан","/unban") for _ in [0]))
async def unban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target_id, target_name = await resolve_target_from_text(message.chat.id, message.text.split(maxsplit=1)[-1] if len(message.text.split())>1 else "")
    if not target_id:
        target_id, target_name = await resolve_target_from_reply(message)
        if not target_id: return
    db("DELETE FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
    try:
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"✅ {target_name} разбанен, может вернуться по ссылке")
    except:
        pass

# ---------- Причина ----------
@dp.message(F.text.lower().startswith("!причина"))
async def reason_cmd(message: types.Message):
    target_id, target_name = await resolve_target_from_text(message.chat.id, message.text[9:].strip())
    if not target_id:
        target_id, target_name = await resolve_target_from_reply(message)
        if not target_id: return
    r = db("SELECT reason FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id), fetch=True)
    if r:
        await message.answer(f"Причина: {r[0][0] if r[0][0] else 'не указана'}")
    else:
        await message.answer("Пользователь не забанен или причина отсутствует.")

# ---------- Кик ----------
@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!кик","!kick","/кик","/kick") for _ in [0]))
async def kick_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target_id, target_name = await resolve_target_from_text(message.chat.id, message.text.split(maxsplit=1)[-1] if len(message.text.split())>1 else "")
    if not target_id:
        target_id, target_name = await resolve_target_from_reply(message)
        if not target_id: return
    if await is_admin(message.chat.id, target_id): return
    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await asyncio.sleep(1)
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"👢 {target_name} кикнут")
    except:
        pass

# ---------- Амнистия ----------
@dp.message(F.text.lower().startswith("!амнистия"))
async def amnesty_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    rows = db("SELECT user_id FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    for (uid,) in rows:
        try: await bot.unban_chat_member(message.chat.id, uid)
        except: pass
    db("DELETE FROM bans WHERE chat_id=?", (message.chat.id,))
    await message.answer("🔓 Амнистия: все баны сняты.")

# ---------- Банлист ----------
@dp.message(F.text.lower().startswith("!банлист"))
async def banlist_cmd(message: types.Message):
    rows = db("SELECT user_id, reason, banned_until FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not rows:
        return await message.answer("📭 Нет забаненных")
    lines = []
    for uid, reason, until in rows:
        try:
            user = await bot.get_chat(uid)
            name = user.first_name or str(uid)
        except:
            name = str(uid)
        dur = "навсегда" if until==0 else f"до {datetime.fromtimestamp(until)}"
        lines.append(f"• {name} — {reason if reason else '—'} ({dur})")
    await message.answer("\n".join(lines))

# ---------- Админка ----------
@dp.message(F.text.lower().startswith("!админ"))
async def admin_promote(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target_id, _ = await resolve_target_from_text(message.chat.id, message.text[6:].strip())
    if not target_id: return
    try:
        await bot.promote_chat_member(message.chat.id, target_id,
                                      can_manage_chat=True, can_delete_messages=True,
                                      can_restrict_members=True)
    except: pass

@dp.message(F.text.lower().startswith("-админ"))
async def admin_demote(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target_id, _ = await resolve_target_from_text(message.chat.id, message.text[6:].strip())
    if not target_id: return
    try:
        await bot.promote_chat_member(message.chat.id, target_id, can_manage_chat=False)
    except: pass

# ---------- !give (владелец) ----------
@dp.message(F.text.startswith("!give"))
async def give_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    parts = message.text.split()
    if len(parts) < 3: return
    target = parts[1]
    if not target.startswith("@"): target = "@" + target
    try: amount = int(parts[2])
    except: return
    if amount <= 0: return
    try:
        user = await bot.get_chat(target)
        add_coins(user.id, amount)
        await message.answer(f"✅ {amount} 💰")
    except: pass

# ===================== /adminhelp (ОБНОВЛЁН) =====================
@dp.message(Command("adminhelp"))
async def admin_help(message: types.Message):
    await message.answer(
        "⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️\n\n"
        "⚜️⚜️\n"
        "⚜️⚜️<b>Варн |период| |юз/отмет.|</b> ⚜️ выставляется одно предупреждение пользователю сроком, указанным в команде\n"
        "Синонимы: пред, предупреждение, /warn, !warn, !пред\n"
        "⚜️<b>Варны лимит |число|</b> ⚜️ устанавливает число предупреждений, по достижению которых пользователь исключается из беседы\n"
        "⚜️<b>Варны чс |период|</b> ⚜️ устанавливает срок бана по достижению лимита предупреждений\n"
        "⚜️<b>Варны |юз/отмет.|</b> ⚜️ выводится список текущих предупреждений пользователя\n"
        "⚜️<b>Варны период |период|</b> ⚜️ устанавливает срок хранения предупреждения\n"
        "⚜️<b>Снять варны |число| |юз/отмет.|</b> ⚜️ чтобы снять определенное число варнов пользователя\n"
        "⚜️<b>Снять варны |юз/отмет.|</b> ⚜️ чтобы снять все варны с пользователя\n"
        "⚜️<b>Варны помощь</b> ⚜️ выводит справку по командам модуля «Предупреждения»\n"
        "Синонимы к команде \"варн\": пред, предупреждение, /warn, !warn, !пред\n\n"
        "⚜️⚜️\n"
        "⚜️⚜️<b>Мут |срок| |юз/отмет.|</b> ⚜️ принудить пользователя к молчанию на определённый период\n"
        "⚜️<b>Снять мут |юз/отмет.|</b> ⚜️ снять мут\n"
        "Синонимы к команде «мут»: заткнуть, мут, mute\n"
        "Синонимы к команде «снять мут»: говори, unmute, размут\n"
        "⚜️⚜️\n"
        "⚜️⚜️<b>Бан |период| |юз/отмет.|</b> ⚜️ забанит пользователя на заданный период времени. По умолчанию банит навсегда.\n"
        "Синоним: чс, !ban, !permban\n"
        "⚜️<b>Разбан |юз/отмет.|</b> ⚜️ снимает бан с пользователя\n"
        "Синоним: !unban\n"
        " ⚜️После разбана, пользователь сможет вернуться в чат самостоятельно по ссылке\n\n"
        "⚜️<b>Причина |юз/отмет.|</b>  ⚜️ выводит причину, указанную при бане пользователя\n"
        "⚜️<b>Кик |юз/отмет.|</b>  ⚜️ исключает пользователя из беседы без бана. Его может добавить обратно любой пользователь, либо он может вернуться по ссылке.\n"
        "Синонимы: !кик, !kick\n"
        "⚜️<b>!Амнистия</b> ⚜️ снимает баны со всех участников беседы\n"
        "⚜️<b>Банлист</b> ⚜️ список забаненных в данной беседе",
        parse_mode="HTML"
    )

# ---------- Расписание ----------
@dp.message(Command("setautoschedule"))
async def set_schedule(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    if message.chat.type not in ("group", "supergroup"):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: /setautoschedule <закрытие> <открытие>\n/setautoschedule off")
    if args[1].lower() == "off":
        db("UPDATE schedules SET enabled=0 WHERE chat_id=?", (message.chat.id,))
        if message.chat.id in closed_chats:
            try:
                await bot.set_chat_permissions(message.chat.id,
                    ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_polls=True,
                                    can_send_other_messages=True, can_add_web_page_previews=True,
                                    can_change_info=True, can_invite_users=True, can_pin_messages=True))
                closed_chats.discard(message.chat.id)
            except: pass
        return await message.answer("✅ Автозакрытие отключено")
    if len(args) < 3:
        return
    close_str, open_str = args[1], args[2]
    if not re.match(r'^\d{1,2}:\d{2}$', close_str) or not re.match(r'^\d{1,2}:\d{2}$', open_str):
        return await message.answer("❌ Формат времени HH:MM")
    db("INSERT OR REPLACE INTO schedules (chat_id, close_time, open_time, enabled) VALUES (?,?,?,1)",
       (message.chat.id, close_str, open_str))
    await message.answer(f"✔ Закрытие: {close_str}, открытие: {open_str}")

# ---------- Callback меню ----------
@dp.callback_query(F.data == "menu_profile")
async def cb_profile(call: types.CallbackQuery):
    await profile_cmd(call.message)
    await call.answer()
@dp.callback_query(F.data == "menu_top")
async def cb_top(call: types.CallbackQuery):
    await top_cmd(call.message)
    await call.answer()
@dp.callback_query(F.data == "menu_econ")
async def cb_econ(call: types.CallbackQuery):
    await call.message.edit_text("/work /daily /shop /buy")
    await call.answer()
@dp.callback_query(F.data == "menu_games")
async def cb_games(call: types.CallbackQuery):
    await call.message.edit_text("/casino /darts /coinflip /rps")
    await call.answer()

# ---------- Запуск ----------
async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    asyncio.create_task(schedule_task())
    me = await bot.get_me()
    print(f"✅ БОТ ГОТОВ: @{me.username}")
    try:
        await dp.start_polling(bot, timeout=60)
    except KeyboardInterrupt:
        print("Отключено")

if __name__ == "__main__":
    asyncio.run(main())
