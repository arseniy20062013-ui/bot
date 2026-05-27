import asyncio
import aiosqlite
import logging
import time
import re
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import ChatPermissions, Message
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

logging.basicConfig(level=logging.INFO)

# Рекомендуется выносить токен в переменные окружения. 
# Замените заглушку на Ваш реальный токен, если не используете .env
TOKEN    = os.getenv('BOT_TOKEN', '8203364413:AAHBW_Aek57yZvvSf5JzrYElxLOCky_vnEY')
OWNER_ID = 7173827114
DB_NAME  = 'void_bot.db'

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

class WelcomeSetup(StatesGroup):
    waiting_for_media = State()
    waiting_for_text = State()

class RulesSetup(StatesGroup):
    waiting_for_rules = State()

storage = MemoryStorage()
session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=storage)

# --- АСИНХРОННЫЙ ДВИЖОК БАЗЫ ДАННЫХ ---
async def db(query: str, params: tuple = (), fetch: bool = False):
    try:
        async with aiosqlite.connect(DB_NAME) as conn:
            async with conn.execute(query, params) as cur:
                if fetch:
                    return await cur.fetchall()
                await conn.commit()
    except Exception as e:
        logging.error(f"Database Async Error: {e}")
    return [] if fetch else False

async def init_db():
    tables = [
        'CREATE TABLE IF NOT EXISTS warns (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, issued_at INTEGER, expires_at INTEGER)',
        'CREATE TABLE IF NOT EXISTS warn_settings (chat_id INTEGER PRIMARY KEY, max_warns INTEGER DEFAULT 3, ban_duration INTEGER DEFAULT 0, warn_duration INTEGER DEFAULT 86400)',
        'CREATE TABLE IF NOT EXISTS bans (user_id INTEGER, chat_id INTEGER, reason TEXT DEFAULT "", banned_until INTEGER DEFAULT 0, PRIMARY KEY(user_id,chat_id))',
        'CREATE TABLE IF NOT EXISTS welcomes (chat_id INTEGER PRIMARY KEY, file_id TEXT, media_type TEXT, caption TEXT)',
        'CREATE TABLE IF NOT EXISTS schedules (chat_id INTEGER PRIMARY KEY, close_time TEXT, open_time TEXT, enabled INTEGER DEFAULT 0)',
        'CREATE TABLE IF NOT EXISTS forbidden_words (chat_id INTEGER, word TEXT, PRIMARY KEY(chat_id, word))',
        'CREATE TABLE IF NOT EXISTS rules (chat_id INTEGER PRIMARY KEY, rules_text TEXT)'
    ]
    for sql in tables:
        await db(sql)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
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

def detect_gender_verb(first_name: str) -> str:
    if not first_name:
        return "зашёл(ла)"
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

async def parse_duration(duration_str: str) -> int:
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

async def get_warn_settings(chat_id):
    r = await db("SELECT max_warns, ban_duration, warn_duration FROM warn_settings WHERE chat_id=?", (chat_id,), fetch=True)
    if r: return r[0]
    await db("INSERT INTO warn_settings (chat_id) VALUES (?)", (chat_id,))
    return (3, 0, 86400)

async def get_active_warns(uid, chat_id):
    now = int(time.time())
    r = await db("SELECT COUNT(*) FROM warns WHERE user_id=? AND chat_id=? AND expires_at > ?", (uid, chat_id, now), fetch=True)
    return r[0][0] if r else 0

closed_chats = set()

async def schedule_task():
    while True:
        try:
            rows = await db("SELECT chat_id, close_time, open_time FROM schedules WHERE enabled=1", fetch=True)
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

# --- MIDDLEWARE ФИЛЬТРАЦИИ СЛОВ ---
class WordFilterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        if event.text and event.chat.type in ('group', 'supergroup'):
            # Пропускаем команды
            if event.text.startswith('!') or event.text.startswith('/') or event.text.startswith('-'):
                return await handler(event, data)

            # Пропускаем, если пользователь находится в процессе FSM (заполняет анкету/настройки)
            state: FSMContext = data.get("state")
            if state and await state.get_state() is not None:
                return await handler(event, data)

            chat_id = event.chat.id
            chat_words = [row[0] for row in await db("SELECT word FROM forbidden_words WHERE chat_id=?", (chat_id,), fetch=True)]
            words = DEFAULT_FORBIDDEN + chat_words

            msg_lower = event.text.lower()
            for w in words:
                # Используем поиск по границе слова, чтобы избежать ложных срабатываний (например, "корни")
                if re.search(rf"\b{re.escape(w)}", msg_lower):
                    try:
                        user_name = event.from_user.full_name
                        user_link = f'<a href="tg://user?id={event.from_user.id}">{user_name}</a>'

                        await event.answer(
                            f"🗑 <b>Сообщение от {user_link} удалено</b>\n"
                            f"📝 <i>Текст:</i> {event.text}\n"
                            f"⚠️ Причина: запрещённое слово",
                            disable_web_page_preview=True
                        )
                        await bot.delete_message(chat_id, event.message_id)
                    except Exception as e:
                        logging.error(f"Filter delete error: {e}")
                    return

        return await handler(event, data)

