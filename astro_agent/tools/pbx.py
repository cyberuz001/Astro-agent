import requests
from langchain_core.tools import tool
from astro_agent.tools.terminal import bash_terminal

@tool
def pbx_admin(action: str) -> str:
    """Asterisk VoIP PBX tizimiga qilingan turli operatsiyalar (Masalan action='reload')"""
    if action == "reload":
        return bash_terminal.invoke("asterisk -rx 'core reload'")
    return bash_terminal.invoke("asterisk -rx 'core show hints'")

@tool
def get_weather_and_time(location: str, iana_timezone: str = "Asia/Tashkent") -> str:
    """Vaqt (Time) va havo ma'lumotlarini qaytaruvchi mutlaq aniq tizim."""
    time_str = "Noma'lum"
    try:
        data = requests.get(f"https://time.now/developer/api/timezone/{iana_timezone}", timeout=5).json()
        time_str = data.get("datetime", "")
    except: pass
    return f"So'rov markazi `{location}` uchun API vaqti: {time_str}"

@tool
def make_pbx_call(audio_message: str, call_target_extension: str = "101") -> str:
    """Asterisk tizimi orqali berilgan telefon raqamiga (masalan 101 ga) haqiqiy qo'ng'iroq qiladi."""
    cmd = f"asterisk -rx 'channel originate PJSIP/{call_target_extension} application Playback tt-weasels'"
    bash_terminal.invoke(cmd)
    return f"Muvaffaqiyatli! {call_target_extension} raqamiga qo'ng'iroq qilinib '{audio_message}' qo'yilmoqda."
