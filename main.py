import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Включаем логирование, чтобы видеть работу бота в консоли
logging.basicConfig(level=logging.INFO)

# Твой рабочий токен бота
BOT_TOKEN = "8203364413:AAGOjBjFHfDtdm1w5vlmqHcxhD9HpR4_MNo"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Временная база данных для хранения количества репортов
report_stats = {}

# --- АВТОМАТИЧЕСКАЯ ОЧИСТКА И ОБНОВЛЕНИЕ МЕНЮ КОМАНД ---
async def set_bot_commands(bot: Bot):
    # Новый список команд без казино и игр
    group_commands = [
        BotCommand(command="help", description="📋 Все команды"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="rep", description="⚠️ Пожаловаться (в ответе на сообщение)"),
        BotCommand(command="replist", description="📊 Список жалоб чата"),
        BotCommand(command="moderation", description="⚙️ Автомодерация")
    ]
    
    # Жестко чистим старый кэш команд в Telegram (удаляет казино из меню)
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    
    # Устанавливаем новое чистое меню
    await bot.set_my_commands(commands=group_commands, scope=BotCommandScopeAllGroupChats())
    print("[Система] Меню команд успешно обновлено. Старые игры полностью удалены!")


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
    await message.reply(f"👤 <b>Профиль пользователя:</b> {message.from_user.mention_html()}\n🆔 ID: <code>{message.from_user.id}</code>")


@dp.message(Command("moderation"))
async def cmd_mod(message: Message):
    await message.reply("⚙️ Меню настроек автомодерации находится в разработке.")


# --- СИСТЕМА РЕПОРТОВ (ЖАЛОБ) ---

@dp.message(Command("report", "rep"))
async def report_user(message: Message):
    # Если команда отправлена не ответом на сообщение
    if not message.reply_to_message:
        await message.reply("❌ Чтобы пожаловаться на нарушителя, сделай <b>ответ (reply)</b> на его сообщение и напиши <code>/rep [причина]</code>")
        return

    target_user = message.reply_to_message.from_user  # Нарушитель
    reporter = message.from_user  # Тот, кто пожаловался
    
    # Если пытаются пожаловаться на самого себя (смайлик полностью убран)
    if target_user.id == reporter.id:
        await message.reply("На самого себя жаловаться нельзя.")
        return

    # Вытаскиваем причину жалобы
    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "Причина не указана"

    # Формируем ссылку на плохое сообщение
    chat_username = message.chat.username
    if chat_username:
        msg_link = f"https://t.me/{chat_username}/{message.reply_to_message.message_id}"
    else:
        msg_link = "Ссылка недоступна (приватный чат)"

    # Записываем жалобу в статистику сессии
    report_stats[target_user.id] = report_stats.get(target_user.id, 0) + 1

    # Сообщение для администрации в чат
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
    
    # Удаляем само сообщение с текстом /rep, чтобы не засорять чат
    try:
        await message.delete()
    except Exception:
        pass


@dp.message(Command("replist"))
async def show_report_list(message: Message):
    if not report_stats:
        await message.reply("📭 Список жалоб пуст. В чате пока идеальный порядок!")
        return

    # Сортируем нарушителей по убыванию жалоб
    sorted_reports = sorted(report_stats.items(), key=lambda x: x[1], reverse=True)
    
    text = "📊 <b>Топ пользователей по количеству жалоб:</b>\n\n"
    for index, (user_id, count) in enumerate(sorted_reports[:10], start=1):
        text += f"<b>{index}.</b> Юзер ID: <code>{user_id}</code> — <b>{count}</b> репортов.\n"
        
    await message.reply(text)


# --- ЗАПУСК БОТА ---
async def main():
    # Запускаем автоматическое обновление меню команд в Телеграме
    await set_bot_commands(bot)
    # Включаем опрос сервера Telegram
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
