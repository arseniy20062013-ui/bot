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

DEFAULT_FORBIDDEN = [
    "камшот", "камшоты", "камшотов", "гетеро", "гетеросексуальность", "джонуанство",
    "импотенция", "интим", "интимность", "интроитус", "клитор", "клитора", "клиторов",
    "стояк", "стояка", "кама-сутра", "контрацептивы", "презик", "презики", "презика",
    "либидо", "либида", "лебида", "лубрикант", "лубриканта", "сперма", "спермы", "спермов",
    "сублимация", "триолизм", "порно", "секс", "гей", "лесбиянка", "лесбийск", "лесби",
    "лесб", "орно", "порн", "орн", "анал", "оргазм", "оргазмы", "оргазмов", "оргазму",
    "оргазма", "оргазмом", "оргазме", "порна", "порны", "гея", "геи", "хентай", "сексизм",
    "секси", "голые", "голый", "голая", "голое", "член", "хуй", "анилингус", "бдсм",
    "glory hole", "куколд", "солнечная", "солнечный", "гей за деньги", "кунилингус",
    "куни", "сексуальный", "сексуальное", "сексуальная", "пенис", "пениса", "пенисов",
    "вагина", "вагины", "вагин", "вульва", "вульвы", "влагалище", "влагалища", "мошонка",
    "мошонки", "яички", "яичек", "половой член", "полового члена", "крайняя плоть",
    "девственная плева", "гимен", "поза 69", "догги стайл", "миссионерская поза",
    "фроттаж", "фистинг", "фингеринг", "римминг", "иррумация", "дефлорация", "мастурбация",
    "онанизм", "онанист", "онанистка", "вибратор", "вибратора", "вибраторов", "фалоимитатор",
    "страпон", "латекс", "зппп", "венерическое заболевание", "сифилис", "гонорея",
    "хламидиоз", "вич", "спид", "герпес", "кондом", "кондомы", "кондома", "спермицид",
    "фертильность", "овуляция", "эякуляция", "эякулят", "семяизвержение", "поллюция",
    "нимфоманка", "нимфомания", "сатириазис", "эксгибиционизм", "вуайеризм", "фетиш",
    "фетишизм", "садомазохизм", "доминация", "квир", "трансгендер", "трансвестит",
    "бисексуал", "бисексуальность", "пансексуал", "пансексуальность", "асексуал",
    "асексуальность", "сквиртинг", "сквирт", "фаллос", "фаллический", "вагинизм",
    "диспареуния", "аноргазмия", "преждевременная эякуляция", "эreктильная дисфункция",
    "тестостерон", "эстроген", "афродизиак", "порнография", "порнографический",
    "порноактер", "порноактриса", "порнофильм", "порносайт", "хардкор", "софткор",
    "эротика", "эротический", "ню", "топлес", "стриптиз", "стриптизерша", "интимная стрижка",
    "минета", "минетчик", "минетчица", "фелляция", "буккаке", "инцест", "милф", "дилф",
    "твинк", "секс шоп", "секс игрушка", "секс кукла", "искусственная вагина", "любрикант",
    "кастрация", "стерилизация", "оральные контрацептивы", "противозачаточные",
    "экстренная контрацепция", "внутриматочная спираль", "презерватив", "смазка",
    "суррогатное материнство", "донор спермы", "яйцеклетка", "эмбрион", "зачатие",
    "бесплодие", "фригидность", "клиторальный", "вагинальный", "цервикальный", "анальный",
    "оральный", "возбуждение", "половое возбуждение", "эрекция", "гиперсексуальность",
    "гипосексуальность", "астенозооспермия", "фимоз", "приапизм", "менопауза", "климакс",
    "виагра", "сиалис"
]

class WelcomeSetup(StatesGroup):
    waiting_for_media = State()
    waiting_for_text = State()

class RulesSetup(StatesGroup):
    waiting_for_rules = State()

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
        'CREATE TABLE IF NOT EXISTS rules (chat_id INTEGER PRIMARY KEY, rules_text TEXT)'
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
    if not first_name:
        return "присоединился(ась)"
    name_lower = first_name.strip().lower()
    male_exceptions = {
        "никита", "илья", "лука", "фома", "савва", "данила", "данило",
        "саша", "паша", "дима", "вова", "ваня", "миша", "коля", "петя", 
        "вася", "гена", "рома", "леша", "лёша", "сева", "слава", "влад", "тёма"
    }
    if name_lower in male_exceptions:
        return "зашёл"
    if name_lower.endswith(('а', 'я')):
        return "зашла"
    return "зашёл"

