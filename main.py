# ============================================================
#  VOID HELPER BOT — БЕЗ БАГОВ
#  Исправленная и дополненная версия
# ============================================================
import asyncio
import sqlite3
import logging
import time
import random
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List

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

# ---------- Состояния для настройки приветствия ----------
class WelcomeSetup(StatesGroup):
    waiting_for_media = State()
    waiting_for_text = State()

storage = MemoryStorage()
session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=storage)

# ---------- Работа с БД ----------
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

# Инициализация всех таблиц
for sql in [
    # Пользователи (экономика)
    'CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 500, xp INTEGER DEFAULT 0, last_work INTEGER DEFAULT 0, last_daily INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, name TEXT DEFAULT "")',
    # Мьюты
    'CREATE TABLE IF NOT EXISTS muted (user_id INTEGER, chat_id INTEGER, until INTEGER, PRIMARY KEY(user_id,chat_id))',
    # Баны
    'CREATE TABLE IF NOT EXISTS bans (user_id INTEGER, chat_id INTEGER, reason TEXT DEFAULT "", banned_until INTEGER DEFAULT 0, PRIMARY KEY(user_id,chat_id))',
    # Браки
    'CREATE TABLE IF NOT EXISTS marriages (user1 INTEGER, user2 INTEGER, chat_id INTEGER, since INTEGER, PRIMARY KEY(user1,user2,chat_id))',
    # Приветствия
    'CREATE TABLE IF NOT EXISTS welcomes (chat_id INTEGER PRIMARY KEY, file_id TEXT, media_type TEXT, caption TEXT)',
    # Предупреждения (варны)
    'CREATE TABLE IF NOT EXISTS warns (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, issued_at INTEGER, expires_at INTEGER)',
    'CREATE TABLE IF NOT EXISTS warn_settings (chat_id INTEGER PRIMARY KEY, max_warns INTEGER DEFAULT 3, ban_duration INTEGER DEFAULT 0, warn_duration INTEGER DEFAULT 86400)',
    # Расписание закрытия чата
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

def update_user_name(uid: int, name: str):
    db("UPDATE users SET name=? WHERE id=?", (name, uid))

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

async def resolve_target(message: types.Message, args_str: str = "") -> Tuple[Optional[int], Optional[str]]:
    # Цель через reply
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name
    # Цель через @username
    for word in args_str.split():
        if word.startswith("@"):
            username = word[1:]
            try:
                user = await bot.get_chat(f"@{username}")
                return user.id, user.first_name or username
            except:
                pass
    # Цель по ID (если число)
    for word in args_str.split():
        if word.isdigit():
            try:
                user = await bot.get_chat(int(word))
                return user.id, user.first_name or str(user.id)
            except:
                pass
    return None, None

def extract_bet(text: str) -> Optional[int]:
    n = re.findall(r'\d+', text)
    return int(n[0]) if n else None

def parse_duration(duration_str: str) -> int:
    """Парсинг строки в секунды: м, мин, минуты, ч, час, д, день, дни"""
    duration_str = duration_str.lower().strip()
    match = re.match(r'(\d+)\s*(м|мин|минуты|минута|ч|час|часа|часов|д|день|дня|дней)', duration_str)
    if not match:
        return 3600  # по умолчанию 1 час
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

# ---------- Фоновая задача для расписания ----------
closed_chats = set()  # кэш, чтобы не дёргать API лишний раз

async def schedule_task():
    while True:
        try:
            rows = db("SELECT chat_id, close_time, open_time FROM schedules WHERE enabled=1", fetch=True)
            now = datetime.now().strftime("%H:%M")
            
            for chat_id, close, open_t in rows:
                # Определяем, нужно ли сейчас закрывать чат
                close_parts = close.split(":")
                open_parts = open_t.split(":")
                close_minutes = int(close_parts[0]) * 60 + int(close_parts[1])
                open_minutes = int(open_parts[0]) * 60 + int(open_parts[1])
                now_parts = now.split(":")
                now_minutes = int(now_parts[0]) * 60 + int(now_parts[1])
                
                should_be_closed = False
                if close_minutes < open_minutes:   # обычный период, напр. 0:00 - 7:30
                    if close_minutes <= now_minutes < open_minutes:
                        should_be_closed = True
                else:                              # ночной период, напр. 23:00 - 09:00
                    if now_minutes >= close_minutes or now_minutes < open_minutes:
                        should_be_closed = True
                
                if should_be_closed:
                    if chat_id not in closed_chats:
                        try:
                            await bot.set_chat_permissions(
                                chat_id,
                                ChatPermissions(can_send_messages=False)
                            )
                            closed_chats.add(chat_id)
                        except:
                            pass
                else:
                    if chat_id in closed_chats:
                        try:
                            await bot.set_chat_permissions(
                                chat_id,
                                ChatPermissions(
                                    can_send_messages=True,
                                    can_send_media_messages=True,
                                    can_send_polls=True,
                                    can_send_other_messages=True,
                                    can_add_web_page_previews=True,
                                    can_change_info=True,
                                    can_invite_users=True,
                                    can_pin_messages=True
                                )
                            )
                            closed_chats.discard(chat_id)
                        except:
                            pass
        except Exception as e:
            logging.error(f"Schedule error: {e}")
        
        await asyncio.sleep(60)  # проверка каждую минуту

# ---------- Команды ----------
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
    await message.answer(
        "<b>📖 VOID HELPER</b>\n\n"
        "<b>💰 Экономика:</b> /work /daily /profile /top /shop /buy\n"
        "<b>🎮 Игры:</b> /casino /darts /coinflip /rps\n"
        "<b>💍 Браки:</b> +брак +развод +пара +список браков\n"
        "<b>⚙️ Модерация:</b> !мут !бан !варн !кик !админ !амнистия !банлист\n"
        "<b>🔰 Админ-команды:</b> /adminhelp\n"
        "<b>🕒 Расписание:</b> /setautoschedule\n"
        "<b>💎 Права владельца:</b> !give @user сумма"
    )

# ============================================================
#  РАСПИСАНИЕ ЗАКРЫТИЯ ЧАТА
# ============================================================
@dp.message(Command("setautoschedule"))
async def set_auto_schedule(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    if message.chat.type not in ("group", "supergroup"):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "<b>Использование:</b>\n"
            "/setautoschedule <закрытие> <открытие>\n"
            "Пример: /setautoschedule 0:00 7:30\n"
            "/setautoschedule off — отключить"
        )

    if args[1].lower() == "off":
        db("UPDATE schedules SET enabled=0 WHERE chat_id=?", (message.chat.id,))
        # Снимаем ограничения, если они были
        if message.chat.id in closed_chats:
            try:
                await bot.set_chat_permissions(
                    message.chat.id,
                    ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                                    can_send_polls=True, can_send_other_messages=True,
                                    can_add_web_page_previews=True, can_change_info=True,
                                    can_invite_users=True, can_pin_messages=True)
                )
                closed_chats.discard(message.chat.id)
            except:
                pass
        return await message.answer("✅ Автозакрытие отключено")

    if len(args) < 3:
        return

    close_str = args[1]
    open_str = args[2]

    # Валидация формата
    if not re.match(r'^\d{1,2}:\d{2}$', close_str) or not re.match(r'^\d{1,2}:\d{2}$', open_str):
        return await message.answer("❌ Неверный формат времени. Используй HH:MM")

    db("INSERT OR REPLACE INTO schedules (chat_id, close_time, open_time, enabled) VALUES (?,?,?,1)",
       (message.chat.id, close_str, open_str))
    await message.answer(f"✔ Закрытие: {close_str}, открытие: {open_str}")

