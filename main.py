# ============================================================
#  VOID HELPER BOT — БЕЗ БАГОВ
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

class WelcomeSetup(StatesGroup):
    waiting_for_media = State()
    waiting_for_text = State()

storage = MemoryStorage()
session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=storage)

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
    'CREATE TABLE IF NOT EXISTS banned (user_id INTEGER, chat_id INTEGER, PRIMARY KEY(user_id,chat_id))',
    'CREATE TABLE IF NOT EXISTS marriages (user1 INTEGER, user2 INTEGER, chat_id INTEGER, since INTEGER, PRIMARY KEY(user1,user2,chat_id))',
    'CREATE TABLE IF NOT EXISTS welcomes (chat_id INTEGER PRIMARY KEY, file_id TEXT, media_type TEXT, caption TEXT)',
]:
    db(sql)

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
    n = re.findall(r'\d+', text)
    return int(n[0]) if n else None

def parse_duration(duration_str: str) -> int:
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
#  КОМАНДЫ
# ============================================================
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
        "<b>💰:</b> /work /daily /profile /top /shop /buy\n"
        "<b>🎮:</b> /casino /darts /coinflip /rps\n"
        "<b>💍:</b> +брак +развод +пара +список браков\n"
        "<b>⚙️:</b> !мут !бан !админ !варн -варн\n"
        "<b>🎉:</b> /welcome /delwelcome\n"
        "<b>💎:</b> !give @user сумма")

# ============================================================
#  ПРИВЕТСТВИЕ - ИСПРАВЛЕННОЕ
# ============================================================
@dp.message(Command("welcome"))
async def welcome_cmd(message: types.Message, state: FSMContext):
    """Начало установки приветствия"""
    # Проверка в группе ли команда
    if message.chat.type not in ("group", "supergroup"):
        return await message.answer("❌ Команду пиши в группе!")

    # Проверка прав админа
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только для администраторов!")

    # Устанавливаем состояние и сохраняем ID группы
    await state.set_state(WelcomeSetup.waiting_for_media)
    await state.update_data(chat_id=message.chat.id)

    await message.answer(
        "<b>🎉 УСТАНОВКА ПРИВЕТСТВИЯ</b>\n\n"
        "📸 <b>ОТПРАВЬ ФОТО, ВИДЕО ИЛИ ГИФКУ</b>\n\n"
        "Это будет показано новым членам чата.")

# ============================================================
#  ОЖИДАНИЕ МЕДИА
# ============================================================
@dp.message(WelcomeSetup.waiting_for_media)
async def welcome_media_handler(message: types.Message, state: FSMContext):
    """Получаем фото/видео/гифку"""
    
    file_id = None
    media_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
        await message.answer("✅ <b>Фото получено!</b>\n\n📝 Напиши текст приветствия")
    
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
        await message.answer("✅ <b>Видео получено!</b>\n\n📝 Напиши текст приветствия")
    
    elif message.animation:
        file_id = message.animation.file_id
        media_type = "animation"
        await message.answer("✅ <b>Гифка получена!</b>\n\n📝 Напиши текст приветствия")
    
    else:
        return await message.answer("❌ ОШИБКА!\n\nОтправь фото, видео или гифку! 📸")

    await state.update_data(file_id=file_id, media_type=media_type)
    await state.set_state(WelcomeSetup.waiting_for_text)

# ============================================================
#  ОЖИДАНИЕ ТЕКСТА
# ============================================================
@dp.message(WelcomeSetup.waiting_for_text)
async def welcome_text_handler(message: types.Message, state: FSMContext):
    """Получаем текст приветствия"""
    
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

    # Сохраняем в БД
    db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
       (chat_id, file_id, media_type, text))

    await state.clear()

    await message.answer(
        f"<b>✅ ПРИВЕТСТВИЕ УСТАНОВЛЕНО!</b>\n\n"
        f"📝 {text[:50]}...\n\n"
        f"<b>Готово!</b>")