async def resolve_target_from_reply(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name
    return None, None

async def resolve_target_from_text(chat_id, text: str):
    words = text.split()
    for word in words:
        if word.startswith("@"):
            username = word[1:]
            try:
                user = await bot.get_chat(f"@{username}")
                return user.id, user.first_name or username
            except:
                continue
        if word.isdigit():
            try:
                user = await bot.get_chat(int(word))
                return user.id, user.first_name or str(user.id)
            except:
                continue
    return None, None

def extract_duration(text: str) -> Tuple[Optional[int], str]:
    pattern = r'(\d+)\s*(м|мин|минуты|минута|минут|ч|час|часа|часов|д|день|дня|дней)\b'
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
    if not target_id:
        for entity in (message.entities or []):
            if entity.type == "mention":
                username = message.text[entity.offset+1 : entity.offset+entity.length]
                try:
                    user = await bot.get_chat(f"@{username}")
                    target_id, target_name = user.id, user.first_name or username
                    break
                except:
                    pass
    return duration, target_id, target_name

async def get_warn_settings(chat_id):
    r = await db("SELECT max_warns, ban_duration, warn_duration FROM warn_settings WHERE chat_id=?", (chat_id,), fetch=True)
    if r: 
        return r[0]
    await db("INSERT INTO warn_settings (chat_id) VALUES (?)", (chat_id,))
    return (3, 0, 86400)

async def get_active_warns(uid, chat_id):
    now = int(time.time())
    r = await db("SELECT COUNT(*) FROM warns WHERE user_id=? AND chat_id=? AND expires_at > ?", (uid, chat_id, now), fetch=True)
    return r[0][0] if r else 0

class WordFilterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        if not event.text or event.chat.type not in ('group', 'supergroup'):
            return await handler(event, data)

        first_word = event.text.split()[0].lower()
        if first_word.startswith(('!', '/', '-')):
            return await handler(event, data)

        state = data.get("state")
        if state and await state.get_state() is not None:
            return await handler(event, data)

        chat_id = event.chat.id
        chat_words = [row[0] for row in await db("SELECT word FROM forbidden_words WHERE chat_id=?", (chat_id,), fetch=True)]
        words = DEFAULT_FORBIDDEN + chat_words

        msg_lower = event.text.lower()
        for w in words:
            if re.search(rf"\b{re.escape(w)}", msg_lower):
                try:
                    user_link = f'<a href="tg://user?id={event.from_user.id}">{event.from_user.full_name}</a>'
                    await event.answer(
                        f"🗑 <b>Сообщение от {user_link} удалено</b>\n"
                        f"📝 <i>Текст:</i> {event.text}\n"
                        f"⚠️ Причина: ненормативная лексика / запрещенное слово",
                        disable_web_page_preview=True
                    )
                    await bot.delete_message(chat_id, event.message_id)
                except:
                    pass
                return 
        return await handler(event, data)

dp.message.middleware(WordFilterMiddleware())

@dp.message(Command("cancel", prefix="!/"))
@dp.message(lambda msg: msg.text and msg.text.lower().strip() in ("!отмена", "отмена"))
async def cancel_handler(message: Message, state: FSMContext):
    if await state.get_state() is not None:
        await state.clear()
        await message.answer("<b>📥 Настройка прервана.</b> Бот вернулся в штатный режим.")

@dp.message(Command("start", prefix="!/"))
async def start_cmd(message: Message):
    await message.answer(
        "<b>🦾 Приветствую! Я VOID Helper.</b>\n"
        "Специализированный бот для модерации, защиты от мата и ведения правил группы.\n\n"
        "ℹ️ Добавьте меня в админы группы и введите команду: <code>!help</code>"
    )

@dp.message(Command("help", "помощь", prefix="!/"))
async def help_cmd(message: Message):
    await message.answer(
        "<b>⚔️ МЕНЮ КОМАНД VOID HELPER</b>\n\n"
        "🛡 <b>Администрация (Модерация чата):</b>\n"
        "• <code>!мут [время] [цель]</code> — Чтение (Пример: <i>!мут 2ч @username</i>)\n"
        "• <code>!размут [цель]</code> — Снять ограничение чата\n"
        "• <code>!варн [время] [цель]</code> — Выдать предупреждение нарушителю\n"
        "• <code>!снять варны [цель]</code> — Обнулить предупреждения\n"
        "• <code>!бан [время?] [цель] [причина]</code> — Чёрный список чата\n"
        "• <code>!разбан [цель]</code> — Помиловать участника\n"
        "• <code>!кик [цель]</code> — Исключить (выгнать) из группы\n"
        "• <code>!банлист</code> — Список забаненных аккаунтов\n"
        "• <code>!амнистия</code> — Полная очистка ЧС группы\n\n"
        "🚫 <b>Фильтрация мата и слов:</b>\n"
        "• <code>!запретслово [слово]</code> — Внести фразу в чёрный список\n"
        "• <code>!разрешслово [слово]</code> — Убрать слово из фильтрации\n"
        "• <code>!списокзапретов</code> — Посмотреть базу запрещенных слов чата\n\n"
        "⚙️ <b>Конфигурация (Настройки):</b>\n"
        "• <code>/setwelcome</code> — Настроить медиа-приветствие\n"
        "• <code>/delwelcome</code> — Отключить приветствие\n"
        "• <code>/set rules [текст]</code> или <code>!установитьправила</code> — Записать регламент\n"
        "• <code>/rules</code> или <code>!правила</code> — Вывести правила группы\n"
        "• <code>!отмена</code> — Прервать настройку"
    )

@dp.message(Command("setwelcome", prefix="!/"))
async def set_welcome_cmd(message: Message, state: FSMContext):
    if message.chat.type not in ("group", "supergroup"): return
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Настройка доступна только администраторам.")
    
    await state.set_state(WelcomeSetup.waiting_for_media)
    await state.update_data(chat_id=message.chat.id, admin_id=message.from_user.id)
    await message.answer("<b>🎉 НАСТРОЙКА ПРИВЕТСТВИЯ</b>\n📸 Отправьте фото, видео или GIF-анимацию.\n\n<i>Для отмены напишите: <code>!отмена</code></i>")

@dp.message(WelcomeSetup.waiting_for_media)
async def welcome_media_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.from_user.id != data.get('admin_id'): return

    file_id, media_type = None, None
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
        return await message.answer("❌ Неверный формат. Пожалуйста, пришлите изображение, видео или анимацию.")
    
    if message.caption:
        await db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
                 (data['chat_id'], file_id, media_type, message.caption.strip()))
        await state.clear()
        return await message.answer("<b>✅ ПРИВЕТСТВИЕ УСПЕШНО СОХРАНЕНО!</b>")
        
    await state.update_data(file_id=file_id, media_type=media_type)
    await state.set_state(WelcomeSetup.waiting_for_text)
    await message.answer("✅ Медиа получено!\n📝 Теперь отправьте текст приветствия.")

