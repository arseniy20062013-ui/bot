import asyncio
import logging
import aiosqlite
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Твой рабочий токен
BOT_TOKEN = "8203364413:AAGOjBjFHfDtdm1w5vlmqHcxhD9HpR4_MNo"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Хранилище репортов в памяти
report_stats = {}

# --- УДАЛЕНИЕ КАЗИНО И ОБНОВЛЕНИЕ МЕНЮ ---
async def set_bot_commands(bot: Bot):
    group_commands = [
        BotCommand(command="help", description="📋 Все команды"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="rep", description="⚠️ Пожаловаться (ответом на сообщение)"),
        BotCommand(command="replist", description="📊 Список жалоб чата"),
        BotCommand(command="moderation", description="⚙️ Автомодерация")
    ]
    
    # Сносим старый кэш с казино
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    
    # Ставим новые команды
    await bot.set_my_commands(commands=group_commands, scope=BotCommandScopeAllGroupChats())
    print("[Система] Меню очищено от казино. Новые команды успешно загружены!")

# --- БАЗОВЫЕ КОМАНДЫ ---
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "<b>📌 Список доступных команд:</b>\n\n"
        "👤 /profile — Посмотреть свой профиль\n"
        "⚠️ /rep [причина] — Подать жалобу на игрока (ответом на его сообщение)\n"
        "📊 /replist — Посмотреть статистику жалоб чата\n"
        "⚙️ /moderation — Настройки автомодерации"
    )
    await message.reply(help_text)

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    await message.reply(f"👤 <b>Профиль:</b> {message.from_user.mention_html()}\n🆔 ID: <code>{message.from_user.id}</code>")

@dp.message(Command("moderation"))
async def cmd_mod(message: Message):
    await message.reply("⚙️ Настройки автомодерации находятся в разработке.")

# --- СИСТЕМА РЕПОРТОВ (ЖАЛОБ) ---
@dp.message(Command("report", "rep"))
async def report_user(message: Message):
    if not message.reply_to_message:
        await message.reply("❌ Чтобы пожаловаться, сделай ответ (reply) на сообщение нарушителя!")
        return

    target_user = message.reply_to_message.from_user
    reporter = message.from_user
    
    # Смайлик убран по твоему требованию
    if target_user.id == reporter.id:
        await message.reply("На самого себя жаловаться нельзя.")
        return

    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "Причина не указана"

    chat_username = message.chat.username
    msg_link = f"https://t.me/{chat_username}/{message.reply_to_message.message_id}" if chat_username else "Приватный чат"

    report_stats[target_user.id] = report_stats.get(target_user.id, 0) + 1

    report_text = (
        f"⚠️ <b>[🚨 ПОСТУПИЛ РЕПОРТ!]</b>\n\n"
        f"👤 <b>Нарушитель:</b> {target_user.mention_html()} (ID: <code>{target_user.id}</code>)\n"
        f"✍️ <b>Кто отправил:</b> {reporter.mention_html()}\n"
        f"📝 <b>Причина:</b> {reason}\n"
        f"📊 Жалоб на этого юзера: <code>{report_stats[target_user.id]}</code>\n"
        f"🔗 <a href='{msg_link}'>Перейти к сообщению нарушителя</a>\n\n"
        f"📢 <b>Администраторы, разберитесь с нарушением!</b>"
    )
    
    await message.answer(report_text, disable_web_page_preview=True)
    
    try:
        await message.delete()
    except Exception:
        pass

@dp.message(Command("replist"))
async def show_report_list(message: Message):
    if not report_stats:
        await message.reply("📭 Список жалоб пуст. В чате пока идеальный порядок!")
        return

    sorted_reports = sorted(report_stats.items(), key=lambda x: x[1], reverse=True)
    
    text = "📊 <b>Топ пользователей по количеству жалоб:</b>\n\n"
    for index, (user_id, count) in enumerate(sorted_reports[:10], start=1):
        text += f"<b>{index}.</b> Юзер ID: <code>{user_id}</code> — <b>{count}</b> репортов.\n"
        
    await message.reply(text)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (чтобы aiosqlite не простаивал) ---
async def init_db():
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, rep_count INTEGER DEFAULT 0)")
        await db.commit()

# --- ЗАПУСК БОТА ---
async def main():
    await init_db() # Инициализируем БД
    await set_bot_commands(bot) # Чистим меню от казино
    await dp.start_polling(bot) # Запуск опроса

if __name__ == "__main__":
    asyncio.run(main())