@dp.message(Command("delwelcome"))
async def del_welcome(message: types.Message):
    """Удалить приветствие"""
    if message.chat.type not in ("group", "supergroup"):
        return

    if not await is_admin(message.chat.id, message.from_user.id):
        return

    r = db("SELECT file_id FROM welcomes WHERE chat_id=?", (message.chat.id,), fetch=True)

    if not r:
        return await message.answer("❌ Приветствия нет")

    db("DELETE FROM welcomes WHERE chat_id=?", (message.chat.id,))
    await message.answer("🗑️ Удалено")

# ============================================================
#  НОВЫЕ ЧЛЕНЫ
# ============================================================
@dp.message(F.new_chat_members)
async def new_member_handler(message: types.Message):
    """При входе нового члена"""
    
    chat_id = message.chat.id
    
    r = db("SELECT file_id, media_type, caption FROM welcomes WHERE chat_id=?", (chat_id,), fetch=True)

    if not r:
        return

    file_id, media_type, caption = r[0]

    for member in message.new_chat_members:
        if member.is_bot:
            continue

        name = member.first_name or "Гость"
        
        if member.username:
            mention = f"@{member.username}"
        else:
            mention = f"<a href='tg://user?id={member.id}'>{name}</a>"

        text = caption.replace("{name}", name)
        text = text.replace("{mention}", mention)

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
#  ЭКОНОМИКА
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
    if len(args) < 2:
        return

    try:
        item = int(args[1])
    except:
        return

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)

    if item == 1:
        if coins < 500:
            return
        add_coins(uid, -500)
        await message.answer("✨ x2 на 1 час!")

    elif item == 2:
        if coins < 300:
            return
        add_coins(uid, -300)
        db("UPDATE users SET last_work=0 WHERE id=?", (uid,))
        await message.answer("⚡ Сброс!")

# ============================================================
#  ИГРЫ
# ============================================================
@dp.message(Command("casino"))
async def casino_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet:
        return

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)

    if bet > coins or bet < 10:
        return

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
    if not bet or bet < 10:
        return

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins:
        return

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
    if not bet or bet < 10:
        return

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins:
        return

    add_coins(uid, -bet)

    if random.random() > 0.5:
        add_coins(uid, bet * 2)
        await message.answer(f"🪙 +{bet * 2}")
    else:
        await message.answer(f"🪙 -{bet}")

@dp.message(Command("rps"))
async def rps_cmd(message: types.Message):
    bet = extract_bet(message.text)
    if not bet or bet < 10:
        return

    uid = message.from_user.id
    coins, _, _, _ = get_user(uid)
    if bet > coins:
        return

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

    if call.from_user.id != uid:
        return

    if user_choice == bot_choice:
        add_coins(uid, bet)
        result = f"🤝"
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
#  БРАКИ
# ============================================================
@dp.message(F.text.lower().startswith("+брак"))
async def marry_cmd(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    uid = message.from_user.id
    chat_id = message.chat.id

    args = message.text[5:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id or target_id == uid:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data=f"marry_yes_{uid}_{target_id}_{chat_id}"),
         InlineKeyboardButton(text="❌", callback_data=f"marry_no_{uid}_{target_id}")],
    ])

    await message.answer(f"💍 {message.from_user.first_name} → {target_name}?", reply_markup=kb)

@dp.callback_query(F.data.startswith("marry_yes_"))
async def marry_accept(call: types.CallbackQuery):
    parts = call.data.split("_")
    uid1, uid2, chat_id = int(parts[2]), int(parts[3]), int(parts[4])

    if call.from_user.id != uid2:
        return

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
    if message.chat.type not in ("group", "supergroup"):
        return

    uid = message.from_user.id
    r = db("SELECT user1, user2 FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?",
           (uid, uid, message.chat.id), fetch=True)

    if not r:
        return

    db("DELETE FROM marriages WHERE (user1=? OR user2=?) AND chat_id=?",
       (uid, uid, message.chat.id))
    await message.answer("💔")