# ============================================================
#  ПРИВЕТСТВИЕ
# ============================================================
@dp.message(Command("welcome"))
async def welcome_cmd(message: types.Message, state: FSMContext):
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("❌ Команду пиши в группе!")
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только для администраторов!")

    await state.set_state(WelcomeSetup.waiting_for_media)
    await state.update_data(chat_id=message.chat.id)
    await message.answer(
        "<b>🎉 УСТАНОВКА ПРИВЕТСТВИЯ</b>\n\n"
        "📸 <b>ОТПРАВЬ ФОТО, ВИДЕО ИЛИ ГИФКУ</b>\n\n"
        "Это будет показано новым членам чата.")

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
        return await message.answer("❌ ОШИБКА!\n\nОтправь фото, видео или гифку! 📸")

    await state.update_data(file_id=file_id, media_type=media_type)
    await state.set_state(WelcomeSetup.waiting_for_text)
    await message.answer("✅ <b>Медиа получено!</b>\n\n📝 Напиши текст приветствия")

@dp.message(WelcomeSetup.waiting_for_text)
async def welcome_text_handler(message: types.Message, state: FSMContext):
    if not message.text:
        return await message.answer("❌ Напиши текст!")

    text = message.text.strip()
    data = await state.get_data()
    chat_id = data.get('chat_id')
    file_id = data.get('file_id')
    media_type = data.get('media_type')

    if not file_id or not media_type:
        await state.clear()
        return await message.answer("❌ Ошибка! Начни заново: /welcome")

    db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
       (chat_id, file_id, media_type, text))
    await state.clear()
    await message.answer(
        f"<b>✅ ПРИВЕТСТВИЕ УСТАНОВЛЕНО!</b>\n\n"
        f"📝 {text[:50]}...\n\n<b>Готово!</b>")

