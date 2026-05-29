import os
import sys
import time
import re
import asyncio
import logging
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

for module in ['aiosqlite', 'aiogram']:
    try:
        __import__(module)
    except ModuleNotFoundError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", module])

import aiosqlite
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import ChatPermissions, Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

TOKEN = os.getenv('BOT_TOKEN', '8203364413:AAGOjBjFHfDtdm1w5vlmqHcxhD9HpR4_MNo')
OWNER_ID = 7173827114
DB_NAME = 'void_bot.db'

# Статистика репортов в памяти
report_stats = {}

DEFAULT_FORBIDDEN = [
    "камшот", "камшоты", "гетеро", "интим", "порно", "секс", "гей", "член", "хуй", "пенис", "вагина"
]

# Стейты для FSM
class WelcomeSetup(StatesGroup):
    waiting_for_media = State()
    waiting_for_text = State()

class RulesSetup(StatesGroup):
    waiting_for_rules = State()

class ReportActionSetup(StatesGroup):
    waiting_for_mute_time = State()
    waiting_for_ban_time = State()

storage = MemoryStorage()
session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=storage)

logging.basicConfig(level=logging.INFO)

async def db(query: str, params: tuple = (), fetch: bool = False):
    try:
        async with aiosqlite.connect(DB_NAME) as conn:
            async with conn.execute(query, params) as cur:
                if fetch:
                    return await cur.fetchall()
                await conn.commit()
    except Exception as e:
        logging.error(f"DB Error: {e}")
    return [] if fetch else False

async def init_db():
    queries = [
        'CREATE TABLE IF NOT EXISTS warns (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, issued_at INTEGER, expires_at INTEGER)',
        'CREATE TABLE IF NOT EXISTS warn_settings (chat_id INTEGER PRIMARY KEY, max_warns INTEGER DEFAULT 3, ban_duration INTEGER DEFAULT 0, warn_duration INTEGER DEFAULT 86400)',
        'CREATE TABLE IF NOT EXISTS bans (user_id INTEGER, chat_id INTEGER, reason TEXT DEFAULT "", banned_until INTEGER DEFAULT 0, PRIMARY KEY(user_id,chat_id))',
        'CREATE TABLE IF NOT EXISTS welcomes (chat_id INTEGER PRIMARY KEY, file_id TEXT, media_type TEXT, caption TEXT)',
        'CREATE TABLE IF NOT EXISTS forbidden_words (chat_id INTEGER, word TEXT, PRIMARY KEY(chat_id, word))',
        'CREATE TABLE IF NOT EXISTS rules (chat_id INTEGER PRIMARY KEY, rules_text TEXT)',
        'CREATE TABLE IF NOT EXISTS schedules (chat_id INTEGER PRIMARY KEY, close_time TEXT, open_time TEXT, is_enabled INTEGER DEFAULT 0, last_state TEXT DEFAULT "")'
    ]
    for q in queries:
        await db(q)

