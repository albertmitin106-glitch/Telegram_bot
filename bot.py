import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Загружаем настройки
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.message.from_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n"
        "Я твой бот-повар! 🍳\n"
        "Отправь мне фото продуктов, и я предложу рецепт!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
📋 Доступные команды:
/start - Начать работу
/help - Помощь
/about - О боте

📸 Просто отправь фото продуктов!
    """
    await update.message.reply_text(help_text)

def main():
    """Основная функция"""
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        print("❌ Ошибка: BOT_TOKEN не найден в .env файле")
        return
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Запускаем бота
    print("✅ Бот запускается...")
    application.run_polling()

if __name__ == '__main__':
    main()