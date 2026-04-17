import subprocess
from langchain_core.tools import tool
from astro_agent.core.config import config, decrypt_pwd

def get_pwd() -> str:
    return decrypt_pwd(config.get("sudo_secure"))

@tool
def bash_terminal(command: str) -> str:
    """Linux tizimini to'liq boshqarish. Buyruqlarni xuddi bash da yozilgandek yozing (ls -la, free -m)"""
    if "sudo " in command and "-S" not in command:
        command = command.replace("sudo ", f"echo '{get_pwd()}' | sudo -S ")
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        if not out:
            return "Buyruq muvaffaqiyatli bajarildi (hech qanday matn qaytmadi)."
        return out[:4000]
    except Exception as e:
        return f"Xato: {e}"