@dp.message(Command("delwelcome"))
async def del_welcome(message: types.Message):
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
            text = text.replace("{count}", "")

        try:
            if media_type == "photo":
                await bot.send_photo(chat_id, file_id, caption=text, message_thread_id=tid(message))
            elif media_type == "video":
                await bot.send_video(chat_id, file_id, caption=text, message_thread_id=tid(message))
            elif media_type == "animation":
                await bot.send_animation(chat_id, file_id, caption=text, message_thread_id=tid(message))
        except Exception as e:
            logging.error(f"Welcome: {e}")

# ============================================================
#  ЭКОНОМИКА И ИГРЫ (оставлены без изменений, кроме команд)
# ============================================================
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
    bet = extract_bet(message.text)
    if not bet: return
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins or bet < 10: return
    add_coins(uid, -bet)
    dice = await bot.send_dice(message.chat.id, emoji="🎰", message_thread_id=tid(message))
    await asyncio.sleep(3)
    v = dice.dice.value
    if v == 64:
        add_coins(uid, bet * 10)
        txt = f"🎉 ДЖЕКПОТ!\n+{bet * 10}"
    elif v >= 50:
        add_coins(uid, bet * 4)
        txt = f"🎰 +{bet * 4}"
    elif v >= 30:
        add_coins(uid, bet * 2)
        txt = f"+{bet * 2}"
    elif v >= 15:
        add_coins(uid, bet)
        txt = f"Возврат {bet}"
    else:
        txt = f"Минус {bet}"
    await message.answer(txt)

@dp.message(Command("darts"))
async def darts_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet or bet < 10: return
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins: return
    add_coins(uid, -bet)
    dice = await bot.send_dice(message.chat.id, emoji="🎯", message_thread_id=tid(message))
    await asyncio.sleep(3)
    v = dice.dice.value
    if v == 6:
        add_coins(uid, bet * 5)
        txt = f"+{bet * 5}"
    elif v == 5:
        add_coins(uid, bet * 3)
        txt = f"+{bet * 3}"
    elif v == 4:
        add_coins(uid, bet * 2)
        txt = f"+{bet * 2}"
    else:
        txt = f"-{bet}"
    await message.answer(txt)

@dp.message(Command("coinflip"))
async def coinflip_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet or bet < 10: return
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins: return
    add_coins(uid, -bet)
    if random.random() > 0.5:
        add_coins(uid, bet * 2)
        await message.answer(f"🪙 +{bet * 2}")
    else:
        await message.answer(f"🪙 -{bet}")