# ============================================================
#  МОДЕРАЦИЯ
# ============================================================
@dp.message(F.text.startswith("!мут"))
async def mute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    args = message.text[4:].strip()
    target_id, target_name = await resolve_target(message, args)

    if not target_id or await is_admin(message.chat.id, target_id):
        return

    duration_seconds = parse_duration(args)
    until = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

    try:
        await bot.restrict_chat_member(message.chat.id, target_id,
                                       permissions=ChatPermissions(can_send_messages=False),
                                       until_date=until)
        await message.answer(f"🔇 {target_name}")
    except:
        pass

@dp.message(F.text.startswith("-размут"))
async def unmute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    args = message.text[8:].strip()
    target_id, _ = await resolve_target(message, args)

    if not target_id:
        return

    try:
        await bot.restrict_chat_member(message.chat.id, target_id,
                                       permissions=ChatPermissions(can_send_messages=True))
    except:
        pass

@dp.message(F.text.startswith("!бан"))
async def ban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    args = message.text[4:].strip()
    target_id, _ = await resolve_target(message, args)

    if not target_id or await is_admin(message.chat.id, target_id):
        return

    try:
        await bot.ban_chat_member(message.chat.id, target_id)
    except:
        pass

@dp.message(F.text.startswith("-разбан"))
async def unban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    args = message.text[8:].strip()
    target_id, _ = await resolve_target(message, args)

    if not target_id:
        return

    try:
        await bot.unban_chat_member(message.chat.id, target_id)
    except:
        pass

@dp.message(F.text.startswith("!админ"))
async def admin_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    args = message.text[6:].strip()
    target_id, _ = await resolve_target(message, args)

    if not target_id:
        return

    try:
        await bot.promote_chat_member(message.chat.id, target_id, can_manage_chat=True,
                                      can_delete_messages=True, can_restrict_members=True)
    except:
        pass

@dp.message(F.text.startswith("-админ"))
async def unadmin_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    args = message.text[6:].strip()
    target_id, _ = await resolve_target(message, args)

    if not target_id:
        return

    try:
        await bot.promote_chat_member(message.chat.id, target_id, can_manage_chat=False)
    except:
        pass

@dp.message(F.text.startswith("!варн"))
async def warn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    args = message.text[5:].strip()
    target_id, _ = await resolve_target(message, args)

    if not target_id or await is_admin(message.chat.id, target_id):
        return

    _, _, warns, _ = get_user(target_id)
    warns += 1
    db("UPDATE users SET warns=? WHERE id=?", (warns, target_id))

@dp.message(F.text.startswith("-варн"))
async def remove_warn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    args = message.text[5:].strip()
    target_id, _ = await resolve_target(message, args)

    if not target_id:
        return

    _, _, warns, _ = get_user(target_id)
    if warns > 0:
        warns -= 1
        db("UPDATE users SET warns=? WHERE id=?", (warns, target_id))

# ============================================================
#  !give
# ============================================================
@dp.message(F.text.startswith("!give"))
async def give_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return

    text = message.text.strip()
    parts = text.split()

    if len(parts) < 3:
        return

    target = parts[1]
    if not target.startswith("@"):
        target = "@" + target

    try:
        amount = int(parts[2])
    except:
        return

    if amount <= 0:
        return

    try:
        user = await bot.get_chat(target)
        add_coins(user.id, amount)
        await message.answer(f"✅ {amount} 💰")
    except:
        pass

# ============================================================
#  CALLBACK
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

    me = await bot.get_me()
    print(f"\n✅ БОТ ГОТОВ: @{me.username}\n")

    try:
        await dp.start_polling(bot, timeout=60)
    except KeyboardInterrupt:
        print("Отключено")

if __name__ == "__main__":
    asyncio.run(main())