async def is_admin(chat_id: int, user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

def tid(message: Message) -> Optional[int]:
    return message.message_thread_id

def detect_gender_verb(first_name: str) -> str:
    if not first_name: return "присоединился(ась)"
    name_lower = first_name.strip().lower()
    if name_lower.endswith(('а', 'я')): return "зашла"
    return "зашёл"

async def resolve_target_from_reply(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name
    return None, None

async def resolve_target_from_text(chat_id, text: str):
    if not text: return None, None
    words = text.split()
    for word in words:
        if word.startswith("@"):
            username = word[1:]
            try:
                user = await bot.get_chat(f"@{username}")
                return user.id, user.first_name or username
            except: continue
        if word.isdigit():
            try:
                user = await bot.get_chat(int(word))
                return user.id, user.first_name or str(user.id)
            except: continue
    return None, None

def extract_duration(text: str) -> Tuple[Optional[int], str]:
    pattern = r'(\d+)\s*(м|мин|ч|час|д|день|дня|дней)\b'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        unit = match.group(2).lower()
        if unit.startswith('м'): sec = num * 60
        elif unit.startswith('ч'): sec = num * 3600
        elif unit.startswith('д'): sec = num * 86400
        else: sec = 3600
        cleaned = text[:match.start()] + text[match.end():]
        return sec, cleaned.strip()
    return None, text

async def parse_moderation_args(message: Message):
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    args_str = parts[1] if len(parts) > 1 else ""
    target_id, target_name = await resolve_target_from_reply(message)
    duration, clean_args = extract_duration(args_str)
    if not target_id:
        target_id, target_name = await resolve_target_from_text(message.chat.id, clean_args)
    return duration, target_id, target_name

# Middleware для фильтрации мата
class WordFilterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        if not event.text or event.chat.type not in ('group', 'supergroup'):
            return await handler(event, data)
        if event.text.startswith(('!', '/')):
            return await handler(event, data)
        
        chat_words = [row[0] for row in await db("SELECT word FROM forbidden_words WHERE chat_id=?", (event.chat.id,), fetch=True)]
        words = DEFAULT_FORBIDDEN + chat_words
        msg_lower = event.text.lower()
        for w in words:
            if re.search(rf"\b{re.escape(w)}", msg_lower):
                try:
                    await event.answer(f"🗑 <b>Сообщение от {event.from_user.mention_html()} удалено за запрещенные слова.</b>")
                    await bot.delete_message(event.chat.id, event.message_id)
                except: pass
                return 
        return await handler(event, data)

dp.message.middleware(WordFilterMiddleware())

# --- КОМАНДЫ НАВИГАЦИИ И СЕРВИСА ---

@dp.message(Command("cancel", prefix="!/"))
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("<b>📥 Настройка прервана.</b>")

@dp.message(Command("start", prefix="!/"))
async def start_cmd(message: Message):
    await message.answer("<b>🦾 Приветствую! Я VOID Helper.</b>\nВведите команду: <code>!help</code>")

@dp.message(Command("help", "помощь", prefix="!/"))
async def help_cmd(message: Message):
    await message.answer(
        "<b>⚔️ МЕНЮ КОМАНД VOID HELPER</b>\n\n"
        "🛡 <b>Модерация:</b>\n"
        "• <code>!мут [время] [цель]</code> / <code>!размут</code>\n"
        "• <code>!бан [время] [цель]</code> / <code>!разбан</code>\n"
        "• <code>!кик [цель]</code> | <code>!варн [время]</code>\n"
        "• <code>!банлист</code> | <code>!амнистия</code>\n\n"
        "⚠️ <b>Репорты:</b>\n"
        "• <code>!rep [причина]</code> (в ответе на сообщение)\n"
        "• <code>!replist</code> — Список жалоб (Только для Админов)\n\n"
        "📅 <b>Авторасписание (МСК):</b>\n"
        "• <code>/setautoschedule [выкл] [вкл]</code>\n"
        "• <code>/check_schedule</code> | <code>/delautoschedule</code>\n\n"
        "⚙️ <b>Настройки:</b>\n"
        "• <code>/setwelcome</code> | <code>/delwelcome</code>\n"
        "• <code>/setrules [текст]</code> | <code>/rules</code>"
    )

# --- МОДЕРАЦИЯ ЧАТА ---

@dp.message(Command("mute", "мут", prefix="!/"))
async def mute_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if duration is None: duration = 3600
    if not target_id: return await message.answer("❌ Участник не найден.")
    if await is_admin(message.chat.id, target_id): return
    
    until = datetime.now(timezone.utc) + timedelta(seconds=duration)
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await message.answer(f"静 <b>{target_name}</b> отправлен в мут на {duration//60} мин.")
    except: pass

@dp.message(Command("unmute", "размут", prefix="!/"))
async def unmute_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    text_arg = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, text_arg)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_send_polls=True))
        await message.answer(f"🔊 Мут с <b>{target_name}</b> снят.")
    except: pass

@dp.message(Command("ban", "бан", prefix="!/"))
async def ban_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if not target_id: return await message.answer("❌ Участник не найден.")
    if await is_admin(message.chat.id, target_id): return
    
    until = int(time.time()) + duration if duration else 0
    await db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,'Нарушение правил',?)", (target_id, message.chat.id, until))
    try:
        await bot.ban_chat_member(message.chat.id, target_id, until_date=None if not duration else datetime.fromtimestamp(until, tz=timezone.utc))
        await message.answer(f"🚫 <b>{target_name}</b> забанен.")
    except: pass

@dp.message(Command("unban", "разбан", prefix="!/"))
async def unban_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    text_arg = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, text_arg)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return
    await db("DELETE FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
    try:
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"✅ {target_name} разбанен.")
    except: pass

# --- ИНТЕРАКТИВНЫЕ РЕПОРТЫ С КНОПКАМИ И ВВОДОМ ВРЕМЕНИ В ЧАСАХ ---

