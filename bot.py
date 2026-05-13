from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import requests
import threading
from flask import Flask
import os

# 🔤 транслитерация
def translit(text):
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh",
        "з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o",
        "п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"ts",
        "ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    return "".join(table.get(c, c) for c in text.lower())

# 🌦 описание погоды
def get_weather_info(code):
    if code == 0:
        return "Ясно ☀"
    elif code <= 3:
        return "Облачно ⛅"
    elif code < 60:
        return "Туман 🌫"
    elif code < 70:
        return "Дождь 🌧"
    elif code < 80:
        return "Снег ❄"
    return "Шторм 🌪"

# 🌦 получение данных
def get_weather_by_coords(city_data):

    weather_data = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={city_data['latitude']}&longitude={city_data['longitude']}&current_weather=true"
    ).json()

    if "current_weather" not in weather_data:
        return "❌ Нет данных о погоде"

    weather = weather_data["current_weather"]

    # 🌊 вода
    water_temp = None
    try:
        water_data = requests.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={city_data['latitude']}&longitude={city_data['longitude']}&hourly=sea_surface_temperature"
        ).json()

        if "hourly" in water_data:
            water_temp = water_data["hourly"]["sea_surface_temperature"][0]
    except:
        pass

    # 📊 данные
    status = get_weather_info(weather["weathercode"])
    day = "День 🌞" if weather["is_day"] else "Ночь 🌙"

    text = f"""📍 {city_data['name']} ({city_data.get('admin1', '')}, {city_data.get('country', '')})

🌡 Температура: {weather['temperature']}°C
💨 Ветер: {weather['windspeed']} км/ч
🌦 {status}
🕒 {day}"""

    if water_temp:
        text += f"\n🌊 Вода: {water_temp}°C"

    return text


# 📩 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\nНапиши название города, и я покажу погоду 🌦"
    )


# 📩 обработка
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text

    # транслит
    if any("а" <= c.lower() <= "я" for c in city):
        city = translit(city)

    geo = requests.get(
        f"https://geocoding-api.open-meteo.com/v1/search?name={city}"
    ).json()

    if "results" not in geo:
        await update.message.reply_text("❌ Город не найден")
        return

    # список городов
    results = geo["results"]

    # если несколько — показываем выбор
    if len(results) > 1:
        context.user_data["cities"] = results

        keyboard = [
            [f"{i+1}. {c['name']} ({c.get('admin1','')}, {c.get('country','')})"]
            for i, c in enumerate(results[:5])
        ]

        await update.message.reply_text(
            "👇 Выберите город:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        context.user_data["step"] = "choose_city"
        return

    # если один — сразу погода
    result = get_weather_by_coords(results[0])
    await update.message.reply_text(result)


# 📍 выбор города
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "choose_city":
        return False

    text = update.message.text

    try:
        index = int(text.split(".")[0]) - 1
        city_data = context.user_data["cities"][index]

        result = get_weather_by_coords(city_data)
        await update.message.reply_text(result)

        context.user_data.clear()
        return True
    except:
        return False


# 📩 общий обработчик
async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_choice(update, context):
        return

    await handle_message(update, context)


# ===== Telegram =====

app = ApplicationBuilder().token("8273914318:AAFyc_DDcB5hxAohUo2Wc8p3cI4V3Zh4Qbk").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))


# ===== Flask (Render) =====

app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Бот работает!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()


# 🚀 запуск
print("Бот запущен...")
app.run_polling(drop_pending_updates=True)
