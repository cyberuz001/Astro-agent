import requests
from langchain_core.tools import tool
from astro_agent.tools.terminal import bash_terminal


@tool
def pbx_admin(action: str) -> str:
    """Asterisk VoIP PBX tizimiga qilingan turli operatsiyalar (Masalan action='reload')"""
    if action == "reload":
        return bash_terminal.invoke("sudo asterisk -rx 'core reload'")
    return bash_terminal.invoke("sudo asterisk -rx 'core show hints'")


@tool
def get_weather_and_time(location: str, iana_timezone: str = "Asia/Tashkent") -> str:
    """Ixtiyoriy shahar yoki davlat uchun HOZIRGI ANIQ VAQT va sana. Masalan: location='Toshkent', iana_timezone='Asia/Tashkent'"""
    time_str = "Noma'lum"
    try:
        data = requests.get(
            f"https://time.now/developer/api/timezone/{iana_timezone}",
            timeout=8
        ).json()
        dt_iso = data.get("datetime", "")
        if dt_iso:
            # Parse: "2026-04-20T22:05:00.123456+05:00"
            date_part, time_part = dt_iso.split("T")
            time_hm = time_part[:5]  # "22:05"
            y, m, d = date_part.split("-")
            months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
                       "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"]
            time_str = f"{y}-yil {int(d)}-{months[int(m)-1]}, soat {time_hm}"
    except:
        pass
    return f"{location} vaqti: {time_str}"


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

    # Originate call FROM registered endpoint 100 TO the target extension
    cmd = (
        f"sudo asterisk -rx '"
        f"channel originate Local/{call_target_extension}@from-internal "
        f"application AGI antigravity.py,custom_call'"
    )
    result = bash_terminal.invoke(cmd)
    return f"Qo'ng'iroq yuborildi: {call_target_extension} raqamiga. Asterisk javobi: {result}"
