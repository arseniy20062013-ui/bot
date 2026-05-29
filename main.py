import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Логирование для отслеживания работы
logging.basicConfig(level=logging.INFO)

# Твой токен
BOT_TOKEN = "8203364413:AAGOjBjFHfDtdm1w5vlmqHcxhD9HpR4_MNo"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# База данных жалоб в памяти
report_stats = {}

# --- СНОСИМ СТАРЫЕ КОМАНДЫ И СТАВИМ НОВЫЕ ---
async def set_bot_commands(bot: Bot):
    group_commands = [
        BotCommand(command="help", description="📋 Инструкция по командам"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="rep", description="⚠️ Подать жалобу (в ответе на сообщение)"),
        BotCommand(command="replist", description="📊 Список жалоб (Только для Админов)")
    ]
    # Очистка кэша старых команд
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    # Запись новых команд
    await bot.set_my_commands(commands=group_commands, scope=BotCommandScopeAllGroupChats())
    print("[Система] Меню команд успешно обновлено!")


# --- ЧИСТЫЙ И ПОДРОБНЫЙ HELP ---
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>РУКОВОДСТВО ПО КОМАНДАМ БОТА</b>\n\n"
        "📌 <b>ОБЩИЕ КОМАНДЫ:</b>\n"
        "👉 <code>/help</code> — Вызов этого меню.\n"
        "👉 <code>/profile</code> — Посмотреть свой профиль и узнать свой Telegram ID.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <b>СИСТЕМА ЖАЛОБ (РЕПОРТОВ):</b>\n"
        "👉 <code>/rep [причина]</code> или <code>/report [причина]</code>\n"
        "• <b>Как использовать:</b> Ответь командой <code>/rep</code> на сообщение нарушителя (флуд, спам, оскорбления) и укажи причину.\n"
        "• <b>Пример:</b> <i>/rep спамит ссылками</i>\n"
        "• <i>Бот автоматически удалит твою команду из чата, чтобы не засорять переписку, и призовет администраторов группы.</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>ДЛЯ АДМИНИСТРАЦИИ ЧАТА:</b>\n"
        "👉 <code>/replist</code> — Список пользователей с наибольшим количеством жалоб.\n"
        "• 🔒 <i>Команда доступна только администраторам группы.</i>"
    )
    await message.reply(help_text)


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    await message.reply(f"👤 <b>Профиль пользователя:</b> {message.from_user.mention_html()}\n🆔 ID: <code>{message.from_user.id}</code>")


# --- СИСТЕМА РЕПОРТОВ (ЖАЛОБ) ---
@dp.message(Command("report", "rep"))
async def report_user(message: Message):
    if not message.reply_to_message:
        await message.reply("❌ Чтобы пожаловаться на нарушителя, сделай <b>ответ (reply)</b> на его сообщение и напиши <code>/rep [причина]</code>")
        return

    target_user = message.reply_to_message.from_user  # Нарушитель
    reporter = message.from_user  # Тот, кто пожаловался
    
    if target_user.id == reporter.id:
        await message.reply("На самого себя жаловаться нельзя.")
        return

    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "Причина не указана"

    chat_username = message.chat.username
    msg_link = f"https://t.me/{chat_username}/{message.reply_to_message.message_id}" if chat_username else "Приватный чат"

    # Запись в статистику
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


# --- ПРОСМОТР ТОПА ЖАЛОБ (ТОЛЬКО ДЛЯ АДМИНОВ) ---
@dp.message(Command("replist"))
async def show_report_list(message: Message, bot: Bot):
    # Проверяем права в группах
    if message.chat.type in ["group", "supergroup"]:
        member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        
        # Если юзер не админ и не создатель чата — от ворот поворот
        if member.status not in ["administrator", "creator"]:
            await message.reply("🔒 <b>Доступ заблокирован:</b> Эта команда доступна только администраторам группы.")
            return

    if not report_stats:
        await message.reply("📭 Список жалоб пуст. В чате пока идеальный порядок!")
        return

    sorted_reports = sorted(report_stats.items(), key=lambda x: x[1], reverse=True)
    
    text = "📊 <b>Админ-панель: Топ нарушителей по жалобам:</b>\n\n"
    for index, (user_id, count) in enumerate(sorted_reports[:10], start=1):
        text += f"<b>{index}.</b> Юзер ID: <code>{user_id}</code> — <b>{count}</b> репортов.\n"
        
    await message.reply(text)


# --- ЗАПУСК ---
async def main():
    await set_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
