# ============================================================
#  VOID HELPER BOT — МОДЕРАЦИЯ + АВТОЗАКРЫТИЕ + ФИЛЬТР СЛОВ
#  Список запрещённых слов заменён на пользовательский
# ============================================================
import asyncio
import sqlite3
import logging
import time
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import ChatPermissions
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(level=logging.INFO)  # Изменил на INFO для отладки

TOKEN    = '8203364413:AAHBW_Aek57yZvvSf5JzrYElxLOCky_vnEY'
OWNER_ID = 7173827114
DB_NAME  = 'void_bot.db'

# ---------- СПИСОК ЗАПРЕЩЁННЫХ СЛОВ ----------
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
    "диспареуния", "аноргазмия", "преждевременная эякуляция", "эректильная дисфункция",
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
    'CREATE TABLE IF NOT EXISTS warns (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, issued_at INTEGER, expires_at INTEGER)',
    'CREATE TABLE IF NOT EXISTS warn_settings (chat_id INTEGER PRIMARY KEY, max_warns INTEGER DEFAULT 3, ban_duration INTEGER DEFAULT 0, warn_duration INTEGER DEFAULT 86400)',
    'CREATE TABLE IF NOT EXISTS bans (user_id INTEGER, chat_id INTEGER, reason TEXT DEFAULT "", banned_until INTEGER DEFAULT 0, PRIMARY KEY(user_id,chat_id))',
    'CREATE TABLE IF NOT EXISTS welcomes (chat_id INTEGER PRIMARY KEY, file_id TEXT, media_type TEXT, caption TEXT)',
    'CREATE TABLE IF NOT EXISTS schedules (chat_id INTEGER PRIMARY KEY, close_time TEXT, open_time TEXT, enabled INTEGER DEFAULT 0)',
    'CREATE TABLE IF NOT EXISTS forbidden_words (chat_id INTEGER, word TEXT, PRIMARY KEY(chat_id, word))',
]:
    db(sql)

# ---------- Вспомогательные функции ----------
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

def parse_duration(duration_str: str) -> int:
    return extract_duration(duration_str)[0] or 3600

async def parse_moderation_args(message: types.Message):
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

def get_warn_settings(chat_id):
    r = db("SELECT max_warns, ban_duration, warn_duration FROM warn_settings WHERE chat_id=?", (chat_id,), fetch=True)
    if r: return r[0]
    db("INSERT INTO warn_settings (chat_id) VALUES (?)", (chat_id,))
    return (3, 0, 86400)

def get_active_warns(uid, chat_id):
    now = int(time.time())
    r = db("SELECT COUNT(*) FROM warns WHERE user_id=? AND chat_id=? AND expires_at > ?", (uid, chat_id, now), fetch=True)
    return r[0][0] if r else 0

# ---------- Расписание ----------
closed_chats = set()

async def schedule_task():
    while True:
        try:
            rows = db("SELECT chat_id, close_time, open_time FROM schedules WHERE enabled=1", fetch=True)
            now = datetime.now().strftime("%H:%M")
            for chat_id, close, open_t in rows:
                close_min = int(close.split(":")[0])*60 + int(close.split(":")[1])
                open_min = int(open_t.split(":")[0])*60 + int(open_t.split(":")[1])
                now_min = int(now.split(":")[0])*60 + int(now.split(":")[1])
                should = False
                if close_min < open_min:
                    if close_min <= now_min < open_min: should = True
                else:
                    if now_min >= close_min or now_min < open_min: should = True
                if should:
                    if chat_id not in closed_chats:
                        try:
                            await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
                            closed_chats.add(chat_id)
                        except: pass
                else:
                    if chat_id in closed_chats:
                        try:
                            await bot.set_chat_permissions(chat_id,
                                ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                                                can_send_polls=True, can_send_other_messages=True,
                                                can_add_web_page_previews=True, can_change_info=True,
                                                can_invite_users=True, can_pin_messages=True))
                            closed_chats.discard(chat_id)
                        except: pass
        except Exception as e:
            logging.error(f"Schedule: {e}")
        await asyncio.sleep(60)

