import os
import json
import telebot
import logging
import time
from datetime import date, datetime
from random import choice
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()
STICKERS = (
# вставить айди стикеров
)
BOT_TOKEN = os.getenv("BOT_TOKEN")
USER_ID = os.getenv("USER_ID")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
DEMILITARIZATION_DATE_STR = os.getenv("DEMILITARIZATION_DATE")

STATE_FILE = "sticker_state.json"
LOG_FILE = "user_logs.json"

def log_user_activity(user_id, username, command, message_text=""):
    """Логирование активности пользователей"""
    try:
        # Загружаем существующие логи
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        
        # Добавляем новую запись
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": str(user_id),
            "username": username or "Unknown",
            "command": command,
            "message": message_text[:100] if message_text else ""  # Ограничиваем длину
        }
        logs.append(log_entry)
        
        # Сохраняем обратно (оставляем только последние 1000 записей)
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        
        # Выводим в консоль
        logging.info(f"👤 Пользователь: {username or 'Unknown'} (ID: {user_id}) использовал команду: {command}")
        
    except Exception as e:
        logging.error(f"Ошибка логирования пользователя: {e}")

def load_sticker_state():
    try:
        if not os.path.exists(STATE_FILE):
            return {}
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        logging.error(f"Не удалось прочитать состояние стикеров: {e}")
        return {}

def save_sticker_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Не удалось сохранить состояние стикеров: {e}")

def choose_sticker_without_repeat(stickers, key):
    if not stickers:
        return None
    state = load_sticker_state()
    last = state.get(key)
    # Исключаем вчерашний, если есть альтернатива
    candidates = [s for s in stickers if s != last]
    if not candidates:
        candidates = stickers
    selected = choice(candidates)
    state[key] = selected
    save_sticker_state(state)
    return selected

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не указан в .env")

bot = telebot.TeleBot(BOT_TOKEN)

with open("phrases.json", "r", encoding="utf-8") as f:
    PHRASES = json.load(f)

# Парсим дату
try:
    DEMILITARIZATION_DATE = date.fromisoformat(DEMILITARIZATION_DATE_STR)
except Exception as e:
    logging.error(f"Ошибка в дате: {e}")
    DEMILITARIZATION_DATE = None

# Проверка на админа по user_id
def is_admin(user_id):
    return str(user_id) == str(ADMIN_USER_ID)

# Команда /start — покажет user_id
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Логируем активность
    log_user_activity(
        message.from_user.id, 
        message.from_user.username, 
        "/start", 
        message.text
    )
    
    bot.reply_to(
        message,
        (
            "Привет! 💕 Я буду поддерживать тебя каждый день.\n"
            "Команды:\n"
            "/status — сколько дней до дембеля\n"
            "/hug — получить поддержку\n"
        ),
        parse_mode="Markdown"
    )

# /status — для всех
@bot.message_handler(commands=['status'])
def send_status(message):
    # Логируем активность
    log_user_activity(
        message.from_user.id, 
        message.from_user.username, 
        "/status", 
        message.text
    )
    send_daily_update()

# /hug — для всех
@bot.message_handler(commands=['hug'])
def send_hug(message):
    # Логируем активность
    log_user_activity(
        message.from_user.id, 
        message.from_user.username, 
        "/hug", 
        message.text
    )
    
    phrase = choice(PHRASES)
    bot.send_message(message.chat.id, f"🤗 {phrase}")

# /send — только для админа
@bot.message_handler(commands=['send'])
def manual_send(message):
    if is_admin(message.from_user.id):
        send_daily_update()
        bot.reply_to(message, "✅ Сообщение отправлено вручную!")
    else:
        bot.reply_to(message, "🚫 Только админ может использовать эту команду.")