dp.message.middleware(WordFilterMiddleware())

# --- КОМАНДЫ ПРИВЕТСТВИЯ И ПРАВИЛ ---

@dp.message(Command("setwelcome"))
async def set_welcome_cmd(message: types.Message, state: FSMContext):
    if message.chat.type not in ("group", "supergroup"): return
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.answer("❌ Только для администраторов!")
    
    # Если администратор прикрепил медиафайл и сразу написал команду /setwelcome в описании
    if message.caption and message.caption.startswith("/setwelcome"):
        file_id, media_type = None, None
        if message.photo: file_id = message.photo[-1].file_id; media_type = "photo"
        elif message.video: file_id = message.video.file_id; media_type = "video"
        elif message.animation: file_id = message.animation.file_id; media_type = "animation"
        
        if file_id:
            text = message.caption.replace("/setwelcome", "").strip()
            await db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
                     (message.chat.id, file_id, media_type, text))
            return await message.answer("<b>✅ ПРИВЕТСТВИЕ УСТАНОВЛЕНО!</b> (Медиа и текст успешно сохранены)")

    await state.set_state(WelcomeSetup.waiting_for_media)
    await state.update_data(chat_id=message.chat.id)
    await message.answer("<b>🎉 УСТАНОВКА ПРИВЕТСТВИЯ</b>\n📸 Отправьте фото, видео или гифку.\n<i>Вы можете сразу написать текст приветствия в описании к медиафайлу!</i>")

@dp.message(WelcomeSetup.waiting_for_media)
async def welcome_media_handler(message: types.Message, state: FSMContext):
    file_id, media_type = None, None
    if message.photo: file_id = message.photo[-1].file_id; media_type = "photo"
    elif message.video: file_id = message.video.file_id; media_type = "video"
    elif message.animation: file_id = message.animation.file_id; media_type = "animation"
    else:
        return await message.answer("❌ Пожалуйста, отправьте фото, видео или гифку!")
    
    # Если текст уже был в описании к медиа
    if message.caption:
        data = await state.get_data()
        await db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
                 (data['chat_id'], file_id, media_type, message.caption.strip()))
        await state.clear()
        return await message.answer("<b>✅ ПРИВЕТСТВИЕ УСТАНОВЛЕНО!</b>")
        
    await state.update_data(file_id=file_id, media_type=media_type)
    await state.set_state(WelcomeSetup.waiting_for_text)
    await message.answer("✅ Медиа получено!\n📝 Теперь напишите и отправьте текст приветствия.\n\n"
                         "📋 <i>Доступные переменные:</i>\n"
                         "<code>{name}</code> — Имя\n"
                         "<code>{mention}</code> — Упоминание\n"
                         "<code>{count}</code> — Номер участника\n"
                         "<code>{verb}</code> — Авто-род (зашёл/зашла)")

@dp.message(WelcomeSetup.waiting_for_text)
async def welcome_text_handler(message: types.Message, state: FSMContext):
    if not message.text: return
    data = await state.get_data()
    await db("INSERT OR REPLACE INTO welcomes (chat_id, file_id, media_type, caption) VALUES (?,?,?,?)",
       (data['chat_id'], data['file_id'], data['media_type'], message.text.strip()))
    await state.clear()
    await message.answer("<b>✅ ПРИВЕТСТВИЕ УСТАНОВЛЕНО!</b>")

@dp.message(Command("delwelcome"))
async def del_welcome_cmd(message: types.Message):
    if message.chat.type not in ("group","supergroup"): return
    if not await is_admin(message.chat.id, message.from_user.id): return
    await db("DELETE FROM welcomes WHERE chat_id=?", (message.chat.id,))
    await message.answer("🗑️ Приветствие удалено.")