# ===================== MIDDLEWARE ДЛЯ ФИЛЬТРА СЛОВ =====================
from aiogram import BaseMiddleware
from aiogram.types import Message

class WordFilterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        # Проверяем только текстовые сообщения в группах
        if event.text and event.chat.type in ('group', 'supergroup'):
            # Пропускаем команды (начинаются с ! или /)
            if event.text.startswith('!') or event.text.startswith('/'):
                return await handler(event, data)
            
            # Проверяем запрещённые слова
            chat_id = event.chat.id
            chat_words = [row[0] for row in db("SELECT word FROM forbidden_words WHERE chat_id=?", (chat_id,), fetch=True)]
            words = DEFAULT_FORBIDDEN + chat_words
            
            msg_lower = event.text.lower()
            for w in words:
                if w in msg_lower:
                    try:
                        await bot.delete_message(chat_id, event.message_id)
                        warning = await event.answer(
                            f"⚠️ {event.from_user.first_name}, сообщение удалено: запрещённое слово."
                        )
                        # Удаляем предупреждение через 5 секунд
                        await asyncio.sleep(5)
                        await warning.delete()
                    except Exception as e:
                        logging.error(f"Filter delete error: {e}")
                    return  # Не передаём сообщение дальше
        
        return await handler(event, data)

# Регистрируем middleware
dp.message.middleware(WordFilterMiddleware())

# ===================== КОМАНДЫ =====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.type != "private": return
    await message.answer("👋 Привет! Я VOID Helper – бот модерации и расписания.\n\n📋 /help – список команд\n📘 /adminhelp – административная справка")

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer(
        "<b>📖 VOID HELPER – МОДЕРАЦИЯ</b>\n\n"
        "🛡 <b>Модерация</b>\n"
        "!мут <срок> <цель> | !размут <цель>\n"
        "!варн <срок> <цель> | !варны лимит/чс/период/помощь\n"
        "!бан <срок?> <цель> [причина] | !разбан <цель>\n"
        "!кик <цель> | !амнистия | !банлист\n"
        "!админ <цель> / -админ <цель>\n\n"
        "🔞 <b>Фильтр запрещённых слов</b>\n"
        "Добавление своих слов: !запретслово <слово>\n"
        "Удаление: !разрешслово <слово>\n"
        "Список: !списокзапретов\n\n"
        "🕒 <b>Расписание</b>\n"
        "/setautoschedule <HH:MM> <HH:MM>\n"
        "/setautoschedule off\n\n"
        "🎉 <b>Приветствие</b> /welcome /delwelcome"
    )

# ---------- Приветствие ----------
@dp.message(Command("welcome"))
async def welcome_cmd(message: types.Message, state: FSMContext):
    if message.chat.type not in ("group","supergroup"): return
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только для администраторов!")
    await state.set_state(WelcomeSetup.waiting_for_media)
    await state.update_data(chat_id=message.chat.id)
    await message.answer("<b>🎉 УСТАНОВКА ПРИВЕТСТВИЯ</b>\n📸 ОТПРАВЬ ФОТО, ВИДЕО ИЛИ ГИФКУ")

@dp.message(WelcomeSetup.waiting_for_media)
async def welcome_media_handler(message: types.Message, state: FSMContext):
    file_id, media_type = None, None
    if message.photo:
        file_id = message.photo[-1].file_id; media_type = "photo"
    elif message.video:
        file_id = message.video.file_id; media_type = "video"
    elif message.animation:
        file_id = message.animation.file_id; media_type = "animation"
    else:
        return await message.answer("❌ Отправь фото, видео или гифку!")
    await state.update_data(file_id=file_id, media_type=media_type)
    await state.set_state(WelcomeSetup.waiting_for_text)
    await message.answer("✅ Медиа получено!\n📝 Напиши текст приветствия")