@dp.message(Command("rep", "report", prefix="!/"))
async def report_user_cmd(message: Message):
    if not message.reply_to_message:
        return await message.reply("❌ Пиши команду в ответе (reply) на сообщение нарушителя!")
        
    target_user = message.reply_to_message.from_user
    reporter = message.from_user
    if target_user.id == reporter.id: return
    
    parts = message.text.split(maxsplit=1)
    reason = parts[1] if len(parts) > 1 else "Не указана"
    
    report_stats[target_user.id] = report_stats.get(target_user.id, 0) + 1
    
    report_text = (
        f"🚨 <b>ПОСТУПИЛ РЕПОРТ!</b>\n\n"
        f"👤 <b>Нарушитель:</b> {target_user.mention_html()} (ID: <code>{target_user.id}</code>)\n"
        f"✍️ <b>Отправил:</b> {reporter.mention_html()}\n"
        f"📝 <b>Причина:</b> {reason}\n"
        f"📊 Жалоб на юзера: <code>{report_stats[target_user.id]}</code>\n\n"
        f"🛠 <b>Действия администрации:</b>"
    )
    
    kbd = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚠️ Мут", callback_data=f"rep_m_{target_user.id}"),
            InlineKeyboardButton(text="🚫 Бан", callback_data=f"rep_b_{target_user.id}")
        ],
        [
            InlineKeyboardButton(text="✅ Отпустить", callback_data="rep_dismiss")
        ]
    ])
    await message.answer(report_text, reply_markup=kbd)
    try: await message.delete()
    except: pass

@dp.callback_query(F.data.startswith("rep_"))
async def handle_report_callback(callback: CallbackQuery, state: FSMContext):
    chat_id = callback.message.chat.id
    if not await is_admin(chat_id, callback.from_user.id):
        return await callback.answer("❌ Вы не админ!", show_alert=True)
        
    action = callback.data.split("_")[1]
    
    if action == "dismiss":
        await callback.message.edit_text(f"{callback.message.text}\n\n✅ <i>Жалоба отклонена админом {callback.from_user.full_name}.</i>", reply_markup=None)
        return
        
    target_id = int(callback.data.split("_")[2])
    if await is_admin(chat_id, target_id):
        return await callback.answer("❌ Это админ чата!", show_alert=True)
        
    if action == "m":
        await state.set_state(ReportActionSetup.waiting_for_mute_time)
        await state.update_data(c_id=chat_id, t_id=target_id, msg_id=callback.message.message_id, text=callback.message.text)
        await callback.message.reply(f"✍️ @{callback.from_user.username}, <b>введите время МУТА в часах</b> (целое число):")
        await callback.answer()
        
    elif action == "b":
        await state.set_state(ReportActionSetup.waiting_for_ban_time)
        await state.update_data(c_id=chat_id, t_id=target_id, msg_id=callback.message.message_id, text=callback.message.text)
        await callback.message.reply(f"✍️ @{callback.from_user.username}, <b>введите время БАНА в часах</b> (целое число, или 0 для вечного):")
        await callback.answer()