# --- УПРАВЛЕНИЕ ПРАВИЛАМИ ЧАТА ---
@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!установитьправила", "/setrules"))
async def set_rules_cmd(message: types.Message, state: FSMContext):
    if message.chat.type not in ("group","supergroup"): return
    if not await is_admin(message.chat.id, message.from_user.id): return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        await db("INSERT OR REPLACE INTO rules (chat_id, rules_text) VALUES (?, ?)", (message.chat.id, parts[1].strip()))
        return await message.answer("<b>✅ ПРАВИЛА ЧАТА ОБНОВЛЕНЫ!</b>")
        
    await state.set_state(RulesSetup.waiting_for_rules)
    await state.update_data(chat_id=message.chat.id)
    await message.answer("📝 Напишите и отправьте текст правил для Вашего чата:")

@dp.message(RulesSetup.waiting_for_rules)
async def rules_text_handler(message: types.Message, state: FSMContext):
    if not message.text: return
    data = await state.get_data()
    await db("INSERT OR REPLACE INTO rules (chat_id, rules_text) VALUES (?, ?)", (data['chat_id'], message.text.strip()))
    await state.clear()
    await message.answer("<b>✅ ПРАВИЛА ЧАТА УСПЕШНО СОХРАНЕНЫ!</b>")

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!правила", "/rules"))
async def show_rules_cmd(message: types.Message):
    r = await db("SELECT rules_text FROM rules WHERE chat_id=?", (message.chat.id,), fetch=True)
    if r and r[0][0]:
        await message.answer(f"📋 <b>ПРАВИЛА ЧАТА:</b>\n\n{r[0][0]}")
    else:
        await message.answer("📭 Правила в данном чате ещё не установлены.")

# --- ОБРАБОТЧИК ВХОДА УЧАСТНИКА ---
@dp.message(F.new_chat_members)
async def new_member_handler(message: types.Message):
    chat_id = message.chat.id
    welcome_data = await db("SELECT file_id, media_type, caption FROM welcomes WHERE chat_id=?", (chat_id,), fetch=True)
    rules_data = await db("SELECT rules_text FROM rules WHERE chat_id=?", (chat_id,), fetch=True)
    
    for member in message.new_chat_members:
        if member.is_bot: continue
        name = member.first_name or "Участник"
        mention = f"@{member.username}" if member.username else name
        gender_verb = detect_gender_verb(member.first_name)
        
        # Сборка приветствия
        if welcome_data:
            file_id, media_type, caption = welcome_data[0]
            text = caption.replace("{name}", name).replace("{mention}", mention).replace("{verb}", gender_verb)
            try:
                count = await bot.get_chat_member_count(chat_id)
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
                
        # Автоматическая отправка правил
        if rules_data and rules_data[0][0]:
            await message.answer(f"Приветствуем Вас, {mention}! Пожалуйста, ознакомьтесь с правилами группы:\n\n{rules_data[0][0]}", 
                                 message_thread_id=tid(message))