@dp.message(WelcomeSetup.waiting_for_text)
async def welcome_text_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.from_user.id != data.get('admin_id'): return
    if not message.text: return
    
    await db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
       (data['chat_id'], data['file_id'], data['media_type'], message.text.strip()))
    await state.clear()
    await message.answer("<b>✅ ПРИВЕТСТВИЕ ПОЛНОСТЬЮ УСТАНОВЛЕНО!</b>")

@dp.message(Command("delwelcome", prefix="!/"))
async def del_welcome_cmd(message: Message):
    if message.chat.type not in ("group","supergroup"): return
    if not await is_admin(message.chat.id, message.from_user.id): return
    await db("DELETE FROM welcomes WHERE chat_id=?", (message.chat.id,))
    await message.answer("🗑️ Медиа-приветствие успешно отключено.")

@dp.message(Command("rules", prefix="!/"))
@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!правила", "!rules"))
async def show_rules_cmd(message: Message):
    text = message.text.strip()
    if text.lower().startswith(("/set rules", "!установитьправила", "/setrules")):
        return 

    r = await db("SELECT rules_text FROM rules WHERE chat_id=?", (message.chat.id,), fetch=True)
    if r and r[0][0]:
        await message.answer(f"📋 <b>ПРАВИЛА И РЕГЛАМЕНТ ЧАТА:</b>\n\n{r[0][0]}")
    else:
        await message.answer("📭 Для данной группы правила ещё не были настроены администрацией.")

