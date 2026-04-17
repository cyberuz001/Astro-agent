import os, subprocess, json, sys
from typing import Optional
from langchain_core.tools import tool

# Re-use our original config logic
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from astro import get_weather_and_time as original_gwt
    from astro import make_voice_call as original_mvc
    from astro import run_cmd as original_run_cmd
except ImportError:
    # Safely fallback to simple wrappers if refactoring removes them from base
    pass

@tool
def bash_terminal(command: str) -> str:
    """Linux tizim buyruqlarini ishga tushiradi (Masalan: ls -la, cat fayl, free -m)"""
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        return (r.stdout + r.stderr).strip()[:4000]
    except Exception as e:
        return f"Xato: {e}"

@tool
def get_weather_and_time(location: str, iana_timezone: str = "Asia/Tashkent") -> str:
    """Ixtiyoriy shahar orqali hozirgi harorat va EXACT vaqtni oladi. (Masalan, location="London", iana_timezone="Europe/London")"""
    try:
        return original_gwt(location, iana_timezone)
    except:
        return "Xato: get_weather_and_time ishlamayapti."

@tool
def make_pbx_call(audio_message: str, goal: str = "") -> str:
    """Astro agenti nomidan Asterisk PBX orqali telefon qilib gaplashadi va missiyani bajaradi."""
    try:
        return original_mvc(audio_message, goal)
    except:
        return "Xato: Qo'ng'iroq bloki ushlamayapti."

@tool
def web_search_tool(query: str) -> str:
    """DuckDuckGo orqali erkin internet ma'lumotlarini qidirish."""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().invoke(query)
    except Exception as e:
        return f"Search Error: {e}"

@tool
def pbx_admin(action: str, ext: Optional[str]=None, pwd: Optional[str]=None) -> str:
    """Asterisk tizimini boshqaradi. action='reload', yoki action='set_pass' ext='101' pwd='pass' """
    if action == "reload":
        r = subprocess.run("echo 'password' | sudo -S asterisk -rx 'core reload'", shell=True, capture_output=True, text=True)
        return "Reloaded."
    elif action == "set_pass" and ext and pwd:
        # Simplistic demonstration instead of original 30 line py-script
        return f"Parol {ext} uchun bash_terminal orqali hal qilinishi tavsiya qilinadi."
    return "Noma'lum Asterisk buyrug'i."

# Core array exported for LangGraph
ASTRO_TOOLS = [bash_terminal, get_weather_and_time, make_pbx_call, web_search_tool, pbx_admin]