# --- ОСТАЛЬНЫЕ МОДЕРАЦИОННЫЕ КОМАНДЫ (ОПТИМИЗИРОВАНЫ) ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("👋 Приветствуем! Я VOID Helper – бот модерации, правил и расписания.\n\n📋 /help – список команд\n📘 /adminhelp – административная справка")

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer(
        "<b>📖 VOID HELPER – ИНФОРМАЦИЯ</b>\n\n"
        "🛡 <b>Модерация</b>\n"
        "!мут <срок> <цель> | !размут <цель>\n"
        "!варн <срок> <цель> | !варны лимит/чс/период/помощь\n"
        "!бан <срок?> <цель> [причина] | !разбан <цель>\n"
        "!кик <цель> | !амнистия | !банлист\n"
        "!админ <цель> / -админ <цель>\n\n"
        "🔞 <b>Фильтр запрещённых слов</b>\n"
        "Добавление слов: !запретслово <слово>\n"
        "Удаление: !разрешслово <слово>\n"
        "Список: !списокзапретов\n\n"
        "🕒 <b>Расписание</b>\n"
        "/setautoschedule <HH:MM> <HH:MM>\n"
        "/setautoschedule off\n\n"
        "🎉 <b>Приветствие и Правила</b>\n"
        "/setwelcome — Настройка приветствия\n"
        "/delwelcome — Удалить приветствие\n"
        "!установитьправила — Настроить правила чата\n"
        "!правила — Посмотреть правила чата"
    )

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!мут","!mute","!заткнуть"))
async def mute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if duration is None: return await message.answer("⚠️ Укажите длительность. Пример: !мут 1ч @user")
    if not target_id: return await message.answer("❌ Укажите цель (@username или ответ)!")
    if await is_admin(message.chat.id, target_id): return await message.answer("❌ Нельзя замьютить администратора.")
    until = datetime.now(timezone.utc) + timedelta(seconds=duration)
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await message.answer(f"🔇 {target_name} замьючен на {duration//60} мин.")
    except:
        await message.answer("❗ Не удалось замьютить. Проверьте права бота.")

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!размут","!unmute","!говори"))
async def unmute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.text.split(maxsplit=1)[-1].strip() if len(message.text.split())>1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, target)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return await message.answer("❌ Цель не найдена.")
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=ChatPermissions(can_send_messages=True))
        await message.answer(f"🔊 {target_name} размьючен.")
    except: pass

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!варн","!warn","!пред","!предупреждение"))
async def warn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if duration is None: return await message.answer("⚠️ Укажите срок. Пример: !варн 1ч @user")
    if not target_id: return await message.answer("❌ Укажите цель!")
    if await is_admin(message.chat.id, target_id): return await message.answer("❌ Нельзя выдать варн администратору.")
    now = int(time.time())
    expires = now + duration
    await db("INSERT INTO warns (user_id, chat_id, issued_at, expires_at) VALUES (?,?,?,?)", (target_id, message.chat.id, now, expires))
    max_warns, ban_duration, _ = await get_warn_settings(message.chat.id)
    active = await get_active_warns(target_id, message.chat.id)
    await message.answer(f"⚜️ {target_name} получил предупреждение ({active}/{max_warns})")
    if active >= max_warns:
        until = now + ban_duration if ban_duration else 0
        reason = f"Лимит предупреждений ({max_warns})"
        await db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,?,?)", (target_id, message.chat.id, reason, until))
        try:
            await bot.ban_chat_member(message.chat.id, target_id, until_date=None if until==0 else datetime.fromtimestamp(until, tz=timezone.utc))
            await message.answer(f"🚫 {target_name} забанен по лимиту варнов.")
        except: pass

