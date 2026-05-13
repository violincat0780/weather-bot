from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import requests
import threading
from flask import Flask
import os

# ====== транслитерация ======
def translit(text):
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh",
        "з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o",
        "п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"ts",
        "ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    return "".join(table.get(c, c) for c in text.lower())

# ====== формат даты ======
def format_date(date_str):
    parts = date_str.split("-")
    return f"{parts[2]}.{parts[1]}"

# ====== описание погоды ======
def get_weather_info(code):
    if code == 0: return "☀ Ясно"
    elif code <= 3: return "⛅ Облачно"
    elif code < 60: return "🌫 Туман"
    elif code < 70: return "🌧 Дождь"
    elif code < 80: return "❄ Снег"
    return "🌪 Шторм"

# ====== избранное ======
favorites = {}  # user_id: [cities]

# ====== текущая погода ======
def get_weather(city_data):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={city_data['latitude']}&longitude={city_data['longitude']}&current_weather=true"
    data = requests.get(url).json()

    weather = data["current_weather"]
    status = get_weather_info(weather["weathercode"])
    day = "🌞 День" if weather["is_day"] else "🌙 Ночь"

    return f"""📍 {city_data['name']} ({city_data.get('admin1','')}, {city_data.get('country','')})

🌡 {weather['temperature']}°C
💨 {weather['windspeed']} км/ч
{status}
{day}"""

# ====== прогноз ======
def get_forecast(city_data):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={city_data['latitude']}&longitude={city_data['longitude']}&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
    data = requests.get(url).json()

    days = data["daily"]["time"]
    max_t = data["daily"]["temperature_2m_max"]
    min_t = data["daily"]["temperature_2m_min"]

    text = "📅 Прогноз на 3 дня:\n\n"

    for i in range(3):
        text += f"{format_date(days[i])}: {min_t[i]}°C — {max_t[i]}°C\n"

    return text

# ====== старт ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🌦 Погода", "⭐ Избранное"]]

    await update.message.reply_text(
        "👋 Привет! Я покажу погоду 🌍",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ====== основной обработчик ======
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    # 🌦 погода
    if text == "🌦 Погода":
        await update.message.reply_text("Введите город:")
        return

    # ⭐ избранное
    if text == "⭐ Избранное":
        fav = favorites.get(user_id, [])

        if not fav:
            await update.message.reply_text("Нет избранных")
            return

        keyboard = [
            [f"{i+1}. {c['name']} ({c.get('country','')})"]
            for i, c in enumerate(fav)
        ]

        context.user_data["fav_list"] = fav
        context.user_data["step"] = "fav"

        await update.message.reply_text(
            "Выбери город:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # выбор из избранного
    if context.user_data.get("step") == "fav":
        try:
            index = int(text.split(".")[0]) - 1
            city = context.user_data["fav_list"][index]

            context.user_data["last_city"] = city

            await update.message.reply_text(get_weather(city))
            return
        except:
            pass

    # ⭐ добавить
    if text == "⭐ Добавить":
        city = context.user_data.get("last_city")

        if not city:
            await update.message.reply_text("Сначала выбери город")
            return

        favorites.setdefault(user_id, [])

        if city in favorites[user_id]:
            await update.message.reply_text("Уже в избранном")
            return

        favorites[user_id].append(city)
        await update.message.reply_text("⭐ Добавлено!")
        return

    # 📅 прогноз
    if text == "📅 Прогноз":
        city = context.user_data.get("last_city")

        if not city:
            await update.message.reply_text("Сначала выбери город")
            return

        await update.message.reply_text(get_forecast(city))
        return

    # 🏠 меню
    if text == "🏠 Меню":
        keyboard = [["🌦 Погода", "⭐ Избранное"]]

        await update.message.reply_text(
            "Главное меню",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # ====== поиск города ======
    if any("а" <= c.lower() <= "я" for c in text):
        text = translit(text)

    geo = requests.get(
        f"https://geocoding-api.open-meteo.com/v1/search?name={text}"
    ).json()

    if "results" not in geo:
        await update.message.reply_text("❌ Город не найден")
        return

    results = geo["results"]

    # выбор города
    if len(results) > 1:
        context.user_data["cities"] = results
        context.user_data["step"] = "choose"

        keyboard = [
            [f"{i+1}. {c['name']} ({c.get('admin1','')}, {c.get('country','')})"]
            for i, c in enumerate(results[:5])
        ]

        await update.message.reply_text(
            "👇 Выберите город:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    city_data = results[0]
    context.user_data["last_city"] = city_data

    keyboard = [["⭐ Добавить", "📅 Прогноз"], ["🏠 Меню"]]

    await update.message.reply_text(
        get_weather(city_data),
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ====== выбор города из списка ======
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "choose":
        return False

    if "cities" not in context.user_data:
        return False

    try:
        index = int(update.message.text.split(".")[0]) - 1
        city_data = context.user_data["cities"][index]

        context.user_data["last_city"] = city_data
        context.user_data.clear()

        keyboard = [["⭐ Добавить", "📅 Прогноз"], ["🏠 Меню"]]

        await update.message.reply_text(
            get_weather(city_data),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

        return True
    except:
        return False

# ====== главный обработчик ======
async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_choice(update, context):
        return

    await handle(update, context)

# ====== Telegram ======
app = ApplicationBuilder().token("ТВОЙ_ТОКЕН").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))

# ====== Flask ======
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Бот работает!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()

print("Бот запущен...")
app.run_polling(drop_pending_updates=True)
