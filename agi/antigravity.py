#!/usr/bin/env python3
"""
ASTRO AGI Voice Engine — Asterisk Gateway Interface
Handles voice calls with AI-powered conversation in Uzbek
"""
import sys, os, time, json, subprocess, wave, signal
import requests
from datetime import datetime, timedelta

CLOUD_KEY = ""  # Set via install.sh or config
GEMMA_URL = "https://openrouter.ai/api/v1/chat/completions"
WEATHER_API_KEY = ""

BRIDGE_FILE = "/tmp/voice_bridge.txt"
EDGE_TTS = "/home/user/astro-agent/venv/bin/edge-tts"
FFMPEG = "/usr/bin/ffmpeg"
MODEL_PATH = "/usr/share/asterisk/vosk-model"
CONTEXT_FILE = "/tmp/agi_outbound_context.txt"

OUTBOUND_MODE = ""
if len(sys.argv) > 1: OUTBOUND_MODE = sys.argv[1]

active_mission = False
full_transcript = []

try: signal.signal(signal.SIGHUP, signal.SIG_IGN)
except: pass

# Load API keys from astro config if available
try:
    import pathlib
    cfg_path = pathlib.Path.home() / ".astro" / "config.json"
    if cfg_path.exists():
        _cfg = json.loads(cfg_path.read_text())
        _prov = _cfg.get("providers", {}).get(_cfg.get("provider", "openrouter"), {})
        CLOUD_KEY = _prov.get("key", CLOUD_KEY)
        GEMMA_URL = _prov.get("url", GEMMA_URL)
        WEATHER_API_KEY = _cfg.get("weather_api_key", WEATHER_API_KEY)
except: pass

def get_voice():
    try:
        v = open("/tmp/astro_voice.cfg").read().strip()
        if v: return v
    except: pass
    return "uz-UZ-MadinaNeural"

def broadcast(text, role="User"):
    try:
        open(BRIDGE_FILE, "a").close()
        os.chmod(BRIDGE_FILE, 0o666)
        with open(BRIDGE_FILE, "a") as f:
            f.write(f"[{role}] {text}\n")
            f.flush()
    except: pass

def agi_send(cmd):
    try:
        sys.stdout.write(cmd + "\n")
        sys.stdout.flush()
        return sys.stdin.readline().strip()
    except: return ""

def say_uz(text):
    tmp_mp3 = "/tmp/agi_tts.mp3"
    tmp_wav = "/tmp/agi_tts.wav"
    voice = get_voice()
    try:
        subprocess.run([EDGE_TTS, "--voice", voice, "--rate", "+35%", "--volume", "+100%",
                       "--text", text, "--write-media", tmp_mp3],
                      check=True, timeout=20, capture_output=True)
        subprocess.run([FFMPEG, "-y", "-i", tmp_mp3, "-ar", "8000", "-ac", "1",
                       "-acodec", "pcm_s16le", tmp_wav],
                      check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=10)
        agi_send('STREAM FILE /tmp/agi_tts ""')
    except Exception as e:
        broadcast(f"TTS xato: {e}", "SYSTEM")

def transcribe(wav_path):
    from vosk import Model, KaldiRecognizer
    if not os.path.exists(MODEL_PATH) or not os.path.exists(wav_path): return ""
    try:
        if os.path.getsize(wav_path) < 1000: return ""
        wf = wave.open(wav_path, "rb")
        model = Model(MODEL_PATH)
        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)
        while True:
            data = wf.readframes(4000)
            if len(data) == 0: break
            rec.AcceptWaveform(data)
        wf.close()
        return json.loads(rec.FinalResult()).get("text", "")
    except Exception as e:
        broadcast(f"STT Error: {e}", "SYSTEM")
        return ""

def get_weather_and_time(location, iana_timezone="Asia/Tashkent"):
    time_str = ""
    try:
        if "time_now_offset" not in locals():
            tz_req = requests.get(f"https://time.now/developer/api/timezone/{iana_timezone}", timeout=5).json()
            if "datetime" in tz_req:
                dt_iso = tz_req["datetime"]
                # Manual parsing: 2026-04-17T16:13:00.123456+05:00
                date_part, time_part = dt_iso.split("T")
                time_part = time_part[:5] # "16:13"
                y, m, d = date_part.split("-")
                months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"]
                time_str = f"{y}-yil {int(d)}-{months[int(m)-1]}, soat {time_part}"
    except:
        time_str = "Vaqtni aniqlab bo'lmadi."

    try:
        api_key = config.get("weather_api_key", "") if "config" in globals() else WEATHER_API_KEY
        if api_key:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric&lang=uz"
            data = requests.get(url, timeout=8).json()
            if data.get("cod") == 200:
                temp = data["main"]["temp"]
                desc = data["weather"][0]["description"]
                weather_str = f"Ob-havo: harorat {temp}°C, {desc}."
                return f"{location}: {time_str}. {weather_str}"
            else:
                return f"{location}: {time_str}. Ob-havo aniqlanmadi."
        return f"{location}: {time_str}."
    except Exception as e:
        return f"Xato: {e}"

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()[:4000]
    except Exception as e: return f"Xato: {e}"

TOOLS = [
    {"type": "function", "function": {"name": "run_terminal", "description": "Tizim buyruqlari", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "get_weather_and_time", "description": "Ixtiyoriy shahar", "parameters": {"type": "object", "properties": {"location": {"type": "string"}, "iana_timezone": {"type": "string"}}, "required": ["location", "iana_timezone"]}}},
    {"type": "function", "function": {"name": "save_user_name", "description": "Foydalanuvchining ismini yoki familiyasini eslab qolish uchun kiritish. Agar kishi o'z ismini aytsa zudlik bilan ushbu API ni ishlating.", "parameters": {"type": "object", "properties": {"user_name": {"type": "string"}}, "required": ["user_name"]}}}
]

