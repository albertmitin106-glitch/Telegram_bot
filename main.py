import logging
import os
import random
import sqlite3
from datetime import datetime
import aiohttp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ============ НАСТРОЙКИ ============
TOKEN = "8356413290:AAGvwTj0fK8_QxwwrPHhB7Kdw6UlblbmECE"  # Замените на токен вашего Telegram бота
DB_PATH = "fridge.db"

AI_API_URL = os.getenv("AI_API_URL", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateText")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gemini-2.5-flash")

# ============ ЛОГИ ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ БАЗА ДАННЫХ ============
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")
conn.commit()

# ============ ЛОКАЛЬНЫЕ РЕЦЕПТЫ ============
RECIPES = [
    {"title": "Паста с томатами", "ingredients": ["спагетти", "помидоры", "чеснок", "оливковое масло", "соль"], "steps": ["Отварить пасту до аль денте", "Обжарить чеснок и помидоры на оливковом масле", "Смешать с пастой и посолить"]},
    {"title": "Омлет с сыром", "ingredients": ["яйца", "сыр", "сливочное масло", "соль"], "steps": ["Взбить яйца с щепоткой соли", "Растопить масло на сковороде", "Вылить яйца, добавить сыр и довести до готовности"]},
    {"title": "Салат с огурцом", "ingredients": ["огурец", "укроп", "сметана", "соль"], "steps": ["Нарезать огурец", "Добавить укроп и сметану", "Посолить и перемешать"]},
]

def format_recipe_block(title, ingredients, steps, time=None, kcal=None):
    lines = [f"🍽 {title}", "", "Ингредиенты:"]
    lines += [f"• {i}" for i in ingredients]
    lines += ["", "Шаги:"]
    lines += [f"{idx+1}. {step}" for idx, step in enumerate(steps)]
    if time:
        lines += ["", f"Время: {time}"]
    if kcal:
        lines += [f"Калорийность: {kcal}"]
    return "\n".join(lines)

def format_recipe_local(r):
    return format_recipe_block(r["title"], r["ingredients"], r["steps"])

def is_valid_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except:
        return False

def build_recipe_prompt(ingredients=None):
    ing = ", ".join(ingredients) if ingredients else "любые простые продукты из холодильника"
    return (f"Сгенерируй 1 реалистичный рецепт на русском языке из: {ing}.\n"
            "Формат строго:\n"
            "Название:\n"
            "Ингредиенты:\n"
            "Шаги:\n"
            "Время:\n"
            "Калорийность:\n"
            "Пиши кратко и по делу.")

async def ask_ai_for_recipe(ingredients=None):
    if not AI_API_KEY:
        r = random.choice(RECIPES)
        return format_recipe_local(r)

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": "Ты шеф-повар и диетолог. Пиши коротко и структурировано."},
            {"role": "user", "content": build_recipe_prompt(ingredients)}
        ],
        "temperature": 0.9,
        "max_tokens": 600,
    }
    logger.info(f"Запрос AI: {payload}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(AI_API_URL, json=payload, headers=headers, timeout=60) as resp:
                text_resp = await resp.text()
                logger.info(f"Ответ AI статус: {resp.status}")
                logger.info(f"Ответ AI тело: {text_resp}")
                if resp.status != 200:
                    r = random.choice(RECIPES)
                    return format_recipe_local(r)
                data = await resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                if not content:
                    r = random.choice(RECIPES)
                    return format_recipe_local(r)
                return content
    except Exception as e:
        logger.exception(f"Ошибка при запросе AI: {e}")
        r = random.choice(RECIPES)
        return format_recipe_local(r)

# ============ КОМАНДЫ И КНОПКИ ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Запустить Cook Bro", callback_data="cookbro")],
        [InlineKeyboardButton("/premium Перейти на PRO за 1 ₽", callback_data="premium")],
        [InlineKeyboardButton("/profile Личный кабинет", callback_data="profile")]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Меню:",
        reply_markup=markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/add <название> <YYYY-MM-DD> — добавить продукт\n"
        "/list — показать список\n"
        "/del <id> — удалить по ID\n"
        "Используйте кнопки в меню для навигации."
    )

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /add <название> <YYYY-MM-DD>")
        return
    name = " ".join(context.args[:-1]).strip()
    expiry = context.args[-1].strip()
    if not name:
        await update.message.reply_text("Укажите название продукта.")
        return
    if not is_valid_date(expiry):
        await update.message.reply_text("Дата должна быть в формате YYYY-MM-DD, например 2025-10-01.")
        return
    user_id = update.effective_user.id
    cur.execute("INSERT INTO products (user_id, name, expiry_date, created_at) VALUES (?, ?, ?, ?)",
                (user_id, name, expiry, datetime.utcnow().isoformat(timespec="seconds")))
    conn.commit()
    await update.message.reply_text(f"Добавлено: {name} со сроком до {expiry}")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = cur.execute("SELECT id, name, expiry_date FROM products WHERE user_id = ? ORDER BY expiry_date ASC", (user_id,)).fetchall()
    if not rows:
        await update.message.reply_text("Список пуст. Добавьте продукт: /add <название> <YYYY-MM-DD>")
        return
    lines = [f"{r[0]}. {r[1]} — до {r[2]}" for r in rows]
    await update.message.reply_text("\n".join(lines))

async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Использование: /del <id> (id смотрите в /list)")
        return
    pid = int(context.args[0])
    user_id = update.effective_user.id
    cur.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (pid, user_id))
    conn.commit()
    if cur.rowcount:
        await update.message.reply_text(f"Удалено: запись #{pid}")
    else:
        await update.message.reply_text("Запись не найдена.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Вы написали: {update.message.text}")

# Обработчик callback кнопок
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cookbro":
        await query.edit_message_text("Добро пожаловать в Cook Bro! Выберите команду или кнопку.")
    elif query.data == "premium":
        await query.edit_message_text("Перейти на PRO версию за 1 ₽. Подробнее скоро...")
    elif query.data == "profile":
        await query.edit_message_text("Ваш личный кабинет в разработке.")
    else:
        await query.edit_message_text("Неизвестная команда.")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("del", del_command))

    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    app.run_polling()

if __name__ == "__main__":
    main()