@dp.message(ReportActionSetup.waiting_for_mute_time)
async def process_report_mute_time(message: Message, state: FSMContext):
    if not await is_admin(message.chat.id, message.from_user.id): return
    data = await state.get_data()
    
    if not message.text.isdigit():
        return await message.reply("Введите корректное число часов!")
        
    hours = int(message.text)
    until = datetime.now(timezone.utc) + timedelta(hours=hours)
    
    try:
        await bot.restrict_chat_member(data['c_id'], data['t_id'], permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await bot.edit_message_text(
            chat_id=data['c_id'], message_id=data['msg_id'],
            text=f"{data['text']}\n\n🔇 <b>Применено:</b> Мут на {hours} ч. администратором {message.from_user.full_name}.",
            reply_markup=None
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    await state.clear()

@dp.message(ReportActionSetup.waiting_for_ban_time)
async def process_report_ban_time(message: Message, state: FSMContext):
    if not await is_admin(message.chat.id, message.from_user.id): return
    data = await state.get_data()
    
    if not message.text.isdigit():
        return await message.reply("Введите корректное число часов!")
        
    hours = int(message.text)
    until_ts = int(time.time()) + (hours * 3600) if hours > 0 else 0
    
    try:
        await db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,'По репорту участников',?)", (data['t_id'], data['c_id'], until_ts))
        await bot.ban_chat_member(data['c_id'], data['t_id'], until_date=None if hours == 0 else datetime.fromtimestamp(until_ts, tz=timezone.utc))
        
        txt = f"на {hours} ч." if hours > 0 else "навсегда"
        await bot.edit_message_text(
            chat_id=data['c_id'], message_id=data['msg_id'],
            text=f"{data['text']}\n\n🚫 <b>Применено:</b> Бан {txt} администратором {message.from_user.full_name}.",
            reply_markup=None
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    await state.clear()

@dp.message(Command("replist", prefix="!/"))
async def show_report_list_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("🔒 Действие доступно только для администрации чата.")
    if not report_stats:
        return await message.reply("📭 Список жалоб пуст.")
        
    sorted_reports = sorted(report_stats.items(), key=lambda x: x[1], reverse=True)
    text = "📊 <b>Список нарушителей по жалобам:</b>\n\n"
    for idx, (user_id, count) in enumerate(sorted_reports[:10], start=1):
        try:
            u = await bot.get_chat(user_id)
            name = u.first_name or f"ID: {user_id}"
        except: name = f"ID: {user_id}"
        text += f"<b>{idx}.</b> {name} — <b>{count}</b> репортов.\n"
    await message.reply(text)

# --- ПРИВЕТСТВИЯ И ПРАВИЛА ЧАТА ---

@dp.message(Command("setwelcome", prefix="!/"))
async def set_welcome_cmd(message: Message, state: FSMContext):
    if not await is_admin(message.chat.id, message.from_user.id): return
    await state.set_state(WelcomeSetup.waiting_for_media)
    await state.update_data(chat_id=message.chat.id, admin_id=message.from_user.id)
    await message.answer("<b>🎉 НАСТРОЙКА ПРИВЕТСТВИЯ</b>\nОтправьте фото, видео или GIF.")

@dp.message(WelcomeSetup.waiting_for_media)
async def welcome_media_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.from_user.id != data.get('admin_id'): return
    file_id, media_type = None, None
    if message.photo: file_id, media_type = message.photo[-1].file_id, "photo"
    elif message.video: file_id, media_type = message.video.file_id, "video"
    elif message.animation: file_id, media_type = message.animation.file_id, "animation"
    else: return await message.answer("❌ Формат не поддерживается.")
    
    if message.caption:
        await db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)", (data['chat_id'], file_id, media_type, message.caption.strip()))
        await state.clear()
        return await message.answer("<b>✅ Приветствие установлено!</b>")
    await state.update_data(file_id=file_id, media_type=media_type)
    await state.set_state(WelcomeSetup.waiting_for_text)
    await message.answer("📝 Теперь отправьте текст приветствия.")

@dp.message(WelcomeSetup.waiting_for_text)
async def welcome_text_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.from_user.id != data.get('admin_id') or not message.text: return
    await db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)", (data['chat_id'], data['file_id'], data['media_type'], message.text.strip()))
    await state.clear()
    await message.answer("<b>✅ Приветствие сохранено!</b>")

@dp.message(Command("delwelcome", prefix="!/"))
async def del_welcome_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    await db("DELETE FROM welcomes WHERE chat_id=?", (message.chat.id,))
    await message.answer("🗑️ Приветствие отключено.")

@dp.message(Command("rules", "правила", prefix="!/"))
async def show_rules_cmd(message: Message):
    r = await db("SELECT rules_text FROM rules WHERE chat_id=?", (message.chat.id,), fetch=True)
    if r and r[0][0]: await message.answer(f"📋 <b>ПРАВИЛА ЧАТА:</b>\n\n{r[0][0]}")
    else: await message.answer("📭 Правила ещё не установлены.")

@dp.message(Command("setrules", "установитьправила", prefix="!/"))
async def set_rules_cmd(message: Message, state: FSMContext):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        await db("INSERT OR REPLACE INTO rules (chat_id, rules_text) VALUES (?, ?)", (message.chat.id, parts[1].strip()))
        return await message.answer("<b>✅ Правила обновлены!</b>")
    await state.set_state(RulesSetup.waiting_for_rules)
    await state.update_data(chat_id=message.chat.id, admin_id=message.from_user.id)
    await message.answer("📝 Отправьте текст правил Вашего сообщества:")

@dp.message(RulesSetup.waiting_for_rules)
async def rules_text_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.from_user.id != data.get('admin_id') or not message.text: return
    await db("INSERT OR REPLACE INTO rules (chat_id, rules_text) VALUES (?, ?)", (data['chat_id'], message.text.strip()))
    await state.clear()
    await message.answer("<b>✅ Правила сохранены!</b>")

# --- РАСПИСАНИЕ И ОСТАЛЬНЫЕ КОМАНДЫ (ВАРНЫ, ФИЛЬТРЫ) ---

@dp.message(Command("setautoschedule", prefix="!/"))
async def set_auto_schedule_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split()
    if len(parts) < 3: return await message.answer("Формат: <code>/setautoschedule 23:00 07:00</code>")
    close_time, open_time = parts[1], parts[2]
    await db("INSERT OR REPLACE INTO schedules (chat_id, close_time, open_time, is_enabled, last_state) VALUES (?, ?, ?, 1, '')", (message.chat.id, close_time, open_time))
    await message.answer(f"🔒 Авторасписание установлено: {close_time} - {open_time} по МСК.")