@dp.message(WelcomeSetup.waiting_for_text)
async def welcome_text_handler(message: types.Message, state: FSMContext):
    if not message.text: return
    data = await state.get_data()
    chat_id, file_id, media_type = data['chat_id'], data['file_id'], data['media_type']
    text = message.text.strip()
    db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
       (chat_id, file_id, media_type, text))
    await state.clear()
    await message.answer(f"<b>✅ ПРИВЕТСТВИЕ УСТАНОВЛЕНО!</b>")

@dp.message(Command("delwelcome"))
async def del_welcome_cmd(message: types.Message):
    if message.chat.type not in ("group","supergroup"): return
    if not await is_admin(message.chat.id, message.from_user.id): return
    db("DELETE FROM welcomes WHERE chat_id=?", (message.chat.id,))
    await message.answer("🗑️ Приветствие удалено")

@dp.message(F.new_chat_members)
async def new_member_handler(message: types.Message):
    chat_id = message.chat.id
    r = db("SELECT file_id, media_type, caption FROM welcomes WHERE chat_id=?", (chat_id,), fetch=True)
    if not r: return
    file_id, media_type, caption = r[0]
    for member in message.new_chat_members:
        if member.is_bot: continue
        name = member.first_name or "Гость"
        mention = f"@{member.username}" if member.username else name
        text = caption.replace("{name}", name).replace("{mention}", mention)
        try:
            count = await bot.get_chat_members_count(chat_id)
            text = text.replace("{count}", str(count))
        except: pass
        try:
            if media_type == "photo":
                await bot.send_photo(chat_id, file_id, caption=text, message_thread_id=tid(message))
            elif media_type == "video":
                await bot.send_video(chat_id, file_id, caption=text, message_thread_id=tid(message))
            elif media_type == "animation":
                await bot.send_animation(chat_id, file_id, caption=text, message_thread_id=tid(message))
        except Exception as e:
            logging.error(f"Welcome send error: {e}")

# ---------- Модерация ----------
@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!мут","!mute","!заткнуть") for _ in [0]))
async def mute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if duration is None: return await message.answer("⚠️ Укажи длительность. Пример: !мут 1ч @user")
    if not target_id: return await message.answer("❌ Укажи цель (@username или ответ)!")
    if await is_admin(message.chat.id, target_id): return await message.answer("❌ Нельзя замьютить администратора.")
    until = datetime.now(timezone.utc) + timedelta(seconds=duration)
    try:
        await bot.restrict_chat_member(message.chat.id, target_id,
                                       permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await message.answer(f"🔇 {target_name} замьючен на {duration//60} мин")
    except:
        await message.answer("❗ Не удалось замьютить. Проверь права бота.")

@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!размут","!unmute","!говори") for _ in [0]))
async def unmute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.text.split(maxsplit=1)[-1].strip() if len(message.text.split())>1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, target)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return await message.answer("❌ Цель не найдена.")
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=ChatPermissions(can_send_messages=True))
        await message.answer(f"🔊 {target_name} размьючен")
    except: pass

@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!варн","!warn","!пред","!предупреждение") for _ in [0]))
async def warn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if duration is None: return await message.answer("⚠️ Укажи срок. Пример: !варн 1ч @user")
    if not target_id: return await message.answer("❌ Укажи цель!")
    if await is_admin(message.chat.id, target_id): return await message.answer("❌ Нельзя выдать варн администратору.")
    now = int(time.time())
    expires = now + duration
    db("INSERT INTO warns (user_id, chat_id, issued_at, expires_at) VALUES (?,?,?,?)", (target_id, message.chat.id, now, expires))
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
            await message.answer(f"🚫 {target_name} забанен по лимиту варнов.")
        except: pass