@dp.message(lambda msg: msg.text and (msg.text.lower().startswith("/set rules") or msg.text.lower().split()[0] in ("!установитьправила", "/setrules")))
async def set_rules_cmd(message: Message, state: FSMContext):
    if message.chat.type not in ("group","supergroup"): return
    if not await is_admin(message.chat.id, message.from_user.id): return
    
    text = message.text.strip()
    if text.lower().startswith("/set rules"):
        parts = text.split(maxsplit=2)
        rules_text = parts[2] if len(parts) > 2 else ""
    else:
        parts = text.split(maxsplit=1)
        rules_text = parts[1] if len(parts) > 1 else ""
        
    if rules_text:
        await db("INSERT OR REPLACE INTO rules (chat_id, rules_text) VALUES (?, ?)", (message.chat.id, rules_text.strip()))
        return await message.answer("<b>✅ РЕГЛАМЕНТ И ПРАВИЛА ЧАТА ОБНОВЛЕНЫ!</b>")
        
    await state.set_state(RulesSetup.waiting_for_rules)
    await state.update_data(chat_id=message.chat.id, admin_id=message.from_user.id)
    await message.answer("📝 Отправьте текст правил Вашего сообщества следующим сообщением:")

@dp.message(RulesSetup.waiting_for_rules)
async def rules_text_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.from_user.id != data.get('admin_id'): return
    if not message.text: return
    
    await db("INSERT OR REPLACE INTO rules (chat_id, rules_text) VALUES (?, ?)", (data['chat_id'], message.text.strip()))
    await state.clear()
    await message.answer("<b>✅ ПРАВИЛА ЧАТА БЛАГОПОЛУЧНО СОХРАНЕНЫ!</b>")

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!мут","!mute"))
async def mute_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if duration is None: return await message.answer("⚠️ Неверный формат. Используйте: !мут 30м @username")
    if not target_id: return await message.answer("❌ Пользователь не найден.")
    if await is_admin(message.chat.id, target_id): return await message.answer("❌ Нельзя выдать мут администратору.")
    
    until = datetime.now(timezone.utc) + timedelta(seconds=duration)
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await message.answer(f"🔇 Участник <b>{target_name}</b> переведен в режим чтения на {duration//60} минут.")
    except:
        await message.answer("❌ Не удалось ограничить права пользователя.")

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!размут","!unmute"))
async def unmute_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.text.split(maxsplit=1)[-1].strip() if len(message.text.split())>1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, target)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_send_polls=True))
        await message.answer(f"🔊 Право отправки сообщений для <b>{target_name}</b> восстановлено.")
    except: pass

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!варн","!warn"))
async def warn_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if duration is None: return await message.answer("⚠️ Формат: !варн 1д @username")
    if not target_id: return await message.answer("❌ Цель не найдена.")
    if await is_admin(message.chat.id, target_id): return
    
    now = int(time.time())
    expires = now + duration
    await db("INSERT INTO warns (user_id, chat_id, issued_at, expires_at) VALUES (?,?,?,?)", (target_id, message.chat.id, now, expires))
    max_warns, ban_duration, _ = await get_warn_settings(message.chat.id)
    active = await get_active_warns(target_id, message.chat.id)
    await message.answer(f"⚜️ Участнику {target_name} вынесено предупреждение ({active}/{max_warns})")
    
    if active >= max_warns:
        until = now + ban_duration if ban_duration else 0
        reason = f"Превышен лимит предупреждений чата ({max_warns})"
        await db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,?,?)", (target_id, message.chat.id, reason, until))
        try:
            await bot.ban_chat_member(message.chat.id, target_id, until_date=None if until==0 else datetime.fromtimestamp(until, tz=timezone.utc))
            await message.answer(f"🚫 {target_name} автоматически заблокирован за систематические нарушения.")
        except: pass

