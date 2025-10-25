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

bot = telebot.TeleBot(BOT_TOKEN)

with open("phrases.json", "r", encoding="utf-8") as f:
    PHRASES = json.load(f)

try:
    DEMILITARIZATION_DATE = date.fromisoformat(DEMILITARIZATION_DATE_STR)
except Exception as e:
    logging.error(f"Ошибка в дате: {e}")
    DEMILITARIZATION_DATE = None

def log_user_activity(user_id, username, command, message_text=""):
    try:
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": str(user_id),
            "username": username or "Unknown",
            "command": command,
            "message": message_text[:100] if message_text else ""
        }
        logs.append(log_entry)
        
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        
        logging.info(f"👤 Пользователь: {username or 'Unknown'} (ID: {user_id}) использовал команду: {command}")
    except Exception as e:
        logging.error(f"Ошибка логирования пользователя: {e}")

def choose_sticker_without_repeat(stickers, key):
    if not stickers:
        return None
    state = load_sticker_state()
    last = state.get(key)
    candidates = [s for s in stickers if s != last]
    if not candidates:
        candidates = stickers
    selected = choice(candidates)
    state[key] = selected
    save_sticker_state(state)
    return selected

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

def send_daily_update():
    recipients = {str(USER_ID), str(ADMIN_USER_ID)}

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

    # Отправляем сообщение
    for uid in recipients:
        try:
            # Отправляем статус дембеля
            bot.send_message(uid, msg, parse_mode="Markdown")

            markup = telebot.types.InlineKeyboardMarkup()
            item2 = telebot.types.InlineKeyboardButton("💖 Получить поддержку", callback_data="hug")
            markup.add(item2)
            # Отправляем стикер

            sticker_id = choose_sticker_without_repeat(STICKERS, "status")
            bot.send_sticker(uid, sticker_id, reply_markup=markup)
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {uid}: {e}")

def send_morning_greeting():
    recipients = {str(USER_ID), str(ADMIN_USER_ID)}
    if not recipients:
        logging.error("Ни USER_ID, ни ADMIN_USER_ID не заданы")
        return

    logging.info("🌅 Отправка утреннего приветствия")
    text = "Доброе утро! ☀️"
    markup = telebot.types.InlineKeyboardMarkup()
    item2 = telebot.types.InlineKeyboardButton("💖 Получить поддержку", callback_data="hug")
    markup.add(item2)

    for uid in recipients:
        try:
            bot.send_message(uid, text)
            sticker_id = choose_sticker_without_repeat(STICKERS, "morning")
            if sticker_id:
                bot.send_sticker(uid, sticker_id, reply_markup=markup)
        except Exception as e:
            logging.error(f"Не удалось отправить утреннее сообщение пользователю {uid}: {e}")

def send_night_greeting():
    recipients = {str(USER_ID), str(ADMIN_USER_ID)}
    if not recipients:
        logging.error("Ни USER_ID, ни ADMIN_USER_ID не заданы")
        return

    logging.info("🌙 Отправка ночного пожелания")
    text = "Сладких снов! 🌙"
    markup = telebot.types.InlineKeyboardMarkup()
    item2 = telebot.types.InlineKeyboardButton("💖 Получить поддержку", callback_data="hug")
    markup.add(item2)

    for uid in recipients:
        try:
            bot.send_message(uid, text)
            sticker_id = choose_sticker_without_repeat(STICKERS, "night")
            if sticker_id:
                bot.send_sticker(uid, sticker_id, reply_markup=markup)
        except Exception as e:
            logging.error(f"Не удалось отправить ночное сообщение пользователю {uid}: {e}")

# Inline кнопки под сообщениями
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup()
    item1 = telebot.types.InlineKeyboardButton("🗓 Статус дембеля", callback_data="status")
    markup.add(item1)
    bot.send_message(message.chat.id, "Привет! Я помогу отслеживать дни до дембеля.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "status")
def send_status(call):
    send_daily_update()
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "hug")
def send_hug(call):
    phrase = choice(PHRASES)
    bot.send_message(call.message.chat.id, f"🤗 {phrase}")
    bot.answer_callback_query(call.id)

scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_update, CronTrigger(hour=9, minute=0, timezone="Asia/Shanghai"))
scheduler.add_job(send_morning_greeting, CronTrigger(hour=7, minute=0, timezone="Asia/Shanghai"))
scheduler.add_job(send_night_greeting, CronTrigger(hour=23, minute=0, timezone="Asia/Shanghai"))
scheduler.start()

def run_bot_safe():
    while True:
        try:
            logging.info("Попытка подключения к Telegram API...")
            me = bot.get_me()
            logging.info(f"✅ Успешное подключение к Telegram API! Бот: @{me.username} (id={me.id})")
            bot.polling(none_stop=True, skip_pending=True, timeout=20)
            break
        except Exception as e:
            logging.error(f"Ошибка подключения: {e}")
            wait_time = 30
            logging.info(f"Переподключение через {wait_time} секунд...")
            time.sleep(wait_time)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Бот запущен. Подключение...")
    try:
        run_bot_safe()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Остановка бота...")
        scheduler.shutdown()