@dp.message(F.text.lower().startswith("!варны лимит"))
async def set_warn_limit(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    nums = re.findall(r'\d+', message.text)
    if not nums: return
    limit = int(nums[0])
    max_warns, ban_duration, warn_duration = get_warn_settings(message.chat.id)
    db("UPDATE warn_settings SET max_warns=? WHERE chat_id=?", (limit, message.chat.id))
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
    target_id, target_name = await resolve_target_from_text(message.chat.id, target_str)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return await message.answer("Пользователь не найден.")
    active = get_active_warns(target_id, message.chat.id)
    await message.answer(f"⚜️ {target_name}: {active} активных варнов")

@dp.message(F.text.lower().startswith("!снять варны"))
async def remove_warns_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    args = message.text[12:].strip()
    if not args: return
    parts = args.split()
    num = None; target_str = args
    if parts[0].isdigit():
        num = int(parts[0]); target_str = " ".join(parts[1:])
    target_id, target_name = await resolve_target_from_text(message.chat.id, target_str)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return
    now = int(time.time())
    if num:
        rows = db("SELECT id FROM warns WHERE user_id=? AND chat_id=? AND expires_at>? ORDER BY issued_at ASC LIMIT ?",
                  (target_id, message.chat.id, now, num), fetch=True)
        for r in rows: db("DELETE FROM warns WHERE id=?", (r[0],))
        await message.answer(f"⚜️ Снято {len(rows)} варнов с {target_name}")
    else:
        db("DELETE FROM warns WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
        await message.answer(f"⚜️ Все варны сняты с {target_name}")

@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!бан","!ban","!permban","!чс") for _ in [0]))
async def ban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if not target_id: return await message.answer("❌ Укажи цель!")
    if await is_admin(message.chat.id, target_id): return await message.answer("❌ Нельзя забанить администратора.")
    clean_args = re.sub(r'(@\w+|\d+\s*(м|мин|ч|час|д|день)\b)', '', message.text.split(maxsplit=1)[-1]).strip()
    reason = clean_args or ""
    now = int(time.time())
    banned_until = now + duration if duration else 0
    db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,?,?)",
       (target_id, message.chat.id, reason, banned_until))
    try:
        await bot.ban_chat_member(message.chat.id, target_id,
                                  until_date=None if not duration else datetime.fromtimestamp(banned_until, tz=timezone.utc))
        msg = f"🚫 {target_name} забанен"
        if duration: msg += f" на {duration//3600}ч"
        if reason: msg += f"\nПричина: {reason}"
        await message.answer(msg)
    except:
        await message.answer("❗ Не удалось забанить.")

@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!разбан","!unban") for _ in [0]))
async def unban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.text.split(maxsplit=1)[-1].strip() if len(message.text.split())>1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, target)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return
    db("DELETE FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
    try:
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"✅ {target_name} разбанен")
    except: pass

@dp.message(F.text.lower().startswith("!причина"))
async def reason_cmd(message: types.Message):
    target_id, target_name = await resolve_target_from_text(message.chat.id, message.text[9:].strip())
    if not target_id: target_id, _ = await resolve_target_from_reply(message)
    if not target_id: return
    r = db("SELECT reason FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id), fetch=True)
    if r:
        await message.answer(f"Причина: {r[0][0] if r[0][0] else 'не указана'}")
    else:
        await message.answer("Пользователь не забанен или причина отсутствует.")

@dp.message(lambda msg: msg.text and any(msg.text.lower().split()[0] in ("!кик","!kick") for _ in [0]))
async def kick_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.text.split(maxsplit=1)[-1].strip() if len(message.text.split())>1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, target)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id or await is_admin(message.chat.id, target_id): return
    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await asyncio.sleep(1)
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"👢 {target_name} кикнут")
    except: pass

