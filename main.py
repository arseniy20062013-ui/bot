import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)

# Твой рабочий токен
BOT_TOKEN = "8203364413:AAGOjBjFHfDtdm1w5vlmqHcxhD9HpR4_MNo"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Хранилища в памяти
report_stats = {}

# --- СПИСОК ЗАПРЕЩЕННЫХ СЛОВ (АВТОМОДЕРАЦИЯ 18+) ---
# Допиши сюда любые маты/слова, которые бот должен тереть
BAD_WORDS = ["хуй", "пизда", "еблан", "хуууй", "хууй", "пидор", "сука"]

# --- НАСТРОЙКА РАСПИСАНИЯ ЗАКРЫТИЯ ЧАТА ---
# Время в формате HH:MM когда чат автоматически закрывается и открывается
CLOSE_TIME = "23:00"
OPEN_TIME = "07:00"

# --- ОБНОВЛЕНИЕ МЕНЮ (БЕЗ КАЗИНО) ---
async def set_bot_commands(bot: Bot):
    group_commands = [
        BotCommand(command="help", description="📋 Подробное меню команд"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="rep", description="⚠️ Подать жалобу (в ответе)"),
        BotCommand(command="replist", description="📊 Список жалоб (Админам)"),
        BotCommand(command="check_schedule", description="🔎 Проверить расписание чата")
    ]
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands=group_commands, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(commands=group_commands, scope=BotCommandScopeAllPrivateChats())
    print("[Система] Меню команд обновлено. Лишнее удалено.")


# --- ПОДРОБНЫЙ И ПОНЯТНЫЙ HELP ---
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📋 <b>ПОДРОБНОЕ РУКОВОДСТВО ПО БОТУ</b>\n\n"
        "👤 <b>Профиль и инфо:</b>\n"
        "• <code>/profile</code> — Показывает твой аккаунт и ID.\n\n"
        "⚠️ <b>Система репортов (жалоб):</b>\n"
        "• <code>/rep [причина]</code> — Подать жалобу на нарушителя. Её нужно писать <b>строго в ответе (reply)</b> на плохое сообщение.\n"
        "• Бот сам удалит твою команду и позовет админов.\n\n"
        "🔞 <b>Автомодерация:</b>\n"
        "• В чате включен фильтр мата и 18+ слов. Бот автоматически удаляет такие сообщения, чтобы группу не заблокировали.\n\n"
        "⏰ <b>Расписание чата:</b>\n"
        "• <code>/check_schedule</code> — Показывает время работы чата.\n"
        f"• Чат автоматически закрывается на ночь в <b>{CLOSE_TIME}</b> и открывается в <b>{OPEN_TIME}</b>.\n\n"
        "📊 <b>Для Администрации:</b>\n"
        "• <code>/replist</code> — Выводит топ игроков по количеству жалоб. Доступно только админам."
    )
    await message.reply(help_text)


# --- КОМАНДА PROFILE ---
@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    await message.reply(f"👤 <b>Профиль пользователя:</b> {message.from_user.mention_html()}\n🆔 ID: <code>{message.from_user.id}</code>")


# --- КОМАНДА ПРОВЕРКИ РАСПИСАНИЯ ---
@dp.message(Command("check_schedule"))
async def cmd_schedule(message: Message):
    await message.reply(
        f"🔎 <b>Расписание работы чата:</b>\n\n"
        f"🔓 Открытие чата: <code>{OPEN_TIME}</code>\n"
        f"🔒 Закрытие чата: <code>{CLOSE_TIME}</code>\n\n"
        f"<i>В нерабочее время бот будет автоматически удалять сообщения от обычных пользователей.</i>"
    )


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
    except:
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


# --- ФИЛЬТР МАТА И АВТОМОВЕРАЦИЯ ПО ВРЕМЕНИ ---
@dp.message(F.text)
async def автомодерация(message: Message, bot: Bot):
    # 1. Проверяем расписание (закрыт ли чат)
    now = datetime.now().strftime("%H:%M")
    if now >= CLOSE_TIME or now < OPEN_TIME:
        # Проверяем, админ ли пишет. Если обычный юзер — сносим сообщение
        if message.chat.type in ["group", "supergroup"]:
            member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
            if member.status not in ["administrator", "creator"]:
                try:
                    await message.delete()
                except:
                    pass
                return

    # 2. Проверяем 18+ слова
    text_lower = message.text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            try:
                await message.delete()
                # Опционально: бот может написать предупреждение
                alert = await message.answer(f"⚠️ {message.from_user.first_name}, твоё сообщение удалено за мат.")
                await asyncio.sleep(5)
                await alert.delete() # Удаляем пред через 5 сек, чтоб не засирать чат
            except:
                pass
            break


# --- ЗАПУСК ---
async def main():
    await set_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
