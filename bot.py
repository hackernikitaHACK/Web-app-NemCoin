from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests

# Токен бота
TELEGRAM_TOKEN = 'ВАШ_ТОКЕН_ТЕЛЕГРАМ_БОТА'

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Добро пожаловать! Используйте команду /earn, чтобы заработать токены.")

def earn(update: Update, context: CallbackContext) -> None:
    username = update.message.from_user.username
    response = requests.post('http://127.0.0.1:5000/earn_tokens', data={'username': username})
    update.message.reply_text(response.text)

def main() -> None:
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("earn", earn))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