@dp.message(F.text.lower().startswith("!амнистия"))
async def amnesty_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    rows = db("SELECT user_id FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    for (uid,) in rows:
        try: await bot.unban_chat_member(message.chat.id, uid)
        except: pass
    db("DELETE FROM bans WHERE chat_id=?", (message.chat.id,))
    await message.answer("🔓 Амнистия: все баны сняты.")

@dp.message(F.text.lower().startswith("!банлист"))
async def banlist_cmd(message: types.Message):
    rows = db("SELECT user_id, reason, banned_until FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not rows: return await message.answer("📭 Нет забаненных")
    lines = []
    for uid, reason, until in rows:
        try:
            user = await bot.get_chat(uid)
            name = user.first_name or str(uid)
        except: name = str(uid)
        dur = "навсегда" if until==0 else f"до {datetime.fromtimestamp(until)}"
        lines.append(f"• {name} — {reason if reason else '—'} ({dur})")
    await message.answer("\n".join(lines))

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

# ========== Команды фильтра слов ==========
@dp.message(F.text.lower().startswith("!запретслово"))
async def add_forbidden_word(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await message.answer("Используй: !запретслово <слово>")
    word = parts[1].strip().lower()
    if not word: return
    try:
        db("INSERT OR IGNORE INTO forbidden_words (chat_id, word) VALUES (?,?)", (message.chat.id, word))
        await message.answer(f"🔞 Слово '{word}' добавлено в запрещённые.")
    except: pass

@dp.message(F.text.lower().startswith("!разрешслово"))
async def del_forbidden_word(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await message.answer("Используй: !разрешслово <слово>")
    word = parts[1].strip().lower()
    db("DELETE FROM forbidden_words WHERE chat_id=? AND word=?", (message.chat.id, word))
    await message.answer(f"🔓 Слово '{word}' удалено из списка.")

@dp.message(F.text.lower().startswith("!списокзапретов"))
async def list_forbidden_words(message: types.Message):
    chat_words = [row[0] for row in db("SELECT word FROM forbidden_words WHERE chat_id=?", (message.chat.id,), fetch=True)]
    words = DEFAULT_FORBIDDEN + chat_words
    if not words: return await message.answer("Список пуст.")
    await message.answer("🔞 Запрещённые слова:\n" + ", ".join(words[:50]) + ("..." if len(words)>50 else ""))

# ---------- /adminhelp ----------
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
        "⚜️<b>Банлист</b> ⚜️ список забаненных в данной беседе\n\n"
        "🔞 <b>Встроенный фильтр слов (сексуальная лексика).</b>\n"
        "Дополнительно можно добавлять свои слова: !запретслово <слово>, !разрешслово <слово>, !списокзапретов.",
        parse_mode="HTML"
    )

# ---------- Расписание ----------
@dp.message(Command("setautoschedule"))
async def set_schedule(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    if message.chat.type not in ("group","supergroup"): return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: /setautoschedule <HH:MM закрытия> <HH:MM открытия>\n/setautoschedule off")
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
    if len(args) < 3: return
    close_str, open_str = args[1], args[2]
    if not re.match(r'^\d{1,2}:\d{2}$', close_str) or not re.match(r'^\d{1,2}:\d{2}$', open_str):
        return await message.answer("❌ Формат времени: HH:MM")
    db("INSERT OR REPLACE INTO schedules (chat_id, close_time, open_time, enabled) VALUES (?,?,?,1)",
       (message.chat.id, close_str, open_str))
    await message.answer(f"✔ Закрытие: {close_str}, открытие: {open_str}")

# ---------- Запуск ----------
async def main():
    try: await bot.delete_webhook(drop_pending_updates=True)
    except: pass
    asyncio.create_task(schedule_task())
    me = await bot.get_me()
    print(f"✅ БОТ ГОТОВ: @{me.username}")
    try: await dp.start_polling(bot, timeout=60)
    except KeyboardInterrupt: print("Отключено")

if __name__ == "__main__":
    asyncio.run(main())