@dp.message(F.text.lower().startswith("!варны лимит"))
async def set_warn_limit(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    nums = re.findall(r'\d+', message.text)
    if not nums: return
    limit = int(nums[0])
    await db("UPDATE warn_settings SET max_warns=? WHERE chat_id=?", (limit, message.chat.id))
    await message.answer(f"⚜️ Порог автоматического бана изменен на: {limit} варна(ов)")

@dp.message(F.text.lower().startswith("!снять варны"))
async def remove_warns_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    args = message.text[12:].strip()
    if not args: return
    target_id, target_name = await resolve_target_from_text(message.chat.id, args)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return
    await db("DELETE FROM warns WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
    await message.answer(f"⚜️ Предупреждения с пользователя {target_name} аннулированы.")

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!бан","!ban","!чс"))
async def ban_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if not target_id: return await message.answer("❌ Участник не найден.")
    if await is_admin(message.chat.id, target_id): return await message.answer("❌ Нельзя блокировать администрацию.")
    
    clean_args = re.sub(r'(@\w+|\d+\s*(м|мин|ч|час|д|день)\b)', '', message.text.split(maxsplit=1)[-1]).strip()
    reason = clean_args or "Нарушение внутренних правил чата"
    now = int(time.time())
    banned_until = now + duration if duration else 0
    await db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,?,?)", (target_id, message.chat.id, reason, banned_until))
    try:
        await bot.ban_chat_member(message.chat.id, target_id, until_date=None if not duration else datetime.fromtimestamp(banned_until, tz=timezone.utc))
        msg = f"🚫 Пользователь <b>{target_name}</b> заблокирован"
        if duration: msg += f" на {duration//3600}ч"
        msg += f"\n📝 Причина: {reason}"
        await message.answer(msg)
    except:
        await message.answer("❌ Не хватило прав на выполнение операции блокировки.")

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!разбан","!unban"))
async def unban_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.text.split(maxsplit=1)[-1].strip() if len(message.text.split())>1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, target)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return
    await db("DELETE FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
    try:
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"✅ Пользователь {target_name} амнистирован.")
    except: pass

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!кик","!kick"))
async def kick_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.text.split(maxsplit=1)[-1].strip() if len(message.text.split())>1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, target)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id or await is_admin(message.chat.id, target_id): return
    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await asyncio.sleep(0.5)
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"👢 Участник {target_name} принудительно удален из группы.")
    except: pass