# Основная функция отправки — только указанному пользователю
def send_daily_update():
    recipients = set()  # используем set, чтобы избежать дублей, если ID совпадают

    if USER_ID:
        recipients.add(str(USER_ID))
    if ADMIN_USER_ID:
        recipients.add(str(ADMIN_USER_ID))

    if not recipients:
        logging.error("Ни USER_ID, ни ADMIN_USER_ID не заданы")
        return

    if not DEMILITARIZATION_DATE:
        error_msg = "❌ Ошибка: не указана дата дембеля."
        for uid in recipients:
            try:
                bot.send_message(uid, error_msg)
            except Exception as e:
                logging.error(f"Не удалось отправить админу/получателю {uid}: {e}")
        return

    today = date.today()
    days_left = (DEMILITARIZATION_DATE - today).days

    if days_left < 0:
        msg = "🎉 УРА! Твой парень уже дембель! Поздравляю! 🥳"
    elif days_left == 0:
        msg = "Сегодня день дембеля! 🎊 Он свободен! Беги встречать! 💃"
    else:
        phrase = choice(PHRASES)
        msg = f"До дембеля твоего парня осталось: *{days_left}* дней 💖\n\n{phrase}"

    # Отправляем каждому получателю
    for uid in recipients:
        try:
            bot.send_message(uid, msg, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {uid}: {e}")
    if not USER_ID:
        logging.error("USER_ID не задан")
        return

    if not DEMILITARIZATION_DATE:
        bot.send_message(USER_ID, "❌ Ошибка: не указана дата дембеля.")
        return

    today = date.today()
    days_left = (DEMILITARIZATION_DATE - today).days

    if days_left < 0:
        msg = "🎉 УРА! Твой парень уже дембель! Поздравляю! 🥳"
    elif days_left == 0:
        msg = "Сегодня день дембеля! 🎊 Он свободен! Беги встречать! 💃"
    else:
        phrase = choice(PHRASES)
        msg = f"До дембеля твоего парня осталось: *{days_left}* дней 💖\n\n{phrase}"

    try:
        bot.send_message(USER_ID, msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Не удалось отправить сообщение пользователю {USER_ID}: {e}")

# Утреннее приветствие в 07:00
def send_morning_greeting():
    recipients = set()

    if USER_ID:
        recipients.add(str(USER_ID))
    if ADMIN_USER_ID:
        recipients.add(str(ADMIN_USER_ID))

    if not recipients:
        logging.error("Ни USER_ID, ни ADMIN_USER_ID не заданы")
        return

    # Логируем автоматическую отправку
    logging.info("🌅 Отправка утреннего приветствия")
    
    text = "Доброе утро! ☀️"
    for uid in recipients:
        try:
            bot.send_message(uid, text)
            sticker_id = choose_sticker_without_repeat(STICKERS, "morning")
            if sticker_id:
                bot.send_sticker(uid, sticker_id)
        except Exception as e:
            logging.error(f"Не удалось отправить утреннее сообщение пользователю {uid}: {e}")

# Ночное пожелание в 23:00
def send_night_greeting():
    recipients = set()

    if USER_ID:
        recipients.add(str(USER_ID))
    if ADMIN_USER_ID:
        recipients.add(str(ADMIN_USER_ID))

    if not recipients:
        logging.error("Ни USER_ID, ни ADMIN_USER_ID не заданы")
        return

    # Логируем автоматическую отправку
    logging.info("🌙 Отправка ночного пожелания")
    
    text = "Сладких снов! 🌙"
    for uid in recipients:
        try:
            bot.send_message(uid, text)
            sticker_id = choose_sticker_without_repeat(STICKERS, "night")
            if sticker_id:
                bot.send_sticker(uid, sticker_id)
        except Exception as e:
            logging.error(f"Не удалось отправить ночное сообщение пользователю {uid}: {e}")

# Планировщик: ежедневно в 09:00 по UTC+8
scheduler = BackgroundScheduler()
scheduler.add_job(
    send_daily_update,
    CronTrigger(hour=9, minute=0, timezone="Asia/Shanghai")
)
# Новые задания: 07:00 — доброе утро; 23:00 — сладких снов
scheduler.add_job(
    send_morning_greeting,
    CronTrigger(hour=7, minute=00, timezone="Asia/Shanghai")
)
scheduler.add_job(
    send_night_greeting,
    CronTrigger(hour=23, minute=2, timezone="Asia/Shanghai")
)
scheduler.start()

# Запуск
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Бот запущен. Отправка в 09:00 (UTC+8) пользователю с USER_ID.")
    
    # Функция для безопасного запуска бота с переподключением
    def run_bot_safe():
        max_retries = 100
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logging.info(f"Попытка подключения {retry_count + 1}/{max_retries}")
                # Проверяем доступность API до запуска long-polling
                me = bot.get_me()
                logging.info(f"✅ Успешное подключение к Telegram API! Бот: @{me.username} (id={me.id})")
                bot.polling(none_stop=True, skip_pending=True, timeout=20)
                break
            except Exception as e:
                retry_count += 1
                logging.error(f"Ошибка подключения (попытка {retry_count}): {e}")
                
                if retry_count < max_retries:
                    # Экспоненциальная задержка с верхней границей
                    wait_time = min(30, 5 * retry_count)
                    logging.info(f"Переподключение через {wait_time} секунд...")
                    time.sleep(wait_time)
                else:
                    logging.error("Превышено максимальное количество попыток подключения")
                    break
    
    try:
        run_bot_safe()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Остановка бота...")

        scheduler.shutdown()