@dp.message(Command("check_schedule", prefix="!/"))
async def check_schedule_cmd(message: Message):
    r = await db("SELECT close_time, open_time, is_enabled FROM schedules WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not r or not r[0][2]: return await message.answer("📅 Авторасписание отключено.")
    await message.answer(f"📅 Расписание (МСК): Мут в {r[0][0]} | Открытие в {r[0][1]}")

@dp.message(Command("delautoschedule", prefix="!/"))
async def del_auto_schedule_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    await db("UPDATE schedules SET is_enabled=0 WHERE chat_id=?", (message.chat.id,))
    await message.answer("📅 Расписание отключено.")

@dp.message(Command("warn", "варн", prefix="!/"))
async def warn_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    _, target_id, target_name = await parse_moderation_args(message)
    if not target_id: return
    now = int(time.time())
    await db("INSERT INTO warns (user_id, chat_id, issued_at, expires_at) VALUES (?,?,?,?)", (target_id, message.chat.id, now, now+86400))
    await message.answer(f"⚜️ Участнику {target_name} выдано предупреждение.")

@dp.message(Command("banlist", "банлист", prefix="!/"))
async def banlist_cmd(message: Message):
    rows = await db("SELECT user_id, reason FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not rows: return await message.answer("📭 Черный список пуст.")
    text = "🚫 <b>БАН-ЛИСТ ЧАТА:</b>\n\n" + "\n".join([f"• ID: {uid} — {reason}" for uid, reason in rows])
    await message.answer(text)

@dp.message(Command("amnesty", "амнистия", prefix="!/"))
async def amnesty_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    await db("DELETE FROM bans WHERE chat_id=?", (message.chat.id,))
    await message.answer("🔓 Бан-лист чата полностью очищен.")

# Вход новых участников
@dp.message(F.new_chat_members)
async def new_member_handler(message: Message):
    chat_id = message.chat.id
    welcome_data = await db("SELECT file_id, media_type, caption FROM welcomes WHERE chat_id=?", (chat_id,), fetch=True)
    for member in message.new_chat_members:
        if member.is_bot: continue
        try: await bot.restrict_chat_member(chat_id, member.id, permissions=ChatPermissions(can_send_messages=False))
        except: pass
        
        kbd = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛡 Пройти верификацию", callback_data=f"verify_{member.id}")]])
        if welcome_data and welcome_data[0]:
            file_id, media_type, caption = welcome_data[0]
            text = caption.replace("{mention}", member.mention_html())
            if media_type == "photo": await bot.send_photo(chat_id, file_id, caption=text, reply_markup=kbd, message_thread_id=tid(message))
            continue
        await bot.send_message(chat_id, f"👋 Привет, {member.mention_html()}! Пройди верификацию.", reply_markup=kbd, message_thread_id=tid(message))

@dp.callback_query(F.data.startswith("verify_"))
async def process_verification(callback: CallbackQuery):
    target = int(callback.data.split("_")[1])
    if callback.from_user.id != target:
        return await callback.answer("❌ Кнопка не для вас!", show_alert=True)
    try:
        await bot.restrict_chat_member(callback.message.chat.id, target, permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True))
        await callback.answer("✅ Верификация пройдена!")
        await callback.message.edit_reply_markup(reply_markup=None)
    except: pass

async def auto_schedule_checker():
    msk_tz = timezone(timedelta(hours=3))
    while True:
        try:
            now = datetime.now(msk_tz)
            m_now = now.hour * 60 + now.minute
            rows = await db("SELECT chat_id, close_time, open_time, last_state FROM schedules WHERE is_enabled=1", fetch=True)
            for chat_id, close_time, open_time, last_state in rows:
                h_c, m_c = map(int, close_time.split(':'))
                h_o, m_o = map(int, open_time.split(':'))
                m_close = h_c * 60 + m_c
                m_open = h_o * 60 + m_o
                
                should_be_closed = (m_now >= m_close or m_now < m_open) if m_close > m_open else (m_close <= m_now < m_open)
                target_state = "closed" if should_be_closed else "opened"
                
                if last_state != target_state:
                    if target_state == "closed":
                        await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
                    else:
                        await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True))
                    await db("UPDATE schedules SET last_state=? WHERE chat_id=?", (target_state, chat_id))
        except: pass
        await asyncio.sleep(30)

async def main():
    await init_db()
    asyncio.create_task(auto_schedule_checker())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
