import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8203364413:AAGOjBjFHfDtdm1w5vlmqHcxhD9HpR4_MNo"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# База данных жалоб в памяти
report_stats = {}

# --- ЖЁСТКОЕ ОБНОВЛЕНИЕ МЕНЮ КОМАНД ---
async def set_bot_commands(bot: Bot):
    # Новое чистое меню
    group_commands = [
        BotCommand(command="help", description="📋 Инструкция"),
        BotCommand(command="profile", description="👤 Профиль"),
        BotCommand(command="rep", description="⚠️ Пожаловаться (в ответе)"),
        BotCommand(command="replist", description="📊 Список жалоб (Админам)")
    ]
    # Намертво сносим старые команды (казино, игры и т.д.) из кэша Telegram
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    
    # Записываем новые команды во все типы чатов
    await bot.set_my_commands(commands=group_commands, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(commands=group_commands, scope=BotCommandScopeAllPrivateChats())
    print("[Система] Меню очищено. Новые команды загружены.")


# --- СУХОЙ И КОРОТКИЙ HELP ---
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📋 <b>Команды бота:</b>\n\n"
        "👤 /profile — Посмотреть свой профиль\n"
        "⚠️ /rep [причина] — Подать жалобу (ответом на сообщение нарушителя)\n"
        "📊 /replist — Посмотреть список жалоб (Только для админов)"
    )
    await message.reply(help_text)


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    await message.reply(f"👤 <b>Профиль:</b> {message.from_user.mention_html()}\n🆔 ID: <code>{message.from_user.id}</code>")


# --- СИСТЕМА РЕПОРТОВ (ЖАЛОБ) ---
@dp.message(Command("report", "rep"))
async def report_user(message: Message):
    if not message.reply_to_message:
        await message.reply("❌ Чтобы пожаловаться, ответь командой /rep на сообщение нарушителя!")
        return

    target_user = message.reply_to_message.from_user
    reporter = message.from_user
    
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
        f"📊 Жалоб на юзера: <code>{report_stats[target_user.id]}</code>\n"
        f"🔗 <a href='{msg_link}'>Перейти к сообщению</a>\n\n"
        f"📢 <b>Администрация, разберитесь!</b>"
    )
    
    await message.answer(report_text, disable_web_page_preview=True)
    
    try:
        await message.delete()
    except Exception:
        pass


# --- ТОП ЖАЛОБ (ТОЛЬКО ДЛЯ АДМИНОВ) ---
@dp.message(Command("replist"))
async def show_report_list(message: Message, bot: Bot):
    if message.chat.type in ["group", "supergroup"]:
        member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        
        if member.status not in ["administrator", "creator"]:
            await message.reply("🔒 <b>Доступ заблокирован:</b> Эта команда доступна только администраторам группы.")
            return

    if not report_stats:
        await message.reply("📭 Список жалоб пуст.")
        return

    sorted_reports = sorted(report_stats.items(), key=lambda x: x[1], reverse=True)
    
    text = "📊 <b>Топ нарушителей чата:</b>\n\n"
    for index, (user_id, count) in enumerate(sorted_reports[:10], start=1):
        text += f"<b>{index}.</b> ID: <code>{user_id}</code> — <b>{count}</b> репортов.\n"
        
    await message.reply(text)


# --- ЗАПУСК ---
async def main():
    await set_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