@dp.message(F.text.lower().startswith("!амнистия"))
async def amnesty_cmd(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    rows = await db("SELECT user_id FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    for (uid,) in rows:
        try: await bot.unban_chat_member(message.chat.id, uid)
        except: pass
    await db("DELETE FROM bans WHERE chat_id=?", (message.chat.id,))
    await message.answer("🔓 <b>Глобальная амнистия:</b> ЧС чата полностью очищен.")

@dp.message(F.text.lower().startswith("!банлист"))
async def banlist_cmd(message: Message):
    rows = await db("SELECT user_id, reason, banned_until FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not rows: return await message.answer("📭 Список заблокированных пользователей пуст.")
    lines = []
    for uid, reason, until in rows:
        try:
            user = await bot.get_chat(uid)
            name = user.first_name or str(uid)
        except: name = str(uid)
        dur = "вечно" if until==0 else f"до {datetime.fromtimestamp(until).strftime('%d.%m %H:%M')}"
        lines.append(f"• {name} — {reason} ({dur})")
    await message.answer("🚫 <b>СПИСОК БЛОКИРОВОК ЧАТА:</b>\n\n" + "\n".join(lines))

@dp.message(F.text.lower().startswith("!запретслово"))
async def add_forbidden_word(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await message.answer("Использование: !запретслово [слово]")
    word = parts[1].strip().lower()
    if not word: return
    try:
        await db("INSERT OR IGNORE INTO forbidden_words (chat_id, word) VALUES (?,?)", (message.chat.id, word))
        await message.answer(f"🔞 Слово «{word}» добавлено в фильтр.")
    except: pass

@dp.message(F.text.lower().startswith("!разрешслово"))
async def del_forbidden_word(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await message.answer("Использование: !разрешслово [слово]")
    word = parts[1].strip().lower()
    await db("DELETE FROM forbidden_words WHERE chat_id=? AND word=?", (message.chat.id, word))
    await message.answer(f"🔓 Слово «{word}» убрано из фильтра.")

@dp.message(F.text.lower().startswith("!списокзапретов"))
async def list_forbidden_words(message: Message):
    chat_words = [row[0] for row in await db("SELECT word FROM forbidden_words WHERE chat_id=?", (message.chat.id,), fetch=True)]
    words = DEFAULT_FORBIDDEN + chat_words
    await message.answer("🔞 <b>ФИЛЬТРУЕМЫЕ СЛОВА ЧАТА:</b>\n\n" + ", ".join(words[:30]) + ("..." if len(words)>30 else ""))


@dp.message(F.new_chat_members)
async def new_member_handler(message: Message):
    chat_id = message.chat.id
    welcome_data = await db("SELECT file_id, media_type, caption FROM welcomes WHERE chat_id=?", (chat_id,), fetch=True)

    for member in message.new_chat_members:
        if member.is_bot: continue
        
        try:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=member.id,
                permissions=ChatPermissions(can_send_messages=False)
            )
        except Exception as e:
            logging.error(f"Restrict error: {e}")

        name = member.first_name or "Участник"
        mention = f'<a href="tg://user?id={member.id}">{name}</a>'
        gender_verb = detect_gender_verb(member.first_name)
        
        welcome_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🛡 Пройти верификацию", callback_data=f"verify_{member.id}")
            ]
        ])
        
        if welcome_data and welcome_data[0]:
            file_id, media_type, caption = welcome_data[0]
            text = caption.replace("{name}", name).replace("{mention}", mention).replace("{verb}", gender_verb)
            try:
                count = await bot.get_chat_member_count(chat_id)
                text = text.replace("{count}", str(count))
            except: pass
            
            try:
                if media_type == "photo":
                    await bot.send_photo(chat_id, file_id, caption=text, reply_markup=welcome_keyboard, message_thread_id=tid(message))
                elif media_type == "video":
                    await bot.send_video(chat_id, file_id, caption=text, reply_markup=welcome_keyboard, message_thread_id=tid(message))
                elif media_type == "animation":
                    await bot.send_animation(chat_id, file_id, caption=text, reply_markup=welcome_keyboard, message_thread_id=tid(message))
                continue
            except Exception as e:
                logging.error(f"Media send failed: {e}")
        
        default_text = (
            f"👋 Привет, {mention}!\n\n"
            f"Рады, что ты <b>{gender_verb}</b> в чат мессенджера VOID!\n"
            f"⚠️ Нажми кнопку <b>«🛡 Пройти верификацию»</b> ниже, чтобы разблокировать отправку сообщений."
        )
        try:
            await bot.send_message(chat_id, default_text, reply_markup=welcome_keyboard, message_thread_id=tid(message))
        except Exception as e:
            logging.error(f"Text send failed: {e}")

@dp.callback_query(F.data.startswith("verify_"))
async def process_verification(callback: CallbackQuery):
    target_user_id = int(callback.data.split("_")[1])
    clicker_user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if clicker_user_id != target_user_id:
        return await callback.answer("❌ Эта верификация создана не для Вас!", show_alert=True)
        
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=clicker_user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_send_polls=True
            )
        )
        
        await callback.answer("✅ Верификация успешно пройдена!", show_alert=True)
        
        # Отправка нового текстового сообщения в чат
        user_name = callback.from_user.first_name or "Участник"
        user_mention = f'<a href="tg://user?id={clicker_user_id}">{user_name}</a>'
        await callback.message.answer(
            f"🎉 {user_mention} успешно верифицировался, можешь писать!",
            message_thread_id=tid(callback.message)
        )
        
        verified_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Пройдено", callback_data="already_verified")
            ]
        ])
        
        await callback.message.edit_reply_markup(reply_markup=verified_keyboard)
        
    except Exception as e:
        logging.error(f"Unmute error: {e}")
        await callback.answer("❌ Ошибка размута. Проверьте права бота в администраторах чата!", show_alert=True)

@dp.callback_query(F.data == "already_verified")
async def process_already_verified(callback: CallbackQuery):
    await callback.answer("Успешно верифицирован!", show_alert=False)


async def main():
    await init_db()
    try: 
        await bot.delete_my_commands()
    except: 
        pass
    try: 
        await bot.delete_webhook(drop_pending_updates=True)
    except: 
        pass
    
    me = await bot.get_me()
    print(f"Запуск прошел успешно. Профиль бота: @{me.username}")
    await dp.start_polling(bot, timeout=60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