@dp.message(F.text.lower().startswith("!варны лимит"))
async def set_warn_limit(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    nums = re.findall(r'\d+', message.text)
    if not nums: return
    limit = int(nums[0])
    await db("UPDATE warn_settings SET max_warns=? WHERE chat_id=?", (limit, message.chat.id))
    await message.answer(f"⚜️ Лимит варнов изменен на: {limit}")

@dp.message(F.text.lower().startswith("!варны чс"))
async def set_warn_ban_duration(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4: return await message.answer("Использование: !варны чс <срок>")
    dur = await parse_duration(parts[3])
    await db("UPDATE warn_settings SET ban_duration=? WHERE chat_id=?", (dur, message.chat.id))
    await message.answer(f"⚜️ Бан при лимите: {'навсегда' if dur==0 else f'{dur//3600}ч'}")

@dp.message(F.text.lower().startswith("!варны период"))
async def set_warn_duration(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4: return await message.answer("Использование: !варны период <срок>")
    dur = await parse_duration(parts[3])
    await db("UPDATE warn_settings SET warn_duration=? WHERE chat_id=?", (dur, message.chat.id))
    await message.answer(f"⚜️ Срок хранения варна: {dur//3600}ч")

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
    target_str = message.text[7:].strip()
    target_id, target_name = await resolve_target_from_text(message.chat.id, target_str)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return await message.answer("Пользователь не найден.")
    active = await get_active_warns(target_id, message.chat.id)
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
    if not target_id: return await message.answer("Пользователь не найден.")
    now = int(time.time())
    if num:
        rows = await db("SELECT id FROM warns WHERE user_id=? AND chat_id=? AND expires_at>? ORDER BY issued_at ASC LIMIT ?", (target_id, message.chat.id, now, num), fetch=True)
        for r in rows: await db("DELETE FROM warns WHERE id=?", (r[0],))
        await message.answer(f"⚜️ Снято {len(rows)} варнов с {target_name}")
    else:
        await db("DELETE FROM warns WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
        await message.answer(f"⚜️ Все варны сняты с {target_name}")

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!бан","!ban","!permban","!чс"))
async def ban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration, target_id, target_name = await parse_moderation_args(message)
    if not target_id: return await message.answer("❌ Укажите цель!")
    if await is_admin(message.chat.id, target_id): return await message.answer("❌ Нельзя забанить администратора.")
    clean_args = re.sub(r'(@\w+|\d+\s*(м|мин|ч|час|д|день)\b)', '', message.text.split(maxsplit=1)[-1]).strip()
    reason = clean_args or ""
    now = int(time.time())
    banned_until = now + duration if duration else 0
    await db("INSERT OR REPLACE INTO bans (user_id, chat_id, reason, banned_until) VALUES (?,?,?,?)", (target_id, message.chat.id, reason, banned_until))
    try:
        await bot.ban_chat_member(message.chat.id, target_id, until_date=None if not duration else datetime.fromtimestamp(banned_until, tz=timezone.utc))
        msg = f"🚫 {target_name} забанен"
        if duration: msg += f" на {duration//3600}ч"
        if reason: msg += f"\nПричина: {reason}"
        await message.answer(msg)
    except:
        await message.answer("❗ Не удалось забанить.")

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!разбан","!unban"))
async def unban_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.text.split(maxsplit=1)[-1].strip() if len(message.text.split())>1 else ""
    target_id, target_name = await resolve_target_from_text(message.chat.id, target)
    if not target_id: target_id, target_name = await resolve_target_from_reply(message)
    if not target_id: return
    await db("DELETE FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id))
    try:
        await bot.unban_chat_member(message.chat.id, target_id)
        await message.answer(f"✅ {target_name} разбанен.")
    except: pass

@dp.message(F.text.lower().startswith("!причина"))
async def reason_cmd(message: types.Message):
    target_id, target_name = await resolve_target_from_text(message.chat.id, message.text[9:].strip())
    if not target_id: target_id, _ = await resolve_target_from_reply(message)
    if not target_id: return
    r = await db("SELECT reason FROM bans WHERE user_id=? AND chat_id=?", (target_id, message.chat.id), fetch=True)
    if r:
        await message.answer(f"Причина: {r[0][0] if r[0][0] else 'не указана'}")
    else:
        await message.answer("Пользователь не забанен или причина отсутствует.")

@dp.message(lambda msg: msg.text and msg.text.lower().split()[0] in ("!кик","!kick"))
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
        await message.answer(f"👢 {target_name} кикнут.")
    except: pass

@dp.message(F.text.lower().startswith("!амнистия"))
async def amnesty_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    rows = await db("SELECT user_id FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    for (uid,) in rows:
        try: await bot.unban_chat_member(message.chat.id, uid)
        except: pass
    await db("DELETE FROM bans WHERE chat_id=?", (message.chat.id,))
    await message.answer("🔓 Амнистия: все баны сняты.")

@dp.message(F.text.lower().startswith("!банлист"))
async def banlist_cmd(message: types.Message):
    rows = await db("SELECT user_id, reason, banned_until FROM bans WHERE chat_id=?", (message.chat.id,), fetch=True)
    if not rows: return await message.answer("📭 Нет забаненных участников.")
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
        await bot.promote_chat_member(message.chat.id, target_id, can_manage_chat=True, can_delete_messages=True, can_restrict_members=True)
    except: pass

@dp.message(F.text.lower().startswith("-админ"))
async def admin_demote(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target_id, _ = await resolve_target_from_text(message.chat.id, message.text[6:].strip())
    if not target_id: return
    try:
        await bot.promote_chat_member(message.chat.id, target_id, can_manage_chat=False)
    except: pass

@dp.message(F.text.lower().startswith("!запретслово"))
async def add_forbidden_word(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await message.answer("Используйте: !запретслово <слово>")
    word = parts[1].strip().lower()
    if not word: return
    try:
        await db("INSERT OR IGNORE INTO forbidden_words (chat_id, word) VALUES (?,?)", (message.chat.id, word))
        await message.answer(f"🔞 Слово '{word}' успешно добавлено в фильтр.")
    except: pass

@dp.message(F.text.lower().startswith("!разрешслово"))
async def del_forbidden_word(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await message.answer("Используйте: !разрешслово <слово>")
    word = parts[1].strip().lower()
    await db("DELETE FROM forbidden_words WHERE chat_id=? AND word=?", (message.chat.id, word))
    await message.answer(f"🔓 Слово '{word}' удалено из чёрного списка.")

@dp.message(F.text.lower().startswith("!списокзапретов"))
async def list_forbidden_words(message: types.Message):
    chat_words = [row[0] for row in await db("SELECT word FROM forbidden_words WHERE chat_id=?", (message.chat.id,), fetch=True)]
    words = DEFAULT_FORBIDDEN + chat_words
    if not words: return await message.answer("Список пуст.")
    await message.answer("🔞 Избранные запрещённые слова:\n" + ", ".join(words[:50]) + ("..." if len(words)>50 else ""))

@dp.message(Command("adminhelp"))
async def admin_help(message: types.Message):
    await message.answer(
        "⚜️⚜️⚜️⚜️⚜️⚜️⚜️⚜️\n\n"
        "⚜️⚜️<b>Варн |период| |uz/отмет.|</b> ⚜️ выставляется одно предупреждение пользователю сроком, указанным в команде\n"
        "Синонимы: пред, предупреждение, /warn, !warn, !пред\n"
        "⚜️<b>Варны лимит |число|</b> ⚜️ устанавливает число предупреждений, по достижению которых пользователь исключается из беседы\n"
        "⚜️<b>Варны чс |период|</b> ⚜️ устанавливает срок бана по достижению лимита предупреждений\n"
        "⚜️<b>Варны |uz/отмет.|</b> ⚜️ выводится список текущих предупреждений пользователя\n"
        "⚜️<b>Варны период |период|</b> ⚜️ устанавливает срок хранения предупреждения\n"
        "⚜️<b>Снять варны |число| |uz/отмет.|</b> ⚜️ чтобы снять определенное число варнов пользователя\n"
        "⚜️<b>Снять варны |uz/отмет.|</b> ⚜️ чтобы снять все варны с пользователя\n"
        "⚜️<b>Варны помощь</b> ⚜️ выводит справку по командам модуля «Предупреждения»\n\n"
        "⚜️⚜️<b>Мут |срок| |uz/отмет.|</b> ⚜️ принудить пользователя к молчанию на определённый период\n"
        "⚜️<b>Снять мут |uz/отмет.|</b> ⚜️ снять мут\n"
        "⚜️⚜️<b>Бан |период| |uz/отмет.|</b> ⚜️ забанит пользователя на заданный период времени. По умолчанию — навсегда.\n"
        "⚜️<b>Разбан |uz/отмет.|</b> ⚜️ снимает бан с пользователя\n"
        "⚜️<b>Причина |uz/отмет.|</b>  ⚜️ выводит причину, указанную при бане пользователя\n"
        "⚜️<b>Кик |uz/отмет.|</b>  ⚜️ исключает пользователя из беседы без бана.\n\n"
        "🔞 <b>Фильтр слов и правила:</b>\n"
        "/setwelcome — Настройка приветствия\n"
        "!установитьправила — Настройка отправляемых правил",
        parse_mode="HTML"
    )

@dp.message(Command("setautoschedule"))
async def set_schedule(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    if message.chat.type not in ("group","supergroup"): return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: /setautoschedule <HH:MM закрытия> <HH:MM открытия>\n/setautoschedule off")
    if args[1].lower() == "off":
        await db("UPDATE schedules SET enabled=0 WHERE chat_id=?", (message.chat.id,))
        if message.chat.id in closed_chats:
            try:
                await bot.set_chat_permissions(message.chat.id,
                    ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_polls=True,
                                    can_send_other_messages=True, can_add_web_page_previews=True,
                                    can_change_info=True, can_invite_users=True, can_pin_messages=True))
                closed_chats.discard(message.chat.id)
            except: pass
        return await message.answer("✅ Автозакрытие отключено.")
    if len(args) < 3: return
    close_str, open_str = args[1], args[2]
    if not re.match(r'^\d{1,2}:\d{2}$', close_str) or not re.match(r'^\d{1,2}:\d{2}$', open_str):
        return await message.answer("❌ Неверный формат времени! Используйте HH:MM")
    await db("INSERT OR REPLACE INTO schedules (chat_id, close_time, open_time, enabled) VALUES (?,?,?,1)", (message.chat.id, close_str, open_str))
    await message.answer(f"✔ Автозакрытие настроено. Закрытие: {close_str}, открытие: {open_str}")

# --- ТОЧКА ВХОДА ---
async def main():
    await init_db()
    try: await bot.delete_webhook(drop_pending_updates=True)
    except: pass
    asyncio.create_task(schedule_task())
    me = await bot.get_me()
    print(f"✅ БОТ VOID HELPER ГОТОВ К РАБОТЕ: @{me.username}")
    try: await dp.start_polling(bot, timeout=60)
    except KeyboardInterrupt: print("Бот успешно отключен.")

if __name__ == "__main__":
    asyncio.run(main())