@dp.message(Command("rps"))
async def rps_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet or bet < 10: return
    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins: return
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
    user_choice = parts[1]
    uid = int(parts[2])
    bet = int(parts[3])
    bot_choice = "_".join(parts[4:])
    if call.from_user.id != uid: return
    if user_choice == bot_choice:
        add_coins(uid, bet)
        result = "🤝"
    elif (user_choice == "камень" and bot_choice == "ножницы") or \
         (user_choice == "ножницы" and bot_choice == "бумага") or \
         (user_choice == "бумага" and bot_choice == "камень"):
        add_coins(uid, bet * 2)
        result = f"🎉 +{bet * 2}"
    else:
        result = f"😞 -{bet}"
    await call.message.edit_text(result)
    await call.answer()

# ============================================================
#  БРАКИ (без изменений)
# ============================================================
@dp.message(F.text.lower().startswith("+брак"))
async def marry_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"): return
    uid = message.from_user.id
    chat_id = message.chat.id
    args = message.text[5:].strip()
    target_id, target_name = await resolve_target(message, args)
    if not target_id or target_id == uid: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data=f"marry_yes_{uid}_{target_id}_{chat_id}"),
         InlineKeyboardButton(text="❌", callback_data=f"marry_no_{uid}_{target_id}")],
    ])
    await message.answer(f"💍 {message.from_user.first_name} → {target_name}?", reply_markup=kb)

@dp.callback_query(F.data.startswith("marry_yes_"))
async def marry_accept(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid1, uid2, chat_id = int(parts[2]), int(parts[3]), int(parts[4])
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
    r = db("SELECT user1, user2 FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?",
           (uid, uid, message.chat.id), fetch=True)
    if not r: return
    db("DELETE FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?",
       (uid, uid, message.chat.id))
    await message.answer("💔")

# ============================================================
#  МОДЕРАЦИЯ (ПОЛНОСТЬЮ ПЕРЕРАБОТАНО)
# ============================================================

# ---------- Варны ----------
def get_warn_settings(chat_id: int):
    r = db("SELECT max_warns, ban_duration, warn_duration FROM warn_settings WHERE chat_id=?", (chat_id,), fetch=True)
    if r:
        return r[0]
    db("INSERT INTO warn_settings (chat_id) VALUES (?)", (chat_id,))
    return (3, 0, 86400)  # по умолчанию: 3 предупреждения, бан навсегда, варн действует 24ч

def get_active_warns(user_id: int, chat_id: int) -> int:
    now = int(time.time())
    r = db("SELECT COUNT(*) FROM warns WHERE user_id=? AND chat_id=? AND expires_at > ?",
           (user_id, chat_id, now), fetch=True)
    return r[0][0] if r else 0

@dp.message(F.text.lower().startswith("!варн"))
async def warn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    if message.chat.type not in ("group", "supergroup"):
        return

    # Разбор аргументов
    text = message.text.strip()
    parts = text.split(maxsplit=3)
    if len(parts) < 3:
        return await message.answer("⚠️ Использование: !варн <срок> <цель>\nПример: !варн 1ч @user")

    duration_str = parts[1]
    target_str = parts[2] if len(parts) > 2 else ""
    try:
        duration = parse_duration(duration_str)
    except:
        duration = 3600  # час по умолчанию

    target_id, target_name = await resolve_target(message, target_str)
    if not target_id or await is_admin(message.chat.id, target_id):
        return await message.answer("❌ Нельзя выдать варн администратору или цель не найдена.")

    chat_id = message.chat.id
    now = int(time.time())
    expires = now + duration
    db("INSERT INTO warns (user_id, chat_id, issued_at, expires_at) VALUES (?,?,?,?)",
       (target_id, chat_id, now, expires))

    max_warns, ban_duration, _ = get_warn_settings(chat_id)
    active = get_active_warns(target_id, chat_id)

    await message.answer(f"⚜️ {target_name} получил предупреждение ({active}/{max_warns})")

    if active >= max_warns:
        # Бан по лимиту
        until = 0  # навсегда
        reason = f"Лимит предупреждений ({max_warns})"
        if ban_duration > 0:
            until = now + ban_duration
        db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,?,?)",
           (target_id, chat_id, reason, until))
        try:
            await bot.ban_chat_member(chat_id, target_id, until_date=until if until > 0 else None)
            await message.answer(f"🚫 {target_name} забанен по достижению лимита варнов.")
        except:
            await message.answer("❗ Не удалось забанить пользователя.")

