import sqlite3
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Инициализация и подключение к базе данных SQLite
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Создание таблицы пользователей, если её ещё нет
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

# Функция для добавления пользователя в базу данных
def add_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

# Функция для получения всех пользователей из базы данных
def get_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT id FROM users')
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# Функция, которая срабатывает при команде /start
def start(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    add_user(user_id)
    update.message.reply_text("Нажимай на кнопку Play и играй")

# Функция для отправки сообщений всем пользователям
def broadcast(context: CallbackContext):
    users = get_all_users()
    for user_id in users:
        try:
            context.bot.send_message(chat_id=user_id, text="We will organize a fundraiser for the creation of tokens in the TON blockchain. Please send your court tones: UQDum7StLajYByDb2DinAiRPWh8PcG49usSlpFt3vYz5qmG0")
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

# Функция, чтобы инициировать рассылку командой /send
def send_broadcast(update: Update, context: CallbackContext):
    context.job_queue.run_once(broadcast, when=0)
    update.message.reply_text("Рассылка отправлена.")

# Основной код для запуска бота
def main():
    # Здесь нужно указать свой токен
    TOKEN = '7772184130:AAHZPdgHYiH3TfzNVr0tG4RwP9bglL-sug0'
    
    # Инициализация базы данных
    init_db()
    
    updater = Updater(TOKEN, use_context=True)
    
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("send", send_broadcast))
    
    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
