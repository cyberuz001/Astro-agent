import requests
from langchain_core.tools import tool
from astro_agent.tools.terminal import bash_terminal

WEATHER_API_KEY = "addd33113ee89bed5030d244960f6f92"


@tool
def pbx_admin(action: str) -> str:
    """Asterisk VoIP PBX tizimiga qilingan turli operatsiyalar (Masalan action='reload')"""
    if action == "reload":
        return bash_terminal.invoke("sudo asterisk -rx 'core reload'")
    return bash_terminal.invoke("sudo asterisk -rx 'core show hints'")


def _format_uz_time(iso_str: str) -> str:
    """Convert ISO datetime to natural 12h Uzbek: 'Hozir 2026-chi yil 20-chi aprel, kechki 9dan 38 daqiqa o'tdi'"""
    try:
        date_part, time_part = iso_str.split("T")
        hm = time_part[:5]
        h, m = hm.split(":")
        hour24 = int(h)
        minute = int(m)

        # 12-hour conversion with time-of-day
        if 5 <= hour24 < 11:
            period = "ertalabki"
        elif 11 <= hour24 < 14:
            period = "tushki"
        elif 14 <= hour24 < 18:
            period = "kunduzi"
        elif 18 <= hour24 < 22:
            period = "kechki"
        else:
            period = "tungi"

        hour12 = hour24 % 12
        if hour12 == 0:
            hour12 = 12

        # Date
        y, mo, d = date_part.split("-")
        months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
                   "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"]
        date_str = f"{y}-chi yil {int(d)}-chi {months[int(mo)-1]}"

        # Time phrase
        if minute == 0:
            time_str = f"{period} soat {hour12} bo'ldi"
        elif minute == 30:
            time_str = f"{period} {hour12}dan yarim soat o'tdi"
        else:
            time_str = f"{period} soat {hour12}dan {minute} daqiqa o'tdi"

        return f"Hozir {date_str}, {time_str}."
    except:
        return f"Vaqt: {iso_str}"


def _get_weather(location: str) -> str:
    """Get weather from OpenWeatherMap in Uzbek"""
    try:
        url = (
            f"http://api.openweathermap.org/data/2.5/weather"
            f"?q={location}&appid={WEATHER_API_KEY}&units=metric&lang=uz"
        )
        data = requests.get(url, timeout=8).json()
        if data.get("cod") == 200:
            temp = round(data["main"]["temp"])
            desc = data["weather"][0]["description"]
            feels = round(data["main"]["feels_like"])
            humidity = data["main"]["humidity"]
            return f"Ob-havo: harorat {temp}°C ({desc}), his qilinadi {feels}°C, namlik {humidity}%."
        return "Ob-havo aniqlanmadi."
    except:
        return "Ob-havo aniqlanmadi."


@tool
def get_weather_and_time(location: str, iana_timezone: str = "Asia/Tashkent") -> str:
    """Ixtiyoriy shahar uchun HOZIRGI ANIQ VAQT, sana va ob-havo. Masalan: location='Toshkent', iana_timezone='Asia/Tashkent'"""
    # Get time
    time_result = ""
    try:
        data = requests.get(
            f"https://time.now/developer/api/timezone/{iana_timezone}",
            timeout=8
        ).json()
        dt_iso = data.get("datetime", "")
        if dt_iso:
            time_result = _format_uz_time(dt_iso)
    except:
        time_result = "Vaqtni aniqlab bo'lmadi."

    # Get weather
    weather_result = _get_weather(location)

    return f"{location}: {time_result} {weather_result}"


@tool
def make_pbx_call(audio_message: str, call_target_extension: str = "777") -> str:
    """Asterisk tizimi orqali berilgan raqamga HAQIQIY telefon qo'ng'iroq qiladi.
    audio_message: telefon orqali aytish kerak bo'lgan matn
    call_target_extension: qo'ng'iroq qilinadigan raqam (masalan 777, 100)"""
    # Write the outbound context message
    try:
        with open("/tmp/agi_outbound_msg.txt", "w") as f:
            f.write(audio_message)
        with open("/tmp/agi_outbound_context.txt", "w") as f:
            f.write(f"Foydalanuvchi so'rovi: {audio_message}")
    except:
        pass

    # Originate call with CallerID=777
    cmd = (
        f'sudo asterisk -rx \''
        f'channel originate Local/{call_target_extension}@from-internal '
        f'application AGI antigravity.py,custom_call\''
    )
    result = bash_terminal.invoke(cmd)
    return f"Qo'ng'iroq yuborildi: {call_target_extension} raqamiga. Natija: {result}"