# ---------- Управление настройками варнов ----------
@dp.message(F.text.lower().startswith("!варны лимит"))
async def set_warn_limit(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    num = re.findall(r'\d+', message.text)
    if not num:
        return await message.answer("Укажи число.")
    limit = int(num[0])
    db("INSERT OR REPLACE INTO warn_settings (chat_id, max_warns, ban_duration, warn_duration) VALUES (?,?,?,?)",
       (message.chat.id, limit, 0, 86400))
    await message.answer(f"⚜️ Лимит варнов: {limit}")

@dp.message(F.text.lower().startswith("!варны чс"))
async def set_warn_ban_duration(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        return await message.answer("Используй: !варны чс <срок>")
    dur = parse_duration(parts[3])
    db("UPDATE warn_settings SET ban_duration=? WHERE chat_id=?", (dur, message.chat.id))
    await message.answer(f"⚜️ Срок бана по лимиту: {dur // 3600}ч" if dur > 0 else "⚜️ Бан навсегда")

@dp.message(F.text.lower().startswith("!варны период"))
async def set_warn_duration(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        return await message.answer("Используй: !варны период <срок>")
    dur = parse_duration(parts[3])
    db("UPDATE warn_settings SET warn_duration=? WHERE chat_id=?", (dur, message.chat.id))
    await message.answer(f"⚜️ Варн действителен {dur // 3600}ч")

@dp.message(F.text.lower().startswith("!варны "))
async def list_warns(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    target_id, target_name = await resolve_target(message, message.text[6:].strip())
    if not target_id:
        return await message.answer("Пользователь не найден.")
    active = get_active_warns(target_id, message.chat.id)
    await message.answer(f"⚜️ {target_name}: {active} активных предупреждений")

# ---------- Снятие варнов ----------
@dp.message(F.text.lower().startswith("!снять варны"))
async def remove_warns(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    text = message.text[11:].strip()
    parts = text.split()
    if not parts:
        return await message.answer("Укажи пользователя или количество и пользователя.")
    # Снять все
    if parts[0].isdigit():
        num = int(parts[0])
        target_str = " ".join(parts[1:])
    else:
        num = None
        target_str = text

    target_id, target_name = await resolve_target(message, target_str)
    if not target_id:
        return await message.answer("Цель не найдена.")
    now = int(time.time())
    if num:
        # Удаляем num самых старых варнов
        rows = db("SELECT id FROM warns WHERE user_id=? AND chat_id=? AND expires_at>? ORDER BY issued_at ASC LIMIT ?",
                  (target_id, message.chat.id, now, num), fetch=True)
        for r in rows:
            db("DELETE FROM warns WHERE id=?", (r[0],))
        await message.answer(f"⚜️ Снято {len(rows)} предупреждений с {target_name}")
    else:
        db("DELETE FROM warns WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
        await message.answer(f"⚜️ Все предупреждения сняты с {target_name}")

@dp.message(F.text.lower().startswith("!варны помощь"))
async def warns_help(message: types.Message):
    await message.answer(
        "⚜️ <b>Предупреждения (варны)</b>\n"
        "!варн <срок> <цель> — выдать варн\n"
        "!варны лимит <число> — макс. варнов до бана\n"
        "!варны чс <срок> — длительность бана\n"
        "!варны период <срок> — срок действия варна\n"
        "!варны <цель> — просмотр\n"
        "!снять варны <кол-во> <цель> / !снять варны <цель>"
    )

# ---------- Мут ----------
@dp.message(F.text.lower().startswith(("!мут", "!mute")))
async def mute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    text = message.text.strip()
    # Удаляем команду
    cmd = text.split()[0].lower()
    args_text = text[len(cmd):].strip()
    if not args_text:
        return await message.answer("Используй: !мут <срок> <цель>")
    parts = args_text.split(maxsplit=2)
    if len(parts) < 2:
        return await message.answer("Недостаточно аргументов.")
    duration = parse_duration(parts[0])
    target_id, target_name = await resolve_target(message, " ".join(parts[1:]))
    if not target_id or await is_admin(message.chat.id, target_id):
        return
    until = datetime.now(timezone.utc) + timedelta(seconds=duration)
    try:
        await bot.restrict_chat_member(message.chat.id, target_id,
                                       permissions=ChatPermissions(can_send_messages=False),
                                       until_date=until)
        await message.answer(f"🔇 {target_name} замьючен на {duration // 60} мин")
    except:
        await message.answer("Не удалось замьютить.")

@dp.message(F.text.lower().startswith(("!размут", "!снять мут", "!unmute")))
async def unmute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    target_id, target_name = await resolve_target(message, message.text.split(maxsplit=1)[-1])
    if not target_id:
        return
    try:
        await bot.restrict_chat_member(message.chat.id, target_id,
                                       permissions=ChatPermissions(can_send_messages=True))
        await message.answer(f"🔊 {target_name} размьючен")
    except:
        pass

# ---------- Бан ----------
@dp.message(F.text.lower().startswith(("!бан", "!ban", "!permban", "!чс")))
async def ban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    text = message.text.strip()
    parts = text.split(maxsplit=3)
    if len(parts) < 2:
        return await message.answer("Используй: !бан <срок?> <цель> [причина]")

    # Проверяем, указан ли срок
    first = parts[1]
    duration = None
    target_str = ""
    reason = ""
    if re.match(r'\d+[мчдМЧД]', first):  # если первый аргумент похож на срок
        duration = parse_duration(first)
        target_str = parts[2] if len(parts) > 2 else ""
        reason = parts[3] if len(parts) > 3 else ""
    else:
        target_str = first
        reason = parts[2] if len(parts) > 2 else ""

    target_id, target_name = await resolve_target(message, target_str)
    if not target_id or await is_admin(message.chat.id, target_id):
        return

    now = int(time.time())
    banned_until = now + duration if duration else 0  # 0 = навсегда

    db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,?,?)",
       (target_id, message.chat.id, reason, banned_until))
    try:
        await bot.ban_chat_member(message.chat.id, target_id,
                                  until_date=None if not duration else datetime.fromtimestamp(banned_until, tz=timezone.utc))
        msg = f"🚫 {target_name} забанен"
        if duration:
            msg += f" на {duration // 3600}ч"
        if reason:
            msg += f"\nПричина: {reason}"
        await message.answer(msg)
    except:
        await message.answer("Не удалось забанить.")

# ---------- Разбан ----------
@dp.message(F.text.lower().startswith(("!разбан", "!unban")))
async def unban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    target_id, target_name = await resolve_target(message, message.text.split(maxsplit=1)[-1])
    if not target_id:
        return
    db("DELETE FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
    try:
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"✅ {target_name} разбанен и может вернуться по ссылке")
    except:
        pass

# ---------- Причина бана ----------
@dp.message(F.text.lower().startswith("!причина"))
async def ban_reason_cmd(message: types.Message):
    target_id, target_name = await resolve_target(message, message.text.split(maxsplit=1)[-1])
    if not target_id:
        return
    r = db("SELECT reason FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id), fetch=True)
    if r and r[0][0]:
        await message.answer(f"Причина: {r[0][0]}")
    else:
        await message.answer("Причина не указана или пользователь не забанен.")

# ---------- Кик ----------
@dp.message(F.text.lower().startswith(("!кик", "!kick")))
async def kick_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    target_id, target_name = await resolve_target(message, message.text.split(maxsplit=1)[-1])
    if not target_id or await is_admin(message.chat.id, target_id):
        return
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
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    rows = db("SELECT user_id FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    for (uid,) in rows:
        try:
            await bot.unban_chat_member(message.chat.id, uid)
        except:
            pass
    db("DELETE FROM bans WHERE chat_id=?", (message.chat.id,))
    await message.answer("🔓 Все пользователи разбанены.")

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
        if until == 0:
            dur = "навсегда"
        else:
            dur = f"до {datetime.fromtimestamp(until)}"
        reason_str = reason if reason else "—"
        lines.append(f"• {name} — {reason_str} ({dur})")
    await message.answer("\n".join(lines))

# ---------- Админка (уже было) ----------
@dp.message(F.text.lower().startswith("!админ"))
async def admin_promote(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    target_id, _ = await resolve_target(message, message.text[6:].strip())
    if not target_id:
        return
    try:
        await bot.promote_chat_member(message.chat.id, target_id,
                                      can_manage_chat=True, can_delete_messages=True,
                                      can_restrict_members=True)
    except:
        pass

@dp.message(F.text.lower().startswith("-админ"))
async def admin_demote(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    target_id, _ = await resolve_target(message, message.text[6:].strip())
    if not target_id:
        return
    try:
        await bot.promote_chat_member(message.chat.id, target_id, can_manage_chat=False)
    except:
        pass

# ============================================================
#  !give (владелец)
# ============================================================
@dp.message(F.text.startswith("!give"))
async def give_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    text = message.text.strip()
    parts = text.split()
    if len(parts) < 3: return
    target = parts[1]
    if not target.startswith("@"):
        target = "@" + target
    try:
        amount = int(parts[2])
    except:
        return
    if amount <= 0: return
    try:
        user = await bot.get_chat(target)
        add_coins(user.id, amount)
        await message.answer(f"✅ {amount} 💰")
    except:
        pass

# ============================================================
#  /adminhelp
# ============================================================
@dp.message(Command("adminhelp"))
async def admin_help(message: types.Message):
    await message.answer(
        "<b>🔰 Команды администратора</b>\n\n"
        "<b>🔇 Мут</b>\n"
        "!мут <срок> <цель> — замьютить\n"
        "!размут <цель> — размьютить\n\n"
        "<b>🚫 Бан</b>\n"
        "!бан <срок?> <цель> [причина] — бан (срок необязателен)\n"
        "!разбан <цель> — разбанить\n"
        "!причина <цель> — причина бана\n"
        "!кик <цель> — кикнуть\n\n"
        "<b>⚜️ Варны</b>\n"
        "!варн <срок> <цель> — выдать предупреждение\n"
        "!варны лимит <число> — лимит для бана\n"
        "!варны чс <срок> — длительность бана при лимите\n"
        "!варны период <срок> — срок жизни варна\n"
        "!варны <цель> — просмотр\n"
        "!снять варны <цель> / !снять варны <кол-во> <цель>\n\n"
        "<b>🔓 Амнистия / Банлист</b>\n"
        "!амнистия — разбанить всех\n"
        "!банлист — список забаненных\n\n"
        "<b>🔧 Админ</b>\n"
        "!админ <цель> — назначить\n"
        "-админ <цель> — снять\n\n"
        "<b>🎉 Приветствие</b>\n"
        "/welcome — установить\n"
        "/delwelcome — удалить\n\n"
        "<b>🕒 Расписание</b>\n"
        "/setautoschedule <закрытие> <открытие> — закрытие чата по времени\n"
        "/setautoschedule off — отключить"
    )

# ============================================================
#  Callback-меню
# ============================================================
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

# ============================================================
#  ЗАПУСК
# ============================================================
async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except:
        pass

    asyncio.create_task(schedule_task())  # фоновая задача расписания

    me = await bot.get_me()
    print(f"\n✅ БОТ ГОТОВ: @{me.username}\n")

    try:
        await dp.start_polling(bot, timeout=60)
    except KeyboardInterrupt:
        print("Отключено")

if __name__ == "__main__":
    asyncio.run(main())