def save_name_to_file(name):
    try:
        with open("/tmp/astro_caller_name.txt", "w") as f:
            f.write(name)
        os.chmod("/tmp/astro_caller_name.txt", 0o666)
    except: pass
    return f"Ism eslab qolindi: {name}"

current_user = ""
try:
    with open("/tmp/astro_caller_name.txt", "r") as f:
        current_user = f.read().strip()
except: pass

user_context = f"\nFoydalanuvchining ismi: {current_user}" if current_user else "\nSiz foydalanuvchining ismini bilmaysiz. Suhbat orasida muloyimlik bilan bilintirmasdan ismini yoki familiyasini so'rab oling. Agar ismini aytsa SEZDIRMASDAN darhol 'save_user_name' funksiyasidan foydalanib yozib oling."

BASE_PROMPT = f"""Siz Astro — oliy darajadagi Avtonom Voice AI Agentsiz. Telefon qo'ng'irogidasiz! 
1. Jumlalar qisqa, tushunarli va odamdek sof O'zbek tilida bo'lsin. 
2. 'Rahmat' desa xayrlashib tugating.{user_context}"""

def main():
    global active_mission, full_transcript
    while True:
        if sys.stdin.readline().strip() == "": break

    try:
        open(BRIDGE_FILE, "a").close()
        os.chmod(BRIDGE_FILE, 0o666)
    except: pass

    agi_send("ANSWER")
    broadcast("--- Kiruvchi/Chiquvchi Qo'ng'iroq ---", "SYSTEM")

    hist = []

    if OUTBOUND_MODE == "custom_call":
        intro = ""
        try:
            with open("/tmp/agi_outbound_msg.txt", "r") as f: intro = f.read().strip()
        except: pass
        if not intro: intro = "Salom!"

        mission_goal = ""
        try:
            with open(CONTEXT_FILE, "r") as f: mission_goal = f.read().strip()
        except: pass

        if mission_goal:
            active_mission = True
            hist.append({"role":"system","content":f"Siz Astro AI siz. Raqamga QO'NG'IROQ QILDINGIZ!\nMAQSAD:\n{mission_goal}\nMaqsad yakunlangach xayrlashing!"})
        else:
            hist.append({"role":"system","content":BASE_PROMPT})

        say_uz(intro)
        broadcast(intro, "Agent")
        hist.append({"role":"assistant","content":intro})
    else:
        hist.append({"role":"system","content":BASE_PROMPT})
        say_uz("Assalomu alaykum! Men Astro yordamchisiman. Eshitaman!")
        broadcast("Assalomu alaykum! Men Astro man. Eshitaman!", "Agent")
        hist.append({"role":"assistant","content":"Assalomu alaykum! Eshitaman!"})

    silence_count = 0
    for _ in range(25):
        wav_path = "/tmp/agi_voice_input.wav"
        try: os.remove(wav_path)
        except: pass

        agi_status = agi_send('RECORD FILE /tmp/agi_voice_input wav "#" 10000 0 BEEP s=4')
        if not agi_status: break

        user_text = transcribe(wav_path).lower()
        if not user_text.strip():
            silence_count += 1
            if silence_count >= 2:
                say_uz("Hech kim gapirmadi, sog bo'ling.")
                broadcast("Sog bo'ling.", "Agent")
                break
            continue

        silence_count = 0
        broadcast(user_text, "User")
        hist.append({"role":"user","content":user_text})
        full_transcript.append(f"Foydalanuvchi: {user_text}")

        hangup_words = ["hayr","xayr","rahmat","sog","stop","tugat","qoy"]
        if any(w in user_text for w in hangup_words) and len(user_text.split()) < 4:
            say_uz("Sog bo'ling!")
            broadcast("Sog bo'ling!", "Agent")
            full_transcript.append("Agent: Sog bo'ling!")
            break

        for __ in range(2):
            try:
                r = requests.post(GEMMA_URL, headers={"Authorization":"Bearer "+CLOUD_KEY},
                    json={"model":"google/gemini-2.0-flash-lite-001","messages":hist,
                          "max_tokens":512,"temperature":0.2,"tools":TOOLS}, timeout=30).json()
                if "choices" not in r: break
                m = r["choices"][0]["message"]

                if m.get("tool_calls"):
                    hist.append(m)
                    for tc in m["tool_calls"]:
                        fn = tc["function"]["name"]
                        args = json.loads(tc["function"]["arguments"])
                        broadcast(f"[⚙️ {fn}]", "SYSTEM")
                        if fn == "run_terminal": res = run_cmd(args.get("command",""))
                        elif fn == "get_weather_and_time": res = get_weather_and_time(args.get("location","Tashkent"), args.get("iana_timezone", "Asia/Tashkent"))
                        elif fn == "save_user_name": res = save_name_to_file(args.get("user_name", ""))
                        else: res = "OK"
                        hist.append({"role":"tool","tool_call_id":tc["id"],"name":fn,"content":str(res)[:1000]})
                    continue

                ans = m.get("content","")
                if ans:
                    hist.append({"role":"assistant","content":ans})
                    broadcast(ans, "Agent")
                    say_uz(ans)
                    full_transcript.append(f"Agent: {ans}")
                break
            except Exception as e:
                broadcast(f"AI Xato: {e}", "SYSTEM")
                break

    agi_send("HANGUP")
    if active_mission:
        try:
            with open("/tmp/agi_mission_result.txt","w") as f:
                f.write("\n".join(full_transcript))
            os.chmod("/tmp/agi_mission_result.txt", 0o666)
        except: pass

if __name__ == "__main__":
    main()
