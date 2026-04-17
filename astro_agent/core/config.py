import json
import os
import getpass
import base64
from pathlib import Path

# Paths
CONFIG_DIR = Path.home() / ".astro"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEY_FILE = CONFIG_DIR / ".secret.key"

DEFAULT_CONFIG = {
    "provider": "openrouter",
    "providers": {
        "openrouter": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "key": "",
            "model": "google/gemini-2.0-flash-lite-001"
        }
    },
    "weather_api_key": ""
}

def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            # merge
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

def get_fernet():
    try:
        from cryptography.fernet import Fernet
        if not KEY_FILE.exists():
            KEY_FILE.write_bytes(Fernet.generate_key())
        return Fernet(KEY_FILE.read_bytes())
    except ImportError:
        return None

def encrypt_pwd(raw: str) -> dict:
    f = get_fernet()
    if f:
        return {"enc": f.encrypt(raw.encode()).decode("utf-8")}
    return {"b64": base64.b64encode(raw.encode()).decode("utf-8")}

def decrypt_pwd(data: dict) -> str:
    if not data:
        return ""
    if "enc" in data:
        f = get_fernet()
        if f:
            return f.decrypt(data["enc"].encode()).decode("utf-8")
    elif "b64" in data:
        return base64.b64decode(data["b64"].encode()).decode("utf-8")
    return ""

def ensure_sudo():
    cfg = load_config()
    if "sudo_secure" not in cfg:
        print("\\033[93m[ ASTRO SECURE BOOT ]\\033[0m")
        print("Tizimni avtonom boshqarish uchun Administrator (sudo) parolini aniqlash...")
        pwd = getpass.getpass("Sudo parol: ")
        cfg["sudo_secure"] = encrypt_pwd(pwd)
        save_config(cfg)
        print("✅ Parol AES shifrida himoyalandi.\\n")
    return decrypt_pwd(cfg.get("sudo_secure"))

config = load_config()
