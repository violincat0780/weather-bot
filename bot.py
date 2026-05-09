from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import requests

# 🔤 транслитерация (из твоего проекта)
def translit(text):
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh",
        "з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o",
        "п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"ts",
        "ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    return "".join(table.get(c, c) for c in text.lower())

# 🌦 функция погоды
def get_weather(city):

    # если русский — переводим
    if any("а" <= c.lower() <= "я" for c in city):
        city = translit(city)

    # гео
    geo = requests.get(
        f"https://geocoding-api.open-meteo.com/v1/search?name={city}"
    ).json()

    if "results" not in geo:
        return "❌ Город не найден"

    city_data = geo["results"][0]

    # погода
    weather_data = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={city_data['latitude']}&longitude={city_data['longitude']}&current_weather=true"
    ).json()

    if "current_weather" not in weather_data:
        return "❌ Нет данных о погоде"

    weather = weather_data["current_weather"]

    # вода
    water_temp = None
    try:
        water_data = requests.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={city_data['latitude']}&longitude={city_data['longitude']}&hourly=sea_surface_temperature"
        ).json()

        if "hourly" in water_data:
            water_temp = water_data["hourly"]["sea_surface_temperature"][0]
    except:
        pass

    # собираем ответ
    text = f"""📍 {city_data['name']}
🌡 Температура: {weather['temperature']}°C
💨 Ветер: {weather['windspeed']} км/ч"""

    if water_temp:
        text += f"\n🌊 Вода: {water_temp}°C"

    return text


# 📩 обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    result = get_weather(city)
    await update.message.reply_text(result)


# 🚀 запуск бота
app = ApplicationBuilder().token("8273914318:AAFyc_DDcB5hxAohUo2Wc8p3cI4V3Zh4Qbk").build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Бот запущен...")
app.run_polling()
