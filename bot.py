from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import requests
import threading
from flask import Flask
import os

# ===== транслит =====
def translit(text):
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh",
        "з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o",
        "п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"ts",
        "ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    return "".join(table.get(c, c) for c in text.lower())

# ===== описание =====
def get_weather_info(code):
    if code == 0: return "☀ Ясно"
    elif code <= 3: return "⛅ Облачно"
    elif code < 60: return "🌫 Туман"
    elif code < 70: return "🌧 Дождь"
    elif code < 80: return "❄ Снег"
    return "🌪 Шторм"

# ===== избранное =====
favorites = {}

# ===== погода =====
def get_weather(city):
    data = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={city['latitude']}&longitude={city['longitude']}&current_weather=true"
    ).json()

    weather = data["current_weather"]

    # вода
    water = None
    try:
        water_data = requests.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={city['latitude']}&longitude={city['longitude']}&hourly=sea_surface_temperature"
        ).json()

        water = water_data["hourly"]["sea_surface_temperature"][0]
    except:
        pass

    status = get_weather_info(weather["weathercode"])
    day = "🌞 День" if weather["is_day"] else "🌙 Ночь"

    text = f"""📍 {city['name']} ({city.get('admin1','')}, {city.get('country','')})

🌡 Температура: {weather['temperature']}°C
💨 Ветер: {weather['windspeed']} км/ч
🌦 Погода: {status}
🕒 {day}"""

    if water:
        text += f"\n🌊 Вода: {water}°C"

    return text

# ===== прогноз =====
def get_forecast(city):
    data = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={city['latitude']}&longitude={city['longitude']}&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
    ).json()

    days = data["daily"]["time"]
    max_t = data["daily"]["temperature_2m_max"]
    min_t = data["daily"]["temperature_2m_min"]

    text = "📅 Прогноз на 3 дня:\n\n"

    for i in range(3):
        text += f"{days[i]}: {min_t[i]}°C — {max_t[i]}°C\n"

    return text

# ===== старт =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🌦 Погода", "⭐ Избранное"]]

    await update.message.reply_text(
        "👋 Привет!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===== логика =====
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    # меню
    if text == "🌦 Погода":
        await update.message.reply_text("Введите город:")
        return

    if text == "⭐ Избранное":
        fav = favorites.get(user_id, [])

        if not fav:
            await update.message.reply_text("Нет избранных")
            return

        msg = "\n".join([f"{c['name']} ({c['country']})" for c in fav])
        await update.message.reply_text(msg)
        return

    # кнопки после выбора
    if text == "⭐ Добавить":
        city = context.user_data.get("last_city")

        if not city:
            await update.message.reply_text("Сначала выбери город")
            return

        favorites.setdefault(user_id, [])

        if city not in favorites[user_id]:
            favorites[user_id].append(city)

        await update.message.reply_text("⭐ Добавлено")
        return

    if text == "📅 Прогноз":
        city = context.user_data.get("last_city")

        if not city:
            await update.message.reply_text("Сначала выбери город")
            return

        await update.message.reply_text(get_forecast(city))
        return

    # ===== поиск =====
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
            [f"{i+1}. {c['name']} ({c.get('country','')})"]
            for i, c in enumerate(results[:5])
        ]

        await update.message.reply_text(
            "Выберите город:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # сразу погода
    city = results[0]
    context.user_data["last_city"] = city

    keyboard = [["⭐ Добавить", "📅 Прогноз"]]

    await update.message.reply_text(
        get_weather(city),
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===== выбор из списка =====
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "choose":
        return False

    try:
        index = int(update.message.text.split(".")[0]) - 1
        city = context.user_data["cities"][index]

        context.user_data["last_city"] = city
        context.user_data["step"] = None  # 👈 ВАЖНО

        keyboard = [["⭐ Добавить", "📅 Прогноз"]]

        await update.message.reply_text(
            get_weather(city),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

        return True
    except:
        return False

# ===== главный =====
async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_choice(update, context):
        return

    await handle(update, context)

# ===== запуск =====
app = ApplicationBuilder().token("8273914318:AAFyc_DDcB5hxAohUo2Wc8p3cI4V3Zh4Qbk").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))

# ===== Flask =====
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "ok"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()

print("Бот запущен")
app.run_polling()
