#!/usr/bin/env python3
import sys
import os

# Server-specific Virtual Environment Auto-Boot Sequence
SERVER_PYTHON = "/home/user/gemma-telegram-bot/venv/bin/python3"
if os.path.exists(SERVER_PYTHON) and sys.executable != SERVER_PYTHON:
    os.execl(SERVER_PYTHON, SERVER_PYTHON, *sys.argv)

# Provide fallback syspath to root application node
sys.path.insert(0, "/home/user/astro-agent")

try:
    from astro_agent.core.config import ensure_sudo
except ModuleNotFoundError:
    print("\\033[91mXato: 'astro_agent' modul papkasi topilmadi yoki 'textual' o'rnatilmagan!\\033[0m")
    sys.exit(1)

def main():
    # 1. Ask securely for sudo if not cached
    ensure_sudo()
    
    # 2. Launch Textual Dashboard natively
    from astro_agent.ui.tui import AstroApp
    app = AstroApp()
    app.run()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        main()
    else:
        print("\\033[36m◆ ASTRO V2.1 (Multi-Agent Orchestrator & TUI Protocol)\\033[0m")
        print("Barcha komponentlar modul yordamida tashkil qilindi.")
        print("Ishga tushirish uchun yozing: astro run")
