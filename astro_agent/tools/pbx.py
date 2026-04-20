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
def get_weather_time_and_pbx_call(location: str, call_target_extension: str = "777", iana_timezone: str = "Asia/Tashkent") -> str:
    """Foydalanuvchi birorta mintaqani aytib, unga telefon qilib ob-havo/vaqtni aytishni so'rasa, FAQAT SHU asbobdan foydalaning! LLM matn o'ylamaydi."""
    try:
        data = requests.get(f"https://time.now/developer/api/timezone/{iana_timezone}", timeout=8).json()
        time_result = _format_uz_time(data.get("datetime", ""))
    except:
        time_result = "Vaqtni aniqlab bo'lmadi."
    weather_result = _get_weather(location)
    
    final_msg = f"{location} hududi bo'yicha ma'lumot: {time_result} {weather_result}. Boshqa savollaringiz bormi?"
    
    try:
        with open("/tmp/agi_outbound_msg.txt", "w") as f:
            f.write(final_msg)
        with open("/tmp/agi_outbound_context.txt", "w") as f:
            f.write(f"Maqsad: Foydalanuvchiga ob-havo va vaqt haqida ma'lumot berildi ({location}).")
    except:
        pass

    # Drop Call File for guaranteed Caller ID
    cf = f"""Channel: PJSIP/{call_target_extension}
CallerID: "Astro" <777>
Context: from-internal
Extension: 778
Priority: 1
MaxRetries: 0
"""
    try:
        with open("/tmp/astro_call.call", "w") as f:
            f.write(cf)
        bash_terminal.invoke("sudo mv /tmp/astro_call.call /var/spool/asterisk/outgoing/")
    except:
        return f"Xatolik: Call File yartilmadi"

    return f"Muvaffaqiyatli: {call_target_extension} raqamiga HAQIQIY qo'ng'iroq jo'natildi."

@tool
def make_pbx_call(audio_message: str, call_target_extension: str = "777") -> str:
    """Oddiy muloqot va boshqa mavzular uchun telefon qilish."""
    try:
        with open("/tmp/agi_outbound_msg.txt", "w") as f:
            f.write(f"{audio_message} Savollaringiz bormi?")
        with open("/tmp/agi_outbound_context.txt", "w") as f:
            f.write(f"So'rov: {audio_message}")

        cf = f'Channel: PJSIP/{call_target_extension}\nCallerID: "Astro" <777>\nContext: from-internal\nExtension: 778\nPriority: 1\nMaxRetries: 0\n'
        with open("/tmp/astro_call2.call", "w") as f:
            f.write(cf)
        bash_terminal.invoke("sudo mv /tmp/astro_call2.call /var/spool/asterisk/outgoing/")
    except:
        pass
    return f"Qo'ng'iroq yuborildi."
